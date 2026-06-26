"""
voice/validators.py — Service Number Validation (Phase 2)
===========================================================
Normalises speech-transcribed service numbers and validates them
against the expected AFNET format.

Requirements Covered:
  R-30: Voice capture of service number
  R-32: Service-number validation

Design Decisions:
  - Handles common STT artefacts: spelled-out digits ("one", "two"),
    multiplier words ("double", "triple"), Hindi digit words, and
    phonetic alphabet letters.
  - Regex pattern is kept broad (5–20 alphanumeric + dash) because
    the exact AFNET format may vary across units.
  - Returns a structured ValidationResult so the session manager can
    decide whether to retry, accept, or fall back.
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional

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

# NATO / common phonetic alphabet for letters
PHONETIC_TO_LETTER = {
    "alpha": "A", "alfa": "A",
    "bravo": "B",
    "charlie": "C",
    "delta": "D",
    "echo": "E",
    "foxtrot": "F",
    "golf": "G",
    "hotel": "H",
    "india": "I",
    "juliet": "J", "juliett": "J",
    "kilo": "K",
    "lima": "L",
    "mike": "M",
    "november": "N",
    "oscar": "O",
    "papa": "P",
    "quebec": "Q",
    "romeo": "R",
    "sierra": "S",
    "tango": "T",
    "uniform": "U",
    "victor": "V",
    "whiskey": "W",
    "x-ray": "X", "xray": "X",
    "yankee": "Y",
    "zulu": "Z",
}

MULTIPLIER_WORDS = {"double": 2, "triple": 3}

# Validation regex: 5–20 alphanumeric characters (with optional dashes)
SERVICE_NUMBER_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9\-]{3,18}[A-Z0-9]$")


@dataclass
class ValidationResult:
    """Result of service number normalisation + validation."""
    is_valid: bool
    normalised: str          # The cleaned / normalised value
    raw_input: str           # What the STT originally returned
    error_reason: Optional[str] = None


def normalise_service_number(raw_text: str) -> str:
    """
    Convert a speech transcription of a service number into its
    canonical alphanumeric form.

    Examples:
        "two eight nine three four five six papa"   → "2893456P"
        "double two nine three four five six P"     → "2293456P"
        "SVC dash one two three four five"          → "SVC-12345"
        "ek do teen char paanch"                    → "12345"
    """
    if not raw_text:
        return ""

    # Lowercase and strip
    text = raw_text.strip().lower()

    # Remove filler words and punctuation
    text = re.sub(r"[,.\?!]", " ", text)
    text = re.sub(r"\b(is|mera|my|number|hai|hain|service)\b", "", text)

    tokens = text.split()
    result_chars = []
    i = 0

    while i < len(tokens):
        token = tokens[i]

        # Check for multiplier ("double", "triple") followed by a value
        if token in MULTIPLIER_WORDS and i + 1 < len(tokens):
            count = MULTIPLIER_WORDS[token]
            next_token = tokens[i + 1]
            # Resolve the next token to a character
            char = _resolve_token(next_token)
            if char:
                result_chars.append(char * count)
                i += 2
                continue

        # Check if token is "dash" or "hyphen"
        if token in ("dash", "hyphen", "minus"):
            result_chars.append("-")
            i += 1
            continue

        # Resolve individual token
        char = _resolve_token(token)
        if char:
            result_chars.append(char)

        i += 1

    normalised = "".join(result_chars).upper().strip("-")
    return normalised


def _resolve_token(token: str) -> str:
    """Resolve a single token to its character representation."""
    # Direct digit
    if token.isdigit():
        return token

    # Single letter
    if len(token) == 1 and token.isalpha():
        return token.upper()

    # Word-to-digit mapping
    if token in WORD_TO_DIGIT:
        return WORD_TO_DIGIT[token]

    # Phonetic alphabet
    if token in PHONETIC_TO_LETTER:
        return PHONETIC_TO_LETTER[token]

    # Short uppercase abbreviation (e.g. "svc" spoken as letters)
    if len(token) <= 4 and token.isalpha():
        return token.upper()

    return ""


def validate_service_number(raw_stt_text: str) -> ValidationResult:
    """
    Normalise and validate a spoken service number.

    Parameters
    ----------
    raw_stt_text : str
        The raw text from the STT engine.

    Returns
    -------
    ValidationResult
        Whether the number is valid, the normalised form, and any error reason.
    """
    normalised = normalise_service_number(raw_stt_text)

    if not normalised:
        return ValidationResult(
            is_valid=False,
            normalised="",
            raw_input=raw_stt_text,
            error_reason="Could not extract any alphanumeric characters from speech.",
        )

    if len(normalised) < 5:
        return ValidationResult(
            is_valid=False,
            normalised=normalised,
            raw_input=raw_stt_text,
            error_reason=f"Too short ({len(normalised)} chars). Minimum 5 characters expected.",
        )

    if len(normalised) > 20:
        return ValidationResult(
            is_valid=False,
            normalised=normalised,
            raw_input=raw_stt_text,
            error_reason=f"Too long ({len(normalised)} chars). Maximum 20 characters expected.",
        )

    if not SERVICE_NUMBER_PATTERN.match(normalised):
        return ValidationResult(
            is_valid=False,
            normalised=normalised,
            raw_input=raw_stt_text,
            error_reason="Does not match expected service number pattern (alphanumeric with optional dashes).",
        )

    logger.info("Service number validated: '%s' → '%s'", raw_stt_text, normalised)

    return ValidationResult(
        is_valid=True,
        normalised=normalised,
        raw_input=raw_stt_text,
    )
