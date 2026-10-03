import React, { useState } from 'react';

export async function encodeAudio(file) {
  if (!file || file.size > 8_000_000) throw new Error('Choose two audio files, each at most 8 MB.');
  const extension = file.name.split('.').at(-1).toLowerCase();
  if (!['wav', 'mp3', 'flac', 'ogg', 'webm'].includes(extension)) throw new Error('Use WAV, MP3, FLAC, OGG or WebM audio.');
  const data = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(',')[1]);
    reader.onerror = () => reject(new Error('Could not read this local file.'));
    reader.readAsDataURL(file);
  });
  return { extension, data };
}

export default function UploadForm({ onCompare, pending }) {
  const [reference, setReference] = useState(null);
  const [delivery, setDelivery] = useState(null);
  const [transcript, setTranscript] = useState('');
  const [error, setError] = useState('');
  async function submit(e) {
    e.preventDefault(); setError('');
    try {
      if (!transcript.trim()) throw new Error('Add the transcript spoken in both recordings.');
      await onCompare({ reference, delivery, transcript });
    } catch (issue) { setError(issue.message); }
  }
  return <form className="upload-form" onSubmit={submit}>
    <p className="form-note">Compare two recordings of the same English transcript. Each file: 0.5–30 seconds, up to 8 MB.</p>
    <div className="file-fields">
      <label>Reference audio<input disabled={pending} required type="file" accept=".wav,.mp3,.flac,.ogg,.webm" onChange={e => setReference(e.target.files[0])} /></label>
      <label>Delivery audio<input disabled={pending} required type="file" accept=".wav,.mp3,.flac,.ogg,.webm" onChange={e => setDelivery(e.target.files[0])} /></label>
    </div>
    <label>Shared transcript
      <textarea disabled={pending} required maxLength={1200} rows={3} value={transcript} onChange={e => setTranscript(e.target.value)} placeholder="The words spoken in both recordings. Spell numbers as words." />
    </label>
    <div className="upload-bottom">
      <label className="transcript-file">Or load a .txt transcript<input disabled={pending} type="file" accept=".txt,text/plain" onChange={async e => {
        const file = e.target.files[0];
        if (!file) return;
        if (file.size > 8_000) { setError('Transcript file is too large. Use at most 1,200 characters.'); return; }
        const text = await file.text();
        if (text.length > 1200) { setError('Use a transcript of at most 1,200 characters. The file was not truncated.'); return; }
        setTranscript(text); setError('');
      }} /></label>
      <button className="primary" disabled={pending} type="submit">{pending ? 'Comparing locally…' : 'Compare recordings'}</button>
    </div>
    <p className="privacy-note">Audio is processed on this machine. Temporary uploads are deleted after the comparison.</p>
    {error && <p className="error" role="alert">{error}</p>}
  </form>;
}
