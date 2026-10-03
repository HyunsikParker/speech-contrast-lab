"""Build an edited functional walkthrough from actual prototype captures.

No interface state is synthesized. Capture sequences are sampled at 1–2 fps;
still-analysis scenes are labeled separately from live playback sequences.
Source captures live under output/video/captures and are not runtime assets.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import wave

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/video'
CAPTURES = OUT / 'captures'
WIDTH, HEIGHT = 1440, 1080
FONT_PATHS = [Path('/System/Library/Fonts/Supplemental/Arial.ttf'),
              Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
FONT = next((p for p in FONT_PATHS if p.is_file()), None)
if FONT is None:
    raise RuntimeError('Install an Arial-compatible or DejaVu Sans font before rendering the demo.')


def font(size):
    return ImageFont.truetype(str(FONT), size)


def wrap(text, face, max_width):
    draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    lines, current = [], ''
    for word in text.split():
        candidate = f'{current} {word}'.strip()
        if draw.textlength(candidate, font=face) > max_width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def card(kind):
    result = Image.new('RGB', (WIDTH, 900), 'white')
    d = ImageDraw.Draw(result)
    titles = {'intro': 'Compare the same words. Hear the difference.',
              'dataset': 'From a public speech to a labeled pair',
              'reproduce': 'Recorded checks, with the failure preserved',
              'close': 'Speech Contrast Lab'}
    title_lines = wrap(titles[kind], font(48), WIDTH - 128)
    for i, line in enumerate(title_lines):
        d.text((64, 60 + i * 58), line, font=font(48), fill='#222')
    if kind == 'intro':
        paragraphs = [
            'Track C · Multimodal AI Hackathon 2026',
            'Two recordings. One shared transcript. Local acoustic evidence.',
            'Upload audio, compare word-aligned features, then replay each alert.',
            'Edited walkthrough: actual interface captures and published audio.',
            'Playback sequences are sampled at 1–2 frames per second.'
        ]
        for i, text in enumerate(paragraphs):
            d.text((64, 240 + i * 98), text, font=font(32), fill='#444')
    elif kind == 'dataset':
        d.text((64, 145), 'Public-domain weekly addresses · Obama (2009) / Biden (2011)', font=font(30), fill='#444')
        d.text((64, 192), 'Crop → 16 kHz mono PCM → exact local edit → frozen alignment estimates', font=font(30), fill='#444')
        rows = [
            ['Edit family', 'Near-perfect', 'Moderate', 'Strong'],
            ['Tempo request', '1.08×', '1.40×', '2.10×'],
            ['Inserted pause', '0.12 s', '0.40 s', '0.95 s'],
            ['Local amplitude', '×0.85', '×0.50', '×0.22'],
            ['White-noise SNR', '25 dB', '15 dB', '5 dB'],
        ]
        columns = [64, 448, 790, 1100]
        for i, row in enumerate(rows):
            y = 295 + i * 76
            if i == 0:
                d.rectangle((52, y - 12, WIDTH - 52, y + 55), fill='#eee')
            for x, value in zip(columns, row):
                d.text((x, y), value, font=font(30), fill='#222')
            d.line((52, y + 60, WIDTH - 52, y + 60), fill='#ddd', width=1)
        d.text((64, 720), '24 original edits + 6 normalization controls + 4 new noise edits = 34 pairs', font=font(30), fill='#333')
        d.text((64, 778), 'Edit intervals: exact PCM labels. Word intervals: unreviewed model estimates.', font=font(27), fill='#555')
    elif kind == 'reproduce':
        rows = [
            ('34 / 34', 'Frozen analyses reproduced exactly; no new neural inference'),
            ('20 + 2', 'Python and JavaScript tests passed'),
            ('0', 'Dependency audit advisories'),
            ('6 pages', 'Technical report: dataset, equations, scoring and evaluation'),
            ('Failed', 'The predeclared v2 validation gate remains failed'),
        ]
        for i, (number, label) in enumerate(rows):
            y = 175 + i * 126
            d.text((64, y), number, font=font(40), fill='#222')
            for j, line in enumerate(wrap(label, font(29), 1020)):
                d.text((350, y + j * 37), line, font=font(29), fill='#444')
            d.line((64, y + 95, WIDTH - 64, y + 95), fill='#ddd', width=1)
    else:
        paragraphs = [
            'Local prototype · pinned models · no paid API or training',
            'Reference similarity is not persuasiveness or an official contest score.',
            'Code, paired audio, labels and the six-page report are in the repository.',
            'OpenAI Codex assisted with code, tests, documentation and demo assembly.',
        ]
        for i, text in enumerate(paragraphs):
            for j, line in enumerate(wrap(text, font(32), WIDTH - 128)):
                d.text((64, 230 + i * 140 + j * 40), line, font=font(32), fill='#444')
    return result


def sequence(prefix, count, fps):
    return {'prefix': prefix, 'count': count, 'fps': fps}


def still(filename):
    return {'image': filename}


def scenes():
    obama = 'data/examples/obama-weekly-20090711/'
    biden = 'data/examples/biden-weekly-20110528/'
    return [
        {'title': 'What the prototype does', 'duration': 10, 'card': 'intro', 'captions': [
            (0, 5, 'Compare recordings of the same text. Locate acoustic differences and hear the evidence.'),
            (5, 10, 'This is an edited functional walkthrough, not a continuous screen recording.') ]},
        {'title': 'Dataset construction', 'duration': 22, 'card': 'dataset', 'captions': [
            (0, 7, 'Two short public-domain weekly addresses supply the reference audio and official transcripts.'),
            (7, 14, 'Three fixed edit levels preserve the same words while changing pace, pauses, local volume or noise.'),
            (14, 22, 'Hashes, actual sample boundaries and time maps accompany each pair. Word times remain model estimates.') ]},
        {'title': 'Unedited reference · actual playback capture', 'duration': 16, 'source': sequence('demo-reference-', 16, 1),
         'audio': {'path': obama+'corrected-reference.wav'}, 'captions': [
            (0, 8, 'Listen to the unedited reference. The identical-audio control scores 100 with no alert.'),
            (8, 16, 'The chart follows actual playback. A chosen reference is not a universal rhetorical ideal.') ]},
        {'title': 'Strong pace edit · actual playback capture', 'duration': 18, 'source': sequence('demo-pace-', 18, 1),
         'audio': {'path': obama+'pace-3.wav'}, 'captions': [
            (0, 7, 'The same text now contains a local tempo edit requesting 2.10× dilation. Listen to the changed phrase.'),
            (7, 13, 'The delivery lasts 16.46 seconds, versus 14.84 seconds for the reference.'),
            (13, 18, 'The fixed rubric reports 65.03 reference similarity, with three grounded alerts.') ]},
        {'title': 'Play region · actual button playback capture', 'duration': 6, 'source': sequence('demo-region-fixed-', 7, 2),
         'audio': {'path': obama+'pace-3.wav', 'offset': .9, 'length': 2.066845}, 'captions': [
            (0, 6, 'Play region replays the selected delivery span: 0.90–2.96 seconds, with its word context.') ]},
        {'title': 'Numerical explanation · captured analysis', 'duration': 12, 'source': still('demo-pace-evidence.png'), 'captions': [
            (0, 6, 'IMPORTANT lasts 0.64 seconds instead of 0.35: 1.87× the reference duration.'),
            (6, 12, 'The advice stays conditional. A deliberate emphasis is a choice, not a diagnosis of speaking ability.') ]},
        {'title': 'Pause edit · audio excerpt with captured analysis', 'duration': 18, 'source': still('demo-pause-evidence.png'),
         'audio': {'path': obama+'pause-3.wav', 'length': 7}, 'captions': [
            (0, 8, 'The edit inserts 0.95 seconds of silence. Alignment estimates a 0.99-second gap before THE.'),
            (8, 18, 'The reference gap is 0.07 seconds: an estimated extra 0.92 seconds. Edit labels and model times are distinct.') ]},
        {'title': 'Local volume edit · audio with captured analysis', 'duration': 18, 'source': still('demo-volume-evidence.png'),
         'audio': {'path': obama+'volume-3.wav'}, 'captions': [
            (0, 8, 'The local amplitude multiplier is 0.22. The shared transcript and clip duration stay unchanged.'),
            (8, 18, 'Measured relative energy falls by 12.0 dB after each recording’s median level is removed.') ]},
        {'title': 'Near-perfect pace edit · captured analysis', 'duration': 16, 'source': still('demo-near-perfect-evidence.png'),
         'audio': {'path': obama+'pace-1.wav', 'length': 8}, 'captions': [
            (0, 8, 'The 1.08× tempo request has no matching pace alert. The subtle target is missed.'),
            (8, 16, 'Two off-target volume alerts remain. A non-perfect score does not establish a correct target hit.') ]},
        {'title': 'Noise localization miss · audio with captured analysis', 'duration': 14, 'source': still('demo-noise-localization-miss.png'),
         'audio': {'path': biden+'roughness-3.wav'}, 'captions': [
            (0, 7, 'Biden’s 5 dB SNR edit produces noise alerts, but their intervals cover too little of the exact target.'),
            (7, 14, 'The best matching IoU is 0.224, below the 0.25 target-hit threshold. This pair counts as a miss.') ]},
        {'title': 'Global pitch control · excerpt with captured analysis', 'duration': 12, 'source': still('demo-pitch-control-false-alert.png'),
         'audio': {'path': obama+'control-global_pitch_1.15.wav', 'offset': 11.8, 'length': 2.8}, 'captions': [
            (0, 6, 'A global pitch shift with tempo compensation should not create a local-volume warning.'),
            (6, 12, 'It does here. The OF alert is the single control false alarm, so normalization is not fully robust.') ]},
        {'title': 'All results · captured validation table', 'duration': 22, 'source': {'parts': [
            {'image': 'demo-validation-summary.png', 'start': 0}, {'image': 'demo-validation-misses.png', 'start': 11}]}, 'captions': [
            (0, 7, 'The reported target hits are 16/18 moderate or strong cases and 0/10 near-perfect cases.'),
            (7, 14, 'One of six controls has a false alert. All 34 pairs remain visible, including the misses.'),
            (14, 22, 'The predeclared ≥93% / zero-false-alert gate failed. V2 uses known speakers, not a new blind-speaker test.') ]},
        {'title': 'New upload · actual prepared input', 'duration': 8, 'source': still('demo-upload-input.png'), 'captions': [
            (0, 8, 'Choose two 0.5–30-second audio files, at most 8 MB each, and the same English transcript.') ]},
        {'title': 'New upload · actual local processing capture', 'duration': 8, 'source': sequence('demo-upload-', 16, 2), 'captions': [
            (0, 4, 'Whisper checks the text, then CTC alignment and acoustic features run on this machine.'),
            (4, 8, 'This is the real processing sequence. No audio is sent to a hosted inference service.') ]},
        {'title': 'New upload · actual returned result', 'duration': 12, 'source': still('demo-upload-result.png'), 'captions': [
            (0, 6, 'The uploaded public example returns 80.47, 46 aligned words and one local-volume region.'),
            (6, 12, 'The server deletes temporary upload files before the reply. Export JSON retains the numerical evidence.') ]},
        {'title': 'Reproducibility and technical report', 'duration': 18, 'card': 'reproduce', 'captions': [
            (0, 8, 'Read-only replay reproduces all 34 recorded analyses from their frozen word times.'),
            (8, 18, 'Software replay passed; the experiment gate did not. The six-page report keeps that distinction explicit.') ]},
        {'title': 'Scope and AI assistance', 'duration': 10, 'card': 'close', 'captions': [
            (0, 5, 'Two speakers and controlled edits do not establish general rhetorical or demographic validity.'),
            (5, 10, 'OpenAI Codex assisted with implementation, tests, documentation and demo assembly. No model was trained.') ]},
    ]


def source_image(scene, time):
    if 'card' in scene:
        return card(scene['card'])
    source = scene['source']
    if 'prefix' in source:
        index = min(source['count'] - 1, int(time * source['fps'] + 1e-7))
        name = f"{source['prefix']}{index:03d}.png"
    elif 'parts' in source:
        name = next(p['image'] for p in reversed(source['parts']) if p['start'] <= time)
    else:
        name = source['image']
    actual = Image.open(CAPTURES / name).convert('RGB')
    if actual.size != (WIDTH, 900):
        raise ValueError(f'Unexpected capture dimensions: {name} {actual.size}')
    return actual


def frame(scene, local_time, index, total):
    image = Image.new('RGB', (WIDTH, HEIGHT), 'white')
    image.paste(source_image(scene, local_time), (0, 64))
    d = ImageDraw.Draw(image)
    d.text((24, 17), scene['title'], font=font(27), fill='#222')
    page_number = f'{index + 1} / {total}'
    d.text((WIDTH - 24 - d.textlength(page_number, font=font(22)), 20), page_number, font=font(22), fill='#666')
    d.line((0, 63, WIDTH, 63), fill='#aaa', width=1)
    d.rectangle((0, 964, WIDTH, HEIGHT), fill='#f1f1f1')
    d.line((0, 964, WIDTH, 964), fill='#aaa', width=1)
    caption = next((text for a, b, text in scene['captions'] if a <= local_time < b), '')
    lines = wrap(caption, font(30), WIDTH - 64)
    if len(lines) > 2:
        raise ValueError('Caption exceeds the two-line reading area: ' + caption)
    y = 977 + (2 - len(lines)) * 18
    for line in lines:
        d.text((32, y), line, font=font(30), fill='#222')
        y += 38
    return image


def srt_time(seconds):
    ms = round(seconds * 1000)
    hours, remainder = divmod(ms, 3600000)
    minutes, remainder = divmod(remainder, 60000)
    secs, millis = divmod(remainder, 1000)
    return f'{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}'


def main():
    timeline = scenes()
    duration = sum(scene['duration'] for scene in timeline)
    if not 180 <= duration <= 600:
        raise ValueError('The event requires a 3–10-minute video.')
    frames = OUT / 'frames'
    frames.mkdir(parents=True, exist_ok=True)
    concat, subtitles, chapters, records = [], [], [], []
    audio = bytearray(duration * 16000 * 2)
    cursor, frame_number, subtitle_number = 0, 0, 1
    for i, scene in enumerate(timeline):
        changes = {0, scene['duration']}
        changes.update(a for a, _, _ in scene['captions'])
        changes.update(b for _, b, _ in scene['captions'])
        source = scene.get('source', {})
        if 'prefix' in source:
            changes.update(n / source['fps'] for n in range(source['count']) if n / source['fps'] < scene['duration'])
        changes.update(p['start'] for p in source.get('parts', []))
        changes = sorted(changes)
        for a, b in zip(changes, changes[1:]):
            name = frames / f'{frame_number:04d}.png'
            frame(scene, a, i, len(timeline)).save(name)
            quoted = str(name).replace("'", "'\\''")
            concat += [f"file '{quoted}'", f'duration {b - a:.9f}']
            records.append({'frame': name.name, 'start_s': cursor + a, 'duration_s': b - a,
                            'sha256': hashlib.sha256(name.read_bytes()).hexdigest()})
            frame_number += 1
        for a, b, text in scene['captions']:
            subtitles += [str(subtitle_number), f'{srt_time(cursor+a)} --> {srt_time(cursor+b)}', text, '']
            subtitle_number += 1
        if scene.get('audio'):
            item = scene['audio']
            with wave.open(str(ROOT / item['path'])) as source_audio:
                if (source_audio.getframerate(), source_audio.getnchannels(), source_audio.getsampwidth()) != (16000, 1, 2):
                    raise ValueError('Demo audio must be published 16 kHz mono 16-bit PCM.')
                offset = round(item.get('offset', 0) * 16000)
                source_audio.setpos(offset)
                count = min(source_audio.getnframes() - offset, round(item.get('length', scene['duration']) * 16000))
                body = source_audio.readframes(count)
            start_byte = cursor * 16000 * 2
            audio[start_byte:start_byte + len(body)] = body
        chapters.append({'start_s': cursor, 'duration_s': scene['duration'], 'title': scene['title']})
        cursor += scene['duration']
    concat.append(concat[-2])
    (OUT / 'frames.ffconcat').write_text('\n'.join(concat) + '\n')
    (OUT / 'speech-contrast-demo.en.srt').write_text('\n'.join(subtitles) + '\n')
    with wave.open(str(OUT / 'demo-audio.wav'), 'wb') as destination:
        destination.setnchannels(1)
        destination.setsampwidth(2)
        destination.setframerate(16000)
        destination.writeframes(audio)
    result = OUT / 'speech-contrast-demo.mp4'
    command = ['ffmpeg', '-y', '-nostdin', '-hide_banner', '-loglevel', 'error',
               '-f', 'concat', '-safe', '0', '-i', str(OUT / 'frames.ffconcat'),
               '-i', str(OUT / 'demo-audio.wav'), '-r', '24', '-c:v', 'libx264',
               '-preset', 'veryfast', '-crf', '18', '-threads', '2', '-pix_fmt', 'yuv420p',
               '-c:a', 'aac', '-b:a', '128k', '-ar', '48000', '-movflags', '+faststart',
               '-t', str(duration), str(result)]
    subprocess.run(command, check=True, timeout=300)
    metadata = {'duration_s': duration, 'width': WIDTH, 'height': HEIGHT,
                'chapters': chapters, 'caption_cues': subtitle_number - 1,
                'rendered_states': records, 'video_sha256': hashlib.sha256(result.read_bytes()).hexdigest(),
                'scope': 'Edited functional walkthrough from actual prototype captures and the published public-domain paired audio. No synthesized UI state or voice narration.'}
    (OUT / 'DEMO_RECEIPT.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(json.dumps({k: metadata[k] for k in ['duration_s', 'width', 'height', 'caption_cues', 'video_sha256']}))


if __name__ == '__main__':
    main()
