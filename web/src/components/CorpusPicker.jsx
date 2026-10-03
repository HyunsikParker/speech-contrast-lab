import React from 'react';

export const familyNames = { pace: 'Pace', pause: 'Pause', volume: 'Local volume', roughness: 'Added noise', control: 'Control' };
export const strengthNames = { 1: 'Near-perfect edit', 2: 'Moderate edit', 3: 'Strong edit' };
export const controlNames = { identical: 'Identical audio', 'global_gain_0.5': 'Global volume ×0.5', 'global_pitch_1.15': 'Global pitch ×1.15' };
export const speakerName = id => id.startsWith('obama') ? 'Barack Obama' : 'Joe Biden';

export default function CorpusPicker({ manifest, selected, onSelect, disabled }) {
  const example = manifest.examples.find(e => e.id === selected);
  const sourceId = example?.source_id ?? manifest.references[0].id;
  const options = manifest.examples.filter(e => e.source_id === sourceId);
  return <div className="corpus-picker">
    <label>Reference speaker
      <select disabled={disabled} value={sourceId} onChange={e => onSelect(manifest.examples.find(x => x.source_id === e.target.value && x.family === 'pace' && x.level === 3).id)}>
        {manifest.references.map(ref => <option key={ref.id} value={ref.id}>{speakerName(ref.id)}</option>)}
      </select>
    </label>
    <label>Paired delivery
      <select disabled={disabled} value={selected} onChange={e => onSelect(e.target.value)}>
        {options.map(e => <option key={e.id} value={e.id}>{e.family === 'control' ? controlNames[e.control] : `${familyNames[e.family]} · ${e.fresh_perturbation ? `fresh noise ${e.label.parameter} dB SNR` : strengthNames[e.level]}`}</option>)}
      </select>
    </label>
  </div>;
}
