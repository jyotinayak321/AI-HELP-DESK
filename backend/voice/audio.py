"""
voice/audio.py — Audio Preprocessing (Phase 2)
=================================================
Handles audio format conversion, resampling, silence detection,
and basic noise reduction to prepare browser-captured audio for
the STT engine.

Design Decisions:
  - Browser MediaRecorder typically produces WebM/Opus.  Faster-whisper
    can handle most formats via ffmpeg, but we normalise to 16-bit
    PCM WAV at 16 kHz for maximum compatibility and predictability.
  - Uses pydub (with ffmpeg backend) for format conversion.
  - Falls back to raw passthrough if pydub/ffmpeg is unavailable
    (faster-whisper can still attempt decoding via its own ffmpeg).
  - Silence detection returns True if the audio is below a dBFS
    threshold — useful for skipping STT on empty recordings.
"""

import io
import os
import logging
import tempfile
from typing import Optional, Tuple

logger = logging.getLogger("voice.audio")

# Target format for STT engine
TARGET_SAMPLE_RATE = 16000
TARGET_CHANNELS = 1
TARGET_SAMPLE_WIDTH = 2  # 16-bit


def convert_to_wav(
    audio_bytes: bytes,
    source_format: str = "webm",
) -> bytes:
    """
    Convert audio bytes from any format to 16 kHz mono WAV.

    Parameters
    ----------
    audio_bytes : bytes
        Raw audio data (WebM, Opus, MP3, OGG, etc.).
    source_format : str
        Hint for the source format ("webm", "ogg", "mp3", "wav").

    Returns
    -------
    bytes
        16 kHz mono PCM WAV data.
    """
    try:
        from pydub import AudioSegment  # type: ignore

        audio = AudioSegment.from_file(
            io.BytesIO(audio_bytes),
            format=source_format,
        )

        # Normalise to target spec
        audio = audio.set_frame_rate(TARGET_SAMPLE_RATE)
        audio = audio.set_channels(TARGET_CHANNELS)
        audio = audio.set_sample_width(TARGET_SAMPLE_WIDTH)

        buf = io.BytesIO()
        audio.export(buf, format="wav")
        wav_bytes = buf.getvalue()

        logger.debug(
            "Audio converted: %s → WAV  (%d → %d bytes, %.1fs)",
            source_format, len(audio_bytes), len(wav_bytes),
            len(audio) / 1000,
        )
        return wav_bytes

    except ImportError:
        logger.warning(
            "pydub not installed — passing raw audio to STT engine. "
            "Install pydub and ffmpeg for reliable format conversion."
        )
        return audio_bytes

    except Exception as exc:
        logger.warning(
            "Audio conversion failed (%s) — passing raw bytes. Error: %s",
            source_format, exc,
        )
        return audio_bytes


def detect_silence(
    audio_bytes: bytes,
    source_format: str = "wav",
    silence_threshold_dbfs: float = -40.0,
) -> bool:
    """
    Check if an audio buffer is effectively silent.

    Parameters
    ----------
    audio_bytes : bytes
        Audio data.
    source_format : str
        Format of the audio data.
    silence_threshold_dbfs : float
        dBFS threshold below which audio is considered silent.

    Returns
    -------
    bool
        True if the audio is below the silence threshold.
    """
    try:
        from pydub import AudioSegment  # type: ignore

        audio = AudioSegment.from_file(
            io.BytesIO(audio_bytes),
            format=source_format,
        )

        # Use max_dBFS (peak volume) instead of average dBFS, because trailing 
        # silence from the VAD can artificially lower the average dBFS of the file.
        if audio.max_dBFS < silence_threshold_dbfs:
            logger.info(
                "Silence detected: max_dBFS=%.1f (threshold=%.1f)",
                audio.max_dBFS, silence_threshold_dbfs,
            )
            return True
        return False

    except ImportError:
        logger.debug("pydub not available — skipping silence detection.")
        return False
    except Exception as exc:
        logger.debug("Silence detection failed: %s", exc)
        return False


def get_audio_duration(audio_bytes: bytes, source_format: str = "wav") -> float:
    """
    Get the duration of an audio buffer in seconds.

    Returns 0.0 if duration cannot be determined.
    """
    try:
        from pydub import AudioSegment  # type: ignore

        audio = AudioSegment.from_file(
            io.BytesIO(audio_bytes),
            format=source_format,
        )
        return len(audio) / 1000.0

    except Exception:
        return 0.0


def detect_format_from_content_type(content_type: str) -> str:
    """
    Map an HTTP Content-Type header to a pydub-compatible format string.

    Parameters
    ----------
    content_type : str
        e.g. "audio/webm", "audio/wav", "audio/ogg; codecs=opus"

    Returns
    -------
    str
        Format string for pydub/ffmpeg.
    """
    ct = content_type.lower().split(";")[0].strip()
    mapping = {
        "audio/webm":  "webm",
        "audio/ogg":   "ogg",
        "audio/opus":  "ogg",
        "audio/wav":   "wav",
        "audio/wave":  "wav",
        "audio/x-wav": "wav",
        "audio/mp3":   "mp3",
        "audio/mpeg":  "mp3",
        "audio/flac":  "flac",
        "audio/mp4":   "mp4",
        "audio/m4a":   "mp4",
    }
    return mapping.get(ct, "webm")  # Default to webm (browser default)
