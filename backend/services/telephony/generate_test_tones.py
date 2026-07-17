"""
Phase 3 - Synthetic DTMF Test Tone Generator
-----------------------------------------------
Purpose : Generate a WAV file with real DTMF tones (dual sine waves)
          so dtmf_decoder.py can be tested without any phone hardware.

Usage:
    python generate_test_tones.py                  # generates "125#" by default
    python generate_test_tones.py --digits 90210*  # generate any digit sequence
    python generate_test_tones.py --out my_test.wav
"""

import argparse
import wave
import numpy as np

SAMPLE_RATE = 16000
TONE_DURATION = 0.3   # seconds each digit tone plays
GAP_DURATION = 0.2    # seconds of silence between digits
AMPLITUDE = 10000      # keep well under int16 max (32767) to avoid clipping

# Same frequency matrix as dtmf_decoder.py
DTMF_FREQUENCIES = {
    "1": (697, 1209), "2": (697, 1336), "3": (697, 1477), "A": (697, 1633),
    "4": (770, 1209), "5": (770, 1336), "6": (770, 1477), "B": (770, 1633),
    "7": (852, 1209), "8": (852, 1336), "9": (852, 1477), "C": (852, 1633),
    "*": (941, 1209), "0": (941, 1336), "#": (941, 1477), "D": (941, 1633),
}


def generate_tone(digit: str, sample_rate: int, duration: float) -> np.ndarray:
    """Generate one DTMF tone (sum of two sine waves) for a single digit."""
    if digit not in DTMF_FREQUENCIES:
        raise ValueError(f"'{digit}' is not a valid DTMF digit (0-9, *, #, A-D)")

    low_freq, high_freq = DTMF_FREQUENCIES[digit]
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    tone = 0.5 * np.sin(2 * np.pi * low_freq * t) + 0.5 * np.sin(2 * np.pi * high_freq * t)
    return tone


def generate_sequence_wav(digits: str, output_path: str):
    """Build a full WAV file: tone, gap, tone, gap... for each digit in `digits`."""
    silence = np.zeros(int(SAMPLE_RATE * GAP_DURATION))

    chunks = []
    for digit in digits:
        chunks.append(generate_tone(digit, SAMPLE_RATE, TONE_DURATION))
        chunks.append(silence)

    audio = np.concatenate(chunks)
    audio_int16 = (audio * AMPLITUDE).astype(np.int16)

    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_int16.tobytes())

    print(f"Generated '{digits}' as DTMF tones -> {output_path}")
    print(f"Total duration: {len(audio) / SAMPLE_RATE:.2f}s")


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic DTMF test tones")
    parser.add_argument("--digits", type=str, default="125#", help="Digit sequence to encode (0-9, *, #, A-D)")
    parser.add_argument("--out", type=str, default="test_dtmf.wav", help="Output WAV file path")
    args = parser.parse_args()

    generate_sequence_wav(args.digits, args.out)


if __name__ == "__main__":
    main()