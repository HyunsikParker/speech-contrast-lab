import React from 'react';

const names = { pace: 'Pace', pause: 'Pause', volume: 'Relative volume', roughness: 'Spectral noise' };

export function Regions({ result, selected, onSelect }) {
  return <section className="regions-section" aria-labelledby="regions-heading">
    <div className="section-heading"><h2 id="regions-heading">Grounded deviations</h2><span>{result.regions.length} regions</span></div>
    {!result.regions.length && <p className="empty-state">No deviation crosses the fixed thresholds. Subtle differences may remain.</p>}
    <ol className="region-list">
      {result.regions.map((region, i) => <li key={i} className={selected === i ? 'region selected' : 'region'}>
        <div className="region-top"><span className="region-number">R{i + 1}</span><strong>{names[region.kind]}</strong><span className="region-time">{region.start.toFixed(2)}–{region.end.toFixed(2)}s</span><button aria-label={`Play region ${i + 1}: ${names[region.kind]}`} aria-pressed={selected === i} onClick={() => onSelect(i)}>Play region</button></div>
        <p className="region-words">{region.words}</p><p>{region.explanation}</p>
        {region.word_evidence.length > 1 && <details><summary>Measurements for {region.word_evidence.length} words</summary><ul className="word-evidence">
          {region.word_evidence.map((word, j) => <li key={j}><strong>{word.words}</strong> · {word.start.toFixed(2)}–{word.end.toFixed(2)}s — {word.explanation}</li>)}
        </ul></details>}
      </li>)}
    </ol>
  </section>;
}

export function Rubric({ result }) {
  return <details className="rubric"><summary>How the custom score is calculated</summary>
    <p>The score starts at 100 and subtracts four weighted acoustic-deviation penalties. It measures similarity to this reference, not persuasiveness or speaking ability.</p>
    <div className="rubric-rows">{result.components.map(component => <div className="rubric-row" key={component.kind}>
      <span>{names[component.kind]}</span><span className="penalty-track"><span style={{ width: `${component.penalty / component.weight * 100}%` }} /></span><span>−{component.penalty.toFixed(2)} / {component.weight}</span>
    </div>)}</div>
    <p className="fineprint">For each family: penalty = weight × min(1, 0.75 × maximum detected severity + 0.25 × summed severity / total words). {result.rubric_version}. Severity is fixed by the documented acoustic equations.</p>
    <p className="fineprint">Scores are not guaranteed to decrease monotonically with every injected edit. Alignment and other acoustic differences can change several penalties at once.</p>
  </details>;
}

export function Transcript({ result, onWord }) {
  const uncertain = result.words.filter(w => !w.reliable).length;
  return <section className="transcript-section" aria-labelledby="transcript-heading">
    <div className="section-heading"><h2 id="transcript-heading">Aligned transcript</h2><span>{result.words.length} words · {uncertain} low-support</span></div>
    <div className="transcript-words">{result.words.map(row => <button key={row.index} className={row.reliable ? 'word' : 'word uncertain'} onClick={() => onWord(row)} title={`Delivery ${row.delivery.start.toFixed(2)}–${row.delivery.end.toFixed(2)}s; duration ${row.duration_ratio.toFixed(2)}×; relative energy ${row.energy_delta_db.toFixed(1)}dB`} aria-label={`Play ${row.word} at ${row.delivery.start.toFixed(2)} seconds`}>{row.word.toLowerCase()}</button>)}</div>
    <p className="fineprint">Word boundaries are frozen-model estimates, not manually verified labels. Low-support words are excluded from alerts.</p>
    <details><summary>Original transcript and model checks</summary><p>{result.transcript}</p>
      {result.verification && <p>Independent transcript agreement: reference {(result.verification.reference.word_agreement * 100).toFixed(1)}%; delivery {(result.verification.delivery.word_agreement * 100).toFixed(1)}%. Acoustic probabilities are not calibrated timing accuracy.</p>}
    </details>
  </section>;
}
