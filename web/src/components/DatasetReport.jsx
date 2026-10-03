import React from 'react';
import { familyNames, speakerName, controlNames } from './CorpusPicker.jsx';

export default function DatasetReport({ manifest, onSelect }) {
  const strong = manifest.examples.filter(e => e.level >= 2);
  const near = manifest.examples.filter(e => e.level === 1);
  const controls = manifest.examples.filter(e => e.family === 'control');
  return <details className="dataset-report"><summary>Dataset and validation · {manifest.examples.length} paired recordings</summary>
    <div className="validation-summary">
      <div><strong>{strong.filter(e => e.targeted_hit).length}/{strong.length}</strong><span>moderate / strong target regions hit</span></div>
      <div><strong>{near.filter(e => e.targeted_hit).length}/{near.length}</strong><span>near-perfect target regions hit</span></div>
      <div><strong>{controls.filter(e => e.regions.length).length}/{controls.length}</strong><span>controls with false alerts</span></div>
    </div>
    {!manifest.gate_passed && <p className="validation-note">Validation target not met: target-region hit rate is below 93%, and one normalization control has a false alert. This prototype reports the observed results; it is not a validated general-purpose judge.</p>}
    <p>The original second speaker was unseen in the first evaluation. Later versions are known-speaker replays, with four new noise realizations. A target hit requires a matching alert family and at least 0.25 intersection-over-union with the exact DSP edit interval.</p>
    <div className="table-scroll"><table><caption>All paired recordings, including misses and controls</caption><thead><tr><th>Speaker</th><th>Pair</th><th>Target hit</th><th>IoU</th><th>Custom score</th></tr></thead><tbody>
      {manifest.examples.map(e => <tr key={e.id}><td>{speakerName(e.source_id)}</td><td><button className="text-button" onClick={() => onSelect(e.id)}>{e.family === 'control' ? controlNames[e.control] : `${familyNames[e.family]} · ${e.fresh_perturbation ? `${e.label.parameter} dB SNR (new)` : `level ${e.level}`}`}</button></td><td>{e.family === 'control' ? (e.regions.length ? 'False alert' : 'No alert') : e.abstained ? 'Abstained' : e.targeted_hit ? 'Hit' : 'Miss'}</td><td>{e.family === 'control' ? '—' : e.max_target_iou.toFixed(2)}</td><td>{e.score === null ? 'No score' : e.score.toFixed(2)}</td></tr>)}
    </tbody></table></div>
    <p className="fineprint">Two public-domain government speech clips, controlled local edits, no training. Exact edit labels and model-estimated word times are stored separately. Smaller edits can fall below the warning thresholds. Global pitch shifting is a limited synthetic normalization test, not proof of robustness across natural voices.</p>
    <p className="source-links">Sources: <a href="https://obamawhitehouse.archives.gov/video/Weekly-Address-Recovery-and-the-Jobs-of-the-Future/index__q_page=1.html" target="_blank" rel="noreferrer">Obama · 11 July 2009 · Public Domain</a> · <a href="https://obamawhitehouse.archives.gov/photos-and-video/video/2011/05/28/weekly-address-biden-american-auto-comeback" target="_blank" rel="noreferrer">Biden · 28 May 2011 · Public Domain</a></p>
  </details>;
}
