# Dataset notes

The canonical index is `data/manifest.json`: two reference clips and 34 paired
deliveries. All paths are relative to the repository root. Each pair includes its
shared transcript, waveform hash, edit label, independent transcription check,
estimated word intervals and recorded analysis hash.

## Sources

| Reference | Official transcript | Rights page |
| --- | --- | --- |
| Barack Obama, 11 July 2009 | [Recovery Act progress](https://obamawhitehouse.archives.gov/the_press_office/Weekly-Address-President-Obama-Praises-Recovery-Act-Progress) | [Archive: Public Domain](https://obamawhitehouse.archives.gov/video/Weekly-Address-Recovery-and-the-Jobs-of-the-Future/index__q_page=1.html) |
| Joe Biden, 28 May 2011 | [American auto manufacturers](https://obamawhitehouse.archives.gov/the-press-office/2011/05/28/weekly-address-resurgent-american-auto-manufacturers-signal-economy-rise) | [Archive: Public Domain](https://obamawhitehouse.archives.gov/photos-and-video/video/2011/05/28/weekly-address-biden-american-auto-comeback) |

Direct audio URLs and source dates are in `data/sources.json`. Only short opening
excerpts are distributed. The full source downloads and model caches are not
part of the release. A prominent speaker's recording is a chosen comparison,
not a universal ideal or an endorsement of its content.

The Obama excerpt contains 46 words and lasts 14.835 seconds; the Biden excerpt
contains 21 words and lasts 6.665 seconds. Official transcript wording is retained.
Whisper's recognized wording is stored separately, including its `towards`
variant against the official `toward`.

## Construction

Each reference is decoded to 16 kHz mono PCM and peak-scaled for editing headroom.
Forced alignment is run on the actual cropped, quantized reference waveform,
not on a longer source window whose timestamps have merely been shifted.

Four edit families target zero-based word indices 4–9. The pause edit inserts
silence before word index 7. Three severity levels are fixed in `protocol-v1.json`:

| Family | Near-perfect | Moderate | Strong |
| --- | ---: | ---: | ---: |
| Local tempo dilation request | 1.08× | 1.40× | 2.10× |
| Inserted pause | 0.12 s | 0.40 s | 0.95 s |
| Local amplitude multiplier | 0.85 | 0.50 | 0.22 |
| Added white-noise SNR | 25 dB | 15 dB | 5 dB |

FFmpeg `atempo` changes local tempo while approximately preserving pitch.
Filters can produce a duration different from the requested factor, so the label
records the actual sample interval and time map. Local volume edits do not change
the text or time axis. Noise uses fixed seeds, with SNR measured on the edited
span. Three controls per speaker use identical audio, global amplitude ×0.5 and
global pitch ×1.15 with a compensating tempo filter.

The v2 protocol adds noise at 20 and 8 dB SNR for both source clips, seed 71003.
These four perturbations had not been generated when their protocol was frozen.
The speakers and original 30 pairs were already known. The `split` field retains
the original v1 designation; it does not make the v2 replay a fresh holdout.

## Labels and alignment

- `label.sample_start` and `label.sample_end` are exact edit boundaries in the
  delivered PCM. `label.time_map` explains the relation to reference time.
- `words` are silver labels from frozen CTC alignment. Their confidence values
  are acoustic support, not calibrated timing accuracy. They have not been
  manually corrected or reviewed as a gold timing benchmark.
- `verification.word_agreement` measures independent Whisper agreement with the
  supplied transcript. It does not prove every word boundary is correct.
- `targeted_hit` requires the expected alert family and interval IoU ≥ 0.25.
  Off-target alerts do not count as target hits. Misses and abstentions remain in
  their denominators; controls are reported separately.

All 34 pairs received scores in the recorded v2 evaluation. Moderate/strong
target hits were 16/18, near-perfect hits 0/10, and control false alerts 1/6.
Both strong-case misses were Biden added-noise cases; the false alert was the
Obama global-pitch control. The gate required ≥93% moderate/strong hits and zero
control false alerts, so `gate_passed` is false.

## Versions and replay

`manifest-v1.json` preserves the initial result. An identical-audio false alert
revealed mismatched crop/frame origins; `manifest-repair-v1.json` records the
fixture repair without treating it as a new blind test. `manifest-v2.json` and
the canonical manifest retain the subsequent failed v2 evaluation. Older
waveforms and analyses remain available but are not the canonical reference set.

Run `python3 scripts/reproduce.py` to verify the published hashes and recompute
the canonical outputs from frozen word times. This checks software reproduction,
not a new hypothesis or a new speaker-generalization result. Model-based
alignment and historical experiment-launch scripts are not required for replay.

Project-created edits and annotations are released under [CC0](../data/LICENSE.md).
Original speech rights and model licenses remain separate.
