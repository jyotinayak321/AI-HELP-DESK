"""
generate_static_prompts.py
--------------------------
Synthesises the 7 missing pre-recorded WAV prompt files using
Windows SAPI5 (pyttsx3) and writes them to voice/static_prompts/.

Run from the backend directory with the venv activated:
    python generate_static_prompts.py
"""

import os
import sys
import tempfile
import shutil
import pyttsx3

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "voice", "static_prompts")

# (filename, text) — English prompts matching the tone of greeting.wav
PROMPTS = [
    (
        "ask_service_number.wav",
        "Please state your service number.",
    ),
    (
        "ask_complaint.wav",
        "Please describe your problem. You may start speaking now.",
    ),
    (
        "retry_service_number.wav",
        "Sorry, I could not catch your service number. Please say it again.",
    ),
    (
        "fallback_operator.wav",
        "We were unable to verify your service number by voice. An operator will now assist you.",
    ),
    (
        "goodbye.wav",
        "Thank you. Your ticket has been created. Please note your ticket number.",
    ),
    (
        "confirm_yes_no.wav",
        "Please say yes or no.",
    ),
    (
        "processing.wav",
        "Please wait. Your request is being processed.",
    ),
]


def synthesise_wav(engine, text, dest_path):
    """Synthesise text to a WAV file at dest_path. Returns True on success."""
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        engine.save_to_file(text, tmp_path)
        engine.runAndWait()

        if not os.path.isfile(tmp_path) or os.path.getsize(tmp_path) == 0:
            print(f"  [ERROR] pyttsx3 produced an empty file for: {text[:60]}")
            return False

        shutil.move(tmp_path, dest_path)
        size_kb = os.path.getsize(dest_path) / 1024
        print(f"  [OK] {os.path.basename(dest_path)}  ({size_kb:.1f} KB)")
        return True

    except Exception as exc:
        print(f"  [ERROR] {exc}")
        return False
    finally:
        if tmp_path and os.path.isfile(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"\nOutput directory: {OUTPUT_DIR}")
    print("Initialising SAPI5 engine ...\n")

    try:
        engine = pyttsx3.init("sapi5")
    except Exception as exc:
        print(f"[FATAL] Could not initialise SAPI5: {exc}")
        sys.exit(1)

    engine.setProperty("rate", 140)
    engine.setProperty("volume", 1.0)

    voices = engine.getProperty("voices")
    print(f"Available voices ({len(voices)}):")
    for v in voices:
        print(f"  {v.id}  ({v.name})")

    if voices:
        # Prefer ZIRA (female US English) if present, else first available
        chosen = next(
            (v for v in voices if "zira" in v.name.lower()), voices[0]
        )
        engine.setProperty("voice", chosen.id)
        print(f"\nUsing voice: {chosen.name}\n")

    ok = 0
    fail = 0
    for filename, text in PROMPTS:
        dest = os.path.join(OUTPUT_DIR, filename)
        print(f"Synthesising: {filename}")
        print(f"  Text: {text}")
        if synthesise_wav(engine, text, dest):
            ok += 1
        else:
            fail += 1

    print(f"\n{'='*50}")
    print(f"Done.  {ok} generated, {fail} failed.")
    if fail:
        print("Re-run or place manually recorded WAV files in:")
        print(f"  {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
