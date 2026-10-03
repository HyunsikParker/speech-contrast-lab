"""One bounded spectral-ratio evaluation with four frozen new perturbations."""

from __future__ import annotations

import argparse
import copy
import gc
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from speechcontrast.alignment import Aligner
from speechcontrast.audio import decode_audio, write_wav
from speechcontrast.comparison import compare, RUBRIC_VERSION, THRESHOLDS
from speechcontrast.perturbations import inject
from speechcontrast.transcript import TranscriptVerifier


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(p, data, private=False):
    p.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')
    if private:
        p.chmod(0o600)


def iou(a, b):
    overlap = max(0, min(a['end'], b['end']) - max(a['start'], b['start']))
    return overlap / max(1e-8, max(a['end'], b['end']) - min(a['start'], b['start']))


def main():
    parser = argparse.ArgumentParser()
    for name in ['wait-for', 'ready', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    save(args.ready, {'pid': os.getpid(), 'status': 'waiting_for_run_receipt'}, True)
    wait = time.monotonic()
    while not args.wait_for.exists():
        if time.monotonic() - wait > 180:
            raise TimeoutError('No registered v2 run.')
        time.sleep(0.2)
    started = time.perf_counter()
    try:
        protocol = json.loads((ROOT / 'data/protocol-v2.json').read_text())
        old_path = ROOT / protocol['source_manifest']
        if digest(old_path) != protocol['source_manifest_sha256']:
            raise ValueError('Frozen input manifest changed.')
        manifest = copy.deepcopy(json.loads(old_path.read_text()))
        save(ROOT / 'data/manifest-repair-v1.json', manifest)
        fresh = []
        recipe = protocol['fresh_perturbations']
        for reference in manifest['references']:
            audio = decode_audio(ROOT / reference['audio'], seconds=30)
            first, last = recipe['target_word_indices']
            start, end = reference['words'][first]['start'], reference['words'][last]['end']
            for snr in recipe['snr_db']:
                waveform, label = inject(audio, 'roughness', snr, start, end, seed=recipe['seed'] + snr)
                path = (ROOT / reference['audio']).with_name(f'fresh-noise-snr-{snr}.wav')
                write_wav(path, waveform)
                fresh.append({'id': f"{reference['id']}-fresh-noise-{snr}", 'source_id': reference['id'],
                              'split': 'unseen_perturbation_known_speaker', 'transcript': reference['transcript'],
                              'family': 'roughness', 'level': 1 if snr == 20 else 3, 'fresh_perturbation': True,
                              'audio': path.relative_to(ROOT).as_posix(), 'audio_sha256': digest(path), 'label': label})
        verifier = TranscriptVerifier()
        for example in fresh:
            example['verification'] = verifier.verify(decode_audio(ROOT / example['audio'], seconds=30), example['transcript'])
        del verifier
        gc.collect()
        aligner = Aligner()
        for example in fresh:
            if example['verification']['word_agreement'] < THRESHOLDS['transcript_agreement_min']:
                example.update({'abstained': True, 'abstention_reason': 'Independent transcript support below0.90.',
                                'score': None, 'regions': [], 'targeted_hit': False, 'max_target_iou': 0})
                continue
            aligned = aligner.align(decode_audio(ROOT / example['audio'], seconds=30), example['transcript'])
            example.update({'words': aligned['words'], 'abstained': False})
        del aligner
        gc.collect()
        examples = manifest['examples'] + fresh
        for example in examples:
            if example['abstained']:
                continue
            ref = next(r for r in manifest['references'] if r['id'] == example['source_id'])
            if digest(ROOT / example['audio']) != example['audio_sha256']:
                raise ValueError('Input waveform changed.')
            result = compare(decode_audio(ROOT / ref['audio'], seconds=30),
                             decode_audio(ROOT / example['audio'], seconds=30), ref['words'], example['words'])
            result.update({'transcript': example['transcript'],
                           'verification': {'reference': ref['verification'], 'delivery': example['verification']}})
            path = (ROOT / example['audio']).with_suffix('.v2.analysis.json')
            save(path, result)
            overlap = max([iou(region, example['label']) for region in result['regions']
                           if region['kind'] == example['family']], default=0) if example['label'] else 0
            example.update({'analysis': path.relative_to(ROOT).as_posix(), 'analysis_sha256': digest(path),
                            'score': result['score'], 'targeted_hit': overlap >= 0.25, 'max_target_iou': round(overlap, 5),
                            'regions': [{k: r[k] for k in ['kind', 'start', 'end', 'words']} for r in result['regions']]})
            print(json.dumps({'example': example['id'], 'score': example['score'], 'targeted_hit': example['targeted_hit'],
                              'regions': len(example['regions'])}), flush=True)
        controls = [e for e in examples if e['family'] == 'control']
        strong = [e for e in examples if e['level'] >= 2]
        near = [e for e in examples if e['level'] == 1]
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024)
        metrics = {'examples': len(examples), 'moderate_severe_targeted_hit_fraction': sum(e['targeted_hit'] for e in strong) / len(strong),
                   'near_perfect_targeted_hit_fraction': sum(e['targeted_hit'] for e in near) / len(near),
                   'fresh_strong_perturbation_hits': sum(e['targeted_hit'] for e in fresh if e['level'] >= 2),
                   'fresh_near_perfect_perturbation_hits': sum(e['targeted_hit'] for e in fresh if e['level'] == 1),
                   'control_false_alerts': sum(bool(e['regions']) for e in controls),
                   'control_scored_fraction': sum(not e['abstained'] for e in controls) / len(controls),
                   'abstentions': sum(e['abstained'] for e in examples), 'reference_null_exact': int(all(e['score'] == 100 for e in controls if e['control'] == 'identical')),
                   'peak_resident_bytes': peak, 'elapsed_s': round(time.perf_counter() - started, 4)}
        gate = protocol['success_gate']
        passed = (metrics['examples'] == gate['examples'] and metrics['moderate_severe_targeted_hit_fraction'] >= gate['moderate_severe_targeted_hit_fraction']
                  and metrics['fresh_strong_perturbation_hits'] == gate['fresh_strong_perturbation_hits']
                  and metrics['control_false_alerts'] == gate['control_false_alerts'] and metrics['control_scored_fraction'] == 1
                  and metrics['reference_null_exact'] == 1 and peak <= gate['maximum_peak_resident_bytes'] and metrics['elapsed_s'] <= gate['maximum_wall_seconds'])
        manifest.update({'protocol_id': protocol['protocol_id'], 'protocol_sha256': digest(ROOT / 'data/protocol-v2.json'),
                         'rubric_version': RUBRIC_VERSION, 'thresholds': THRESHOLDS, 'examples': examples, 'metrics': metrics,
                         'gate_passed': passed, 'evaluation_kind': '30known-example replay plus4unseen perturbations on known speakers.',
                         'artifact_version': 'v2', 'initial_failure_preserved': True})
        save(ROOT / 'data/manifest-v2.json', manifest)
        if passed:
            save(ROOT / 'data/manifest.json', manifest)
        save(args.output, {'gate_passed': passed, 'metrics': metrics, 'manifest_sha256': digest(ROOT / 'data/manifest-v2.json'),
                           'protocol_sha256': manifest['protocol_sha256'], 'evaluation_kind': manifest['evaluation_kind']}, True)
        print(json.dumps({'gate_passed': passed, 'metrics': metrics}), flush=True)
        return 0 if passed else 1
    except Exception as error:
        save(args.output, {'gate_passed': False, 'failure_class': 'operational', 'error_type': type(error).__name__,
                           'error_message': str(error)[:300], 'metrics': {'elapsed_s': round(time.perf_counter() - started, 4)}}, True)
        raise


if __name__ == '__main__':
    raise SystemExit(main())
