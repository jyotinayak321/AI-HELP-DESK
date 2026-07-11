import asyncio
import json
import numpy as np
import sounddevice as sd
import websockets

WS_URL = "ws://192.168.1.34:8000/api/voice/ws/vad-stream"
SAMPLE_RATE = 16000
CHUNK_SAMPLES = 1600


async def listen_for_events(ws):
    try:
        async for message in ws:
            data = json.loads(message)
            print("  EVENT:", data)
            if data.get("event") == "end_of_speech":
                print("Detected end of speech! Stopping.")
                break
    except Exception as exc:
        print("  LISTENER ERROR:", repr(exc))


async def main():
    print("Connecting...")
    async with websockets.connect(WS_URL) as ws:
        listener_task = asyncio.create_task(listen_for_events(ws))

        print("Speak now, recording for 6 seconds")

        loop = asyncio.get_event_loop()

        def audio_callback(indata, frames, time_info, status):
            if status:
                print("  mic status:", status)
            pcm16 = (indata[:, 0] * 32767).astype(np.int16)
            amplitude = np.abs(pcm16).max()
            print("  mic chunk max_amplitude:", amplitude)
            asyncio.run_coroutine_threadsafe(ws.send(pcm16.tobytes()), loop)

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            blocksize=CHUNK_SAMPLES,
            callback=audio_callback,
        ):
            await asyncio.sleep(6)

        listener_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())