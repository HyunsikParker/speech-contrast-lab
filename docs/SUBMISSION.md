# Submission copy

## Name

Speech Contrast Lab

## Tagline

Compare the same words, locate acoustic differences and replay the evidence.

## About the project

Speech feedback often points to a whole performance: too slow, too quiet, too
many pauses. Speech Contrast Lab makes a narrower claim. It compares two
recordings of the same text, shows where their acoustics differ, and lets the
speaker hear the interval behind each alert.

The dataset starts with short, public-domain weekly addresses by Barack Obama
and Joe Biden. Local tempo changes, inserted silence, volume dips and added noise
produce three edit levels per family. Unchanged audio, global-volume and
global-pitch controls test whether normalization prevents obvious false alarms.
There are 34 pairs, with transcripts, waveform hashes, edit intervals and frozen
word-alignment estimates included in the repository.

The dashboard accepts two audio files and a shared English transcript. Frozen
Whisper checks the words before wav2vec2 CTC alignment estimates their times.
FFT, MFCCs, autocorrelation pitch, relative energy, durations and gaps feed a
fixed four-part rubric. Every alert contains a numerical explanation, word
context and a button that replays the actual delivery interval. No audio goes
to a hosted model service.

An early identical-audio false alarm exposed a crop/frame-origin mismatch. The
reference fixture was repaired, and the original failure was preserved. The
published v2 stress test located 16 of 18 moderate/strong target regions, missed
all ten near-perfect targets, and raised one false alert among six controls.
It failed the predeclared gate of at least 93% target hits and zero control false
alerts. The interface shows the misses, controls and failed gate alongside the
successful examples.

All 34 recorded analyses reproduce exactly from their frozen word times. That
is a software-replay result, not evidence that the failed gate passed. Two
speakers and synthetic edits also cannot establish broad rhetorical or
cross-speaker validity. The score means acoustic similarity to the chosen
reference, not persuasiveness or speaking ability.

The prototype runs locally with pinned dependencies, public model checkpoints
and no paid API. The six-page report documents construction, equations, score
weights and evaluation. The demo shows the source-to-pair process, contrasting
edit levels, grounded playback, upload analysis and the known failure cases.

## Built With

Python, NumPy, SciPy, PyTorch, Transformers, Hugging Face, Whisper, wav2vec2,
FFmpeg, React, Vite, OpenAI Codex.

## AI assistance

OpenAI Codex assisted with implementation, tests, documentation and demo assembly.
The project uses frozen pretrained Whisper and wav2vec2 models; neither was
trained or fine-tuned for this entry. Model times are identified as estimates,
and failed validation results have not been removed.
