"""
voice/audio.py - Audio Preprocessing (Phase 2)
=================================================
Handles audio format conversion, resampling, silence detection,
and basic noise reduction to prepare browser-captured audio for
the STT engine.

Design Decisions:
  - Browser MediaRecorder typically produces WebM/Opus. Faster-whisper
    can handle most formats via ffmpeg, but we normalise to 16-bit
    PCM WAV at 16 kHz for maximum compatibility and predictability.
  - Uses pydub (with ffmpeg backend) for format conversion.
  - Falls back to raw passthrough if pydub/ffmpeg is unavailable
    (faster-whisper can still attempt decoding via its own ffmpeg).
  - Silence detection returns True if the audio is below a dBFS
    threshold - useful for skipping STT on empty recordings.
"""

import io
import os
import logging
import tempfile
from typing import Optional, Tuple

from pydub import AudioSegment
FFMPEG_BIN_DIR = r"C:\Users\rajes\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin"
os.environ["PATH"] = FFMPEG_BIN_DIR + os.pathsep + os.environ.get("PATH", "")

from pydub import AudioSegment
AudioSegment.converter = os.path.join(FFMPEG_BIN_DIR, "ffmpeg.exe")
AudioSegment.ffprobe = os.path.join(FFMPEG_BIN_DIR, "ffprobe.exe")

from pydub import AudioSegment
AudioSegment.converter = os.path.join(FFMPEG_BIN_DIR, "ffmpeg.exe")
AudioSegment.ffprobe = os.path.join(FFMPEG_BIN_DIR, "ffprobe.exe")

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
            "Audio converted: %s ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾Ãƒâ€šÃ‚Â¢ WAV  (%d ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾Ãƒâ€šÃ‚Â¢ %d bytes, %.1fs)",
            source_format, len(audio_bytes), len(wav_bytes),
            len(audio) / 1000,
        )
        return wav_bytes

    except ImportError:
        logger.warning(
            "pydub not installed ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â passing raw audio to STT engine. "
            "Install pydub and ffmpeg for reliable format conversion."
        )
        return audio_bytes

    except Exception as exc:
        logger.exception(
            "Audio conversion failed (%s) - passing raw bytes.", source_format
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

        if audio.dBFS < silence_threshold_dbfs:
            logger.info(
                "Silence detected: dBFS=%.1f (threshold=%.1f)",
                audio.dBFS, silence_threshold_dbfs,
            )
            return True
        return False

    except ImportError:
        logger.debug("pydub not available ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â skipping silence detection.")
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

import numpy as np


class FrameBuffer:
    """
    Streaming audio bytes ko fixed-size (512-sample) float32 frames
    me todta hai ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â VAD ko chahiye exactly is size ka input.

    Usage:
        buf = FrameBuffer()
        for chunk_bytes in incoming_websocket_chunks:
            for frame in buf.add_chunk(chunk_bytes):
                # frame ab exactly 512 samples ka hai, VAD ko do
                prob = detector.vad.speech_probability(frame)
    """

    FRAME_SAMPLES = 512

    def __init__(self):
        self._leftover = np.array([], dtype=np.float32)

    def add_chunk(self, pcm_bytes: bytes):
        """
        Raw 16-bit PCM bytes (mono, 16kHz) do ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â ye yield karega
        har complete 512-sample frame jo ban paya, aur bacha hua
        agli baar ke liye internally rakh lega.
        """
        # 16-bit PCM ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾Ãƒâ€šÃ‚Â¢ float32 normalized (-1.0 se 1.0)
        new_samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        combined = np.concatenate([self._leftover, new_samples])

        num_full_frames = len(combined) // self.FRAME_SAMPLES
        frames = []
        for i in range(num_full_frames):
            start = i * self.FRAME_SAMPLES
            frames.append(combined[start : start + self.FRAME_SAMPLES])

        # Jo samples bache (frame poora nahi bana), agli baar ke liye rakho
        self._leftover = combined[num_full_frames * self.FRAME_SAMPLES :]
        return frames

    def reset(self):
        self._leftover = np.array([], dtype=np.float32)
