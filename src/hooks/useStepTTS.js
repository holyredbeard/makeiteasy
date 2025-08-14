import { detectLanguage } from '../lib/tts/index.js';
import { audio, getCached, setCached } from '../lib/tts/index.js';
import { init as piperInit, synthesize as piperSynthesize } from '../lib/tts/providers/piper.js';

export function useStepTTS() {
  const onStepClick = async (stepId, text, opts = {}) => {
    try {
      const locale = opts.overrideLocale || detectLanguage(text);
      const cached = getCached(stepId);
      if (cached) { audio.play(cached.url); return; }
      await piperInit(locale);
      const wav = await piperSynthesize(text, { locale, rate: opts.rate || 1.0 });
      const url = URL.createObjectURL(wav);
      setCached(stepId, { url, locale, createdAt: Date.now() });
      audio.play(url);
      return;
    } catch (e) {
      console.error('[TTS] Piper synth failed:', e);
      alert('TTS misslyckades att starta (Piper). Kontrollera worker och modeller.');
    }
  };
  return { onStepClick };
}


