import React, { useEffect, useMemo, useState } from 'react';
import { GROUPS, resolvePresets, getDisabledPresets, getVisibleAddOns } from './presetRules';

const PRESETS = [
  // Diet style
  'vegan','plant-based','vegetarian','pescetarian','omnivore','Mediterranean','whole30',
  // Add-ons
  'add-meat','add-fish','add-dairy',
  // Exclusions
  'dairy-free','gluten-free','nut-free','soy-free','egg-free','halal','kosher',
  // Macros
  'keto','low-carb','low-fat','high-protein','low-sodium','paleo'
];
const ALLERGENS = ['nuts','soy','gluten','dairy','eggs','fish','shellfish','sesame'];

export default function RecipeConvertPanel({ isOpen, onClose, onPreview, onApply, initialConstraints, busy, previewResult, PreviewRenderer, errorText, recipeId }) {
  const [presets, setPresets] = useState(initialConstraints?.presets || []);
  const [locale, setLocale] = useState(initialConstraints?.locale || 'sv');
  const [nutrition, setNutrition] = useState(initialConstraints?.nutrition || { maxCalories: null, minProtein: null, maxCarbs: null, maxFat: null, maxSodium: null });
  const [excludeAllergens, setExcludeAllergens] = useState(initialConstraints?.excludeAllergens || []);
  const [customTitle, setCustomTitle] = useState('');
  // Image preview state (post-Preview only)
  const [imageURL, setImageURL] = useState(null);
  const [imageBusy, setImageBusy] = useState(false);
  const [imageNotice, setImageNotice] = useState('');
  const [imageAspect, setImageAspect] = useState('1:1'); // '1:1' | '4:3' | '3:2' | '16:9'
  const [visibility, setVisibility] = useState('public');

  const togglePreset = (p) => setPresets((arr)=> arr.includes(p) ? arr.filter(x=>x!==p) : [...arr, p]);
  const toggleAllergen = (a) => setExcludeAllergens((arr)=> arr.includes(a) ? arr.filter(x=>x!==a) : [...arr, a]);

  const { resolved: normalizedPresets, adjustments } = useMemo(()=>resolvePresets(presets), [presets]);
  const disabledPresets = useMemo(()=>new Set(getDisabledPresets(normalizedPresets)), [normalizedPresets]);
  const visibleAddOns = useMemo(()=>new Set(getVisibleAddOns(normalizedPresets)), [normalizedPresets]);
  const constraints = useMemo(()=>({ presets: normalizedPresets, nutrition, excludeAllergens, locale }), [normalizedPresets, nutrition, excludeAllergens, locale]);

  // Generate image helper
  const generateImage = async () => {
    if (!previewResult) return;
    try {
      setImageBusy(true);
      setImageNotice('');
      const res = await fetch('http://localhost:8001/api/v1/images/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          recipe_id: recipeId,
          allow_placeholder: false,
          title: previewResult?.title || '',
          ingredients: previewResult?.ingredients || [],
          constraints,
          aspect: imageAspect,
          fast_mode: true
        })
      });
      const j = await res.json();
      if (!res.ok) {
        // In convert flow, fall back to original image silently
        if (res.status === 503) {
          setImageURL(null);
          setImageNotice('AI image failed, using original image.');
          return;
        }
        throw new Error(j?.detail || 'Image generation failed');
      }
      setImageURL(j.url);
    } catch (e) {
      setImageURL(null);
      setImageNotice(String(e?.message || 'Image generation failed'));
    } finally {
      setImageBusy(false);
    }
  };

  // Reset image state when preview changes; no auto generation
  useEffect(() => {
    if (!previewResult) {
      setImageURL(null);
      setImageNotice('');
    }
  }, [previewResult]);

  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-end sm:items-center justify-center p-0 sm:p-6" onClick={(e)=>{ if(e.target===e.currentTarget) onClose?.(); }}>
      <div className="bg-white w-full sm:max-w-[900px] sm:rounded-2xl sm:shadow-2xl sm:overflow-hidden rounded-t-2xl">
        <div className="p-4 sm:p-6 border-b flex items-center justify-between">
          <h3 className="text-lg sm:text-xl font-bold">Convert recipe</h3>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-700">✕</button>
        </div>

        <div className="p-4 sm:p-6 grid gap-6 max-h-[70vh] sm:max-h-[60vh] overflow-y-auto">
          <section>
            <h4 className="font-semibold mb-2">Presets</h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {Object.entries(GROUPS).map(([group, items]) => (
                <div key={group}>
                  <div className="text-xs uppercase text-gray-500 mb-2">{group.replace(/([A-Z])/g,' $1')}</div>
                  <div className="flex flex-wrap gap-2">
                    {items.filter(p => group !== 'addOns' ? true : visibleAddOns.has(p)).map(p => (
                      <button key={p}
                        onClick={()=>!disabledPresets.has(p) && togglePreset(p)}
                        disabled={disabledPresets.has(p)}
                        className={`px-2 py-1 rounded-full text-sm border ${normalizedPresets.includes(p) ? 'bg-green-50 text-green-700 border-green-200' : 'bg-gray-50 text-gray-700 border-gray-200'} ${disabledPresets.has(p) ? 'opacity-50 cursor-not-allowed' : ''}`}
                      >{p}</button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            {(adjustments.autoUnselected.length > 0 || adjustments.autoAdded.length > 0) && (
              <div className="mt-3 text-xs text-gray-600">
                {adjustments.autoUnselected.length > 0 && (
                  <div>Auto-unselected: <span className="text-gray-800">{adjustments.autoUnselected.join(', ')}</span></div>
                )}
                {adjustments.autoAdded.length > 0 && (
                  <div>Auto-added: <span className="text-gray-800">{adjustments.autoAdded.join(', ')}</span></div>
                )}
              </div>
            )}
          </section>

          {errorText && (
            <div className="rounded-lg border border-red-200 bg-red-50 text-red-700 p-3 text-sm">
              {errorText}
            </div>
          )}

          {/* Title and Visibility moved to Step 2 (after Preview) */}

          {previewResult && (
            <>
              <section>
                <h4 className="font-semibold mb-2">Preview</h4>
                {PreviewRenderer ? <PreviewRenderer result={previewResult} /> : null}
              </section>

              <section>
                <h4 className="font-semibold mb-2">Title (optional)</h4>
                <input value={customTitle} onChange={e=>setCustomTitle(e.target.value)} placeholder="Custom variant title" className="w-full border border-gray-300 rounded-lg px-3 py-2" />
                <p className="text-xs text-gray-500 mt-1">Leave empty to auto‑generate from diet and constraints.</p>
              </section>

              <section>
                <h4 className="font-semibold mb-2">Visibility</h4>
                <select value={visibility} onChange={e=>setVisibility(e.target.value)} className="border border-gray-300 rounded-lg px-3 py-2 text-sm">
                  <option value="public">Public (will appear in Variants)</option>
                  <option value="private">Private</option>
                </select>
              </section>
            </>
          )}

          {previewResult && (
            <section>
              <h4 className="font-semibold mb-2">Preview Image</h4>
              {/* Constraint chips above image */}
              <div className="mb-2 flex flex-wrap gap-2 text-xs">
                {(constraints.presets || []).map(p => (
                  <span key={`p-${p}`} className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">{p}</span>
                ))}
                {(() => {
                  const n = constraints.nutrition || {};
                  const chips = [];
                  if (n.maxCalories != null) chips.push(`≤ ${n.maxCalories} kcal`);
                  if (n.minProtein != null) chips.push(`≥ ${n.minProtein} g protein`);
                  if (n.maxCarbs != null) chips.push(`≤ ${n.maxCarbs} g carbs`);
                  if (n.maxFat != null) chips.push(`≤ ${n.maxFat} g fat`);
                  if (n.maxSodium != null) chips.push(`≤ ${n.maxSodium} mg sodium`);
                  return chips.map((label, i) => (
                    <span key={`n-${i}`} className="px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">{label}</span>
                  ));
                })()}
              </div>
              <div className="border rounded-lg p-3">
                <div className="flex items-center gap-2 mb-2">
                  <div className="flex items-center gap-2 text-sm">
                    <span className="text-gray-600">Aspect</span>
                    {['1:1','4:3','3:2','16:9'].map(a => (
                      <button key={a} disabled={imageBusy} onClick={()=>setImageAspect(a)} className={`px-2 py-1 rounded border text-xs ${imageAspect===a?'bg-gray-900 text-white border-gray-900':'bg-white text-gray-800'}`}>{a}</button>
                    ))}
                  </div>
                  <button disabled={imageBusy} onClick={()=>generateImage()} className="ml-auto px-3 py-1.5 rounded-lg bg-blue-600 text-white text-sm">{imageURL ? 'Regenerate' : 'Generate image'}</button>
                </div>
                {imageBusy && (
                  <p className="text-sm text-gray-600">Generating recipe image...</p>
                )}
                {imageURL && !imageBusy && (
                  <img src={`http://localhost:8001${imageURL}`} alt="Preview of converted recipe" className="max-h-64 rounded" />
                )}
                {(!imageURL && !imageBusy) && (
                  <p className="text-gray-500 text-sm">Default is to use the original photo. Click “Generate image” to create an AI image based on the converted recipe.</p>
                )}
                {imageNotice && (<p className="text-xs text-amber-600 mt-2">{imageNotice}</p>)}
              </div>
              <div className="mt-2 text-xs text-gray-500">Switch to original photo in Apply-step if needed.</div>
            </section>
          )}

          <section>
            <h4 className="font-semibold mb-2">Nutrition targets (per serving)</h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {[
                ['maxCalories','Max kcal'],
                ['minProtein','Min protein (g)'],
                ['maxCarbs','Max carbs (g)'],
                ['maxFat','Max fat (g)'],
                ['maxSodium','Max sodium (mg)']
              ].map(([key,label]) => (
                <label key={key} className="text-sm">
                  <span className="block text-gray-600 mb-1">{label}</span>
                  <input type="number" step="1" className="w-full border border-gray-300 rounded-lg px-3 py-2"
                    value={nutrition?.[key] ?? ''}
                    onChange={(e)=>setNutrition(n=>({ ...n, [key]: e.target.value === '' ? null : Number(e.target.value) }))}
                  />
                </label>
              ))}
            </div>
          </section>

          <section>
            <h4 className="font-semibold mb-2">Allergens to exclude</h4>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {ALLERGENS.map(a => (
                <label key={a} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={excludeAllergens.includes(a)} onChange={()=>toggleAllergen(a)} />
                  <span>{a}</span>
                </label>
              ))}
            </div>
          </section>

          <section>
            <h4 className="font-semibold mb-2">Locale</h4>
            <select value={locale} onChange={e=>setLocale(e.target.value)} className="border border-gray-300 rounded-lg px-3 py-2">
              <option value="sv">sv</option>
              <option value="en">en</option>
            </select>
          </section>
        </div>

        <div className="p-4 sm:p-6 border-t flex flex-col sm:flex-row gap-3 sm:justify-end">
          <button disabled={busy} onClick={()=>onPreview?.(constraints)} className="px-4 py-2 rounded-lg border border-gray-300 bg-white hover:bg-gray-50">{busy ? 'Loading…' : 'Preview'}</button>
          <button disabled={busy} onClick={()=>{
            const effectiveSource = imageURL ? 'ai' : 'original';
            onApply?.({ ...constraints, customTitle, imageSource: effectiveSource, imageURL, visibility });
          }} className="px-4 py-2 rounded-lg bg-green-600 text-white hover:bg-green-700">{busy ? 'Saving…' : 'Apply & Save as Variant'}</button>
          <button disabled={busy} onClick={onClose} className="px-4 py-2 rounded-lg bg-gray-100">Close</button>
        </div>
      </div>
    </div>
  );
}


// Side-effects and helpers placed after component definition using function hoisting is not available;
// so define generateImage inside the component via function expression with access to state via closure.
