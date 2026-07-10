"""
routers/voice.py ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â Voice Layer REST API (Phase 2)
====================================================
Exposes endpoints for the voice-driven complaint intake workflow.

This router orchestrates the voice session state machine, STT/TTS
engines, service number validation, and integrates with the existing
Phase 1 classification pipeline (embedder ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ classifier ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ search ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢
dependency expansion) WITHOUT modifying any Phase 1 code.

Endpoints:
  POST /api/voice/start            ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â Start a new voice session
  POST /api/voice/service-number   ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â Upload audio ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ validate service number
  POST /api/voice/confirm          ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â Confirm/reject service number
  POST /api/voice/complaint        ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â Upload audio ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ classify complaint
  POST /api/voice/fallback         ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â Operator manual service number entry
  GET  /api/voice/status           ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â Query current session state
  GET  /api/voice/tts              ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â Dynamic TTS audio generation
  GET  /api/voice/prompt/{key}     ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â Serve pre-recorded static prompt

Requirements Covered:
  R-30 through R-39 (full voice layer)
"""

import time
import logging
import re
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from sqlmodel import Session

from database import get_session
from security import CurrentUser, get_current_user, require_operator

# Phase 2 voice modules
from voice.stt import SpeechToTextEngine
from voice.tts import TextToSpeechEngine
from voice.session import VoiceSessionManager, SessionState, MAX_SERVICE_NUMBER_RETRIES
from voice.validators import validate_service_number
from voice.audio import convert_to_wav, detect_silence, detect_format_from_content_type, FrameBuffer
from voice.vad import StreamingEndpointDetector
from voice.prompts import (
    get_static_prompt_bytes,
    get_prompt_text,
    render_dynamic_prompt,
)
from voice_schemas import (
    VoiceStartResponse,
    VoiceServiceNumberResponse,
    VoiceConfirmRequest,
    VoiceConfirmResponse,
    VoiceConfirmAudioResponse,
    VoiceComplaintResponse,
    VoiceCandidateApp,
    VoiceStatusResponse,
    VoiceFallbackRequest,
    VoiceFallbackResponse,
)

logger = logging.getLogger("routers.voice")

session_manager = VoiceSessionManager()

# Phase 2 voice singletons — lazy-loaded on first use
_stt_engine: Optional[SpeechToTextEngine] = None
_tts_engine: Optional[TextToSpeechEngine] = None


from config import settings

def _get_stt() -> SpeechToTextEngine:
    global _stt_engine
    if _stt_engine is None:
        _stt_engine = SpeechToTextEngine(
            model_size=settings.STT_MODEL_SIZE,
            device=settings.STT_DEVICE,
            compute_type=settings.STT_COMPUTE_TYPE
        )
    return _stt_engine


def _get_tts() -> TextToSpeechEngine:
    global _tts_engine
    if _tts_engine is None:
        _tts_engine = TextToSpeechEngine()
    return _tts_engine


router = APIRouter()


# =====================================================================
# 1. POST /voice/start ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â  Start a new voice session
# =====================================================================

@router.post("/start", response_model=VoiceStartResponse)
async def voice_start(
    current_user: CurrentUser = Depends(require_operator),
):
    """
    Initialise a new voice session and return the greeting prompt.

    Phase 4 (LIVEKIT_ENABLED=True): Also creates a LiveKit room using the
    session_id as the room name, connects the AI agent, and returns the
    LiveKit token so the browser can join directly.

    Session is always created first via VoiceSessionManager.
    LiveKit attaches to it — never the reverse.
    If LiveKit setup fails, the session continues on the legacy
    WebSocket/REST audio path (graceful degradation, non-fatal).
    """
    session = session_manager.create_session()

    # Transition from GREETING ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ CAPTURING_SERVICE_NUMBER
    session_manager.transition(
        session.session_id,
        SessionState.CAPTURING_SERVICE_NUMBER,
    )

    prompt_text = get_prompt_text("greeting")
    audio_bytes = get_static_prompt_bytes("greeting")

    # ── Phase 4: LiveKit attachment (Q2: this endpoint, not a new one) ─
    # Q3: runtime backend flag — decision made server-side.
    # Frontend reads response.livekit_enabled (no build-time env var).
    livekit_token: Optional[str] = None
    livekit_url:   Optional[str] = None
    room_name:     Optional[str] = None
    livekit_ready              = False

    if settings.LIVEKIT_ENABLED:
        try:
            # Lazy imports: only loaded when LiveKit is actually enabled.
            from routers.livekit import (
                get_room_manager,
                get_livekit_client,
                get_connection_manager,
                get_token_manager,
            )

            sid = session.session_id   # the universal identifier

            # 1. Register room entry in transport registry (transport state only)
            rm = get_room_manager()
            rm.register(sid)

            # 2. Provision the LiveKit room on the server
            lk_client = get_livekit_client()
            await lk_client.ensure_room_exists(sid)

            # 3. Spawn agent asyncio.Task in this process (one per room)
            cm = get_connection_manager()
            await cm.connect_agent(sid)

            # 4. Generate caller token (room name == session_id everywhere)
            tm = get_token_manager()
            livekit_token = tm.generate_caller_token(
                session_id=sid,
                identity=current_user.service_no,
                display_name=current_user.service_no,
            )
            livekit_url = settings.LIVEKIT_URL
            room_name   = sid
            livekit_ready = True

            logger.info(
                "LiveKit room ready: session=%s  url=%s",
                sid, settings.LIVEKIT_URL,
            )

        except Exception as exc:
            # Non-fatal: session continues on legacy WebSocket/REST path.
            logger.error(
                "LiveKit setup failed for session %s: %s — "
                "continuing on legacy audio path.",
                session.session_id,
                exc,
                exc_info=True,
            )

    return VoiceStartResponse(
        session_id=session.session_id,
        state=SessionState.CAPTURING_SERVICE_NUMBER.value,
        prompt_text=prompt_text,
        audio_available=audio_bytes is not None,
        # Q3: runtime flag — frontend reads this, not a build-time env var
        livekit_enabled=livekit_ready,
        livekit_token=livekit_token,
        livekit_url=livekit_url,
        room_name=room_name,
    )



# =====================================================================
# 2. POST /voice/service-number ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â Upload audio, transcribe & validate
# =====================================================================

@router.post("/service-number", response_model=VoiceServiceNumberResponse)
async def voice_service_number(
    session_id: str = Form(...),
    audio: UploadFile = File(...),
    current_user: CurrentUser = Depends(require_operator),
):
    """
    Receive an audio recording of the caller speaking their service number.

    Pipeline:
      1. Convert audio to WAV
      2. Run STT transcription
      3. Normalise & validate the service number
      4. If valid ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ transition to ManagerNFIRMING_SERVICE_NUMBER
      5. If invalid ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ increment retries or fall back to operator

    Satisfies R-30 (voice capture) and R-32 (validation).
    """
    # Retrieve session
    session = session_manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Voice session not found or expired.")

    if session.state not in (
        SessionState.CAPTURING_SERVICE_NUMBER,
        SessionState.CONFIRMING_SERVICE_NUMBER,  # Re-capture after rejection
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state for service number capture: {session.state.value}",
        )

    # Read and convert audio
    raw_bytes = await audio.read()
    content_type = audio.content_type or "audio/webm"
    source_format = detect_format_from_content_type(content_type)
    wav_bytes = convert_to_wav(raw_bytes, source_format=source_format)

    # Check for silence
    if detect_silence(wav_bytes, source_format="wav"):
        retries = session_manager.increment_svc_retries(session_id)

        if session_manager.should_fallback(session_id):
            session_manager.transition(session_id, SessionState.OPERATOR_FALLBACK)
            return VoiceServiceNumberResponse(
                session_id=session_id,
                state=SessionState.OPERATOR_FALLBACK.value,
                recognized_text="",
                normalised_service_no="",
                is_valid=False,
                retries_count=retries,
                max_retries=MAX_SERVICE_NUMBER_RETRIES,
                prompt_text=get_prompt_text("fallback_operator"),
                error_reason="No speech detected. Maximum retries exceeded.",
            )

        return VoiceServiceNumberResponse(
            session_id=session_id,
            state=SessionState.CAPTURING_SERVICE_NUMBER.value,
            recognized_text="",
            normalised_service_no="",
            is_valid=False,
            retries_count=retries,
            max_retries=MAX_SERVICE_NUMBER_RETRIES,
            prompt_text=render_dynamic_prompt(
                "retry_service_number",
                attempt=retries,
                max_attempts=MAX_SERVICE_NUMBER_RETRIES,
            ),
            error_reason="No speech detected. Please try again.",
        )

    # Run STT
    stt = _get_stt()
    try:
        result = stt.transcribe(wav_bytes)
    except Exception as exc:
        logger.warning("STT failed for session %s (treating as silent): %s", session_id, exc)
        # Don't crash with 500 ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â treat any STT error as a silent/empty recording
        # and route back into the retry loop gracefully.
        retries = session_manager.increment_svc_retries(session_id)
        if session_manager.should_fallback(session_id):
            session_manager.transition(session_id, SessionState.OPERATOR_FALLBACK)
            return VoiceServiceNumberResponse(
                session_id=session_id,
                state=SessionState.OPERATOR_FALLBACK.value,
                recognized_text="",
                normalised_service_no="",
                is_valid=False,
                retries_count=retries,
                max_retries=MAX_SERVICE_NUMBER_RETRIES,
                prompt_text=get_prompt_text("fallback_operator"),
                error_reason="Audio processing failed. Maximum retries exceeded.",
            )
        return VoiceServiceNumberResponse(
            session_id=session_id,
            state=SessionState.CAPTURING_SERVICE_NUMBER.value,
            recognized_text="",
            normalised_service_no="",
            is_valid=False,
            retries_count=retries,
            max_retries=MAX_SERVICE_NUMBER_RETRIES,
            prompt_text=render_dynamic_prompt(
                "retry_service_number",
                attempt=retries,
                max_attempts=MAX_SERVICE_NUMBER_RETRIES,
            ),
            error_reason="Could not process audio. Please try again.",
        )

    session.total_stt_calls += 1
    session.stt_latency_ms = result.processing_time_ms

    if result.is_silent or not result.text.strip():
        retries = session_manager.increment_svc_retries(session_id)

        if session_manager.should_fallback(session_id):
            session_manager.transition(session_id, SessionState.OPERATOR_FALLBACK)
            return VoiceServiceNumberResponse(
                session_id=session_id,
                state=SessionState.OPERATOR_FALLBACK.value,
                recognized_text=result.text,
                normalised_service_no="",
                is_valid=False,
                confidence=result.confidence,
                retries_count=retries,
                max_retries=MAX_SERVICE_NUMBER_RETRIES,
                prompt_text=get_prompt_text("fallback_operator"),
                error_reason="No speech detected. Maximum retries exceeded.",
                stt_language=result.language,
                stt_processing_time_ms=result.processing_time_ms,
            )

        return VoiceServiceNumberResponse(
            session_id=session_id,
            state=SessionState.CAPTURING_SERVICE_NUMBER.value,
            recognized_text=result.text,
            normalised_service_no="",
            is_valid=False,
            confidence=result.confidence,
            retries_count=retries,
            max_retries=MAX_SERVICE_NUMBER_RETRIES,
            prompt_text=render_dynamic_prompt(
                "retry_service_number",
                attempt=retries,
                max_attempts=MAX_SERVICE_NUMBER_RETRIES,
            ),
            error_reason="Could not understand speech. Please try again.",
            stt_language=result.language,
            stt_processing_time_ms=result.processing_time_ms,
        )

    # Validate service number
    validation = validate_service_number(result.text)

    if validation.is_valid:
        # Store and move to confirmation state
        session_manager.transition(
            session_id,
            SessionState.CONFIRMING_SERVICE_NUMBER,
            service_no=validation.normalised,
            stt_confidence=result.confidence,
            stt_language=result.language,
        )

        prompt_text = render_dynamic_prompt(
            "confirm_service_number",
            service_number=validation.normalised,
        )

        return VoiceServiceNumberResponse(
            session_id=session_id,
            state=SessionState.CONFIRMING_SERVICE_NUMBER.value,
            recognized_text=result.text,
            normalised_service_no=validation.normalised,
            is_valid=True,
            confidence=result.confidence,
            retries_count=session.svc_retries,
            max_retries=MAX_SERVICE_NUMBER_RETRIES,
            prompt_text=prompt_text,
            stt_language=result.language,
            stt_processing_time_ms=result.processing_time_ms,
        )
    else:
        # Invalid ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â increment retries
        retries = session_manager.increment_svc_retries(session_id)

        if session_manager.should_fallback(session_id):
            session_manager.transition(session_id, SessionState.OPERATOR_FALLBACK)
            return VoiceServiceNumberResponse(
                session_id=session_id,
                state=SessionState.OPERATOR_FALLBACK.value,
                recognized_text=result.text,
                normalised_service_no=validation.normalised,
                is_valid=False,
                confidence=result.confidence,
                retries_count=retries,
                max_retries=MAX_SERVICE_NUMBER_RETRIES,
                prompt_text=get_prompt_text("fallback_operator"),
                error_reason=validation.error_reason,
                stt_language=result.language,
                stt_processing_time_ms=result.processing_time_ms,
            )

        return VoiceServiceNumberResponse(
            session_id=session_id,
            state=SessionState.CAPTURING_SERVICE_NUMBER.value,
            recognized_text=result.text,
            normalised_service_no=validation.normalised,
            is_valid=False,
            confidence=result.confidence,
            retries_count=retries,
            max_retries=MAX_SERVICE_NUMBER_RETRIES,
            prompt_text=render_dynamic_prompt(
                "retry_service_number",
                attempt=retries,
                max_attempts=MAX_SERVICE_NUMBER_RETRIES,
            ),
            error_reason=validation.error_reason,
            stt_language=result.language,
            stt_processing_time_ms=result.processing_time_ms,
        )


# =====================================================================
# 3. POST /voice/confirm ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â Confirm or reject service number
# =====================================================================

@router.post("/confirm", response_model=VoiceConfirmResponse)
def voice_confirm(
    request: VoiceConfirmRequest,
    current_user: CurrentUser = Depends(require_operator),
):
    """
    Confirm or reject the recognised service number.

    If confirmed ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ transition to CAPTURING_COMPLAINT.
    If rejected  ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ transition back to CAPTURING_SERVICE_NUMBER.

    Satisfies R-31 (read-back confirmation loop).
    """
    session = session_manager.get_session(request.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Voice session not found or expired.")

    if session.state not in (
        SessionState.CONFIRMING_SERVICE_NUMBER,
        SessionState.OPERATOR_FALLBACK,
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state for confirmation: {session.state.value}",
        )

    if request.confirmed:
        # If coming from fallback with manual override
        if request.manual_service_no:
            session.service_no = request.manual_service_no.strip().upper()

        # Store optional complainant details
        if request.complainant_name:
            session.complainant_name = request.complainant_name
        if request.complainant_unit:
            session.complainant_unit = request.complainant_unit
        if request.complainant_rank:
            session.complainant_rank = request.complainant_rank

        # If in OPERATOR_FALLBACK, transition to OPERATOR_REVIEW
        # so that the manual service number is accepted
        if session.state == SessionState.OPERATOR_FALLBACK:
            session_manager.transition(
                request.session_id,
                SessionState.OPERATOR_REVIEW,
                service_no=session.service_no,
            )
            return VoiceConfirmResponse(
                session_id=request.session_id,
                state=SessionState.OPERATOR_REVIEW.value,
                prompt_text=get_prompt_text("ask_complaint"),
            )

        session_manager.transition(
            request.session_id,
            SessionState.CAPTURING_COMPLAINT,
        )

        return VoiceConfirmResponse(
            session_id=request.session_id,
            state=SessionState.CAPTURING_COMPLAINT.value,
            prompt_text=get_prompt_text("ask_complaint"),
        )
    else:
        # Rejected ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â go back to capturing
        session_manager.transition(
            request.session_id,
            SessionState.CAPTURING_SERVICE_NUMBER,
        )

        return VoiceConfirmResponse(
            session_id=request.session_id,
            state=SessionState.CAPTURING_SERVICE_NUMBER.value,
            prompt_text=get_prompt_text("ask_service_number"),
        )


# =====================================================================
# 3b. POST /voice/confirm-audio  ­  ­  ­ Confirm via voice (say "yes" or "no")
# =====================================================================

@router.post("/confirm-audio", response_model=VoiceConfirmAudioResponse)
async def voice_confirm_audio(
    session_id: str = Form(...),
    audio: UploadFile = File(...),
    current_user: CurrentUser = Depends(require_operator),
):
    """
    Accept a voice recording for the yes/no confirmation step.
    Runs STT and parses the response for yes/no intent in
    English, Hindi, and Hinglish.
    """
    session = session_manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Voice session not found or expired.")

    if session.state != SessionState.CONFIRMING_SERVICE_NUMBER:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state for audio confirmation: {session.state.value}",
        )

    # Read and convert audio
    raw_bytes = await audio.read()
    content_type = audio.content_type or "audio/webm"
    source_format = detect_format_from_content_type(content_type)
    wav_bytes = convert_to_wav(raw_bytes, source_format=source_format)

    # Detect silence  prompt to repeat
    if detect_silence(wav_bytes, source_format="wav"):
        return VoiceConfirmAudioResponse(
            session_id=session_id,
            state=SessionState.CONFIRMING_SERVICE_NUMBER.value,
            recognized_text="",
            confirmed=None,
            prompt_text="No speech detected. Please say Yes or No.",
        )

    # Run STT
    stt = _get_stt()
    try:
        result = stt.transcribe(wav_bytes)
    except Exception as exc:
        logger.warning("STT failed during confirm-audio for session %s: %s", session_id, exc)
        return VoiceConfirmAudioResponse(
            session_id=session_id,
            state=SessionState.CONFIRMING_SERVICE_NUMBER.value,
            recognized_text="",
            confirmed=None,
            prompt_text="Could not process audio. Please say Yes or No.",
        )

    text = (result.text or "").lower().strip()
    logger.info("[confirm-audio] session=%s transcript='%s'", session_id, text)

    # Remove punctuation so "No." matches "no"
    clean_text = re.sub(r'[^\w\s]', '', text)

    # Detect YES intent
    YES_WORDS = {"yes", "yeah", "yep", "correct", "right", "haan", "han", "ha", "bilkul", "sahi", "ok", "okay", "confirm"}
    NO_WORDS  = {"no", "nope", "wrong", "incorrect", "nahi", "nein", "nai", "nah", "retry", "again"}

    words = set(clean_text.split())
    is_yes = bool(words & YES_WORDS)
    is_no  = bool(words & NO_WORDS)

    if is_yes and not is_no:
        session_manager.transition(session_id, SessionState.CAPTURING_COMPLAINT)
        return VoiceConfirmAudioResponse(
            session_id=session_id,
            state=SessionState.CAPTURING_COMPLAINT.value,
            recognized_text=result.text,
            confirmed=True,
            prompt_text=get_prompt_text("ask_complaint"),
            stt_language=result.language,
            stt_processing_time_ms=result.processing_time_ms,
        )

    if is_no and not is_yes:
        session_manager.transition(session_id, SessionState.CAPTURING_SERVICE_NUMBER)
        return VoiceConfirmAudioResponse(
            session_id=session_id,
            state=SessionState.CAPTURING_SERVICE_NUMBER.value,
            recognized_text=result.text,
            confirmed=False,
            prompt_text=get_prompt_text("ask_service_number"),
            stt_language=result.language,
            stt_processing_time_ms=result.processing_time_ms,
        )

    # Unclear  ask again
    return VoiceConfirmAudioResponse(
        session_id=session_id,
        state=SessionState.CONFIRMING_SERVICE_NUMBER.value,
        recognized_text=result.text,
        confirmed=None,
        prompt_text="Sorry, I didn't understand. Please say Yes to confirm or No to retry.",
        stt_language=result.language,
        stt_processing_time_ms=result.processing_time_ms,
    )


# =====================================================================
# 4. POST /voice/complaint  Upload audio, transcribe & classify
# =====================================================================

@router.post("/complaint", response_model=VoiceComplaintResponse)
async def voice_complaint(
    session_id: str = Form(...),
    audio: UploadFile = File(...),
    db_session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(require_operator),
):
    """
    Receive audio of the caller describing their complaint.

    Pipeline:
      1. Convert audio to WAV
      2. Run STT transcription
      3. Feed transcript to Phase 1 classifier (embedder  classifier  search)
      4. Return classification proposals for operator review

    Satisfies R-34 (speech-to-text intake) and R-35 (multilingual).
    The existing classifier is called WITHOUT MODIFICATION (R-39).
    """

    session = session_manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Voice session not found or expired.")

    if session.state not in (
        SessionState.CAPTURING_COMPLAINT,
        SessionState.OPERATOR_REVIEW,  # Allow re-recording
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state for complaint capture: {session.state.value}",
        )

    # Read and convert audio
    raw_bytes = await audio.read()
    content_type = audio.content_type or "audio/webm"
    source_format = detect_format_from_content_type(content_type)
    wav_bytes = convert_to_wav(raw_bytes, source_format=source_format)

    # Check for silence
    if detect_silence(wav_bytes, source_format="wav"):
        return VoiceComplaintResponse(
            session_id=session_id,
            state=session.state.value,
            transcript="",
            confidence=0.0,
            prompt_text="No speech detected. Please describe your complaint again.",
        )

    # Run STT
    stt = _get_stt()
    try:
        result = stt.transcribe(wav_bytes)
    except Exception as exc:
        logger.warning("STT failed for complaint in session %s (treating as silent): %s", session_id, exc)
        return VoiceComplaintResponse(
            session_id=session_id,
            state=session.state.value,
            transcript="",
            confidence=0.0,
            stt_language=None,
            stt_processing_time_ms=0.0,
            prompt_text="Could not process audio. Please describe your complaint again.",
        )

    session.total_stt_calls += 1
    session.stt_latency_ms = result.processing_time_ms

    if result.is_silent or not result.text.strip():
        return VoiceComplaintResponse(
            session_id=session_id,
            state=session.state.value,
            transcript="",
            confidence=result.confidence,
            stt_language=result.language,
            stt_processing_time_ms=result.processing_time_ms,
            prompt_text="Could not understand speech. Please describe your complaint again.",
        )

    complaint_text = result.text.strip()

    # ── Shared Pipeline Execution ──
    from voice.complaint_processor import process_complaint_transcript
    
    result_data = process_complaint_transcript(
        db_session=db_session,
        session_manager=session_manager,
        session_id=session_id,
        raw_transcript=complaint_text,
        operator_id=current_user.service_no,
        complainant_service_no=session.service_no,
        complainant_name=session.complainant_name,
        complainant_unit=session.complainant_unit,
        complainant_rank=session.complainant_rank,
        stt_confidence=result.confidence,
        stt_language=result.language,
    )

    if result_data.status == "rejected":
        return VoiceComplaintResponse(
            session_id=session_id,
            state=session.state.value,
            transcript=result_data.corrected_transcript,
            confidence=result.confidence,
            stt_language=result.language,
            stt_processing_time_ms=result.processing_time_ms,
            prompt_text=result_data.prompt_text,
        )

    return VoiceComplaintResponse(
        session_id=session_id,
        state=SessionState.OPERATOR_REVIEW.value,
        transcript=result_data.corrected_transcript,
        confidence=result.confidence,
        stt_language=result.language,
        stt_processing_time_ms=result.processing_time_ms,
        intake_id=result_data.intake_id,
        fault_type_proposal=result_data.fault_type,
        severity_proposal=result_data.severity,
        candidates=result_data.candidates or [],
        potential_duplicates=result_data.potential_duplicates or [],
        is_repeat_caller=result_data.is_repeat_caller or False,
        prompt_text=result_data.prompt_text,
    )


# =====================================================================
# 5. POST /voice/fallback ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â Operator manual service number entry
# =====================================================================

@router.post("/fallback", response_model=VoiceFallbackResponse)
def voice_fallback(
    request: VoiceFallbackRequest,
    current_user: CurrentUser = Depends(require_operator),
):
    """
    Operator manually enters the service number after voice capture
    has failed repeatedly.

    Satisfies R-33 (operator fallback after repeated failures).
    """
    session = session_manager.get_session(request.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Voice session not found or expired.")

    if session.state != SessionState.OPERATOR_FALLBACK:
        raise HTTPException(
            status_code=400,
            detail=f"Fallback only available in OPERATOR_FALLBACK state. Current: {session.state.value}",
        )

    # Store the manually entered data
    service_no = request.service_no.strip().upper()

    session_manager.transition(
        request.session_id,
        SessionState.CAPTURING_COMPLAINT,
        service_no=service_no,
        complainant_name=request.complainant_name,
        complainant_unit=request.complainant_unit,
        complainant_rank=request.complainant_rank,
    )

    # Now proceed ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â operator can either type the complaint or record it
    return VoiceFallbackResponse(
        session_id=request.session_id,
        state=SessionState.CAPTURING_COMPLAINT.value,
        service_no=service_no,
        prompt_text=get_prompt_text("ask_complaint"),
    )


# =====================================================================
# 6. GET /voice/status ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â Query session state
# =====================================================================

@router.get("/status", response_model=VoiceStatusResponse)
def voice_status(
    session_id: str = Query(...),
    current_user: CurrentUser = Depends(require_operator),
):
    """Return the current state and data of a voice session."""
    session = session_manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Voice session not found or expired.")

    return VoiceStatusResponse(
        session_id=session.session_id,
        state=session.state.value,
        service_no=session.service_no,
        complaint_text=session.complaint_text,
        intake_id=session.intake_id,
        ticket_number=session.ticket_number,
        svc_retries=session.svc_retries,
        created_at=session.created_at,
        errors=session.errors,
    )


# =====================================================================
# 7. GET /voice/tts ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â Dynamic text-to-speech
# =====================================================================

@router.get("/tts")
def voice_tts(
    text: str = Query(..., min_length=1, description="Text to synthesise."),
    normalise: bool = Query(False, description="Apply phonetic normalisation."),
    current_user: CurrentUser = Depends(require_operator),
):
    """
    Synthesise text to speech on-the-fly and return WAV audio.

    Satisfies R-37 (local GPU-backed TTS) and R-38 (ticket number read-back).
    """
    tts = _get_tts()
    if not tts.is_available():
        raise HTTPException(
            status_code=503,
            detail="No TTS backend available. Install piper-tts or pyttsx3.",
        )

    audio_bytes = tts.synthesise(text, normalise=normalise)
    if not audio_bytes:
        raise HTTPException(status_code=500, detail="TTS synthesis returned empty audio.")

    return Response(
        content=audio_bytes,
        media_type="audio/wav",
        headers={"Content-Disposition": "inline; filename=tts_output.wav"},
    )


# =====================================================================
# 9. GET /voice/char/{char} ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â Serve individual character audio clip
# =====================================================================

@router.get("/char/{char}")
def voice_char(
    char: str,
    current_user: CurrentUser = Depends(require_operator),
):
    """
    Serve a pre-recorded WAV clip for a single character (digit or letter).

    Character clips live in voice/static_prompts/chars/ and are named:
      0.wav ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¦ 9.wav   (digits)
      A.wav ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¦ Z.wav   (uppercase letters)
      dash.wav        (hyphen / dash)

    These clips are recorded with the same Zira voice as all other static
    prompts, ensuring a consistent audio experience when reading back
    service numbers character-by-character (R-31, R-38).
    """
    import os

    # Normalise input
    c = char.strip().upper()
    if c == "-":
        c = "dash"

    # Only allow safe single chars or 'dash'
    if c != "dash" and (len(c) != 1 or not c.isalnum()):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid character '{char}'. Only 0-9, A-Z, or '-' are supported.",
        )

    chars_dir = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "voice", "static_prompts", "chars")
    )
    clip_path = os.path.join(chars_dir, f"{c}.wav")

    if not os.path.isfile(clip_path):
        raise HTTPException(
            status_code=404,
            detail=f"No audio clip found for character '{char}'. "
                   "Run generate_char_clips.py to create missing clips.",
        )

    with open(clip_path, "rb") as f:
        audio_bytes = f.read()

    return Response(
        content=audio_bytes,
        media_type="audio/wav",
        headers={"Content-Disposition": f"inline; filename={c}.wav"},
    )


# =====================================================================
# 10. GET /voice/spell/{text} ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â Stitch character clips into one WAV
# =====================================================================

@router.get("/spell/{text}")
def voice_spell(
    text: str,
    current_user: CurrentUser = Depends(require_operator),
):
    """
    Concatenate pre-recorded character clips for every character in {text}
    into a single WAV file and return it.

    This lets the frontend play a service number as one continuous audio
    stream (same Zira voice, no per-character HTTP gaps) instead of
    fetching and playing each clip individually.

    Supported characters: 0-9, A-Z, '-' (dash).
    Unknown characters are silently skipped.
    """
    import os
    import io

    chars_dir = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "voice", "static_prompts", "chars")
    )

    try:
        from pydub import AudioSegment  # type: ignore
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="pydub is required for spell stitching. Install with: pip install pydub",
        )

    # Small pause between characters ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â kept tight so the read-back
    # doesn't drag; the clips themselves have been silence-stripped below.
    GAP_MS = 30
    gap = AudioSegment.silent(duration=GAP_MS)

    def _strip_clip(seg: "AudioSegment") -> "AudioSegment":
        """
        Remove the leading and trailing silence that pyttsx3 pads around
        each word/letter clip so consecutive characters flow naturally.
        silence_thresh is set conservatively (-38 dBFS) to avoid clipping
        real speech content.
        """
        from pydub.silence import detect_nonsilent  # type: ignore
        ranges = detect_nonsilent(seg, min_silence_len=50, silence_thresh=-38)
        if not ranges:
            return seg  # nothing audible ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â return as-is
        start_ms, end_ms = ranges[0][0], ranges[-1][1]
        # Add a small 10 ms pad so we don't clip the very edges of the audio
        return seg[max(0, start_ms - 10): min(len(seg), end_ms + 10)]

    combined = AudioSegment.empty()
    normalised = text.strip().upper()

    for ch in normalised:
        clip_name = "dash" if ch == "-" else ch
        if not (clip_name == "dash" or (len(clip_name) == 1 and clip_name.isalnum())):
            continue  # skip unsupported chars
        clip_path = os.path.join(chars_dir, f"{clip_name}.wav")
        if not os.path.isfile(clip_path):
            logger.warning("Missing char clip: %s", clip_path)
            continue
        segment = _strip_clip(AudioSegment.from_wav(clip_path))
        combined = combined + segment + gap

    if len(combined) == 0:
        raise HTTPException(
            status_code=400,
            detail=f"No recognisable characters in '{text}'.",
        )

    buf = io.BytesIO()
    combined.export(buf, format="wav")
    wav_bytes = buf.getvalue()

    return Response(
        content=wav_bytes,
        media_type="audio/wav",
        headers={"Content-Disposition": f"inline; filename=spell_{normalised}.wav"},
    )


@router.get("/prompt/{key}")
def voice_prompt(
    key: str,
    current_user: CurrentUser = Depends(require_operator),
):
    """
    Serve a pre-recorded static prompt WAV file.

    If the file doesn't exist, falls back to TTS synthesis of the
    prompt text.

    Satisfies R-36 (pre-recorded prompts).
    """
    # Try static file first
    audio_bytes = get_static_prompt_bytes(key)
    if audio_bytes:
        return Response(
            content=audio_bytes,
            media_type="audio/wav",
            headers={"Content-Disposition": f"inline; filename={key}.wav"},
        )

    # Fallback: generate via TTS
    fallback_text = get_prompt_text(key)
    if not fallback_text:
        raise HTTPException(status_code=404, detail=f"Unknown prompt key: '{key}'")

    tts = _get_tts()
    if tts.is_available():
        audio_bytes = tts.synthesise(fallback_text)
        if audio_bytes:
            return Response(
                content=audio_bytes,
                media_type="audio/wav",
                headers={"Content-Disposition": f"inline; filename={key}.wav"},
            )

    # Last resort: return the text
    return {"prompt_key": key, "text": fallback_text, "audio_available": False}


# =====================================================================
# 11. WS /voice/ws/vad-stream ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â Real-time streaming VAD (end-of-speech detection)
# =====================================================================
#
# IMPORTANT: Ye endpoint RAW PCM audio expect karta hai ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â
#   Format:      16-bit signed PCM
#   Sample rate: 16000 Hz (16kHz)
#   Channels:    1 (mono)
#
# Browser ka MediaRecorder (jo baaki endpoints use karte hain) WebM/Opus
# deta hai, raw PCM nahi ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â isliye frontend me AudioWorklet/ScriptProcessor
# use karna padega jo seedha mic se raw samples nikaale (alag se banega).
#
# Client ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ Server: binary audio chunks (bytes)
# Server ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ Client: JSON messages:
#     {"event": "listening"}           ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â connection established
#     {"event": "speech_started"}      ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â user ne bolna shuru kiya
#     {"event": "end_of_speech"}       ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â user chup ho gaya, recording stop karo
#     {"event": "error", "detail": ""} ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â kuch galat hua
# =====================================================================

@router.websocket("/ws/vad-stream")
async def voice_vad_stream(websocket: WebSocket):
    """
    Real-time WebSocket jo continuously audio chunks receive karta hai
    aur Silero VAD se "end of speech" detect karte hi signal bhejta hai.

    Client (browser) yaha connect karega, phir chhote-chhote raw PCM
    chunks bhejta rahega jab tak server "end_of_speech" event na bheje ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â
    tab client recording stop kar dega aur poori WAV file normal REST
    endpoint (/voice/complaint ya /voice/service-number) pe bhej dega.
    """
    await websocket.accept()

    # Har naye connection ke liye fresh buffer + detector
    frame_buffer = FrameBuffer()
    detector = StreamingEndpointDetector(
        silence_duration_ms=2500,
        speech_threshold=0.4,
        min_speech_ms=300,
    )
    detector.reset()

    was_speaking = False  # "speech_started" event sirf ek baar bhejne ke liye

    try:
        await websocket.send_json({"event": "listening"})

        while True:
            # Client se raw PCM bytes receive karo
            chunk = await websocket.receive_bytes()

            # Chunk ko 512-sample frames me todo
            frames = frame_buffer.add_chunk(chunk)

            for frame in frames:
                result = detector.process_frame(frame)

                if detector._has_spoken and not was_speaking:
                    was_speaking = True
                    await websocket.send_json({"event": "speech_started"})

                if result == "end_of_speech":
                    await websocket.send_json({"event": "end_of_speech"})
                    detector.reset()
                    frame_buffer.reset()
                    was_speaking = False

                elif result == "timeout":
                    await websocket.send_json({"event": "timeout", "detail": "No speech detected within max wait time."})
                    detector.reset()
                    frame_buffer.reset()
                    was_speaking = False

    except WebSocketDisconnect:
        logger.info("VAD WebSocket disconnected normally.")
    except Exception as exc:
        logger.error("VAD WebSocket error: %s", exc, exc_info=True)
        try:
            await websocket.send_json({"event": "error", "detail": str(exc)})
        except Exception:
            pass  # connection already band ho chuki hogi
