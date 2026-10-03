"""One local comparison process. The HTTP server deletes its input directory."""

from __future__ import annotations

import gc
import json
from pathlib import Path
import sys
import time

from .alignment import Aligner, normalize_transcript
from .audio import decode_audio, SAMPLE_RATE
from .comparison import compare, THRESHOLDS
from .transcript import TranscriptVerifier


def analyze_files(reference: Path, delivery: Path, transcript: str) -> dict:
    normalize_transcript(transcript)
    started = time.perf_counter()
    # Decode one extra second to reject, not silently trim, overlong uploads.
    waveforms = [decode_audio(path, seconds=31) for path in (reference, delivery)]
    if any(len(audio) > 30 * SAMPLE_RATE for audio in waveforms):
        raise ValueError("Each recording must be at most 30 seconds; trim it before uploading.")
    verifier = TranscriptVerifier()
    verified = [verifier.verify(audio, transcript) for audio in waveforms]
    del verifier
    gc.collect()
    if any(item["word_agreement"] < THRESHOLDS["transcript_agreement_min"] for item in verified):
        return {"abstained": True, "reason": "The independent recognizer does not support the same supplied transcript in both recordings (minimum agreement:90%).",
                "verification": {"reference": verified[0], "delivery": verified[1]}, "score": None,
                "regions": [], "transcript": transcript, "processing_seconds": round(time.perf_counter() - started, 3)}
    aligner = Aligner()
    alignments = [aligner.align(audio, transcript) for audio in waveforms]
    if any(alignment["median_confidence"] < THRESHOLDS["word_confidence_min"] for alignment in alignments):
        return {"abstained": True, "reason": "Word alignment has insufficient acoustic support; no delivery score is assigned.",
                "verification": {"reference": verified[0], "delivery": verified[1]}, "score": None, "regions": [], "transcript": transcript}
    result = compare(waveforms[0], waveforms[1], alignments[0]["words"], alignments[1]["words"])
    return {**result, "abstained": False, "transcript": transcript,
            "verification": {"reference": verified[0], "delivery": verified[1]},
            "processing_seconds": round(time.perf_counter() - started, 3)}


def main():
    request_path, result_path = map(Path, sys.argv[1:])
    request = json.loads(request_path.read_text())
    try:
        result = analyze_files(Path(request["reference"]), Path(request["delivery"]), request["transcript"])
        code = 0
    except ValueError as error:
        result = {"error": str(error)}
        code = 2
    result_path.write_text(json.dumps(result, allow_nan=False) + "\n")
    result_path.chmod(0o600)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
