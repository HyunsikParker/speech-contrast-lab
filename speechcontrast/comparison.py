"""Transcript-conditioned deltas, fixed thresholds, and a transparent rubric.

Reference delivery is a chosen comparison, not a universal rhetorical ideal.
Observed acoustic differences are not diagnoses of intent or speaker quality.
"""

from __future__ import annotations

import math
import numpy as np

from .features import extract_features, plot_frames, word_features

RUBRIC_VERSION = "contrast-v2.0"
THRESHOLDS = {"duration_ratio_high": 1.25, "duration_ratio_low": 0.75,
              "minimum_word_duration_delta_s": 0.08,
              "extra_pause_s": 0.20, "relative_energy_delta_db": 3.0,
              "flatness_ratio_db": 12.0, "periodicity_drop": 0.06,
              "word_confidence_min": 0.15, "transcript_agreement_min": 0.90}
WEIGHTS = {"pace": 35, "pause": 25, "volume": 25, "roughness": 15}


def compare(reference: np.ndarray, delivery: np.ndarray, reference_words: list[dict],
            delivery_words: list[dict]) -> dict:
    if not reference_words or len(reference_words) != len(delivery_words):
        raise ValueError("Both recordings need the same aligned transcript.")
    if [w["word"] for w in reference_words] != [w["word"] for w in delivery_words]:
        raise ValueError("Aligned transcripts differ.")
    for words, audio in [(reference_words, reference), (delivery_words, delivery)]:
        if any(not 0 <= w["start"] < w["end"] <= len(audio) / 16000 + 0.01
               or (i and w["start"] < words[i - 1]["end"]) for i, w in enumerate(words)):
            raise ValueError("Word intervals must be ordered, disjoint and inside the audio.")
    baseline_frames, delivery_frames = extract_features(reference), extract_features(delivery)
    baseline = word_features(baseline_frames, reference_words)
    observed = word_features(delivery_frames, delivery_words)
    events, rows = [], []
    for i, (a, b, ref_word, word) in enumerate(zip(baseline, observed, reference_words, delivery_words)):
        ratio = b["duration"] / a["duration"]
        energy = b["relative_energy_db"] - a["relative_energy_db"]
        flatness = b["spectral_flatness"] - a["spectral_flatness"]
        flatness_ratio_db = 10 * math.log10(max(b["spectral_flatness"], 1e-6) / max(a["spectral_flatness"], 1e-6))
        periodicity_drop = a["periodicity"] - b["periodicity"]
        reliable = min(ref_word["confidence"], word["confidence"]) >= THRESHOLDS["word_confidence_min"]
        rows.append({"index": i, "word": word["word"], "reference": ref_word, "delivery": word,
                     "duration_ratio": round(ratio, 4), "energy_delta_db": round(energy, 4),
                     "flatness_delta": round(flatness, 5), "periodicity_drop": round(periodicity_drop, 5),
                     "flatness_ratio_db": round(flatness_ratio_db, 4),
                     "mfcc_distance": round(float(np.linalg.norm(np.array(b["mfcc"]) - a["mfcc"])), 4),
                     "reference_features": a, "delivery_features": b, "reliable": reliable})
        if not reliable:
            continue
        def add(kind: str, severity: float, explanation: str, measured: dict, start=None, end=None):
            events.append({"kind": kind, "word_indices": [i], "words": word["word"],
                           "start": word["start"] if start is None else start,
                           "end": word["end"] if end is None else end,
                           "reference_start": ref_word["start"], "reference_end": ref_word["end"],
                           "severity": round(float(np.clip(severity, 0, 1)), 4),
                           "explanation": explanation, "measured": measured})
        if (ratio > THRESHOLDS["duration_ratio_high"] or ratio < THRESHOLDS["duration_ratio_low"]) and abs(b["duration"] - a["duration"]) > THRESHOLDS["minimum_word_duration_delta_s"]:
            add("pace", abs(math.log(ratio)) / math.log(2),
                f"Word duration is {ratio:.2f}× the reference ({a['duration']:.2f}s → {b['duration']:.2f}s). "
                "Try this phrase at the reference pace, then choose the emphasis you want.",
                {"duration_ratio": round(ratio, 4), "baseline_s": round(a["duration"], 4), "delivery_s": round(b["duration"], 4)})
        if abs(energy) > THRESHOLDS["relative_energy_delta_db"]:
            add("volume", abs(energy) / 12,
                f"Relative energy differs by {energy:+.1f} dB after removing each recording's median level. "
                "Check whether this local emphasis or dip was intended.", {"energy_delta_db": round(energy, 4)})
        if flatness_ratio_db > THRESHOLDS["flatness_ratio_db"] and periodicity_drop > THRESHOLDS["periodicity_drop"]:
            add("roughness", max((flatness_ratio_db - 12) / 24, periodicity_drop),
                f"Spectral flatness rose by {flatness_ratio_db:.1f} dB; periodicity fell by {periodicity_drop:.2f}. "
                "This is compatible with added noise, but a recording change can also cause it. Check the audio.",
                {"flatness_ratio_db": round(flatness_ratio_db, 4), "periodicity_drop": round(periodicity_drop, 5)})
        if i:
            old_gap = ref_word["start"] - reference_words[i - 1]["end"]
            gap = word["start"] - delivery_words[i - 1]["end"]
            extra = gap - old_gap
            if extra > THRESHOLDS["extra_pause_s"]:
                add("pause", extra / 0.9,
                    f"The gap before {word['word']} is {gap:.2f}s; the reference gap is {old_gap:.2f}s "
                    f"({extra:+.2f}s). Shorten it if the break is not part of your phrasing.",
                    {"extra_pause_s": round(extra, 4), "baseline_gap_s": round(old_gap, 4), "delivery_gap_s": round(gap, 4)},
                    start=delivery_words[i - 1]["end"], end=word["start"])
    # Merge adjacent word detections of the same family, never unrelated spans.
    merged = []
    for kind in WEIGHTS:
        for event in [e for e in events if e["kind"] == kind]:
            if merged and merged[-1]["kind"] == kind and kind != "pause" and event["word_indices"][0] == merged[-1]["word_indices"][-1] + 1:
                target = merged[-1]
                target["end"] = event["end"]
                target["reference_end"] = event["reference_end"]
                target["word_indices"] += event["word_indices"]
                target["words"] += " " + event["words"]
                target["severity"] = max(target["severity"], event["severity"])
                target["word_evidence"].append(event)
            else:
                merged.append({**event, "word_evidence": [event]})
    components = []
    for kind, weight in WEIGHTS.items():
        values = [event["severity"] for event in events if event["kind"] == kind]
        burden = 0 if not values else min(1, 0.75 * max(values) + 0.25 * sum(values) / len(rows))
        components.append({"kind": kind, "weight": weight, "penalty": round(weight * burden, 2)})
    return {"rubric_version": RUBRIC_VERSION, "thresholds": THRESHOLDS,
            "score": round(100 - sum(component["penalty"] for component in components), 2),
            "score_label": "Reference similarity · custom acoustic rubric",
            "score_scope": "Not an official contest score or a measure of persuasiveness, accent, identity or speaking ability.",
            "components": components, "regions": sorted(merged, key=lambda e: e["start"]), "words": rows,
            "reference_frames": plot_frames(baseline_frames), "delivery_frames": plot_frames(delivery_frames),
            "reference_duration": round(len(reference) / 16000, 4), "delivery_duration": round(len(delivery) / 16000, 4),
            "normalization": "Energy: subtract active-frame median dB. Pitch: semitones relative to each recording's voiced median. "
                             "MFCC distance is diagnostic only; spectral or microphone differences may confound it.",
            "alignment_kind": "Frozen CTC model estimate, not manually verified word boundaries."}
