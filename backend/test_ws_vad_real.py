"""
test_ws_vad_real.py — Test /api/voice/ws/vad-stream using REAL recorded speech.

Reads voice/static_prompts/greeting.wav, converts it to 16kHz mono PCM,
and streams it in small chunks to the VAD WebSocket — followed by
silence — to properly verify speech_started + end_of_speech detection.
"""

import asyncio
import json
import io
import numpy as np
import websockets

WS_URL = "ws://192.168.1.34:8000/api/voice/ws/vad-stream"
WAV_PATH = "voice/static_prompts/greeting.wav"
SAMPLE_RATE = 16000
CHUNK_SAMPLES = 1600  # 100ms chunks


def load_wav_as_pcm16(path: str) -> np.ndarray:
    """Load a WAV file and return 16kHz mono int16 samples using pydub."""
    from pydub import AudioSegment

    audio = AudioSegment.from_wav(path)
    audio = audio.set_frame_rate(SAMPLE_RATE).set_channels(1).set_sample_width(2)
    samples = np.array(audio.get_array_of_samples(), dtype=np.int16)
    return samples


def silence_chunk() -> bytes:
    samples = np.zeros(CHUNK_SAMPLES, dtype=np.int16)
    return samples.tobytes()


async def listen_for_events(ws, stop_event: asyncio.Event):
    try:
        async for message in ws:
            data = json.loads(message)
            print(f"  <<< SERVER EVENT: {data}")
            if data.get("event") == "end_of_speech":
                stop_event.set()
    except websockets.exceptions.ConnectionClosed:
        print("  (connection closed)")


async def main():
    print(f"Loading {WAV_PATH} ...")
    samples = load_wav_as_pcm16(WAV_PATH)
    duration_s = len(samples) / SAMPLE_RATE
    print(f"Loaded {len(samples)} samples (~{duration_s:.1f}s of audio)")

    print(f"\nConnecting to {WS_URL} ...")
    async with websockets.connect(WS_URL) as ws:
        stop_event = asyncio.Event()
        listener_task = asyncio.create_task(listen_for_events(ws, stop_event))

        await asyncio.sleep(0.3)

        print("\n--- Streaming REAL speech (greeting.wav) ---")
        for i in range(0, len(samples), CHUNK_SAMPLES):
            chunk = samples[i : i + CHUNK_SAMPLES]
            if len(chunk) < CHUNK_SAMPLES:
                # Pad the last chunk with zeros so it's a valid size
                chunk = np.pad(chunk, (0, CHUNK_SAMPLES - len(chunk)))
            await ws.send(chunk.astype(np.int16).tobytes())
            await asyncio.sleep(0.1)  # simulate real-time pacing

        print("\n--- Now sending silence (waiting for end_of_speech) ---")
        for _ in range(20):  # up to 2s
            await ws.send(silence_chunk())
            await asyncio.sleep(0.1)
            if stop_event.is_set():
                break

        if stop_event.is_set():
            print("\n✅ SUCCESS: 'end_of_speech' received after real speech!")
        else:
            print("\n⚠️  'end_of_speech' not received — check server logs.")

        listener_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())