"""Blank-aware CTC Viterbi alignment; the acoustic model remains frozen.

Word times are acoustic estimates, not manual labels. The optional free edge
blanks allow an excerpt to contain speech outside the supplied transcript.
"""

from __future__ import annotations

from pathlib import Path
import hashlib
import re
import time

import numpy as np

from .audio import SAMPLE_RATE

MODEL_REVISION = "22aad52d435eb6dbaf354bdad9b0da84ce7d6156"
MODEL_SHA256 = "8aa76ab2243c81747a1f832954586bc566090c83a0ac167df6f31f0fa917d74a"
MODEL_PATH = Path(__file__).resolve().parents[1] / ".cache" / "wav2vec2-base-960h"


def normalize_transcript(text: str) -> str:
    if not isinstance(text, str) or len(text) > 1200:
        raise ValueError("Transcript must be text of at most 1,200 characters.")
    text = text.replace("’", "'").replace("‘", "'")
    if re.search(r"\d", text):
        raise ValueError("Spell numbers as spoken words before alignment.")
    if re.search(r"[^\x00-\x7f]", text):
        raise ValueError("This model supports English transcripts only.")
    normalized = " ".join(re.sub(r"[^A-Z' ]", " ", text.upper()).split())
    if not normalized or len(normalized.split()) > 180:
        raise ValueError("Transcript must contain 1 to 180 English words.")
    return normalized


def align_emissions(
    log_probs: np.ndarray, transcript: str, vocab: dict[str, int], *,
    blank: int = 0, frame_hop: float = 0.02, frame_width: float = 0.025,
    duration: float | None = None, free_edges: bool = False,
) -> list[dict]:
    text = normalize_transcript(transcript)
    symbols = text.replace(" ", "|")
    if any(character not in vocab for character in symbols):
        raise ValueError("Transcript contains a character outside the model vocabulary.")
    emissions = np.asarray(log_probs, dtype=np.float64)
    if emissions.ndim != 2 or not emissions.shape[0] or not np.isfinite(emissions).all():
        raise ValueError("Expected finite frame-by-token log probabilities.")
    if emissions.shape[0] > 5000 or len(symbols) > 1200:
        raise ValueError("Alignment exceeds the bounded frame/token limit.")
    if frame_hop <= 0 or frame_width <= 0 or (duration is not None and duration <= 0):
        raise ValueError("Alignment time scale must be positive.")
    if any(index < 0 or index >= emissions.shape[1] for index in [blank, *vocab.values()]):
        raise ValueError("Vocabulary index does not match emissions.")
    tokens = [vocab[symbol] for symbol in symbols]
    if blank in tokens:
        raise ValueError("Blank cannot appear in the transcript.")
    min_frames = len(tokens) + sum(a == b for a, b in zip(tokens, tokens[1:]))
    if min_frames > len(emissions):
        raise ValueError("Audio is too short to align this transcript.")
    labels = np.full(2 * len(tokens) + 1, blank, dtype=int)
    labels[1::2] = tokens
    skips = np.zeros(len(labels), dtype=bool)
    skips[2:] = (labels[2:] != blank) & (labels[2:] != labels[:-2])
    previous = np.full(len(labels), -np.inf)
    previous[0] = 0
    back = np.zeros((len(emissions), len(labels)), dtype=np.uint8)
    for frame, probabilities in enumerate(emissions):
        step_one = np.r_[-np.inf, previous[:-1]]
        step_two = np.r_[-np.inf, -np.inf, previous[:-2]]
        step_two[~skips] = -np.inf
        candidates = np.vstack([previous, step_one, step_two])
        hop = candidates.argmax(axis=0)
        scores = probabilities[labels].copy()
        if free_edges:
            scores[0] = scores[-1] = 0
        previous = candidates[hop, np.arange(len(labels))] + scores
        back[frame] = hop
    state = len(labels) - 2 + int(previous[-1] >= previous[-2])
    if not np.isfinite(previous[state]):
        raise ValueError("No complete CTC path exists for this transcript.")
    path = np.empty(len(emissions), dtype=np.int32)
    for frame in range(len(emissions) - 1, -1, -1):
        path[frame] = state
        state -= int(back[frame, state])
    words, char_cursor = [], 0
    for word in text.split():
        positions = []
        confidences = []
        for index in range(char_cursor, char_cursor + len(word)):
            frames = np.flatnonzero(path == 2 * index + 1)
            if not len(frames):
                raise ValueError("Incomplete character path.")
            positions.extend(frames.tolist())
            confidences.append(float(np.exp(emissions[frames, tokens[index]].mean())))
        start = min(positions) * frame_hop
        end = max(positions) * frame_hop + frame_width
        if duration is not None:
            end = min(end, duration)
        if end <= start:
            raise ValueError("Word interval lies outside the audio.")
        words.append({"word": word, "start": round(start, 5), "end": round(end, 5),
                      "confidence": round(float(np.mean(confidences)), 5)})
        char_cursor += len(word) + 1
    return words


class Aligner:
    """Loads only local, hash-verified safetensors; never downloads during use."""

    def __init__(self, model_path: Path | str = MODEL_PATH):
        from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
        import torch
        path = Path(model_path)
        weights = path / "model.safetensors"
        if not weights.is_file():
            raise ValueError("Run scripts/fetch_models.py before starting the app.")
        with weights.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != MODEL_SHA256:
            raise ValueError("Acoustic model checksum does not match the pinned revision.")
        torch.set_num_threads(2)
        self.processor = Wav2Vec2Processor.from_pretrained(path, local_files_only=True)
        self.model = Wav2Vec2ForCTC.from_pretrained(path, local_files_only=True, use_safetensors=True).eval()
        self.vocab = self.processor.tokenizer.get_vocab()
        self.blank = self.processor.tokenizer.pad_token_id
        self.hop = int(np.prod(self.model.config.conv_stride)) / SAMPLE_RATE
        width, stride = 1, 1
        for kernel, step in zip(self.model.config.conv_kernel, self.model.config.conv_stride):
            width += (kernel - 1) * stride
            stride *= step
        self.width = width / SAMPLE_RATE

    def emissions(self, audio: np.ndarray) -> tuple[np.ndarray, str, float]:
        import torch
        audio = np.asarray(audio, dtype=np.float32)
        if audio.ndim != 1 or len(audio) < SAMPLE_RATE // 2 or len(audio) > 90 * SAMPLE_RATE:
            raise ValueError("Expected 0.5 to 90 seconds of mono audio.")
        if not np.isfinite(audio).all():
            raise ValueError("Audio contains non-finite samples.")
        before = time.perf_counter()
        inputs = self.processor(audio, sampling_rate=SAMPLE_RATE, return_tensors="pt")
        with torch.inference_mode():
            logits = self.model(**inputs).logits[0]
            probabilities = logits.log_softmax(-1).cpu().numpy()
        decoded = self.processor.decode(logits.argmax(-1).tolist())
        return probabilities, decoded, time.perf_counter() - before

    def align(self, audio: np.ndarray, transcript: str, *, free_edges: bool = False) -> dict:
        transcript = normalize_transcript(transcript)
        probabilities, decoded, seconds = self.emissions(audio)
        words = align_emissions(probabilities, transcript, self.vocab, blank=self.blank,
                                frame_hop=self.hop, frame_width=self.width,
                                duration=len(audio) / SAMPLE_RATE, free_edges=free_edges)
        return {"words": words, "greedy_transcript": decoded, "inference_seconds": round(seconds, 4),
                "median_confidence": round(float(np.median([word["confidence"] for word in words])), 5),
                "emissions": probabilities}
