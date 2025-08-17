import React, { useState, useEffect } from 'react';
import { useOutletContext, useNavigate, useLocation, Link } from 'react-router-dom';
import { 
  LinkIcon, 
  XMarkIcon, 
  ArrowDownTrayIcon, 
  BookmarkIcon,
  ChevronDownIcon
} from '@heroicons/react/24/outline';
import RecipeView from './components/RecipeView';

const API_BASE = 'http://localhost:8001/api/v1';

const CreateCollectionForm = ({ onCreated }) => {
    const [title, setTitle] = useState('');
    const [description, setDescription] = useState('');
    const [visibility, setVisibility] = useState('public');
    const [imageUrl, setImageUrl] = useState('');
    return (
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">Title</label>
          <input className="w-full border rounded-lg px-3 py-2" value={title} onChange={(e)=>setTitle(e.target.value)} />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Description</label>
          <textarea className="w-full border rounded-lg px-3 py-2" value={description} onChange={(e)=>setDescription(e.target.value)} />
        </div>
        <div className="flex gap-3">
          <select className="border rounded-lg px-3 py-2" value={visibility} onChange={(e)=>setVisibility(e.target.value)}>
            <option value="public">Public</option>
            <option value="private">Private</option>
          </select>
          <input className="flex-1 border rounded-lg px-3 py-2" placeholder="Image URL (optional)" value={imageUrl} onChange={(e)=>setImageUrl(e.target.value)} />
        </div>
        <div className="flex justify-end gap-3">
          <button className="px-4 py-2 rounded-lg border" onClick={()=>onCreated?.(null)}>Cancel</button>
          <button className="px-4 py-2 rounded-lg bg-green-600 text-white" onClick={async()=>{
            try {
              const res = await fetch(`${API_BASE}/collections`, { method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify({ title, description, visibility, image_url: imageUrl }) });
              const json = await res.json();
              onCreated?.(json.id || null);
            } catch { onCreated?.(null); }
          }}>Create</button>
        </div>
      </div>
    );
};

// API_BASE already defined above
const STATIC_BASE = 'http://localhost:8001';
const PROXY = `${STATIC_BASE}/api/v1/proxy-image?url=`;
// --- Tagging UI components ---
const TagChip = ({ label, type, status, onRemove }) => {
    const styleByType = {
        dish: 'bg-sky-50 text-sky-700 border-sky-200',
        method: 'bg-violet-50 text-violet-700 border-violet-200',
        meal: 'bg-emerald-50 text-emerald-700 border-emerald-200',
        cuisine: 'bg-blue-50 text-blue-700 border-blue-200',
        diet: 'bg-rose-50 text-rose-700 border-rose-200',
        theme: 'bg-amber-50 text-amber-800 border-amber-200',
    };
    const base = styleByType[type] || 'bg-gray-50 text-gray-700 border-gray-200';
    const pendingCls = 'bg-yellow-50 text-yellow-800 border-yellow-200';
    const cls = status === 'pending' ? pendingCls : base;
    return (
        <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs mr-2 mb-2 border ${cls}`}>
            <span className="font-medium">{label}</span>
        {status === 'pending' && <span className="ml-2 text-[10px] uppercase tracking-wide">pending</span>}
        {onRemove && (
            <button
              onClick={onRemove}
              aria-label={`Ta bort tagg ${label}`}
                  className="ml-2 text-inherit/70 hover:text-inherit hover:bg-white/40 rounded-full px-1 leading-none"
            >
              ×
            </button>
        )}
    </span>
);
};

const TagPicker = ({ canEdit, onAdd, suggestions }) => {
    const [input, setInput] = useState('');
    const [matches, setMatches] = useState([]);
    useEffect(() => {
        const q = input.trim().toLowerCase();
        if (!q) { setMatches([]); return; }
        const m = (suggestions || []).filter(s => s.keyword.includes(q));
        setMatches(m.slice(0, 8));
    }, [input, suggestions]);
    const add = (kw) => {
        setInput('');
        onAdd([kw]);
    };
    return (
        <div>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={canEdit ? 'Add tags…' : 'Suggest tags…'}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
            />
            {matches.length > 0 && (
                <div className="mt-1 bg-white border rounded-lg shadow-sm max-h-40 overflow-auto">
                    {matches.map(m => (
                        <button key={m.id} onClick={() => add(m.keyword)} className="w-full text-left px-3 py-2 hover:bg-gray-50 flex justify-between">
                            <span>{m.keyword}</span>
                            <span className="text-gray-400 text-xs">{m.type}</span>
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
};

const normalizeUrlPort = (url) => {
    if (!url || typeof url !== 'string') return url;
    return url
        .replace('http://127.0.0.1:8000', 'http://127.0.0.1:8001')
        .replace('http://localhost:8000', 'http://localhost:8001');
};

const asThumbSrc = (imageUrl) => {
    const url = normalizeUrlPort(imageUrl);
    if (!url) return null;
    if (url.startsWith('http://localhost:8001') || url.startsWith('http://127.0.0.1:8001') || url.startsWith('/')) {
        return url.startsWith('http') ? url : STATIC_BASE + url;
    }
    return PROXY + encodeURIComponent(url);
};

// Helper: human friendly saved time
const humanSaved = (dateStr) => {
    try {
        const saved = new Date(dateStr);
        const now = new Date();
        const days = Math.max(0, Math.floor((now - saved) / (1000*60*60*24)));
        if (days === 0) return 'Saved today';
        if (days === 1) return 'Saved 1 day ago';
        return `Saved ${days} days ago`;
    } catch { return `Saved ${new Date(dateStr).toLocaleDateString()}`; }
};

// --- Reusable Sub-components ---
const InfoCard = ({ label, value }) => {
    const isTime = /prep|cook/i.test(label);
    const normalized = (() => {
        if (!isTime) return value;
        const str = String(value || '').trim();
        if (/min/i.test(str)) return str;
        const num = parseInt(str, 10);
        return Number.isFinite(num) ? `${num} min` : str;
    })();
    const icon = (() => {
        if (/prep/i.test(label)) return { name: 'clock', cls: 'bg-amber-100 text-amber-600' };
        if (/cook/i.test(label)) return { name: 'clock', cls: 'bg-red-100 text-red-600' };
        return { name: 'users', cls: 'bg-blue-100 text-blue-600' };
    })();
    return (
        <div className="bg-white border border-gray-100 p-4 rounded-xl shadow-sm flex items-center gap-3">
            <div className={`w-9 h-9 rounded-full flex items-center justify-center ${icon.cls}`}>
                {icon.name === 'clock' && (<svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6l3 3"/><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10Z"/></svg>)}
                {icon.name === 'users' && (
                    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M16 14a4 4 0 1 1-8 0"/><path strokeLinecap="round" strokeLinejoin="round" d="M12 14a5 5 0 1 0-5-5M12 14a5 5 0 1 1 5-5"/></svg>
                )}
            </div>
            <div>
                <h4 className="text-sm text-gray-500">{label}</h4>
                <p className="text-lg font-semibold text-gray-900">{normalized}</p>
            </div>
        </div>
    );
};

const Section = ({ title, children }) => (
    <div className="mb-8">
        <h3 className="text-2xl font-bold mb-4 text-gray-900">{title}</h3>
        {children}
    </div>
);

const InstructionSection = ({ items }) => (
    <Section title="Instructions">
        <div className="space-y-4">
            {items.map((instruction, index) => {
                const displayText = typeof instruction === 'string' ? instruction : 
                    instruction.description || instruction.step || `Step ${index + 1}`;
                return (
                    <div key={index} className="flex items-start">
                        <div className="flex-shrink-0 w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold mr-4">{index + 1}</div>
                        <p className="flex-1 text-gray-700 leading-relaxed pt-1">{displayText}</p>
                    </div>
                );
            })}
        </div>
    </Section>
);

const IngredientSection = ({ items }) => {
    const emphasize = (text) => {
        try {
            const UNIT_WORDS = ['tsp','teaspoon','teaspoons','tbsp','tablespoon','tablespoons','cup','cups','pinch','pint','pints','quart','quarts','ounce','ounces','oz','lb','lbs','ml','cl','dl','l','g','gram','grams','kg','kilogram','kilograms','kopp','koppar','tsk','msk','st','pkt'];
            const units = UNIT_WORDS.join('|');
            const rx = new RegExp(`(\\b\\d+[\\d/.,]*\\b|[¼½¾]|\\b(?:${units})\\b)`, 'gi');
            const parts = String(text).split(rx);
            return parts.map((p, i) => {
                if (!p) return null;
                if (rx.test(p)) { rx.lastIndex = 0; return <strong key={i} className="font-semibold text-gray-900">{p}</strong>; }
                return <span key={i}>{p}</span>;
            });
        } catch { return text; }
    };
    return (
        <Section title="Ingredients">
            <div className="bg-gray-50 p-6 rounded-lg">
                <ul className="space-y-2">
                    {items.map((item, index) => {
                        const displayText = typeof item === 'string' ? item : 
                            item.name ? `${item.quantity || ''} ${item.name} ${item.notes ? `(${item.notes})` : ''}`.trim() : 
                            'Unknown ingredient';
                        return (
                            <li key={index} className="flex items-start">
                                <span className="text-green-600 mr-3 mt-1 flex-shrink-0">•</span>
                                <span className="text-gray-700">{emphasize(displayText)}</span>
                            </li>
                        );
                    })}
                </ul>
            </div>
        </Section>
    );
};

const NutritionSection = ({ data }) => {
    // Normalize incoming nutrition shapes
    const normalize = (n) => {
        if (!n || typeof n !== 'object') return null;
        const calories = n.calories || n.kcal || n.Calories || null;
        const protein = n.protein || n.protein_g || n.proteinContent || null;
        const fat = n.fat || n.fat_g || n.fatContent || null;
        const carbs = n.carbohydrates || n.carbs || n.carbs_g || n.carbohydrateContent || null;
        return { calories, protein, fat, carbs };
    };
    const n = normalize(data) || {};
    const nutritionItems = [
        { label: "Calories", value: n.calories },
        { label: "Protein", value: n.protein ? (String(n.protein).endsWith('g') ? n.protein : `${n.protein}g`) : null },
        { label: "Fat", value: n.fat ? (String(n.fat).endsWith('g') ? n.fat : `${n.fat}g`) : null },
        { label: "Carbs", value: n.carbs ? (String(n.carbs).endsWith('g') ? n.carbs : `${n.carbs}g`) : null }
    ];
    return (
        <Section title="Nutritional Information">
            <div className="bg-gray-50 p-4 rounded-lg grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
                {nutritionItems.map(item => (
                    <div key={item.label}>
                        <p className="text-sm text-gray-500">{item.label}</p>
                        <p className="font-medium text-gray-800">{item.value || 'N/A'}</p>
                    </div>
                ))}
            </div>
        </Section>
    );
}

const SourceSection = ({ url }) => (
    <Section title="Source">
        <div className="bg-gray-50 p-4 rounded-lg flex items-center gap-3">
            <LinkIcon className="h-5 w-5 text-gray-400 flex-shrink-0" />
            <a href={url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline truncate">
                {url}
            </a>
        </div>
    </Section>
);

// --- Dropdown Components ---
const Dropdown = ({ label, value, options, onChange, isOpen, onToggle, isOptionDisabled }) => (
    <div className="relative">
        <button
            onClick={onToggle}
            className="flex items-center justify-between w-full px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        >
            <span>{options.find(opt => opt.value === value)?.label || label}</span>
            <ChevronDownIcon className={`h-4 w-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
        </button>
        {isOpen && (
            <div className="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg">
                {options.map((option) => {
                    const disabled = typeof isOptionDisabled === 'function' ? !!isOptionDisabled(option) : false;
                    const isSelected = value === option.value;
                    const baseCls = 'block w-full text-left px-4 py-2 text-sm';
                    const stateCls = disabled
                        ? 'text-gray-300 cursor-not-allowed'
                        : (isSelected ? 'bg-blue-50 text-blue-700' : 'text-gray-700 hover:bg-gray-100');
                    return (
                        <button
                            key={option.value}
                            disabled={disabled}
                            onClick={() => {
                                if (disabled) return;
                                onChange(option.value);
                                onToggle();
                            }}
                            className={`${baseCls} ${stateCls}`}
                        >
                            {option.label}
                        </button>
                    );
                })}
            </div>
        )}
    </div>
);

// --- Main Modal Component ---
// Star rating icon
const Star = ({ filled, onClick, onMouseEnter, onMouseLeave, ariaLabel }) => (
    <button
        type="button"
        className={`w-5 h-5 ${filled ? 'text-yellow-400' : 'text-gray-300'}`}
        onClick={onClick}
        onMouseEnter={onMouseEnter}
        onMouseLeave={onMouseLeave}
        aria-label={ariaLabel}
    >
        <svg viewBox="0 0 20 20" fill="currentColor"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/></svg>
    </button>
);

const RecipeModal = ({ recipe, onClose, currentUser, onOpenRecipe, onTagsUpdated }) => {
    if (!recipe) return null;
    // Close on ESC
    useEffect(() => {
        const onKey = (e) => { if (e.key === 'Escape') onClose?.(); };
        document.addEventListener('keydown', onKey);
        return () => document.removeEventListener('keydown', onKey);
    }, [onClose]);

    return (
        <div
          className="fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center z-50 p-4 transition-opacity duration-300"
          onClick={(e) => { if (e.target === e.currentTarget) onClose?.(); }}
          role="dialog"
          aria-modal="true"
        >
            <div className="bg-white rounded-2xl w-full max-w-[1080px] max-h-[90vh] shadow-2xl relative flex flex-col" onClick={(e) => e.stopPropagation()}>
                <button onClick={onClose} className="absolute top-3 right-3 text-gray-400 hover:text-gray-600"><XMarkIcon className="h-7 w-7" /></button>
                <div className="p-6 overflow-auto">
                  <RecipeView
                    recipeId={recipe.id}
                    recipe={recipe.recipe_content}
                    variant="modal"
                    isSaved={true}
                    currentUser={currentUser}
                    onOpenRecipeInModal={(id, state)=>{ if (!id) return; navigate(`/recipes/${id}`); }}
                    sourceFrom={recipe._sourceFrom}
                    onTagsUpdated={(tags)=>{ try { onTagsUpdated?.(tags); } catch {} }}
                  />
                </div>
            </div>
        </div>
    );
};

// --- Recipe Card Component ---
const RecipeCard = ({ recipe, viewMode, onClick, onDelete, onFilterByChip, currentUser, onAddToCollection }) => {
    const { title, description, image_url, ingredients } = recipe.recipe_content;
    const [cardRating, setCardRating] = React.useState({ average: null, count: 0 });
    const chips = React.useMemo(() => {
        const out = [];
        const rc = recipe?.recipe_content || {};
        const conv = rc.conversion || {};
        if (conv.isVariant) out.push({ label: 'Variant', cls: 'bg-blue-600 text-white' });
        const normalize = (k) => String(k || '').toLowerCase().replace(/\s+/g, '-');
        let presets = [];
        try { presets = ((conv.constraints || {}).presets || []).map(normalize); } catch {}
        if (presets.length === 0) {
            const t = String(rc.title || '').toLowerCase();
            if (/\bvegan\b/.test(t)) presets.push('vegan');
            else if (/\bvegetarian\b/.test(t)) presets.push('vegetarian');
            else if (/\bpesc(etarian)?\b/.test(t)) presets.push('pescetarian');
        }
        if (presets.includes('vegan')) out.push({ label: 'Vegan', cls: 'bg-emerald-600 text-white' });
        if (presets.includes('vegetarian')) out.push({ label: 'Vegetarian', cls: 'bg-lime-600 text-white' });
        if (presets.includes('pescetarian')) out.push({ label: 'Pescetarian', cls: 'bg-sky-600 text-white' });
        // Include approved tags from backend
        try {
            const approved = (recipe.tags && recipe.tags.approved) ? recipe.tags.approved : [];
            for (const t of approved) {
                const key = String(t?.keyword || t).toLowerCase();
                if (key === 'vegan' && !out.find(c=>c.label==='Vegan')) { out.push({ label:'Vegan', cls:'bg-emerald-600 text-white' }); continue; }
                if (key === 'vegetarian' && !out.find(c=>c.label==='Vegetarian')) { out.push({ label:'Vegetarian', cls:'bg-lime-600 text-white' }); continue; }
                if (key === 'pescetarian' && !out.find(c=>c.label==='Pescetarian')) { out.push({ label:'Pescetarian', cls:'bg-sky-600 text-white' }); continue; }
                // default subdued style for generic tags
                out.push({ label: t.keyword || t, cls: 'bg-gray-100 text-gray-700 border border-gray-200' });
            }
        } catch {}
        return out;
    }, [recipe]);

    React.useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const res = await fetch(`${API_BASE}/recipes/${recipe.id}/ratings`, { credentials: 'include' });
                const json = await res.json();
                if (!cancelled && json?.ok) setCardRating(json.data || { average: null, count: 0 });
            } catch {}
        })();
        return () => { cancelled = true; };
    }, [recipe.id]);

    const TitleRow = ({ children }) => (
        <div className="flex items-center justify-between gap-3">
            <h2 className="font-semibold text-lg text-gray-800 truncate">{children}</h2>
            {cardRating.count > 0 && (
                <div className="flex items-center gap-1 text-gray-700">
                    <svg viewBox="0 0 24 24" width="18" height="18" fill="#facc15" aria-hidden="true"><path d="M12 17.27L18.18 21 16.54 13.97 22 9.24l-7.19-.62L12 2 9.19 8.62 2 9.24l5.46 4.73L5.82 21z"/></svg>
                    <span className="text-gray-700 font-medium">{Number(cardRating.average || 0).toFixed(1)}</span>
                </div>
            )}
        </div>
    );
    
    const renderContent = () => {
        switch (viewMode) {
            case 'title_only':
                return (
                    <div className="p-5">
                        <h2 className="font-semibold text-lg text-gray-800">{title}</h2>
                    </div>
                );
            case 'title_image':
                return (
                    <>
                        <div className="relative w-full h-56">
                          <img 
                              src={image_url ? (asThumbSrc(image_url) || 'https://placehold.co/800x600/EEE/31343C?text=No+Image') : 'https://placehold.co/800x600/EEE/31343C?text=No+Image'} 
                              alt={title} 
                              className="w-full h-56 object-cover rounded-t-lg" 
                              onError={(e) => { e.target.src = 'https://placehold.co/800x600/EEE/31343C?text=No+Image'; }}
                          />
                          <div className="absolute inset-0 rounded-t-lg bg-gradient-to-t from-black/70 via-black/25 to-transparent" />
                          <div className="absolute top-3 left-3">
                            <div className="flex items-center bg-white/95 rounded-full px-2 py-0.5 text-xs shadow">
                              <svg viewBox="0 0 24 24" width="14" height="14" fill="#facc15" aria-hidden="true" className="mr-1"><path d="M12 17.27L18.18 21 16.54 13.97 22 9.24l-7.19-.62L12 2 9.19 8.62 2 9.24l5.46 4.73L5.82 21z"/></svg>
                              <span className="text-gray-800 font-semibold">{cardRating && cardRating.count > 0 ? Number(cardRating.average || 0).toFixed(1) : '-'}</span>
                            </div>
                          </div>
                          <div className="absolute bottom-3 left-4 right-4 flex items-end justify-between">
                            <div>
                              <h2 className="text-white text-lg font-extrabold drop-shadow-sm">{title}</h2>
                              {(() => {
                                const ownerDisplayName = recipe.owner_username || recipe.owner || (recipe.user?.username) || (recipe.user?.full_name) || 'You';
                                const ownerUsername = recipe.owner_username || recipe.user?.username || ownerDisplayName;
                                const ownerIsSelf = !!currentUser && (ownerDisplayName === 'You' || String(recipe.user?.id || '') === String(currentUser.id || ''));
                                const linkTarget = ownerIsSelf ? '/profile' : `/users/${encodeURIComponent(ownerUsername)}`;
                                return (
                                  <p className="text-white/90 text-xs mt-2">
                                    By <Link to={linkTarget} className="font-semibold underline-offset-2 hover:underline">{ownerDisplayName}</Link>
                                  </p>
                                );
                              })()}
                            </div>
                          </div>
                        </div>
                    </>
                );
            case 'title_image_description':
                return (
                    <>
                        <div className="relative w-full h-56">
                          <img 
                              src={image_url ? (asThumbSrc(image_url) || 'https://placehold.co/800x600/EEE/31343C?text=No+Image') : 'https://placehold.co/800x600/EEE/31343C?text=No+Image'} 
                              alt={title} 
                              className="w-full h-56 object-cover rounded-t-lg" 
                              onError={(e) => { e.target.src = 'https://placehold.co/800x600/EEE/31343C?text=No+Image'; }}
                          />
                          <div className="absolute inset-0 rounded-t-lg bg-gradient-to-t from-black/70 via-black/25 to-transparent" />
                          <div className="absolute top-3 left-3">
                            <div className="flex items-center bg-white/95 rounded-full px-2 py-0.5 text-xs shadow">
                              <svg viewBox="0 0 24 24" width="14" height="14" fill="#facc15" aria-hidden="true" className="mr-1"><path d="M12 17.27L18.18 21 16.54 13.97 22 9.24l-7.19-.62L12 2 9.19 8.62 2 9.24l5.46 4.73L5.82 21z"/></svg>
                              <span className="text-gray-800 font-semibold">{cardRating && cardRating.count > 0 ? Number(cardRating.average || 0).toFixed(1) : '-'}</span>
                            </div>
                          </div>
                          <div className="absolute bottom-3 left-4 right-4 flex items-end justify-between">
                            <div>
                              <h2 className="text-white text-lg font-extrabold drop-shadow-sm">{title}</h2>
                              {(() => {
                                const ownerDisplayName = recipe.owner_username || recipe.owner || (recipe.user?.username) || (recipe.user?.full_name) || 'You';
                                const ownerUsername = recipe.owner_username || recipe.user?.username || ownerDisplayName;
                                const ownerIsSelf = !!currentUser && (ownerDisplayName === 'You' || String(recipe.user?.id || '') === String(currentUser.id || ''));
                                const linkTarget = ownerIsSelf ? '/profile' : `/users/${encodeURIComponent(ownerUsername)}`;
                                return (
                                  <p className="text-white/90 text-xs mt-2">
                                    By <Link to={linkTarget} className="font-semibold underline-offset-2 hover:underline">{ownerDisplayName}</Link>
                                  </p>
                                );
                              })()}
                            </div>
                          </div>
                        </div>
                        <div className="p-5">
                            {chips.length > 0 && (
                              <div className="mb-2 flex flex-wrap gap-2">
                                {(() => { const max = 3; const visible = chips.slice(0, max); const extra = chips.length - visible.length; return (
                                  <>
                                    {visible.map((c, i) => (
                                      <button key={`${c.label}-${i}`} onClick={(e)=>{ e.stopPropagation(); if (typeof onFilterByChip === 'function') onFilterByChip(c.label); }} className={`text-xs px-2 py-1 rounded-full shadow-sm ${c.cls} cursor-pointer hover:opacity-90`} title={`Filter by ${c.label}`}>{c.label}</button>
                                    ))}
                                    {extra > 0 && (<span className="text-xs px-2 py-1 rounded-full bg-gray-200 text-gray-700">+{extra}</span>)}
                                  </>
                                ); })()}
                              </div>
                            )}
                            <p className="text-sm text-gray-600 line-clamp-2">{description}</p>
                        </div>
                    </>
                );
            case 'title_image_ingredients':
                return (
                    <>
                        <img 
                            src={image_url ? (asThumbSrc(image_url) || 'https://placehold.co/800x600/EEE/31343C?text=No+Image') : 'https://placehold.co/800x600/EEE/31343C?text=No+Image'} 
                            alt={title} 
                            className="w-full h-56 object-cover rounded-t-lg" 
                            onError={(e) => { e.target.src = 'https://placehold.co/800x600/EEE/31343C?text=No+Image'; }}
                        />
                        <div className="p-5">
                            <TitleRow>{title}</TitleRow>
                            {(() => {
                              const ownerDisplayName = recipe.owner_username || recipe.owner || (recipe.user?.username) || (recipe.user?.full_name) || 'You';
                              const ownerUsername = recipe.owner_username || recipe.user?.username || ownerDisplayName;
                              const ownerIsSelf = !!currentUser && (ownerDisplayName === 'You' || String(recipe.user?.id || '') === String(currentUser.id || ''));
                              const linkTarget = ownerIsSelf ? '/profile' : `/users/${encodeURIComponent(ownerUsername)}`;
                              return (
                                <p className="text-gray-600 text-xs mt-3">
                                  By <Link to={linkTarget} className="font-semibold text-gray-800 underline-offset-2 hover:underline">{ownerDisplayName}</Link>
                                </p>
                              );
                            })()}
                            <div className="h-2" />
                            {ingredients && ingredients.length > 0 && (
                                <div className="text-sm text-gray-600">
                                    <p className="font-medium mb-1">Ingredients:</p>
                                    <ul className="space-y-1">
                                        {ingredients.slice(0, 3).map((ingredient, index) => (
                                            <li key={index} className="flex items-start">
                                                <span className="text-green-600 mr-2 mt-1 flex-shrink-0">•</span>
                                                <span className="text-gray-700">
                                                    {typeof ingredient === 'string' ? ingredient : 
                                                     ingredient.name ? `${ingredient.quantity || ''} ${ingredient.name}`.trim() : 
                                                     'Unknown ingredient'}
                                                </span>
                                            </li>
                                        ))}
                                        {ingredients.length > 3 && (
                                            <li className="text-gray-500 italic">... and {ingredients.length - 3} more</li>
                                        )}
                                    </ul>
                                </div>
                            )}
                        </div>
                    </>
                );
            default:
                return null;
        }
    };

    return (
        <div 
            className="group relative bg-white rounded-lg shadow-lg overflow-hidden cursor-pointer hover:shadow-2xl transition-shadow duration-300 flex flex-col" 
            onClick={onClick}
        >
            {/* Hover delete icon */}
            <button
              className="absolute top-3 right-3 z-10 hidden group-hover:flex items-center justify-center w-9 h-9 rounded-full bg-white/90 shadow ring-1 ring-gray-200 hover:bg-red-50"
              title="Delete"
              onClick={(e) => { e.stopPropagation(); onDelete?.(recipe); }}
            >
              <svg viewBox="0 0 24 24" width="18" height="18" fill="#ef4444"><path d="M6 7h12l-1 14H7L6 7zm3-3h6l1 2H8l1-2z"/></svg>
            </button>
            {/* Chips moved to bottom section above description */}
            {renderContent()}
            <div className="px-5 pb-5 mt-auto">
                <div className="flex items-center justify-between text-xs pt-4 border-t border-gray-100">
                    <span className="text-gray-400">{humanSaved(recipe.created_at)}</span>
                    <button className="text-[#e87b35] font-medium hover:underline" onClick={(e)=>{ e.stopPropagation(); if (typeof onAddToCollection === 'function') onAddToCollection(recipe); }}>
                        + Add to Collection
                    </button>
                </div>
            </div>
        </div>
    );
};

// --- Main Page Component ---
const MyRecipes = () => {
    const { currentUser } = useOutletContext();
    const navigate = useNavigate();
    const location = useLocation();
    const [recipes, setRecipes] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [selectedRecipe, setSelectedRecipe] = useState(null);
    const [toDelete, setToDelete] = useState(null);
    const [justInsertedId, setJustInsertedId] = useState(null);
    const [tagFilter, setTagFilter] = useState(null);
    // Always reset any residual filter on mount to avoid showing a single filtered recipe
    useEffect(() => { setTagFilter(null); }, []);
    
    // Dropdown states
    const [viewMode, setViewMode] = useState('title_image_description');
    const [layoutMode, setLayoutMode] = useState('grid_3');
    const [isDropdownOpen, setIsDropdownOpen] = useState(false);
    const [isLayoutDropdownOpen, setIsLayoutDropdownOpen] = useState(false);

    // Enforce valid combinations: List layout only supports Title only view
    useEffect(() => {
        if (layoutMode === 'list' && viewMode !== 'title_only') {
            setViewMode('title_only');
        }
    }, [layoutMode]);

    // Dropdown options
    const viewOptions = [
        { value: 'title_only', label: 'Title only' },
        { value: 'title_image', label: 'Title + image' },
        { value: 'title_image_description', label: 'Title + image + description' },
        { value: 'title_image_ingredients', label: 'Title + image + ingredients' }
    ];

    const layoutOptions = [
        { value: 'grid_2', label: 'Columns (2 per row)' },
        { value: 'grid_3', label: 'Columns (3 per row)' },
        { value: 'list', label: 'List (title only)' }
    ];

    useEffect(() => {
        const fetchRecipes = async () => {
            try {
                // Fetch only current user's saved recipes (backend defaults to scope="mine")
                const response = await fetch(`${API_BASE}/recipes`, { credentials: 'include' });
                if (!response.ok) throw new Error('Failed to fetch recipes from the server.');
                const data = await response.json();
                console.log('Fetched recipes:', data);
                setRecipes(data);
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };
        fetchRecipes();
    }, []);

    // Listen for optimistic insert events from Convert flow
    useEffect(() => {
        const onVariantSaved = (e) => {
            const v = e?.detail?.recipe;
            if (!v || !v.id) return;
            setRecipes((list) => {
                const exists = (list || []).some(r => String(r.id) === String(v.id));
                const next = exists ? list.map(r => String(r.id) === String(v.id) ? v : r) : [v, ...list];
                return next;
            });
            setJustInsertedId(String(v.id));
            setTimeout(() => setJustInsertedId(null), 900);
        };
        window.addEventListener('recipes:variant-saved', onVariantSaved);
        return () => window.removeEventListener('recipes:variant-saved', onVariantSaved);
    }, []);

    // Deep-link: open modal if ?variant=ID is present
    useEffect(() => {
        const params = new URLSearchParams(location.search);
        const variantId = params.get('variant');
        if (!variantId || recipes.length === 0) return;
        const r = recipes.find(x => String(x.id) === String(variantId));
        if (r) {
            if (window.innerWidth < 768) navigate(`/recipes/${r.id}`);
            else setSelectedRecipe(r);
        }
    }, [location.search, recipes, navigate]);

    const getGridClasses = () => {
        switch (layoutMode) {
            case 'grid_2':
                return 'grid-cols-1 md:grid-cols-2 lg:grid-cols-2';
            case 'grid_3':
                return 'grid-cols-1 md:grid-cols-3';
            case 'list':
                return 'grid-cols-1';
            default:
                return 'grid-cols-1 md:grid-cols-3';
        }
    };

    // Collection picker state
    const [showPicker, setShowPicker] = useState(false);
    const [pickerRecipe, setPickerRecipe] = useState(null);
    const [collections, setCollections] = useState([]);
    const [showCreate, setShowCreate] = useState(false);

    const openPicker = async () => {
        try {
            const res = await fetch('http://localhost:8001/api/v1/collections', { credentials: 'include' });
            const data = await res.json();
            setCollections(Array.isArray(data) ? data : []);
        } catch {}
    };
    useEffect(() => { if (showPicker) openPicker(); }, [showPicker]);

    if (loading) return <div className="text-center p-8">Loading recipes...</div>;
    if (error) return <div className="text-center p-8 text-red-500">Error: {error}</div>;

    const normalize = (s) => String(s || '').trim().toLowerCase().replace(/\s+/g, '-');
    const visibleRecipes = (() => {
        if (!tagFilter) return recipes;
        const needle = normalize(tagFilter);
        return (recipes || []).filter((r) => {
            const rc = (r.recipe_content || {});
            const conv = rc.conversion || {};
            if (needle === 'variant' && conv.isVariant) return true;
            const presets = ((conv.constraints || {}).presets || []).map(normalize);
            if (presets.includes(needle)) return true;
            const appr = ((r.tags || {}).approved || []).map(t => normalize(t.keyword));
            if (appr.includes(needle)) return true;
            return false;
        });
    })();

    // helper: human friendly saved time
    const humanSaved = (dateStr) => {
        try {
            const saved = new Date(dateStr);
            const now = new Date();
            const days = Math.max(0, Math.floor((now - saved) / (1000*60*60*24)));
            if (days === 0) return 'Saved today';
            if (days === 1) return 'Saved 1 day ago';
            return `Saved ${days} days ago`;
        } catch { return `Saved ${new Date(dateStr).toLocaleDateString()}`; }
    };

    return (
        <div className="container mx-auto p-8">
            <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between mb-8 gap-4">
                <h1 className="text-4xl font-bold text-gray-800">My Saved Recipes</h1>
                
                {/* Dropdown Controls */}
                <div className="flex flex-col sm:flex-row gap-4 self-start sm:self-auto">
                    {/* View Mode Dropdown */}
                    <div className="w-full sm:w-64">
                        <label className="block text-sm font-medium text-gray-700 mb-2">View Mode</label>
                        <Dropdown
                            label="Select view mode"
                            value={viewMode}
                            options={viewOptions}
                            onChange={setViewMode}
                            isOpen={isDropdownOpen}
                            onToggle={() => setIsDropdownOpen(!isDropdownOpen)}
                            isOptionDisabled={(opt) => layoutMode === 'list' && opt.value !== 'title_only'}
                        />
                    </div>
                    
                    {/* Layout Mode Dropdown */}
                    <div className="w-full sm:w-64">
                        <label className="block text-sm font-medium text-gray-700 mb-2">Layout Mode</label>
                        <Dropdown
                            label="Select layout mode"
                            value={layoutMode}
                            options={layoutOptions}
                            onChange={setLayoutMode}
                            isOpen={isLayoutDropdownOpen}
                            onToggle={() => setIsLayoutDropdownOpen(!isLayoutDropdownOpen)}
                        />
                    </div>
                </div>
            </div>
            {tagFilter && (
                <div className="mb-6 flex items-center justify-between bg-amber-50 border border-amber-200 text-amber-800 px-3 py-2 rounded-lg">
                    <div>Filter: <span className="font-semibold">{tagFilter}</span></div>
                    <button className="text-sm underline" onClick={()=>setTagFilter(null)}>Clear filter</button>
                </div>
            )}

            {recipes.length === 0 ? (
                <div className="text-center py-16">
                     <BookmarkIcon className="h-16 w-16 mx-auto mb-4 text-gray-300" />
                     <h3 className="text-xl font-semibold mb-2 text-gray-600">No Saved Recipes Yet</h3>
                     <p className="text-gray-500">Start by generating and saving your first recipe!</p>
                </div>
            ) : (
                <div className={`grid ${getGridClasses()} gap-8`}>
                    {visibleRecipes.map(recipe => (
                        <div key={recipe.id} className={justInsertedId === String(recipe.id) ? 'animate-slide-in-top' : ''}>
                          <RecipeCard
                              recipe={recipe}
                              viewMode={viewMode}
                              onFilterByChip={(label)=> setTagFilter(label)}
                              currentUser={currentUser}
                              onClick={() => {
                                  // Always navigate to full page view; pass state so Back returns to My Recipes
                                  navigate(`/recipes/${recipe.id}`, { state: { fromMyRecipes: true } });
                              }}
                              onDelete={(r) => setToDelete(r)}
                              onAddToCollection={(r)=>{ setPickerRecipe(r); setShowPicker(true); }}
                          />
                        </div>
                    ))}
                </div>
            )}
            {/* Modal removed to always use full page view */}

            {showPicker && (
              <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={()=>setShowPicker(false)}>
                <div className="bg-white rounded-2xl max-w-lg w-full p-6" onClick={(e)=>e.stopPropagation()}>
                  <h3 className="text-2xl font-bold mb-4">Add to Collection</h3>
                  <div className="space-y-3 max-h-60 overflow-auto">
                    {collections.map(c => (
                      <button key={c.id} className="w-full text-left px-3 py-2 rounded-lg hover:bg-gray-50 border" onClick={async()=>{
                        await fetch(`http://localhost:8001/api/v1/collections/${c.id}/recipes`, { method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify({ recipe_id: pickerRecipe.id }) });
                        setShowPicker(false);
                      }}>
                        <div className="flex items-center gap-3">
                          <img src={(c.image_url && (c.image_url.startsWith('http') ? c.image_url : `${STATIC_BASE}${c.image_url}`)) || 'https://placehold.co/80x60?text=+'} alt="thumb" className="w-16 h-12 object-cover rounded" onError={(e)=>{ e.currentTarget.src='https://placehold.co/80x60?text=+'; }} />
                          <div>
                            <div className="font-semibold">{c.title}</div>
                            <div className="text-xs text-gray-500">{c.recipes_count} recept</div>
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                  <div className="mt-4 flex justify-between items-center">
                    <button className="text-sm underline" onClick={()=>setShowPicker(false)}>Cancel</button>
                    <button className="px-4 py-2 rounded-lg bg-[#da8146] text-white" onClick={()=>setShowCreate(true)}>+ New Collection</button>
                  </div>
                </div>
              </div>
            )}

            {showPicker && showCreate && (
              <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={()=>setShowCreate(false)}>
                <div className="bg-white rounded-2xl max-w-lg w-full p-6" onClick={(e)=>e.stopPropagation()}>
                  <h3 className="text-2xl font-bold mb-4">New Collection</h3>
                  <CreateCollectionForm onCreated={async (cid)=>{ if (cid) {
                    await fetch(`http://localhost:8001/api/v1/collections/${cid}/recipes`, { method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify({ recipe_id: pickerRecipe.id }) });
                  } setShowCreate(false); setShowPicker(false); }} />
                </div>
              </div>
            )}

            {/* Delete confirmation modal */}
            {toDelete && (
              <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setToDelete(null)}>
                <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6" onClick={(e)=>e.stopPropagation()}>
                  <h3 className="text-xl font-bold mb-2">Delete recipe?</h3>
                  <p className="text-gray-600 mb-6">Are you sure you want to delete "{toDelete?.recipe_content?.title}" from your saved recipes? This action cannot be undone.</p>
                  <div className="flex justify-end gap-3">
                    <button className="px-4 py-2 rounded-lg border border-gray-300 hover:bg-gray-50" onClick={()=>setToDelete(null)}>Cancel</button>
                    <button className="px-4 py-2 rounded-lg bg-red-600 text-white hover:bg-red-700" onClick={async ()=>{
                      try {
                        await fetch(`${API_BASE}/recipes/${toDelete.id}`, { method:'DELETE', credentials:'include' });
                        setRecipes(list => list.filter(r => r.id !== toDelete.id));
                        setToDelete(null);
                      } catch (e) {
                        alert('Failed to delete recipe');
                      }
                    }}>Delete</button>
                  </div>
                </div>
              </div>
            )}
        </div>
    );
};

export default MyRecipes;