"""
voice/stt.py — Speech-to-Text Engine (Phase 2)
=================================================
Wraps the faster-whisper library for local, GPU-accelerated,
multilingual speech recognition.

Requirements Covered:
  R-30: Voice capture of service number (transcription layer)
  R-34: Speech-to-text complaint intake
  R-35: English, Hindi, and Hinglish support

Design Decisions:
  - Uses CTranslate2-optimised Whisper (faster-whisper) for 4x speed gain
    over vanilla Whisper with half the VRAM usage.
  - Model is loaded ONCE at import time and reused across all requests
    (singleton pattern matching existing embedder.py / classifier.py).
  - Accepts raw bytes so the caller (router) handles file I/O.
  - Returns structured TranscriptionResult with confidence scoring for
    downstream validation and logging.
"""

import os
import io
import time
import logging
import tempfile
import numpy as np
import collections
import wave
import struct
import torch
from dataclasses import dataclass, field
from typing import Optional, List

logger = logging.getLogger("voice.stt")



@dataclass
class TranscriptionSegment:
    """A single segment returned by Whisper."""
    text: str
    start: float
    end: float
    avg_logprob: float
    no_speech_prob: float


@dataclass
class TranscriptionResult:
    """Full transcription output with metadata for logging (Phase 10)."""
    text: str
    language: str
    language_probability: float
    segments: List[TranscriptionSegment] = field(default_factory=list)
    confidence: float = 0.0          # Derived average confidence
    duration_seconds: float = 0.0    # Audio duration
    processing_time_ms: float = 0.0  # STT inference wall-clock time
    is_silent: bool = False          # True if no speech detected


class SpeechToTextEngine:
    """
    Singleton-style STT engine backed by faster-whisper.

    Loads the model from a local directory (air-gapped) on first
    instantiation.  All subsequent calls reuse the same model object.

    The model directory should contain the CTranslate2-converted
    Whisper weights.  Use `ct2-whisper-converter` to produce them
    from a standard Whisper checkpoint:

        ct2-whisper-converter --model medium --output_dir ./local_models/whisper-medium-ct2
    """

    _instance: Optional["SpeechToTextEngine"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, model_size: str = "medium", device: str = "auto",
                 compute_type: str = "float16"):
        if hasattr(self, "_initialised"):
            return
        self._initialised = True

        # Resolve model path relative to this file
        # backend/voice/stt.py → backend/local_models/whisper-medium-ct2
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.model_dir = os.path.normpath(
            os.path.join(current_dir, "..", "local_models", f"whisper-{model_size}-ct2")
        )

        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None

        logger.info(
            "STT engine configured: model_dir=%s  device=%s  compute_type=%s",
            self.model_dir, self.device, self.compute_type,
        )

    # ------------------------------------------------------------------
    # Lazy model loading — defers GPU memory allocation until first use
    # ------------------------------------------------------------------
    def _ensure_model(self):
        """Load the model on first transcription request (lazy loading)."""
        if self._model is not None:
            return

        try:
            from faster_whisper import WhisperModel

            if os.path.isdir(self.model_dir):
                logger.info("Loading faster-whisper model from local dir: %s", self.model_dir)
                self._model = WhisperModel(
                    self.model_dir,
                    device=self.device,
                    compute_type=self.compute_type,
                    local_files_only=True,
                )
            else:
                # Fallback: use model size string (will look in HF cache or download)
                logger.warning(
                    "Local model dir not found (%s). Falling back to model_size='%s'. "
                    "This will FAIL on air-gapped machines without cached models.",
                    self.model_dir, self.model_size,
                )
                self._model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                )

            logger.info("STT model loaded successfully.")

        except ImportError:
            logger.error(
                "faster-whisper is not installed. "
                "Install with: pip install faster-whisper"
            )
            raise
        except Exception as exc:
            logger.error("Failed to load STT model: %s", exc, exc_info=True)
            raise RuntimeError(f"STT model loading failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def transcribe(
        self,
        audio_bytes: bytes,
        language: Optional[str] = None,
        *,
        beam_size: int = 5,
        vad_filter: bool = True,
        word_timestamps: bool = False,
    ) -> TranscriptionResult:
        """
        Transcribe an audio buffer (WAV/PCM bytes) to text.

        Parameters
        ----------
        audio_bytes : bytes
            Raw audio file content (WAV, WebM, or any ffmpeg-supported format).
        language : str, optional
            ISO-639-1 code ("en", "hi").  None = auto-detect.
        beam_size : int
            Beam search width.  Higher = more accurate but slower.
        vad_filter : bool
            Enable Silero VAD to skip silent chunks — reduces hallucination.
        word_timestamps : bool
            Whether to compute per-word timestamps (slower).

        Returns
        -------
        TranscriptionResult
            Structured output including text, language, confidence, and timing.
        """
        self._ensure_model()

        # Write bytes to a temp file because faster-whisper expects a path
        # or numpy array.  Using tempfile avoids holding large buffers.
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".wav", delete=False, dir=tempfile.gettempdir()
            ) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            t0 = time.perf_counter()

            segments_gen, info = self._model.transcribe(
                tmp_path,
                language=language,
                beam_size=beam_size,
                vad_filter=vad_filter,
                word_timestamps=word_timestamps,
            )

            # Materialise the generator to collect all segments
            segments: List[TranscriptionSegment] = []
            full_text_parts: List[str] = []

            for seg in segments_gen:
                segments.append(TranscriptionSegment(
                    text=seg.text.strip(),
                    start=seg.start,
                    end=seg.end,
                    avg_logprob=seg.avg_logprob,
                    no_speech_prob=seg.no_speech_prob,
                ))
                full_text_parts.append(seg.text.strip())

            elapsed_ms = (time.perf_counter() - t0) * 1000
            full_text = " ".join(full_text_parts).strip()

            # Derive aggregate confidence from average log-probabilities
            if segments:
                avg_logprob = sum(s.avg_logprob for s in segments) / len(segments)
                # Convert log-prob to a 0-1 confidence (rough heuristic)
                confidence = min(1.0, max(0.0, 1.0 + avg_logprob))
                avg_no_speech = sum(s.no_speech_prob for s in segments) / len(segments)
            else:
                confidence = 0.0
                avg_no_speech = 1.0

            is_silent = (not full_text) or (avg_no_speech > 0.8)

            result = TranscriptionResult(
                text=full_text,
                language=info.language,
                language_probability=info.language_probability,
                segments=segments,
                confidence=round(confidence, 4),
                duration_seconds=round(info.duration, 2),
                processing_time_ms=round(elapsed_ms, 1),
                is_silent=is_silent,
            )

            logger.info(
                "STT result: lang=%s  conf=%.2f  silent=%s  time=%.0fms  text='%s'",
                result.language, result.confidence, result.is_silent,
                result.processing_time_ms, result.text[:80],
            )
            return result

        finally:
            # Clean up temp file
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def is_loaded(self) -> bool:
        """Check whether the model has been loaded into GPU memory."""
        return self._model is not None


def float32_to_wav_bytes(samples: np.ndarray, sample_rate: int = 16000) -> bytes:
    """Convert float32 samples (-1.0 to 1.0) to 16-bit PCM WAV bytes."""
    # Scale to 16-bit int range (-32768 to 32767)
    int_samples = np.clip(samples, -1.0, 1.0) * 32767.0
    int_samples = int_samples.astype(np.int16)
    
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(int_samples.tobytes())
    return buf.getvalue()


class SileroVADDetector:
    """Stateful voice activity detector using Silero VAD PyTorch JIT model."""

    def __init__(self, model_path: Optional[str] = None, threshold: float = 0.5,
                 sampling_rate: int = 16000, silence_timeout_ms: int = 800):
        if model_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            model_path = os.path.normpath(
                os.path.join(current_dir, "..", "local_models", "silero_vad.jit")
            )
            
        logger.info("Loading Silero VAD from: %s", model_path)
        self.model = torch.jit.load(model_path, map_location="cpu")
        self.model.eval()
        
        self.threshold = threshold
        self.sampling_rate = sampling_rate
        self.silence_timeout_samples = int(sampling_rate * silence_timeout_ms / 1000)
        
        # State variables
        self.triggered = False
        self.temp_end = 0
        self.current_sample = 0
        self.speech_buffer = []
        self.pre_roll = collections.deque(maxlen=10)  # 10 chunks of 512 samples = ~320ms pre-roll
        
        self.reset()
        
    def reset(self):
        """Reset internal detector state."""
        self.model.reset_states()
        self.triggered = False
        self.temp_end = 0
        self.current_sample = 0
        self.speech_buffer = []
        self.pre_roll.clear()
        
    def process_chunk(self, chunk: np.ndarray) -> dict:
        """
        Process a chunk of 16kHz audio samples.
        
        Parameters
        ----------
        chunk : np.ndarray
            1D float32 array of shape (512,).
            
        Returns
        -------
        dict
            Contains:
            - "status": "speech_started", "speech_ended", or "none"
            - "audio": numpy array of float32 samples (only when status is "speech_ended")
        """
        if chunk.ndim != 1 or len(chunk) != 512:
            # We buffer chunks in routers to ensure we always pass exactly 512 samples.
            raise ValueError(f"Silero VAD expects a 512-sample chunk, got {len(chunk)}")
            
        x = torch.from_numpy(chunk).unsqueeze(0)  # shape: (1, 512)
        window_size_samples = len(chunk)
        self.current_sample += window_size_samples
        
        with torch.no_grad():
            speech_prob = self.model(x, self.sampling_rate).item()
            
        status = "none"
        
        if speech_prob >= self.threshold:
            if self.temp_end:
                self.temp_end = 0
            if not self.triggered:
                self.triggered = True
                status = "speech_started"
                
        elif speech_prob < (self.threshold - 0.15):
            if self.triggered:
                if not self.temp_end:
                    self.temp_end = self.current_sample
                if self.current_sample - self.temp_end >= self.silence_timeout_samples:
                    self.triggered = False
                    self.temp_end = 0
                    status = "speech_ended"
                    
        # Buffering logic
        if not self.triggered:
            self.pre_roll.append(chunk)
        else:
            if status == "speech_started":
                # Speech just started - copy all pre-roll samples to speech buffer
                self.speech_buffer.extend(list(self.pre_roll))
                self.pre_roll.clear()
            self.speech_buffer.append(chunk)
            
        if status == "speech_ended":
            full_audio = np.concatenate(self.speech_buffer, axis=0) if self.speech_buffer else np.array([], dtype=np.float32)
            self.speech_buffer = []
            return {"status": "speech_ended", "audio": full_audio}
        elif status == "speech_started":
            return {"status": "speech_started", "audio": None}
            
        return {"status": "none", "audio": None}

