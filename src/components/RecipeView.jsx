import React, { useEffect, useMemo, useRef, useState } from 'react';
import { detectLanguage } from '../lib/tts/index.js';
import { audio, getCached, setCached } from '../lib/tts/index.js';
import { init as piperInit, synthesize as piperSynthesize } from '../lib/tts/providers/piper.js';
import { useStepTTS } from '../hooks/useStepTTS.js';
import { 
  LinkIcon,
  ArrowDownTrayIcon,
  BookmarkIcon,
  PlusCircleIcon,
  BookOpenIcon,
  PencilSquareIcon,
  SpeakerWaveIcon,
  SpeakerXMarkIcon,
  FireIcon,
} from '@heroicons/react/24/outline';
import RecipeSubnav from './RecipeSubnav';
import useScrollSpy from './useScrollSpy';
import RecipeSection from './RecipeSection';
import { ClockIcon, UserGroupIcon, TrashIcon, EllipsisVerticalIcon, XMarkIcon, ExclamationTriangleIcon, EyeIcon, EyeSlashIcon } from '@heroicons/react/24/outline';
import TagInput from './TagInput';
import RecipeConvertPanel from './RecipeConvertPanel';
import { convertRecipeWithDeepSeek, validateConversionSchema } from './deepseekClient';
import { SYSTEM_PROMPT, buildUserPayload, buildSystemPrompt } from './DeepSeekPrompts';
import DeepSeekPreviewDiff from './DeepSeekPreviewDiff';
import VariantsList from './VariantsList';

const API_BASE = 'http://localhost:8001/api/v1';
const STATIC_BASE = 'http://localhost:8001';

// --- Helpers: split quantity from ingredient line ---
const UNIT_WORDS = new Set([
  // English
  'cup','cups','tbsp','tablespoon','tablespoons','tsp','teaspoon','teaspoons','oz','ounce','ounces','lb','lbs','pound','pounds','g','gram','grams','kg','ml','l','liter','liters','slice','slices','clove','cloves','can','cans','package','packages','pinch','dash','head','heads','stalk','stalks','bunch','bunches','piece','pieces',
  // Swedish
  'dl','cl','msk','tsk','krm','hg','kg','l','ml','stycken','stycke','st','påse','påsar','burk','burkar','förpackning','förpackningar','klyfta','klyftor','skiva','skivor','förp'
]);

const isNumberLike = (token) => {
  if (!token) return false;
  const t = token.replace(/[()]/g, '').trim();
  // unicode fractions
  const unicodeFracs = '¼½¾⅓⅔⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞';
  if (unicodeFracs.includes(t)) return true;
  // simple number or decimal
  if (/^\d+(?:[\.,]\d+)?$/.test(t)) return true;
  // simple fraction
  if(/^\d+\/\d+$/.test(t)) return true;
  // ranges like 1-2 or 1–2
  if(/^\d+(?:[\.,]\d+)?\s*[–-]\s*\d+(?:[\.,]\d+)?$/.test(t)) return true;
  // mixed number with fraction 1 1/2
  if(/^\d+\s+\d+\/\d+$/.test(t)) return true;
  return false;
};

const splitQuantityFromText = (raw) => {
  const line = String(raw || '').trim();
  if (!line) return { quantity: '', name: '' };
  const tokens = line.split(/\s+/);
  const picked = [];
  for (let i = 0; i < tokens.length; i += 1) {
    const tok = tokens[i];
    if (i === 0) {
      if (!isNumberLike(tok)) break; // no leading number → no qty
      picked.push(tok);
      continue;
    }
    const normalized = tok.toLowerCase().replace(/[.,]/g, '');
    if (isNumberLike(tok) || UNIT_WORDS.has(normalized)) {
      picked.push(tok);
    } else {
      break;
    }
  }
  if (picked.length === 0) return { quantity: '', name: line };
  const quantity = picked.join(' ');
  const name = line.slice(quantity.length).trim();
  return { quantity, name };
};

// Chip colors unified with card chips
const chipCls = (type, label) => {
  const l = String(label || '').toLowerCase();
  if (l === 'variant') return 'bg-blue-600 text-white border-blue-600';
  if (l === 'vegan') return 'bg-emerald-600 text-white border-emerald-600';
  if (l === 'vegetarian') return 'bg-lime-600 text-white border-lime-600';
  if (l === 'pescetarian') return 'bg-sky-600 text-white border-sky-600';
  const map = {
    dish: 'bg-sky-50 text-sky-700 border-sky-200',
    method: 'bg-violet-50 text-violet-700 border-violet-200',
    meal: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    cuisine: 'bg-blue-50 text-blue-700 border-blue-200',
    diet: 'bg-rose-50 text-rose-700 border-rose-200',
    theme: 'bg-amber-50 text-amber-800 border-amber-200',
  };
  return map[type] || 'bg-gray-50 text-gray-700 border-gray-200';
};

function MetaBadge({ label, value }) {
  if (!value) return null;
  return (
    <div className="inline-flex items-center gap-2 bg-gray-100 text-gray-800 rounded-full px-3 py-1 text-sm">
      <span className="font-medium">{label}</span>
      <span className="text-gray-600">{value}</span>
    </div>
  );
}

function Section({ title, children, className = '', padded = false, showTitle = true }) {
  return (
    <div className={`mb-6 ${padded ? 'px-4 lg:px-8' : ''} ${className}`}>
      {showTitle && (
        <h3 className="text-2xl font-bold text-gray-900 mb-4">{title}</h3>
      )}
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
  onAddToCollection,
  onEditRecipe,
  onOpenRecipeInModal,
  onRequestCloseModal,
  sourceFrom: sourceFromProp,
  onTagsUpdated,
  onSaved, // optional callback invoked after successful save with updated SavedRecipe
  onEditStateChange, // callback for edit state changes
}) {
  const [rating, setRating] = useState({ average: 0, count: 0, userValue: null });
  const [tags, setTags] = useState({ approved: [], pending: [] });
  const [comments, setComments] = useState([]);
  const [commentInput, setCommentInput] = useState('');
  const [replyToId, setReplyToId] = useState(null);
  const [replyText, setReplyText] = useState('');
  const [nextCursor, setNextCursor] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editValue, setEditValue] = useState('');
  const isSticky = false;
  const [convertOpen, setConvertOpen] = useState(false);
  const [convertBusy, setConvertBusy] = useState(false);
  const [lastConstraints, setLastConstraints] = useState(null);
  const [previewResult, setPreviewResult] = useState(null);
  const [convertError, setConvertError] = useState('');
  const [overrideRecipe, setOverrideRecipe] = useState(null);
  const [activeConstraints, setActiveConstraints] = useState(null);
  const sourceFrom = sourceFromProp || null;
  const [visibilitySaving, setVisibilitySaving] = useState(false);
  const [justSavedVariant, setJustSavedVariant] = useState(false);
  const [savedVariantId, setSavedVariantId] = useState(null);
  // Inline edit mode
  const [isEditing, setIsEditing] = useState(false);
  const [edited, setEdited] = useState(null);
  const [activeEditField, setActiveEditField] = useState(null); // 'title', 'image', 'description', 'ingredients', 'instructions'
  const [busySave, setBusySave] = useState(false);
  const [aiBusy, setAiBusy] = useState(false);
  const [gallery, setGallery] = useState([]);
  const [galleryIndex, setGalleryIndex] = useState(0);
  const [hoverHighlight, setHoverHighlight] = useState(false);
  const [ttsActive, setTtsActive] = useState(false);
  const [isTtsPlaying, setIsTtsPlaying] = useState(false);
  const utterRef = useRef(null);
  const { onStepClick } = useStepTTS();
  const [dragItem, setDragItem] = useState(null); // { type: 'ingredients'|'instructions', index: number }
  const [dropIndicator, setDropIndicator] = useState(null); // { type, index, pos: 'before'|'after' }
  const [confirmDelete, setConfirmDelete] = useState(null); // { type: 'ingredient'|'instruction', index }
  const [sort, setSort] = useState('popular');
  const [hoveredItem, setHoveredItem] = useState(null); // { type: 'ingredients'|'instructions', index: number }
  const [keyboardFocusedItem, setKeyboardFocusedItem] = useState(null); // { type: 'ingredients'|'instructions', index: number }
  const hoverTimeoutRef = useRef(null);

  const moveArrayItem = (array, fromIndex, toIndex) => {
    const list = Array.isArray(array) ? [...array] : [];
    if (fromIndex === toIndex || fromIndex < 0 || toIndex < 0 || fromIndex >= list.length || toIndex > list.length) return list;
    const [moved] = list.splice(fromIndex, 1);
    list.splice(toIndex, 0, moved);
    return list;
  };

  const handleDragStart = (type, index) => (e) => {
    setDragItem({ type, index });
    try { e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', String(index)); } catch {}
  };
  const handleDragOver = (type, index) => (e) => {
    if (dragItem && dragItem.type === type) {
      e.preventDefault();
      try { e.dataTransfer.dropEffect = 'move'; } catch {}
      const rect = e.currentTarget.getBoundingClientRect();
      const pos = (e.clientY - rect.top) < rect.height / 2 ? 'before' : 'after';
      setDropIndicator({ type, index, pos });
    }
  };
  const handleDrop = (type, index) => (e) => {
    e.preventDefault();
    if (!dragItem || dragItem.type !== type) return;
    const using = (dropIndicator && dropIndicator.type === type) ? dropIndicator : { type, index, pos: 'after' };
    const toIndex = using.pos === 'after' ? (using.index + 1) : using.index;
    setEdited(prev => {
      const current = Array.isArray(prev?.[type]) ? prev[type] : [];
      const reordered = moveArrayItem(current, dragItem.index, toIndex);
      return { ...(prev || {}), [type]: reordered };
    });
    setDragItem(null);
    setDropIndicator(null);
  };
  const clearDrag = () => { setDragItem(null); setDropIndicator(null); };

  // ----- Add/Remove rows -----
  const addIngredientRow = () => {
    setEdited(prev => {
      const arr = Array.isArray(prev?.ingredients) ? [...prev.ingredients] : [];
      arr.push({ quantity: '', name: '' });
      return { ...(prev || {}), ingredients: arr };
    });
  };
  const removeIngredientAt = (idx) => {
    setEdited(prev => {
      const arr = Array.isArray(prev?.ingredients) ? [...prev.ingredients] : [];
      if (idx >= 0 && idx < arr.length) arr.splice(idx, 1);
      return { ...(prev || {}), ingredients: arr };
    });
  };
  const confirmAndRemoveIngredient = (idx) => { setConfirmDelete({ type: 'ingredient', index: idx }); };
  const addInstructionRow = () => {
    setEdited(prev => {
      const arr = Array.isArray(prev?.instructions) ? [...prev.instructions] : [];
      arr.push({ description: '' });
      return { ...(prev || {}), instructions: arr };
    });
  };
  const removeInstructionAt = (idx) => {
    setEdited(prev => {
      const arr = Array.isArray(prev?.instructions) ? [...prev.instructions] : [];
      if (idx >= 0 && idx < arr.length) arr.splice(idx, 1);
      return { ...(prev || {}), instructions: arr };
    });
  };
  const confirmAndRemoveInstruction = (idx) => { setConfirmDelete({ type: 'instruction', index: idx }); };

  const onConfirmDelete = () => {
    if (!confirmDelete) return;
    if (confirmDelete.type === 'ingredient') removeIngredientAt(confirmDelete.index);
    else removeInstructionAt(confirmDelete.index);
    setConfirmDelete(null);
  };
  const onCancelDelete = () => setConfirmDelete(null);

  // Auto-resize textarea function
  const autoResizeTextarea = (element) => {
    if (element) {
      element.style.height = 'auto';
      element.style.height = element.scrollHeight + 'px';
    }
  };

  // Handle clicks outside active edit field
  const handleOutsideClick = (e) => {
    if (isEditing && activeEditField) {
      // Check if click is outside the active edit field
      const activeField = e.target.closest('[data-edit-field]');
      if (!activeField || activeField.dataset.editField !== activeEditField) {
        setActiveEditField(null);
      }
    }
  };

  // Debounced hover handler
  const handleHover = (type, index) => {
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current);
    }
    hoverTimeoutRef.current = setTimeout(() => {
      setHoveredItem({ type, index });
    }, 100);
  };

  const handleHoverLeave = () => {
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current);
    }
    setHoveredItem(null);
  };

  // Keyboard navigation handlers
  const handleKeyDown = (e) => {
    console.log('Key pressed:', e.key, 'hoverHighlight:', hoverHighlight);
    if (!hoverHighlight) return;
    
    const currentItem = keyboardFocusedItem || hoveredItem;
    console.log('Current item:', currentItem);
    if (!currentItem) return;

    let newIndex = currentItem.index;
    const maxIndex = instructionsToRender.length - 1;

    switch (e.key) {
      case 'ArrowUp':
        e.preventDefault();
        newIndex = Math.max(0, newIndex - 1);
        console.log('ArrowUp - new index:', newIndex);
        break;
      case 'ArrowDown':
        e.preventDefault();
        newIndex = Math.min(maxIndex, newIndex + 1);
        console.log('ArrowDown - new index:', newIndex);
        break;
      case 'Escape':
        e.preventDefault();
        setKeyboardFocusedItem(null);
        setHoveredItem(null);
        console.log('Escape - cleared focus');
        return;
      default:
        return;
    }

    const newItem = { type: 'instructions', index: newIndex };
    console.log('Setting new item:', newItem);

    setKeyboardFocusedItem(newItem);
    setHoveredItem(newItem);
  };

  useEffect(() => {
    if (!confirmDelete) return;
    const onKey = (e) => { if (e.key === 'Escape') setConfirmDelete(null); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [confirmDelete]);

  // Cleanup speech on unmount
  useEffect(() => {
    return () => {
      try { if (typeof window !== 'undefined' && window.speechSynthesis) { window.speechSynthesis.cancel(); } } catch {}
    };
  }, []);

  const speakText = (text, stepId) => {
    try {
      if (!ttsActive || !text) return;
      setIsTtsPlaying(true);
      onStepClick(stepId || `step-${Math.random()}`, String(text));
    } catch {}
  };

  useEffect(() => {
    const handler = () => setIsTtsPlaying(false);
    window.addEventListener('tts:ended', handler);
    return () => window.removeEventListener('tts:ended', handler);
  }, []);

  // Prefetch TTS for steps (Piper), once per mount
  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      try {
        const list = Array.isArray(instructions) ? instructions : [];
        for (let idx = 0; idx < list.length; idx += 1) {
          if (cancelled) break;
          const txt = typeof list[idx] === 'string' ? list[idx] : (list[idx]?.description || '');
          const stepId = `pf-${recipeId}-${idx}`;
          if (!txt || getCached(stepId)) { await new Promise(r=>setTimeout(r,250)); continue; }
          const locale = detectLanguage(txt);
          try { await piperInit(locale); } catch {}
          try {
            const wav = await piperSynthesize(txt, { locale, rate: 1.0 });
            if (cancelled) break;
            const url = URL.createObjectURL(wav);
            setCached(stepId, { url, locale, createdAt: Date.now() });
          } catch {}
          await new Promise(r=>setTimeout(r,250));
        }
      } catch {}
    };
    run();
    return () => { cancelled = true; };
  }, [recipeId]);

  const content = useMemo(() => overrideRecipe || recipe || {}, [recipe, overrideRecipe]);
  const title = content.title || '';
  const image = content.image_url || content.thumbnail_path || content.img || null;
  const description = content.description || '';
  const ingredients = Array.isArray(content.ingredients) ? content.ingredients : [];
  const instructions = Array.isArray(content.instructions) ? content.instructions : [];
  const ingredientsToRender = useMemo(() => {
    const ingredientsToUse = edited?.ingredients || ingredients;
    return variant === 'modal' ? ingredientsToUse.slice(0, 8) : ingredientsToUse;
  }, [variant, ingredients, edited?.ingredients]);
  const instructionsToRender = useMemo(() => {
    const instructionsToUse = edited?.instructions || instructions;
    return variant === 'modal' ? instructionsToUse.slice(0, 3) : instructionsToUse;
  }, [variant, instructions, edited?.instructions]);
  const nutrition = content.nutritional_information || content.nutrition || content.nutritionPerServing || {};
  const sourceUrl = content.source_url || content.source || null;

  // Auto-hide toast
  useEffect(() => {
    if (justSavedVariant) {
      const t = setTimeout(() => setJustSavedVariant(false), 3000);
      return () => clearTimeout(t);
    }
  }, [justSavedVariant]);

  // Dynamic document title (restore on unmount) without site suffix
  const prevTitleRef = useRef(typeof document !== 'undefined' ? document.title : '');
  useEffect(() => {
    const base = content?.title || title || 'Recipe';
    const withSuffix = variant === 'page' ? `${base}  Site` : base;
    if (typeof document !== 'undefined') document.title = withSuffix;
    return () => {
      if (typeof document !== 'undefined') document.title = prevTitleRef.current || 'Clip2Cook';
    };
  }, [content?.title, title]);

  // ----- Edit helpers -----
  const startEdit = () => {
    setIsEditing(true);
    setEdited({
      title,
      description,
      image_url: image,
      ingredients: (ingredients || []).map((i) => {
        if (typeof i === 'string') {
          const { quantity, name } = splitQuantityFromText(i);
          return { quantity, name };
        }
        const q0 = (i && i.quantity) ? String(i.quantity) : '';
        const n0 = (i && i.name) ? String(i.name) : '';
        if (!q0 && n0) {
          const { quantity, name } = splitQuantityFromText(n0);
          if (quantity) return { ...i, quantity, name };
        }
        return { ...i };
      }),
      instructions: (instructions || []).map(s => ({ ...(typeof s === 'string' ? { step: s.step, description: s } : s) })),
    });
    const base = image ? (String(image).startsWith('http') ? image : STATIC_BASE + image) : null;
    setGallery(base ? [base] : []);
    setGalleryIndex(0);
  };

  const activateFieldEdit = (fieldName) => {
    if (!isEditing) {
      startEdit();
    }
    setActiveEditField(fieldName);
  };

  const saveEdits = async () => {
    try {
      setBusySave(true);
      // Build updated content
      const updatedContent = {
        ...content,
        title: edited.title,
        description: edited.description,
        image_url: edited.image_url,
        ingredients: edited.ingredients,
        instructions: edited.instructions,
      };
      if (isSaved && recipeId) {
        // Update existing saved recipe
        const params = new URLSearchParams();
        if (typeof window !== 'undefined') {
          const p = new URLSearchParams(window.location.search);
          if (p.get('open')) params.set('collectionId', p.get('open'));
        }
        const res = await fetch(`${API_BASE}/recipes/${recipeId}?${params.toString()}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ recipe_content: updatedContent })
        });
        const updated = await res.json().catch(()=>null);
        if (updated && typeof onSaved === 'function') onSaved(updated);
      } else {
        // Create new saved recipe (extract flow)
        const payload = { source_url: content.source_url || '', recipe_content: updatedContent };
        const res = await fetch(`${API_BASE}/recipes/save`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include', body: JSON.stringify(payload)
        });
        const created = await res.json().catch(()=>null);
        if (created && typeof onSaved === 'function') onSaved(created);
      }
      setOverrideRecipe(updatedContent);
      setIsEditing(false);
      setActiveEditField(null);
    } catch (e) {
      alert('Failed to save changes');
    } finally {
      setBusySave(false);
    }
  };

  const generateAiImage = async () => {
    try {
      setAiBusy(true);
      const names = (edited?.ingredients || []).map(i => (i.name || '').trim()).filter(Boolean).slice(0,5);
      const body = { title: edited?.title || title, ingredients: names, allow_placeholder: false };
      const res = await fetch(`${API_BASE}/images/generate`, { method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify(body) });
      const json = await res.json();
      if (json?.url) {
        setEdited(prev => ({ ...(prev || {}), image_url: json.url }));
        const abs = json.url.startsWith('http') ? json.url : STATIC_BASE + json.url;
        setGallery(g => { const ng = g && g.length ? [...g, abs] : [abs]; setGalleryIndex(ng.length-1); return ng; });
      }
    } catch { alert('AI image generation failed'); }
    finally { setAiBusy(false); }
  };

  // Load social data for saved recipes
  // Add global click listener for outside clicks
  useEffect(() => {
    if (isEditing && activeEditField) {
      document.addEventListener('click', handleOutsideClick);
      return () => document.removeEventListener('click', handleOutsideClick);
    }
  }, [isEditing, activeEditField]);

  // Add global keyboard listener for navigation
  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [hoverHighlight, keyboardFocusedItem, hoveredItem, ingredientsToRender.length, instructionsToRender.length]);

  // Notify parent of edit state changes
  useEffect(() => {
    if (onEditStateChange) {
      onEditStateChange(isEditing);
    }
  }, [isEditing, onEditStateChange]);



  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (hoverTimeoutRef.current) {
        clearTimeout(hoverTimeoutRef.current);
      }
    };
  }, []);

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
        try { if (typeof onTagsUpdated === 'function') onTagsUpdated({ approved: json.data.added || [], pending: json.data.pending || [] }); } catch {}
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

  const postReply = async (parentId) => {
    const body = (replyText || '').trim();
    if (!body || !parentId) return;
    try {
      const res = await fetch(`${API_BASE}/recipes/${recipeId}/comments`, { method:'POST', headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify({ body, parentId }) });
      const json = await res.json();
      if (json.ok) {
        setComments((prev) => [json.data, ...prev]);
        setReplyToId(null); setReplyText('');
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
      // Extract number from strings like "20 minutes" or "20 min"
      const numMatch = str.match(/(\d+)/);
      if (numMatch) {
        return `${numMatch[1]} min`;
      }
      // If already has units like 'min', keep as is
      if (/[a-zA-Z]/.test(str)) return str;
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

  // --- Subnav (page only) ---
  const subnavItems = [
    { id: 'ingredients', label: 'Ingredients' },
    { id: 'instructions', label: 'Instructions' },
  ];
  if (nutrition && Object.keys(nutrition).length > 0) subnavItems.push({ id: 'nutrition', label: 'Nutrition' });
  if (isSaved && !content?.conversion?.isVariant) subnavItems.push({ id: 'variants', label: 'Variants' });
  subnavItems.push({ id: 'tags', label: 'Tags' });
  subnavItems.push({ id: 'ratings', label: 'Ratings' });
  subnavItems.push({ id: 'comments', label: 'Comments' });

  const activeId = useScrollSpy(subnavItems.map(i => i.id), 88);
  
  const scrollToId = (id) => {
    const el = document.getElementById(id);
    if (!el) return;
    const topOffset = 88; // TODO: read actual topbar height dynamically
    const target = el.querySelector('h2') || el;
    const y = target.getBoundingClientRect().top + window.pageYOffset - topOffset;
    window.scrollTo({ top: y, behavior: 'smooth' });
    try { target?.focus?.(); } catch {}
  };

  return (
    <div className={`w-full ${variant === 'modal' ? 'max-w-[1180px]' : ''}`}>
      <div className="px-4 lg:px-8">
        {/* Header */}
      <div className="mb-8">
        {variant === 'modal' && sourceFrom && !recipe?.conversion?.isVariant && (
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
              
              return chips.map(c => (
                <span key={`n-${c.k}`} className="px-2 py-1 rounded-full text-xs bg-blue-50 text-blue-700 border border-blue-200">{c.label}</span>
              ));
            })()}
          </div>
        )}
          <div className="flex items-center gap-3">
            <h2 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
              {isEditing && activeEditField === 'title' ? (
                <div data-edit-field="title">
                  <input
                    value={edited?.title || ''}
                    onChange={(e)=>setEdited(v=>({...(v||{}), title: e.target.value}))}
                    className="flex-1 w-[50vw] max-w-[730px] min-w-[35ch] text-3xl font-extrabold leading-tight border-b-2 border-amber-300 focus:outline-none focus:border-amber-500 rounded-sm px-1"
                    placeholder="Title"
                    aria-label="Recipe title"
                    onBlur={() => setActiveEditField(null)}
                  />
                </div>
              ) : (
                <span 
                  className={isEditing ? "cursor-pointer hover:bg-yellow-50 rounded px-1 transition-colors" : ""}
                  onClick={isEditing ? () => activateFieldEdit('title') : undefined}
                  data-edit-field="title"
                >
                  {edited?.title || title || 'Untitled Recipe'}
                </span>
              )}
              {content?.conversion?.isVariant && (
                <span className="text-xs px-2 py-1 rounded-full bg-amber-50 text-amber-700 border border-amber-200">Variant</span>
              )}
              {/* removed variant title tag near header */}
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
            {!isEditing && Number(rating.count || 0) > 0 && (
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
            {(image || edited?.image_url) && (
              <div className={`${isEditing && activeEditField === 'image' ? 'ring-2 ring-amber-300 rounded-lg p-1 relative' : ''}`}>
                <div className={`${variant === 'modal' ? 'relative w-full aspect-[4/3]' : ''}`}>
                  <img
                    src={(isEditing && (gallery[galleryIndex])) ? gallery[galleryIndex] : ((edited?.image_url || image).startsWith('http') ? (edited?.image_url || image) : STATIC_BASE + (edited?.image_url || image))}
                    alt={edited?.title || title}
                    className={`w-full ${variant === 'modal' ? 'h-full absolute inset-0' : 'h-auto'} object-cover rounded-lg shadow-md ${isEditing ? 'cursor-pointer' : ''}`}
                    loading={variant === 'modal' ? 'lazy' : 'eager'}
                    decoding="async"
                    onClick={isEditing ? () => activateFieldEdit('image') : undefined}
                    data-edit-field="image"
                  />
                </div>
                {isEditing && activeEditField === 'image' && gallery.length > 1 && (
                  <>
                    <button onClick={()=>setGalleryIndex(i => (i-1+gallery.length)%gallery.length)} className="absolute left-2 top-1/2 -translate-y-1/2 bg-white/80 hover:bg-white text-gray-800 w-8 h-8 rounded-full shadow flex items-center justify-center" aria-label="Prev">‹</button>
                    <button onClick={()=>setGalleryIndex(i => (i+1)%gallery.length)} className="absolute right-2 top-1/2 -translate-y-1/2 bg-white/80 hover:bg-white text-gray-800 w-8 h-8 rounded-full shadow flex items-center justify-center" aria-label="Next">›</button>
                  </>
                )}
                {isEditing && activeEditField === 'image' && (
                  <div className="mt-3 flex items-center gap-2">
                    <button className="px-4 py-2 rounded-lg bg-[#da8146] text-white disabled:opacity-60" onClick={generateAiImage} disabled={aiBusy}>{aiBusy ? 'Generating…' : 'Generate'}</button>
                    <input id="rv-upload" type="file" accept="image/*" className="hidden" onChange={async (e)=>{
                      const f = e.target.files && e.target.files[0];
                      if(!f) return;
                      try {
                        const form = new FormData();
                        form.append('file', f);
                        const r = await fetch(`${API_BASE}/images/upload`, { method: 'POST', credentials: 'include', body: form });
                        const j = await r.json();
                        if (j?.url) {
                          setEdited(prev => ({ ...(prev||{}), image_url: j.url }));
                          const abs = j.url.startsWith('http') ? j.url : STATIC_BASE + j.url;
                          setGallery(g => { const ng = g && g.length ? [...g, abs] : [abs]; setGalleryIndex(ng.length-1); return ng; });
                        } else {
                          alert('Upload failed');
                        }
                      } catch {
                        alert('Upload failed');
                      } finally {
                        e.target.value = '';
                      }
                    }} />
                    <button className="px-4 py-2 rounded-lg bg-gray-200 text-gray-800 hover:bg-gray-300" onClick={()=>document.getElementById('rv-upload')?.click()}>Upload</button>
                  </div>
                )}
              </div>
            )}
          </div>
          <div className="md:w-2/3 flex flex-col">
            <Section title="Description" showTitle={false}>
              {isEditing && activeEditField === 'description' ? (
                <div data-edit-field="description">
                  <textarea
                    value={edited?.description||''}
                    onChange={(e)=>setEdited(v=>({...(v||{}), description:e.target.value}))}
                    className="w-full border rounded-lg px-4 py-3 text-base leading-relaxed min-h-[200px] resize-y ring-amber-200 focus:ring-2"
                    rows={8}
                    placeholder="Add description"
                    onBlur={() => setActiveEditField(null)}
                  />
                </div>
              ) : (
                <p 
                  className={`text-gray-700 leading-relaxed ${isEditing ? 'cursor-pointer hover:bg-yellow-50 rounded-lg p-2 transition-colors' : ''}`}
                  onClick={isEditing ? () => activateFieldEdit('description') : undefined}
                  data-edit-field="description"
                >
                  {edited?.description || description}
                </p>
              )}
            </Section>
          </div>
        </div>

        {/* Stats bar on its own row */}
        <div className="mb-8">
          <div className="flex flex-wrap items-center justify-between gap-4 md:gap-6">
            <div className="inline-flex items-center gap-2 px-4 py-3 bg-blue-50 rounded-lg border border-blue-100">
              <UserGroupIcon className="w-5 h-5 text-blue-600" aria-hidden="true" />
              <span className="text-sm text-blue-700">Servings</span>
              <span className="text-sm font-semibold text-blue-900">{content.servings || content.serves || '—'}</span>
            </div>
            <div className="inline-flex items-center gap-2 px-4 py-3 bg-amber-50 rounded-lg border border-amber-100">
              <ClockIcon className="w-5 h-5 text-amber-600" aria-hidden="true" />
              <span className="text-sm text-amber-700">Prep Time</span>
              <span className="text-sm font-semibold text-amber-900">{(() => { const v = content.prep_time ?? content.prep_time_minutes; return v != null && String(v) !== '' ? `${String(v).replace(/\s*minutes?\s*/i, '')} min` : '—'; })()}</span>
            </div>
            <div className="inline-flex items-center gap-2 px-4 py-3 bg-orange-50 rounded-lg border border-orange-100">
              <FireIcon className="w-5 h-5 text-orange-600" aria-hidden="true" />
              <span className="text-sm text-orange-700">Cook Time</span>
              <span className="text-sm font-semibold text-orange-900">{(() => { const v = content.cook_time ?? content.cook_time_minutes; return v != null && String(v) !== '' ? `${String(v).replace(/\s*minutes?\s*/i, '')} min` : '—'; })()}</span>
            </div>
            <div className="inline-flex items-center gap-2 px-4 py-3 bg-green-50 rounded-lg border border-green-100">
              <span className="text-sm text-green-700">Difficulty</span>
              <span className="text-sm font-semibold text-green-900">Easy</span>
            </div>
          </div>
        </div>

        {/* Mobile/tablet full-width badges below image, above ingredients */}
        {/* removed MetaCards duplicate for mobile in favor of unified stats bar */}

        {/* Ingredients & Instructions as separate white cards; no outer visual title */}
        <RecipeSection id="ingredients-section" title="Ingredients & Instructions" titleHidden variant="plain" className="px-0">
          <div className="grid gap-6 md:grid-cols-[2fr,3fr]">
            {/* Ingredients column */}
            <div 
              className={`rounded-2xl border border-black/5 shadow-sm p-4 sm:p-6 ${isEditing ? 'cursor-pointer' : ''}`}
              style={{ background: 'rgb(250 250 250 / 95%)' }}
              onClick={isEditing && activeEditField !== 'ingredients' ? () => activateFieldEdit('ingredients') : undefined}
              data-edit-field="ingredients"
            >
              <div className="flex items-center justify-between mb-3">
                <h3 id="ingredients" className="text-lg font-semibold flex items-center gap-2 scroll-mt-[88px]">
                  Ingredients
                </h3>
              </div>
              {isEditing && activeEditField === 'ingredients' ? (
                <div className="space-y-2" onDragEnd={clearDrag}>
                  {(edited?.ingredients||[]).map((ing, idx) => (
                    <div key={idx}
                         className={`relative flex items-center gap-2 p-2 rounded hover:bg-yellow-50 ${dragItem&&dragItem.type==='ingredients'&&dragItem.index===idx? 'ring-2 ring-amber-300' : ''}`}
                         draggable
                         onDragStart={handleDragStart('ingredients', idx)}
                         onDragOver={handleDragOver('ingredients', idx)}
                         onDrop={handleDrop('ingredients', idx)}
                    >
                      {dropIndicator && dropIndicator.type==='ingredients' && (
                        ((dropIndicator.pos==='before' && dropIndicator.index===idx) || (dropIndicator.pos==='after' && dropIndicator.index+1===idx)) && (
                          <div className="absolute -top-1 left-0 right-0 h-0.5 bg-amber-500" />
                        )
                      )}
                      <input value={ing.quantity||''} onChange={(e)=>setEdited(v=>{ const arr=[...(v?.ingredients||[])]; arr[idx]={...arr[idx], quantity:e.target.value}; return {...v, ingredients:arr}; })} className="w-24 border rounded-lg px-2 py-1" placeholder="Qty" />
                      <input value={ing.name||''} onChange={(e)=>setEdited(v=>{ const arr=[...(v?.ingredients||[])]; arr[idx]={...arr[idx], name:e.target.value}; return {...v, ingredients:arr}; })} className="flex-1 border rounded-lg px-3 py-1.5" placeholder="Ingredient" />
                      <button type="button" className="text-gray-500 hover:text-red-600 p-1" title="Remove ingredient" onClick={()=>confirmAndRemoveIngredient(idx)}>
                        <TrashIcon className="w-5 h-5" />
                      </button>
                      {dropIndicator && dropIndicator.type==='ingredients' && dropIndicator.pos==='after' && dropIndicator.index===idx && idx === (edited?.ingredients?.length||0) - 1 && (
                        <div className="absolute -bottom-1 left-0 right-0 h-0.5 bg-amber-500" />
                      )}
                    </div>
                  ))}
                  <div className="pt-1">
                    <button type="button" className="mt-2 px-3 py-1.5 rounded-lg bg-green-600 text-white hover:bg-green-700" onClick={addIngredientRow}>+ Add ingredient</button>
                  </div>
                </div>
               ) : (
                <ul className="space-y-2">
                  {ingredientsToRender.map((ing, idx) => {
                    const text = typeof ing === 'string' ? ing : `${ing.quantity || ''} ${ing.name || ''} ${ing.notes ? `(${ing.notes})` : ''}`.trim();
                    const m = /^(\S+\s+\S+)(.*)$/i.exec(text);
                    const shouldDim = false;
                    return (
                      <li 
                        key={idx} 
                        className={`flex items-start p-1 rounded ${isEditing ? 'hover:bg-yellow-50 cursor-pointer' : ''} focus:outline-none focus:ring-0 focus:border-0`}
                        onClick={isEditing ? () => activateFieldEdit('ingredients') : undefined}
                        onFocus={undefined}
                        onBlur={undefined}
                        tabIndex={-1}
                        data-edit-field="ingredients"
                      >
                        <span className="text-green-600 mr-3 mt-1 flex-shrink-0">•</span>
                        <span className="text-gray-700">{m ? (<><strong className="font-semibold text-gray-900">{m[1]}</strong>{m[2]}</>) : text}</span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            {/* Instructions column */}
            <div 
              className={`rounded-2xl border border-black/5 shadow-sm p-4 sm:p-6 ${isEditing ? 'cursor-pointer' : ''}`}
              style={{ background: 'rgb(250 250 250 / 95%)' }}
              onClick={isEditing && activeEditField !== 'instructions' ? () => activateFieldEdit('instructions') : undefined}
              data-edit-field="instructions"
            >
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-lg font-semibold flex items-center gap-2 scroll-mt-[88px]">
                  Instructions
                </h3>
                {!isEditing && (
                  <button 
                    onClick={() => setHoverHighlight(v => !v)} 
                    aria-pressed={hoverHighlight}
                    className={`inline-flex items-center gap-2 px-2 py-1 rounded-lg transition-colors ${
                      hoverHighlight 
                        ? 'text-blue-700 bg-blue-50 hover:bg-blue-100' 
                        : 'text-gray-700 hover:text-gray-900 hover:bg-gray-100'
                    }`}
                    title={hoverHighlight ? "Disable focus mode" : "Enable focus mode (instructions only)"}
                  >
                    {hoverHighlight ? (
                      <EyeIcon className="h-5 w-5 text-blue-600" />
                    ) : (
                      <EyeSlashIcon className="h-5 w-5" />
                    )}
                    <span className="text-sm font-medium">
                      {hoverHighlight ? 'Focus mode ON' : 'Focus mode'}
                    </span>
                  </button>
                )}
              </div>
              <div className="sr-only" aria-hidden="true"></div>
              {isEditing && activeEditField === 'instructions' ? (
                    <div className="space-y-2" onDragEnd={clearDrag}>
                  {(edited?.instructions||[]).map((st, idx) => (
                    <div key={idx}
                         className={`relative p-2 rounded hover:bg-yellow-50 ${dragItem&&dragItem.type==='instructions'&&dragItem.index===idx? 'ring-2 ring-amber-300' : ''}`}
                         draggable
                         onDragStart={handleDragStart('instructions', idx)}
                         onDragOver={handleDragOver('instructions', idx)}
                          onDrop={handleDrop('instructions', idx)}
                         onClick={() => { if (ttsActive) speakText(st.description || '', `st-${recipeId}-${idx}`); }}
                    >
                      {dropIndicator && dropIndicator.type==='instructions' && (
                        ((dropIndicator.pos==='before' && dropIndicator.index===idx) || (dropIndicator.pos==='after' && dropIndicator.index+1===idx)) && (
                          <div className="absolute -top-1 left-0 right-0 h-0.5 bg-amber-500" />
                        )
                      )}
                      <div className="flex items-start gap-3">
                        <div className="w-8 h-8 mt-1 rounded-full bg-[#e87b35] text-white inline-flex items-center justify-center font-bold shrink-0">{idx + 1}</div>
                        <div className="flex-1">
                          <textarea 
                            value={st.description||''} 
                            onChange={(e)=>{
                              setEdited(v=>{ 
                                const arr=[...(v?.instructions||[])]; 
                                arr[idx]={...arr[idx], description:e.target.value}; 
                                return {...v, instructions:arr}; 
                              });
                              autoResizeTextarea(e.target);
                            }} 
                            onInput={(e) => autoResizeTextarea(e.target)}
                            ref={(el) => {
                              if (el) autoResizeTextarea(el);
                            }}
                            className="w-full border rounded-lg px-3 py-2 focus:ring-2 ring-amber-200 resize-none overflow-hidden" 
                            rows={1}
                          />
                        </div>
                        <div className="shrink-0">
                          <button type="button" className="text-gray-500 hover:text-red-600 p-1" title="Remove step" onClick={()=>confirmAndRemoveInstruction(idx)}>
                            <TrashIcon className="w-5 h-5" />
                          </button>
                        </div>
                      </div>
                      {dropIndicator && dropIndicator.type==='instructions' && dropIndicator.pos==='after' && dropIndicator.index===idx && idx === (edited?.instructions?.length||0) - 1 && (
                        <div className="absolute -bottom-1 left-0 right-0 h-0.5 bg-amber-500" />
                      )}
                    </div>
                  ))}
                  <div className="pt-1">
                    <button type="button" className="mt-2 px-3 py-1.5 rounded-lg bg-green-600 text-white hover:bg-green-700" onClick={addInstructionRow}>+ Add step</button>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  {instructionsToRender.map((inst, idx) => {
                    const isActive = hoverHighlight && (
                      (keyboardFocusedItem?.type === 'instructions' && keyboardFocusedItem?.index === idx) ||
                      (!keyboardFocusedItem && hoveredItem?.type === 'instructions' && hoveredItem?.index === idx)
                    );
                    const hasAnyFocus = hoverHighlight && (hoveredItem?.type === 'instructions' || keyboardFocusedItem?.type === 'instructions');
                    const shouldDim = hasAnyFocus && !isActive;
                    return (
                      <div 
                        key={idx} 
                        className={`grid grid-cols-[2rem,1fr] gap-3 items-start p-1 rounded ${isEditing ? 'hover:bg-yellow-50 cursor-pointer' : ''} transition-all duration-200 will-change-opacity ${shouldDim ? 'opacity-40 blur-[1px]' : ''} focus:outline-none focus:ring-0 focus:border-0`} 
                        onClick={(e) => { 
                          if (isEditing) {
                            activateFieldEdit('instructions');
                          } else if (ttsActive) {
                            speakText(typeof inst === 'string' ? inst : (inst.description || ''), `st-${recipeId}-${idx}`);
                          }
                        }}
                        onMouseEnter={hoverHighlight ? () => handleHover('instructions', idx) : undefined}
                        onMouseLeave={hoverHighlight ? handleHoverLeave : undefined}
                        onFocus={hoverHighlight ? () => {
                          setKeyboardFocusedItem({ type: 'instructions', index: idx });
                        } : undefined}
                        onBlur={() => setKeyboardFocusedItem(null)}
                        tabIndex={hoverHighlight ? 0 : -1}
                        data-edit-field="instructions"
                      >
                        <div className="w-8 h-8 rounded-full bg-[#e87b35] text-white inline-flex items-center justify-center font-bold shrink-0">{idx + 1}</div>
                        <p className="text-gray-700 leading-relaxed">{typeof inst === 'string' ? inst : (inst.description || `Step ${idx + 1}`)}</p>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </RecipeSection>

        {/* Confirm delete modal */}
        {isEditing && confirmDelete && (
          <div className="fixed inset-0 z-40 flex items-center justify-center">
            <div className="absolute inset-0 bg-black/40" onClick={onCancelDelete} />
            <div className="relative z-50 w-[92vw] max-w-md bg-white rounded-2xl shadow-xl p-6">
              <div className="flex items-start gap-3">
                <div className="shrink-0 h-10 w-10 rounded-full bg-amber-100 flex items-center justify-center">
                  <ExclamationTriangleIcon className="h-6 w-6 text-amber-600" />
                </div>
                <div className="flex-1">
                  <h4 className="text-lg font-semibold text-gray-900 mb-1">Ta bort {confirmDelete.type === 'ingredient' ? 'ingrediens' : 'steg'}?</h4>
                  <p className="text-gray-600 text-sm">Detta går inte att ångra. Vill du fortsätta?</p>
                </div>
                <button onClick={onCancelDelete} className="text-gray-400 hover:text-gray-600">
                  <XMarkIcon className="w-6 h-6" />
                </button>
              </div>
              <div className="mt-5 flex justify-end gap-3">
                <button onClick={onCancelDelete} className="px-4 py-2 rounded-lg bg-gray-100 text-gray-800 hover:bg-gray-200">Avbryt</button>
                <button onClick={onConfirmDelete} className="px-4 py-2 rounded-lg bg-red-600 text-white hover:bg-red-700">Ta bort</button>
              </div>
            </div>
          </div>
        )}

      {variant !== 'modal' && (
      <RecipeSection id="nutrition" title="Nutrition Information (per serving)">
        <div className="flex flex-wrap items-center gap-2 mb-2 mt-6">
          {[{k:'calories', l:'Calories'},{k:'protein',l:'Protein'},{k:'fat',l:'Fat'},{k:'carbs',l:'Carbs'}].map(({k,l}) => (
            <div key={k} className="inline-flex items-center gap-2 bg-white text-gray-800 rounded-full px-3 py-1 border border-gray-200">
              <span className="text-sm text-gray-600">{l}</span>
              <span className="text-sm font-medium">{(() => {
                const val = resolveNutritionValue(nutrition, k);
                if (val === 0 || val === '0' || val === 0.0) return ['protein','fat','carbs'].includes(k) ? '0g' : '0';
                const formatted = (val !== undefined && val !== null && String(val).trim() !== '') ? formatNutritionValue(k, val) : '—';
                return k === 'calories' ? `${formatted} kcal` : formatted;
              })()}</span>
            </div>
          ))}
        </div>
      </RecipeSection>
      )}

      {/* Removed divider between Nutrition and social sections to keep seamless flow */}

        {/* Variants section for original recipes */}
        {isSaved && !content?.conversion?.isVariant && (
          <RecipeSection id="variants" title="Variants" titleHidden>
            <div className="flex items-center justify-between mb-4">
              <h2 className="scroll-mt-[88px] text-xl font-semibold">Variants</h2>
              <select 
                value={sort} 
                onChange={(e) => setSort(e.target.value)} 
                className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm"
              >
                <option value="popular">Most popular</option>
                <option value="newest">Newest</option>
                <option value="closest">Closest to your filters</option>
              </select>
            </div>
            <VariantsList 
              parentId={recipeId} 
              onOpenRecipeInModal={variant === 'modal' ? (id)=>onOpenRecipeInModal?.(id) : undefined}
              sort={sort}
            />
          </RecipeSection>
        )}


      {/* Source directly between Nutrition and Tags (omit in quick view) */}
      {variant !== 'modal' && sourceUrl && (
        <RecipeSection id="source" title="Source">
          <div className="bg-gray-50 p-4 rounded-lg flex items-center gap-3">
            <LinkIcon className="h-5 w-5 text-gray-400 flex-shrink-0" />
            <a href={sourceUrl} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline truncate">{sourceUrl}</a>
          </div>
        </RecipeSection>
      )}

      {/* Social section for saved recipes (omit in quick view via isSaved=false) */}
      {isSaved && (
        <div className="mt-8 mb-24">
          {/* Tags */}
          <RecipeSection id="tags" title="Tags" className="mt-8">
            <div className="flex flex-wrap gap-2 mb-3">
              {(() => {
                const approved = (tags.approved||[]);
                const out = [...approved];
                try {
                  const rc = recipe || {};
                  const conv = rc.conversion || {};
                  if (conv.isVariant) out.push({ keyword: 'Variant', type: 'variant' });
                  const presets = ((conv.constraints||{}).presets||[]).map(p=>String(p).toLowerCase());
                  const label = (p)=> p==='plant-based' ? 'Plant based' : p.charAt(0).toUpperCase()+p.slice(1);
                  ['vegan','vegetarian','pescetarian'].forEach(p=>{ if (presets.includes(p)) out.push({ keyword: label(p), type: 'diet' }); });
                } catch {}
                return out.map((t, idx) => (
                  <span key={`tag-${idx}-${t.keyword}`} className={`inline-flex items-center px-2 py-1 rounded-full text-xs border ${chipCls(t.type, t.keyword)}`}>
                    <span className="font-medium">{t.keyword}</span>
                  </span>
                ));
              })()}
            </div>
            {/* Input: no required validation in view/edit; only enforce on create */}
            <TagInput required={false} tags={[]} setTags={(ts)=>addTags((ts||[]).map(x=>x.label))} placeholder="Add new tag and press Add" />
          </RecipeSection>

          {/* Ratings */}
          <RecipeSection id="ratings" title="Ratings" className="mt-4">
            <div className="flex items-center gap-2" role="radiogroup" aria-label="Rate 1 to 5">
              {[1,2,3,4,5].map(v => (
                <button key={v} className={`w-6 h-6 ${v <= (rating.userValue || Math.round(rating.average)) ? 'text-yellow-400' : 'text-gray-300'}`} onClick={()=>putRating(v)}>
                  <svg viewBox="0 0 20 20" fill="currentColor"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/></svg>
                </button>
              ))}
              <span className="text-sm text-gray-600 ml-2">{Number(rating.average||0).toFixed(2)} ({rating.count})</span>
            </div>
          </RecipeSection>

      {/* Comments */}
      <RecipeSection id="comments" title="Comments" className="mt-8">
            <div className="bg-gray-50 rounded-lg p-4">
              <textarea value={commentInput} onChange={(e)=>setCommentInput(e.target.value)} rows={3} className="w-full bg-white px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent" placeholder="Write a comment..." />
              <div className="flex justify-end mt-2">
                <button onClick={postComment} className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700">Send</button>
              </div>
              <div className="mt-6">
                {(() => {
                  if (comments.length === 0) return (<p className="text-gray-500">Be the first to comment.</p>);
                  const byParent = new Map();
                  comments.forEach(cm => {
                    const pid = cm.parentId || 0; if (!byParent.has(pid)) byParent.set(pid, []); byParent.get(pid).push(cm);
                  });
                  const renderThread = (list, level=0) => (
                    <div>
                      {list.map((c) => (
                        <div key={c.id} className={`border border-gray-200 rounded-lg p-3 bg-white mb-3 ${level>0? 'ml-6 md:ml-10' : ''}`}>
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
                          <div className="flex justify-between items-center mt-2">
                            <div className="flex items-center gap-3">
                              <button onClick={()=>{ setReplyToId(c.id === replyToId ? null : c.id); setReplyText(''); }} className="text-sm text-blue-600 hover:underline">Reply</button>
                            </div>
                            <div className="flex items-center gap-3">
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
                          {replyToId === c.id && (
                            <div className="mt-3">
                              <textarea value={replyText} onChange={(e)=>setReplyText(e.target.value)} rows={2} className="w-full bg-white px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent" placeholder="Write a reply..." />
                              <div className="flex justify-end gap-2 mt-2">
                                <button onClick={()=>setReplyToId(null)} className="px-3 py-1.5 rounded-lg bg-gray-100 text-gray-700 text-sm">Cancel</button>
                                <button onClick={()=>postReply(c.id)} className="px-3 py-1.5 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-700">Reply</button>
                              </div>
                            </div>
                          )}
                          {byParent.has(c.id) && (
                            <div className="mt-3 border-l-2 border-gray-200 pl-3">
                              {renderThread(byParent.get(c.id), level+1)}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  );
                  return renderThread(byParent.get(0) || byParent.get(null) || []);
                })()}
              </div>
            </div>
      </RecipeSection>
          {isSticky && <div className="h-24" />}
        </div>
      )}
      </div>

      {/* Action Bar after content */}
      {variant !== 'modal' && (
      <div className={`mt-8`}>
          <div className="flex items-center justify-between py-4 ${variant === 'modal' ? '' : 'px-4 lg:px-8'}">
          <div className="flex-1">
            {!isEditing && (
              <div className="inline-flex items-center gap-2">
                <button aria-pressed={ttsActive} onClick={()=>setTtsActive(v=>!v)} className={`inline-flex items-center justify-center w-9 h-9 rounded-lg border ${ttsActive ? 'bg-emerald-50 border-emerald-300 text-emerald-700' : 'bg-white border-gray-300 text-gray-700'} hover:bg-gray-50`} title="Text-to-Speech">
                  {ttsActive ? (<SpeakerWaveIcon className="h-5 w-5" />) : (<SpeakerXMarkIcon className="h-5 w-5" />)}
                </button>
                {isTtsPlaying && (
                  <button onClick={()=>{ try{ if (window.speechSynthesis) window.speechSynthesis.cancel(); } catch {}; setIsTtsPlaying(false); }} className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-red-50 text-red-600 border border-red-200" title="Stop">
                    <span className="block w-3 h-3 bg-red-600" />
                  </button>
                )}
              </div>
            )}
          </div>
          <div className="flex flex-wrap justify-end gap-3">
            <button onClick={() => onDownload?.(content)} className="flex items-center justify-center gap-2 bg-[#00b5c3] text-white font-semibold py-2.5 px-5 rounded-lg hover:brightness-110 transition-colors text-sm">
              <ArrowDownTrayIcon className="h-5 w-5" />
              <span>Download PDF</span>
            </button>
            {!isSaved && (
              <button onClick={() => onSave?.(content)} className="flex items-center justify-center gap-2 bg-green-600 text-white font-semibold py-2.5 px-5 rounded-lg hover:bg-green-700 transition-colors text-sm">
                <BookmarkIcon className="h-5 w-5" />
                <span>Save to Recipes</span>
              </button>
            )}
            {isSaved && (
              <>
                <button onClick={()=>setConvertOpen(true)} className="flex items-center justify-center gap-2 bg-[#e87b35] text-white font-semibold py-2.5 px-5 rounded-lg hover:brightness-110 transition-colors text-sm">
                  <span>Convert</span>
                </button>
              <button onClick={() => { isEditing ? saveEdits() : startEdit(); }} disabled={busySave} className={`flex items-center justify-center gap-2 ${isEditing ? 'bg-green-600 hover:bg-green-700' : 'bg-violet-600 hover:bg-violet-700'} text-white font-semibold py-2.5 px-5 rounded-lg transition-colors disabled:opacity-60 text-sm`} data-save-button>
                  <PencilSquareIcon className="h-5 w-5" />
                  <span>{isEditing ? (busySave ? 'Saving…' : 'Save Changes') : 'Edit Recipe'}</span>
                </button>
              </>
            )}
            {justSavedVariant && (
              <>
                <button onClick={()=>{ if (variant==='modal' && typeof onOpenRecipeInModal==='function') { onOpenRecipeInModal(null); } }} className="flex items-center justify-center gap-2 bg-gray-100 text-gray-800 font-semibold py-3 px-6 rounded-lg hover:bg-gray-200 transition-colors">Close</button>
                <button onClick={()=>{ window.location.href = '/'; }} className="flex items-center justify-center gap-2 bg-blue-600 text-white font-semibold py-3 px-6 rounded-lg hover:bg-blue-700 transition-colors">View in My Recipes</button>
              </>
            )}
            {!isSaved && (
              <>
                <button onClick={() => onAddToCollection?.()} className="flex items-center justify-center gap-2 bg-[#da8146] text-white font-semibold py-3 px-6 rounded-lg hover:brightness-110 transition-colors">
                  <BookOpenIcon className="h-5 w-5" />
                  <span>Add to Collection</span>
                </button>
              <button onClick={() => { isEditing ? saveEdits() : startEdit(); }} disabled={busySave} className={`flex items-center justify-center gap-2 ${isEditing ? 'bg-green-600 hover:bg-green-700' : 'bg-violet-600 hover:bg-violet-700'} text-white font-semibold py-3 px-6 rounded-lg transition-colors disabled:opacity-60`} data-save-button>
                  <PencilSquareIcon className="h-5 w-5" />
                  <span>{isEditing ? (busySave ? 'Saving…' : 'Save Changes') : 'Edit Recipe'}</span>
                </button>
              </>
            )}
          </div>
        </div>
      </div>
      )}
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
              constraints={lastConstraints}
            />
          )}
           recipeId={recipeId}
           originalImage={image}
           baseTitle={title}
          onClose={()=>setConvertOpen(false)}
          onBack={()=>setPreviewResult(null)}
          onPreview={async (constraints)=>{
            try {
              setConvertBusy(true); setLastConstraints(constraints);
              setConvertError(''); setPreviewResult(null);
              console.info('[Convert] Building compact payload for preview...');
              const payload = buildUserPayload({
                title, description, ingredients, instructions,
                nutritionPerServing: nutrition
              }, constraints);
              const result = await convertRecipeWithDeepSeek({
                apiKey: process.env.DEEPSEEK_API_KEY || '',
                systemPrompt: (buildSystemPrompt ? buildSystemPrompt(constraints, constraints?.locale || 'sv') : SYSTEM_PROMPT),
                userPayload: payload,
                fast: true
              });
              if (!validateConversionSchema(result)) throw new Error('Invalid schema');
              setPreviewResult(result);
            } catch (e) {
              setConvertError(String(e?.message || 'Conversion failed'));
              console.error('[Convert] Preview failed:', e);
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
              // Switch modal to saved variant and show toast + deep-link + optimistic broadcast
              if (saved?.id) {
                setSavedVariantId(saved.id);
                try {
                  const parentId = saved.parentRecipeId || recipeId;
                  const url = `/recipes/${parentId}?variant=${saved.id}`;
                  window.history.pushState({}, '', url);
                } catch {}
                try {
                  window.dispatchEvent(new CustomEvent('recipes:variant-saved', { detail: { recipe: saved } }));
                } catch {}
                // Open saved variant in the same modal (desktop) or navigate in inline/page
                if (variant === 'modal' && typeof onOpenRecipeInModal === 'function') {
                  onOpenRecipeInModal(saved.id, { sourceRecipeId: recipeId, sourceTitle: title });
                } else if (variant === 'inline') {
                  try {
                    window.location.href = `/recipes/${saved.id}`;
                  } catch {}
                }
                // If this RecipeView is rendered inside Collections modal without onOpenRecipeInModal, broadcast an intent
                if (variant === 'modal' && typeof onOpenRecipeInModal !== 'function') {
                  try {
                    window.dispatchEvent(new CustomEvent('collections:open-recipe', { detail: { id: saved.id, fromId: recipeId, fromTitle: title } }));
                  } catch {}
                }
              }
              setJustSavedVariant(true);
              setConvertOpen(false);
            } catch (e) {
              setConvertError(String(e?.message || 'Failed to save variant'));
            } finally { setConvertBusy(false); }
          }}
        />
      )}
    </div>
  );
}


