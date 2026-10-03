"""Independent English sequence-to-sequence transcript verification.

This module checks textual support only. It does not assess a speaker's traits
or speaking ability and never rewrites the user-supplied comparison transcript.
"""

from __future__ import annotations

from pathlib import Path
import hashlib
import re
import time

import numpy as np

from .alignment import normalize_transcript
from .audio import SAMPLE_RATE

WHISPER_REVISION = "911407f4214e0e1d82085af863093ec0b66f9cd6"
WHISPER_SHA256 = "d4dd5542fd6a1d35639e21384238f3bfe6c557c849d392b5905d33ee29e71db5"
WHISPER_PATH = Path(__file__).resolve().parents[1] / ".cache" / "whisper-base-en"


def edit_distance(a: list[str], b: list[str]) -> int:
    previous = list(range(len(b) + 1))
    for i, left in enumerate(a, 1):
        current = [i]
        for j, right in enumerate(b, 1):
            current.append(min(current[-1] + 1, previous[j] + 1,
                               previous[j - 1] + (left != right)))
        previous = current
    return previous[-1]


def word_agreement(expected: str, recognized: str, *, prefix: bool = False) -> float:
    wanted = normalize_transcript(expected).split()
    # Recognition may render digits even when the supplied transcript spells
    # them out. Keep those as mismatches rather than raising an input error.
    heard = re.sub(r"[^A-Z0-9' ]", " ", recognized.replace("’", "'").upper()).split()
    if prefix:
        heard = heard[:len(wanted)]
    return max(0.0, 1.0 - edit_distance(wanted, heard) / len(wanted))


class TranscriptVerifier:
    def __init__(self, model_path: Path | str = WHISPER_PATH):
        import torch
        from transformers import WhisperForConditionalGeneration, WhisperProcessor
        path = Path(model_path)
        weights = path / "model.safetensors"
        if not weights.is_file():
            raise ValueError("Pinned local transcript-verifier weights are missing.")
        with weights.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != WHISPER_SHA256:
            raise ValueError("Transcript-verifier checksum does not match the pinned revision.")
        torch.set_num_threads(2)
        torch.manual_seed(0)
        self.processor = WhisperProcessor.from_pretrained(path, local_files_only=True)
        self.model = WhisperForConditionalGeneration.from_pretrained(
            path, local_files_only=True, use_safetensors=True).eval()

    def verify(self, audio: np.ndarray, transcript: str, *, prefix: bool = False) -> dict:
        import torch
        audio = np.asarray(audio, dtype=np.float32)
        if audio.ndim != 1 or not 0.5 * SAMPLE_RATE <= len(audio) <= 30 * SAMPLE_RATE:
            raise ValueError("Transcript verification accepts 0.5 to 30 seconds of mono audio.")
        if not np.isfinite(audio).all():
            raise ValueError("Audio contains non-finite samples.")
        normalize_transcript(transcript)
        before = time.perf_counter()
        inputs = self.processor(audio, sampling_rate=SAMPLE_RATE, return_tensors="pt",
                                return_attention_mask=True)
        with torch.inference_mode():
            tokens = self.model.generate(**inputs, do_sample=False, num_beams=1,
                                         max_new_tokens=200, return_timestamps=False)
        recognized = self.processor.batch_decode(tokens, skip_special_tokens=True)[0].strip()
        return {"recognized_text": recognized,
                "word_agreement": round(word_agreement(transcript, recognized, prefix=prefix), 5),
                "inference_seconds": round(time.perf_counter() - before, 4),
                "model_revision": WHISPER_REVISION}
