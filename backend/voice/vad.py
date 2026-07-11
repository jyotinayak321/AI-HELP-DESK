"""
voice/vad.py — Real-Time Voice Activity Detection (Phase 2)
=================================================
Ab OFFICIAL silero-vad Python package use karta hai (torch-based),
manual ONNX wrapper ki jagah — jisme wiring bug tha (probabilities
kabhi threshold cross nahi karti thi, verified via test_official_silero.py
vs test_vad_direct.py comparison).

Design Decisions:
  - silero-vad package apna VADIterator deta hai jo exactly streaming
    ke liye bana hai — 512-sample chunks, internal state management,
    "speech_start"/"speech_end" events khud handle karta hai.
  - Class-level singleton model (RAM me sirf ek baar load ho).
"""

import numpy as np
from typing import Optional


class SileroVAD:
    """Official silero-vad model ka thin wrapper."""

    _model = None  # class-level singleton

    SAMPLE_RATE = 16000
    FRAME_SAMPLES = 512

    def __init__(self):
        pass  # model lazy-load hota hai self.model property se

    @property
    def model(self):
        if SileroVAD._model is None:
            print("[vad] Loading official silero-vad model (first use)...")
            from silero_vad import load_silero_vad
            SileroVAD._model = load_silero_vad()
        return SileroVAD._model

    def reset_state(self):
        self.model.reset_states()

    def speech_probability(self, frame: np.ndarray) -> float:
        """
        Ek FRAME_SAMPLES-length audio frame do (float32, -1 se 1 tak),
        wapas milega 0.0-1.0 ke beech probability ki isme speech hai.
        """
        import torch

        if len(frame) != self.FRAME_SAMPLES:
            raise ValueError(f"Frame {self.FRAME_SAMPLES} samples ka hona chahiye, mila {len(frame)}")

        tensor = torch.from_numpy(frame)
        prob = self.model(tensor, self.SAMPLE_RATE).item()
        return prob


class StreamingEndpointDetector:
    """
    High-level wrapper: "user chup ho gaya kya, recording stop karu?"
    ka jawab deta hai. Same public API as before — routers/voice.py
    me kuch change karne ki zaroorat nahi.
    """

    def __init__(
        self,
        silence_duration_ms: int = 800,
        speech_threshold: float = 0.5,
        min_speech_ms: int = 250,
        max_wait_ms: int = 8000,
    ):
        self.vad = SileroVAD()
        self.silence_duration_ms = silence_duration_ms
        self.speech_threshold = speech_threshold
        self.min_speech_ms = min_speech_ms
        self.max_wait_ms = max_wait_ms

        self.frame_ms = (SileroVAD.FRAME_SAMPLES / SileroVAD.SAMPLE_RATE) * 1000
        self._silence_frames = 0
        self._speech_frames = 0
        self._has_spoken = False
        self._total_frames_processed = 0

    def reset(self):
        self.vad.reset_state()
        self._silence_frames = 0
        self._speech_frames = 0
        self._has_spoken = False
        self._total_frames_processed = 0

    def process_frame(self, frame: np.ndarray) -> str:
        """
        Returns: "continue" | "end_of_speech" | "timeout"
        """
        self._total_frames_processed += 1
        prob = self.vad.speech_probability(frame)

        if prob >= self.speech_threshold:
            self._speech_frames += 1
            self._silence_frames = 0
            if (self._speech_frames * self.frame_ms) >= self.min_speech_ms:
                self._has_spoken = True
        else:
            self._silence_frames += 1
            self._speech_frames = 0

        if self._has_spoken:
            silence_elapsed_ms = self._silence_frames * self.frame_ms
            if silence_elapsed_ms >= self.silence_duration_ms:
                return "end_of_speech"
        else:
            elapsed_ms = self._total_frames_processed * self.frame_ms
            if elapsed_ms >= self.max_wait_ms:
                return "timeout"

        return "continue"
