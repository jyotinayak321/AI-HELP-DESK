# backend/voice/stt.py
# STT = Speech To Text
# Ye file audio ko text mein convert karegi using Whisper model

from faster_whisper import WhisperModel
import tempfile
import os
import logging

logger = logging.getLogger(__name__)

# ── Singleton Pattern ──────────────────────────────────────────────
# Model ek baar load hoga — RAM bachane ke liye
_model = None

def get_stt_model():
    global _model
    if _model is None:
        logger.info("Loading Whisper STT model... please wait")

        MODEL_ROOT = os.environ.get(
            "WHISPER_MODEL_ROOT",
            "C:/Users/rajes/Desktop/AI-HELP-DESK/AI-HELP-DESK/models/whisper"
        )

        _model = WhisperModel(
            "small",
            device="cpu",
            compute_type="int8",
            local_files_only=False,
            download_root=MODEL_ROOT
        )
        logger.info("Whisper model loaded successfully!")
    return _model

# ── Main Function ──────────────────────────────────────────────────
def transcribe_audio(audio_bytes: bytes, language: str = None) -> dict:
    """
    Audio bytes lega → text return karega

    Args:
        audio_bytes: .wav ya .webm audio ka raw data
        language: "hi" Hindi, "en" English, None = auto detect

    Returns:
        {
            "text": "mera HRMS system nahi chal raha",
            "language": "hi",
            "confidence": 0.92
        }
    """
    model = get_stt_model()

    # Temp file banao — Whisper ko file path chahiye, bytes nahi
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        logger.info(f"Transcribing audio file: {tmp_path}")

        segments, info = model.transcribe(
            tmp_path,
            language=language,       # None = Whisper khud detect karega
            beam_size=5,             # Accuracy vs speed balance
            vad_filter=True,         # Silence remove karega
            vad_parameters=dict(
                min_silence_duration_ms=500
            )
        )

        # Segments ko join karo full text banane ke liye
        full_text = " ".join([seg.text.strip() for seg in segments])
        full_text = full_text.strip()

        logger.info(f"Transcription: '{full_text}' | Lang: {info.language}")

        return {
            "text": full_text,
            "language": info.language,
            "confidence": round(info.language_probability, 2)
        }

    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise RuntimeError(f"STT Error: {str(e)}")

    finally:
        # Temp file delete karo — cleanup
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ── Quick Test ─────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Testing STT module...")
    print("Model load ho raha hai — 30-60 seconds wait karo...")
    model = get_stt_model()
    print("✅ STT Model loaded successfully!")
    print("Real audio test ke liye voice router use karo.")