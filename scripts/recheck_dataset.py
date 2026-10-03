"""Bounded operational repair: reuse cached cropped-PCM word alignments.

No threshold change, model inference, waveform edit, or new blind-holdout claim.
The original manifest and analyses remain intact.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from speechcontrast.audio import decode_audio
from speechcontrast.v1.comparison import compare, THRESHOLDS


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(path, data, private=False):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    if private:
        path.chmod(0o600)


def iou(a, b):
    intersection = max(0, min(a['end'], b['end']) - max(a['start'], b['start']))
    return intersection / max(1e-8, max(a['end'], b['end']) - min(a['start'], b['start']))


def main():
    parser = argparse.ArgumentParser()
    for name in ['wait-for', 'ready', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    save(args.ready, {'pid': os.getpid(), 'status': 'waiting_for_run_receipt'}, True)
    wait = time.monotonic()
    while not args.wait_for.exists():
        if time.monotonic() - wait > 180:
            raise TimeoutError('No registered repair run.')
        time.sleep(0.2)
    started = time.perf_counter()
    manifest = copy.deepcopy(json.loads((ROOT / 'data/manifest-v1.json').read_text()))
    if manifest['thresholds'] != THRESHOLDS:
        raise ValueError('Frozen thresholds changed; replay is forbidden.')
    for ref in manifest['references']:
        null = next(e for e in manifest['examples'] if e['source_id'] == ref['id'] and e.get('control') == 'identical')
        analysis = json.loads((ROOT / null['analysis']).read_text())
        if digest(ROOT / null['audio']) != null['audio_sha256'] or digest(ROOT / null['analysis']) != null['analysis_sha256']:
            raise ValueError('Cached null artifact changed.')
        path = (ROOT / ref['audio']).with_name('corrected-reference.wav')
        shutil.copyfile(ROOT / null['audio'], path)
        ref.update({'audio': path.relative_to(ROOT).as_posix(), 'audio_sha256': digest(path),
                    'words': [row['delivery'] for row in analysis['words']],
                    'reference_repair': 'Exact cropped control PCM and its cached CTC alignment; no new inference.'})
    for example in manifest['examples']:
        ref = next(r for r in manifest['references'] if r['id'] == example['source_id'])
        if example['abstained']:
            continue
        if digest(ROOT / example['audio']) != example['audio_sha256']:
            raise ValueError('Paired waveform changed.')
        old = json.loads((ROOT / example['analysis']).read_text())
        result = compare(decode_audio(ROOT / ref['audio'], seconds=30),
                         decode_audio(ROOT / example['audio'], seconds=30),
                         ref['words'], [row['delivery'] for row in old['words']])
        result.update({'transcript': example['transcript'], 'verification': old['verification']})
        output = (ROOT / example['audio']).with_suffix('.corrected.analysis.json')
        save(output, result)
        overlap = max([iou(region, example['label']) for region in result['regions']
                       if region['kind'] == example['family']], default=0) if example['label'] else 0
        example.update({'analysis': output.relative_to(ROOT).as_posix(), 'analysis_sha256': digest(output),
                        'score': result['score'], 'targeted_hit': overlap >= 0.25, 'max_target_iou': round(overlap, 5),
                        'regions': [{k: r[k] for k in ['kind', 'start', 'end', 'words']} for r in result['regions']]})
    strong = [e for e in manifest['examples'] if e['level'] >= 2]
    near = [e for e in manifest['examples'] if e['level'] == 1]
    controls = [e for e in manifest['examples'] if e['family'] == 'control']
    metrics = {**manifest['metrics'],
               'moderate_severe_targeted_hit_fraction': sum(e['targeted_hit'] for e in strong) / len(strong),
               'near_perfect_targeted_hit_fraction': sum(e['targeted_hit'] for e in near) / len(near),
               'control_false_alerts': sum(bool(e['regions']) for e in controls),
               'reference_null_exact': int(all(e['score'] == 100 and not e['regions'] for e in controls if e['control'] == 'identical')),
               'repair_elapsed_s': round(time.perf_counter() - started, 4)}
    # The source speaker was unseen only in v1. Never rename this repair replay
    # as a fresh blind generalization evaluation.
    holdout = [e for e in strong if e['split'] == 'unseen_speaker_holdout']
    metrics.pop('unseen_speaker_moderate_severe_hit_fraction')
    metrics['previous_holdout_replay_hit_fraction'] = sum(e['targeted_hit'] for e in holdout) / len(holdout)
    passed = (metrics['moderate_severe_targeted_hit_fraction'] >= 0.75 and metrics['control_false_alerts'] <= 1
              and metrics['control_scored_fraction'] == 1 and metrics['reference_null_exact'] == 1
              and metrics['repair_elapsed_s'] <= 60)
    manifest.update({'metrics': metrics, 'gate_passed': passed, 'artifact_version': 'v1-operational-repair',
                     'original_manifest_sha256': digest(ROOT / 'data/manifest-v1.json'),
                     'evaluation_kind': 'Frozen-threshold repair replay, not a fresh holdout.',
                     'initial_failure_preserved': True})
    save(ROOT / 'data/manifest.json', manifest)
    save(args.output, {'gate_passed': passed, 'metrics': metrics,
                       'manifest_sha256': digest(ROOT / 'data/manifest.json'),
                       'original_manifest_sha256': manifest['original_manifest_sha256'],
                       'evaluation_kind': manifest['evaluation_kind']}, True)
    print(json.dumps({'gate_passed': passed, 'metrics': metrics}), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
