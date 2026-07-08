"""
Phase 3 - DTMF Tone Decoder using the Goertzel Algorithm (R-43)
-----------------------------------------------------------------
Purpose : Decode DTMF keypad tones from captured call audio
          WITHOUT any external/cloud library - fully air-gap safe.

Usage:
    python dtmf_decoder.py test_capture.wav
"""

import sys
import wave
import numpy as np

# DTMF frequency matrix
# Row = low frequency group, Column = high frequency group
LOW_FREQS = [697, 770, 852, 941]
HIGH_FREQS = [1209, 1336, 1477, 1633]

DTMF_TABLE = {
    (697, 1209): "1", (697, 1336): "2", (697, 1477): "3", (697, 1633): "A",
    (770, 1209): "4", (770, 1336): "5", (770, 1477): "6", (770, 1633): "B",
    (852, 1209): "7", (852, 1336): "8", (852, 1477): "9", (852, 1633): "C",
    (941, 1209): "*", (941, 1336): "0", (941, 1477): "#", (941, 1633): "D",
}

SAMPLE_RATE = 16000
BLOCK_SIZE = 205          # ~12.8ms block at 16kHz - enough samples for
                          # Goertzel to clearly separate DTMF frequencies
MAGNITUDE_THRESHOLD = 3.0 # minimum energy to call it a real tone, not noise


def goertzel(samples: np.ndarray, target_freq: float, sample_rate: int) -> float:
    """
    Compute the "energy" of `target_freq` inside `samples` using the
    Goertzel algorithm. Cheaper than a full FFT when you only care
    about a handful of known frequencies - exactly our DTMF case.
    """
    n = len(samples)
    k = int(0.5 + (n * target_freq) / sample_rate)
    omega = (2.0 * np.pi * k) / n
    coeff = 2.0 * np.cos(omega)

    s_prev = 0.0
    s_prev2 = 0.0
    for sample in samples:
        s = sample + coeff * s_prev - s_prev2
        s_prev2 = s_prev
        s_prev = s

    power = s_prev2 ** 2 + s_prev ** 2 - coeff * s_prev * s_prev2
    return float(np.sqrt(abs(power)))


def detect_dtmf_in_block(samples: np.ndarray, sample_rate: int):
    """
    Given one small block of audio, find the strongest low-frequency
    and high-frequency DTMF component, and return the matching digit
    if both are strong enough (i.e. an actual tone, not speech/silence).
    """
    low_mags = [goertzel(samples, f, sample_rate) for f in LOW_FREQS]
    high_mags = [goertzel(samples, f, sample_rate) for f in HIGH_FREQS]

    best_low = LOW_FREQS[int(np.argmax(low_mags))]
    best_high = HIGH_FREQS[int(np.argmax(high_mags))]

    if max(low_mags) < MAGNITUDE_THRESHOLD or max(high_mags) < MAGNITUDE_THRESHOLD:
        return None  # no tone strong enough - likely silence/speech, not DTMF

    return DTMF_TABLE.get((best_low, best_high))


def decode_wav_file(path: str) -> str:
    """
    Slide a window over the whole WAV file block-by-block and build
    the sequence of DTMF digits detected, collapsing repeated
    detections of the same held tone into a single digit.
    """
    with wave.open(path, "rb") as wf:
        sample_rate = wf.getframerate()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)
        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float64)

    digits = []
    last_digit = None

    for start in range(0, len(audio) - BLOCK_SIZE, BLOCK_SIZE):
        block = audio[start:start + BLOCK_SIZE]
        digit = detect_dtmf_in_block(block, sample_rate)

        if digit is not None and digit != last_digit:
            digits.append(digit)
        last_digit = digit

    return "".join(digits)


def main():
    if len(sys.argv) < 2:
        print("Usage: python dtmf_decoder.py <wav_file>")
        sys.exit(1)

    path = sys.argv[1]
    result = decode_wav_file(path)
    print(f"\nDetected DTMF sequence: {result if result else '(none found)'}\n")


if __name__ == "__main__":
    main()