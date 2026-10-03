"""Deterministic 25 ms acoustic frames with 10 ms hop; no learned scoring."""

from __future__ import annotations

import numpy as np
from scipy.fft import dct
from scipy.signal import find_peaks

from .audio import SAMPLE_RATE

FRAME, HOP, FFT = 400, 160, 512


def extract_features(audio: np.ndarray) -> dict[str, np.ndarray]:
    signal = np.asarray(audio, dtype=np.float64)
    if signal.ndim != 1 or not FRAME <= len(signal) <= 30 * SAMPLE_RATE:
        raise ValueError("Features accept a mono signal between 25 ms and 30 seconds.")
    if not np.isfinite(signal).all():
        raise ValueError("Feature input must be finite.")
    frames = np.lib.stride_tricks.sliding_window_view(signal, FRAME)[::HOP].copy()
    rms = np.sqrt(np.mean(frames ** 2, axis=1))
    db = 20 * np.log10(np.maximum(rms, 1e-8))
    active = (db > max(-80, float(np.percentile(db, 85)) - 30))
    energy_center = float(np.median(db[active])) if active.any() else 0.0
    spectrum = np.abs(np.fft.rfft(frames * np.hanning(FRAME), n=FFT, axis=1)) ** 2 + 1e-12
    frequencies = np.fft.rfftfreq(FFT, 1 / SAMPLE_RATE)
    flatness = np.exp(np.mean(np.log(spectrum[:, 2:]), axis=1)) / np.mean(spectrum[:, 2:], axis=1)
    centroid = np.sum(spectrum * frequencies, axis=1) / np.sum(spectrum, axis=1)
    mel_points = np.linspace(2595 * np.log10(1 + 80 / 700), 2595 * np.log10(1 + 7600 / 700), 28)
    hz_points = 700 * (10 ** (mel_points / 2595) - 1)
    banks = np.maximum(0, np.minimum(
        (frequencies[None, :] - hz_points[:-2, None]) / (hz_points[1:-1] - hz_points[:-2])[:, None],
        (hz_points[2:, None] - frequencies[None, :]) / (hz_points[2:] - hz_points[1:-1])[:, None]))
    mfcc = dct(np.log(np.maximum(spectrum @ banks.T, 1e-12)), type=2, norm="ortho", axis=1)[:, 1:14]
    # Per-frame, mean-centered autocorrelation. Peak selection avoids the
    # minimum-lag edge being mistaken for a fundamental.
    centered = frames - frames.mean(axis=1, keepdims=True)
    autocorr = np.fft.irfft(np.abs(np.fft.rfft(centered, n=1024, axis=1)) ** 2, n=1024, axis=1)[:, :FRAME]
    autocorr /= np.maximum(autocorr[:, :1], 1e-12)
    pitch = np.zeros(len(frames))
    periodicity = np.zeros(len(frames))
    low, high = int(SAMPLE_RATE / 400), int(SAMPLE_RATE / 60)
    for i, correlation in enumerate(autocorr):
        peaks, _ = find_peaks(correlation[low:high + 1])
        if len(peaks) and active[i]:
            candidates = peaks + low
            lag = candidates[np.argmax(correlation[candidates])]
            periodicity[i] = np.clip(correlation[lag], 0, 1)
            if periodicity[i] >= 0.6:
                pitch[i] = SAMPLE_RATE / lag
    voiced = pitch > 0
    pitch_center = float(np.median(pitch[voiced])) if voiced.any() else 0.0
    semitones = np.zeros(len(pitch))
    if voiced.any():
        semitones[voiced] = 12 * np.log2(pitch[voiced] / pitch_center)
    return {"time": (np.arange(len(frames)) * HOP + FRAME / 2) / SAMPLE_RATE,
            "rms": rms, "energy_db": db, "relative_energy_db": db - energy_center,
            "f0_hz": pitch, "pitch_semitones": semitones, "voiced": voiced,
            "periodicity": periodicity, "spectral_flatness": flatness,
            "spectral_centroid_hz": centroid, "mfcc": mfcc, "active": active}


def word_features(frames: dict[str, np.ndarray], words: list[dict]) -> list[dict]:
    results = []
    for word in words:
        mask = (frames["time"] >= word["start"]) & (frames["time"] <= word["end"])
        if not mask.any():
            mask[np.argmin(abs(frames["time"] - (word["start"] + word["end"]) / 2))] = True
        voiced = mask & frames["voiced"]
        results.append({
            "duration": word["end"] - word["start"],
            "relative_energy_db": float(np.median(frames["relative_energy_db"][mask])),
            "pitch_semitones": float(np.median(frames["pitch_semitones"][voiced])) if voiced.any() else None,
            "voiced_fraction": float(voiced.sum() / mask.sum()),
            "periodicity": float(np.median(frames["periodicity"][mask])),
            "spectral_flatness": float(np.median(frames["spectral_flatness"][mask])),
            "mfcc": np.median(frames["mfcc"][mask], axis=0).round(5).tolist(),
        })
    return results


def plot_frames(frames: dict[str, np.ndarray], *, maximum: int = 800) -> dict:
    indices = np.arange(0, len(frames["time"]), max(1, int(np.ceil(len(frames["time"]) / maximum))))
    return {key: [None if key == "pitch_semitones" and not frames["voiced"][i]
                  else round(float(frames[key][i]), 4) for i in indices]
            for key in ("time", "relative_energy_db", "pitch_semitones", "spectral_flatness")}
