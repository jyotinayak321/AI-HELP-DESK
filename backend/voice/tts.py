"""
voice/tts.py — Text-to-Speech Engine (Phase 2)
=================================================
Provides local, GPU-accelerated speech synthesis for dynamic
confirmations (service number read-back, ticket number, etc.).

Requirements Covered:
  R-31: Read-back confirmation (TTS generation)
  R-37: Local GPU-backed TTS for dynamic confirmations
  R-38: Reliable ticket-number read-back

Design Decisions:
  - Primary engine: Piper TTS (ONNX-based, sub-100ms latency).
  - Fallback engine: Windows SAPI5 via pyttsx3 (zero dependencies,
    guaranteed to work on any Windows machine).
  - Generates 16-bit PCM WAV at 22050 Hz — universally playable.
  - Text normalisation layer converts ticket numbers and service
    numbers into phonetically spellable sequences before synthesis.
"""

import os
import io
import time
import wave
import struct
import logging
import tempfile
from config import settings
from typing import Optional

logger = logging.getLogger("voice.tts")


class TextToSpeechEngine:
    """
    Hybrid TTS engine.

    Tries Piper first (fast, natural, GPU-accelerated).
    Falls back to Windows SAPI5 via pyttsx3 if Piper is unavailable.
    """

    _instance: Optional["TextToSpeechEngine"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialised"):
            return
        self._initialised = True

        self._piper_voice = None
        self._pyttsx_engine = None
        self._backend = None  # "piper" | "sapi5" | None

        # Piper model paths (relative to backend/local_models/)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self._piper_models_dir = os.path.normpath(
            os.path.join(current_dir, "..", "local_models", "piper")
        )

        self._try_init_piper()
        if self._backend is None:
            self._try_init_sapi5()

        if self._backend is None:
            logger.warning(
                "No TTS backend available. TTS calls will return empty audio. "
                "Install piper-tts or pyttsx3 to enable speech synthesis."
            )

    # ------------------------------------------------------------------
    # Backend initialisation
    # ------------------------------------------------------------------
    def _try_init_piper(self):
        """Attempt to load Piper TTS from local ONNX model files."""
        try:
            from piper import PiperVoice  # type: ignore

            # Look for an English model first, then Hindi
            for voice_name in ["en_US-lessac-medium", "en_US-amy-medium", "hi_IN-swara-medium"]:
                onnx_path = os.path.join(self._piper_models_dir, f"{voice_name}.onnx")
                json_path = os.path.join(self._piper_models_dir, f"{voice_name}.onnx.json")
                if os.path.isfile(onnx_path) and os.path.isfile(json_path):
                    self._piper_voice = PiperVoice.load(onnx_path, config_path=json_path)
                    self._backend = "piper"
                    logger.info("TTS backend: Piper (%s)", voice_name)
                    return

            logger.info("No Piper voice models found in %s", self._piper_models_dir)

        except ImportError:
            logger.info("piper-tts not installed; skipping Piper backend.")
        except Exception as exc:
            logger.warning("Piper init failed: %s", exc)

    def _try_init_sapi5(self):
        """Attempt to initialise Windows SAPI5 via pyttsx3."""
        try:
            import pyttsx3  # type: ignore

            engine = pyttsx3.init("sapi5")
            # Configure voice properties
            engine.setProperty("rate", 150)   # Words per minute
            engine.setProperty("volume", 1.0)
            self._pyttsx_engine = engine
            self._backend = "sapi5"
            logger.info("TTS backend: Windows SAPI5 (pyttsx3)")

        except ImportError:
            logger.info("pyttsx3 not installed; skipping SAPI5 backend.")
        except Exception as exc:
            logger.warning("SAPI5 init failed: %s", exc)

    # ------------------------------------------------------------------
    # Text normalisation for reliable read-back
    # ------------------------------------------------------------------
    @staticmethod
    def normalise_for_speech(text: str) -> str:
        """
        Convert structured identifiers into speakable text.

        Examples:
            "TIC-202606-0001" → "T I C, 2 0 2 6 0 6, 0 0 0 1"
            "2893456P"        → "2 8 9 3 4 5 6 P"
            "SVC-12345"       → "S V C, 1 2 3 4 5"
        """
        result_parts = []
        # Split on dashes first
        chunks = text.split("-")
        for chunk in chunks:
            # Spell out each character with spaces
            spelled = " ".join(ch for ch in chunk)
            result_parts.append(spelled)

        return ", ".join(result_parts)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def synthesise(self, text: str, *, normalise: bool = False) -> bytes:
        """
        Convert text to speech, returning WAV bytes.

        Parameters
        ----------
        text : str
            The text to speak.
        normalise : bool
            If True, apply phonetic normalisation (for ticket/service numbers).

        Returns
        -------
        bytes
            PCM WAV audio data, or empty bytes if no backend is available.
        """
        if not text or not text.strip():
            return b""

        if normalise:
            text = self.normalise_for_speech(text)

        t0 = time.perf_counter()

        if self._backend == "piper":
            audio_bytes = self._synthesise_piper(text)
        elif self._backend == "sapi5":
            audio_bytes = self._synthesise_sapi5(text)
        else:
            logger.warning("No TTS backend — returning empty audio.")
            return b""

        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.info(
            "TTS synthesis: backend=%s  time=%.0fms  text='%s'  bytes=%d",
            self._backend, elapsed_ms, text[:60], len(audio_bytes),
        )
        return audio_bytes

    def _synthesise_piper(self, text: str) -> bytes:
        """Generate WAV audio via Piper TTS."""
        try:
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wav_file:
                self._piper_voice.synthesize(text, wav_file)
            return buf.getvalue()
        except Exception as exc:
            logger.error("Piper synthesis failed: %s", exc, exc_info=True)
            # Try SAPI5 fallback
            if self._pyttsx_engine is None:
                self._try_init_sapi5()
            if self._pyttsx_engine is not None:
                return self._synthesise_sapi5(text)
            return b""

    def _synthesise_sapi5(self, text: str) -> bytes:
        """Generate WAV audio via Windows SAPI5 (pyttsx3)."""
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".wav", delete=False, dir=tempfile.gettempdir()
            ) as tmp:
                tmp_path = tmp.name

            self._pyttsx_engine.save_to_file(text, tmp_path)
            self._pyttsx_engine.runAndWait()

            with open(tmp_path, "rb") as f:
                return f.read()

        except Exception as exc:
            logger.error("SAPI5 synthesis failed: %s", exc, exc_info=True)
            return b""
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    @property
    def backend_name(self) -> Optional[str]:
        """Return the active TTS backend name."""
        return self._backend

    def is_available(self) -> bool:
        """Check if any TTS backend is ready."""
        return self._backend is not None
