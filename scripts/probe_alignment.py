"""One preregistered feasibility check. Waits for the Bounty run receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time

import numpy as np
from scipy.signal import resample_poly

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from speechcontrast.alignment import Aligner, align_emissions, normalize_transcript
from speechcontrast.audio import SAMPLE_RATE, decode_audio


def edit_distance(a: list[str], b: list[str]) -> int:
    previous = list(range(len(b) + 1))
    for i, left in enumerate(a, 1):
        current = [i]
        for j, right in enumerate(b, 1):
            current.append(min(current[-1] + 1, previous[j] + 1,
                               previous[j - 1] + (left != right)))
        previous = current
    return previous[-1]


def save(path: Path, result: dict) -> None:
    path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    path.chmod(0o600)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait-for", type=Path, required=True)
    parser.add_argument("--ready", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    save(args.ready, {"pid": os.getpid(), "status": "waiting_for_run_receipt"})
    waiting = time.monotonic()
    while not args.wait_for.exists():
        if time.monotonic() - waiting > 180:
            raise TimeoutError("No Bounty run receipt within launch window.")
        time.sleep(0.2)
    root = Path(__file__).resolve().parents[1]
    started = time.perf_counter()
    try:
        source = json.loads((root / "data/sources.json").read_text())[0]
        audio = decode_audio(root / "data/raw/obama-weekly-20090711.mp3", seconds=30)
        transcript = source["opening_transcript"]
        aligner = Aligner()
        shifted = np.r_[np.zeros(int(0.8 * SAMPLE_RATE), dtype=np.float32), audio]
        dilated = resample_poly(audio, 11, 10).astype(np.float32)
        examples = {"original": audio, "prepend_0_8s": shifted, "dilate_1_1": dilated}
        results = {}
        inference_seconds = 0
        for name, waveform in examples.items():
            result = aligner.align(waveform, transcript, free_edges=True)
            np.savez_compressed(args.output.parent / (name + "-emissions.npz"),
                                log_probs=result.pop("emissions"))
            results[name] = result
            inference_seconds += result["inference_seconds"]
            print(json.dumps({"example": name, "inference_seconds": result["inference_seconds"],
                              "median_confidence": result["median_confidence"]}), flush=True)
            if inference_seconds > 120 or time.perf_counter() - started > 900:
                break
        original = results["original"]
        expected = normalize_transcript(transcript).split()
        decoded = normalize_transcript(original["greedy_transcript"]).split()[:len(expected)]
        agreement = max(0, 1 - edit_distance(expected, decoded) / len(expected))
        deviations = []
        for name in ["prepend_0_8s", "dilate_1_1"]:
            if name not in results:
                deviations.append(900)
                continue
            for old, new in zip(original["words"], results[name]["words"]):
                midpoint = (old["start"] + old["end"]) / 2
                expected_midpoint = midpoint + 0.8 if name == "prepend_0_8s" else midpoint * 1.1
                deviations.append(abs((new["start"] + new["end"]) / 2 - expected_midpoint))
        words = original["words"]
        valid = sum(word["end"] > word["start"] and (i == 0 or word["start"] >= words[i - 1]["start"])
                    for i, word in enumerate(words)) / len(expected)
        replay = align_emissions(np.load(args.output.parent / "original-emissions.npz")["log_probs"],
                                 transcript, aligner.vocab, blank=aligner.blank,
                                 frame_hop=aligner.hop, frame_width=aligner.width,
                                 duration=len(audio) / SAMPLE_RATE, free_edges=True)
        peak_bytes = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform != "darwin":
            peak_bytes *= 1024
        metrics = {
            "greedy_token_agreement": round(agreement, 5), "valid_word_fraction": valid,
            "median_acoustic_probability": original["median_confidence"],
            "median_time_map_error_s": round(float(np.median(deviations)), 5),
            "p95_time_map_error_s": round(float(np.percentile(deviations, 95)), 5),
            "cumulative_inference_s": round(inference_seconds, 4),
            "emissions_replay_exact": int(replay == words),
            "peak_resident_bytes": peak_bytes, "elapsed_s": round(time.perf_counter() - started, 4),
        }
        passed = (agreement >= 0.9 and valid >= 0.95 and original["median_confidence"] >= 0.15
                  and metrics["median_time_map_error_s"] <= 0.12
                  and metrics["p95_time_map_error_s"] <= 0.30 and inference_seconds <= 120
                  and metrics["emissions_replay_exact"] == 1 and peak_bytes <= 4 * 2**30
                  and len(results) == 3 and metrics["elapsed_s"] <= 900)
        result = {"gate_passed": passed, "metrics": metrics, "examples": results,
                  "source_audio_sha256": hashlib.sha256((root / "data/raw/obama-weekly-20090711.mp3").read_bytes()).hexdigest(),
                  "limitation": "Timing equivariance and token agreement are feasibility proxies, not manually labeled absolute word timing accuracy or official judging results."}
        save(args.output, result)
        print(json.dumps({"gate_passed": passed, "metrics": metrics}), flush=True)
        return 0 if passed else 1
    except Exception as error:
        save(args.output, {"gate_passed": False, "failure_class": "operational",
                           "error_type": type(error).__name__, "error_message": str(error)[:300],
                           "metrics": {"elapsed_s": round(time.perf_counter() - started, 4)}})
        raise


if __name__ == "__main__":
    raise SystemExit(main())

