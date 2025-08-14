import { detectLanguage } from '../lib/tts';
import { audio, getCached, setCached } from '../lib/tts';
import { init as piperInit, synthesize as piperSynthesize } from '../lib/tts/providers/piper';

export function useStepTTS() {
  const onStepClick = async (stepId: string, text: string, opts?: { overrideLocale?: 'sv-SE'|'en-US', rate?: number }) => {
    try {
      const locale = (opts?.overrideLocale) || detectLanguage(text);
      const cached = getCached(stepId);
      if (cached) { audio.play(cached.url); return; }
      // Piper synth
      await piperInit(locale as any);
      const wav = await piperSynthesize(text, { locale: locale as any, rate: opts?.rate || 1.0 });
      const url = URL.createObjectURL(wav);
      setCached(stepId, { url, locale: locale as any, createdAt: Date.now() });
      audio.play(url);
    } catch {}
  };
  return { onStepClick };
}


