"""Deterministic labeled edits. Labels describe edits, not rhetorical judgments."""

from __future__ import annotations

import subprocess
import numpy as np

from .audio import SAMPLE_RATE


def ffmpeg_filter(audio: np.ndarray, expression: str) -> np.ndarray:
    # Only internal fixed filter expressions are used; this is not an API input.
    result = subprocess.run([
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
        "-f", "f32le", "-ar", str(SAMPLE_RATE), "-ac", "1", "-i", "pipe:0",
        "-af", expression, "-f", "f32le", "-ar", str(SAMPLE_RATE), "pipe:1"],
        input=np.asarray(audio, dtype="<f4").tobytes(), capture_output=True, timeout=15)
    if result.returncode:
        raise ValueError("Internal audio transformation failed.")
    return np.frombuffer(result.stdout, dtype="<f4").copy()


def inject(audio: np.ndarray, kind: str, value: float, start: float, end: float, *, seed: int) -> tuple[np.ndarray, dict]:
    signal = np.asarray(audio, dtype=np.float32)
    a, b = round(start * SAMPLE_RATE), round(end * SAMPLE_RATE)
    if not 0 <= a < b <= len(signal):
        raise ValueError("Edit interval must lie inside the waveform.")
    segment = signal[a:b].copy()
    if kind == "pace":
        rate = (1 / value) ** 0.5
        modified = ffmpeg_filter(segment, f"atempo={rate:.9f},atempo={rate:.9f}")
    elif kind == "pause":
        modified = np.r_[np.zeros(round(value * SAMPLE_RATE), dtype=np.float32), segment]
    elif kind == "volume":
        modified = segment * value
    elif kind == "roughness":
        noise = np.random.default_rng(seed).normal(size=len(segment))
        noise *= np.sqrt(np.mean(segment ** 2)) / max(np.std(noise), 1e-12) / 10 ** (value / 20)
        modified = (segment + noise).astype(np.float32)
    else:
        raise ValueError("Unknown edit family.")
    output = np.r_[signal[:a], modified, signal[b:]].astype(np.float32)
    if np.max(np.abs(output), initial=0) > 1:
        raise ValueError("Transformation would clip; preserve the source rather than rescale it silently.")
    label_end = start + value if kind == "pause" else (a + len(modified)) / SAMPLE_RATE
    return output, {"kind": kind, "parameter": value, "start": a / SAMPLE_RATE,
                    "end": label_end, "reference_start": a / SAMPLE_RATE, "reference_end": b / SAMPLE_RATE,
                    "sample_start": a, "sample_end": round(label_end * SAMPLE_RATE),
                    "time_map": {"before": "identity", "inside_scale": len(modified) / len(segment),
                                 "after_offset_s": (len(modified) - len(segment)) / SAMPLE_RATE},
                    "label_kind": "Exact inserted/edit interval, not a manual speech-quality label."}
