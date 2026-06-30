"""
voice/validators.py — Service Number Validation (Phase 2)
===========================================================
Normalises speech-transcribed service numbers and validates them
against the expected enterprise network format.

Requirements Covered:
  R-30: Voice capture of service number
  R-32: Service-number validation

Design Decisions:
  - Handles common STT artefacts: spelled-out digits ("one", "two"),
    multiplier words ("double", "triple"), Hindi digit words, and
    phonetic alphabet letters.
  - Regex pattern is kept broad (5–20 alphanumeric + dash) because
    the exact service number format may vary across units.
  - Returns a structured ValidationResult so the session manager can
    decide whether to retry, accept, or fall back.
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
    # ── FAST PATH: Direct pattern scan of the raw text ───────────────────────────
    # When the STT outputs a compact token like "457F" or "457 F" we can just
    # strip whitespace and search for the pattern directly — no token splitting needed.
    # This handles the very common case where the user says the number slowly but
    # the STT correctly groups it into one or two clean tokens.
    compacted = re.sub(r'\s+', '', raw_text.strip()).upper()
    direct_match = re.search(r'[0-9]{3}[A-Z]', compacted)
    if direct_match:
        logger.info("normalise_service_number fast-path: '%s' → '%s'", raw_text, direct_match.group(0))
        return direct_match.group(0)

    # ── SLOW PATH: Token-by-token translation (spoken words like "four five seven F") ─
    # Lowercase and strip
    text = raw_text.strip().lower()

    # Remove filler words and punctuation
    text = re.sub(r"[,.\?!]", " ", text)
    text = re.sub(r"\b(is|mera|my|number|hai|hain|service|no|the|an|ok|okay|please)\b", "", text)
    # Note: "a" is intentionally NOT in the stopword list because it resolves to "0".

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

    raw_joined = "".join(result_chars).upper().strip("-")
    
    # Search for 3 digits followed by 1 letter in the joined string
    match = re.search(r'[0-9]{3}[A-Z]', raw_joined)
    if match:
        normalised = match.group(0)
    else:
        normalised = raw_joined
        
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


def _build_extract_svc_system_prompt() -> str:
    return """You are a precise data extraction assistant for an Enterprise IT Help Desk.
Your ONLY task is to extract the caller's service number from an STT (speech-to-text) transcript.

SERVICE NUMBER FORMAT: Exactly 3 digits followed by exactly 1 uppercase letter. Examples: "123A", "457F", "999Z".

DIGIT RECOGNITION — spoken digits must be converted to numerals:
  - English words:  "zero/oh"=0, "one/won"=1, "two/to/too"=2, "three/tree"=3, "four/for"=4,
                    "five"=5, "six"=6, "seven"=7, "eight/ate"=8, "nine/niner"=9
  - Hindi words:    "shunya/sifar"=0, "ek"=1, "do"=2, "teen/tin"=3, "char/chaar"=4,
                    "paanch/panch"=5, "chhah/chhe"=6, "saat/saath"=7, "aath/aat"=8, "nau"=9
  - Multipliers:    "double X" means XX (e.g. "double four" = 44), "triple X" means XXX

LETTER RECOGNITION — spoken/phonetic letters must be converted to single uppercase letters:
  - Direct letters: "A", "B", ... "Z" spoken as individual letters
  - NATO phonetic:  Alpha=A, Bravo=B, Charlie=C, Delta=D, Echo=E, Foxtrot=F, Golf=G,
                    Hotel=H, India=I, Juliet/Juliett=J, Kilo=K, Lima=L, Mike=M,
                    November=N, Oscar=O, Papa=P, Quebec=Q, Romeo=R, Sierra=S,
                    Tango=T, Uniform=U, Victor=V, Whiskey=W, X-Ray/Xray=X, Yankee=Y, Zulu=Z
  - Alternate spellings are also valid: "Alfa"=A, "Foxtrot"=F etc.

SELF-CORRECTION: If the user corrects themselves mid-sentence, extract the FINAL intended value.
  Example: "my number is 4 5 6... no wait, 4 5 7 Foxtrot" → "457F"

FILLER WORDS TO IGNORE: "my", "service", "number", "is", "hai", "mera", "sir", "please", "ok", "uh", "um", "haan"

CONCRETE EXAMPLES:
  "four five seven foxtrot"       → {"service_number": "457F"}
  "457 F"                         → {"service_number": "457F"}
  "457 alpha"                     → {"service_number": "457A"}
  "457 Alpha"                     → {"service_number": "457A"}
  "four five seven alpha"         → {"service_number": "457A"}
  "chaar paanch saat foxtrot"     → {"service_number": "457F"}
  "one two three A"               → {"service_number": "123A"}
  "double two nine Zulu"          → {"service_number": "229Z"}
  "mera number hai 4 5 7 F"       → {"service_number": "457F"}
  "uh my number, ek do teen Bravo"→ {"service_number": "123B"}
  "hello sir"                     → {"service_number": null}
  "I don't know"                  → {"service_number": null}

You MUST respond with ONLY a valid JSON object in this exact format:
{"service_number": "123A"}
OR
{"service_number": null}

Do NOT include any explanation, markdown, or text outside of the JSON object."""


def extract_service_number(raw_text: str) -> Optional[str]:
    """
    Uses the LLM to intelligently extract a service number from a raw STT transcript.
    """
    if settings.MOCK_LLM:
        logger.info("[LLM MOCK] extract_service_number called. Using regex fallback.")
        # We reuse the python-based normaliser for mock mode so it can handle
        # translated phonetic words (e.g. "one two three") offline.
        return normalise_service_number(raw_text)

    logger.info("[LLM] Calling vLLM to extract service number.")
    system_prompt = _build_extract_svc_system_prompt()
    try:
        raw_response = _call_llm(system_prompt, raw_text)
        result = json.loads(raw_response)
        
        svc_no = result.get("service_number")
        if not svc_no:
            return None
            
        svc_no = str(svc_no).upper().replace(" ", "").replace("-", "")
        if re.match(r'^[0-9]{3}[A-Z]$', svc_no):
            return svc_no
        return None
    except Exception as e:
        logger.error("[LLM] Unexpected error extracting service number: %s", e)
        return None


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
    # Use the LLM to extract the service number intelligently
    normalised = extract_service_number(raw_stt_text)

    if not normalised:
        return ValidationResult(
            is_valid=False,
            normalised="",
            raw_input=raw_stt_text,
            error_reason="Could not extract any alphanumeric characters from speech.",
        )



    if not re.match(r"^[0-9]{3}[A-Z]$", normalised):
        return ValidationResult(
            is_valid=False,
            normalised=normalised,
            raw_input=raw_stt_text,
            error_reason="Does not match expected service number pattern (3 digits followed by 1 letter).",
        )

    logger.info("Service number validated: '%s' → '%s'", raw_stt_text, normalised)

    return ValidationResult(
        is_valid=True,
        normalised=normalised,
        raw_input=raw_stt_text,
    )
