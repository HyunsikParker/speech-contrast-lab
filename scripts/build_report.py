"""Six-page monochrome technical document from the measured artifact manifest."""

from __future__ import annotations

from html import escape
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'output/pdf/Speech-Contrast-Lab-Technical-Report.pdf'
WIDTH, HEIGHT = A4
styles = {
    'title': ParagraphStyle('title', fontName='Helvetica-Bold', fontSize=25, leading=29, spaceAfter=10, textColor=colors.HexColor('#202020')),
    'subtitle': ParagraphStyle('subtitle', fontName='Helvetica', fontSize=11, leading=16, spaceAfter=19, textColor=colors.HexColor('#555555')),
    'h1': ParagraphStyle('h1', fontName='Helvetica-Bold', fontSize=18, leading=23, spaceAfter=15),
    'h2': ParagraphStyle('h2', fontName='Helvetica-Bold', fontSize=11, leading=16, spaceBefore=13, spaceAfter=6),
    'body': ParagraphStyle('body', fontName='Helvetica', fontSize=9.6, leading=14.2, spaceAfter=9, alignment=TA_LEFT),
    'small': ParagraphStyle('small', fontName='Helvetica', fontSize=8.2, leading=11.7, spaceAfter=7, textColor=colors.HexColor('#555555')),
    'code': ParagraphStyle('code', fontName='Courier', fontSize=8, leading=12, spaceAfter=7),
    'cell': ParagraphStyle('cell', fontName='Helvetica', fontSize=8.7, leading=12),
    'head': ParagraphStyle('head', fontName='Helvetica-Bold', fontSize=8.5, leading=12),
}


def p(text, kind='body'):
    return Paragraph(text, styles[kind])


def table(headers, rows, widths):
    data = [[p(escape(str(value)), 'head') for value in headers]]
    data += [[p(escape(str(value)), 'cell') for value in row] for row in rows]
    t = Table(data, colWidths=widths, repeatRows=1, hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ededed')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LINEBELOW', (0, 0), (-1, -1), 0.35, colors.HexColor('#cccccc')),
    ]))
    return t


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor('#cccccc'))
    canvas.line(46, 38, WIDTH - 46, 38)
    canvas.setFont('Helvetica', 7.5)
    canvas.setFillColor(colors.HexColor('#666666'))
    canvas.drawString(46, 25, 'Speech Contrast Lab | Technical report | 3 October 2026')
    canvas.drawRightString(WIDTH - 46, 25, f'{doc.page} / 6')
    canvas.restoreState()


def main():
    manifest = json.loads((ROOT / 'data/manifest.json').read_text())
    metrics = manifest['metrics']
    strong = [e for e in manifest['examples'] if e['level'] >= 2]
    near = [e for e in manifest['examples'] if e['level'] == 1]
    controls = [e for e in manifest['examples'] if e['family'] == 'control']
    hits = sum(e['targeted_hit'] for e in strong)
    false_controls = sum(bool(e['regions']) for e in controls)
    story = []
    story += [p('Speech Contrast Lab', 'title'), p('Contrastive speech analytics and temporal grounding<br/>Multimodal AI Hackathon 2026 - Track C', 'subtitle')]
    story += [p('A reference-conditioned measurement tool', 'h2'), p('The app compares two recordings of the same English transcript. It estimates word times, measures acoustic differences and links each warning to a replayable interval. Its score describes similarity to a chosen reference; it is not a universal judgment of delivery quality, accent or persuasiveness.')]
    story += [p('What is implemented', 'h2'), p('A local upload workflow, two-source contrastive dataset, frozen transcript verification and forced alignment, deterministic acoustic features, interactive overlays, interval playback, word-level evidence and JSON export. All inference is local. No model training or paid API is used.')]
    story += [table(['Measured artifact', 'Observed result'], [
        ['Paired recordings', '34: 24 gradient edits, 6 normalization controls, 4 new noise realizations'],
        ['Moderate / strong target hits', f'{hits}/{len(strong)} ({100 * hits / len(strong):.1f}%), matching family at IoU >=0.25'],
        ['Near-perfect target hits', f'{sum(e["targeted_hit"] for e in near)}/{len(near)}'],
        ['Controls with false alerts', f'{false_controls}/{len(controls)}; all controls received scores'],
        ['Independent transcript checks', 'No abstentions on the final dataset; baseline agreement >=97.8%'],
        ['Final evaluation runtime', f'{metrics["elapsed_s"]:.2f}s; peak resident {metrics["peak_resident_bytes"] / 2**30:.2f}GiB on CPU'],
    ], [175, 328])]
    story += [Spacer(1, 12), p('<b>Validation status: target not met.</b> The preregistered v2 target was at least 93% moderate/strong target hits and zero alerting controls. The experiment was recorded as a scientific failure. This document reports its measurements without treating them as a passed benchmark or an official contest score.')]
    story += [p('Track C asks for a same-text good/bad spectrum, temporal labels, feature extraction, a functional dashboard and reproducible scoring. This prototype addresses those deliverables while making its small sample and detection failures visible. [1]', 'small'), PageBreak()]

    story += [p('1. Dataset construction and rights', 'h1')]
    story += [p('Source selection', 'h2'), p('The reference clips come from official archived weekly addresses by Barack Obama (11 July 2009) and Joe Biden (28 May 2011). The corresponding archive video pages explicitly label the recordings Public Domain. Official transcripts supply the text; a frozen independent recognizer checks whether the audio supports it. Prominent public speech is a useful reference, not proof of a universally ideal delivery. [2,3]')]
    story += [table(['Reference', 'Text / audio excerpt'], [
        ['Obama - development', 'Opening two sentences; 46 aligned words; source window 0-30s'],
        ['Biden - initial unseen speaker', 'Opening three sentences; 21 aligned words; source window 0-30s'],
    ], [175, 328])]
    story += [p('Same-text gradient', 'h2'), p('The local edit span covers words 4-9 (zero-based). A pause is inserted before word 7. Every edit retains the original spoken words. The reference peak is capped at 0.5 before editing, with the gain recorded to leave headroom. The pipeline refuses clipping rather than silently renormalizing a corrupted variant.')]
    story += [table(['Family', 'Near-perfect', 'Moderate', 'Strong'], [
        ['Local pacing', 'duration x1.08', 'duration x1.40', 'duration x2.10'],
        ['Inserted pause', '+0.12s', '+0.40s', '+0.95s'],
        ['Local amplitude', 'gain x0.85', 'gain x0.50', 'gain x0.22'],
        ['Added white noise', '25dB SNR', '15dB SNR', '5dB SNR'],
    ], [143, 120, 120, 120])]
    story += [p('Tempo changes use pitch-preserving FFmpeg atempo filters. White noise uses a fixed NumPy generator seed and measured segment RMS. Six controls test identical audio, global gain x0.5 and global pitch x1.15. Four later noise files use frozen SNR values 20 and 8dB with a new seed; they are unseen perturbations on known voices, not a new speaker holdout.')]
    story += [p('Two annotation layers', 'h2'), p('<b>Exact DSP labels:</b> sample-bounded edit intervals, parameters and piecewise time maps. <b>Silver alignment:</b> model-estimated word starts, ends and token probabilities. These labels are stored separately. No manually verified absolute word-timing accuracy is claimed.')]
    story += [p('Raw full speeches are excluded from the repository. The paired clips, transcripts, alignment records, source URLs, raw-file checksums and final audio SHA-256 values are included. Earlier failures and the corrected reference artifacts remain available for audit.', 'small'), PageBreak()]

    story += [p('2. Transcript support and alignment', 'h1')]
    story += [p('Why two frozen models', 'h2'), p('The first CTC-only feasibility test failed its exact-word agreement threshold: greedy agreement was 88.889%, below 90%, despite good time-map equivariance. An independent autoregressive recognizer then supplied the transcript check; CTC supplies the word path. The old failure remains recorded. Model weights are local safetensors, pinned by revision and SHA-256. No remote inference or fine-tuning is performed.')]
    story += [table(['Role', 'Pinned model / revision'], [
        ['Transcript verification', 'openai/whisper-base.en\n911407f4214e0e1d82085af863093ec0b66f9cd6'],
        ['Word timing', 'facebook/wav2vec2-base-960h\n22aad52d435eb6dbaf354bdad9b0da84ce7d6156'],
    ], [150, 353])]
    story += [p('Both checkpoints are Apache-2.0. Combined weight size is 668,009,789 bytes. The application verifies the exact weight hashes before loading, uses local_files_only and eval/inference mode, and limits Torch to two CPU threads. [4,5]', 'small')]
    story += [p('Text gate and abstention', 'h2'), p('Normalize case and punctuation while preserving apostrophes. The recognizer must reach at least 90% word agreement against the full supplied transcript in each uploaded recording. Unsupported text receives no score. Users must spell numbers as spoken words. Recognition agreement is a textual-support check, not a guarantee that every word was spoken exactly as written.')]
    story += [p('Blank-aware CTC Viterbi path', 'h2'), p('Insert blank states around transcript tokens, allow stay/advance transitions, and allow a two-state skip only when the destination token is nonblank and differs from the previous token. This prevents repeated letters from collapsing. Backtracking yields character frames; word times span the first and last assigned character frames.')]
    story += [p('CTC frame hop = 0.020s; receptive width = 0.025s.<br/>Word start = first character frame x hop.<br/>Word end = last character frame x hop + receptive width.', 'code')]
    story += [p('Model-emitted token probabilities are used only as an acoustic support floor (0.15), not calibrated timing confidence. Low-support words do not generate alerts. Cached emissions replay is deterministic. The feasibility test checked silence/dilation time-map equivariance, with median 0.00013s and p95 0.00925s; this was not a manually labeled absolute timing benchmark.')]
    story += [p('Reference-crop defect and repair', 'h2'), p('The first paired evaluation offset full-recording word times onto a cropped reference while re-aligning the delivery crop. A 10ms mask difference produced a false 4.2851dB energy delta on identical content. The repair uses the actual cropped PCM and its alignment on both sides. Exact null controls then score 100 with no regions. The original result is preserved.'), PageBreak()]

    story += [p('3. Acoustic features and scoring', 'h1')]
    story += [p('Feature frames', 'h2'), p('Decode mono audio at 16kHz. Use 400-sample (25ms) frames with 160-sample (10ms) hop, a Hann window and a 512-point FFT. Compute RMS, relative energy, spectral flatness, spectral centroid, 13 MFCC coefficients and autocorrelation F0. The 26 triangular mel bands span 80-7600Hz; discard MFCC coefficient zero so diagnostic MFCC distance does not duplicate overall energy.')]
    story += [p('Speaker-relative measurements', 'h2'), p('Energy is referenced to each recording\'s active-frame median dB. Word energy pools linear power before taking a logarithm to reduce frame-mask median flips. Pitch is expressed in semitones relative to the recording\'s voiced median. F0 uses a local autocorrelation peak in 60-400Hz with periodicity at least 0.6. This is a simple estimator, especially uncertain on short/unvoiced frames; pitch and MFCC distance are displayed as diagnostics, not separate scoring penalties.')]
    story += [p('relative_energy = 10*log10(mean(word_frame_RMS^2))<br/>                  - median(active_frame_energy_dB)<br/>relative_pitch = 12*log2(F0 / median(voiced_F0))<br/>flatness_ratio = 10*log10(max(delivery_flatness,1e-6)<br/>                         / max(reference_flatness,1e-6))', 'code')]
    story += [table(['Alert family', 'Fixed rule', 'Weight'], [
        ['Pace', 'word duration ratio >1.25 or <0.75, AND absolute duration delta >0.08s', '35'],
        ['Pause', 'gap before the matching word exceeds reference by >0.20s', '25'],
        ['Relative volume', 'absolute speaker-relative word energy delta >3dB', '25'],
        ['Spectral noise', 'flatness ratio >12dB AND periodicity loss >0.06', '15'],
    ], [100, 350, 53])]
    story += [p('Temporal and causal evidence', 'h2'), p('Adjacent word detections of one family merge into a delivery-time region. Pause regions span the actual gap. Each region retains per-word measurements, baseline values and an explanation; selecting it seeks and plays the real interval. Added noise is described as compatible with spectral changes, not established causation: microphones and recording conditions can also cause them.')]
    story += [p('score = 100 - sum(family_penalty)<br/>family_penalty = weight * min(1,<br/>  0.75*max(detected_severity)<br/>  + 0.25*sum(detected_severity)/total_words)', 'code')]
    story += [p('Pace severity is |ln(duration_ratio)|/ln(2); volume is |delta_dB|/12; pause is extra_gap/0.9; spectral noise is max((flatness_ratio_dB-12)/24, periodicity_loss). Clamp each to [0,1]. The score is reproducible reference similarity, not a rhetorical rank. It need not decrease monotonically with every edit.', 'small'), PageBreak()]

    story += [p('4. Evaluation, including failures', 'h1')]
    story += [p('Protocol and denominators', 'h2'), p('Freeze the edit recipes, thresholds, implementation hashes and validation targets before each bounded run. A target hit requires the correct alert family and delivery-time interval IoU >=0.25 with the exact edit interval. An abstention counts as a miss. Every control is checked for any alert; near-perfect edits have a separate denominator and no guaranteed hit target.')]
    story += [table(['Evaluation', 'Target hits', 'False-alert controls', 'Disposition'], [
        ['v1 original', '12/16 (75.0%)', '3/6', 'Operational failure: crop fixture'],
        ['v1 frozen repair replay', '12/16 (75.0%)', '1/6', 'Repair gate passed; not new blind data'],
        ['v2 power + spectral ratio', f'{hits}/{len(strong)} (88.9%)', f'{false_controls}/6', 'Scientific failure: strict target missed'],
    ], [142, 103, 115, 143])]
    story += [p('The second speaker was unseen only in the first v1 evaluation. The crop repair and v2 reuse known examples and are not fresh speaker-generalization tests. V2 adds four previously ungenerated noise realizations on those known speakers; both strong new files were detected, while both near-perfect new files were missed.')]
    story += [p('What failed in the final version', 'h2'), p('The two original Biden noise edits at 15 and 5dB SNR did not produce a matching spectral-noise region at IoU >=0.25. The Obama global-pitch control produced a relative-volume alert. Near-perfect target regions were missed in all ten cases. The custom score was also nonmonotonic for some noise levels because alignment and several acoustic penalties changed together.')]
    story += [p('These are visible in the dashboard\'s full results table, not removed as outliers. The strict v2 hypothesis (>=93% targeted hits; no control alerts) was recorded as falsified and its mechanism stopped. The implementation remains a usable measurement prototype; it is not presented as a validated general-purpose speech judge.')]
    story += [p('Verification beyond the experiment', 'h2'), p('Software checks cover repeated-letter alignment, text rejection, global-gain invariance, known F0 normalization, local-energy grounding, audio-duration rejection, loopback Host/Origin protection, path traversal, byte-range seeking, serialized uploads, private temporary permissions and cleanup before response. Browser checks cover the interactive surface separately. Passing software tests does not turn a failed acoustic hypothesis into success.')]
    story += [p('Limited scope', 'h2'), p('Two English public-speech clips and synthetic edits do not establish performance across accents, demographics, natural rhetorical styles or recording devices. There is no learned rubric and no claim of personality, emotion or intent inference. Absolute word-time accuracy has not been manually scored. No official contest score, award or payout has been received.'), PageBreak()]

    story += [p('5. Run locally and inspect the evidence', 'h1')]
    story += [p('Reproduction', 'h2'), p('The repository carries the paired WAVs, source metadata, exact edit labels, cached word alignments, versioned analysis JSON and frozen protocols. Recompute the published analyses with the pinned Python dependencies; this is a read-only software reproduction check, not a new blind experiment. Interactive examples do not require downloading the model weights.')]
    story += [p('python3 -m venv .venv<br/>source .venv/bin/activate<br/>python3 -m pip install -r requirements.txt<br/>python3 scripts/reproduce.py --output output/reproduction.json<br/>pnpm install --frozen-lockfile<br/>pnpm build<br/>python3 server.py --port 5276', 'code')]
    story += [p('For new uploads, fetch the two pinned Apache-2.0 checkpoints once with scripts/fetch_models.py. Node >=22.19, pnpm 12.8.1, Python 3.13 and FFmpeg are required. The verified local build used Node 22.23.3. Model inference uses only the local, checksum-verified safetensors.')]
    story += [p('Upload handling', 'h2'), p('The server binds only 127.0.0.1. Each input is limited to 8MB and 0.5-30s; accepted formats are WAV, MP3, FLAC, OGG and WebM. JSON requests are bounded, compute is serialized, external-origin requests are rejected and the child process has a 90s timeout. FFmpeg accepts only local file/pipe protocols and bounded audio/container formats. Temporary directories use mode 0700 and files 0600; audio, transcript and child output are deleted before the HTTP result is sent.')]
    story += [p('AI assistance and licenses', 'h2'), p('OpenAI Codex assisted with implementation, tests and documentation. That assistance is also disclosed in the README and must be listed in Built With at submission. Model checkpoints are Apache-2.0; the source recordings are explicitly Public Domain. Project code is MIT. No personal accounts, keys or raw full-speech files are included.')]
    story += [p('Primary references', 'h2')]
    refs = [
        ('1', 'Track C challenge brief', 'https://drive.google.com/file/d/1ewVNqeGBcg76GUUvoj0buPWueQrgDf_6/view'),
        ('2', 'Obama archive video and Public Domain label', 'https://obamawhitehouse.archives.gov/video/Weekly-Address-Recovery-and-the-Jobs-of-the-Future/index__q_page=1.html'),
        ('3', 'Biden archive video and Public Domain label', 'https://obamawhitehouse.archives.gov/photos-and-video/video/2011/05/28/weekly-address-biden-american-auto-comeback'),
        ('4', 'Wav2Vec2 checkpoint and license', 'https://huggingface.co/facebook/wav2vec2-base-960h'),
        ('5', 'Whisper checkpoint and license', 'https://huggingface.co/openai/whisper-base.en'),
    ]
    for number, label, url in refs:
        story.append(p(f'[{number}] <link href="{escape(url, quote=True)}">{escape(label)}</link> - {escape(url)}', 'small'))
    story += [p('Source transcript URLs, exact revision hashes and the complete per-pair results are in data/sources.json, data/manifest.json and the versioned protocol files.', 'small')]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUTPUT), pagesize=A4, rightMargin=46, leftMargin=46, topMargin=42, bottomMargin=52,
                            title='Speech Contrast Lab - Track C Technical Report', author='Speech Contrast Lab', pageCompression=1)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(str(OUTPUT))


if __name__ == '__main__':
    main()
