"""
voice/complaint_processor.py — Shared Complaint Processing Pipeline
===================================================================
Executes the Phase 1 AI pipeline for a transcribed complaint.
Shared between the legacy REST API (routers/voice.py) and the 
WebRTC audio adapter (livekit_bridge/adapter.py).

Responsibilities:
- LLM Guardrails
- Embedding extraction
- Fault type & severity classification
- Application candidate search & dependency expansion
- Intake record creation
- Voice session state transition
- Prompt generation
"""

import logging
from dataclasses import dataclass
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

# Lazy-loaded singletons to avoid repeated initialization
_embedder = None
_classifier = None
_search_engine = None
_dependency_engine = None

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
    prompt_text: str            # TTS response text
    corrected_transcript: str
    intake_id: Optional[int] = None
    fault_type: Optional[str] = None
    severity: Optional[str] = None
    candidates: Optional[List[VoiceCandidateApp]] = None
    potential_duplicates: Optional[list] = None
    is_repeat_caller: bool = False


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
    stt_language: str = "en",
) -> ComplaintProcessingResult:
    """
    Executes the entire complaint pipeline.
    
    If the text is rejected by the guardrail, the session transitions to CAPTURING_COMPLAINT.
    If accepted, the session transitions to OPERATOR_REVIEW.
    """
    embedder, classifier, search_engine, dependency_engine = _get_services()

    # ── LLM GUARDRAIL ──
    guardrail_result = verify_and_correct_text(raw_transcript)
    if guardrail_result["status"] == "rejected":
        # Re-prompt the caller
        reason = guardrail_result.get("reason", "Complaint could not be understood.")
        prompt_text = f"{reason} Please describe your IT issue again clearly."
        
        # Ensure session stays in capturing state
        session_manager.transition(session_id, SessionState.CAPTURING_COMPLAINT)
        
        return ComplaintProcessingResult(
            status="rejected",
            prompt_text=prompt_text,
            corrected_transcript=raw_transcript,
        )

    # Use LLM-corrected text
    complaint_text = guardrail_result.get("corrected_text", raw_transcript)

    # ── Phase 1 AI Pipeline ──
    from services.pipeline import run_ai_pipeline
    fault_type, severity, raw_candidates, potential_duplicates, is_repeat = run_ai_pipeline(
        session=db_session,
        complaint_text=complaint_text,
        complainant_service_no=complainant_service_no or "unknown",
    )

    enriched_candidates = [VoiceCandidateApp(**c) for c in raw_candidates]

    # ── Database Intake Record ──
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

    # ── Session Transition ──
    # Pushes WebSocket state change to the frontend
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
        potential_duplicates=potential_duplicates,
        is_repeat_caller=is_repeat,
    )

    # Build summary prompt for TTS
    app_name = enriched_candidates[0].application_name if enriched_candidates else "Unknown"
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
        potential_duplicates=potential_duplicates,
        is_repeat_caller=is_repeat,
    )
