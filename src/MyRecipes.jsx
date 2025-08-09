import React, { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { 
  LinkIcon, 
  XMarkIcon, 
  ArrowDownTrayIcon, 
  BookmarkIcon,
  ChevronDownIcon
} from '@heroicons/react/24/outline';

const API_BASE = 'http://localhost:8001/api/v1';
const STATIC_BASE = 'http://localhost:8001';
// --- Tagging UI components ---
const TagChip = ({ label, type, status, onRemove }) => (
    <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs mr-2 mb-2 border ${status === 'pending' ? 'bg-yellow-50 text-yellow-700 border-yellow-200' : 'bg-green-50 text-green-700 border-green-200'}`}>
        <span className="font-medium mr-1">{label}</span>
        <span className="text-gray-400">{type}</span>
        {status === 'pending' && <span className="ml-2 text-[10px] uppercase tracking-wide">pending</span>}
        {onRemove && (
            <button
              onClick={onRemove}
              aria-label={`Ta bort tagg ${label}`}
              className="ml-2 text-gray-400 hover:text-gray-600 hover:bg-gray-200 rounded-full px-1 leading-none"
            >
              ×
            </button>
        )}
    </span>
);

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
const Dropdown = ({ label, value, options, onChange, isOpen, onToggle }) => (
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
                {options.map((option) => (
                    <button
                        key={option.value}
                        onClick={() => {
                            onChange(option.value);
                            onToggle();
                        }}
                        className={`block w-full text-left px-4 py-2 text-sm hover:bg-gray-100 ${
                            value === option.value ? 'bg-blue-50 text-blue-700' : 'text-gray-700'
                        }`}
                    >
                        {option.label}
                    </button>
                ))}
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

const RecipeModal = ({ recipe, onClose, currentUser }) => {
    if (!recipe) return null;
    
    const {
        title, description, ingredients, instructions, image_url,
        prep_time, cook_time, servings, nutritional_information
    } = recipe.recipe_content;
    
    const { source_url } = recipe;

    // Ratings state and actions
    const [ratingSummary, setRatingSummary] = useState({ average: 0, count: 0, userValue: null });
    const [hoverValue, setHoverValue] = useState(0);
    const [busyRating, setBusyRating] = useState(false);

    // Comments state
    const [comments, setComments] = useState([]);
    const [nextCursor, setNextCursor] = useState(null);
    const [commentBody, setCommentBody] = useState("");
    const [busyComment, setBusyComment] = useState(false);
    const [commentError, setCommentError] = useState("");
    const [commentBusyId, setCommentBusyId] = useState(null);
    const [editingCommentId, setEditingCommentId] = useState(null);
    const [editingBody, setEditingBody] = useState("");

    // Tags state
    const [tagsApproved, setTagsApproved] = useState([]);
    const [tagsPending, setTagsPending] = useState([]);
    const [tagError, setTagError] = useState('');
    const [tagSuggestions, setTagSuggestions] = useState([]);

    useEffect(() => {
        const fetchRatings = async () => {
            try {
                const res = await fetch(`${API_BASE}/recipes/${recipe.id}/ratings`, { credentials: 'include' });
                const json = await res.json();
                if (json.ok) setRatingSummary(json.data);
            } catch {}
        };
        const fetchComments = async () => {
            try {
                const res = await fetch(`${API_BASE}/recipes/${recipe.id}/comments?limit=20`, { credentials: 'include' });
                const json = await res.json();
                if (json.ok) {
                    setComments(json.data.items);
                    setNextCursor(json.data.nextCursor);
                }
            } catch {}
        };
        const fetchTags = async () => {
            try {
                const res = await fetch(`${API_BASE}/recipes/${recipe.id}/tags`, { credentials: 'include' });
                const json = await res.json();
                if (json.ok) {
                    setTagsApproved(json.data.approved);
                    setTagsPending(json.data.pending);
                }
                const ts = await fetch(`${API_BASE}/tags/search`).then(r => r.json());
                if (ts.ok) setTagSuggestions(ts.data);
            } catch {}
        };
        fetchRatings();
        fetchComments();
        fetchTags();
    }, [recipe.id]);

    const submitRating = async (value) => {
        if (busyRating) return;
        setBusyRating(true);
        // optimistic update
        const prev = ratingSummary;
        const wasUserValue = prev.userValue;
        let newCount = prev.count;
        let total = prev.average * prev.count;
        if (wasUserValue) {
            total = total - wasUserValue + value;
        } else {
            newCount = prev.count + 1;
            total = total + value;
        }
        const optimistic = { average: newCount ? +(total / newCount).toFixed(2) : 0, count: newCount, userValue: value };
        setRatingSummary(optimistic);
        try {
            const res = await fetch(`${API_BASE}/recipes/${recipe.id}/ratings`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ value })
            });
            const json = await res.json();
            if (!json.ok) throw new Error(json.error || 'Failed');
            setRatingSummary(json.data);
        } catch (e) {
            setRatingSummary(prev);
        } finally {
            setBusyRating(false);
        }
    };

    const canModerate = currentUser?.is_admin || (currentUser?.roles || []).includes('moderator');
    const canDirectTag = canModerate || (currentUser && (currentUser.roles || []).some(r => ['trusted'].includes(r)) || currentUser?.id === recipe.user_id);

    const addTags = async (keywords) => {
        if (!keywords || keywords.length === 0) return;
        setTagError('');
        try {
            const res = await fetch(`${API_BASE}/recipes/${recipe.id}/tags`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ keywords })
            });
            const json = await res.json();
            if (!json.ok) throw new Error('Failed to add tags');
            // Merge into local state
            setTagsApproved(a => [...a, ...(json.data.added || []).map(k => ({ keyword: k, type: (tagSuggestions.find(t=>t.keyword===k)||{}).type, status: 'approved' }))]);
            setTagsPending(p => [...p, ...(json.data.pending || []).map(k => ({ keyword: k, type: (tagSuggestions.find(t=>t.keyword===k)||{}).type, status: 'pending' }))]);
        } catch (e) {
            setTagError('Kunde inte lägga till taggar.');
        }
    };

    const removeTag = async (keyword) => {
        setTagError('');
        try {
            const res = await fetch(`${API_BASE}/recipes/${recipe.id}/tags?keyword=${encodeURIComponent(keyword)}`, { method: 'DELETE', credentials: 'include' });
            const json = await res.json();
            if (!json.ok) throw new Error();
            setTagsApproved(a => a.filter(t => t.keyword !== keyword));
            setTagsPending(p => p.filter(t => t.keyword !== keyword));
        } catch {
            setTagError('Kunde inte ta bort tagg.');
        }
    };

    const deleteRating = async () => {
        if (busyRating || ratingSummary.userValue == null) return;
        setBusyRating(true);
        const prev = ratingSummary;
        let newCount = Math.max(0, prev.count - 1);
        let total = prev.average * prev.count - prev.userValue;
        const optimistic = { average: newCount ? +(total / newCount).toFixed(2) : 0, count: newCount, userValue: null };
        setRatingSummary(optimistic);
        try {
            const res = await fetch(`${API_BASE}/recipes/${recipe.id}/ratings`, { method: 'DELETE', credentials: 'include' });
            const json = await res.json();
            if (!json.ok) throw new Error(json.error || 'Failed');
            setRatingSummary(json.data);
        } catch (e) {
            setRatingSummary(prev);
        } finally {
            setBusyRating(false);
        }
    };

    const submitComment = async (e) => {
        e.preventDefault();
        const body = commentBody.trim();
        if (!body) return;
        if (busyComment) return;
        setBusyComment(true);
        const optimistic = {
            id: `temp-${Date.now()}`,
            recipeId: recipe.id,
            user: { id: 0, displayName: 'Du' },
            body,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            parentId: null
        };
        setComments([optimistic, ...comments]);
        setCommentBody("");
        setCommentError("");
        try {
            const res = await fetch(`${API_BASE}/recipes/${recipe.id}/comments`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ body })
            });
            const json = await res.json().catch(() => ({}));
            if (!res.ok || !json.ok) {
                const detail = json?.error || json?.detail || `${res.status}`;
                throw new Error(detail);
            }
            // replace temp with server dto
            setComments((prevList) => [json.data, ...prevList.filter(c => !String(c.id).startsWith('temp-'))]);
        } catch (e) {
            // revert
            setComments((prevList) => prevList.filter(c => !String(c.id).startsWith('temp-')));
            setCommentBody(body);
            setCommentError(e.message === '401' ? 'Du måste vara inloggad för att kommentera.' : e.message === '429' ? 'För många kommentarer, vänta en stund.' : 'Kunde inte skicka kommentaren.');
        } finally {
            setBusyComment(false);
        }
    };

    const loadMoreComments = async () => {
        if (!nextCursor) return;
        try {
            const res = await fetch(`${API_BASE}/recipes/${recipe.id}/comments?limit=20&after=${encodeURIComponent(nextCursor)}`, { credentials: 'include' });
            const json = await res.json();
            if (json.ok) {
                // dedupe by id
                const existing = new Set(comments.map(c => c.id));
                const merged = [...comments];
                json.data.items.forEach(item => { if (!existing.has(item.id)) merged.push(item); });
                setComments(merged);
                setNextCursor(json.data.nextCursor);
            }
        } catch {}
    };

    const removeComment = async (commentId) => {
        if (commentBusyId) return;
        setCommentError("");
        setCommentBusyId(commentId);
        // Optimistiskt: markera som raderad
        const prev = comments;
        setComments((list) => list.map(c => c.id === commentId ? { ...c, body: '(raderad)' } : c));
        try {
            const res = await fetch(`${API_BASE}/comments/${commentId}`, { method: 'DELETE', credentials: 'include' });
            const json = await res.json().catch(() => ({}));
            if (!res.ok || !json.ok) {
                if (res.status === 401) setCommentError('Du måste vara inloggad.');
                else if (res.status === 403) setCommentError('Otillåten åtgärd.');
                else setCommentError('Kunde inte ta bort kommentaren.');
                // revertera
                setComments(prev);
                return;
            }
            // Uppdatera med serverns DTO (soft-deleted)
            setComments((list) => list.map(c => c.id === commentId ? json.data : c));
        } catch (e) {
            setComments(prev);
            setCommentError('Kunde inte ta bort kommentaren.');
        } finally {
            setCommentBusyId(null);
        }
    };

    const startEdit = (comment) => {
        if (commentBusyId) return;
        setEditingCommentId(comment.id);
        setEditingBody(comment.body === '(raderad)' ? '' : comment.body || '');
        setCommentError("");
    };

    const cancelEdit = () => {
        setEditingCommentId(null);
        setEditingBody("");
    };

    const saveEdit = async (commentId) => {
        const newBody = (editingBody || '').trim();
        if (newBody.length === 0) {
            setCommentError('Kommentaren kan inte vara tom.');
            return;
        }
        if (newBody.length > 2000) {
            setCommentError('Kommentaren är för lång.');
            return;
        }
        if (commentBusyId) return;
        setCommentBusyId(commentId);
        setCommentError("");
        const prev = comments;
        // Optimistiskt
        setComments((list) => list.map(c => c.id === commentId ? { ...c, body: newBody } : c));
        try {
            const res = await fetch(`${API_BASE}/comments/${commentId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ body: newBody })
            });
            const json = await res.json().catch(() => ({}));
            if (!res.ok || !json.ok) {
                if (res.status === 401) setCommentError('Du måste vara inloggad.');
                else if (res.status === 403) setCommentError('Otillåten åtgärd.');
                else if (res.status === 400) setCommentError('Ogiltig kommentar.');
                else setCommentError('Kunde inte spara ändringen.');
                setComments(prev);
                return;
            }
            setComments((list) => list.map(c => c.id === commentId ? json.data : c));
            setEditingCommentId(null);
            setEditingBody("");
        } catch (e) {
            setComments(prev);
            setCommentError('Kunde inte spara ändringen.');
        } finally {
            setCommentBusyId(null);
        }
    };

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
            <div className="bg-white rounded-2xl max-w-4xl w-full max-h-[90vh] flex flex-col shadow-2xl" onClick={(e) => e.stopPropagation()}>
                {/* Header */}
                <div className="p-5 border-b border-gray-200">
                    <div className="flex justify-between items-start">
                        <h2 className="text-3xl font-bold text-gray-900">{title || 'Untitled Recipe'}</h2>
                        <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><XMarkIcon className="h-7 w-7" /></button>
                    </div>
                </div>

                {/* Body */}
                <div className="p-6 overflow-y-auto">
                    <div className="flex flex-col md:flex-row gap-8">
                        {/* Left Column */}
                        <div className="md:w-1/3">
                            {image_url && <img 
                                src={(image_url.startsWith('http') ? normalizeUrlPort(image_url) : STATIC_BASE + image_url)}
                                alt={title} 
                                className="w-full h-auto object-cover rounded-lg shadow-md mb-6" 
                                onError={(e) => { 
                                    console.log('Modal image failed to load:', e.target.src);
                                    e.target.style.display = 'none'; 
                                }}
                                onLoad={(e) => {
                                    console.log('Modal image loaded successfully:', e.target.src);
                                }}
                            />}
                            <div className="space-y-4">
                                {servings && <InfoCard label="Servings" value={servings} />}
                                {prep_time && <InfoCard label="Prep Time" value={prep_time} />}
                                {cook_time && <InfoCard label="Cook Time" value={cook_time} />}
                            </div>
                        </div>
                        {/* Right Column */}
                        <div className="md:w-2/3">
                            {description && <Section title="Description"><p className="text-gray-700 leading-relaxed">{description}</p></Section>}

                            {ingredients?.length > 0 && <IngredientSection items={ingredients} />}
                            {instructions?.length > 0 && <InstructionSection items={instructions} />}
                            {nutritional_information && <NutritionSection data={nutritional_information} />}
                            {source_url && <SourceSection url={source_url} />}

                            {/* Comments Section */}
                            {/* Rating directly above Comments */}
                            <Section title="Ratings">
                                <div className="flex items-center gap-2" role="radiogroup" aria-label="Betygsätt 1 till 5">
                                    {[1,2,3,4,5].map((v) => (
                                        <Star
                                            key={v}
                                            filled={v <= (hoverValue || ratingSummary.userValue || Math.round(ratingSummary.average))}
                                            onClick={() => submitRating(v)}
                                            onMouseEnter={() => setHoverValue(v)}
                                            onMouseLeave={() => setHoverValue(0)}
                                            ariaLabel={`Betygsätt ${v} av 5`}
                                        />
                                    ))}
                                    <span className="text-sm text-gray-600 ml-2">{ratingSummary.average?.toFixed(2)} ({ratingSummary.count})</span>
                                    {ratingSummary.userValue != null && (
                                        <button onClick={deleteRating} className="ml-3 text-xs text-gray-500 underline disabled:text-gray-300" disabled={busyRating}>Ta bort mitt betyg</button>
                                    )}
                                </div>
                            </Section>
                            
                            {/* Tags Section */}
                            <Section title="Tags">
                                <div className="mb-3">
                                    <div className="flex flex-wrap">
                                        {tagsApproved.map(t => (
                                            <span key={`a-${t.keyword}`} className="mr-2 mb-2">
                                                <TagChip
                                                  label={t.keyword}
                                                  type={t.type}
                                                  status="approved"
                                                  onRemove={(canDirectTag || canModerate) ? (() => removeTag(t.keyword)) : undefined}
                                                />
                                            </span>
                                        ))}
                                        {tagsPending.map(t => (
                                            <span key={`p-${t.keyword}`} className="mr-2 mb-2">
                                                <TagChip label={t.keyword} type={t.type} status="pending" />
                                                {canModerate && (
                                                    <>
                                                        <button onClick={async () => {
                                                            await fetch(`${API_BASE}/recipes/${recipe.id}/tags/approve`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include', body: JSON.stringify(t.keyword) });
                                                            setTagsPending(p => p.filter(x => x.keyword !== t.keyword));
                                                            setTagsApproved(a => [...a, { ...t, status: 'approved' }]);
                                                        }} className="text-xs text-green-600 underline ml-1">Godkänn</button>
                                                        <button onClick={async () => {
                                                            await fetch(`${API_BASE}/recipes/${recipe.id}/tags/reject`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include', body: JSON.stringify(t.keyword) });
                                                            setTagsPending(p => p.filter(x => x.keyword !== t.keyword));
                                                        }} className="text-xs text-red-600 underline ml-2">Avslå</button>
                                                    </>
                                                )}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                                <TagPicker canEdit={canDirectTag} onAdd={addTags} suggestions={tagSuggestions} />
                                {tagError && <p className="text-sm text-red-600 mt-1">{tagError}</p>}
                            </Section>

                            {/* Visual separator before comments */}
                            <div className="border-t border-gray-200 my-6" />

                            {/* Comments (kept within same content section at bottom) */}
                            <Section title="Comments">
                                <form onSubmit={submitComment} className="mb-4">
                                    <textarea
                                        value={commentBody}
                                        onChange={(e) => setCommentBody(e.target.value)}
                                        rows={3}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent resize-none"
                                        placeholder="Write a comment…"
                                    />
                                    {commentError && <p className="text-sm text-red-600 mt-1">{commentError}</p>}
                                    <div className="flex justify-end mt-2">
                                        <button disabled={!commentBody.trim() || busyComment} className="bg-green-600 text-white font-semibold py-2 px-4 rounded-lg hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors">Send</button>
                                    </div>
                                </form>
                                        <div className="space-y-4">
                                    {comments.length === 0 ? (
                                        <p className="text-gray-500">Be the first to comment.</p>
                                    ) : comments.map((c) => (
                                        <div key={c.id} className="border border-gray-200 rounded-lg p-4">
                                            <div className="flex items-start justify-between mb-2">
                                                <div className="flex items-center gap-2">
                                                    {c.user?.avatar && (
                                                      <img src={(String(c.user.avatar).startsWith('http') ? c.user.avatar : `${STATIC_BASE}${c.user.avatar}`)} alt="avatar" className="h-6 w-6 rounded-full object-cover" onError={(e)=>{e.currentTarget.style.display='none';}} />
                                                    )}
                                                    <span className="font-medium text-gray-900">{c.user?.username || c.user?.displayName || 'Anonymous'}</span>
                                                </div>
                                                <div className="flex items-center gap-3">
                                                    <span className="text-sm text-gray-500">{new Date(c.createdAt).toLocaleString()}</span>
                                                    {(currentUser?.id === c.user?.id || currentUser?.is_admin) && (
                                                        <>
                                                          <button
                                                            onClick={() => startEdit(c)}
                                                            className="text-xs text-gray-600 underline disabled:text-gray-300"
                                                            disabled={commentBusyId === c.id}
                                                          >Edit</button>
                                                          <button
                                                            onClick={() => removeComment(c.id)}
                                                            className="text-xs text-red-600 underline disabled:text-gray-300"
                                                            disabled={commentBusyId === c.id}
                                                          >Delete</button>
                                                        </>
                                                    )}
                                                </div>
                                            </div>
                                            {editingCommentId === c.id ? (
                                                <div>
                                                    <textarea
                                                      value={editingBody}
                                                      onChange={(e) => setEditingBody(e.target.value)}
                                                      rows={3}
                                                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent resize-none"
                                                    />
                                                    <div className="flex gap-2 mt-2">
                                                        <button
                                                          onClick={() => saveEdit(c.id)}
                                                          className="bg-green-600 text-white text-sm font-semibold py-1.5 px-3 rounded-lg hover:bg-green-700 disabled:bg-gray-300"
                                                          disabled={commentBusyId === c.id}
                                                        >Save</button>
                                                        <button
                                                          onClick={cancelEdit}
                                                          type="button"
                                                          className="text-sm text-gray-600 underline"
                                                        >Cancel</button>
                                                    </div>
                                                </div>
                                            ) : (
                                                <>
                                                  <p className="text-gray-700 leading-relaxed">{c.body}</p>
                                                  <div className="flex justify-end items-center gap-1 mt-2">
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
                                                </>
                                            )}
                                        </div>
                                    ))}
                                </div>
                                {nextCursor && (
                                    <div className="flex justify-center mt-4">
                                        <button onClick={loadMoreComments} className="text-sm text-gray-600 underline">Load more</button>
                                    </div>
                                )}
                            </Section>
                        </div>
                    </div>
                </div>

                {/* (Removed full-width comments block per design revert) */}

                {/* Footer */}
                <div className="p-5 border-t border-gray-200 bg-gray-50 rounded-b-2xl mt-auto">
                    <button className="flex items-center gap-2 bg-blue-600 text-white font-semibold py-3 px-6 rounded-lg hover:bg-blue-700 transition-colors">
                        <ArrowDownTrayIcon className="h-5 w-5" /><span>Download PDF</span>
                    </button>
                </div>
            </div>
        </div>
    );
};

// --- Recipe Card Component ---
const RecipeCard = ({ recipe, viewMode, onClick }) => {
    const { title, description, image_url, ingredients } = recipe.recipe_content;
    
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
                        <img 
                            src={image_url ? (image_url.startsWith('http') ? normalizeUrlPort(image_url) : STATIC_BASE + image_url) : 'https://placehold.co/400x300/EEE/31343C?text=No+Image'} 
                            alt={title} 
                            className="w-full h-48 object-cover" 
                            onError={(e) => { e.target.src = 'https://placehold.co/400x300/EEE/31343C?text=No+Image'; }}
                        />
                        <div className="p-5">
                            <h2 className="font-semibold text-lg text-gray-800">{title}</h2>
                        </div>
                    </>
                );
            case 'title_image_description':
                return (
                    <>
                        <img 
                            src={image_url ? (image_url.startsWith('http') ? normalizeUrlPort(image_url) : STATIC_BASE + image_url) : 'https://placehold.co/400x300/EEE/31343C?text=No+Image'} 
                            alt={title} 
                            className="w-full h-48 object-cover" 
                            onError={(e) => { e.target.src = 'https://placehold.co/400x300/EEE/31343C?text=No+Image'; }}
                        />
                        <div className="p-5">
                            <h2 className="font-semibold text-lg mb-2 text-gray-800">{title}</h2>
                            <p className="text-sm text-gray-500 line-clamp-2">{description}</p>
                        </div>
                    </>
                );
            case 'title_image_ingredients':
                return (
                    <>
                        <img 
                            src={image_url ? (image_url.startsWith('http') ? image_url : STATIC_BASE + image_url) : 'https://placehold.co/400x300/EEE/31343C?text=No+Image'} 
                            alt={title} 
                            className="w-full h-48 object-cover" 
                            onError={(e) => { e.target.src = 'https://placehold.co/400x300/EEE/31343C?text=No+Image'; }}
                        />
                        <div className="p-5">
                            <h2 className="font-semibold text-lg mb-2 text-gray-800">{title}</h2>
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
            className="bg-white rounded-lg shadow-lg overflow-hidden cursor-pointer hover:shadow-2xl transition-shadow duration-300 flex flex-col" 
            onClick={onClick}
        >
            {renderContent()}
            <div className="px-5 pb-5 mt-auto">
                <div className="flex items-center text-xs text-gray-400 pt-4 border-t border-gray-100">
                    <span>Saved on {new Date(recipe.created_at).toLocaleDateString()}</span>
                </div>
            </div>
        </div>
    );
};

// --- Main Page Component ---
const MyRecipes = () => {
    const { currentUser } = useOutletContext();
    const [recipes, setRecipes] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [selectedRecipe, setSelectedRecipe] = useState(null);
    
    // Dropdown states
    const [viewMode, setViewMode] = useState('title_image_description');
    const [layoutMode, setLayoutMode] = useState('grid_2');
    const [isDropdownOpen, setIsDropdownOpen] = useState(false);
    const [isLayoutDropdownOpen, setIsLayoutDropdownOpen] = useState(false);

    // Dropdown options
    const viewOptions = [
        { value: 'title_only', label: 'Bara titel' },
        { value: 'title_image', label: 'Titel + bild' },
        { value: 'title_image_description', label: 'Titel + bild + description' },
        { value: 'title_image_ingredients', label: 'Titel + bild + ingredients' }
    ];

    const layoutOptions = [
        { value: 'grid_2', label: 'Cols (2 bilder per col)' },
        { value: 'grid_3', label: 'Cols (3 bilder per col)' },
        { value: 'list', label: 'Lista (bara titel)' }
    ];

    useEffect(() => {
        const fetchRecipes = async () => {
            try {
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

    const getGridClasses = () => {
        switch (layoutMode) {
            case 'grid_2':
                return 'grid-cols-1 md:grid-cols-2';
            case 'grid_3':
                return 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3';
            case 'list':
                return 'grid-cols-1';
            default:
                return 'grid-cols-1 md:grid-cols-2';
        }
    };

    if (loading) return <div className="text-center p-8">Loading recipes...</div>;
    if (error) return <div className="text-center p-8 text-red-500">Error: {error}</div>;

    return (
        <div className="container mx-auto p-8">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-8 gap-4">
                <h1 className="text-4xl font-bold text-gray-800">My Saved Recipes</h1>
                
                {/* Dropdown Controls */}
                <div className="flex flex-col sm:flex-row gap-4">
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

            {recipes.length === 0 ? (
                <div className="text-center py-16">
                     <BookmarkIcon className="h-16 w-16 mx-auto mb-4 text-gray-300" />
                     <h3 className="text-xl font-semibold mb-2 text-gray-600">No Saved Recipes Yet</h3>
                     <p className="text-gray-500">Start by generating and saving your first recipe!</p>
                </div>
            ) : (
                <div className={`grid ${getGridClasses()} gap-8`}>
                    {recipes.map(recipe => (
                        <RecipeCard
                            key={recipe.id}
                            recipe={recipe}
                            viewMode={viewMode}
                            onClick={() => setSelectedRecipe(recipe)}
                        />
                    ))}
                </div>
            )}
            <RecipeModal key={selectedRecipe?.id || 'modal-empty'} recipe={selectedRecipe} onClose={() => setSelectedRecipe(null)} currentUser={currentUser} />
        </div>
    );
};

export default MyRecipes;