# backend/voice/tts.py
# TTS = Text To Speech
# Ye file text ko audio mein convert karegi using Windows SAPI5

import pyttsx3
import tempfile
import os
import logging

logger = logging.getLogger(__name__)

# ── Singleton Pattern ──────────────────────────────────────────────
_engine = None

def get_tts_engine():
    """
    TTS engine ek baar initialize karo
    Windows SAPI5 use karega — fully offline
    """
    global _engine
    if _engine is None:
        logger.info("Initializing TTS engine...")
        _engine = pyttsx3.init()

        # Speaking speed set karo (150 = normal)
        _engine.setProperty('rate', 145)

        # Volume set karo (0.0 to 1.0)
        _engine.setProperty('volume', 0.95)

        # Hindi voice dhundho agar available ho
        voices = _engine.getProperty('voices')
        for v in voices:
            if any(word in v.name.lower() for word in ['hindi', 'indian', 'heera']):
                _engine.setProperty('voice', v.id)
                logger.info(f"Hindi voice set: {v.name}")
                break
        else:
            logger.info("Hindi voice not found, using default voice")

        logger.info("TTS engine initialized!")
    return _engine


# ── Main Function ──────────────────────────────────────────────────
def synthesize_text(text: str) -> bytes:
    """
    Text lega → WAV audio bytes return karega

    Args:
        text: "Aapka service number 2893456P hai. Kya ye sahi hai?"

    Returns:
        WAV audio as bytes
    """
    engine = get_tts_engine()

    # Temp file mein save karo
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        logger.info(f"Synthesizing: '{text[:50]}...'")

        engine.save_to_file(text, tmp_path)
        engine.runAndWait()

        # File read karke bytes return karo
        with open(tmp_path, 'rb') as f:
            audio_bytes = f.read()

        logger.info(f"TTS generated: {len(audio_bytes)} bytes")
        return audio_bytes

    except Exception as e:
        logger.error(f"TTS failed: {e}")
        raise RuntimeError(f"TTS Error: {str(e)}")

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ── Helper Functions ───────────────────────────────────────────────
def ticket_number_to_speech(ticket_no: str) -> str:
    """
    Ticket number ko speakable format mein convert karo

    Example:
        "TIC-202606-0001" → "T I C dash 2 0 2 6 0 6 dash 0 0 0 1"

    Taaki TTS har character clearly bole
    """
    result = []
    for ch in ticket_no:
        if ch == '-':
            result.append('dash')
        elif ch.isdigit():
            result.append(ch)          # "1" → "1" (TTS reads digit by digit)
        else:
            result.append(ch.upper())  # "T" → "T"
    return ' '.join(result)


def service_number_to_speech(service_no: str) -> str:
    """
    Service number ko clearly readable format mein convert karo

    Example:
        "2893456P" → "2 8 9 3 4 5 6 P"
    """
    return ' '.join(list(service_no))


# ── Quick Test ─────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Testing TTS module...")
    engine = get_tts_engine()

    test_text = "Namaste! Aapka service number 2 8 9 3 4 5 6 P hai. Kya ye sahi hai?"
    print(f"Speaking: '{test_text}'")

    audio = synthesize_text(test_text)
    print(f"✅ Generated {len(audio)} bytes of audio")

    ticket_speech = ticket_number_to_speech("TIC-202606-0001")
    print(f"Ticket speech format: '{ticket_speech}'")