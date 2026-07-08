"""
voice_schemas.py — Pydantic Schemas for Voice Endpoints (Phase 2)
===================================================================
Request/response models for the /api/voice/* router.

Kept in a separate file from schemas.py to avoid polluting the
Phase 1 schema namespace — clean separation of concerns.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# =====================================================================
# VOICE SESSION RESPONSES
# =====================================================================

class VoiceStartResponse(BaseModel):
    """Response from POST /api/voice/start."""
    session_id: str
    state: str
    prompt_text: str = Field(
        ...,
        description="Text content of the greeting prompt (for display).",
    )
    audio_available: bool = Field(
        default=False,
        description="Whether a pre-recorded audio file is available for this prompt.",
    )


class VoiceServiceNumberResponse(BaseModel):
    """Response from POST /api/voice/service-number."""
    session_id: str
    state: str
    recognized_text: str = Field(
        ...,
        description="Raw text from STT transcription.",
    )
    normalised_service_no: str = Field(
        ...,
        description="Cleaned/normalised service number.",
    )
    is_valid: bool
    confidence: float = Field(
        default=0.0,
        description="STT confidence score (0.0–1.0).",
    )
    retries_count: int = 0
    max_retries: int = 3
    prompt_text: str = Field(
        default="",
        description="Next prompt text (confirmation or retry).",
    )
    error_reason: Optional[str] = Field(
        default=None,
        description="Why validation failed (if is_valid=False).",
    )
    stt_language: Optional[str] = None
    stt_processing_time_ms: float = 0.0


class VoiceConfirmRequest(BaseModel):
    """Request for POST /api/voice/confirm."""
    session_id: str
    confirmed: bool = Field(
        ...,
        description="True if the caller confirmed, False to retry.",
    )
    # Optional: operator can override the service number manually
    manual_service_no: Optional[str] = Field(
        default=None,
        description="Manual override by operator (for OPERATOR_FALLBACK).",
    )
    # Optional complainant details the operator may fill in
    complainant_name: Optional[str] = None
    complainant_unit: Optional[str] = None
    complainant_rank: Optional[str] = None


class VoiceConfirmResponse(BaseModel):
    """Response from POST /api/voice/confirm."""
    session_id: str
    state: str
    prompt_text: str


class VoiceConfirmAudioResponse(BaseModel):
    """Response from POST /api/voice/confirm-audio."""
    session_id: str
    state: str
    recognized_text: str
    confirmed: Optional[bool] = None   # True=yes, False=no, None=unclear
    prompt_text: str
    stt_language: Optional[str] = None
    stt_processing_time_ms: float = 0.0


class VoiceCandidateApp(BaseModel):
    """Candidate application in complaint classification result."""
    application_id: int
    application_name: str
    confidence_score: float
    is_primary: bool = False


class VoiceComplaintResponse(BaseModel):
    """Response from POST /api/voice/complaint."""
    session_id: str
    state: str
    transcript: str = Field(
        ...,
        description="Transcribed complaint text from STT.",
    )
    confidence: float = 0.0
    stt_language: Optional[str] = None
    stt_processing_time_ms: float = 0.0

    # Classification results (from Phase 1 pipeline)
    intake_id: Optional[int] = None
    fault_type_proposal: Optional[str] = None
    severity_proposal: Optional[str] = None
    candidates: List[VoiceCandidateApp] = Field(default_factory=list)

    # Prompt for operator
    prompt_text: str = ""


class VoiceStatusResponse(BaseModel):
    """Response from GET /api/voice/status."""
    session_id: str
    state: str
    service_no: Optional[str] = None
    complaint_text: Optional[str] = None
    intake_id: Optional[int] = None
    ticket_number: Optional[str] = None
    svc_retries: int = 0
    created_at: Optional[float] = None
    errors: List[str] = Field(default_factory=list)


class VoiceFallbackRequest(BaseModel):
    """Request for POST /api/voice/fallback — operator manual override."""
    session_id: str
    service_no: str = Field(
        ...,
        description="Manually entered service number by operator.",
    )
    complainant_name: Optional[str] = None
    complainant_unit: Optional[str] = None
    complainant_rank: Optional[str] = None


class VoiceFallbackResponse(BaseModel):
    """Response from POST /api/voice/fallback."""
    session_id: str
    state: str
    service_no: str
    prompt_text: str


class VoiceAnotherComplaintResponse(BaseModel):
    """Response from POST /api/voice/another-complaint (R-42)."""
    session_id: str
    state: str
    recognized_text: str
    wants_another: Optional[bool] = None   # True=yes, False=no, None=unclear
    prompt_text: str
    stt_language: Optional[str] = None
    stt_processing_time_ms: float = 0.0


class VoiceRetryResponse(BaseModel):
    """Response from POST /api/voice/retry."""
    session_id: str
    state: str
    retries_count: int
    max_retries: int = 3
    prompt_text: str
