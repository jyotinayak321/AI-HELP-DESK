# backend/voice/prompts.py
# Pre-recorded audio file paths aur dynamic text templates

import os

# ── Base Path ──────────────────────────────────────────────────────
# Yahan pre-recorded .wav files hongi
PROMPTS_DIR = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "static", "voice_prompts"
)

# ── Pre-recorded Prompt Files ──────────────────────────────────────
# Ye files hum baad mein record karke rakhenge
PROMPT_FILES = {
    "welcome":          os.path.join(PROMPTS_DIR, "welcome.wav"),
    "ask_service_no":   os.path.join(PROMPTS_DIR, "ask_service_number.wav"),
    "retry_service_no": os.path.join(PROMPTS_DIR, "retry_service_number.wav"),
    "ask_complaint":    os.path.join(PROMPTS_DIR, "ask_complaint.wav"),
    "processing":       os.path.join(PROMPTS_DIR, "processing.wav"),
    "fallback":         os.path.join(PROMPTS_DIR, "operator_fallback.wav"),
    "thank_you":        os.path.join(PROMPTS_DIR, "thank_you.wav"),
}


# ── Dynamic Text Templates ─────────────────────────────────────────
# Jab pre-recorded file nahi hai toh TTS se yahi bolega

def get_welcome_text() -> str:
    return (
        "Namaste! AI Help Desk mein aapka swagat hai. "
        "Kripya apna service number boliye."
    )

def get_service_number_confirmation_text(service_no: str) -> str:
    """
    "2893456P" → "Kya aapka service number 2 8 9 3 4 5 6 P hai?"
    """
    spaced = ' '.join(list(service_no))
    return f"Kya aapka service number {spaced} hai? Haan ya nahi boliye."

def get_retry_text(retries_left: int) -> str:
    return (
        f"Service number samajh nahi aaya. "
        f"Kripya dobara boliye. Aapke paas {retries_left} aur mauke hain."
    )

def get_complaint_prompt_text() -> str:
    return (
        "Dhanyavaad! Ab kripya apni samasya ke baare mein bataiye. "
        "Kya problem aa rahi hai?"
    )

def get_fallback_text() -> str:
    return (
        "Maafi chahte hain. Service number samajh nahi aaya. "
        "Ek operator aapki madad karega. Kripya pratiksha karein."
    )

def get_ticket_confirmation_text(ticket_no: str) -> str:
    """
    "TIC-202606-0001" → readable format
    """
    spaced = ' '.join(list(ticket_no.replace('-', ' dash ')))
    return (
        f"Aapki complaint register ho gayi hai. "
        f"Aapka ticket number hai: {spaced}. "
        f"Dhanyavaad!"
    )

def prompt_file_exists(prompt_key: str) -> bool:
    """Check karo pre-recorded file exist karti hai ya nahi"""
    path = PROMPT_FILES.get(prompt_key, "")
    return os.path.exists(path)