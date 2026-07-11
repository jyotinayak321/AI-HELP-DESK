"""
Direct test: feed real greeting.wav audio straight into StreamingEndpointDetector,
using process_frame() (the actual method used in production), not just
speech_probability() directly.
"""

from pydub import AudioSegment
import numpy as np
from voice.vad import StreamingEndpointDetector

audio = AudioSegment.from_wav('voice/static_prompts/greeting.wav')
audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
samples = np.array(audio.get_array_of_samples(), dtype=np.int16)
samples_float = samples.astype(np.float32) / 32768.0

detector = StreamingEndpointDetector(
    silence_duration_ms=300,
    speech_threshold=0.5,
    min_speech_ms=250,
)
detector.reset()

FRAME_SIZE = 512
num_frames = len(samples_float) // FRAME_SIZE

print(f"Total frames: {num_frames}")

speech_started_at = None
end_of_speech_at = None

for i in range(num_frames):
    frame = samples_float[i * FRAME_SIZE : (i + 1) * FRAME_SIZE]
    result = detector.process_frame(frame)

    if detector._has_spoken and speech_started_at is None:
        speech_started_at = i
        print(f"  >>> speech_started at frame {i}")

    if result == "end_of_speech":
        end_of_speech_at = i
        print(f"  >>> end_of_speech at frame {i}")
        break  # first utterance ke baad stop

print(f"\nSpeech started at frame: {speech_started_at}")
print(f"End of speech at frame: {end_of_speech_at}")