import React, { useEffect, useRef, useState } from 'react';
import CorpusPicker from './components/CorpusPicker.jsx';
import UploadForm, { encodeAudio } from './components/UploadForm.jsx';
import Timeline from './components/Timeline.jsx';
import { Regions, Rubric, Transcript } from './components/Evidence.jsx';
import DatasetReport from './components/DatasetReport.jsx';
import { deliveryAt, referenceAt } from './timeMap.js';

async function readJson(response) {
  const body = await response.json();
  if (!response.ok) throw new Error(body.error ?? 'The local request could not finish.');
  return body;
}

export default function App() {
  const [manifest, setManifest] = useState(null);
  const [selected, setSelected] = useState('obama-weekly-20090711-pace-3');
  const [mode, setMode] = useState('examples');
  const [result, setResult] = useState(null);
  const [audioUrls, setAudioUrls] = useState({ reference: '', delivery: '' });
  const [selectedRegion, setSelectedRegion] = useState(-1);
  const [playhead, setPlayhead] = useState(0);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const referencePlayer = useRef(null), deliveryPlayer = useRef(null);
  const playbackEnd = useRef(null), playbackTimer = useRef(null), blobs = useRef([]);
  useEffect(() => {
    fetch('/api/manifest').then(readJson).then(setManifest).catch(e => setError(e.message));
    return () => { clearTimeout(playbackTimer.current); blobs.current.forEach(URL.revokeObjectURL); };
  }, []);
  useEffect(() => {
    if (!manifest || mode !== 'examples') return;
    const controller = new AbortController();
    setPending(true); setError(''); setSelectedRegion(-1); setPlayhead(0); playbackEnd.current = null;
    fetch(`/api/analysis/${selected}`, { signal: controller.signal }).then(readJson).then(data => {
      setResult(data); setAudioUrls({ reference: `/api/audio/${selected}/reference`, delivery: `/api/audio/${selected}/delivery` });
    }).catch(e => { if (e.name !== 'AbortError') setError(e.message); }).finally(() => { if (!controller.signal.aborted) setPending(false); });
    return () => controller.abort();
  }, [manifest, mode, selected]);
  function selectExample(id) { setSelected(id); setMode('examples'); window.scrollTo({ top: 0, behavior: 'instant' }); }
  function seekPlayer(player, time, play = false) {
    if (!player) return;
    player.currentTime = time;
    if (play) player.play().catch(() => setError('Playback could not start. Use the audio player’s Play control.'));
  }
  function clearPlaybackTimer() { clearTimeout(playbackTimer.current); playbackTimer.current = null; }
  function armPlaybackStop(player) {
    clearPlaybackTimer();
    if (!player || player.paused || playbackEnd.current === null) return;
    const remaining = playbackEnd.current - player.currentTime;
    if (remaining <= 0.012) { player.pause(); playbackEnd.current = null; return; }
    // timeupdate can be hundreds of milliseconds apart; schedule the actual
    // interval end rather than relying on that coarse display event alone.
    playbackTimer.current = setTimeout(() => armPlaybackStop(player), Math.max(8, remaining / player.playbackRate * 1000));
  }
  function seekReference(time, play = false) {
    clearPlaybackTimer(); setSelectedRegion(-1); playbackEnd.current = null; setPlayhead(time);
    referencePlayer.current?.pause();
    seekPlayer(referencePlayer.current, time);
    seekPlayer(deliveryPlayer.current, deliveryAt(result, time), play);
  }
  function playRegion(index) {
    const region = result.regions[index];
    clearPlaybackTimer();
    setSelectedRegion(index); playbackEnd.current = region.end;
    referencePlayer.current?.pause();
    setPlayhead(region.reference_start); seekPlayer(referencePlayer.current, region.reference_start);
    seekPlayer(deliveryPlayer.current, region.start, true);
    armPlaybackStop(deliveryPlayer.current);
  }
  function playWord(row) {
    clearPlaybackTimer();
    setSelectedRegion(-1); playbackEnd.current = row.delivery.end;
    referencePlayer.current?.pause(); setPlayhead(row.reference.start);
    seekPlayer(referencePlayer.current, row.reference.start); seekPlayer(deliveryPlayer.current, row.delivery.start, true);
    armPlaybackStop(deliveryPlayer.current);
  }
  async function compareUploads({ reference, delivery, transcript }) {
    setPending(true); setError('');
    try {
      const files = await Promise.all([encodeAudio(reference), encodeAudio(delivery)]);
      const response = await fetch('/api/compare', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ reference: files[0], delivery: files[1], transcript }) });
      const data = await readJson(response);
      blobs.current.forEach(URL.revokeObjectURL);
      blobs.current = [URL.createObjectURL(reference), URL.createObjectURL(delivery)];
      setAudioUrls({ reference: blobs.current[0], delivery: blobs.current[1] });
      setResult(data); setPlayhead(0); setSelectedRegion(-1); playbackEnd.current = null;
    } finally { setPending(false); }
  }
  function exportResult() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' }));
    const link = document.createElement('a'); link.href = url; link.download = 'speech-contrast-analysis.json'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <div className="app-shell">
    <header className="app-header"><div><h1>Speech Contrast Lab</h1><p>Compare the same words. Hear the difference.</p></div><span className="header-note">Local analysis · no paid API</span></header>
    <main>
      <section className="input-section" aria-label="Choose a comparison">
        <div className="input-tabs" aria-label="Comparison input"><button disabled={pending} aria-pressed={mode === 'examples'} onClick={() => setMode('examples')}>Paired examples</button><button disabled={pending} aria-pressed={mode === 'upload'} onClick={() => setMode('upload')}>Upload recordings</button></div>
        {mode === 'examples' && manifest && <CorpusPicker manifest={manifest} selected={selected} onSelect={setSelected} disabled={pending} />}
        {mode === 'upload' && <UploadForm onCompare={compareUploads} pending={pending} />}
        {pending && <p className="processing" role="status">{mode === 'upload' ? 'Checking the transcript, aligning words and measuring acoustic differences on this machine…' : 'Loading the recorded comparison…'}</p>}
        {error && <p className="error" role="alert">{error}</p>}
      </section>
      {result && !pending && <>
        {result.abstained ? <section className="abstention" role="status"><h2>No score assigned</h2><p>{result.reason}</p><p>The recordings are still available below. Check that both use the supplied transcript.</p></section> : <div className="comparison-heading"><div><h2>Reference similarity</h2><p>Custom acoustic rubric · not an official contest score</p></div><div className="score"><strong>{result.score.toFixed(1)}</strong><span>/ 100</span></div><button onClick={exportResult}>Export analysis JSON</button></div>}
        <section className="audio-pair" aria-label="Audio playback">
          <div><label htmlFor="reference-audio">Reference{result.reference_duration ? ` · ${result.reference_duration.toFixed(2)}s` : ''}</label><audio id="reference-audio" ref={referencePlayer} controls preload="metadata" src={audioUrls.reference} onPlay={() => deliveryPlayer.current?.pause()} onTimeUpdate={e => setPlayhead(e.currentTarget.currentTime)} /></div>
          <div><label htmlFor="delivery-audio">Delivery{result.delivery_duration ? ` · ${result.delivery_duration.toFixed(2)}s` : ''}</label><audio id="delivery-audio" ref={deliveryPlayer} controls preload="metadata" src={audioUrls.delivery} onPlay={e => { referencePlayer.current?.pause(); armPlaybackStop(e.currentTarget); }} onPause={clearPlaybackTimer} onRateChange={e => armPlaybackStop(e.currentTarget)} onTimeUpdate={e => {
            if (result.words) setPlayhead(referenceAt(result, e.currentTarget.currentTime));
            if (playbackEnd.current !== null && e.currentTarget.currentTime >= playbackEnd.current) { clearPlaybackTimer(); e.currentTarget.pause(); playbackEnd.current = null; }
          }} /></div>
        </section>
        {!result.abstained && <><Timeline result={result} selectedRegion={selectedRegion} playhead={playhead} onSeek={seekReference} /><div className="analysis-columns"><Regions result={result} selected={selectedRegion} onSelect={playRegion} /><aside><Transcript result={result} onWord={playWord} /><Rubric result={result} /><details className="normalization"><summary>Feature normalization and scope</summary><p>{result.normalization}</p><p>{result.score_scope}</p><p>FFT spectral flatness, 13 MFCC coefficients, autocorrelation F0, word durations and gaps are measured locally. MFCC distance and normalized pitch are diagnostics, not standalone penalties.</p></details></aside></div></>}
      </>}
      {manifest && <DatasetReport manifest={manifest} onSelect={selectExample} />}
    </main>
    <footer><span>Frozen models · reproducible edits · no audio sent to a model service</span><span>Code, tests and documentation developed with OpenAI Codex assistance.</span></footer>
  </div>;
}
