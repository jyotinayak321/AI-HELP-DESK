"""
voice/complaint_processor.py — Shared Complaint Processing Pipeline
===================================================================
Executes the Phase 1 AI pipeline for a transcribed complaint. Shared
between the REST API (routers/voice.py POST /complaint) and the
LiveKit WebRTC audio adapter (livekit_bridge/adapter.py), so both
transports run the exact same classify -> Intake -> candidates logic.

Responsibilities:
- LLM guardrail (verify_and_correct_text)
- Embedding extraction
- Fault type & severity classification
- Application candidate search & dependency expansion
- Intake record creation
- Voice session state transition
- Prompt generation
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from sqlmodel import Session

from models import Application, Intake
from voice.session import VoiceSessionManager, SessionState
from voice.prompts import render_dynamic_prompt
from services.llm_client import verify_and_correct_text
from services.embedder import TextEmbedder
from services.classifier import TicketClassifier
from services.search import ApplicationSearchEngine
from services.dependencies import ApplicationDependencyEngine
from voice_schemas import VoiceCandidateApp

logger = logging.getLogger("voice.complaint_processor")

# Lazy-loaded singletons — same instances used across every call, matching
# the pattern already used for _stt_engine/_tts_engine in routers/voice.py.
_embedder: Optional[TextEmbedder] = None
_classifier: Optional[TicketClassifier] = None
_search_engine: Optional[ApplicationSearchEngine] = None
_dependency_engine: Optional[ApplicationDependencyEngine] = None


def _get_services():
    global _embedder, _classifier, _search_engine, _dependency_engine
    if _embedder is None:
        _embedder = TextEmbedder()
        _classifier = TicketClassifier()
        _search_engine = ApplicationSearchEngine()
        _dependency_engine = ApplicationDependencyEngine()
    return _embedder, _classifier, _search_engine, _dependency_engine


@dataclass
class ComplaintProcessingResult:
    """The structured result returned to the caller (REST or LiveKit adapter)."""
    status: str                 # "rejected" or "accepted"
    prompt_text: str            # TTS/display response text
    corrected_transcript: str
    intake_id: Optional[int] = None
    fault_type: Optional[str] = None
    severity: Optional[str] = None
    candidates: List[VoiceCandidateApp] = field(default_factory=list)


def process_complaint_transcript(
    db_session: Session,
    session_manager: VoiceSessionManager,
    session_id: str,
    raw_transcript: str,
    operator_id: str,
    complainant_service_no: Optional[str],
    complainant_name: Optional[str],
    complainant_unit: Optional[str],
    complainant_rank: Optional[str],
    stt_confidence: float = 1.0,
    stt_language: Optional[str] = None,
) -> ComplaintProcessingResult:
    """
    Run the full complaint pipeline for one transcribed utterance.

    On guardrail rejection, the session is left in CAPTURING_COMPLAINT so the
    caller can be re-prompted. On success, the session transitions to
    OPERATOR_REVIEW with the classification results attached — identical to
    the transition that used to be inlined in routers/voice.py's /complaint
    handler.
    """
    embedder, classifier, search_engine, dependency_engine = _get_services()

    # ── LLM GUARDRAIL — verify language + fix STT errors ──
    guardrail_result = verify_and_correct_text(raw_transcript)
    if guardrail_result["status"] == "rejected":
        reason = guardrail_result.get("reason", "Complaint could not be understood.")
        return ComplaintProcessingResult(
            status="rejected",
            prompt_text=f"{reason} Please describe your IT issue again clearly.",
            corrected_transcript=raw_transcript,
        )

    # Use the LLM-corrected text for classification
    complaint_text = guardrail_result.get("corrected_text", raw_transcript)

    # ── Phase 1 AI Pipeline (REUSED UNCHANGED) ──
    embedding = embedder.get_embedding(complaint_text)
    fault_type = classifier.classify_fault_type(db_session, complaint_text, embedding)
    severity = classifier.classify_severity(db_session, complaint_text, embedding)
    raw_candidates = search_engine.search_candidates(db_session, embedding)

    enriched_candidates: List[VoiceCandidateApp] = []
    for cand in raw_candidates:
        app_obj = db_session.get(Application, cand["application_id"])
        if app_obj:
            enriched_candidates.append(VoiceCandidateApp(
                application_id=app_obj.id,
                application_name=app_obj.name,
                confidence_score=round(cand["score"], 4),
                is_primary=(len(enriched_candidates) == 0),
            ))

    # Expand dependencies off the primary candidate
    primary_candidate = enriched_candidates[0] if enriched_candidates else None
    if primary_candidate:
        dep_ids = dependency_engine.expand_dependencies(
            db_session=db_session,
            primary_app_id=primary_candidate.application_id,
            fault_type=fault_type,
        )
        existing_ids = {c.application_id for c in enriched_candidates}
        for d_id in dep_ids:
            if d_id not in existing_ids:
                d_app = db_session.get(Application, d_id)
                if d_app:
                    enriched_candidates.append(VoiceCandidateApp(
                        application_id=d_id,
                        application_name=d_app.name,
                        confidence_score=0.0,
                        is_primary=False,
                    ))

    # ── Create Intake record (same as Phase 1) ──
    intake = Intake(
        raw_text=complaint_text,
        operator_id=operator_id,
        complainant_service_no=complainant_service_no,
        complainant_name=complainant_name,
        complainant_unit=complainant_unit,
        complainant_rank=complainant_rank,
    )
    db_session.add(intake)
    db_session.commit()
    db_session.refresh(intake)

    # ── Update session (transition to OPERATOR_REVIEW) ──
    session_manager.transition(
        session_id,
        SessionState.OPERATOR_REVIEW,
        complaint_text=complaint_text,
        stt_confidence=stt_confidence,
        stt_language=stt_language,
        intake_id=intake.id,
        fault_type_proposal=fault_type,
        severity_proposal=severity,
        candidates=[c.model_dump() for c in enriched_candidates],
    )

    # Build summary prompt for operator
    app_name = primary_candidate.application_name if primary_candidate else "Unknown"
    prompt_text = render_dynamic_prompt(
        "classification_summary",
        complaint_text=complaint_text[:100],
        application_name=app_name,
        fault_type=fault_type,
        severity=severity,
    )

    return ComplaintProcessingResult(
        status="accepted",
        prompt_text=prompt_text,
        corrected_transcript=complaint_text,
        intake_id=intake.id,
        fault_type=fault_type,
        severity=severity,
        candidates=enriched_candidates,
    )
