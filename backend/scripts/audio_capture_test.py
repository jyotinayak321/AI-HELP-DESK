"""
Phase 3 - Audio Capture Test Script (R-40)
-------------------------------------------
Purpose : Test analog audio capture from a sound card input (3.5mm jack)
          BEFORE wiring it into the full VAD/STT pipeline.
          R-40 explicitly says this must be "isolated and tested on its own".

Usage:
    python audio_capture_test.py --list
    python audio_capture_test.py --device 4 --duration 10 --out call_test.wav
"""

import argparse
import sys
import wave
import numpy as np
import sounddevice as sd


SAMPLE_RATE = 16000   # 16kHz - matches faster-whisper's expected input
CHANNELS = 1          # Mono - telephony audio is mono anyway
DTYPE = "int16"       # 16-bit PCM - standard for speech processing


def list_devices():
    """Print all available audio input/output devices with their index."""
    print("\n=== Available Audio Devices ===\n")
    devices = sd.query_devices()
    for idx, dev in enumerate(devices):
        io_type = []
        if dev["max_input_channels"] > 0:
            io_type.append("INPUT")
        if dev["max_output_channels"] > 0:
            io_type.append("OUTPUT")
        print(f"[{idx}] {dev['name']}  "
              f"(in_ch={dev['max_input_channels']}, "
              f"out_ch={dev['max_output_channels']}, "
              f"default_sr={dev['default_samplerate']:.0f}) "
              f"-> {'/'.join(io_type)}")
    print("\nTip: 3.5mm jack / line-in se connected device ka naam usually "
          "'Line In', 'Microphone', ya sound card ka naam hoga.\n")


def record_audio(device_index: int, duration: float, output_path: str):
    """Record audio from the given device for `duration` seconds and save as WAV."""
    print(f"\nRecording {duration}s from device [{device_index}] "
          f"at {SAMPLE_RATE} Hz mono...")
    print("Speak / play the test call audio now.\n")

    try:
        recording = sd.rec(
            int(duration * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            device=device_index,
        )
        sd.wait()  # block until recording is finished
    except Exception as e:
        print(f"[ERROR] Recording failed: {e}")
        print("Common causes: wrong device index, device busy in another app, "
              "or device does not support 16kHz mono input.")
        sys.exit(1)

    save_wav(recording, output_path)
    print(f"Saved recording to: {output_path}")

    # Sanity check - agar sara audio silence hai to warn karo
    max_amplitude = int(np.max(np.abs(recording)))
    if max_amplitude < 100:
        print(f"[WARNING] Recorded audio is almost silent (max amplitude = "
              f"{max_amplitude}). Check cable connection / input volume level.")


def save_wav(recording: np.ndarray, path: str):
    """Save a numpy int16 array as a valid WAV file."""
    with wave.open(path, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # int16 = 2 bytes per sample
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(recording.tobytes())


def main():
    parser = argparse.ArgumentParser(description="Phase 3 audio capture test (R-40)")
    parser.add_argument("--list", action="store_true", help="List all audio devices")
    parser.add_argument("--device", type=int, help="Device index to record from")
    parser.add_argument("--duration", type=float, default=5.0, help="Recording duration in seconds")
    parser.add_argument("--out", type=str, default="test_capture.wav", help="Output WAV file path")
    args = parser.parse_args()

    if args.list or args.device is None:
        list_devices()
        if args.device is None:
            print("Ab --device <index> pass karke recording test karo.")
            return

    record_audio(args.device, args.duration, args.out)


if __name__ == "__main__":
    main()