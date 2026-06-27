# backend/voice/validators.py
import re
import logging

logger = logging.getLogger(__name__)

WORD_TO_DIGIT = {
    "zero": "0", "oh": "0", "o": "0",
    "one": "1",
    "two": "2", "to": "2", "too": "2",
    "three": "3",
    "four": "4", "for": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "niner": "9",
}

PHONETIC_MAP = {
    "alpha":"A","bravo":"B","charlie":"C","delta":"D",
    "echo":"E","foxtrot":"F","golf":"G","hotel":"H",
    "india":"I","juliet":"J","kilo":"K","lima":"L",
    "mike":"M","november":"N","oscar":"O","papa":"P",
    "quebec":"Q","romeo":"R","sierra":"S","tango":"T",
    "uniform":"U","victor":"V","whiskey":"W","xray":"X",
    "yankee":"Y","zulu":"Z",
}

# 7 digits + 1 Capital Letter e.g. "2893456P"
SERVICE_NO_PATTERN = re.compile(r'^\d{7}[A-Z]$')


def normalize_service_number(raw_text: str) -> str:
    if not raw_text:
        return ""

    # Already correct format?
    if SERVICE_NO_PATTERN.match(raw_text.upper()):
        return raw_text.upper()

    text = raw_text.lower().strip()
    tokens = text.split()
    result = []
    i = 0

    while i < len(tokens):
        token = tokens[i]

        # "double two" → "22"
        if token == "double" and i + 1 < len(tokens):
            digit = WORD_TO_DIGIT.get(tokens[i+1])
            if digit:
                result.append(digit * 2)
                i += 2
                continue

        # "triple two" → "222"
        if token == "triple" and i + 1 < len(tokens):
            digit = WORD_TO_DIGIT.get(tokens[i+1])
            if digit:
                result.append(digit * 3)
                i += 2
                continue

        # Word to digit
        digit = WORD_TO_DIGIT.get(token)
        if digit:
            result.append(digit)
            i += 1
            continue

        # Phonetic alphabet "papa" → "P"
        letter = PHONETIC_MAP.get(token)
        if letter:
            result.append(letter)
            i += 1
            continue

        # Direct digit or letter
        if token.isdigit():
            result.append(token)
        elif len(token) == 1 and token.isalpha():
            result.append(token.upper())

        i += 1

    return ''.join(result).upper()


def validate_service_number(normalized: str) -> bool:
    is_valid = bool(SERVICE_NO_PATTERN.match(normalized))
    logger.info(f"Validation '{normalized}': {'PASS' if is_valid else 'FAIL'}")
    return is_valid


if __name__ == "__main__":
    tests = [
        ("two eight nine three four five six papa", "2893456P"),
        ("double two five three four five six P",   "2253456P"),
        ("2893456P",                                 "2893456P"),
    ]
    print("Testing validators...\n")
    all_pass = True
    for raw, expected in tests:
        result = normalize_service_number(raw)
        ok = "✅" if result == expected else "❌"
        if result != expected:
            all_pass = False
        print(f"{ok} '{raw}'")
        print(f"   Got: '{result}' | Expected: '{expected}'\n")
    print("✅ All tests passed!" if all_pass else "❌ Some failed!")