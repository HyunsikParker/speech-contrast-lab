"""Bounded local audio decoding. No URL or network protocol is accepted."""

from __future__ import annotations

from pathlib import Path
import subprocess
import wave

import numpy as np

SAMPLE_RATE = 16_000
MAX_SECONDS = 90
MAX_BYTES = 16_000_000


def decode_audio(path: Path | str, *, start: float = 0, seconds: float = MAX_SECONDS) -> np.ndarray:
    path = Path(path)
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError("Audio must be a local file of at most 16 MB.")
    if not 0 <= start < 3600 or not 0 < seconds <= MAX_SECONDS:
        raise ValueError("Choose a positive excerpt of at most 90 seconds.")
    command = [
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
        "-protocol_whitelist", "file,pipe", "-format_whitelist", "wav,mp3,flac,ogg,matroska,webm",
        "-ss", str(start), "-i", str(path.resolve()), "-t", str(seconds),
        "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "pipe:1",
    ]
    result = subprocess.run(command, capture_output=True, timeout=20, check=False)
    if result.returncode:
        raise ValueError("Could not decode this audio format.")
    audio = np.frombuffer(result.stdout, dtype="<f4").copy()
    if len(audio) < SAMPLE_RATE // 2 or len(audio) > (MAX_SECONDS + 1) * SAMPLE_RATE:
        raise ValueError("Audio must last between 0.5 and 90 seconds.")
    if not np.isfinite(audio).all():
        raise ValueError("Audio contains non-finite samples.")
    return audio


def write_wav(path: Path | str, audio: np.ndarray) -> None:
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim != 1 or not np.isfinite(audio).all():
        raise ValueError("Expected a finite mono signal.")
    samples = (np.clip(audio, -1, 1) * 32767).round().astype("<i2")
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(SAMPLE_RATE)
        stream.writeframes(samples.tobytes())
