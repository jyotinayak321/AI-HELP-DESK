"""
voice/validators.py — Service Number Validation (Phase 2)
===========================================================
Normalises speech-transcribed service numbers and validates them
against the expected enterprise format.

Format: Exactly 5 digits (e.g. "12345", "45789")
"""

import re
import logging
import json
from dataclasses import dataclass
from typing import Optional

from config import settings
from services.llm_client import _call_llm

logger = logging.getLogger("voice.validators")

# ─────────────────────────────────────────────────────────────────────
# Lookup tables for speech-to-digit normalisation
# ─────────────────────────────────────────────────────────────────────

WORD_TO_DIGIT = {
    # English
    "zero": "0", "oh": "0", "o": "0",
    "one": "1", "won": "1",
    "two": "2", "to": "2", "too": "2",
    "three": "3", "tree": "3",
    "four": "4", "for": "4", "fore": "4",
    "five": "5",
    "six": "6", "sicks": "6",
    "seven": "7",
    "eight": "8", "ate": "8",
    "nine": "9", "niner": "9",
    # Hindi
    "shunya": "0", "sifar": "0",
    "ek": "1",
    "do": "2",
    "teen": "3", "tin": "3",
    "char": "4", "chaar": "4",
    "paanch": "5", "panch": "5",
    "chhah": "6", "chhe": "6", "cheh": "6",
    "saat": "7", "saath": "7",
    "aath": "8", "aat": "8",
    "nau": "9",
}

MULTIPLIER_WORDS = {"double": 2, "triple": 3}

# FIX: 5 digits only
SERVICE_NUMBER_PATTERN = re.compile(r"^[0-9]{5}$")


@dataclass
class ValidationResult:
    """Result of service number normalisation + validation."""
    is_valid: bool
    normalised: str
    raw_input: str
    error_reason: Optional[str] = None


def normalise_service_number(raw_text: str) -> str:
    """
    Convert a speech transcription of a service number into its
    canonical 5-digit form.

    Examples:
        "one two three four five"   → "12345"
        "45789"                     → "45789"
        "ek do teen char paanch"    → "12345"
        "double two nine three four"→ "22934"
    """
    # ── FAST PATH: Direct 5-digit scan ───────────────────────────────
    compacted = re.sub(r'\s+', '', raw_text.strip()).upper()
    # FIX: Search for exactly 5 digits
    direct_match = re.search(r'[0-9]{5}', compacted)
    if direct_match:
        logger.info("normalise_service_number fast-path: '%s' → '%s'", raw_text, direct_match.group(0))
        return direct_match.group(0)

    # ── SLOW PATH: Token-by-token translation ─────────────────────────
    text = raw_text.strip().lower()
    text = re.sub(r"[,.\?!]", " ", text)
    text = re.sub(r"\b(is|mera|my|number|hai|hain|service|no|the|an|ok|okay|please)\b", "", text)

    tokens = text.split()
    result_chars = []
    i = 0

    while i < len(tokens):
        token = tokens[i]

        # Multiplier words ("double 4" → "44")
        if token in MULTIPLIER_WORDS and i + 1 < len(tokens):
            count = MULTIPLIER_WORDS[token]
            next_token = tokens[i + 1]
            char = _resolve_token(next_token)
            if char:
                result_chars.append(char * count)
                i += 2
                continue

        # Resolve individual token
        char = _resolve_token(token)
        if char:
            result_chars.append(char)

        i += 1

    raw_joined = "".join(result_chars).strip()

    # FIX: Extract exactly 5 digits
    match = re.search(r'[0-9]{5}', raw_joined)
    if match:
        return match.group(0)

    # Return whatever digits we got (validation will catch if wrong count)
    digits_only = re.sub(r'[^0-9]', '', raw_joined)
    return digits_only


def _resolve_token(token: str) -> str:
    """Resolve a single spoken token to its digit character."""
    # Direct digit string
    if token.isdigit():
        return token

    # Word-to-digit mapping
    if token in WORD_TO_DIGIT:
        return WORD_TO_DIGIT[token]

    return ""


def _build_extract_svc_system_prompt() -> str:
    return """You are a precise data extraction assistant for an Enterprise IT Help Desk.
Your ONLY task is to extract the caller's service number from an STT (speech-to-text) transcript.

SERVICE NUMBER FORMAT: Exactly 5 digits only. Examples: "12345", "45789", "99001".

DIGIT RECOGNITION — spoken digits must be converted to numerals:
  - English words:  "zero/oh"=0, "one/won"=1, "two/to/too"=2, "three/tree"=3, "four/for"=4,
                    "five"=5, "six"=6, "seven"=7, "eight/ate"=8, "nine/niner"=9
  - Hindi words:    "shunya/sifar"=0, "ek"=1, "do"=2, "teen/tin"=3, "char/chaar"=4,
                    "paanch/panch"=5, "chhah/chhe"=6, "saat/saath"=7, "aath/aat"=8, "nau"=9
  - Multipliers:    "double X" means XX (e.g. "double four" = 44), "triple X" means XXX

SELF-CORRECTION: If the user corrects themselves, extract the FINAL intended value.
  Example: "my number is 4 5 6 7... no wait, 4 5 7 8 9" → "45789"

FILLER WORDS TO IGNORE: "my", "service", "number", "is", "hai", "mera", "sir", "please", "ok", "uh", "um", "haan"

CONCRETE EXAMPLES:
  "four five seven eight nine"        → {"service_number": "45789"}
  "45789"                             → {"service_number": "45789"}
  "one two three four five"           → {"service_number": "12345"}
  "ek do teen char paanch"            → {"service_number": "12345"}
  "mera number hai 4 5 7 8 9"         → {"service_number": "45789"}
  "double two nine three four"        → {"service_number": "22934"}
  "hello sir"                         → {"service_number": null}
  "I don't know"                      → {"service_number": null}

You MUST respond with ONLY a valid JSON object in this exact format:
{"service_number": "12345"}
OR
{"service_number": null}

Do NOT include any explanation, markdown, or text outside of the JSON object."""


def extract_service_number(raw_text: str) -> Optional[str]:
    """
    Extract a 5-digit service number from raw STT transcript.
    Uses LLM if available, else falls back to regex normaliser.
    """
    if settings.MOCK_LLM:
        logger.info("[LLM MOCK] extract_service_number: using regex fallback.")
        return normalise_service_number(raw_text)

    logger.info("[LLM] Calling LLM to extract service number.")
    system_prompt = _build_extract_svc_system_prompt()
    try:
        raw_response = _call_llm(system_prompt, raw_text)
        result = json.loads(raw_response)

        svc_no = result.get("service_number")
        if not svc_no:
            return None

        # FIX: Clean and validate as 5 digits only
        svc_no = re.sub(r'[^0-9]', '', str(svc_no))
        if re.match(r'^[0-9]{5}$', svc_no):
            return svc_no
        return None
    except Exception as e:
        logger.error("[LLM] Error extracting service number: %s", e)
        return None


def validate_service_number(raw_stt_text: str) -> ValidationResult:
    """
    Normalise and validate a spoken service number.
    Expected format: exactly 5 digits (e.g. "12345").
    """
    normalised = extract_service_number(raw_stt_text)

    # Could not extract anything
    if not normalised:
        return ValidationResult(
            is_valid=False,
            normalised="",
            raw_input=raw_stt_text,
            error_reason="Could not extract any digits from speech.",
        )

    # FIX: Validate as exactly 5 digits
    if not re.match(r"^[0-9]{5}$", normalised):
        return ValidationResult(
            is_valid=False,
            normalised=normalised,
            raw_input=raw_stt_text,
            error_reason=f"Expected exactly 5 digits, got: '{normalised}'",
        )

    logger.info("Service number validated: '%s' → '%s'", raw_stt_text, normalised)

    return ValidationResult(
        is_valid=True,
        normalised=normalised,
        raw_input=raw_stt_text,
    )
