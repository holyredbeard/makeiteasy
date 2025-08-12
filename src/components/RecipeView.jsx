import React, { useEffect, useMemo, useState } from 'react';
import { 
  LinkIcon,
  ArrowDownTrayIcon,
  BookmarkIcon,
  PlusCircleIcon,
} from '@heroicons/react/24/outline';
import { ClockIcon, UserGroupIcon, PencilSquareIcon, TrashIcon } from '@heroicons/react/24/outline';
import TagInput from './TagInput';
import RecipeConvertPanel from './RecipeConvertPanel';
import { convertRecipeWithDeepSeek, validateConversionSchema } from './deepseekClient';
import { SYSTEM_PROMPT, buildUserPayload } from './DeepSeekPrompts';
import DeepSeekPreviewDiff from './DeepSeekPreviewDiff';
import VariantsList from './VariantsList';

const API_BASE = 'http://localhost:8001/api/v1';
const STATIC_BASE = 'http://localhost:8001';

const chipCls = (type) => ({
  dish: 'bg-sky-50 text-sky-700 border-sky-200',
  method: 'bg-violet-50 text-violet-700 border-violet-200',
  meal: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  cuisine: 'bg-blue-50 text-blue-700 border-blue-200',
  diet: 'bg-rose-50 text-rose-700 border-rose-200',
  theme: 'bg-amber-50 text-amber-800 border-amber-200',
}[type] || 'bg-gray-50 text-gray-700 border-gray-200');

function MetaBadge({ label, value }) {
  if (!value) return null;
  return (
    <div className="inline-flex items-center gap-2 bg-gray-100 text-gray-800 rounded-full px-3 py-1 text-sm">
      <span className="font-medium">{label}</span>
      <span className="text-gray-600">{value}</span>
    </div>
  );
}

function Section({ title, children, className = '', padded = false }) {
  return (
    <div className={`mb-6 ${padded ? 'px-4 lg:px-8' : ''} ${className}`}>
      <h3 className="text-2xl font-bold text-gray-900 mb-4">{title}</h3>
      {children}
    </div>
  );
}

export default function RecipeView({
  recipeId,
  recipe,
  variant = 'inline', // 'inline' | 'modal' | 'page'
  isSaved = false,
  currentUser,
  onSave,
  onDownload,
  onCreateNew,
  onOpenRecipeInModal,
  sourceFrom: sourceFromProp,
}) {
  const [rating, setRating] = useState({ average: 0, count: 0, userValue: null });
  const [tags, setTags] = useState({ approved: [], pending: [] });
  const [comments, setComments] = useState([]);
  const [commentInput, setCommentInput] = useState('');
  const [nextCursor, setNextCursor] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editValue, setEditValue] = useState('');
  const isSticky = variant !== 'inline';
  const [convertOpen, setConvertOpen] = useState(false);
  const [convertBusy, setConvertBusy] = useState(false);
  const [lastConstraints, setLastConstraints] = useState(null);
  const [previewResult, setPreviewResult] = useState(null);
  const [convertError, setConvertError] = useState('');
  const [overrideRecipe, setOverrideRecipe] = useState(null);
  const [activeConstraints, setActiveConstraints] = useState(null);
  const sourceFrom = sourceFromProp || null;
  const [visibilitySaving, setVisibilitySaving] = useState(false);

  const content = useMemo(() => overrideRecipe || recipe || {}, [recipe, overrideRecipe]);
  const title = content.title || '';
  const image = content.image_url || content.thumbnail_path || content.img || null;
  const description = content.description || '';
  const ingredients = Array.isArray(content.ingredients) ? content.ingredients : [];
  const instructions = Array.isArray(content.instructions) ? content.instructions : [];
  const nutrition = content.nutritional_information || content.nutrition || content.nutritionPerServing || {};
  const sourceUrl = content.source_url || content.source || null;

  // Load social data for saved recipes
  useEffect(() => {
    if (!isSaved || !recipeId) return;
    const fetchAll = async () => {
      try {
        const r = await fetch(`${API_BASE}/recipes/${recipeId}/ratings`, { credentials: 'include' });
        const rj = await r.json();
        if (rj.ok) setRating(rj.data);
      } catch {}
      try {
        const t = await fetch(`${API_BASE}/recipes/${recipeId}/tags`, { credentials: 'include' });
        const tj = await t.json();
        if (tj.ok) setTags(tj.data);
      } catch {}
      try {
        const c = await fetch(`${API_BASE}/recipes/${recipeId}/comments?limit=20`, { credentials: 'include' });
        const cj = await c.json();
        if (cj.ok) { setComments(cj.data.items); setNextCursor(cj.data.nextCursor); }
      } catch {}
    };
    fetchAll();
  }, [isSaved, recipeId]);

  const putRating = async (value) => {
    try {
      const res = await fetch(`${API_BASE}/recipes/${recipeId}/ratings`, { method:'PUT', headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify({ value }) });
      const json = await res.json();
      if (json.ok) setRating(json.data);
    } catch {}
  };

  const addTags = async (keywords) => {
    if (!keywords || keywords.length === 0) return;
    try {
      const res = await fetch(`${API_BASE}/recipes/${recipeId}/tags`, { method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify({ keywords }) });
      const json = await res.json();
      if (json.ok) {
        // Merge into local
        setTags((t) => ({
          approved: [...t.approved, ...(json.data.added || []).map(k => ({ keyword: k, type: 'theme' }))],
          pending: [...t.pending, ...(json.data.pending || []).map(k => ({ keyword: k, type: 'theme' }))],
        }));
      }
    } catch {}
  };

  const postComment = async () => {
    const body = (commentInput || '').trim();
    if (!body) return;
    try {
      const res = await fetch(`${API_BASE}/recipes/${recipeId}/comments`, { method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify({ body }) });
      const json = await res.json();
      if (json.ok) {
        setComments((prev) => [json.data, ...prev]);
        setCommentInput('');
      }
    } catch {}
  };

  const isOwner = (comment) => String(currentUser?.id ?? '') === String(comment?.user?.id ?? '');

  const MetaCards = () => {
    const cards = [
      { label: 'Servings', value: content.servings || content.serves, icon: UserGroupIcon, wrapperCls: 'bg-blue-50 text-blue-600' },
      { label: 'Prep Time', value: content.prep_time ?? content.prep_time_minutes, icon: ClockIcon, wrapperCls: 'bg-amber-50 text-amber-600' },
      { label: 'Cook Time', value: content.cook_time ?? content.cook_time_minutes, icon: ClockIcon, wrapperCls: 'bg-rose-50 text-rose-600' },
    ];
    const formatTime = (val) => {
      if (val == null) return '—';
      const str = String(val).trim();
      if (/[a-zA-Z]/.test(str)) return str; // already has units like 'min'
      const num = parseInt(str, 10);
      return Number.isFinite(num) ? `${num} min` : str;
    };
    return (
      <div className="grid grid-cols-1 md:grid-cols-3 gap-2 md:gap-3 justify-items-center lg:justify-items-stretch">
        {cards.map((c, i) => (
          <div key={i} className="bg-white border border-gray-200 rounded-xl p-4 flex items-center gap-3 shadow-sm lg:w-full">
            <div className={`w-9 h-9 rounded-full flex items-center justify-center ${c.wrapperCls}`}>
              <c.icon className="w-5 h-5" />
            </div>
            <div>
              <p className="text-sm text-gray-500">{c.label}</p>
              <p className="text-lg font-semibold text-gray-900">{
                c.label.includes('Time') ? formatTime(c.value) : (c.value || '—')
              }</p>
            </div>
          </div>
        ))}
      </div>
    );
  };

  const resolveNutritionValue = (obj, key) => {
    if (!obj) return undefined;
    const map = {
      calories: ['calories', 'kcal', 'energy', 'Kalorier'],
      protein: ['protein', 'protein_g', 'Protein'],
      fat: ['fat', 'fat_g', 'Fett'],
      carbs: ['carbs', 'carbohydrates', 'carbs_g', 'carb', 'carbohydrate', 'carbohydrate_g', 'Kolhydrater']
    };
    const keys = map[key] || [key];
    for (const k of keys) {
      if (k in obj && obj[k] != null && obj[k] !== '') return obj[k];
      const ku = k.toUpperCase?.();
      if (ku && ku in obj && obj[ku] != null) return obj[ku];
    }
    return undefined;
  };

  const formatNutritionValue = (key, value) => {
    if (value == null) return '—';
    const raw = String(value).trim();
    // Add grams for macros when unit missing
    if (['protein', 'fat', 'carbs'].includes(key)) {
      // If already includes non-digit/unit like 'g' or any letter, keep
      if (/g\b/i.test(raw) || /[a-zA-Z]/.test(raw)) return raw;
      // numeric → append g
      return `${raw}g`;
    }
    return raw;
  };

  return (
    <div className={`w-full ${variant === 'modal' ? 'max-w-[1180px]' : ''}`}>
      <div className="px-4 lg:px-8">
        {/* Header */}
      <div className="mb-8">
        {variant === 'modal' && sourceFrom && (
          <div className="mb-2">
            <button className="text-sm text-blue-600 hover:underline"
              onClick={() => {
                if (typeof onOpenRecipeInModal === 'function') {
                  // Navigate back to the variant and clear source so no back button is shown there
                  onOpenRecipeInModal(sourceFrom.id, { clearSource: true });
                }
              }}
            >Back to {sourceFrom.title || 'variant'}</button>
          </div>
        )}
        {activeConstraints && (
          <div className="mb-3 flex flex-wrap gap-2">
            {(activeConstraints.presets || []).map(p => (
              <span key={`p-${p}`} className="px-2 py-1 rounded-full text-xs bg-emerald-50 text-emerald-700 border border-emerald-200">{p}</span>
            ))}
            {(() => {
              const n = activeConstraints.nutrition || {};
              const chips = [];
              if (n.maxCalories != null) chips.push({ k: 'kcal', label: `≤ ${n.maxCalories} kcal` });
              if (n.minProtein != null) chips.push({ k: 'protein', label: `≥ ${n.minProtein} g protein` });
              if (n.maxCarbs != null) chips.push({ k: 'carbs', label: `≤ ${n.maxCarbs} g carbs` });
              if (n.maxFat != null) chips.push({ k: 'fat', label: `≤ ${n.maxFat} g fat` });
              if (n.maxSodium != null) chips.push({ k: 'sodium', label: `≤ ${n.maxSodium} mg sodium` });
              return chips.map(c => (
                <span key={`n-${c.k}`} className="px-2 py-1 rounded-full text-xs bg-blue-50 text-blue-700 border border-blue-200">{c.label}</span>
              ));
            })()}
          </div>
        )}
          <div className="flex items-center gap-3">
            <h2 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
              <span>{title || 'Untitled Recipe'}</span>
              {content?.conversion?.isVariant && (
                <span className="text-xs px-2 py-1 rounded-full bg-amber-50 text-amber-700 border border-amber-200">Variant</span>
              )}
              {content?.conversion?.isVariant && (
                <button
                  className={`text-xs px-2 py-1 rounded-full border ${content?.conversion?.visibility === 'public' ? 'bg-green-50 text-green-700 border-green-200' : 'bg-gray-50 text-gray-700 border-gray-300'}`}
                  disabled={visibilitySaving}
                  title="Toggle visibility"
                  onClick={async ()=>{
                    try {
                      setVisibilitySaving(true);
                      const desired = content?.conversion?.visibility === 'public' ? 'private' : 'public';
                      const res = await fetch(`http://localhost:8001/api/v1/recipes/${recipeId}/visibility`, {
                        method: 'PUT', headers: { 'Content-Type': 'application/json' }, credentials: 'include', body: JSON.stringify({ visibility: desired })
                      });
                      const j = await res.json();
                      if (!res.ok) throw new Error(j?.detail || 'Visibility update failed');
                      // Update local recipe content
                      setOverrideRecipe((prev) => ({ ...(prev || content), conversion: { ...(prev?.conversion || content?.conversion || {}), visibility: desired } }));
                    } catch (e) {
                      alert(String(e?.message || e));
                    } finally { setVisibilitySaving(false); }
                  }}
                >{content?.conversion?.visibility === 'public' ? 'Public' : 'Private'}</button>
              )}
            </h2>
            {Number(rating.count || 0) > 0 && (
              <div className="flex items-center gap-1 text-gray-700">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="#facc15" aria-hidden="true"><path d="M12 17.27L18.18 21 16.54 13.97 22 9.24l-7.19-.62L12 2 9.19 8.62 2 9.24l5.46 4.73L5.82 21z"/></svg>
                <span className="font-medium">{Number(rating.average || 0).toFixed(1)}</span>
                <span className="text-xs text-gray-500">({rating.count})</span>
              </div>
            )}
          </div>
          {content?.conversion?.isVariant && (
            <div className="mt-1 text-sm text-gray-600">
              Based on: <a className="text-blue-600 hover:underline" href={`/recipes/${content?.conversion?.parentRecipeId}`}
                onClick={(e)=>{
                  if (variant === 'modal' && typeof onOpenRecipeInModal === 'function') {
                    e.preventDefault();
                    const parentId = content?.conversion?.parentRecipeId;
                    if (parentId) onOpenRecipeInModal(parentId, { sourceRecipeId: recipeId, sourceTitle: title });
                  }
                }}
              >{content?.conversion?.basedOnTitle || 'Original'}</a>
            </div>
          )}
        </div>

        {/* Media + Description */}
        <div className="flex flex-col md:flex-row md:items-stretch gap-6 mb-8 lg:mb-10">
          <div className="md:w-1/3">
              {image && (
              <img src={image.startsWith('http') ? image : STATIC_BASE + image} alt={title} className="w-full h-auto object-cover rounded-lg shadow-md" />
            )}
          </div>
          <div className="md:w-2/3 flex flex-col">
            <Section title="Description">
              <p className="text-gray-700 leading-relaxed">{description}</p>
            </Section>
            {/* Desktop-only meta badges directly under description */}
            <div className="hidden lg:block mt-4 mb-6">
              <MetaCards />
            </div>
          </div>
        </div>
        {/* Mobile/tablet full-width badges below image, above ingredients */}
        <div className="block lg:hidden mt-4 mb-6">
          <MetaCards />
        </div>

        {/* Two column body */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 mb-6">
          <div className="lg:col-span-5">
            <Section title="Ingredients">
            <ul className="space-y-2">
              {ingredients.map((ing, idx) => {
                const text = typeof ing === 'string' ? ing : `${ing.quantity || ''} ${ing.name || ''} ${ing.notes ? `(${ing.notes})` : ''}`.trim();
                // emphasize qty/units by bolding leading tokens
                const m = /^(\S+\s+\S+)(.*)$/i.exec(text);
                return (
                  <li key={idx} className="flex items-start">
                    <span className="text-green-600 mr-3 mt-1 flex-shrink-0">•</span>
                    <span className="text-gray-700">
                      {m ? (<><strong className="font-semibold text-gray-900">{m[1]}</strong>{m[2]}</>) : text}
                    </span>
                  </li>
                );
              })}
            </ul>
          </Section>
        </div>
          <div className="lg:col-span-7">
            <Section title="Instructions">
            <div className="space-y-3">
              {instructions.map((inst, idx) => (
                <div key={idx} className="grid grid-cols-[2rem,1fr] gap-3 items-start">
                  <div className="w-8 h-8 rounded-full bg-blue-600 text-white inline-flex items-center justify-center font-bold shrink-0">{idx + 1}</div>
                  <p className="text-gray-700 leading-relaxed">{typeof inst === 'string' ? inst : (inst.description || `Step ${idx + 1}`)}</p>
                </div>
              ))}
            </div>
          </Section>
          </div>
        </div>

      {/* Nutrition */}
      <Section title="Nutrition Information (per serving)">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-2">
          {[{k:'calories', l:'Calories'},{k:'protein',l:'Protein'},{k:'fat',l:'Fat'},{k:'carbs',l:'Carbs'}].map(({k,l}) => (
            <div key={k} className="bg-white border border-gray-200 rounded-xl p-4 text-center shadow-sm">
              <p className="text-sm text-gray-500">{l}</p>
              <p className="text-2xl font-bold text-gray-900">{(() => {
                const val = resolveNutritionValue(nutrition, k);
                if (val === 0 || val === '0' || val === 0.0) return ['protein','fat','carbs'].includes(k) ? '0g' : '0';
                const formatted = (val !== undefined && val !== null && String(val).trim() !== '') ? formatNutritionValue(k, val) : '—';
                return formatted;
              })()}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* Divider between Nutrition and social sections (only when social exists) */}
      {isSaved && (
        <div className="border-t border-gray-200 my-8" />
      )}

        {/* Variants section for original recipes */}
        {isSaved && !content?.conversion?.isVariant && (
          <VariantsList parentId={recipeId} onOpenRecipeInModal={variant === 'modal' ? (id)=>onOpenRecipeInModal?.(id) : undefined} />
        )}

      {/* Source */}
      {sourceUrl && (
        <Section title="Source">
          <div className="bg-gray-50 p-4 rounded-lg flex items-center gap-3">
            <LinkIcon className="h-5 w-5 text-gray-400 flex-shrink-0" />
            <a href={sourceUrl} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline truncate">{sourceUrl}</a>
          </div>
        </Section>
      )}

      {/* Social section for saved recipes */}
      {isSaved && (
        <div className="mt-8 mb-24">
          {/* Tags */}
          <Section title="Tags" className="mt-8">
            <div className="flex flex-wrap gap-2 mb-3">
              {(tags.approved||[]).map(t => (
                <span key={`a-${t.keyword}`} className={`inline-flex items-center px-2 py-1 rounded-full text-xs border ${chipCls(t.type)}`}>
                  <span className="font-medium">{t.keyword}</span>
                </span>
              ))}
              {(tags.pending||[]).map(t => (
                <span key={`p-${t.keyword}`} className={`inline-flex items-center px-2 py-1 rounded-full text-xs border ${chipCls(t.type)}`}> 
                  <span className="font-medium">{t.keyword}</span>
                </span>
              ))}
            </div>
            {/* Input */}
            <TagInput tags={[]} setTags={(ts)=>addTags((ts||[]).map(x=>x.label))} placeholder="Add new tag and press Add" />
          </Section>

          {/* Ratings */}
          <Section title="Ratings" className="mt-4">
            <div className="flex items-center gap-2" role="radiogroup" aria-label="Rate 1 to 5">
              {[1,2,3,4,5].map(v => (
                <button key={v} className={`w-6 h-6 ${v <= (rating.userValue || Math.round(rating.average)) ? 'text-yellow-400' : 'text-gray-300'}`} onClick={()=>putRating(v)}>
                  <svg viewBox="0 0 20 20" fill="currentColor"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/></svg>
                </button>
              ))}
              <span className="text-sm text-gray-600 ml-2">{Number(rating.average||0).toFixed(2)} ({rating.count})</span>
            </div>
          </Section>

          {/* Comments */}
          <Section title="Comments" className="mt-8">
            <div className="bg-gray-50 rounded-lg p-4">
              <textarea value={commentInput} onChange={(e)=>setCommentInput(e.target.value)} rows={3} className="w-full bg-white px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent" placeholder="Write a comment..." />
              <div className="flex justify-end mt-2">
                <button onClick={postComment} className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700">Send</button>
              </div>
              <div className="mt-6">
                {comments.length === 0 ? (<p className="text-gray-500">Be the first to comment.</p>) : comments.map(c => (
                  <div key={c.id} className="border border-gray-200 rounded-lg p-3 bg-white mb-3">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      {c.user?.avatar && (
                        <img src={(String(c.user.avatar).startsWith('http') ? c.user.avatar : `${STATIC_BASE}${c.user.avatar}`)} alt="avatar" className="h-6 w-6 rounded-full object-cover" onError={(e)=>{e.currentTarget.style.display='none';}} />
                      )}
                      <span className="font-medium text-gray-900">{c.user?.username || c.user?.displayName || 'Anonymous'}</span>
                    </div>
                    <span className="text-xs text-gray-500">{new Date(c.createdAt).toLocaleString()}</span>
                  </div>
                   {editingId === c.id ? (
                     <div>
                       <textarea className="w-full border border-gray-300 rounded-lg px-3 py-2" rows={3} value={editValue} onChange={(e)=>setEditValue(e.target.value)} />
                       <div className="flex justify-end gap-2 mt-2">
                         <button onClick={async ()=>{ try{ const r= await fetch(`${API_BASE}/comments/${c.id}`, {method:'PATCH', headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify({body: editValue})}); const j= await r.json(); if(j.ok){ setComments(list => list.map(x => x.id===c.id? j.data : x)); } } finally { setEditingId(null); } }} className="px-3 py-1.5 rounded-lg bg-green-600 text-white text-sm hover:bg-green-700">Save</button>
                         <button onClick={()=>{ setEditingId(null); }} className="px-3 py-1.5 rounded-lg bg-gray-100 text-gray-700 text-sm">Cancel</button>
                       </div>
                     </div>
                   ) : (
                     <p className="text-gray-700">{c.body}</p>
                   )}
                    <div className="flex justify-end items-center gap-3 mt-2">
                     {isOwner(c) && editingId !== c.id && (
                       <>
                         <button onClick={()=>{ setEditingId(c.id); setEditValue(c.body || ''); }} title="Edit" className="text-gray-500 hover:text-gray-700">
                           <PencilSquareIcon className="w-5 h-5" />
                         </button>
                          <button onClick={async ()=>{ if(!confirm('Delete this comment?')) return; try{ const r= await fetch(`${API_BASE}/comments/${c.id}`, {method:'DELETE', credentials:'include'}); const j= await r.json(); if(j.ok){ setComments(list => list.filter(x => x.id !== c.id)); } } catch{} }} title="Delete" className="text-red-500 hover:text-red-600">
                           <TrashIcon className="w-5 h-5" />
                         </button>
                       </>
                     )}
                     <button
                      onClick={async () => {
                        try {
                          const res = await fetch(`${API_BASE}/comments/${c.id}/like`, { method: 'POST', credentials: 'include' });
                          const json = await res.json();
                          if (!json.ok) throw new Error();
                          setComments(list => list.map(x => x.id === c.id ? { ...x, likesCount: json.data.count, likedByMe: json.data.liked } : x));
                        } catch {}
                      }}
                      className={`flex items-center gap-1 text-sm ${c.likedByMe ? 'text-red-600' : 'text-gray-500'} hover:text-red-600`}
                      title={c.likedByMe ? 'Unlike' : 'Like'}
                    >
                      <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41 0.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>
                      <span>{c.likesCount || 0}</span>
                    </button>
                   </div>
                </div>
              ))}
              </div>
            </div>
          </Section>
          {isSticky && <div className="h-24" />}
        </div>
      )}
      </div>

      {/* Action Bar */}
      <div className={`${isSticky ? `sticky left-0 right-0 bg-white border-t border-gray-200 z-30 ${variant === 'modal' ? '-bottom-6 -mx-6 px-6' : 'bottom-0'}` : ''} mt-8`}> 
        <div className="flex flex-wrap justify-end gap-4 py-4 ${variant === 'modal' ? '' : 'px-4 lg:px-8'}">
          <button onClick={() => onDownload?.(content)} className="flex items-center justify-center gap-2 bg-green-600 text-white font-semibold py-3 px-6 rounded-lg hover:bg-green-700 transition-colors">
            <ArrowDownTrayIcon className="h-5 w-5" />
            <span>Download PDF</span>
          </button>
          {!isSaved && (
            <button onClick={() => onSave?.(content)} className="flex items-center justify-center gap-2 bg-purple-600 text-white font-semibold py-3 px-6 rounded-lg hover:bg-purple-700 transition-colors">
              <BookmarkIcon className="h-5 w-5" />
              <span>Save to Recipes</span>
            </button>
          )}
          {isSaved && (
            <button onClick={()=>setConvertOpen(true)} className="flex items-center justify-center gap-2 bg-amber-600 text-white font-semibold py-3 px-6 rounded-lg hover:bg-amber-700 transition-colors">
              <span>Convert</span>
            </button>
          )}
          {!isSaved && (
            <button onClick={() => onCreateNew?.()} className="flex items-center justify-center gap-2 bg-amber-600 text-white font-semibold py-3 px-6 rounded-lg hover:bg-amber-700 transition-colors">
              <PlusCircleIcon className="h-5 w-5" />
              <span>Create New Recipe</span>
            </button>
          )}
        </div>
      </div>
      {convertOpen && (
          <RecipeConvertPanel
          isOpen={convertOpen}
          busy={convertBusy}
          initialConstraints={lastConstraints}
          previewResult={previewResult}
          errorText={convertError}
          PreviewRenderer={(props) => (
            <DeepSeekPreviewDiff
              {...props}
              baseIngredients={ingredients}
              baseInstructions={instructions}
            />
          )}
          recipeId={recipeId}
          onClose={()=>setConvertOpen(false)}
          onPreview={async (constraints)=>{
            try {
              setConvertBusy(true); setLastConstraints(constraints);
              setConvertError(''); setPreviewResult(null);
              const payload = buildUserPayload({
                title, description, ingredients, instructions,
                nutritionPerServing: nutrition
              }, constraints);
              const result = await convertRecipeWithDeepSeek({
                apiKey: process.env.DEEPSEEK_API_KEY || '',
                systemPrompt: SYSTEM_PROMPT,
                userPayload: payload,
                fast: true
              });
              if (!validateConversionSchema(result)) throw new Error('Invalid schema');
              setPreviewResult(result);
            } catch (e) {
              setConvertError(String(e?.message || 'Conversion failed'));
            } finally { setConvertBusy(false); }
          }}
          onApply={async (constraintsArg)=>{
            try {
              setConvertBusy(true);
              setConvertError('');
              const { customTitle, imageSource, imageURL, visibility, ...constraints } = constraintsArg || {};
              const payload = buildUserPayload({ title, description, ingredients, instructions, nutritionPerServing: nutrition }, constraints);
              let result = previewResult;
              if (!result) {
                // ensure we have a fresh result if preview not run
                result = await convertRecipeWithDeepSeek({
                  apiKey: process.env.DEEPSEEK_API_KEY || '',
                  systemPrompt: SYSTEM_PROMPT,
                  userPayload: payload,
                  fast: true
                });
                if (!validateConversionSchema(result)) throw new Error('Invalid schema');
              }
              // Persist variant via backend
              const res = await fetch(`http://localhost:8001/api/v1/recipes/${recipeId}/convert`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ result, constraints, customTitle, image: { source: imageSource, url: imageURL }, visibility })
              });
              const saved = await res.json();
              if (!res.ok) throw new Error(saved?.detail || 'Save failed');
              // Apply visually without reload
              setOverrideRecipe({
                ...content,
                title: result.title || content.title,
                ingredients: result.ingredients || ingredients,
                instructions: result.instructions || instructions,
                nutritionPerServing: result.nutritionPerServing || nutrition
              });
              setActiveConstraints(constraints);
              setConvertOpen(false);
              // Optionellt: trigga refresh utanför panelen
            } catch (e) {
              setConvertError(String(e?.message || 'Failed to save variant'));
            } finally { setConvertBusy(false); }
          }}
        />
      )}
    </div>
  );
}


