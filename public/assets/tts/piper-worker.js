/* Minimal Piper worker stub for verification.
   Replaces real TTS with a short generated WAV tone so we can ensure
   worker loading, messaging and audio pipeline work end-to-end.
   To switch to real Piper WASM, replace this file with the actual worker. */

// Keep last locale/model for debug
let lastLocale = 'sv-SE';
let lastModelBase = '';

function makeWav(samples, sampleRate) {
  // PCM 16-bit mono WAV
  const numSamples = samples.length;
  const buffer = new ArrayBuffer(44 + numSamples * 2);
  const view = new DataView(buffer);
  const writeString = (offset, str) => { for (let i=0;i<str.length;i++) view.setUint8(offset+i, str.charCodeAt(i)); };
  writeString(0, 'RIFF');
  view.setUint32(4, 36 + numSamples * 2, true);
  writeString(8, 'WAVE');
  writeString(12, 'fmt ');
  view.setUint32(16, 16, true); // PCM chunk size
  view.setUint16(20, 1, true);  // PCM
  view.setUint16(22, 1, true);  // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // bytes/sec
  view.setUint16(32, 2, true);  // block align
  view.setUint16(34, 16, true); // bits/sample
  writeString(36, 'data');
  view.setUint32(40, numSamples * 2, true);
  let offset = 44;
  for (let i = 0; i < numSamples; i++) {
    let s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s * 0x7fff, true);
    offset += 2;
  }
  return buffer;
}

function synthTone(durationSec = 0.35, freq = 440, sampleRate = 22050) {
  const N = Math.floor(sampleRate * durationSec);
  const out = new Float32Array(N);
  for (let i=0;i<N;i++) {
    // soft envelope
    const t = i / sampleRate;
    const env = Math.min(1, t*20) * Math.min(1, (durationSec - t) * 25);
    out[i] = Math.sin(2 * Math.PI * freq * t) * 0.3 * env;
  }
  return makeWav(out, sampleRate);
}

self.onmessage = async (e) => {
  const msg = e.data || {};
  try {
    if (msg.type === 'init') {
      lastLocale = msg.locale || 'sv-SE';
      lastModelBase = msg.modelBaseUrl || '';
      // ack init with small payload so main thread proceeds
      self.postMessage({ __piper: 'ok', payload: new ArrayBuffer(0) });
      return;
    }
    if (msg.type === 'synthesize') {
      // Generate a short tone; pick a different frequency per locale
      const tone = synthTone(0.35, msg.locale === 'en-US' ? 660 : 440, 22050);
      self.postMessage({ __piper: 'ok', payload: tone }, [tone]);
      return;
    }
  } catch (err) {
    self.postMessage({ __piper: 'error', message: String(err && err.message || err) });
  }
};


