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
import { ClockIcon, TrashIcon, EllipsisVerticalIcon, XMarkIcon, ExclamationTriangleIcon, EyeIcon, EyeSlashIcon } from '@heroicons/react/24/outline';
import TagInput from './TagInput';
import RecipeConvertPanel from './RecipeConvertPanel';
import { convertRecipeWithDeepSeek, validateConversionSchema } from './deepseekClient';
import { SYSTEM_PROMPT, buildUserPayload, buildSystemPrompt } from './DeepSeekPrompts';
import DeepSeekPreviewDiff from './DeepSeekPreviewDiff';
import VariantsList from './VariantsList';

const API_BASE = 'http://localhost:8000/api/v1';
const STATIC_BASE = 'http://localhost:8000';

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
  if (l === 'zesty') return 'bg-yellow-500 text-white border-yellow-500';
  if (l === 'seafood') return 'bg-blue-600 text-white border-blue-600';
  if (l === 'vegetarian') return 'bg-lime-600 text-white border-lime-600';
  if (l === 'pescetarian' || l === 'pescatarian') return 'bg-blue-600 text-white border-blue-600';
  if (l === 'fastfood') return 'bg-orange-500 text-white border-orange-500';
  if (l === 'spicy') return 'bg-red-600 text-white border-red-600';
  if (l === 'chicken') return 'bg-amber-600 text-white border-amber-600';
  if (l === 'eggs') return 'bg-yellow-400 text-white border-yellow-400';
  if (l === 'cheese') return 'bg-yellow-300 text-gray-800 border-yellow-300';
  if (l === 'fruits') return 'bg-pink-500 text-white border-pink-500';
  if (l === 'wine') return 'bg-purple-600 text-white border-purple-600';
  if (l === 'pasta') return 'bg-orange-600 text-white border-orange-600';
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
  const [hoverHighlight, setHoverHighlight] = useState(() => {
    const saved = localStorage.getItem('recipeFocusMode');
    return saved === 'true';
  });
  const [cartMode, setCartMode] = useState(() => {
    const saved = localStorage.getItem(`recipe:${recipeId}:cartMode`);
    return saved === 'true';
  });
  const [selectedIngredients, setSelectedIngredients] = useState(new Set());
  const [layoutMode, setLayoutMode] = useState(() => {
    const saved = localStorage.getItem('recipeLayoutMode');
    return saved === 'single' ? 'single' : 'two';
  });
  const [ttsActive, setTtsActive] = useState(() => {
    const saved = localStorage.getItem('recipeTTS');
    return saved === 'true';
  });
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
  const [showTimePopover, setShowTimePopover] = useState(false);
  const [showNutritionDetails, setShowNutritionDetails] = useState(false);
  const [highlightedNutritionRow, setHighlightedNutritionRow] = useState(null);
  const [nutritionData, setNutritionData] = useState(null);
  const [nutritionLoading, setNutritionLoading] = useState(false);
  const [nutritionError, setNutritionError] = useState(null);
  const timePopoverRef = useRef(null);
  const titleInputRef = useRef(null);
  const nutritionTableRef = useRef(null);

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
  
  // Servings calculator state
  const [currentServings, setCurrentServings] = useState(() => {
    const saved = localStorage.getItem(`recipe:${recipeId}:servings`);
    return saved ? parseInt(saved, 10) : (content.servings || content.serves || 4);
  });
  const originalServings = useMemo(() => {
    const raw = content.servings || content.serves || 4;
    if (typeof raw === 'number') return raw;
    const m = String(raw).match(/\d+(?:[\.,]\d+)?/);
    return m ? parseFloat(m[0].replace(',', '.')) : 4;
  }, [content.servings, content.serves]);
  const servingsFactor = useMemo(() => {
    const numCurrent = Number(currentServings);
    const numOriginal = Number(originalServings);
    if (!Number.isFinite(numCurrent) || !Number.isFinite(numOriginal) || numOriginal === 1) {
      return Number.isFinite(numCurrent) && Number.isFinite(numOriginal) && numOriginal !== 0
        ? numCurrent / numOriginal
        : 1;
    }
    return numCurrent / numOriginal;
  }, [currentServings, originalServings]);

  // Update currentServings when recipe changes
  useEffect(() => {
    const saved = localStorage.getItem(`recipe:${recipeId}:servings`);
    if (!saved) {
      // Reset to original servings when recipe changes (only if no saved preference)
      setCurrentServingsAndSave(originalServings);
    }
  }, [originalServings, recipeId]);



  const setCurrentServingsAndSave = (servings) => {
    setCurrentServings(servings);
    localStorage.setItem(`recipe:${recipeId}:servings`, servings.toString());
  };

  // Servings calculator helper functions
  const shouldNotScale = (text) => {
    const lower = text.toLowerCase();
    return lower.includes('to taste') || lower.includes('pinch') || lower.includes('dash') || 
           lower.includes('valfritt') || lower.includes('efter smak');
  };

  const isDiscrete = (text) => {
    if (!text) return false;
    const lower = text.toLowerCase();
    return lower.includes('ägg') || lower.includes('egg') || lower.includes('klyfta') || 
           lower.includes('clove') || lower.includes('st') || lower.includes('piece');
  };

  const scaleQuantity = (quantity, factor) => {
    if (!quantity || factor === 1) return quantity;
    if (!Number.isFinite(factor)) return quantity;
    if (shouldNotScale(quantity)) return quantity;

    if (typeof quantity !== 'string') {
      const num = Number(quantity);
      return Number.isFinite(num) ? num * factor : quantity;
    }

    let q = quantity.trim();
    let prefix = '';
    const caMatch = q.match(/^ca\s+/i);
    if (caMatch) {
      prefix = caMatch[0].trim() + ' ';
      q = q.slice(caMatch[0].length).trim();
    }

    const unicodeMap = { '¼': 0.25, '½': 0.5, '¾': 0.75, '⅓': 1/3, '⅔': 2/3, '⅛': 0.125, '⅜': 0.375, '⅝': 0.625, '⅞': 0.875 };
    const unicodeClass = '¼½¾⅓⅔⅛⅜⅝⅞';
    const re = new RegExp(`^(?:\\d+\\s+\\d+/\\d+|\\d+[.,]?\\d*\\s*[${unicodeClass}]?|[${unicodeClass}]|\\d+/\\d+|\\d+[.,]?\\d*)`);
    const m = q.match(re);
    if (!m) return quantity;

    const numStr = m[0];
    let value = NaN;
    const normalizeComma = (s) => s.replace(',', '.');

    if (/^\d+\s+\d+\/\d+$/.test(numStr)) {
      const [i, frac] = numStr.split(/\s+/);
      const [n, d] = frac.split('/').map(Number);
      value = Number(i) + (d ? n/d : 0);
    } else if (new RegExp(`^\\d+[.,]?\\d*\\s*[${unicodeClass}]$`).test(numStr)) {
      const intPart = numStr.slice(0, -1);
      const fracChar = numStr.slice(-1);
      value = parseFloat(normalizeComma(intPart)) + (unicodeMap[fracChar] || 0);
    } else if (new RegExp(`^[${unicodeClass}]$`).test(numStr)) {
      value = unicodeMap[numStr] ?? NaN;
    } else if (/^\d+\/\d+$/.test(numStr)) {
      const [n, d] = numStr.split('/').map(Number);
      value = d ? n/d : NaN;
    } else {
      value = parseFloat(normalizeComma(numStr));
    }

    if (!Number.isFinite(value)) return quantity;

    const after = q.slice(numStr.length).trim();
    const scaled = value * factor;
    const scaledStr = String(scaled).replace(/\.0$/, '');
    return `${prefix}${scaledStr}${after ? ' ' + after : ''}`.trim();
  };

  const formatQuantity = (quantity) => {
    if (typeof quantity === 'string') {
      const trimmed = quantity.trim();
      if (!trimmed || /^nan$/i.test(trimmed)) return '';
      return trimmed;
    }
    if (quantity == null || Number.isNaN(quantity)) return '';
    if (quantity === 0.25) return '¼';
    if (quantity === 0.5) return '½';
    if (quantity === 0.75) return '¾';
    if (quantity === 0.33) return '⅓';
    if (quantity === 0.67) return '⅔';
    return quantity.toString();
  };

  const getScaledIngredients = () => {
    const ingredientsToUse = edited?.ingredients || ingredients;
    return ingredientsToUse.map(ing => {
      if (typeof ing === 'string') {
        const { quantity, name } = splitQuantityFromText(ing);
        if (shouldNotScale(quantity) || shouldNotScale(name)) {
          return ing; // Don't scale "to taste" etc.
        }
        const scaledQuantity = scaleQuantity(quantity, servingsFactor);
        
        // Handle discrete ingredients
        if (isDiscrete(name)) {
          if (scaledQuantity < 0.5) return 'valfritt';
          const rounded = Math.round(scaledQuantity * 2) / 2;
          return `${formatQuantity(rounded)} ${name}`.trim();
        }
        
        return `${formatQuantity(scaledQuantity)} ${name}`.trim();
      } else {
        const scaledQuantity = scaleQuantity(ing.quantity, servingsFactor);
        
        // Handle discrete ingredients
        if (isDiscrete(ing.name)) {
          if (scaledQuantity < 0.5) return { ...ing, quantity: 'valfritt' };
          const rounded = Math.round(scaledQuantity * 2) / 2;
          return { ...ing, quantity: formatQuantity(rounded) };
        }
        
        return {
          ...ing,
          quantity: formatQuantity(scaledQuantity)
        };
      }
    });
  };

  const getScaledNutrition = useMemo(() => {
    // Use backend nutrition data if available, otherwise fall back to content data
    if (nutritionData) {
      const per = nutritionData.perServing || {};
      const tot = nutritionData.total || {};
      const servingsForScale = Number(currentServings || originalServings || 1) || 1;
      // Always compute Total batch relative to the servings currently selected in the UI
      const computedTotal = Object.fromEntries(
        Object.entries(per).map(([k, v]) => [k, (typeof v === 'number' && Number.isFinite(v)) ? Math.round(v * servingsForScale * 10) / 10 : (typeof tot[k] === 'number' ? tot[k] : null)])
      );
      return {
        perServing: per,
        total: computedTotal
      };
    }
    
    // Fallback to content data
    const nutrition = content.nutritional_information || content.nutrition || content.nutritionPerServing || {};
    const totalNutrition = {
      calories: (nutrition.calories || 0) * originalServings,
      protein: (nutrition.protein || 0) * originalServings,
      carbs: (nutrition.carbs || nutrition.carbohydrates || 0) * originalServings,
      fat: (nutrition.fat || 0) * originalServings,
      sodium: (nutrition.sodium || 0) * originalServings,
      saturatedFat: (nutrition.saturated_fat || nutrition.saturatedFat || 0) * originalServings,
      sugar: (nutrition.sugar || 0) * originalServings,
      fiber: (nutrition.fiber || nutrition.fibre || 0) * originalServings,
      cholesterol: (nutrition.cholesterol || 0) * originalServings
    };
    
    return {
      perServing: {
        calories: Math.round(totalNutrition.calories / currentServings),
        protein: Math.round(totalNutrition.protein / currentServings),
        carbs: Math.round(totalNutrition.carbs / currentServings),
        fat: Math.round(totalNutrition.fat / currentServings),
        sodium: Math.round(totalNutrition.sodium / currentServings),
        saturatedFat: Math.round(totalNutrition.saturatedFat / currentServings),
        sugar: Math.round(totalNutrition.sugar / currentServings),
        fiber: Math.round(totalNutrition.fiber / currentServings),
        cholesterol: Math.round(totalNutrition.cholesterol / currentServings)
      },
      total: totalNutrition
    };
  }, [nutritionData, content.nutritional_information, content.nutrition, content.nutritionPerServing, originalServings, currentServings]);

  // Helpers to avoid NaN rendering
  const asNumberOrNull = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null);

  // Nutrition detail functions
  const handleNutritionChipClick = (nutritionKey) => {
    if (!showNutritionDetails) {
      setShowNutritionDetails(true);
    }
    
    // Highlight the corresponding row
    setHighlightedNutritionRow(nutritionKey);
    
    // Clear highlight after 1.5 seconds
    setTimeout(() => setHighlightedNutritionRow(null), 1500);
    
    // Scroll to the nutrition table
    if (nutritionTableRef.current) {
      nutritionTableRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  const getNutritionRDI = (nutrient, value) => {
    if (!value) return null;
    
    const rdiValues = {
      calories: 2000,
      protein: 50,
      fat: 70,
      saturatedFat: 20,
      carbs: 260,
      sugar: 90,
      fiber: 25,
      sodium: 2300,
      cholesterol: 300
    };
    
    const rdi = rdiValues[nutrient];
    if (!rdi) return null;
    
    return Math.round((value / rdi) * 100);
  };

  // Fetch nutrition data from backend
  const fetchNutritionData = async (servings) => {
    const logGroup = `[Nutrition] fetch ${new Date().toISOString()} recipeId=${recipeId} servings=${servings}`;
    const t0 = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
    try {
      setNutritionLoading(true);
      setNutritionError(null);

      const ingredientsToUse = edited?.ingredients || ingredients;

      const ingredientsForAPI = ingredientsToUse.map(ing => {
        if (typeof ing === 'string') {
          return { raw: ing };
        } else {
          return { raw: `${ing.quantity || ''} ${ing.name || ''}`.trim() };
        }
      });

      const requestBody = {
        recipeId: recipeId ? String(recipeId) : 'unknown',
        servings: servings,
        ingredients: ingredientsForAPI,
      };

      // Console logging: compact, human-readable
      try {
        console.groupCollapsed(logGroup);
        const sample = ingredientsForAPI.slice(0, 5).map(i => `- ${i.raw}`).join('\n');
        console.log(`-> POST ${API_BASE}/nutrition/calc`);
        console.log(`-> servings=${servings} items=${ingredientsForAPI.length}`);
        if (ingredientsForAPI.length > 0) {
          console.log(`-> sample ingredients (first ${Math.min(5, ingredientsForAPI.length)}):\n${sample}${ingredientsForAPI.length > 5 ? '\n...' : ''}`);
        }
      } catch {}

      const response = await fetch(`${API_BASE}/nutrition/calc`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify(requestBody)
      });

      // Console logging: response status
      try {
        console.log(`<= status ${response.status} ok=${response.ok}`);
      } catch {}

      if (!response.ok) {
        const text = await response.text().catch(() => '');
        try { console.log('response.text', text?.slice(0, 2000)); } catch {}
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      // Console logging: concise summary
      try {
        const t1 = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
        const p = data?.perServing || {};
        const compact = `kcal=${p?.calories ?? '—'} protein=${p?.protein ?? '—'}g fat=${p?.fat ?? '—'}g carbs=${p?.carbs ?? '—'}g salt=${(p?.salt != null ? p.salt : (typeof p?.sodium === 'number' ? (p.sodium * 2.5 / 1000).toFixed(1) : '—'))}g`;
        const warnCount = Array.isArray(data?.warnings) ? data.warnings.length : 0;
        const reviewCount = Array.isArray(data?.needsReview) ? data.needsReview.length : 0;
        console.log(`<= summary (${Math.round(t1 - t0)}ms): ${compact} | warnings=${warnCount} needsReview=${reviewCount}`);
        // Optional detailed table if explicitly enabled in console
        if (typeof window !== 'undefined' && window.__NUTRITION_DEBUG && Array.isArray(data?.debugEntries)) {
          const rows = data.debugEntries.map(e => ({
            original: e.original,
            normalized: e.normalized,
            grams: e.grams,
            kcal: e.contribution?.calories,
            protein: e.contribution?.protein,
            fat: e.contribution?.fat,
            carbs: e.contribution?.carbs,
            salt: e.contribution?.salt,
            source: e.source_hit
          }));
          console.table(rows);
        }
      } catch {}
      setNutritionData(data);
    } catch (error) {
      try { console.error('[Nutrition] fetch error', String(error && error.message ? error.message : error)); } catch {}
      setNutritionError(error.message);
      setNutritionData(null);
    } finally {
      setNutritionLoading(false);
      try { console.groupEnd(logGroup); } catch {}
    }
  };

  // Snapshot-first fetch: GET /nutrition/:recipeId with polling when pending
  const [snapshotPolls, setSnapshotPolls] = useState(0);
  const fetchNutritionSnapshot = async (attempt = 0) => {
    if (!recipeId) return;
    const url = `${API_BASE}/nutrition/${recipeId}`;
    const t0 = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
    try {
      setNutritionLoading(true);
      // Plain text, no object spam
      console.log(`[Nutrition] SNAPSHOT GET ${url}`);
      const res = await fetch(url, { credentials: 'include' });
      const t1 = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
      console.log(`[Nutrition] STATUS ${res.status} in ${Math.round(t1 - t0)}ms`);
      if (!res.ok) {
        const text = await res.text().catch(() => '');
        console.warn(`[Nutrition] NON-OK ${res.status}: ${String(text || '').slice(0,200)}`);
        return;
      }
      const json = await res.json();
      if (json?.status === 'ready' && json?.data) {
        const p = json.data?.perServing || {};
        const summary = `kcal=${p.calories ?? '-'} protein=${p.protein ?? '-'}g fat=${p.fat ?? '-'}g carbs=${p.carbs ?? '-'}g salt=${(p.salt ?? '-') }g`;
        console.log(`[Nutrition] READY ${summary}`);
        // Print plain-text per-ingredient debug lines, if present
        try {
          const lines = json?.data?.meta?.debugLines;
          if (Array.isArray(lines) && lines.length) {
            console.log('[Nutrition] DEBUG\n' + lines.join('\n'));
          }
        } catch {}
        setNutritionData(json.data);
        setNutritionError(null);
        setNutritionLoading(false);
        setSnapshotPolls(0);
        return;
      }
      // Pending
      console.log(`[Nutrition] PENDING (poll ${attempt + 1})`);
      // Pending → poll a few times with backoff
      const nextAttempt = attempt + 1;
      setSnapshotPolls(nextAttempt);
      if (nextAttempt <= 12) { // ~ up to ~18s total with backoff
        const delay = Math.min(3000, 800 + nextAttempt * 600);
        setTimeout(() => fetchNutritionSnapshot(nextAttempt), delay);
      } else {
        console.warn('snapshot pending too long; stop polling');
        setNutritionLoading(false);
      }
    } catch (e) {
      console.error('[Nutrition] snapshot error', e);
      setNutritionLoading(false);
    } finally {}
  };

  // --- Ingredient translations for UI ---
  const [uiTranslations, setUiTranslations] = useState({});
  const uiLang = 'sv';
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const url = `${API_BASE}/ingredients/translations?lang=${uiLang}`;
      const t0 = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
      try {
        console.groupCollapsed(`[Translations] GET ${url}`);
        const res = await fetch(url, { credentials: 'include' });
        console.log('status', res.status);
        if (res.ok) {
          const json = await res.json();
          console.log('count', Object.keys(json || {}).length);
          if (!cancelled) setUiTranslations(json || {});
        } else {
          const text = await res.text().catch(() => '');
          console.warn('non-OK response', res.status, text?.slice(0, 500));
        }
      } catch (e) {
        console.error('[Translations] error', e);
      } finally {
        const t1 = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
        console.log('timing.ms', Math.round(t1 - t0));
        console.groupEnd(`[Translations] GET ${url}`);
      }
    })();
    return () => { cancelled = true; };
  }, [API_BASE]);

  // Helper to render ingredient name with translation if we know canonical id via explanations
  const getDisplayName = (rawName) => {
    // fallback: just return provided name
    return rawName;
  };

  const title = content.title || '';
  const image = content.image_url || content.thumbnail_path || content.img || null;
  const description = content.description || '';
  const ingredients = Array.isArray(content.ingredients) ? content.ingredients : [];
  const instructions = Array.isArray(content.instructions) ? content.instructions : [];

  // Fetch nutrition data when component mounts or servings change
  useEffect(() => {
    const reason = [];
    if (!currentServings) reason.push('no currentServings');
    if (!(ingredients.length > 0)) reason.push('no ingredients');
    if (!recipeId) reason.push('no recipeId');
    console.log('[Nutrition] effect trigger', { currentServings, ingredientsCount: ingredients.length, recipeId, reason: reason.length ? reason.join(', ') : 'ok' });
    // Snapshot-first path
    if (recipeId && !nutritionData) {
      fetchNutritionSnapshot(0);
    }
    // Fallback compute path (e.g., after user edits ingredients/servings)
    if (currentServings && ingredients.length > 0 && recipeId && edited?.ingredients) {
      fetchNutritionData(currentServings);
    }
  }, [currentServings, ingredients, edited?.ingredients, recipeId]);

  const skippedCount = (() => {
    try { return Array.isArray(nutritionData?.meta?.skipped) ? nutritionData.meta.skipped.length : 0; } catch { return 0; }
  })();
  const ingredientsToRender = useMemo(() => {
    const ingredientsToUse = edited?.ingredients || ingredients;
    const baseIngredients = variant === 'modal' ? ingredientsToUse.slice(0, 8) : ingredientsToUse;
    
    // Apply servings scaling
    return baseIngredients.map(ing => {
      if (typeof ing === 'string') {
        const { quantity, name } = splitQuantityFromText(ing);
        if (shouldNotScale(quantity) || shouldNotScale(name)) {
          return ing; // Don't scale "to taste" etc.
        }
        const scaledQuantity = scaleQuantity(quantity, servingsFactor);
        
        // Handle discrete ingredients
        if (isDiscrete(name)) {
          if (scaledQuantity < 0.5) return 'valfritt';
          const rounded = Math.round(scaledQuantity * 2) / 2;
          return `${formatQuantity(rounded)} ${name}`.trim();
        }
        
        return `${formatQuantity(scaledQuantity)} ${name}`.trim();
      } else {
        const scaledQuantity = scaleQuantity(ing.quantity, servingsFactor);
        
        // Handle discrete ingredients
        if (isDiscrete(ing.name)) {
          if (scaledQuantity < 0.5) return { ...ing, quantity: 'valfritt' };
          const rounded = Math.round(scaledQuantity * 2) / 2;
          return { ...ing, quantity: formatQuantity(rounded) };
        }
        
        return {
          ...ing,
          quantity: formatQuantity(scaledQuantity)
        };
      }
    });
  }, [variant, ingredients, edited?.ingredients, servingsFactor]);
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
    // Automatically exit shopping list mode when entering edit mode
    if (cartMode) {
      setCartModeAndSave(false);
    }
    
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

  const cancelEdit = () => {
    setIsEditing(false);
    setActiveEditField(null);
    setEdited(null);
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

  const removeTag = async (keyword) => {
    try {
      const res = await fetch(`${API_BASE}/recipes/${recipeId}/tags?keyword=${encodeURIComponent(keyword)}`, { method:'DELETE', credentials:'include' });
      const json = await res.json();
      if (json.ok) {
        // Remove from local state
        setTags((t) => ({
          approved: t.approved.filter(tag => tag.keyword !== keyword),
          pending: t.pending.filter(tag => tag.keyword !== keyword),
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

  // localStorage save functions
  const setLayoutModeAndSave = (mode) => {
    setLayoutMode(mode);
    localStorage.setItem('recipeLayoutMode', mode);
  };

  const setHoverHighlightAndSave = (enabled) => {
    setHoverHighlight(enabled);
    localStorage.setItem('recipeFocusMode', enabled.toString());
  };

  const setTtsActiveAndSave = (enabled) => {
    setTtsActive(enabled);
    localStorage.setItem('recipeTTS', enabled.toString());
  };

  const setCartModeAndSave = (enabled) => {
    setCartMode(enabled);
    localStorage.setItem(`recipe:${recipeId}:cartMode`, enabled.toString());
  };

  const toggleIngredientSelection = (index) => {
    setSelectedIngredients(prev => {
      const newSet = new Set(prev);
      if (newSet.has(index)) {
        newSet.delete(index);
      } else {
        newSet.add(index);
      }
      return newSet;
    });
  };



  const addToShoppingList = () => {
    const ingredientsToAdd = selectedIngredients.size > 0 
      ? Array.from(selectedIngredients).map(idx => ingredientsToRender[idx])
      : ingredientsToRender;
    
    // Get existing shopping list
    const existingList = JSON.parse(localStorage.getItem('shoppingList:v1') || '[]');
    
    ingredientsToAdd.forEach(ingredient => {
      const text = typeof ingredient === 'string' ? ingredient : `${ingredient.quantity || ''} ${ingredient.name || ''} ${ingredient.notes ? `(${ingredient.notes})` : ''}`.trim();
      
      // Parse ingredient text to extract quantity, unit, and name
      const match = text.match(/^([\d\/\s]+)?\s*([a-zA-Z]+)?\s+(.+)$/);
      let quantity = '';
      let unit = '';
      let name = text;
      
      if (match) {
        quantity = (match[1] || '').trim();
        unit = (match[2] || '').trim();
        name = (match[3] || '').trim();
      }
      
      // Normalize name
      const normalizedName = name.toLowerCase().trim().replace(/\s+/g, ' ');
      
      // Check if item already exists
      const existingIndex = existingList.findIndex(item => 
        item.name.toLowerCase().trim().replace(/\s+/g, ' ') === normalizedName && 
        item.unit === unit
      );
      
      if (existingIndex >= 0) {
        // Merge quantities if possible
        const existing = existingList[existingIndex];
        if (quantity && existing.quantity) {
          // Simple merge - could be improved with proper unit conversion
          existing.quantity = `${existing.quantity} + ${quantity}`;
        }
        // Add source if not already present
        if (!existing.sources.some(s => s.recipeId === recipeId)) {
          existing.sources.push({
            recipeId: recipeId,
            title: title
          });
        }
      } else {
        // Add new item
        const category = getIngredientCategory(name);
        existingList.push({
          name: name,
          quantity: quantity,
          unit: unit,
          category: category,
          checked: false,
          sources: [{
            recipeId: recipeId,
            title: title
          }],
          addedAt: new Date().toISOString()
        });
      }
    });
    
    // Save updated list
    localStorage.setItem('shoppingList:v1', JSON.stringify(existingList));
    
    // Dispatch custom event to update badge
    window.dispatchEvent(new CustomEvent('shoppingListUpdated'));
    
    // Show toast
    const count = ingredientsToAdd.length;
            const message = `Added ${count} item${count !== 1 ? 's' : ''} to Shop List`;
    
    // Create toast notification
    const toast = document.createElement('div');
    toast.className = 'fixed bottom-4 left-1/2 transform -translate-x-1/2 md:left-auto md:right-4 md:transform-none bg-green-600 text-white px-4 py-3 rounded-lg shadow-lg z-50 flex items-center gap-3 max-w-sm';
    toast.setAttribute('aria-live', 'polite');
    toast.innerHTML = `
      <span>${message}</span>
      <button onclick="window.location.href='/shopping-list'" class="bg-white text-green-600 px-2 py-1 rounded text-sm font-medium hover:bg-gray-100">
        View list
            </button>
    `;
    document.body.appendChild(toast);
    
    // Remove toast after 4 seconds
    setTimeout(() => {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
    }, 4000);
    
    // Close toast on click outside or ESC
    const handleClickOutside = (event) => {
      if (!toast.contains(event.target)) {
        if (toast.parentNode) {
          toast.parentNode.removeChild(toast);
        }
        document.removeEventListener('click', handleClickOutside);
        document.removeEventListener('keydown', handleEscape);
      }
    };
    
    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        if (toast.parentNode) {
          toast.parentNode.removeChild(toast);
        }
        document.removeEventListener('click', handleClickOutside);
        document.removeEventListener('keydown', handleEscape);
      }
    };
    
    // Add event listeners after a small delay to avoid immediate trigger
    setTimeout(() => {
      document.addEventListener('click', handleClickOutside);
      document.addEventListener('keydown', handleEscape);
    }, 100);
  };

  const getIngredientCategory = (name) => {
    const lowerName = name.toLowerCase();
    
    if (lowerName.includes('milk') || lowerName.includes('cheese') || lowerName.includes('yogurt') || lowerName.includes('cream') || lowerName.includes('butter')) {
      return 'Dairy';
    }
    if (lowerName.includes('apple') || lowerName.includes('banana') || lowerName.includes('tomato') || lowerName.includes('lettuce') || lowerName.includes('carrot') || lowerName.includes('onion') || lowerName.includes('garlic') || lowerName.includes('lemon') || lowerName.includes('lime') || lowerName.includes('mango') || lowerName.includes('berry') || lowerName.includes('fruit') || lowerName.includes('vegetable')) {
      return 'Produce';
    }
    if (lowerName.includes('chicken') || lowerName.includes('beef') || lowerName.includes('pork') || lowerName.includes('fish') || lowerName.includes('salmon') || lowerName.includes('tuna') || lowerName.includes('shrimp') || lowerName.includes('meat')) {
      return 'Meat/Fish';
    }
    if (lowerName.includes('bread') || lowerName.includes('pasta') || lowerName.includes('rice') || lowerName.includes('flour') || lowerName.includes('sugar') || lowerName.includes('salt') || lowerName.includes('oil') || lowerName.includes('vinegar') || lowerName.includes('spice') || lowerName.includes('herb')) {
      return 'Pantry';
    }
    if (lowerName.includes('frozen') || lowerName.includes('ice cream') || lowerName.includes('peas') || lowerName.includes('corn')) {
      return 'Frozen';
    }
    if (lowerName.includes('cake') || lowerName.includes('cookie') || lowerName.includes('pastry') || lowerName.includes('bread')) {
      return 'Bakery';
    }
    
    return 'Other';
  };

  // Helper functions for time calculation and popover
  const getTimeValue = (timeField) => {
    const v = content[timeField] ?? content[`${timeField}_minutes`];
    if (v == null || String(v) === '') return null;
    return parseInt(String(v).replace(/\s*minutes?\s*/i, ''), 10);
  };

  const prepTime = getTimeValue('prep_time');
  const cookTime = getTimeValue('cook_time');
  const totalTime = (prepTime || 0) + (cookTime || 0);

  const getDifficultyText = (level) => {
    if (!level) return 'Beginner'; // Default fallback
    const num = parseInt(level, 10);
    if (num === 1) return 'Beginner';
    if (num === 2) return 'Intermediate';
    if (num === 3) return 'Advanced';
    return level; // fallback to original value
  };

  const difficulty = getDifficultyText(content.difficulty || content.difficulty_level);

  // Popover handlers
  const handleTimeClick = () => {
    if (window.innerWidth < 768) { // mobile
      setShowTimePopover(!showTimePopover);
    }
  };

  const handleTimeMouseEnter = () => {
    if (window.innerWidth >= 768) { // desktop
      setShowTimePopover(true);
    }
  };

  const handleTimeMouseLeave = () => {
    if (window.innerWidth >= 768) { // desktop
      setShowTimePopover(false);
    }
  };

  // Close popover when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (timePopoverRef.current && !timePopoverRef.current.contains(event.target)) {
        setShowTimePopover(false);
      }
    };

    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setShowTimePopover(false);
      }
    };

    if (showTimePopover) {
      document.addEventListener('mousedown', handleClickOutside);
      document.addEventListener('keydown', handleEscape);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [showTimePopover]);

  // Handle clicks outside title input field
  useEffect(() => {
    const handleTitleClickOutside = (event) => {
      if (titleInputRef.current && !titleInputRef.current.contains(event.target)) {
        // Check if the click is not on a Save/Cancel button
        const isSaveButton = event.target.closest('button[data-save-button]');
        const isCancelButton = event.target.closest('button[data-cancel-button]');
        
        if (!isSaveButton && !isCancelButton) {
          setActiveEditField(null);
        }
      }
    };

    if (isEditing && activeEditField === 'title') {
      document.addEventListener('mousedown', handleTitleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleTitleClickOutside);
    };
  }, [isEditing, activeEditField]);

  return (
    <div className={`w-full min-h-screen ${variant === 'modal' ? 'max-w-[1180px]' : ''}`}>
      <div className="max-w-7xl mx-auto space-y-6">

        {/* Recipe Header Layout */}
        <div className="mb-8">
          {/* Title Block */}
          <div className="mb-6">
            <div className="flex items-start justify-between gap-4 mb-4">
              <div className="flex-1">
                <h1 className="text-5xl font-bold text-gray-900 recipe-title mb-4" style={{ fontFamily: "'Playfair Display', serif" }}>
              {isEditing && activeEditField === 'title' ? (
                    <div data-edit-field="title" className="w-full" ref={titleInputRef}>
                  <input
                    value={edited?.title || ''}
                    onChange={(e)=>setEdited(v=>({...(v||{}), title: e.target.value}))}
                        className="w-full text-5xl font-bold text-gray-900 recipe-title bg-transparent border-b-2 border-amber-300 focus:outline-none focus:border-amber-500 rounded-sm px-1"
                        style={{ fontFamily: "'Playfair Display', serif" }}
                    placeholder="Title"
                    aria-label="Recipe title"
                        onMouseDown={(e) => {
                          // Prevent blur when starting text selection
                          e.currentTarget.setAttribute('data-selecting', 'true');
                        }}
                        onMouseUp={(e) => {
                          // Allow blur after text selection is complete
                          setTimeout(() => {
                            e.currentTarget.removeAttribute('data-selecting');
                          }, 100);
                        }}
                        onBlur={(e) => {
                          // Only blur if not during text selection
                          if (!e.currentTarget.hasAttribute('data-selecting')) {
                            setActiveEditField(null);
                          }
                        }}
                        autoFocus
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
                </h1>
                
                {/* Variant badges inline with title */}
              {content?.conversion?.isVariant && (
                  <div className="flex items-center gap-2 mb-4">
                    <span className="text-[11px] px-2 py-1 rounded-md bg-orange-100 text-orange-700 border border-orange-300 uppercase font-medium" style={{fontFamily: 'Poppins, sans-serif'}}>Variant</span>
                <button
                      className={`text-[11px] px-2 py-1 rounded-md border ${content?.conversion?.visibility === 'public' ? 'bg-green-100 text-green-700 border-green-300 uppercase font-medium' : 'bg-gray-100 text-gray-700 border-gray-300 uppercase font-medium'}`}
                      style={{fontFamily: 'Poppins, sans-serif'}}
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
              </div>
            )}
                
                {/* Based on link */}
          {content?.conversion?.isVariant && (
                  <div className="text-sm text-gray-600 mb-4">
                    Based on: <a className="hover:underline" style={{ color: 'rgb(204 124 46 / var(--tw-text-opacity, 1))' }} href={`/recipes/${content?.conversion?.parentRecipeId}`}
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

              {/* Rating - Desktop: top right, Mobile: below title */}
              {!isEditing && (
                <div className="flex items-center gap-2 flex-shrink-0 mt-[5px] hidden md:flex">
                  <div className="flex items-center gap-1" role="radiogroup" aria-label="Rate 1 to 5">
                    {[1,2,3,4,5].map(v => (
                      <button key={v} className={`w-4 h-4 sm:w-5 sm:h-5 ${v <= (rating.userValue || Math.round(rating.average)) ? 'text-yellow-400' : 'text-gray-300'}`} onClick={()=>putRating(v)}>
                        <svg viewBox="0 0 20 20" fill="currentColor"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/></svg>
                      </button>
                    ))}
                  </div>
                  {Number(rating.count || 0) > 0 && (
                    <div className="flex items-center gap-1 text-gray-700">
                      <span className="font-medium text-sm">{Number(rating.average || 0).toFixed(1)}</span>
                      <span className="text-xs text-gray-500 hidden sm:inline">({rating.count})</span>
                    </div>
                  )}
                </div>
              )}
            </div>
            
            {/* Rating - Mobile: below title */}
            {!isEditing && (
              <div className="flex items-center gap-2 mb-4 md:hidden">
                <div className="flex items-center gap-1" role="radiogroup" aria-label="Rate 1 to 5">
                  {[1,2,3,4,5].map(v => (
                    <button key={v} className={`w-4 h-4 sm:w-5 sm:h-5 ${v <= (rating.userValue || Math.round(rating.average)) ? 'text-yellow-400' : 'text-gray-300'}`} onClick={()=>putRating(v)}>
                      <svg viewBox="0 0 20 20" fill="currentColor"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/></svg>
                    </button>
                  ))}
                </div>
                {Number(rating.count || 0) > 0 && (
                  <div className="flex items-center gap-1 text-gray-700">
                    <span className="font-medium text-sm">{Number(rating.average || 0).toFixed(1)}</span>
                    <span className="text-xs text-gray-500 hidden sm:inline">({rating.count})</span>
                  </div>
                )}
              </div>
            )}
          </div>
          
          {/* Tags Row */}
          <div className="mb-6 -mt-2">
            <div className="flex flex-wrap gap-2">
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
                
                // Show max 5 tags, collapse rest into +N
                const visibleTags = out.slice(0, 5);
                const hiddenCount = out.length - 5;
                
                return (
                  <>
                    {visibleTags.map((t, idx) => (
                      <span key={`tag-${idx}-${t.keyword}`} className={`inline-flex items-center px-2 py-1 rounded-full text-xs border ${chipCls(t.type, t.keyword)}`}>
                        {t.keyword.toLowerCase() === 'vegan' && <i className="fa-solid fa-leaf mr-1"></i>}
                        {t.keyword.toLowerCase() === 'vegetarian' && <i className="fa-solid fa-carrot mr-1"></i>}
                        {t.keyword.toLowerCase() === 'zesty' && <i className="fa-solid fa-lemon mr-1"></i>}
                        {t.keyword.toLowerCase() === 'pescatarian' && <i className="fa-solid fa-fish mr-1"></i>}
                        {t.keyword.toLowerCase() === 'seafood' && <i className="fa-solid fa-shrimp mr-1"></i>}
                        {t.keyword.toLowerCase() === 'fastfood' && <i className="fa-solid fa-burger mr-1"></i>}
                        {t.keyword.toLowerCase() === 'spicy' && <i className="fa-solid fa-pepper-hot mr-1"></i>}
                        {t.keyword.toLowerCase() === 'chicken' && <i className="fa-solid fa-drumstick-bite mr-1"></i>}
                        {t.keyword.toLowerCase() === 'eggs' && <i className="fa-solid fa-egg mr-1"></i>}
                        {t.keyword.toLowerCase() === 'cheese' && <i className="fa-solid fa-cheese mr-1"></i>}
                        {t.keyword.toLowerCase() === 'fruits' && <i className="fa-solid fa-apple-whole mr-1"></i>}
                        {t.keyword.toLowerCase() === 'wine' && <i className="fa-solid fa-wine-bottle mr-1"></i>}
                        {t.keyword.toLowerCase() === 'pasta' && <i className="fa-solid fa-bacon mr-1"></i>}
                        <span className="font-medium">{t.keyword.charAt(0).toUpperCase() + t.keyword.slice(1)}</span>
                      </span>
                    ))}
                    {hiddenCount > 0 && (
                      <span className="inline-flex items-center px-2 py-1 rounded-full text-xs border bg-gray-100 text-gray-700 border-gray-300">
                        <span className="font-medium">+{hiddenCount}</span>
                      </span>
                    )}
                  </>
                );
              })()}
            </div>
          </div>
          
          {/* Image + Content Two-Column Layout */}
          <div className="flex flex-col md:flex-row gap-6 mb-6">
            {/* Mobile Layout: Image → Description → Meta Pills → Actions */}
            <div className="md:hidden space-y-6">
              {/* Image */}
            {(image || edited?.image_url) && (
              <div className={`${isEditing && activeEditField === 'image' ? 'ring-2 ring-amber-300 rounded-lg p-1 relative' : ''}`}>
                  <div className="relative w-full aspect-square overflow-hidden rounded-lg">
                  <img
                    src={(isEditing && (gallery[galleryIndex])) ? gallery[galleryIndex] : ((edited?.image_url || image).startsWith('http') ? (edited?.image_url || image) : STATIC_BASE + (edited?.image_url || image))}
                    alt={edited?.title || title}
                      className="w-full h-full object-cover rounded-lg shadow-md hover:scale-105 transition-transform duration-300 ease-in-out"
                      loading="eager"
                    decoding="async"
                    onClick={isEditing ? () => activateFieldEdit('image') : undefined}
                    data-edit-field="image"
                  />
                </div>
                {isEditing && activeEditField === 'image' && gallery.length > 1 && (
                  <>
                    <button onClick={()=>setGalleryIndex(i => (i-1+gallery.length)%gallery.length)} className="absolute left-2 top-1/2 -translate-y-1/2 bg-white/80 hover:bg-white text-gray-800 w-8 h-8 rounded-full shadow flex items-center justify-center" aria-label="Prev" data-edit-field="image">‹</button>
                    <button onClick={()=>setGalleryIndex(i => (i+1)%gallery.length)} className="absolute right-2 top-1/2 -translate-y-1/2 bg-white/80 hover:bg-white text-gray-800 w-8 h-8 rounded-full shadow flex items-center justify-center" aria-label="Next" data-edit-field="image">›</button>
                  </>
                )}
                {isEditing && activeEditField === 'image' && (
                  <div className="mt-3 flex items-center gap-2" data-edit-field="image">
                      <button className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#da8146] text-white hover:brightness-110 transition-all duration-200 text-sm disabled:opacity-60" onClick={generateAiImage} disabled={aiBusy}>
                        <i className="fa-solid fa-wand-magic-sparkles"></i>
                        <span>{aiBusy ? 'Generating…' : 'Generate'}</span>
                      </button>
                    <input id="rv-upload" type="file" accept="image/*" className="hidden" onChange={async (e)=>{
                      const f = e.target.files && e.target.files[0];
                      if(!f) return;
                      try {
                          const formData = new FormData();
                          formData.append('image', f);
                          const res = await fetch(`${API_BASE}/recipes/${recipeId}/image`, { method: 'POST', credentials: 'include', body: formData });
                          if (!res.ok) throw new Error('Upload failed');
                          const j = await res.json();
                          setEdited(v => ({ ...(v || {}), image_url: j.image_url }));
                        } catch (e) {
                          alert('Failed to upload image: ' + e.message);
                        }
                      }} />
                      <button className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-500 text-white hover:bg-gray-600 transition-all duration-200 text-sm" onClick={()=>document.getElementById('rv-upload')?.click()}>
                        <i className="fa-solid fa-upload"></i>
                        <span>Upload</span>
                      </button>
                    </div>
                  )}
                </div>
              )}
              
              {/* Description */}
              <div className={`${isEditing && activeEditField === 'description' ? 'ring-2 ring-amber-300 rounded-lg p-1 relative' : ''}`}>
                {isEditing && activeEditField === 'description' ? (
                  <div data-edit-field="description">
                    <textarea
                      value={edited?.description || ''}
                      onChange={(e)=>setEdited(v=>({...(v||{}), description: e.target.value}))}
                      className="w-full min-h-[120px] text-base leading-relaxed border-0 focus:outline-none rounded-lg p-3 resize-y"
                      placeholder="Describe your recipe..."
                      aria-label="Recipe description"
                      onBlur={() => setActiveEditField(null)}
                    />
                  </div>
                ) : (
                  <p 
                    className={`text-base leading-relaxed text-gray-700 ${isEditing ? "cursor-pointer hover:bg-yellow-50 rounded px-1 transition-colors" : ""}`}
                    onClick={isEditing ? () => activateFieldEdit('description') : undefined}
                    data-edit-field="description"
                  >
                    {edited?.description || description || 'No description available.'}
                  </p>
                )}
              </div>
              
              {/* Meta Pills */}
              <div className="flex items-center gap-3 md:gap-4 flex-wrap gap-y-2">
                {/* Servings */}
                {(content.servings || content.serves) && (
                  <div className="inline-flex items-center gap-1 px-4 py-2 bg-white rounded-full shadow-[2px_2px_0_rgb(204_124_46_/_10%)]">
                    <i className="fa-solid fa-utensils text-[#cc7c2e]"></i>
                    <select 
                      value={currentServings}
                      onChange={(e) => setCurrentServingsAndSave(parseInt(e.target.value, 10))}
                      className="text-gray-700 bg-transparent border-none outline-none cursor-pointer pr-0 w-auto"
                    >
                      {Array.from({ length: 12 }, (_, i) => i + 1).map(num => (
                        <option key={num} value={num}>{num}</option>
                      ))}
                    </select>
                    <span className="text-gray-700">servings</span>
                  </div>
                )}
                
                {/* Total Time */}
                {(prepTime || cookTime) && (
                  <div className="relative" ref={timePopoverRef}>
                    <button
                      className="inline-flex items-center gap-2 px-4 py-2 bg-white rounded-full shadow-[2px_2px_0_rgb(204_124_46_/_10%)] hover:shadow-[3px_3px_0_rgb(204_124_46_/_10%)] hover:-translate-y-0.5 transition-transform transition-shadow duration-200 ease-out"
                      onClick={handleTimeClick}
                      onMouseEnter={handleTimeMouseEnter}
                      onMouseLeave={handleTimeMouseLeave}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          handleTimeClick();
                        }
                      }}
                      aria-label={`Total time ${totalTime} minutes`}
                    >
                      <i className="fa-solid fa-clock text-[#cc7c2e]"></i>
                      <span className="text-gray-700">{totalTime} min</span>
                    </button>
                    
                    {/* Desktop tooltip */}
                    {showTimePopover && window.innerWidth >= 768 && (
                      <div 
                        className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-2 bg-gray-900 text-white text-sm rounded-lg shadow-lg z-50 whitespace-nowrap"
                        role="tooltip"
                      >
                        {prepTime && cookTime ? (
                          `Prep: ${prepTime} min • Cook: ${cookTime} min`
                        ) : prepTime ? (
                          `Prep: ${prepTime} min`
                        ) : (
                          `Cook: ${cookTime} min`
                        )}
                        <div className="absolute top-full left-1/2 transform -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-gray-900"></div>
                      </div>
                    )}
                    
                    {/* Mobile popover */}
                    {showTimePopover && window.innerWidth < 768 && (
                      <div 
                        className="absolute top-full left-0 mt-2 px-3 py-2 bg-gray-900 text-white text-sm rounded-lg shadow-lg z-50 whitespace-nowrap"
                        role="tooltip"
                      >
                        {prepTime && cookTime ? (
                          `Prep: ${prepTime} min • Cook: ${cookTime} min`
                        ) : prepTime ? (
                          `Prep: ${prepTime} min`
                        ) : (
                          `Cook: ${cookTime} min`
                        )}
                      </div>
                    )}
                  </div>
                )}
                
                {/* Difficulty */}
                <div className="inline-flex items-center gap-2 px-4 py-2 bg-white rounded-full shadow-[2px_2px_0_rgb(204_124_46_/_10%)]">
                  <i className="fa-regular fa-face-smile" style={{color: 'rgb(204 124 46 / var(--tw-text-opacity, 1))'}}></i>
                  <span className="text-gray-700">{difficulty}</span>
                </div>
              </div>
              
              {/* Action Buttons */}
              <div className="flex items-center gap-2 flex-wrap">
                <button onClick={() => onDownload?.(content)} disabled={isEditing} className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#7ab87a] text-white hover:bg-[#659a63] transition-all duration-200 text-sm ${isEditing ? 'opacity-50 cursor-not-allowed' : ''}`}>
                  <i className="fa-solid fa-download"></i>
                  <span>Download</span>
                </button>
                {isSaved && (
                  <>
                    <button onClick={()=>setConvertOpen(true)} disabled={isEditing} className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#e87b35] text-white transition-all duration-200 text-sm ${isEditing ? 'opacity-50 cursor-not-allowed' : 'hover:brightness-110'}`}>
                      <i className="fa-solid fa-rotate"></i>
                      <span>Convert</span>
                    </button>
                  </>
                )}
                <button onClick={async ()=>{
                  try {
                    const url = window.location.href;
                    const shareData = { title: (edited?.title || title) || 'Recipe', url };
                    if (navigator.share) {
                      await navigator.share(shareData);
                        } else {
                      await navigator.clipboard.writeText(url);
                      const t = document.createElement('div');
                      t.className = 'fixed bottom-4 right-4 bg-gray-900 text-white text-sm px-3 py-2 rounded-lg shadow z-[9999]';
                      t.textContent = 'Link copied to clipboard';
                      document.body.appendChild(t);
                      setTimeout(()=>{ t.remove(); }, 2500);
                    }
                  } catch {}
                }} disabled={isEditing} className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[rgb(158,137,112)] text-white transition-all duration-200 text-sm ${isEditing ? 'opacity-50 cursor-not-allowed' : 'hover:brightness-110'}`}>
                  <i className="fa-solid fa-share-nodes"></i>
                  <span>Share</span>
                </button>
              </div>
            </div>
            
            {/* Desktop Layout: Two-column */}
            <div className="hidden md:flex md:flex-row gap-6 w-full">
            {/* Left column: Image ONLY */}
            <div className="md:w-1/3">
              {(image || edited?.image_url) && (
                <div className={`${isEditing && activeEditField === 'image' ? 'ring-2 ring-amber-300 rounded-lg p-1 relative' : ''}`}>
                  <div className="relative w-full aspect-square overflow-hidden rounded-lg">
                    <img
                      src={(isEditing && (gallery[galleryIndex])) ? gallery[galleryIndex] : ((edited?.image_url || image).startsWith('http') ? (edited?.image_url || image) : STATIC_BASE + (edited?.image_url || image))}
                      alt={edited?.title || title}
                      className="w-full h-full object-cover rounded-lg shadow-md hover:scale-105 transition-transform duration-300 ease-in-out"
                      loading="eager"
                      decoding="async"
                      onClick={isEditing ? () => activateFieldEdit('image') : undefined}
                      data-edit-field="image"
                    />
                  </div>
                  {isEditing && activeEditField === 'image' && gallery.length > 1 && (
                    <>
                      <button onClick={()=>setGalleryIndex(i => (i-1+gallery.length)%gallery.length)} className="absolute left-2 top-1/2 -translate-y-1/2 bg-white/80 hover:bg-white text-gray-800 w-8 h-8 rounded-full shadow flex items-center justify-center" aria-label="Prev" data-edit-field="image">‹</button>
                      <button onClick={()=>setGalleryIndex(i => (i+1)%gallery.length)} className="absolute right-2 top-1/2 -translate-y-1/2 bg-white/80 hover:bg-white text-gray-800 w-8 h-8 rounded-full shadow flex items-center justify-center" aria-label="Next" data-edit-field="image">›</button>
                    </>
                  )}
                  {isEditing && activeEditField === 'image' && (
                    <div className="mt-3 flex items-center gap-2" data-edit-field="image">
                      <button className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#da8146] text-white hover:brightness-110 transition-all duration-200 text-sm disabled:opacity-60" onClick={generateAiImage} disabled={aiBusy}>
                        <i className="fa-solid fa-wand-magic-sparkles"></i>
                        <span>{aiBusy ? 'Generating…' : 'Generate'}</span>
                      </button>
                      <input id="rv-upload" type="file" accept="image/*" className="hidden" onChange={async (e)=>{
                        const f = e.target.files && e.target.files[0];
                        if(!f) return;
                        try {
                          const formData = new FormData();
                          formData.append('image', f);
                          const res = await fetch(`${API_BASE}/recipes/${recipeId}/image`, { method: 'POST', credentials: 'include', body: formData });
                          if (!res.ok) throw new Error('Upload failed');
                          const j = await res.json();
                          setEdited(v => ({ ...(v || {}), image_url: j.image_url }));
                        } catch (e) {
                          alert('Failed to upload image: ' + e.message);
                      }
                    }} />
                      <button className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-500 text-white hover:bg-gray-600 transition-all duration-200 text-sm" onClick={()=>document.getElementById('rv-upload')?.click()}>
                        <i className="fa-solid fa-upload"></i>
                        <span>Upload</span>
                      </button>
                  </div>
                )}
              </div>
            )}
          </div>
            
            {/* Right column: Content Stack (Description → Meta Pills → Actions) */}
            <div className="md:w-2/3">
              <div className="space-y-6">
                {/* Description */}
                <div className={`${isEditing && activeEditField === 'description' ? 'ring-2 ring-amber-300 rounded-lg p-1 relative' : ''}`}>
              {isEditing && activeEditField === 'description' ? (
                <div data-edit-field="description">
                  <textarea
                        value={edited?.description || ''}
                        onChange={(e)=>setEdited(v=>({...(v||{}), description: e.target.value}))}
                        className="w-full min-h-[120px] text-base leading-relaxed border-0 focus:outline-none rounded-lg p-3 resize-y"
                        placeholder="Describe your recipe..."
                        aria-label="Recipe description"
                    onBlur={() => setActiveEditField(null)}
                  />
                </div>
              ) : (
                <p 
                      className={`text-base leading-relaxed text-gray-700 ${isEditing ? "cursor-pointer hover:bg-yellow-50 rounded px-1 transition-colors" : ""}`}
                  onClick={isEditing ? () => activateFieldEdit('description') : undefined}
                  data-edit-field="description"
                >
                      {edited?.description || description || 'No description available.'}
                </p>
              )}
          </div>
                
                {/* Meta Pills */}
                <div className="flex items-center gap-3 md:gap-4 flex-wrap gap-y-2">
                                    {/* Servings */}
                  {(content.servings || content.serves) && (
                    <div className="inline-flex items-center gap-1 px-4 py-2 bg-white rounded-full shadow-[2px_2px_0_rgb(204_124_46_/_10%)]">
                      <i className="fa-solid fa-utensils text-[#cc7c2e]"></i>
                      <select 
                        value={currentServings}
                        onChange={(e) => setCurrentServingsAndSave(parseInt(e.target.value, 10))}
                        className="text-gray-700 bg-transparent border-none outline-none cursor-pointer pr-0 w-auto"
                      >
                        {Array.from({ length: 12 }, (_, i) => i + 1).map(num => (
                          <option key={num} value={num}>{num}</option>
                        ))}
                      </select>
                      <span className="text-gray-700">servings</span>
                    </div>
                  )}
                  
                  {/* Total Time */}
                  {(prepTime || cookTime) && (
                    <div className="relative" ref={timePopoverRef}>
                                          <button
                      className="inline-flex items-center gap-2 px-4 py-2 bg-white rounded-full shadow-[2px_2px_0_rgb(204_124_46_/_10%)] hover:shadow-[3px_3px_0_rgb(204_124_46_/_10%)] hover:-translate-y-0.5 transition-transform transition-shadow duration-200 ease-out"
                        onClick={handleTimeClick}
                        onMouseEnter={handleTimeMouseEnter}
                        onMouseLeave={handleTimeMouseLeave}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            handleTimeClick();
                          }
                        }}
                        aria-label={`Total time ${totalTime} minutes`}
                      >
                        <i className="fa-solid fa-clock text-[#cc7c2e]"></i>
                        <span className="text-gray-700">{totalTime} min</span>
                      </button>
                      
                      {/* Desktop tooltip */}
                      {showTimePopover && window.innerWidth >= 768 && (
                        <div 
                          className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-2 bg-gray-900 text-white text-sm rounded-lg shadow-lg z-50 whitespace-nowrap"
                          role="tooltip"
                        >
                          {prepTime && cookTime ? (
                            `Prep: ${prepTime} min • Cook: ${cookTime} min`
                          ) : prepTime ? (
                            `Prep: ${prepTime} min`
                          ) : (
                            `Cook: ${cookTime} min`
                          )}
                          <div className="absolute top-full left-1/2 transform -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-gray-900"></div>
            </div>
                      )}
                      
                      {/* Mobile popover */}
                      {showTimePopover && window.innerWidth < 768 && (
                        <div 
                          className="absolute top-full left-0 mt-2 px-3 py-2 bg-gray-900 text-white text-sm rounded-lg shadow-lg z-50 whitespace-nowrap"
                          role="tooltip"
                        >
                          {prepTime && cookTime ? (
                            `Prep: ${prepTime} min • Cook: ${cookTime} min`
                          ) : prepTime ? (
                            `Prep: ${prepTime} min`
                          ) : (
                            `Cook: ${cookTime} min`
                          )}
            </div>
                      )}
            </div>
                  )}
                  
                  {/* Difficulty */}
                  <div className="inline-flex items-center gap-2 px-4 py-2 bg-white rounded-full shadow-[2px_2px_0_rgb(204_124_46_/_10%)]">
                    <i className="fa-regular fa-face-smile" style={{color: 'rgb(204 124 46 / var(--tw-text-opacity, 1))'}}></i>
                    <span className="text-gray-700">{difficulty}</span>
                  </div>
                </div>
                
                                {/* Action Buttons */}
                <div className="flex items-center gap-2 flex-wrap">
                  <button onClick={() => onDownload?.(content)} disabled={isEditing} className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#7ab87a] text-white hover:bg-[#659a63] transition-all duration-200 text-sm ${isEditing ? 'opacity-50 cursor-not-allowed' : ''}`}>
                    <i className="fa-solid fa-download"></i>
                    <span>Download</span>
                  </button>
                  {isSaved && (
                    <>
                      <button onClick={()=>setConvertOpen(true)} disabled={isEditing} className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#e87b35] text-white transition-all duration-200 text-sm ${isEditing ? 'opacity-50 cursor-not-allowed' : 'hover:brightness-110'}`}>
                        <i className="fa-solid fa-rotate"></i>
                        <span>Convert</span>
                      </button>
                    </>
                  )}
                  <button onClick={async ()=>{
                    try {
                      const url = window.location.href;
                      const shareData = { title: (edited?.title || title) || 'Recipe', url };
                      if (navigator.share) {
                        await navigator.share(shareData);
                      } else {
                        await navigator.clipboard.writeText(url);
                        const t = document.createElement('div');
                        t.className = 'fixed bottom-4 right-4 bg-gray-900 text-white text-sm px-3 py-2 rounded-lg shadow z-[9999]';
                        t.textContent = 'Link copied to clipboard';
                        document.body.appendChild(t);
                        setTimeout(()=>{ t.remove(); }, 2500);
                      }
                    } catch {}
                  }} disabled={isEditing} className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[rgb(158,137,112)] text-white transition-all duration-200 text-sm ${isEditing ? 'opacity-50 cursor-not-allowed' : 'hover:brightness-110'}`}>
                    <i className="fa-solid fa-share-nodes"></i>
                    <span>Share</span>
                  </button>
                </div>
              </div>
            </div>
            </div>
          </div>
        </div>

        {/* Toolbar - Full width wrapper matching My Recipes style */}
        <div className="w-full bg-white rounded-2xl border border-gray-200 shadow-[3px_3px_0_rgb(204_124_46_/_10%)] -mt-1 mb-6" style={{pointerEvents: 'none'}}>
                      <div className="flex items-center justify-between gap-4 px-5 py-3" style={{pointerEvents: 'auto'}}>
            {/* Left side: Two segment groups */}
            <div className="flex items-center gap-4">
              {/* Segment Group 1 - Layout */}
              <div className="flex items-center rounded-full bg-gray-100 p-1">
                <button
                  onClick={() => setLayoutModeAndSave('two')}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      setLayoutModeAndSave('two');
                    }
                  }}
                  className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg transition-all duration-200 ease-in-out ${
                    layoutMode === 'two'
                      ? 'bg-[#7ab87a] text-white font-semibold border border-[#7ab87a] hover:bg-[#659a63]'
                      : 'bg-white text-[#444] border border-[#ddd] hover:bg-[#f9f9f9]'
                  }`}
                  title="Switch to two-column layout"
                  aria-label="Switch to two-column layout"
                  aria-pressed={layoutMode === 'two'}
                >
                  <i className="fa-solid fa-table-columns text-sm"></i>
                  <span className="text-sm font-medium hidden sm:inline">Two Columns</span>
                </button>
                <button
                  onClick={() => setLayoutModeAndSave('single')}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      setLayoutModeAndSave('single');
                    }
                  }}
                  className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg transition-all duration-200 ease-in-out ${
                    layoutMode === 'single'
                      ? 'bg-[#7ab87a] text-white font-semibold border border-[#7ab87a] hover:bg-[#659a63]'
                      : 'bg-white text-[#444] border border-[#ddd] hover:bg-[#f9f9f9]'
                  }`}
                  title="Switch to single-column layout"
                  aria-label="Switch to single-column layout"
                  aria-pressed={layoutMode === 'single'}
                >
                  <i className="fa-solid fa-align-justify text-sm"></i>
                  <span className="text-sm font-medium hidden sm:inline">Single Column</span>
                </button>
              </div>
              
              {/* Segment Group 2 - Focus + TTS */}
              <div className="flex items-center gap-2">
                <button 
                  onClick={() => setHoverHighlightAndSave(!hoverHighlight)} 
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      setHoverHighlightAndSave(!hoverHighlight);
                    }
                  }}
                  disabled={isEditing}
                  aria-pressed={hoverHighlight}
                  className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg transition-all duration-200 ease-in-out ${
                    isEditing 
                      ? 'bg-gray-100 text-gray-400 border border-gray-200 cursor-not-allowed opacity-50'
                      : hoverHighlight
                        ? 'bg-[#7ab87a] text-white font-semibold border border-[#7ab87a] shadow-[0_2px_4px_rgba(0,0,0,0.15)] hover:bg-[#659a63] hover:shadow-[0_3px_6px_rgba(0,0,0,0.2)]'
                        : 'bg-white text-[#444] border border-[#ddd] shadow-[0_1px_2px_rgba(0,0,0,0.05)] hover:bg-[#f9f9f9] hover:shadow-[0_2px_4px_rgba(0,0,0,0.1)]'
                  }`}
                  title={isEditing ? "Focus mode disabled during editing" : (hoverHighlight ? "Disable focus mode" : "Enable focus mode")}
                  aria-label={isEditing ? "Focus mode disabled during editing" : (hoverHighlight ? "Disable focus mode" : "Enable focus mode")}
                >
                  {hoverHighlight ? (
                    <i className="fa-regular fa-eye text-sm"></i>
                  ) : (
                    <i className="fa-regular fa-eye-slash text-sm"></i>
                  )}
                  <span className="text-sm font-medium hidden sm:inline">Focus</span>
                </button>
                
                <button 
                  onClick={() => setTtsActiveAndSave(!ttsActive)} 
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      setTtsActiveAndSave(!ttsActive);
                    }
                  }}
                  disabled={isEditing}
                  aria-pressed={ttsActive}
                  className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg transition-all duration-200 ease-in-out ${
                    isEditing 
                      ? 'bg-gray-100 text-gray-400 border border-gray-200 cursor-not-allowed opacity-50'
                      : ttsActive
                        ? 'bg-[#7ab87a] text-white font-semibold border border-[#7ab87a] shadow-[0_2px_4px_rgba(0,0,0,0.15)] hover:bg-[#659a63] hover:shadow-[0_3px_6px_rgba(0,0,0,0.2)]'
                        : 'bg-white text-[#444] border border-[#ddd] shadow-[0_1px_2px_rgba(0,0,0,0.05)] hover:bg-[#f9f9f9] hover:shadow-[0_2px_4px_rgba(0,0,0,0.1)]'
                  }`}
                  title={isEditing ? "Read Aloud disabled during editing" : (ttsActive ? "Mute TTS" : "Read steps aloud")}
                  aria-label={isEditing ? "Read Aloud disabled during editing" : (ttsActive ? "Mute TTS" : "Read steps aloud")}
                >
                  {ttsActive ? (
                    <i className="fa-solid fa-volume-high text-sm"></i>
                  ) : (
                    <i className="fa-solid fa-volume-xmark text-sm"></i>
                  )}
                  <span className="text-sm font-medium hidden sm:inline">Read Aloud</span>
                </button>
                
                <button 
                  onClick={() => setCartModeAndSave(!cartMode)} 
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      setCartModeAndSave(!cartMode);
                    }
                  }}
                  disabled={isEditing}
                  aria-pressed={cartMode}
                  className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg transition-all duration-200 ease-in-out ${
                    isEditing 
                      ? 'bg-gray-100 text-gray-400 border border-gray-200 cursor-not-allowed opacity-50'
                      : cartMode
                        ? 'bg-[#7ab87a] text-white font-semibold border border-[#7ab87a] shadow-[0_2px_4px_rgba(0,0,0,0.15)] hover:bg-[#659a63] hover:shadow-[0_3px_6px_rgba(0,0,0,0.2)]'
                        : 'bg-white text-[#444] border border-[#ddd] shadow-[0_1px_2px_rgba(0,0,0,0.05)] hover:bg-[#f9f9f9] hover:shadow-[0_2px_4px_rgba(0,0,0,0.1)]'
                  }`}
                  title={isEditing ? "Shop List mode disabled during editing" : (cartMode ? "Disable shop list mode" : "Enable shop list mode")}
                  aria-label={isEditing ? "Shop List mode disabled during editing" : (cartMode ? "Disable shop list mode" : "Enable shop list mode")}
                >
                  <i className="fa-solid fa-cart-shopping text-sm"></i>
                  <span className="text-sm font-medium hidden sm:inline">Shop List</span>
                </button>
              </div>
            </div>
            
            {/* Right side: Empty for visual balance */}
            <div></div>
          </div>
        </div>

        {/* Ingredients & Instructions as separate white cards; no outer visual title */}
        <RecipeSection id="ingredients-section" title="Ingredients & Instructions" titleHidden variant="plain" className="px-0">
          <div className={`gap-6 ${layoutMode === 'two' ? 'grid md:grid-cols-[2fr,3fr]' : 'flex flex-col'}`}>
            {/* Ingredients Card */}
                          <div 
                className={`bg-white rounded-2xl p-6 shadow-[4px_4px_0_rgb(204_124_46_/_10%)] hover:shadow-[6px_6px_0_rgb(204_124_46_/_10%)] hover:-translate-y-0.5 transition-transform transition-shadow duration-200 ease-out ${isEditing ? 'cursor-pointer' : ''}`}
                onClick={isEditing && activeEditField !== 'ingredients' ? () => activateFieldEdit('ingredients') : undefined}
                data-edit-field="ingredients"
              >
              <div className="flex items-center justify-between mb-3">
                <h3 id="ingredients" className="text-lg font-semibold flex items-center gap-2 scroll-mt-[88px]">
                  <i className="fa-solid fa-carrot mr-2"></i>
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
                <>
                <ul className="space-y-2">
                  {ingredientsToRender.map((ing, idx) => {
                    const text = typeof ing === 'string' ? ing : `${ing.quantity || ''} ${ing.name || ''} ${ing.notes ? `(${ing.notes})` : ''}`.trim();
                    const m = /^(\S+\s+\S+)(.*)$/i.exec(text);
                    const shouldDim = false;
                    const isSelected = selectedIngredients.has(idx);
                    return (
                      <li 
                        key={idx} 
                        className={`flex items-start p-1 rounded ${isEditing ? 'hover:bg-yellow-50 cursor-pointer' : ''} focus:outline-none focus:ring-0 focus:border-0 ${isSelected ? 'line-through opacity-70' : ''}`}
                        onClick={isEditing ? () => activateFieldEdit('ingredients') : undefined}
                        onFocus={undefined}
                        onBlur={undefined}
                        tabIndex={-1}
                        data-edit-field="ingredients"
                      >
                        {cartMode ? (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              toggleIngredientSelection(idx);
                            }}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' || e.key === ' ') {
                                e.preventDefault();
                                e.stopPropagation();
                                toggleIngredientSelection(idx);
                              }
                            }}
                            className={`w-5 h-5 mr-3 flex-shrink-0 border-2 rounded ${isSelected ? 'bg-green-600 border-green-600' : 'border-gray-300'} focus:outline-none focus:ring-2 focus:ring-green-500`}
                            aria-label={isSelected ? `Deselect ${text}` : `Select ${text}`}
                          >
                            {isSelected && (
                              <svg className="w-full h-full text-white" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                              </svg>
                            )}
                          </button>
                        ) : (
                        <span className="text-green-600 mr-3 flex-shrink-0 flex items-center text-lg">•</span>
                        )}
                        <span className="text-gray-700">{m ? (<><strong className="font-semibold text-gray-900">{m[1]}</strong>{m[2]}</>) : text}</span>
                      </li>
                    );
                  })}
                </ul>
                {cartMode && (
                  <div className="mt-4 pt-4 border-t border-gray-200">
                    <button
                      onClick={addToShoppingList}
                      className="w-full bg-green-600 text-white font-semibold py-4 px-6 rounded-lg hover:bg-green-700 transition-colors flex items-center justify-center gap-3 text-lg"
                      aria-label="Add selected ingredients to shop list"
                    >
                      <i className="fa-solid fa-list-check text-xl"></i>
                      <span>Add to Shop List</span>
                    </button>
                  </div>
                )}
                </>
              )}
            </div>

            {/* Instructions Card */}
            <div 
              className={`bg-white rounded-2xl p-6 shadow-[4px_4px_0_rgb(204_124_46_/_10%)] hover:shadow-[6px_6px_0_rgb(204_124_46_/_10%)] hover:-translate-y-0.5 transition-transform transition-shadow duration-200 ease-out ${isEditing ? 'cursor-pointer' : ''}`}
              onClick={isEditing && activeEditField !== 'instructions' ? () => activateFieldEdit('instructions') : undefined}
              data-edit-field="instructions"
            >
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-lg font-semibold flex items-center gap-2 scroll-mt-[88px]">
                  <i className="fa-solid fa-list-ol mr-2"></i>
                  Instructions
                </h3>
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
                          } else if (hoverHighlight) {
                            // Only allow focus when Focus mode is active
                            setKeyboardFocusedItem({ type: 'instructions', index: idx });
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
                <button onClick={onCancelDelete} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-500 text-white hover:bg-gray-600 transition-all duration-200 text-sm">
                  <i className="fa-solid fa-xmark"></i>
                  <span>Avbryt</span>
                </button>
                <button onClick={onConfirmDelete} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-red-600 text-white hover:bg-red-700 transition-all duration-200 text-sm">
                  <i className="fa-solid fa-trash"></i>
                  <span>Ta bort</span>
                </button>
              </div>
            </div>
          </div>
        )}

      {variant !== 'modal' && (
              <RecipeSection id="nutrition" title={
                <span>
                  <i className="fa-solid fa-fire mr-2"></i>
                  Nutrition Information
                </span>
              } className="bg-white">
        {/* Safe Mode notice */}
        {nutritionData?.meta?.safe_mode && (
          <div className="text-sm text-gray-500 mb-2">
            Safe Mode: {skippedCount} ingredients skipped or defaulted.
          </div>
        )}
        {/* Nutrition Chips */}
        <div className="flex flex-wrap items-center gap-3 mb-4">
          {[
            {k:'calories', l:'Calories', icon:'fa-fire', bgColor:'bg-blue-50', borderColor:'border-blue-200', iconColor:'text-blue-600'},
            {k:'protein',l:'Protein', icon:'fa-egg', bgColor:'bg-green-50', borderColor:'border-green-200', iconColor:'text-green-600'},
            {k:'fat',l:'Fat', icon:'fa-bacon', bgColor:'bg-orange-50', borderColor:'border-orange-200', iconColor:'text-orange-600'},
            {k:'carbs',l:'Carbs', icon:'fa-bread-slice', bgColor:'bg-amber-50', borderColor:'border-amber-200', iconColor:'text-amber-600'}
          ].map(({k,l,icon,bgColor,borderColor,iconColor}) => {
            const perServing = getScaledNutrition.perServing[k];
            const total = getScaledNutrition.total[k];
            const isInteractive = showNutritionDetails;
            const isLoading = nutritionLoading;
            
            return (
              <div 
                key={k}
                role={isInteractive ? "button" : "text"}
                tabIndex={isInteractive ? 0 : -1}
                onClick={isInteractive ? () => handleNutritionChipClick(k) : undefined}
                onKeyDown={isInteractive ? (e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    handleNutritionChipClick(k);
                  }
                } : undefined}
                className={`
                  inline-flex items-center gap-2 px-4 py-2.5 rounded-full border transition-all duration-200
                  ${bgColor} ${borderColor}
                  ${isInteractive 
                    ? 'cursor-pointer hover:-translate-y-0.5 hover:border-opacity-80 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500' 
                    : 'cursor-default'
                  }
                `}
              >
                <i className={`fa-solid ${icon} text-sm ${iconColor}`}></i>
                                                 <div className="flex flex-col">
                  <div className="text-sm font-semibold text-gray-900">
                    {isLoading ? '...' : (perServing || '—')}{k === 'calories' ? ' kcal' : 'g'}
                  </div>
                </div>
                {isInteractive && (
                  <i className="fa-solid fa-chevron-right text-xs text-gray-400 ml-1"></i>
                )}
              </div>
            );
          })}
        </div>

        {/* Show Details Link */}
        <button
          onClick={() => setShowNutritionDetails(!showNutritionDetails)}
          className="text-sm text-blue-600 hover:text-blue-700 hover:underline transition-colors duration-200 mb-4"
          aria-expanded={showNutritionDetails}
          disabled={nutritionLoading}
        >
          {nutritionLoading ? 'Laddar...' : (showNutritionDetails ? 'Dölj detaljer' : 'Visa detaljer')}
        </button>

        {/* Error message */}
        {nutritionError && (
          <div className="flex items-center justify-between text-sm text-red-600 mb-4">
            <span>Nutrition calculation failed. {nutritionError}</span>
            <button
              onClick={async ()=>{
                try {
                  const url = `${API_BASE.replace('/api/v1','')}/api/v1/nutrition/${recipeId}/recompute`;
                  await fetch(url, { method:'POST' });
                  setNutritionError(null);
                  fetchNutritionSnapshot(0);
                } catch (e) {}
              }}
              className="ml-4 px-3 py-1.5 border border-red-300 rounded text-red-700 hover:bg-red-50"
            >
              Recompute
            </button>
          </div>
        )}

        {/* Nutrition Details Table */}
        {showNutritionDetails && (
          <div ref={nutritionTableRef} className="mt-4">
            {/* Desktop Table */}
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-2 px-3 font-medium text-gray-700">Ämne</th>
                    <th className="text-right py-2 px-3 font-medium text-gray-700">Per portion</th>
                    <th className="text-right py-2 px-3 font-medium text-gray-700">Total batch</th>
                    <th className="text-right py-2 px-3 font-medium text-gray-700">%RI</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    {key: 'calories', label: 'Energi', unit: 'kcal', showKj: true},
                    {key: 'protein', label: 'Protein', unit: 'g'},
                    {key: 'fat', label: 'Fett', unit: 'g'},
                    {key: 'saturatedFat', label: 'Varav mättat', unit: 'g'},
                    {key: 'carbs', label: 'Kolhydrater', unit: 'g'},
                    {key: 'sugar', label: 'Varav socker', unit: 'g'},
                    {key: 'fiber', label: 'Fibrer', unit: 'g'},
                    {key: 'sodium', label: 'Salt', unit: 'g', calculated: true},
                    {key: 'cholesterol', label: 'Kolesterol', unit: 'mg'}
                  ].map(({key, label, unit, showKj, calculated}) => {
                    const perServing = asNumberOrNull(getScaledNutrition.perServing[key]);
                    const total = asNumberOrNull(getScaledNutrition.total[key]);
                    const rdi = getNutritionRDI(key, perServing);
                    const isHighlighted = highlightedNutritionRow === key;
                    
                    // Calculate salt from sodium if needed
                    let displayValue = perServing;
                    let totalValue = total;
                    if (calculated && key === 'sodium') {
                      const saltPerServing = asNumberOrNull(getScaledNutrition.perServing['salt']);
                      const saltTotal = asNumberOrNull(getScaledNutrition.total['salt']);
                      if (saltPerServing != null) {
                        // Backend provides salt already in grams
                        displayValue = Math.round(saltPerServing * 10) / 10;
                      } else if (perServing != null) {
                        // Convert sodium (mg) -> salt (g): mg * 2.5 / 1000
                        displayValue = Math.round(((perServing * 2.5) / 1000) * 10) / 10;
                      }
                      if (saltTotal != null) {
                        totalValue = Math.round(saltTotal * 10) / 10;
                      } else if (total != null) {
                        totalValue = Math.round(((total * 2.5) / 1000) * 10) / 10;
                      }
                    }
                    
                    return (
                      <tr 
                        key={key}
                        className={`
                          border-b border-gray-100 transition-colors duration-300
                          ${isHighlighted ? 'bg-blue-50' : 'hover:bg-gray-50'}
                        `}
                      >
                        <td className="py-2 px-3 text-gray-900">{label}</td>
                        <td className="py-2 px-3 text-right text-gray-900">
                          {displayValue != null ? displayValue : '—'}
                          {displayValue != null && unit}
                          {showKj && displayValue != null && (
                            <span className="text-xs text-gray-500 ml-1">
                              ({Math.round(displayValue * 4.184)} kJ)
                            </span>
                          )}
                        </td>
                        <td className="py-2 px-3 text-right text-gray-900">
                          {totalValue != null ? totalValue : '—'}
                          {totalValue != null && unit}
                          {showKj && totalValue != null && (
                            <span className="text-xs text-gray-500 ml-1">
                              ({Math.round(totalValue * 4.184)} kJ)
                            </span>
                          )}
                        </td>
                        <td className="py-2 px-3 text-right text-gray-900">
                          {rdi ? `${rdi}%` : '—'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Mobile Stacked View */}
            <div className="md:hidden space-y-3">
              {[
                {key: 'calories', label: 'Energi', unit: 'kcal', showKj: true},
                {key: 'protein', label: 'Protein', unit: 'g'},
                {key: 'fat', label: 'Fett', unit: 'g'},
                {key: 'saturatedFat', label: 'Varav mättat', unit: 'g'},
                {key: 'carbs', label: 'Kolhydrater', unit: 'g'},
                {key: 'sugar', label: 'Varav socker', unit: 'g'},
                {key: 'fiber', label: 'Fibrer', unit: 'g'},
                {key: 'sodium', label: 'Salt', unit: 'g', calculated: true},
                {key: 'cholesterol', label: 'Kolesterol', unit: 'mg'}
              ].map(({key, label, unit, showKj, calculated}) => {
                const perServing = asNumberOrNull(getScaledNutrition.perServing[key]);
                const total = asNumberOrNull(getScaledNutrition.total[key]);
                const rdi = getNutritionRDI(key, perServing);
                const isHighlighted = highlightedNutritionRow === key;
                
                // Calculate salt from sodium if needed
                let displayValue = perServing;
                let totalValue = total;
                if (calculated && key === 'sodium') {
                  const saltPerServing = asNumberOrNull(getScaledNutrition.perServing['salt']);
                  const saltTotal = asNumberOrNull(getScaledNutrition.total['salt']);
                  if (saltPerServing != null) {
                    displayValue = Math.round(saltPerServing * 10) / 10;
                  } else if (perServing != null) {
                    displayValue = Math.round(((perServing * 2.5) / 1000) * 10) / 10;
                  }
                  if (saltTotal != null) {
                    totalValue = Math.round(saltTotal * 10) / 10;
                  } else if (total != null) {
                    totalValue = Math.round(((total * 2.5) / 1000) * 10) / 10;
                  }
                }
                
                return (
                  <div 
                    key={key}
                    className={`
                      p-3 border border-gray-200 rounded-lg transition-colors duration-300
                      ${isHighlighted ? 'bg-blue-50 border-blue-300' : 'bg-white hover:bg-gray-50'}
                    `}
                  >
                    <div className="font-medium text-gray-900 mb-1">{label}</div>
                    <div className="space-y-1 text-sm">
                      <div className="flex justify-between">
                        <span className="text-gray-600">Per portion:</span>
                        <span className="text-gray-900">
                          {displayValue != null ? displayValue : '—'}
                          {displayValue != null && unit}
                          {showKj && displayValue != null && (
                            <span className="text-xs text-gray-500 ml-1">
                              ({Math.round(displayValue * 4.184)} kJ)
                            </span>
                          )}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Total batch:</span>
                        <span className="text-gray-900">
                          {totalValue != null ? totalValue : '—'}
                          {totalValue != null && unit}
                          {showKj && totalValue != null && (
                            <span className="text-xs text-gray-500 ml-1">
                              ({Math.round(totalValue * 4.184)} kJ)
                            </span>
                          )}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">%RI:</span>
                        <span className="text-gray-900">
                          {rdi ? `${rdi}%` : '—'}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            <p className="text-xs text-gray-500 mt-3">
              *%RI avser vuxen referensintag. Salt beräknat från natrium ×2,5.
            </p>
          </div>
        )}
      </RecipeSection>
      )}

      {/* Removed divider between Nutrition and social sections to keep seamless flow */}

      {/* Social section for saved recipes (omit in quick view via isSaved=false) */}
      {isSaved && (
        <div className="mt-8 mb-24">

          {/* Source section */}
          {variant !== 'modal' && sourceUrl && (
            <RecipeSection id="source" title="Source" className="mt-4 bg-white">
              <div className="bg-gray-50 p-4 rounded-2xl border border-gray-200 shadow-[4px_4px_0_rgb(204_124_46_/_10%)] hover:shadow-[6px_6px_0_rgb(204_124_46_/_10%)] hover:-translate-y-0.5 transition-transform transition-shadow duration-200 ease-out flex items-center gap-3">
                <LinkIcon className="h-5 w-5 text-gray-400 flex-shrink-0" />
                <a href={sourceUrl} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline truncate">{sourceUrl}</a>
              </div>
            </RecipeSection>
          )}

          {/* Variants section for original recipes */}
          {!content?.conversion?.isVariant && (
            <VariantsList 
              parentId={recipeId} 
              onOpenRecipeInModal={variant === 'modal' ? (id)=>onOpenRecipeInModal?.(id) : undefined}
              sort={sort}
              renderSection={(variantsContent) => variantsContent ? (
                <RecipeSection id="variants" title="Variants" titleHidden className="mt-4 bg-white">
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
                  {variantsContent}
                </RecipeSection>
              ) : null}
            />
          )}



      {/* Comments */}
      <RecipeSection id="comments" title={
        <span>
          <i className="fa-solid fa-comment mr-2"></i>
          Comments
        </span>
      } className="mt-8 bg-white hover:shadow-[6px_6px_0_rgb(204_124_46_/_15%)] hover:-translate-y-0.5 transition-transform transition-shadow duration-200 ease-out">
            <div className="bg-gray-50 rounded-lg p-4">
              <textarea value={commentInput} onChange={(e)=>setCommentInput(e.target.value)} rows={3} className="w-full bg-white px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent" placeholder="Write a comment..." />
              <div className="flex justify-end mt-2">
                <button onClick={postComment} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#5b8959] text-white hover:brightness-110 transition-all duration-200 text-sm">
                  <i className="fa-solid fa-paper-plane"></i>
                  <span>Send</span>
                </button>
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
                        <div key={c.id} className={`border border-gray-200 rounded-2xl p-3 bg-white mb-3 shadow-[2px_2px_0_rgb(204_124_46_/_10%)] ${level>0? 'ml-6 md:ml-10' : ''}`}>
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
                                <button onClick={async ()=>{ try{ const r= await fetch(`${API_BASE}/comments/${c.id}`, {method:'PATCH', headers:{'Content-Type':'application/json'}, credentials:'include', body: JSON.stringify({body: editValue})}); const j= await r.json(); if(j.ok){ setComments(list => list.map(x => x.id===c.id? j.data : x)); } } finally { setEditingId(null); } }} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-green-600 text-white hover:bg-green-700 transition-all duration-200 text-sm">
                                  <i className="fa-solid fa-check"></i>
                                  <span>Save</span>
                                </button>
                                <button onClick={()=>{ setEditingId(null); }} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-500 text-white hover:bg-gray-600 transition-all duration-200 text-sm">
                                  <i className="fa-solid fa-xmark"></i>
                                  <span>Cancel</span>
                                </button>
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
                                <button onClick={()=>setReplyToId(null)} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-500 text-white hover:bg-gray-600 transition-all duration-200 text-sm">
                                  <i className="fa-solid fa-xmark"></i>
                                  <span>Cancel</span>
                                </button>
                                <button onClick={()=>postReply(c.id)} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-all duration-200 text-sm">
                                  <i className="fa-solid fa-reply"></i>
                                  <span>Reply</span>
                                </button>
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
                            <button onClick={() => onDownload?.(content)} disabled={isEditing} className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#7ab87a] text-white hover:bg-[#659a63] transition-all duration-200 text-sm ${isEditing ? 'opacity-50 cursor-not-allowed' : ''}`}>
              <i className="fa-solid fa-download"></i>
              <span>Download</span>
            </button>
            {!isSaved && (
              <button onClick={() => onSave?.(content)} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-green-600 text-white hover:bg-green-700 transition-all duration-200 text-sm">
                <i className="fa-solid fa-bookmark"></i>
                <span>Save to Recipes</span>
              </button>
            )}
            {isSaved && (
              <>
                <button onClick={()=>setConvertOpen(true)} disabled={isEditing} className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#e87b35] text-white transition-all duration-200 text-sm ${isEditing ? 'opacity-50 cursor-not-allowed' : 'hover:brightness-110'}`}>
                  <i className="fa-solid fa-rotate"></i>
                  <span>Convert</span>
                </button>
                <button onClick={async ()=>{
                  try {
                    const url = window.location.href;
                    const shareData = { title: (edited?.title || title) || 'Recipe', url };
                    if (navigator.share) {
                      await navigator.share(shareData);
                    } else {
                      await navigator.clipboard.writeText(url);
                      // Simple toast fallback
                      const t = document.createElement('div');
                      t.className = 'fixed bottom-4 right-4 bg-gray-900 text-white text-sm px-3 py-2 rounded-lg shadow z-[9999]';
                      t.textContent = 'Link copied to clipboard';
                      document.body.appendChild(t);
                      setTimeout(()=>{ t.remove(); }, 2500);
                    }
                  } catch {}
                }} disabled={isEditing} className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[rgb(158,137,112)] text-white transition-all duration-200 text-sm ${isEditing ? 'opacity-50 cursor-not-allowed' : 'hover:brightness-110'}`}>
                  <i className="fa-solid fa-share-nodes"></i>
                  <span>Share</span>
                </button>
              {isEditing ? (
                <>
                <button onClick={() => { saveEdits(); }} disabled={busySave} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#7ab87a] text-white hover:bg-[#659a63] transition-all duration-200 disabled:opacity-60 text-sm" data-save-button>
                  <i className="fa-solid fa-check"></i>
                  <span>{busySave ? 'Saving…' : 'Save'}</span>
                </button>
                <button onClick={() => { cancelEdit(); }} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-500 text-white hover:bg-gray-600 transition-all duration-200 text-sm" data-cancel-button>
                  <i className="fa-solid fa-xmark"></i>
                    <span>Cancel</span>
                  </button>
                </>
              ) : (
                <button onClick={() => { startEdit(); }} disabled={busySave} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-yellow-500 text-white hover:bg-yellow-600 transition-all duration-200 disabled:opacity-60 text-sm" data-save-button>
                  <i className="fa-solid fa-pen"></i>
                  <span>Edit Recipe</span>
                </button>
              )}
              </>
            )}
            {justSavedVariant && (
              <>
                <button onClick={()=>{ if (variant==='modal' && typeof onOpenRecipeInModal==='function') { onOpenRecipeInModal(null); } }} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-500 text-white hover:bg-gray-600 transition-all duration-200 text-sm">
                  <i className="fa-solid fa-xmark"></i>
                  <span>Close</span>
                </button>
                <button onClick={()=>{ window.location.href = '/'; }} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-all duration-200 text-sm">
                  <i className="fa-solid fa-arrow-left"></i>
                  <span>View in My Recipes</span>
                </button>
              </>
            )}
            {!isSaved && (
              <>
                <button onClick={() => onAddToCollection?.()} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#da8146] text-white hover:brightness-110 transition-all duration-200 text-sm">
                  <i className="fa-solid fa-book-open"></i>
                  <span>Add to Collection</span>
                </button>
              {isEditing ? (
                <>
                  <button onClick={() => { saveEdits(); }} disabled={busySave} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-green-600 text-white hover:bg-green-700 transition-all duration-200 disabled:opacity-60 text-sm" data-save-button>
                    <i className="fa-solid fa-check"></i>
                    <span>{busySave ? 'Saving…' : 'Save Changes'}</span>
                  </button>
                  <button onClick={() => { cancelEdit(); }} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-500 text-white hover:bg-gray-600 transition-all duration-200 text-sm" data-cancel-button>
                    <i className="fa-solid fa-xmark"></i>
                    <span>Cancel</span>
                  </button>
                </>
              ) : (
                <button onClick={() => { startEdit(); }} disabled={busySave} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-yellow-500 text-white hover:bg-yellow-600 transition-all duration-200 disabled:opacity-60 text-sm" data-save-button>
                  <i className="fa-solid fa-pen"></i>
                  <span>Edit Recipe</span>
                </button>
              )}
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
    </div>
  );
}


