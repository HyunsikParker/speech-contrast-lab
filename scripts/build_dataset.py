"""One frozen, preregistered 30-pair evaluation. No model training or tuning."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from speechcontrast.alignment import Aligner
from speechcontrast.audio import SAMPLE_RATE, decode_audio, write_wav
from speechcontrast.comparison import compare, RUBRIC_VERSION, THRESHOLDS
from speechcontrast.perturbations import inject, ffmpeg_filter
from speechcontrast.transcript import TranscriptVerifier


def save(path: Path, value: dict, *, private=False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    if private:
        path.chmod(0o600)


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def iou(left: dict, right: dict) -> float:
    overlap = max(0, min(left["end"], right["end"]) - max(left["start"], right["start"]))
    return overlap / max(1e-8, max(left["end"], right["end"]) - min(left["start"], right["start"]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait-for", type=Path, required=True)
    parser.add_argument("--ready", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    save(args.ready, {"pid": os.getpid(), "status": "waiting_for_run_receipt"}, private=True)
    wait = time.monotonic()
    while not args.wait_for.exists():
        if time.monotonic() - wait > 180:
            raise TimeoutError("No registered run receipt.")
        time.sleep(0.2)
    started = time.perf_counter()
    try:
        protocol = json.loads((ROOT / "data/protocol-v1.json").read_text())
        examples, baselines = [], {}
        aligner = Aligner()
        for source in protocol["speakers"]:
            raw = ROOT / source["raw_file"]
            if digest(raw) != source["raw_sha256"]:
                raise ValueError("Source checksum mismatch.")
            opening = decode_audio(raw, seconds=30)
            aligned = aligner.align(opening, source["transcript"], free_edges=True)
            aligned.pop("emissions")
            crop_a = max(0, int((aligned["words"][0]["start"] - 0.15) * SAMPLE_RATE))
            crop_b = min(len(opening), int((aligned["words"][-1]["end"] + 0.18) * SAMPLE_RATE))
            audio = opening[crop_a:crop_b]
            peak_scale = min(1.0, 0.5 / max(float(np.max(abs(audio))), 1e-8))
            audio = audio * peak_scale
            words = [{**word, "start": round(word["start"] - crop_a / SAMPLE_RATE, 5),
                      "end": round(word["end"] - crop_a / SAMPLE_RATE, 5)} for word in aligned["words"]]
            folder = ROOT / "data/examples" / source["id"]
            folder.mkdir(parents=True, exist_ok=True)
            reference_path = folder / "reference.wav"
            write_wav(reference_path, audio)
            audio = decode_audio(reference_path, seconds=30)
            # Cropping changes the model's frame origin and edge context.
            # Both sides must align the actual cropped, quantized PCM.
            cropped_alignment = aligner.align(audio, source["transcript"])
            words = cropped_alignment["words"]
            reference = {"id": source["id"], "split": source["split"], "transcript": source["transcript"],
                         "audio": reference_path.relative_to(ROOT).as_posix(), "audio_sha256": digest(reference_path),
                         "source_crop_samples": [crop_a, crop_b], "words": words, "verification": None,
                         "source_peak_scale": peak_scale,
                         "median_confidence": cropped_alignment["median_confidence"], "alignment_kind": "silver_frozen_ctc"}
            baselines[source["id"]] = {"metadata": reference, "waveform": audio}
            a, b = protocol["target_word_indices"]
            start, end = words[a]["start"], words[b]["end"]
            for kind, levels in protocol["levels"].items():
                for level, parameter in enumerate(levels, 1):
                    boundary = words[protocol["pause_before_word_index"]]["start"] if kind == "pause" else start
                    edited, label = inject(audio, kind, parameter, boundary, end,
                                           seed=protocol["seed"] + level)
                    example_id = f"{source['id']}-{kind}-{level}"
                    path = folder / f"{kind}-{level}.wav"
                    write_wav(path, edited)
                    examples.append({"id": example_id, "source_id": source["id"], "split": source["split"],
                                     "transcript": source["transcript"], "family": kind, "level": level,
                                     "audio": path.relative_to(ROOT).as_posix(), "audio_sha256": digest(path), "label": label})
            controls = {"identical": audio.copy(), "global_gain_0.5": audio * 0.5,
                        "global_pitch_1.15": ffmpeg_filter(audio, "asetrate=18400,aresample=16000,atempo=0.869565217")}
            for name, waveform in controls.items():
                path = folder / f"control-{name}.wav"
                if name == "identical":
                    shutil.copyfile(reference_path, path)
                else:
                    write_wav(path, waveform)
                examples.append({"id": f"{source['id']}-{name}", "source_id": source["id"],
                                 "split": source["split"], "transcript": source["transcript"],
                                 "family": "control", "control": name, "level": 0,
                                 "audio": path.relative_to(ROOT).as_posix(), "audio_sha256": digest(path), "label": None})
        del aligner
        gc.collect()
        verifier = TranscriptVerifier()
        for baseline in baselines.values():
            baseline["metadata"]["verification"] = verifier.verify(baseline["waveform"], baseline["metadata"]["transcript"])
        for example in examples:
            audio = decode_audio(ROOT / example["audio"], seconds=30)
            example["verification"] = verifier.verify(audio, example["transcript"])
        del verifier
        gc.collect()
        aligner = Aligner()
        for example in examples:
            audio = decode_audio(ROOT / example["audio"], seconds=30)
            baseline = baselines[example["source_id"]]
            if example["verification"]["word_agreement"] < THRESHOLDS["transcript_agreement_min"]:
                example.update({"abstained": True, "abstention_reason": "Independent transcript agreement below 0.90.",
                                "targeted_hit": False, "max_target_iou": 0, "score": None, "regions": []})
            else:
                aligned = aligner.align(audio, example["transcript"])
                aligned.pop("emissions")
                result = compare(baseline["waveform"], audio, baseline["metadata"]["words"], aligned["words"])
                result["transcript"] = example["transcript"]
                result["verification"] = {"reference": baseline["metadata"]["verification"], "delivery": example["verification"]}
                analysis_path = (ROOT / example["audio"]).with_suffix(".analysis.json")
                save(analysis_path, result)
                target_iou = max([iou(region, example["label"]) for region in result["regions"]
                                  if region["kind"] == example["family"]], default=0) if example["label"] else 0
                example.update({"abstained": False, "words": aligned["words"], "analysis": analysis_path.relative_to(ROOT).as_posix(),
                                "analysis_sha256": digest(analysis_path), "score": result["score"],
                                "targeted_hit": target_iou >= 0.25, "max_target_iou": round(target_iou, 5),
                                "regions": [{key: region[key] for key in ("kind", "start", "end", "words")} for region in result["regions"]]})
            print(json.dumps({"example": example["id"], "score": example["score"], "targeted_hit": example["targeted_hit"],
                              "agreement": example["verification"]["word_agreement"], "abstained": example["abstained"]}), flush=True)
            if time.perf_counter() - started > 900:
                raise TimeoutError("Bounded evaluation exceeded 15 minutes.")
        controls = [e for e in examples if e["family"] == "control"]
        strong = [e for e in examples if e["level"] >= 2]
        near = [e for e in examples if e["level"] == 1]
        holdout = [e for e in strong if e["split"] == "unseen_speaker_holdout"]
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024)
        metrics = {"examples": len(examples), "moderate_severe_targeted_hit_fraction": sum(e["targeted_hit"] for e in strong) / len(strong),
                   "near_perfect_targeted_hit_fraction": sum(e["targeted_hit"] for e in near) / len(near),
                   "unseen_speaker_moderate_severe_hit_fraction": sum(e["targeted_hit"] for e in holdout) / len(holdout),
                   "control_false_alerts": sum(bool(e["regions"]) for e in controls),
                   "control_scored_fraction": sum(not e["abstained"] for e in controls) / len(controls),
                   "abstentions": sum(e["abstained"] for e in examples),
                   "minimum_baseline_agreement": min(b["metadata"]["verification"]["word_agreement"] for b in baselines.values()),
                   "minimum_baseline_confidence": min(b["metadata"]["median_confidence"] for b in baselines.values()),
                   "peak_resident_bytes": peak, "elapsed_s": round(time.perf_counter() - started, 4)}
        gate = protocol["success_gate"]
        passed = (metrics["examples"] == gate["examples"] and
                  metrics["moderate_severe_targeted_hit_fraction"] >= gate["minimum_moderate_severe_targeted_hit_fraction"] and
                  metrics["control_false_alerts"] <= gate["maximum_control_false_alerts"] and
                  metrics["control_scored_fraction"] >= gate["minimum_control_scored_fraction"] and
                  metrics["minimum_baseline_agreement"] >= gate["minimum_baseline_transcript_agreement"] and
                  metrics["minimum_baseline_confidence"] >= gate["minimum_baseline_median_word_probability"] and
                  peak <= gate["maximum_peak_resident_bytes"] and metrics["elapsed_s"] <= gate["maximum_wall_seconds"])
        manifest = {"protocol_id": protocol["protocol_id"], "protocol_sha256": digest(ROOT / "data/protocol-v1.json"),
                    "rubric_version": RUBRIC_VERSION, "thresholds": THRESHOLDS,
                    "references": [b["metadata"] for b in baselines.values()], "examples": examples,
                    "metrics": metrics, "gate_passed": passed,
                    "limitations": ["Two source speakers; this is a small controlled stress test, not broad rhetorical or demographic validation.",
                                    "DSP edit boundaries are exact; word times are unreviewed model estimates.",
                                    "Abstentions and subtle misses count in the reported denominators. No official contest score is available."]}
        save(ROOT / "data/manifest-v1.json", manifest)
        save(args.output, {"gate_passed": passed, "metrics": metrics,
                           "manifest_sha256": digest(ROOT / "data/manifest-v1.json"),
                           "protocol_sha256": manifest["protocol_sha256"]}, private=True)
        print(json.dumps({"gate_passed": passed, "metrics": metrics}), flush=True)
        return 0 if passed else 1
    except Exception as error:
        save(args.output, {"gate_passed": False, "failure_class": "operational",
                           "error_type": type(error).__name__, "error_message": str(error)[:300],
                           "metrics": {"elapsed_s": round(time.perf_counter() - started, 4)}}, private=True)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
