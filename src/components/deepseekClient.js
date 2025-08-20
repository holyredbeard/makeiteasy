// Thin client wrapper for DeepSeek Chat Completions
// This file does NOT contain API keys. Expect the caller to provide baseURL and apiKey via env/runtime.

export async function convertRecipeWithDeepSeek({ apiKey, baseURL = 'https://api.deepseek.com', model = 'deepseek-chat', systemPrompt, userPayload, fast = true, timeoutMs = 120000 }) {
  // Först: försök via backend-proxy (enklast & säkrast)
  const controller = timeoutMs && timeoutMs > 0 ? new AbortController() : null;
  const id = controller ? setTimeout(() => controller.abort(), Math.max(5000, timeoutMs)) : null;
  const startedAt = Date.now();
  console.info('[Convert] Preview → calling proxy (fast=%s)...', fast);
  try {
    const proxy = await fetch('http://localhost:8000/api/v1/llm/deepseek/convert', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      ...(controller ? { signal: controller.signal } : {}),
      body: JSON.stringify({ systemPrompt, userPayload, model, baseURL, fast })
    });
    const text = await proxy.text();
    let data;
    try { data = JSON.parse(text); } catch { data = null; }
    if (!proxy.ok) {
      const detail = (data && (data.detail || data.error)) || text || 'Proxy failed';
      throw new Error(detail);
    }
    console.info('[Convert] Proxy OK in %dms', Date.now() - startedAt);
    return data;
  } catch (e) {
    if (e?.name === 'AbortError') {
      console.error('[Convert] Preview timeout after %dms', Date.now() - startedAt);
      // Do not surface as timeout; mark as proxy unavailable so UI can retry
      throw new Error('DeepSeek proxy timeout');
    }
    console.warn('DeepSeek proxy error:', e?.message || e);
    // Surface the proxy error to the caller.
    throw new Error(e?.message || 'DeepSeek proxy unavailable');
  } finally {
    if (id) clearTimeout(id);
  }
}

// Simple schema guard (runtime) – validates the essential keys/shape.
export function validateConversionSchema(obj) {
  const has = (k) => Object.prototype.hasOwnProperty.call(obj, k);
  if (!obj || typeof obj !== 'object') return false;
  const ok = has('title') && Array.isArray(obj.ingredients) && Array.isArray(obj.instructions) && has('nutritionPerServing') && has('compliance');
  return ok;
}


