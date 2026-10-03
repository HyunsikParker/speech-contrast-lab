"""Fetch only pinned public checkpoints through the official HF CLI."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from speechcontrast.alignment import MODEL_REVISION, MODEL_SHA256
from speechcontrast.transcript import WHISPER_REVISION, WHISPER_SHA256


def main():
    cli = shutil.which('hf')
    if not cli:
        raise ValueError('The pinned huggingface_hub dependency supplies the official hf CLI. Activate the project environment first.')
    env = os.environ.copy()
    for name in ['HF_TOKEN', 'HUGGING_FACE_HUB_TOKEN', 'HF_ENDPOINT', 'HF_HUB_OFFLINE']:
        env.pop(name, None)
    env['HF_HUB_DISABLE_IMPLICIT_TOKEN'] = '1'
    models = [
        ('facebook/wav2vec2-base-960h', MODEL_REVISION, 'wav2vec2-base-960h', MODEL_SHA256,
         ['model.safetensors', 'config.json', 'preprocessor_config.json', 'vocab.json']),
        ('openai/whisper-base.en', WHISPER_REVISION, 'whisper-base-en', WHISPER_SHA256,
         ['model.safetensors', 'config.json', 'generation_config.json', 'preprocessor_config.json', 'vocab.json', 'merges.txt', 'normalizer.json']),
    ]
    for repo, revision, folder, expected, files in models:
        destination = ROOT / '.cache' / folder
        weights = destination / 'model.safetensors'
        verified = False
        if weights.is_file():
            with weights.open('rb') as stream:
                verified = hashlib.file_digest(stream, 'sha256').hexdigest() == expected
        if not verified or not all((destination / name).is_file() for name in files):
            subprocess.run([cli, 'download', repo, *files, '--revision', revision, '--local-dir', str(destination)],
                           env=env, check=True, timeout=900)
        with weights.open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if actual != expected:
            raise ValueError('Pinned weight checksum mismatch; the model will not be used.')
        print(f'{repo}: pinned weights verified; local inference only.')


if __name__ == '__main__':
    main()
