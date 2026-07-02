"""
Compare our manual ONNX wrapper against the OFFICIAL silero-vad package,
using the same greeting.wav — isolates whether our wrapper has a bug.
"""

from pydub import AudioSegment
import numpy as np
import torch
from silero_vad import load_silero_vad, get_speech_timestamps

audio = AudioSegment.from_wav('voice/static_prompts/greeting.wav')
audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
samples = np.array(audio.get_array_of_samples(), dtype=np.int16)
samples_float = samples.astype(np.float32) / 32768.0

wav_tensor = torch.from_numpy(samples_float)

model = load_silero_vad()

speech_timestamps = get_speech_timestamps(wav_tensor, model, sampling_rate=16000, return_seconds=True)

print("Speech segments detected by OFFICIAL silero-vad package:")
print(speech_timestamps)