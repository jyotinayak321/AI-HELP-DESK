"""
One-time cleanup script: removes duplicate pydub/ffmpeg setup lines
and fixes mojibake (broken encoding) in the docstring at the top
of voice/audio.py, keeping the rest of the file untouched.
"""

FFMPEG_BIN = r"C:\phase2_downloads\ffmpeg\ffmpeg-7.0-essentials_build\bin"

with open("voice/audio.py", "r", encoding="utf-8", errors="replace") as f:
    lines = f.readlines()

# Find where the real code starts (the logger line) — everything
# from there onward is untouched and kept as-is.
split_index = None
for i, line in enumerate(lines):
    if line.strip().startswith('logger = logging.getLogger'):
        split_index = i
        break

if split_index is None:
    raise SystemExit("Could not find the logger line — aborting to avoid breaking the file.")

rest_of_file = "".join(lines[split_index:])

clean_header = f'''"""
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
AudioSegment.converter = r"{FFMPEG_BIN}\\ffmpeg.exe"
AudioSegment.ffprobe = r"{FFMPEG_BIN}\\ffprobe.exe"

'''

with open("voice/audio.py", "w", encoding="utf-8") as f:
    f.write(clean_header + rest_of_file)

print("✅ voice/audio.py header cleaned successfully.")x