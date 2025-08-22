import React, { useEffect, useMemo, useState } from 'react';
import { GROUPS, resolvePresets, getDisabledPresets, getVisibleAddOns, getLockedPresets, labelForPreset } from './presetRules';
import Spinner from './Spinner';

const STATIC_BASE = 'http://localhost:8000';

const PRESETS = [
  // Diet style
  'vegan','plant-based','vegetarian','pescetarian','omnivore','Mediterranean','whole30','zesty','seafood',
  // Add-ons
  'add-meat','add-fish','add-dairy',
  // Exclusions
  'dairy-free','gluten-free','nut-free','soy-free','egg-free','halal','kosher',
  // Macros
  'keto','low-carb','low-fat','high-protein','low-sodium','paleo'
];
const ALLERGENS = ['nuts','soy','gluten','dairy','eggs','fish','shellfish','sesame'];

export default function RecipeConvertPanel({ isOpen, onClose, onPreview, onApply, onBack, initialConstraints, busy, previewResult, PreviewRenderer, errorText, recipeId, baseTitle, originalImage }) {
  const [presets, setPresets] = useState(initialConstraints?.presets || []);
  const [locale, setLocale] = useState(initialConstraints?.locale || 'sv');
  const [nutrition, setNutrition] = useState(initialConstraints?.nutrition || {
    minCalories: null, maxCalories: null,
    minProtein: null, maxProtein: null,
    minCarbs: null,   maxCarbs: null,
    minFat: null,     maxFat: null,
  });
  const [excludeAllergens, setExcludeAllergens] = useState(initialConstraints?.excludeAllergens || []);
  const [customTitle, setCustomTitle] = useState('');
  const [tolerance, setTolerance] = useState(5); // percent
  // Resolve normalized presets early so we can derive a title suggestion before Preview
  const { resolved: normalizedPresets, adjustments } = useMemo(()=>resolvePresets(presets), [presets]);
  // Prefill title: proposed from preview, else auto from base + constraints
  useEffect(() => {
    if (previewResult?.title) {
      // Ensure diet + up to two constraint chips (kcal/protein) in suffix
      const dietOrder = ['vegan','plant-based','vegetarian','pescetarian','omnivore'];
      const dietRaw = normalizedPresets.find(p => dietOrder.includes(p)) || '';
      const diet = dietRaw ? (dietRaw === 'plant-based' ? 'Plant-based' : dietRaw.replace(/^./, c=>c.toUpperCase())) : '';
      const n = nutrition || {};
      const chips = [];
      if (n.maxCalories != null) chips.push(`≤${n.maxCalories} kcal`);
      if (n.minProtein != null) chips.push(`≥${n.minProtein} g protein`);
      const extras = chips.slice(0, 2);
      const suffixParts = [diet, ...extras].filter(Boolean);
      const titleOut = suffixParts.length ? `${previewResult.title} (${suffixParts.join(', ')})` : previewResult.title;
      setCustomTitle(titleOut.slice(0,70));
      return;
    }
    // Build a lightweight suggested title before preview
    const dietOrder = ['vegan','plant-based','vegetarian','pescetarian','omnivore'];
    const dietRaw = normalizedPresets.find(p => dietOrder.includes(p)) || '';
    const diet = dietRaw ? (dietRaw === 'plant-based' ? 'Plant-based' : dietRaw.replace(/^./, c=>c.toUpperCase())) : '';
    const n = nutrition || {};
    const chips = [];
    if (n.maxCalories != null) chips.push(`≤${n.maxCalories} kcal`);
    if (n.minProtein != null) chips.push(`≥${n.minProtein} g protein`);
    const extras = chips.slice(0,2);
    const suffix = [diet, ...extras].filter(Boolean).join(', ');
    const base = (baseTitle || '').trim();
    if (base && suffix) setCustomTitle(`${base} (${suffix})`.slice(0,70));
    else if (base) setCustomTitle(base.slice(0,70));
  }, [previewResult, baseTitle, normalizedPresets, nutrition]);
  // Image preview state (post-Preview only)
  const [imageURL, setImageURL] = useState(null);
  const [imageBusy, setImageBusy] = useState(false);
  const [imageNotice, setImageNotice] = useState('');
  const [imageAspect, setImageAspect] = useState('1:1'); // '1:1' | '4:3' | '3:2' | '16:9'
  const [visibility, setVisibility] = useState('public');
  const [aiImages, setAiImages] = useState([]); // [{url, meta, aspect, index}]
  const [selectedIndex, setSelectedIndex] = useState(0); // 0 = original by default
  const [generatedCount, setGeneratedCount] = useState(0);
  const [generateRounds, setGenerateRounds] = useState(0); // first batch counts as 1
  const initialRef = React.useRef({
    presets: initialConstraints?.presets || [],
    nutrition: initialConstraints?.nutrition || { maxCalories: null, minProtein: null, maxCarbs: null, maxFat: null },
    excludeAllergens: initialConstraints?.excludeAllergens || [],
    locale: initialConstraints?.locale || 'sv'
  });
  const [showConfirm, setShowConfirm] = useState(false);

  const togglePreset = (p) => setPresets((arr)=> {
    const isDiet = GROUPS.dietStyle.includes(p);
    if (!arr.includes(p)) {
      // selecting p
      if (isDiet) {
        // Exclusivity: remove any other diet styles
        const next = arr.filter(x => !GROUPS.dietStyle.includes(x));
        next.push(p);
        return next;
      }
      return [...arr, p];
    } else {
      // unselecting p
      return arr.filter(x => x !== p);
    }
  });
  const toggleAllergen = (a) => setExcludeAllergens((arr)=> arr.includes(a) ? arr.filter(x=>x!==a) : [...arr, a]);

  const disabledPresets = useMemo(()=>new Set(getDisabledPresets(normalizedPresets)), [normalizedPresets]);
  const lockedPresets = useMemo(()=>new Set(getLockedPresets(normalizedPresets)), [normalizedPresets]);
  const visibleAddOns = useMemo(()=>new Set(getVisibleAddOns(normalizedPresets)), [normalizedPresets]);
  const constraints = useMemo(()=>({ presets: normalizedPresets, nutrition, excludeAllergens, locale }), [normalizedPresets, nutrition, excludeAllergens, locale]);
  const canConvert = useMemo(() => {
    // Enable if any preset selected OR language changed from initial
    const changedLocale = locale !== (initialRef.current?.locale || 'sv');
    return (normalizedPresets.length > 0) || changedLocale;
  }, [normalizedPresets, locale]);

  const isDirty = useMemo(() => {
    const a = new Set((initialRef.current.presets || []).map(x=>String(x).toLowerCase().replace(/\s+/g,'-')));
    const b = new Set((presets || []).map(x=>String(x).toLowerCase().replace(/\s+/g,'-')));
    const presetsChanged = a.size !== b.size || [...b].some(x=>!a.has(x));
    const locChanged = locale !== (initialRef.current.locale || 'sv');
    const n0 = initialRef.current.nutrition || {};
    const n1 = nutrition || {};
    const nutritionChanged = ['minCalories','maxCalories','minProtein','maxProtein','minCarbs','maxCarbs','minFat','maxFat']
      .some(k => (n0[k] ?? null) !== (n1[k] ?? null));
    const e0 = new Set(initialRef.current.excludeAllergens || []);
    const e1 = new Set(excludeAllergens || []);
    const allergenChanged = e0.size !== e1.size || [...e1].some(x=>!e0.has(x));
    return presetsChanged || locChanged || nutritionChanged || allergenChanged;
  }, [presets, locale, nutrition, excludeAllergens]);

  const handleRequestClose = () => {
    if (isDirty) setShowConfirm(true); else onClose?.();
  };

  // Feasibility checker (client-side, per-serving)
  const feasibility = useMemo(()=>{
    const n = nutrition || {};
    const kcalMin = n.minCalories != null ? Number(n.minCalories) : null;
    const kcalMax = n.maxCalories != null ? Number(n.maxCalories) : null;
    const protMin = n.minProtein != null ? Number(n.minProtein) : 0;
    const carbMin = n.minCarbs != null ? Number(n.minCarbs) : 0;
    const fatMin  = n.minFat  != null ? Number(n.minFat)  : 0;
    const protMax = n.maxProtein != null ? Number(n.maxProtein) : null;
    const carbMax = n.maxCarbs   != null ? Number(n.maxCarbs)   : null;
    const fatMax  = n.maxFat     != null ? Number(n.maxFat)     : null;

    const lowestPossible = 4 * (protMin + carbMin) + 9 * fatMin;
    const highestPossible = (
      (protMax != null ? 4 * protMax : 0) +
      (carbMax != null ? 4 * carbMax : 0) +
      (fatMax  != null ? 9 * fatMax  : 0)
    );
    const highestFinite = (protMax == null && carbMax == null && fatMax == null) ? Infinity : highestPossible;

    if (kcalMax != null && lowestPossible > kcalMax) return { status: 'impossible', reason: 'min macros exceed kcal max' };
    if (kcalMin != null && highestFinite < kcalMin) return { status: 'impossible', reason: 'max macros below kcal min' };

    // Tight vs possible
    const tol = Math.max(0, Number(tolerance) || 0) / 100;
    let tight = false;
    if (kcalMax != null) {
      const margin = Math.max(0, kcalMax - lowestPossible);
      const thresh = kcalMax * tol;
      if (margin <= thresh) tight = true;
    }
    if (!tight && kcalMin != null && isFinite(highestFinite)) {
      const margin = Math.max(0, highestFinite - kcalMin);
      const thresh = kcalMin * tol;
      if (margin <= thresh) tight = true;
    }
    return { status: tight ? 'tight' : 'possible', lowestPossible, highestPossible: highestFinite };
  }, [nutrition, tolerance]);

  const disableHint = (p) => {
    if (lockedPresets.has(p)) return 'Locked by Vegan';
    if (!disabledPresets.has(p)) return undefined;
    if (p === 'low-carb' && normalizedPresets.includes('keto')) return 'Included in Keto';
    if (normalizedPresets.includes('vegan')) return 'Disabled by selected diet: Vegan';
    if (normalizedPresets.includes('plant-based')) return 'Disabled by selected diet: Plant-based';
    if (normalizedPresets.includes('vegetarian')) return 'Disabled by selected diet: Vegetarian';
    if (normalizedPresets.includes('pescetarian')) return 'Disabled by selected diet: Pescetarian';
    if (normalizedPresets.includes('dairy-free') && p === 'add-dairy') return 'Disabled by exclusion: dairy-free';
    if (normalizedPresets.includes('fish-free') && p === 'add-fish') return 'Disabled by exclusion: fish-free';
    return 'Disabled';
  };

  // Generate image helper
  const generateImage = async () => {
    if (!previewResult) return;
    try {
      setImageBusy(true);
      setImageNotice('');
      const res = await fetch('http://localhost:8000/api/v1/images/generate', {
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

  // Batch generator: fetch 3 images sequentially; respects aspect and preview data
  const generateImageBatch = async (count = 3) => {
    if (!previewResult) return;
    if (generateRounds >= 3) return;
    const started = Date.now();
    setImageBusy(true);
    try {
      const newImages = [];
      for (let i = 0; i < count; i++) {
        const res = await fetch('http://localhost:8000/api/v1/images/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            recipe_id: recipeId,
            allow_placeholder: !originalImage,
            title: (previewResult?.title || ''),
            ingredients: previewResult?.ingredients || [],
            constraints,
            aspect: imageAspect,
            fast_mode: true,
            mode: originalImage ? 'img2img' : 'txt2img',
            image_url: originalImage || null
          })
        });
        const j = await res.json();
        if (!res.ok) throw new Error(j?.detail || 'Image generation failed');
        newImages.push({ url: j.url, aspect: imageAspect, meta: { provider: 'replicate', model: originalImage ? 'stability-ai/sdxl(img2img)' : 'black-forest-labs/flux-schnell' } });
      }
      setAiImages(prev => [...prev, ...newImages]);
      setGeneratedCount(c => c + newImages.length);
      setGenerateRounds(r => r + 1);
      if (selectedIndex < 0 && (originalImage == null)) setSelectedIndex(1); // pick first AI if no original
    } catch (e) {
      setImageNotice(String(e?.message || 'Image generation failed'));
    } finally {
      const ms = Date.now() - started;
      console.info('[Images] batch generated', count, 'in', ms, 'ms');
      setImageBusy(false);
    }
  };

  // Helper: infer aspect from original image once
  useEffect(()=>{
    if (!originalImage) return;
    const img = new Image();
    img.onload = () => {
      const r = img.width / img.height;
      const diffs = [
        {label:'1:1', val:1},
        {label:'4:3', val:4/3},
        {label:'3:2', val:3/2},
        {label:'16:9', val:16/9},
      ].map(x => ({label:x.label, d: Math.abs(r - x.val)}));
      diffs.sort((a,b)=>a.d-b.d);
      setImageAspect(diffs[0].label);
    };
    img.src = originalImage.startsWith('http') ? originalImage : `http://localhost:8000${originalImage}`;
  }, [originalImage]);

  // Reset image state when preview changes; no auto generation
  useEffect(() => {
    if (!previewResult) {
      setImageURL(null);
      setImageNotice('');
      setAiImages([]);
      setSelectedIndex(originalImage ? 0 : -1);
      setGeneratedCount(0);
      setGenerateRounds(0);
    }
  }, [previewResult]);

  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-end sm:items-center justify-center p-0 sm:p-6" onClick={(e)=>{ if(e.target===e.currentTarget) handleRequestClose(); }}>
      <div className="bg-white w-full sm:max-w-[900px] sm:rounded-2xl sm:shadow-2xl sm:overflow-hidden rounded-t-2xl">
        <div className="p-4 sm:p-6 border-b flex items-center justify-between bg-orange-500 text-white">
          <h3 className="text-lg sm:text-xl font-bold text-white">Convert recipe</h3>
          <button onClick={handleRequestClose} className="text-white hover:text-white/90">✕</button>
        </div>

        <div className="p-4 sm:p-6 grid gap-6 max-h-[70vh] sm:max-h-[60vh] overflow-y-auto">
          {!previewResult && (
          <>
            {/** Active color mapping for diet chips */}
            {(() => null)()}
            {/* Language at top */}
            <section className="border border-gray-200 rounded-2xl p-4 bg-white/80 shadow-[4px_4px_0_rgba(0,0,0,0.06)] hover:shadow-[6px_6px_0_rgba(0,0,0,0.08)] hover:-translate-y-0.5 transition-transform transition-shadow duration-200 ease-out">
              <h4 className="text-sm font-semibold tracking-wide text-gray-700 mb-2">Language & Region</h4>
              <select value={locale} onChange={e=>setLocale(e.target.value)} className="border border-gray-300 rounded-lg px-3 py-2">
                <option value="sv">Swedish (sv)</option>
                <option value="en">English (en)</option>
              </select>
            </section>
            <section className="border border-gray-200 rounded-2xl p-4 bg-white/80 shadow-[4px_4px_0_rgba(0,0,0,0.06)] hover:shadow-[6px_6px_0_rgba(0,0,0,0.08)] hover:-translate-y-0.5 transition-transform transition-shadow duration-200 ease-out">
              <h4 className="text-sm font-semibold tracking-wide text-gray-700 mb-2">Diet Style</h4>
              <div className="flex flex-wrap gap-2 mb-2">
                {GROUPS.dietStyle.map(p => (
                  <button key={`diet-${p}`}
                    onClick={()=>{ togglePreset(p); }}
                    className={`px-3 py-1.5 rounded-full text-sm border ${normalizedPresets.includes(p)
                                                ? (p==='vegan' ? 'bg-emerald-600 text-white border-emerald-600'
            : p==='vegetarian' ? 'bg-lime-600 text-white border-lime-600'
            : p==='pescetarian' ? 'bg-sky-600 text-white border-sky-600'
            : p==='zesty' ? 'bg-yellow-500 text-white border-yellow-500'
            : p==='seafood' ? 'bg-blue-600 text-white border-blue-600'
            : p==='fastfood' ? 'bg-orange-500 text-white border-orange-500'
            : 'bg-green-600 text-white border-green-600')
                      : 'bg-gray-50 text-gray-700 border-gray-200'} cursor-pointer hover:opacity-90 transition-opacity hover:scale-105`}
                  >
                                    {p.toLowerCase() === 'vegan' && <i className="fa-solid fa-leaf mr-1"></i>}
                {p.toLowerCase() === 'vegetarian' && <i className="fa-solid fa-carrot mr-1"></i>}
                {p.toLowerCase() === 'zesty' && <i className="fa-solid fa-lemon mr-1"></i>}
                {p.toLowerCase() === 'pescetarian' && <i className="fa-solid fa-fish mr-1"></i>}
                {p.toLowerCase() === 'seafood' && <i className="fa-solid fa-shrimp mr-1"></i>}
                {p.toLowerCase() === 'fastfood' && <i className="fa-solid fa-burger mr-1"></i>}
                    {labelForPreset(p)}
                  </button>
                ))}
              </div>
            </section>

            <section className="border border-gray-200 rounded-2xl p-4 bg-white/80 shadow-[4px_4px_0_rgba(0,0,0,0.06)] hover:shadow-[6px_6px_0_rgba(0,0,0,0.08)] hover:-translate-y-0.5 transition-transform transition-shadow duration-200 ease-out">
              <h4 className="text-sm font-semibold tracking-wide text-gray-700 mb-2">Add Ons</h4>
              <div className="flex flex-wrap gap-2">
                {GROUPS.addOns.filter(p => visibleAddOns.has(p)).map(p => (
                  <button key={`add-${p}`}
                    onClick={()=>{
                      if (disabledPresets.has(p)) return;
                      if (lockedPresets.has(p)) return;
                      togglePreset(p);
                    }}
                    disabled={disabledPresets.has(p) || lockedPresets.has(p)}
                    title={disableHint(p)}
                    className={`px-3 py-1.5 rounded-full text-sm border ${normalizedPresets.includes(p)
                      ? (p==='add-fish' ? 'bg-sky-600 text-white border-sky-600'
                         : 'bg-emerald-600 text-white border-emerald-600')
                      : 'bg-gray-50 text-gray-700 border-gray-200'} ${(disabledPresets.has(p) || lockedPresets.has(p)) ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >{labelForPreset(p)}</button>
                ))}
              </div>
            </section>

            <section className="border border-gray-200 rounded-2xl p-4 bg-white/80 shadow-[4px_4px_0_rgba(0,0,0,0.06)] hover:shadow-[6px_6px_0_rgba(0,0,0,0.08)] hover:-translate-y-0.5 transition-transform transition-shadow duration-200 ease-out">
              <h4 className="text-sm font-semibold tracking-wide text-gray-700 mb-2">Exclusions</h4>
              <div className="flex flex-wrap gap-2">
                {GROUPS.exclusions.map(p => (
                  <button key={`ex-${p}`}
                    onClick={()=>{ if (!lockedPresets.has(p)) togglePreset(p); }}
                    disabled={lockedPresets.has(p)}
                    title={lockedPresets.has(p) ? 'Locked by Vegan' : undefined}
                    className={`px-3 py-1.5 rounded-full text-sm border ${normalizedPresets.includes(p)
                      ? (p.includes('fish') ? 'bg-sky-600 text-white border-sky-600' : 'bg-emerald-600 text-white border-emerald-600')
                      : 'bg-gray-50 text-gray-700 border-gray-200'} ${lockedPresets.has(p) ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >{labelForPreset(p)}</button>
                ))}
              </div>
            </section>

            <section className="border border-gray-200 rounded-2xl p-4 bg-white/80 shadow-[4px_4px_0_rgba(0,0,0,0.06)] hover:shadow-[6px_6px_0_rgba(0,0,0,0.08)] hover:-translate-y-0.5 transition-transform transition-shadow duration-200 ease-out">
              <h4 className="text-sm font-semibold tracking-wide text-gray-700 mb-2">Macros</h4>
              <div className="flex flex-wrap gap-2">
              {GROUPS.macros.map(p => (
                <button key={`mac-${p}`}
                    onClick={()=>{ if (!disabledPresets.has(p)) togglePreset(p); }}
                    disabled={disabledPresets.has(p)}
                    title={(p==='low-carb' && normalizedPresets.includes('keto')) ? 'Included in Keto' : undefined}
                  className={`px-3 py-1.5 rounded-full text-sm border ${normalizedPresets.includes(p) ? 'bg-green-50 text-green-700 border-green-200' : 'bg-gray-50 text-gray-700 border-gray-200'} ${disabledPresets.has(p) ? 'opacity-50 cursor-not-allowed' : ''}`}
                >{labelForPreset(p)}</button>
                ))}
              </div>
            </section>

            <section className="border border-gray-200 rounded-2xl p-4 bg-white/80 shadow-[4px_4px_0_rgba(0,0,0,0.06)] hover:shadow-[6px_6px_0_rgba(0,0,0,0.08)] hover:-translate-y-0.5 transition-transform transition-shadow duration-200 ease-out">
              <h4 className="text-sm font-semibold tracking-wide text-gray-700 mb-2">Programs</h4>
            <div className="flex flex-wrap gap-2">
              {GROUPS.programs.map(p => (
                <button key={`prog-${p}`}
                    onClick={()=>togglePreset(p)}
                  className={`px-3 py-1.5 rounded-full text-sm border ${normalizedPresets.includes(p) ? 'bg-green-50 text-green-700 border-green-200' : 'bg-gray-50 text-gray-700 border-gray-200'}`}
                >{labelForPreset(p)}</button>
              ))}
            </div>
          </section>

            {(adjustments.autoUnselected.length > 0 || adjustments.autoAdded.length > 0 || (adjustments.autoDisabled && adjustments.autoDisabled.length > 0)) && (
              <div className="mt-3 text-xs text-gray-600">
                {adjustments.autoDisabled && adjustments.autoDisabled.length > 0 && (
                  <div>Auto-disabled: <span className="text-gray-800">{adjustments.autoDisabled.join(', ')}</span></div>
                )}
                {adjustments.autoAdded.length > 0 && (
                  <div>Auto-selected: <span className="text-gray-800">{adjustments.autoAdded.join(', ')}</span></div>
                )}
                {adjustments.autoUnselected.length > 0 && (
                  <div>Auto-unselected: <span className="text-gray-800">{adjustments.autoUnselected.join(', ')}</span></div>
                )}
              </div>
            )}

            {/* Clear all moved to bottom (below Nutrition Targets) */}
          </>
          )}

          {errorText && (
            <div className="rounded-lg border border-red-200 bg-red-50 text-red-700 p-3 text-sm">
              {errorText}
            </div>
          )}

          {/* Title and Visibility moved to Step 2 (after Preview) */}

          {previewResult && (
            <> 
              {/* Preview header removed per request */}

              {/* Image gallery (top of preview) */}
              <section className="border border-gray-200 rounded-2xl p-4 bg-white/80 shadow-[4px_4px_0_rgba(0,0,0,0.06)] hover:shadow-[6px_6px_0_rgba(0,0,0,0.08)] hover:-translate-y-0.5 transition-transform transition-shadow duration-200 ease-out">
                <div className="flex items-center gap-3 justify-between mb-3">
                  <div className="text-sm text-gray-700 font-semibold">Images</div>
                  <div className="flex items-center gap-2">
                    <span className="text-gray-600 text-sm">Aspect</span>
                    {['1:1','4:3','3:2','16:9'].map(a => (
                      <button key={a} disabled={imageBusy} onClick={()=>setImageAspect(a)} className={`px-2 py-1 rounded border text-xs ${imageAspect===a?'bg-gray-900 text-white border-gray-900':'bg-white text-gray-800'}`}>{a}</button>
                    ))}
                    <button disabled={imageBusy || generateRounds>=3} title={generateRounds>=3? 'Limit reached' : ''} onClick={()=>generateImageBatch(3)} className="ml-2 px-3 py-1.5 rounded-lg bg-blue-600 text-white text-sm">{aiImages.length ? 'Generate more' : 'Generate image'}</button>
                  </div>
                </div>
                <div className="flex gap-3 overflow-x-auto">
                  {/* Original card */}
                  <div className={`relative inline-block border rounded ${selectedIndex===0?'ring-2 ring-blue-500':''}`} onClick={()=>setSelectedIndex(0)}>
                    {originalImage ? (
                      <img src={originalImage.startsWith('http') ? originalImage : `${STATIC_BASE}${originalImage}`} alt="Original" className="w-56 h-40 object-cover rounded aspect-square" />
                    ) : (
                      <div className="w-56 h-40 flex items-center justify-center text-sm text-gray-500 bg-gray-50 rounded">No original</div>
                    )}
                    <span className="absolute top-2 left-2 text-xs px-2 py-0.5 rounded-full bg-gray-800/80 text-white">Original</span>
                    {selectedIndex===0 && <span className="absolute bottom-2 left-2 text-xs px-2 py-0.5 rounded-full bg-blue-600 text-white">Selected</span>}
                  </div>
                  {/* AI cards */}
                  {aiImages.map((img, idx) => (
                    <div key={idx} className={`relative inline-block border rounded ${selectedIndex===idx+1?'ring-2 ring-blue-500':''}`} onClick={()=>setSelectedIndex(idx+1)}>
                      <img src={`${STATIC_BASE}${img.url}`} alt={`AI ${idx+1}`} className="w-56 h-40 object-cover rounded aspect-square" />
                      <span className="absolute top-2 left-2 text-xs px-2 py-0.5 rounded-full bg-gray-800/80 text-white">AI #{idx+1}</span>
                      <span className="absolute top-2 right-2 text-xs px-2 py-0.5 rounded-full bg-white/90 text-gray-800 border">{img.aspect}</span>
                      {selectedIndex===idx+1 && <span className="absolute bottom-2 left-2 text-xs px-2 py-0.5 rounded-full bg-blue-600 text-white">Selected</span>}
                    </div>
                  ))}
                </div>
                <div className="mt-2 text-xs text-gray-500">Original image and generated AI alternatives are shown at the same size. Click to select.</div>
              </section>

              <section>
                <h4 className="font-semibold mb-2">Title</h4>
                <input value={customTitle} onChange={e=>setCustomTitle(e.target.value)} placeholder="Custom variant title" className="w-full border border-gray-300 rounded-lg px-3 py-2" />
              </section>

              {/* Substitutions (collapsible) */}
              <CollapsibleSubstitutions substitutions={previewResult?.substitutions} />

              {/* Ingredients (updated) */}
              <section>
                <div className="flex items-center gap-2 mb-2">
                  <h4 className="font-semibold">Ingredients (updated)</h4>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">Updated</span>
                </div>
                <ul className="list-disc pl-5 text-sm space-y-1">
                  {(previewResult?.ingredients || []).map((line, i) => (<li key={i}>{line}</li>))}
                </ul>
              </section>

              {/* Instructions (updated) */}
              <section>
                <div className="flex items-center gap-2 mb-2">
                  <h4 className="font-semibold">Instructions (updated)</h4>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">Updated</span>
                </div>
                <ol className="list-decimal pl-5 text-sm space-y-1">
                  {(previewResult?.instructions || []).map((line, i) => (<li key={i}>{line}</li>))}
                </ol>
              </section>

              {/* Nutrition per serving (read-only) */}
              <section>
                <h4 className="font-semibold mb-2">Nutrition per serving</h4>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-center">
                  {[
                    ['Calories', previewResult?.nutritionPerServing?.calories],
                    ['Protein', previewResult?.nutritionPerServing?.protein],
                    ['Carbs', previewResult?.nutritionPerServing?.carbs],
                    ['Fat', previewResult?.nutritionPerServing?.fat],
                    ['Sodium', previewResult?.nutritionPerServing?.sodium]
                  ].map(([label, val]) => (
                    <div key={label} className="border rounded-lg p-2">
                      <div className="text-xs text-gray-500">{label}</div>
                      <div className="font-semibold">{val ?? '—'}</div>
                    </div>
                  ))}
                </div>
                <div className="text-xs text-gray-500 mt-2">Calculated from the converted ingredients.</div>
              </section>

              {/* Notes (optional) */}
              {(Array.isArray(previewResult?.notes) && previewResult.notes.length > 0) && (
            <section>
                  <h4 className="font-semibold mb-2">Notes</h4>
                  <ul className="list-disc pl-5 text-sm space-y-1">
                    {previewResult.notes.map((n, i) => (<li key={i}>{n}</li>))}
                  </ul>
            </section>
              )}

              {/* Visibility control removed from preview confirmation per new spec */}
            </>
          )}

          {/* Old bottom image section removed in favor of top gallery */}

          {/* Busy placeholder moved to footer */}

          {!previewResult && (
          <>
            <section className="border border-gray-200 rounded-2xl p-4 bg-white/80 shadow-[4px_4px_0_rgba(0,0,0,0.06)] hover:shadow-[6px_6px_0_rgba(0,0,0,0.08)] hover:-translate-y-0.5 transition-transform transition-shadow duration-200 ease-out">
              <h4 className="text-sm font-semibold tracking-wide text-gray-700 mb-2">Allergens</h4>
              <div className="flex flex-wrap gap-2">
                {ALLERGENS.map(a => (
                  <button key={a}
                    type="button"
                    onClick={()=>toggleAllergen(a)}
                    className={`px-3 py-1.5 rounded-full text-sm border ${excludeAllergens.includes(a) ? 'bg-rose-50 text-rose-700 border-rose-200' : 'bg-gray-50 text-gray-700 border-gray-200'}`}
                  >{a.charAt(0).toUpperCase()+a.slice(1)}</button>
                ))}
              </div>
            </section>

            <section className="border border-gray-200 rounded-2xl p-4 bg-white/80 shadow-[4px_4px_0_rgba(0,0,0,0.06)] hover:shadow-[6px_6px_0_rgba(0,0,0,0.08)] hover:-translate-y-0.5 transition-transform transition-shadow duration-200 ease-out">
              <h4 className="text-sm font-semibold tracking-wide text-gray-700 mb-2">Nutrition Targets (per serving)</h4>
              <div className="mb-3 flex items-center gap-2 text-sm">
                <span className="text-gray-600">Tolerance</span>
                <select value={tolerance} onChange={e=>setTolerance(Number(e.target.value))} className="border border-gray-300 rounded px-2 py-1">
                  <option value={2}>±2%</option>
                  <option value={5}>±5%</option>
                  <option value={10}>±10%</option>
                </select>
                <div className={`ml-3 px-2 py-0.5 rounded text-xs ${feasibility.status==='possible' ? 'bg-green-50 text-green-700 border border-green-200' : feasibility.status==='tight' ? 'bg-amber-50 text-amber-700 border border-amber-200' : 'bg-red-50 text-red-700 border border-red-200'}`}
                  title={feasibility.status==='tight' ? 'May require ingredient substitutions.' : undefined}
                >{feasibility.status==='possible' ? 'Possible' : feasibility.status==='tight' ? 'Tight' : 'Impossible'}</div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
                <label className="text-sm">
                  <span className="block text-gray-600 mb-1">Min kcal</span>
                  <input type="text" inputMode="numeric" placeholder="kcal" className="w-full border border-gray-300 rounded-lg px-3 py-2"
                    value={nutrition?.minCalories ?? ''}
                    onChange={(e)=>setNutrition(n=>({ ...n, minCalories: e.target.value === '' ? null : Number(String(e.target.value).replace(/\D/g,'')) }))}
                  />
                </label>
                <label className="text-sm">
                  <span className="block text-gray-600 mb-1">Max kcal</span>
                  <input type="text" inputMode="numeric" placeholder="kcal" className="w-full border border-gray-300 rounded-lg px-3 py-2"
                    value={nutrition?.maxCalories ?? ''}
                    onChange={(e)=>setNutrition(n=>({ ...n, maxCalories: e.target.value === '' ? null : Number(String(e.target.value).replace(/\D/g,'')) }))}
                  />
                </label>
                <label className="text-sm">
                  <span className="block text-gray-600 mb-1">Min protein (g)</span>
                  <input type="text" inputMode="numeric" placeholder="g" className="w-full border border-gray-300 rounded-lg px-3 py-2"
                    value={nutrition?.minProtein ?? ''}
                    onChange={(e)=>setNutrition(n=>({ ...n, minProtein: e.target.value === '' ? null : Number(String(e.target.value).replace(/\D/g,'')) }))}
                  />
                </label>
                <label className="text-sm">
                  <span className="block text-gray-600 mb-1">Max protein (g)</span>
                  <input type="text" inputMode="numeric" placeholder="g" className="w-full border border-gray-300 rounded-lg px-3 py-2"
                    value={nutrition?.maxProtein ?? ''}
                    onChange={(e)=>setNutrition(n=>({ ...n, maxProtein: e.target.value === '' ? null : Number(String(e.target.value).replace(/\D/g,'')) }))}
                  />
                </label>
                <label className="text-sm">
                  <span className="block text-gray-600 mb-1">Min carbs (g)</span>
                  <input type="text" inputMode="numeric" placeholder="g" className="w-full border border-gray-300 rounded-lg px-3 py-2"
                    value={nutrition?.minCarbs ?? ''}
                    onChange={(e)=>setNutrition(n=>({ ...n, minCarbs: e.target.value === '' ? null : Number(String(e.target.value).replace(/\D/g,'')) }))}
                  />
                </label>
                <label className="text-sm">
                  <span className="block text-gray-600 mb-1">Max carbs (g)</span>
                  <input type="text" inputMode="numeric" placeholder="g" className="w-full border border-gray-300 rounded-lg px-3 py-2"
                    value={nutrition?.maxCarbs ?? ''}
                    onChange={(e)=>setNutrition(n=>({ ...n, maxCarbs: e.target.value === '' ? null : Number(String(e.target.value).replace(/\D/g,'')) }))}
                  />
                </label>
                <label className="text-sm">
                  <span className="block text-gray-600 mb-1">Min fat (g)</span>
                  <input type="text" inputMode="numeric" placeholder="g" className="w-full border border-gray-300 rounded-lg px-3 py-2"
                    value={nutrition?.minFat ?? ''}
                    onChange={(e)=>setNutrition(n=>({ ...n, minFat: e.target.value === '' ? null : Number(String(e.target.value).replace(/\D/g,'')) }))}
                  />
                </label>
                <label className="text-sm">
                  <span className="block text-gray-600 mb-1">Max fat (g)</span>
                  <input type="text" inputMode="numeric" placeholder="g" className="w-full border border-gray-300 rounded-lg px-3 py-2"
                    value={nutrition?.maxFat ?? ''}
                    onChange={(e)=>setNutrition(n=>({ ...n, maxFat: e.target.value === '' ? null : Number(String(e.target.value).replace(/\D/g,'')) }))}
                  />
                </label>
              </div>
              {feasibility.status==='impossible' && (
                <p className="mt-2 text-xs text-red-600">The current macro bounds cannot meet the kcal target. Adjust min/max values.</p>
              )}
            </section>
            {/* Clear all directly under Nutrition Targets */}
            <div className="mt-2 flex justify-start">
              <button
                type="button"
                onClick={() => { setPresets([]); setExcludeAllergens([]); setNutrition({ minCalories:null,maxCalories:null,minProtein:null,maxProtein:null,minCarbs:null,maxCarbs:null,minFat:null,maxFat:null }); }}
                className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-700 hover:bg-gray-200 border border-gray-200"
                title="Clear all selections"
              >Clear all</button>
            </div>
          </>
          )}

          

          
        </div>

        <div className="p-4 sm:p-6 border-t flex flex-col sm:flex-row gap-3 sm:justify-end items-center">
          {/* No Clear all in footer per spec */}
          {(!previewResult && busy) && (
            <div className="mr-auto flex items-center gap-3" aria-live="polite">
              <Spinner size={22} thickness={5} color="#0ea5e9" background="#e2e8f0" />
              <div className="text-sm">
                <div className="font-medium text-gray-800">Reading ingredients…</div>
                <div className="text-gray-600">Analyzing nutrition targets and building variant proposal…</div>
              </div>
            </div>
          )}
          {(previewResult && imageBusy) && (
            <div className="mr-auto flex items-center gap-3" aria-live="polite">
              <Spinner size={22} thickness={5} color="#0ea5e9" background="#e2e8f0" />
              <div className="text-sm">
                <div className="font-medium text-gray-800">Generating 3 variations…</div>
                <div className="text-gray-600">Creating AI images based on the converted recipe and aspect.</div>
              </div>
            </div>
          )}
          {!previewResult && (
            <button onClick={handleRequestClose} className="px-3 py-2 rounded-lg border border-gray-300 bg-white hover:bg-gray-50 text-sm">Cancel</button>
          )}
          {!previewResult && (
            <button disabled={busy || !canConvert} onClick={()=>onPreview?.(constraints)} className={`${(busy || !canConvert) ? 'bg-gray-300 text-gray-500 cursor-not-allowed' : 'bg-orange-500 text-white hover:bg-orange-600'} inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm`}>
              <i className="fa-solid fa-rotate"></i>
              <span>{busy ? 'Converting…' : 'Convert'}</span>
            </button>
          )}
          {previewResult && !busy && (
            <button onClick={()=> onBack ? onBack() : onClose?.()} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-500 text-white hover:bg-gray-600 transition-all duration-200 text-sm">
  <i className="fa-solid fa-arrow-left"></i>
  <span>Back</span>
</button>
          )}
          {previewResult && !busy && (
            <button onClick={()=>{
              const effectiveSource = imageURL ? 'ai' : 'original';
              let imageMeta = null;
              if (selectedIndex > 0) {
                const idx = selectedIndex - 1;
                const sel = aiImages[idx];
                if (sel) {
                  imageMeta = { source: 'ai', url: sel.url, meta: { provider: sel.meta?.provider || 'replicate', model: sel.meta?.model || 'black-forest-labs/flux-schnell', aspect: sel.aspect, params: { steps: 18, cfg: 6, mode: 'txt2img' } } };
                }
              }
              onApply?.({ ...constraints, customTitle, imageSource: imageMeta ? 'ai' : 'original', imageURL: imageMeta?.url || null, visibility, _imageMeta: imageMeta });
            }} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-green-600 text-white hover:bg-green-700 transition-all duration-200 text-sm">
              <i className="fa-solid fa-check"></i>
              <span>Save as Variant</span>
            </button>
          )}
          {!previewResult && (
            <button disabled={busy} onClick={()=>onPreview?.(constraints)} className="hidden" />
          )}

          {/* Remove extra Convert button in preview step */}
        </div>
      </div>
      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={(e)=>{ if(e.target===e.currentTarget) setShowConfirm(false); }}>
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-sm p-5">
            <h4 className="text-lg font-semibold text-gray-800 mb-2">Discard changes?</h4>
            <p className="text-sm text-gray-600 mb-4">You have unsaved changes in the conversion settings.</p>
            <div className="flex justify-end gap-2">
              <button onClick={()=>setShowConfirm(false)} className="px-3 py-2 rounded-lg border border-gray-300 bg-white hover:bg-gray-50 text-sm">Keep editing</button>
              <button onClick={()=>{ setShowConfirm(false); onClose?.(); }} className="px-4 py-2 rounded-lg bg-red-600 text-white hover:bg-red-700 text-sm">Discard & close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


// Side-effects and helpers placed after component definition using function hoisting is not available;
// so define generateImage inside the component via function expression with access to state via closure.
function CollapsibleSubstitutions({ substitutions }) {
  const [open, setOpen] = React.useState(true);
  const list = Array.isArray(substitutions) ? substitutions : [];
  if (list.length === 0) return null;
  return (
    <section>
      <div className="flex items-center justify-between mb-2">
        <h4 className="font-semibold">Substitutions</h4>
        <button onClick={()=>setOpen(o=>!o)} className="text-sm text-blue-600 hover:underline">{open ? 'Hide' : 'Show'}</button>
      </div>
      {open && (
        <ul className="list-disc pl-5 text-sm space-y-1">
          {list.map((s, i) => (
            <li key={i}><strong>{s.from}</strong> → <strong>{s.to}</strong>{s.reason ? ` (${s.reason})` : ''}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
