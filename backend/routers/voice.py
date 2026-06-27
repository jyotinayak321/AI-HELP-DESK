# backend/routers/voice.py
# Voice API endpoints — frontend se audio aata hai, response jaata hai

import uuid
import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlmodel import Session, select

from database import get_session
from voice.stt import transcribe_audio
from voice.tts import synthesize_text, service_number_to_speech
from voice.validators import normalize_service_number, validate_service_number
from voice.session import VoiceSession
from voice.prompts import (
    get_welcome_text,
    get_service_number_confirmation_text,
    get_retry_text,
    get_complaint_prompt_text,
    get_fallback_text,
    get_ticket_confirmation_text,
)

router = APIRouter(prefix="/api/voice", tags=["Voice Layer"])
logger = logging.getLogger(__name__)


# ── 1. Session Start ───────────────────────────────────────────────
@router.post("/start")
def start_voice_session(db: Session = Depends(get_session)):
    """
    Naya voice session shuru karo
    Frontend yahan call karega jab user mic button dabayega
    """
    session_id = str(uuid.uuid4())

    vs = VoiceSession(
        id=session_id,
        state="CAPTURING_SERVICE_NUMBER",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(vs)
    db.commit()

    logger.info(f"New voice session started: {session_id}")

    return {
        "session_id": session_id,
        "state": "CAPTURING_SERVICE_NUMBER",
        "message": get_welcome_text(),
    }


# ── 2. Service Number Audio Upload ─────────────────────────────────
@router.post("/service-number")
async def capture_service_number(
    session_id: str = Form(...),
    audio: UploadFile = File(...),
    db: Session = Depends(get_session),
):
    """
    User ka service number audio upload karo
    STT se transcribe karo → validate karo → response do
    """
    # Session dhundho
    vs = db.get(VoiceSession, session_id)
    if not vs:
        raise HTTPException(status_code=404, detail="Session not found")

    if vs.state == "OPERATOR_FALLBACK":
        raise HTTPException(status_code=400, detail="Session in fallback mode")

    # Audio bytes read karo
    audio_bytes = await audio.read()
    logger.info(f"Received audio: {len(audio_bytes)} bytes for session {session_id}")

    # STT — audio → text
    try:
        stt_result = transcribe_audio(audio_bytes)
        raw_text = stt_result["text"]
        logger.info(f"STT result: '{raw_text}'")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"STT failed: {str(e)}")

    # Normalize aur validate
    normalized = normalize_service_number(raw_text)
    is_valid = validate_service_number(normalized)

    if is_valid:
        # ✅ Valid — next state
        vs.service_no = normalized
        vs.state = "CONFIRMING_SERVICE_NUMBER"
        vs.reset_retries()

        confirmation_text = get_service_number_confirmation_text(normalized)

        db.add(vs)
        db.commit()

        return {
            "session_id": session_id,
            "state": vs.state,
            "recognized_text": normalized,
            "is_valid": True,
            "confirmation_message": confirmation_text,
            "retries_count": vs.retries_count,
        }
    else:
        # ❌ Invalid — retry ya fallback
        vs.increment_retry()

        if vs.is_max_retries_exceeded():
            vs.state = "OPERATOR_FALLBACK"
            db.add(vs)
            db.commit()
            return {
                "session_id": session_id,
                "state": "OPERATOR_FALLBACK",
                "recognized_text": normalized,
                "is_valid": False,
                "message": get_fallback_text(),
                "retries_count": vs.retries_count,
            }

        retries_left = vs.max_retries - vs.retries_count
        db.add(vs)
        db.commit()

        return {
            "session_id": session_id,
            "state": "CAPTURING_SERVICE_NUMBER",
            "recognized_text": normalized,
            "is_valid": False,
            "message": get_retry_text(retries_left),
            "retries_count": vs.retries_count,
        }


# ── 3. Confirm Service Number ──────────────────────────────────────
@router.post("/confirm")
def confirm_service_number(
    session_id: str,
    confirmed: bool,
    db: Session = Depends(get_session),
):
    """
    User ne haan/nahi bola service number ke liye
    confirmed=True → complaint capture karo
    confirmed=False → dubara service number lo
    """
    vs = db.get(VoiceSession, session_id)
    if not vs:
        raise HTTPException(status_code=404, detail="Session not found")

    if confirmed:
        vs.state = "CAPTURING_COMPLAINT"
        message = get_complaint_prompt_text()
    else:
        vs.state = "CAPTURING_SERVICE_NUMBER"
        vs.service_no = None
        vs.reset_retries()
        message = "Theek hai. Kripya dobara apna service number boliye."

    vs.updated_at = datetime.utcnow()
    db.add(vs)
    db.commit()

    return {
        "session_id": session_id,
        "state": vs.state,
        "message": message,
    }


# ── 4. Complaint Audio Upload ──────────────────────────────────────
@router.post("/complaint")
async def capture_complaint(
    session_id: str = Form(...),
    audio: UploadFile = File(...),
    db: Session = Depends(get_session),
):
    """
    User ki complaint audio upload karo
    STT se transcribe karo → Phase 1 classifier ko bhejo
    """
    vs = db.get(VoiceSession, session_id)
    if not vs:
        raise HTTPException(status_code=404, detail="Session not found")

    if vs.state != "CAPTURING_COMPLAINT":
        raise HTTPException(
            status_code=400,
            detail=f"Wrong state: {vs.state}. Expected: CAPTURING_COMPLAINT"
        )

    # Audio → Text
    audio_bytes = await audio.read()
    try:
        stt_result = transcribe_audio(audio_bytes)
        transcript = stt_result["text"]
        logger.info(f"Complaint transcript: '{transcript}'")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"STT failed: {str(e)}")

    # Session update karo
    vs.complainant_txt = transcript
    vs.state = "OPERATOR_REVIEW"
    vs.updated_at = datetime.utcnow()
    db.add(vs)
    db.commit()

    # TODO: Phase 1 ke create_intake function ko call karo
    # from backend.routers.tickets import create_intake
    # intake_result = await create_intake(...)

    return {
        "session_id": session_id,
        "state": "OPERATOR_REVIEW",
        "transcript": transcript,
        "service_no": vs.service_no,
        "message": "Complaint record ho gayi. Operator review karega.",
    }


# ── 5. Session Status ──────────────────────────────────────────────
@router.get("/status")
def get_session_status(
    session_id: str,
    db: Session = Depends(get_session),
):
    """Current session ki state check karo"""
    vs = db.get(VoiceSession, session_id)
    if not vs:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": vs.id,
        "state": vs.state,
        "service_no": vs.service_no,
        "retries_count": vs.retries_count,
        "intake_id": vs.intake_id,
        "ticket_number": vs.ticket_number,
        "created_at": vs.created_at,
    }


# ── 6. TTS Endpoint ────────────────────────────────────────────────
@router.get("/tts")
def text_to_speech(text: str):
    """
    Text do → WAV audio wapas lo
    Frontend is URL se audio play karega
    """
    try:
        audio_bytes = synthesize_text(text)
        return Response(
            content=audio_bytes,
            media_type="audio/wav",
            headers={"Content-Disposition": "inline; filename=tts_output.wav"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS failed: {str(e)}")