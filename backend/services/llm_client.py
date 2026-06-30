"""
services/llm_client.py — LLM Guardrail & Fault/Severity Classifier
=====================================================================
Connects to the air-gapped vLLM server (Gemma 4) using the standard
OpenAI-compatible API to perform two functions:

  1. verify_and_correct_text() — Guardrail that:
       - Rejects non-English/Hindi/Hinglish input.
       - Fixes STT transcription errors (wrong words, garbled speech).
       - Rejects completely nonsensical complaints.
       - Returns the corrected text if valid.

  2. predict_fault_and_severity() — Classification that:
       - Predicts the fault_type from the known set of categories.
       - Predicts the severity from the known set of categories.
       - Replaces the old mDeBERTa-v3 zero-shot pipeline.

OFFLINE MODE:
  When settings.MOCK_LLM = True (default at home), no network calls are made.
  The functions return realistic mock data so the UI and logic can be built
  and tested without the air-gapped vLLM server.

  To switch to production mode:
    1. Set MOCK_LLM=False in .env or config.py
    2. Set VLLM_API_URL to the correct server URL in .env or config.py
"""

import json
import logging
from typing import Optional

from config import settings
from schemas import VALID_FAULT_TYPES, VALID_SEVERITIES

logger = logging.getLogger("services.llm_client")

# ---------------------------------------------------------------------------
# Lazy-import the openai package so the rest of the app still boots even if
# the package is not yet installed (e.g., in mock mode during development).
# ---------------------------------------------------------------------------
_openai_client = None

def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        try:
            import openai
            _openai_client = openai.OpenAI(
                base_url=settings.VLLM_API_URL,
                api_key=settings.VLLM_API_KEY,
            )
        except ImportError:
            logger.warning(
                "openai package not installed. Run: pip install openai. "
                "This is only required in production (MOCK_LLM=False)."
            )
            raise
    return _openai_client


# ---------------------------------------------------------------------------
# Internal helper — call the LLM and return the response text
# ---------------------------------------------------------------------------
def _call_llm(system_prompt: str, user_prompt: str, temperature: float = 0.1) -> str:
    """Make a single call to the vLLM server. Returns the raw response string."""
    client = _get_openai_client()
    response = client.chat.completions.create(
        model=settings.VLLM_MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=256,
        response_format={"type": "json_object"},  # Forces valid JSON output
    )
    return response.choices[0].message.content.strip()


# ===========================================================================
# PUBLIC FUNCTION 1: verify_and_correct_text
# ===========================================================================

_VERIFY_SYSTEM_PROMPT = """You are an expert IT support dispatcher for an Enterprise Help Desk.
Your job is to check if an incoming complaint text is valid and correct any Speech-to-Text (STT) transcription errors.
RULES:
1. ONLY accept complaints in English, Hindi, or Hinglish (a mix of Hindi and English). Reject any other language.
2. REJECT complaints that are completely nonsensical, random, or not related to any IT system or application problem (e.g. "what is the capital of France", "the dog ate my shoe").
3. ACCEPT and CORRECT complaints that are clearly about an IT issue but have garbled words due to STT errors (e.g. "my pasword is lok" should become "my password is locked").
4. Do NOT add information that was not present in the original text. Only fix obvious transcription errors.
5. Do NOT change the meaning of the complaint.
ACCEPTED LANGUAGES:
- English (any dialect or formality level)
- Hindi written in Roman script (e.g. "mera system on nahi ho raha")
- Hinglish — a natural mix of Hindi and English (e.g. "login nahi ho raha mujhe", "password reset karna hai")
- Do NOT reject text just because it contains Hindi words mixed with English — this is very common and MUST be accepted.
REJECTION RULES (reject ONLY if ALL of these are clearly true):
1. The text is in a completely unsupported language (e.g. French, Arabic, Chinese, Spanish) with NO English or Hindi words at all.
2. The text is completely unrelated to any IT system, software, hardware, network, login, or workplace application (e.g. "what is the capital of France", "the dog ate my shoe", "recipe for biryani").
3. The text is pure gibberish with no discernible meaning related to a technical problem (e.g. "asdf qwer zxcv", "blah blah blah").
DO NOT REJECT:
- Short complaints like "system slow", "login nahi ho raha", "network down" — these are VALID even if brief.
- Complaints with STT errors, garbled words, or repeated words — fix them instead.
- Complaints that mention an application name, even without much detail.
- Complaints in all-caps or all-lowercase.
- Complaints with punctuation errors or missing spaces.
STT CORRECTION RULES:
- Fix obvious homophones and misheard words caused by speech recognition:
    "pasword" → "password", "lok" → "locked", "acess" → "access",
    "loggin" → "login", "sistum" → "system", "notwerk" → "network",
    "cant" → "cannot", "wont" → "won't", "errror" → "error"
- Fix repeated words caused by STT stuttering: "my my system" → "my system"
- Fix missing spaces: "systemdown" → "system down", "cantlogin" → "can't login"
- Do NOT add information that was not present. Only fix obvious transcription errors.
- Do NOT change the meaning of the complaint.
RESPONSE FORMAT — You MUST respond with ONLY a valid JSON object:
If the complaint is valid:
{"status": "accepted", "corrected_text": "the corrected complaint text here"}
If the complaint is invalid:
{"status": "rejected", "reason": "A clear, brief, user-friendly reason why the complaint was rejected."}
EXAMPLES:
  "my pasword is lok" → {"status": "accepted", "corrected_text": "my password is locked"}
  "sistum nahi chal raha" → {"status": "accepted", "corrected_text": "system nahi chal raha"}
  "login nahi ho raha mujhe" → {"status": "accepted", "corrected_text": "login nahi ho raha mujhe"}
  "network slow hai sab ke liye" → {"status": "accepted", "corrected_text": "network slow hai sab ke liye"}
  "system slow" → {"status": "accepted", "corrected_text": "system slow"}
  "my my system is not working" → {"status": "accepted", "corrected_text": "my system is not working"}
  "what is the capital of France" → {"status": "rejected", "reason": "This does not appear to be an IT complaint. Please describe a technical issue."}
  "bonjour comment allez vous" → {"status": "rejected", "reason": "Please describe your complaint in English, Hindi, or Hinglish only."}
  "asdf qwer zxcv" → {"status": "rejected", "reason": "Could not understand your complaint. Please describe your technical issue clearly."}
Do NOT include any explanation, markdown, or text outside of the JSON object."""


def verify_and_correct_text(raw_text: str) -> dict:
    """
    Passes the raw complaint text through the LLM guardrail.

    Returns a dict with one of two shapes:
      - {"status": "accepted", "corrected_text": "..."}
      - {"status": "rejected", "reason": "..."}
    """
    # ── MOCK MODE ────────────────────────────────────────────────────────────
    if settings.MOCK_LLM:
        logger.info("[LLM MOCK] verify_and_correct_text called — returning mock response.")
        text_lower = raw_text.lower().strip()

        # Simulate a rejection for obviously nonsensical input
        NONSENSE_TRIGGERS = [
            "capital of", "what is", "who is", "dog ate",
            "weather", "recipe", "movie", "song", "cricket",
        ]
        if any(trigger in text_lower for trigger in NONSENSE_TRIGGERS):
            return {
                "status": "rejected",
                "reason": "[MOCK] This does not appear to be an IT helpdesk complaint. Please describe a technical issue with a system or application.",
            }

        # Simulate a language rejection for clearly non-English/Hindi text
        # (Basic check: if it contains characters from other scripts)
        NON_SUPPORTED_SCRIPTS = ["مرحبا", "你好", "こんにちは", "bonjour", "hola"]
        if any(word in text_lower for word in NON_SUPPORTED_SCRIPTS):
            return {
                "status": "rejected",
                "reason": "[MOCK] Please describe your complaint in English, Hindi, or Hinglish only.",
            }

        # Otherwise accept and return the text as-is with a mock fix note
        corrected = raw_text.strip()
        # Simulate a common STT fix: 'pasword' -> 'password', 'lok' -> 'locked'
        corrected = corrected.replace("pasword", "password").replace(" lok ", " locked ")
        return {"status": "accepted", "corrected_text": corrected}

    # ── PRODUCTION MODE ──────────────────────────────────────────────────────
    logger.info("[LLM] Calling vLLM to verify complaint text.")
    try:
        raw_response = _call_llm(_VERIFY_SYSTEM_PROMPT, raw_text)
        result = json.loads(raw_response)

        # Validate the response structure
        if "status" not in result:
            raise ValueError("LLM response missing 'status' field.")
        if result["status"] == "accepted" and "corrected_text" not in result:
            raise ValueError("LLM accepted complaint but missing 'corrected_text'.")
        if result["status"] == "rejected" and "reason" not in result:
            raise ValueError("LLM rejected complaint but missing 'reason'.")

        return result

    except (json.JSONDecodeError, ValueError, KeyError) as e:
        # If the LLM returns malformed JSON, log it and fail open (accept the text as-is)
        # to avoid blocking legitimate complaints due to a model error.
        logger.error("[LLM] Malformed response from vLLM during verification: %s", e)
        return {"status": "accepted", "corrected_text": raw_text}
    except Exception as e:
        logger.error("[LLM] Unexpected error calling vLLM for verification: %s", e)
        return {"status": "accepted", "corrected_text": raw_text}


# ===========================================================================
# PUBLIC FUNCTION 2: predict_fault_and_severity
# ===========================================================================

def _build_extract_svc_system_prompt() -> str:
    return """You are a precise data extraction assistant for an Enterprise Help Desk.
Your task is to extract the caller's service number from the given STT transcript.

Rules:
1. The service number format is exactly 3 letters followed by at least 1 digit (e.g. "ABC1", "SVC12345", "XYZ99").
2. The user might use the NATO phonetic military alphabet to spell out the letters (e.g., "Alpha Bravo Charlie 1" means "ABC1"). You must seamlessly translate phonetic alphabets into their corresponding single letters.
3. Ignore all conversational filler, background noise, or self-corrections. If the user corrects themselves, extract the final intended service number.
4. You must format the extracted service number exactly with NO spaces or dashes.
5. If no valid service number can be identified in the text, return null.

You MUST respond with ONLY a valid JSON object in this exact format:
{"service_number": "ABC1"}
OR
{"service_number": null}

Do NOT include any explanation, markdown, or text outside of the JSON object."""

def extract_service_number(raw_text: str) -> Optional[str]:
    """
    Uses the LLM to intelligently extract a service number from a raw STT transcript.
    """
    if settings.MOCK_LLM:
        logger.info("[LLM MOCK] extract_service_number called.")
        import re
        cleaned = raw_text.upper().replace(" ", "").replace("-", "")
        match = re.search(r'[A-Z]{3}[0-9]+', cleaned)
        return match.group(0) if match else None

    logger.info("[LLM] Calling vLLM to extract service number.")
    system_prompt = _build_extract_svc_system_prompt()
    try:
        raw_response = _call_llm(system_prompt, raw_text)
        result = json.loads(raw_response)
        
        svc_no = result.get("service_number")
        if not svc_no:
            return None
            
        import re
        svc_no = str(svc_no).upper().replace(" ", "").replace("-", "")
        if re.match(r'^[A-Z]{3}[0-9]+$', svc_no):
            return svc_no
        return None
    except Exception as e:
        logger.error("[LLM] Unexpected error extracting service number: %s", e)
        return None



def _build_classify_system_prompt() -> str:
    fault_list = ", ".join([f'"{f}"' for f in VALID_FAULT_TYPES])
    severity_list = ", ".join([f'"{s}"' for s in VALID_SEVERITIES])
    return f"""You are an expert IT support dispatcher for an Enterprise Help Desk.

Your job is to classify a complaint text into exactly ONE fault_type and ONE severity.

VALID FAULT TYPES (choose exactly one):
{fault_list}

FAULT TYPE DEFINITIONS:
- "login/access": Cannot log in, password issues, account locked, OTP not working, SSO failure, access denied.
- "performance/slow": Application is slow, lagging, timing out, hanging, loading forever.
- "data error": Wrong data displayed, incorrect figures, salary mismatch, record not found, data corruption.
- "total outage": Application completely down, server unreachable, 404/500 errors, no one can access.
- "partial/degraded": Some features work but others are broken, partial functionality, specific page/button not working.
- "other": Does not clearly fit into any of the above categories.

VALID SEVERITIES (choose exactly one):
{severity_list}

SEVERITY DEFINITIONS:
- "critical": Entire base or mission-critical systems are down, many users affected, operational impact.
  Keywords: "sab ke liye", "poora base", "nobody can", "all users", "emergency", "mission", "urgent"
- "high": An important workflow is broken for multiple users or a team.
  Keywords: "team", "hamare sab", "everyone in my unit", "many users", "multiple people"
- "normal": A single user has a routine issue with one system.
  This is the DEFAULT — use when no clear indicator of critical/high/low is present.
- "low": Minor cosmetic or non-blocking issue.
  Keywords: "cosmetic", "minor", "spelling", "colour", "UI", "not important", "whenever possible"

IMPORTANT RULES:
- If the complaint is in Hindi or Hinglish, still classify it correctly.
- If you are not sure about severity, default to "normal".
- If you are not sure about fault_type, default to "other".
- Never return a fault_type or severity outside the valid lists.

FEW-SHOT EXAMPLES:
  "my password is locked and I cannot log in" → {{"fault_type": "login/access", "severity": "normal"}}
  "login nahi ho raha mujhe" → {{"fault_type": "login/access", "severity": "normal"}}
  "the payroll system is down for everyone on base" → {{"fault_type": "total outage", "severity": "critical"}}
  "poora AFMS system band ho gaya hai" → {{"fault_type": "total outage", "severity": "critical"}}
  "system bahut slow chal raha hai" → {{"fault_type": "performance/slow", "severity": "normal"}}
  "meri salary mismatch hai, wrong amount show ho raha" → {{"fault_type": "data error", "severity": "normal"}}
  "the submit button on the leave portal is not working" → {{"fault_type": "partial/degraded", "severity": "normal"}}
  "network is very slow for entire squadron" → {{"fault_type": "performance/slow", "severity": "high"}}
  "minor spelling error on the dashboard" → {{"fault_type": "partial/degraded", "severity": "low"}}

You MUST respond with ONLY a valid JSON object in this exact format:
{{"fault_type": "<one of the valid fault types>", "severity": "<one of the valid severities>"}}

Do NOT include any explanation, markdown, or text outside of the JSON object."""


def predict_fault_and_severity(complaint_text: str) -> dict:
    """
    Uses the LLM to predict fault_type and severity for a complaint.

    Returns a dict with this shape:
      {"fault_type": "login/access", "severity": "normal"}
    """
    # ── MOCK MODE ────────────────────────────────────────────────────────────
    if settings.MOCK_LLM:
        logger.info("[LLM MOCK] predict_fault_and_severity called — returning mock response.")
        text_lower = complaint_text.lower()

        # Simple keyword matching to make the mock somewhat realistic
        fault_type = "other"
        if any(w in text_lower for w in ["login", "password", "access", "sso", "lock", "otp"]):
            fault_type = "login/access"
        elif any(w in text_lower for w in ["slow", "hang", "timeout", "loading", "lagging"]):
            fault_type = "performance/slow"
        elif any(w in text_lower for w in ["wrong", "incorrect", "mismatch", "data", "salary", "balance"]):
            fault_type = "data error"
        elif any(w in text_lower for w in ["down", "not opening", "unreachable", "crash"]):
            fault_type = "total outage"
        elif any(w in text_lower for w in ["some", "partial", "page", "button"]):
            fault_type = "partial/degraded"

        severity = "normal"
        if any(w in text_lower for w in ["emergency", "critical", "mission", "urgent", "all users"]):
            severity = "critical"
        elif any(w in text_lower for w in ["many", "everyone", "team", "all", "multiple"]):
            severity = "high"
        elif any(w in text_lower for w in ["cosmetic", "minor", "spelling", "ui", "colour"]):
            severity = "low"

        return {"fault_type": fault_type, "severity": severity}

    # ── PRODUCTION MODE ──────────────────────────────────────────────────────
    logger.info("[LLM] Calling vLLM to classify fault_type and severity.")
    system_prompt = _build_classify_system_prompt()
    try:
        raw_response = _call_llm(system_prompt, complaint_text)
        result = json.loads(raw_response)

        # Validate the response values are from the allowed sets
        fault_type = result.get("fault_type", "other")
        severity = result.get("severity", "normal")

        if fault_type not in VALID_FAULT_TYPES:
            logger.warning("[LLM] Invalid fault_type returned '%s'. Defaulting to 'other'.", fault_type)
            fault_type = "other"
        if severity not in VALID_SEVERITIES:
            logger.warning("[LLM] Invalid severity returned '%s'. Defaulting to 'normal'.", severity)
            severity = "normal"

        return {"fault_type": fault_type, "severity": severity}

    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.error("[LLM] Malformed response from vLLM during classification: %s", e)
        return {"fault_type": "other", "severity": "normal"}
    except Exception as e:
        logger.error("[LLM] Unexpected error calling vLLM for classification: %s", e)
        return {"fault_type": "other", "severity": "normal"}
