import numpy as np
from voice.vad import StreamingEndpointDetector

detector = StreamingEndpointDetector()
detector.reset()

# Dummy test: random noise frames (silence jaisa, chhoti amplitude)
silence_frame = (np.random.randn(512) * 0.001).astype(np.float32)

# Dummy "speech-like" frame (bada amplitude, real speech nahi hai,
# bas pipeline test karne ke liye)
speech_frame = (np.random.randn(512) * 0.3).astype(np.float32)

print("Testing silence frames...")
for i in range(5):
    prob = detector.vad.speech_probability(silence_frame)
    print(f"  frame {i}: speech_prob={prob:.4f}")

print("\nPipeline se koi crash nahi aaya — VAD model load aur run ho raha hai ✅")

print("\nTesting louder/speech-like frames...")
detector.reset()
for i in range(10):
    prob = detector.vad.speech_probability(speech_frame)
    print(f"  frame {i}: speech_prob={prob:.4f}")