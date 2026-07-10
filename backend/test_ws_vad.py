"""
test_ws_vad.py — Standalone test for the /api/voice/ws/vad-stream endpoint.

Simulates a client sending raw PCM audio chunks:
  1. Sends ~1 second of "silence" (near-zero amplitude)
  2. Sends ~1 second of "loud" chunks (fake speech-like signal)
  3. Sends ~2 seconds of silence again
  4. Should receive "speech_started" after step 2, then
     "end_of_speech" after ~1.2s of silence in step 3.

Run this while `uvicorn main:app --reload --port 8000` is running
in another terminal.
"""

import asyncio
import json
import numpy as np
import websockets

WS_URL = "ws://192.168.1.34:8000/api/voice/ws/vad-stream"
SAMPLE_RATE = 16000
CHUNK_SAMPLES = 1600  # 100ms chunks


def make_pcm_chunk(amplitude: float) -> bytes:
    """Generate a fake 16-bit PCM chunk at given amplitude (0.0 - 1.0)."""
    samples = (np.random.randn(CHUNK_SAMPLES) * amplitude * 32767).astype(np.int16)
    return samples.tobytes()


async def listen_for_events(ws, stop_event: asyncio.Event):
    """Background task: print every JSON event the server sends."""
    try:
        async for message in ws:
            data = json.loads(message)
            print(f"  <<< SERVER EVENT: {data}")
            if data.get("event") == "end_of_speech":
                stop_event.set()
    except websockets.exceptions.ConnectionClosed:
        print("  (connection closed)")


async def main():
    print(f"Connecting to {WS_URL} ...")
    async with websockets.connect(WS_URL) as ws:
        stop_event = asyncio.Event()
        listener_task = asyncio.create_task(listen_for_events(ws, stop_event))

        # Wait for initial "listening" event
        await asyncio.sleep(0.3)

        print("\n--- Sending 1s of silence ---")
        for _ in range(10):  # 10 x 100ms = 1s
            await ws.send(make_pcm_chunk(amplitude=0.001))
            await asyncio.sleep(0.1)

        print("\n--- Sending 1s of loud/speech-like audio ---")
        for _ in range(10):
            await ws.send(make_pcm_chunk(amplitude=0.3))
            await asyncio.sleep(0.1)

        print("\n--- Sending silence again (waiting for end_of_speech) ---")
        for _ in range(20):  # up to 2s
            await ws.send(make_pcm_chunk(amplitude=0.001))
            await asyncio.sleep(0.1)
            if stop_event.is_set():
                break

        if stop_event.is_set():
            print("\n✅ SUCCESS: 'end_of_speech' event received as expected!")
        else:
            print("\n⚠️  'end_of_speech' not received within timeout — check server logs.")

        listener_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())