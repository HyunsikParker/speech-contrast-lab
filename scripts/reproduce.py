"""Read-only software replay; never converts the failed experiment into success."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from speechcontrast.audio import decode_audio
from speechcontrast.comparison import compare, RUBRIC_VERSION, THRESHOLDS


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / 'output/reproduction.json')
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'data/manifest.json').read_text())
    if manifest['thresholds'] != THRESHOLDS or manifest['rubric_version'] != RUBRIC_VERSION:
        raise ValueError('Published rubric does not match the implementation.')
    references = {}
    for reference in manifest['references']:
        path = ROOT / reference['audio']
        if sha(path) != reference['audio_sha256']:
            raise ValueError('Reference checksum mismatch.')
        references[reference['id']] = (reference, decode_audio(path, seconds=30))
    checks = []
    for example in manifest['examples']:
        path, recorded_path = ROOT / example['audio'], ROOT / example['analysis']
        if sha(path) != example['audio_sha256'] or sha(recorded_path) != example['analysis_sha256']:
            raise ValueError('Published waveform or analysis checksum mismatch.')
        recorded = json.loads(recorded_path.read_text())
        reference, audio = references[example['source_id']]
        actual = compare(audio, decode_audio(path, seconds=30), reference['words'], example['words'])
        same = all(actual[key] == recorded[key] for key in ['score', 'regions', 'words', 'reference_frames', 'delivery_frames', 'components'])
        checks.append({'id': example['id'], 'recorded_analysis_reproduced': same, 'score': actual['score']})
    result = {'reproduction_passed': all(c['recorded_analysis_reproduced'] for c in checks),
              'reproduced_examples': len(checks), 'experiment_gate_passed': manifest['gate_passed'],
              'scope': 'Read-only software reproduction of frozen recorded outputs. No new hypothesis, tuning, holdout result or official score.',
              'checks': checks}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({key: result[key] for key in ['reproduction_passed', 'reproduced_examples', 'experiment_gate_passed']}))
    return 0 if result['reproduction_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
