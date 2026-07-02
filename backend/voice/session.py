"""
voice/session.py — Voice Session State Machine (Phase 2)
==========================================================
Manages the lifecycle of a voice interaction session with
explicit state transitions and retry tracking.

Requirements Covered:
  R-33: Operator fallback after repeated failures
  R-39: Operator remains in the confirmation loop

Design Decisions:
  - In-memory dictionary for session storage (single-worker uvicorn).
    If multi-worker deployment is needed, swap to the PostgreSQL
    VoiceSession model (see models.py).
  - Explicit state enum prevents invalid transitions.
  - max_retries=3 for service number validation; after that the
    session transitions to OPERATOR_FALLBACK to avoid infinite loops.
  - Sessions auto-expire after 30 minutes to prevent memory leaks.
  - Phase 3 compatibility: the session abstraction is transport-agnostic
    so it can later be driven by telephony events (DTMF, SIP) without
    changing the state machine logic.
"""

import uuid
import time
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

logger = logging.getLogger("voice.session")

# ─────────────────────────────────────────────────────────────────────
# Session states
# ─────────────────────────────────────────────────────────────────────

class SessionState(str, Enum):
    """Possible states of a voice interaction session."""
    GREETING                   = "GREETING"
    CAPTURING_SERVICE_NUMBER   = "CAPTURING_SERVICE_NUMBER"
    CONFIRMING_SERVICE_NUMBER  = "CONFIRMING_SERVICE_NUMBER"
    CAPTURING_COMPLAINT        = "CAPTURING_COMPLAINT"
    CLASSIFYING_COMPLAINT      = "CLASSIFYING_COMPLAINT"
    OPERATOR_REVIEW            = "OPERATOR_REVIEW"
    OPERATOR_FALLBACK          = "OPERATOR_FALLBACK"
    TICKET_CREATED             = "TICKET_CREATED"
    COMPLETED                  = "COMPLETED"
    ERROR                      = "ERROR"


# Maximum retries before falling back to manual operator entry
MAX_SERVICE_NUMBER_RETRIES = 3

# Session TTL in seconds (30 minutes)
SESSION_TTL_SECONDS = 1800


@dataclass
class VoiceSessionData:
    """In-memory representation of a voice session."""
    session_id: str
    state: SessionState
    created_at: float                        # time.time()
    updated_at: float

    # Complainant data (populated progressively)
    service_no: Optional[str] = None
    complainant_name: Optional[str] = None
    complainant_unit: Optional[str] = None
    complainant_rank: Optional[str] = None

    # Retry tracking for service number validation
    svc_retries: int = 0

    # Complaint data
    complaint_text: Optional[str] = None
    stt_confidence: float = 0.0
    stt_language: Optional[str] = None

    # Classification results (from Phase 1 pipeline)
    intake_id: Optional[int] = None
    fault_type_proposal: Optional[str] = None
    severity_proposal: Optional[str] = None
    candidates: List[Dict[str, Any]] = field(default_factory=list)

    # Final ticket
    ticket_number: Optional[str] = None

    # Logging / metrics
    stt_latency_ms: float = 0.0
    tts_latency_ms: float = 0.0
    total_stt_calls: int = 0
    total_tts_calls: int = 0
    errors: List[str] = field(default_factory=list)


class VoiceSessionManager:
    """
    Thread-safe in-memory session store with automatic expiration.

    For Phase 3 (multi-worker telephony), replace _sessions dict with
    a Redis or PostgreSQL-backed store using the same interface.
    """

    def __init__(self):
        self._sessions: Dict[str, VoiceSessionData] = {}

    def create_session(self) -> VoiceSessionData:
        """Create a new voice session in GREETING state."""
        self._cleanup_expired()

        session_id = str(uuid.uuid4())
        now = time.time()

        session = VoiceSessionData(
            session_id=session_id,
            state=SessionState.GREETING,
            created_at=now,
            updated_at=now,
        )
        self._sessions[session_id] = session
        logger.info("Session created: %s", session_id)
        return session

    def get_session(self, session_id: str) -> Optional[VoiceSessionData]:
        """Retrieve a session by ID, or None if expired/missing."""
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if time.time() - session.created_at > SESSION_TTL_SECONDS:
            logger.info("Session expired: %s", session_id)
            del self._sessions[session_id]
            return None
        return session

    def transition(
        self,
        session_id: str,
        new_state: SessionState,
        **kwargs,
    ) -> VoiceSessionData:
        """
        Transition a session to a new state, updating any provided fields.

        Raises ValueError if the session doesn't exist or the transition
        is not valid.
        """
        session = self.get_session(session_id)
        if session is None:
            raise ValueError(f"Session not found or expired: {session_id}")

        # Validate transition
        if not self._is_valid_transition(session.state, new_state):
            raise ValueError(
                f"Invalid state transition: {session.state.value} → {new_state.value}"
            )

        old_state = session.state
        session.state = new_state
        session.updated_at = time.time()

        # Apply any additional field updates
        for key, value in kwargs.items():
            if hasattr(session, key):
                setattr(session, key, value)

        with open("transition_debug.log", "a") as f:
            f.write(f"[{time.time()}] Session {session_id}: {old_state.value} -> {new_state.value}\n")

        logger.info(
            "Session %s: %s → %s",
            session_id, old_state.value, new_state.value,
        )
        return session

    def increment_svc_retries(self, session_id: str) -> int:
        """
        Increment the service number retry counter.
        Returns the new retry count.
        """
        session = self.get_session(session_id)
        if session is None:
            raise ValueError(f"Session not found: {session_id}")

        session.svc_retries += 1
        session.updated_at = time.time()

        logger.info(
            "Session %s: svc_retries=%d / %d",
            session_id, session.svc_retries, MAX_SERVICE_NUMBER_RETRIES,
        )
        return session.svc_retries

    def should_fallback(self, session_id: str) -> bool:
        """Check if retries have exceeded the maximum threshold."""
        session = self.get_session(session_id)
        if session is None:
            return True
        return session.svc_retries >= MAX_SERVICE_NUMBER_RETRIES

    def delete_session(self, session_id: str) -> None:
        """Remove a session from the store."""
        self._sessions.pop(session_id, None)
        logger.info("Session deleted: %s", session_id)

    def get_active_count(self) -> int:
        """Return the number of active (non-expired) sessions."""
        self._cleanup_expired()
        return len(self._sessions)

    # ------------------------------------------------------------------
    # Transition validation matrix
    # ------------------------------------------------------------------
    @staticmethod
    def _is_valid_transition(current: SessionState, target: SessionState) -> bool:
        """
        Enforce the state machine transition rules.

        The matrix is intentionally permissive for ERROR transitions
        (any state can go to ERROR) and for OPERATOR_FALLBACK (which
        can go to OPERATOR_REVIEW when the operator takes over).
        """
        VALID_TRANSITIONS = {
            SessionState.GREETING: {
                SessionState.CAPTURING_SERVICE_NUMBER,
                SessionState.ERROR,
            },
            SessionState.CAPTURING_SERVICE_NUMBER: {
                SessionState.CONFIRMING_SERVICE_NUMBER,   # Valid number
                SessionState.CAPTURING_SERVICE_NUMBER,    # Retry (self-loop)
                SessionState.OPERATOR_FALLBACK,           # Max retries
                SessionState.ERROR,
            },
            SessionState.CONFIRMING_SERVICE_NUMBER: {
                SessionState.CAPTURING_COMPLAINT,         # Confirmed
                SessionState.CAPTURING_SERVICE_NUMBER,    # Rejected → re-capture
                SessionState.ERROR,
            },
            SessionState.CAPTURING_COMPLAINT: {
                SessionState.CLASSIFYING_COMPLAINT,
                SessionState.OPERATOR_REVIEW,             # Direct skip (operator typed)
                SessionState.ERROR,
            },
            SessionState.CLASSIFYING_COMPLAINT: {
                SessionState.OPERATOR_REVIEW,
                SessionState.ERROR,
            },
            SessionState.OPERATOR_REVIEW: {
                SessionState.TICKET_CREATED,
                SessionState.CAPTURING_COMPLAINT,         # Operator wants re-do
                SessionState.ERROR,
            },
            SessionState.OPERATOR_FALLBACK: {
                SessionState.OPERATOR_REVIEW,             # Legacy override
                SessionState.CAPTURING_COMPLAINT,         # After successful manual entry of service number
                SessionState.CAPTURING_SERVICE_NUMBER,    # Retry with voice
                SessionState.ERROR,
            },
            SessionState.TICKET_CREATED: {
                SessionState.COMPLETED,
                SessionState.ERROR,
            },
            SessionState.COMPLETED: set(),                # Terminal state
            SessionState.ERROR: set(),                    # Terminal state
        }

        allowed = VALID_TRANSITIONS.get(current, set())
        return target in allowed

    # ------------------------------------------------------------------
    # Housekeeping
    # ------------------------------------------------------------------
    def _cleanup_expired(self) -> None:
        """Remove sessions older than SESSION_TTL_SECONDS."""
        now = time.time()
        expired = [
            sid for sid, s in self._sessions.items()
            if now - s.created_at > SESSION_TTL_SECONDS
        ]
        for sid in expired:
            del self._sessions[sid]
        if expired:
            logger.info("Cleaned up %d expired sessions", len(expired))
