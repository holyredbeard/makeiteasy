// Thin client wrapper for DeepSeek Chat Completions
// This file does NOT contain API keys. Expect the caller to provide baseURL and apiKey via env/runtime.

export async function convertRecipeWithDeepSeek({ apiKey, baseURL = 'https://api.deepseek.com', model = 'deepseek-chat', systemPrompt, userPayload }) {
  // Först: försök via backend-proxy (enklast & säkrast)
  try {
    const proxy = await fetch('http://localhost:8001/api/v1/llm/deepseek/convert', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ systemPrompt, userPayload, model, baseURL })
    });
    const data = await proxy.json();
    if (!proxy.ok) throw new Error(data?.detail || 'Proxy failed');
    return data;
  } catch (e) {
    console.warn('DeepSeek proxy unavailable:', e?.message);
    // Do not require a frontend API key. Surface the proxy error to the caller.
    throw new Error(e?.message || 'DeepSeek proxy unavailable');
  }
}

// Simple schema guard (runtime) – validates the essential keys/shape.
export function validateConversionSchema(obj) {
  const has = (k) => Object.prototype.hasOwnProperty.call(obj, k);
  if (!obj || typeof obj !== 'object') return false;
  const ok = has('title') && Array.isArray(obj.ingredients) && Array.isArray(obj.instructions) && has('nutritionPerServing') && has('compliance');
  return ok;
}


