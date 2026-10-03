import React, { useEffect, useRef, useState } from 'react';
import { linePath, referenceAt } from '../timeMap.js';

const metrics = { relative_energy_db: { label: 'Energy', unit: 'dB relative to median', min: -45, max: 18 },
  pitch_semitones: { label: 'Pitch', unit: 'semitones from voiced median', min: -12, max: 12 },
  spectral_flatness: { label: 'Spectral flatness', unit: 'flatness (0–1)', min: 0, max: null } };

export default function Timeline({ result, selectedRegion, playhead, onSeek }) {
  const [metric, setMetric] = useState('relative_energy_db');
  const plot = useRef(null);
  const [width, setWidth] = useState(900);
  useEffect(() => {
    const observer = new ResizeObserver(entries => setWidth(Math.max(240, entries[0].contentRect.width)));
    observer.observe(plot.current);
    return () => observer.disconnect();
  }, []);
  const info = metrics[metric];
  const ref = result.reference_frames, observed = result.delivery_frames;
  // Silence has undefined tonal/noise flatness and can occupy the whole scale.
  // Omit low-energy flatness only in the display; recorded features and scoring
  // remain unchanged and available in the JSON export.
  const displayValues = frames => frames[metric].map((value, i) => metric === 'spectral_flatness' && frames.relative_energy_db[i] < -30 ? null : value);
  const referenceValues = displayValues(ref), deliveryValues = displayValues(observed);
  const max = info.max ?? Math.max(0.025, ...referenceValues.filter(Number.isFinite), ...deliveryValues.filter(Number.isFinite));
  const left = 56, right = width - 22, span = right - left;
  const x = time => left + time / result.reference_duration * span;
  const y = value => 202 - (Math.max(info.min, Math.min(max, value)) - info.min) / (max - info.min) * 166;
  const deliveryTimes = observed.time.map(t => referenceAt(result, t));
  const seekEvent = e => {
    const rectangle = e.currentTarget.getBoundingClientRect();
    const position = ((e.clientX - rectangle.left) / rectangle.width * width - left) / span * result.reference_duration;
    onSeek(Math.max(0, Math.min(result.reference_duration, position)), false);
  };
  return <section className="timeline-section" aria-labelledby="timeline-heading">
    <div className="section-heading"><h2 id="timeline-heading">Word-aligned comparison</h2><div className="metric-toggle" aria-label="Acoustic feature">
      {Object.entries(metrics).map(([key, item]) => <button key={key} aria-pressed={key === metric} onClick={() => setMetric(key)}>{item.label}</button>)}
    </div></div>
    <div className="plot-legend"><span className="reference-key">Reference</span><span className="delivery-key">Delivery</span><span>{info.unit}</span></div>
    <div ref={plot} className="plot" role="slider" tabIndex={0} aria-label="Seek on the reference time axis" aria-valuemin={0} aria-valuemax={result.reference_duration} aria-valuenow={Number(playhead.toFixed(2))} aria-valuetext={`${playhead.toFixed(2)} seconds on reference axis`} onClick={seekEvent} onKeyDown={e => {
      const step = e.shiftKey ? 1 : 0.25;
      const values = { ArrowLeft: Math.max(0, playhead - step), ArrowRight: Math.min(result.reference_duration, playhead + step), Home: 0, End: result.reference_duration };
      if (e.key in values) { e.preventDefault(); onSeek(values[e.key], false); }
      if (e.key === 'Enter') { e.preventDefault(); onSeek(playhead, true); }
    }}>
      <svg viewBox={`0 0 ${width} 242`} aria-hidden="true">
        <defs><pattern id="region-hatch" width="6" height="6" patternUnits="userSpaceOnUse"><path d="M0 6L6 0" stroke="#777" strokeWidth="0.5" /></pattern></defs>
        {[0, 1, 2, 3].map(i => { const value = info.min + (max - info.min) * i / 3; return <g key={i}><line x1={left} y1={y(value)} x2={right} y2={y(value)} stroke="#ddd" /><text x={left - 10} y={y(value) + 4} textAnchor="end">{metric === 'spectral_flatness' ? value.toFixed(3) : value.toFixed(0)}</text></g>; })}
        {result.regions.map((region, i) => <g key={i}><rect x={x(region.reference_start)} y="29" width={Math.max(3, x(region.reference_end) - x(region.reference_start))} height="178" fill="url(#region-hatch)" opacity={selectedRegion === i ? 0.45 : 0.13} />{(selectedRegion >= 0 ? selectedRegion === i : i === 0 || x(region.reference_start) - x(result.regions[i - 1].reference_start) > 32) && <text x={x(region.reference_start) + 3} y="23" className="region-tag">R{i + 1}</text>}</g>)}
        <path d={linePath(ref.time, referenceValues, x, y)} fill="none" stroke="#242424" strokeWidth="1.8" />
        <path d={linePath(deliveryTimes, deliveryValues, x, y)} fill="none" stroke="#666" strokeWidth="1.6" strokeDasharray="5 4" />
        <line x1={x(playhead)} y1="29" x2={x(playhead)} y2="207" stroke="#111" strokeWidth="1.2" />
        {[0, 1, 2, 3, 4].map(i => { const time = result.reference_duration * i / 4; return <text key={i} x={x(time)} y="229" textAnchor="middle">{time.toFixed(1)}s</text>; })}
      </svg>
    </div>
    <p className="plot-note">Delivery features are warped to matching word anchors. Replay uses real audio time. Click to seek; use arrow keys to move and Enter to play.{metric === 'spectral_flatness' ? ' Low-energy frames (below −30 dB relative level) are omitted from this plot only.' : ''}</p>
  </section>;
}
