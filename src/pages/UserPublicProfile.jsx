import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, Link, useOutletContext } from 'react-router-dom';
import RecipeView from '../components/RecipeView';

// NOTE: We reuse existing API base; where services/hooks exist in the app, wire them in. Until then, we use simple fetches.
const API_BASE = 'http://localhost:8001/api/v1';
const API_ROOT = API_BASE.replace(/\/api\/v1$/, '');
const STATIC_BASE = API_ROOT;
const PROXY = `${API_BASE}/proxy-image?url=`;
function normalizeBackendUrl(pathOrUrl) {
  if (!pathOrUrl) return pathOrUrl;
  if (/^https?:\/\//i.test(pathOrUrl)) return pathOrUrl;
  const clean = String(pathOrUrl).startsWith('/') ? pathOrUrl : `/${pathOrUrl}`;
  return `${API_ROOT}${clean}`;
}

function normalizeUrlPort(url) {
  if (!url || typeof url !== 'string') return url;
  return url
    .replace('http://127.0.0.1:8000', 'http://127.0.0.1:8001')
    .replace('http://localhost:8000', 'http://localhost:8001');
}

function asThumbSrc(imageUrl) {
  const url = normalizeUrlPort(imageUrl);
  if (!url) return null;
  if (url.startsWith('http://localhost:8001') || url.startsWith('http://127.0.0.1:8001') || url.startsWith('/')) {
    return url.startsWith('http') ? url : STATIC_BASE + url;
  }
  return PROXY + encodeURIComponent(url);
}

// Small UI primitives (use project UI kit if available)
const Button = ({ children, className = '', variant = 'default', disabled, ...props }) => {
  const base = 'inline-flex items-center justify-center px-4 py-2 rounded-lg font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed';
  const variants = {
    default: 'bg-[#e87b35] hover:bg-[#d1742f] text-white focus:ring-[#e87b35] focus:ring-offset-white',
    ghost: 'bg-white hover:bg-gray-50 text-gray-800 border border-gray-300',
    subtle: 'bg-gray-100 hover:bg-gray-200 text-gray-800',
    danger: 'bg-red-600 hover:bg-red-700 text-white',
    outline: 'border border-gray-300 bg-white hover:bg-gray-50 text-gray-800',
  };
  return (
    <button className={`${base} ${variants[variant] || variants.default} ${className}`} disabled={disabled} {...props}>
      {children}
    </button>
  );
};

const Stat = ({ label, value, onClick }) => (
  <button onClick={onClick} className="text-center px-3 py-1 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-[#e87b35]">
    <div className="text-lg font-semibold">{value ?? '–'}</div>
    <div className="text-xs text-gray-500">{label}</div>
  </button>
);

const Chip = ({ children }) => (
  <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs bg-amber-50 text-amber-800 border border-amber-200 mr-2 mb-2">
    {children}
  </span>
);

// Match tag coloring used on recipe cards
function getTagClass(label) {
  const l = String(label||'').toLowerCase();
  if (l === 'vegan') return 'bg-emerald-600 text-white';
  if (l === 'zesty') return 'bg-yellow-500 text-white';
  if (l === 'seafood') return 'bg-blue-600 text-white';
  if (l === 'vegetarian') return 'bg-lime-600 text-white';
  if (l === 'pescetarian' || l === 'pescatarian') return 'bg-sky-600 text-white';
  if (l === 'fastfood') return 'bg-orange-500 text-white';
  // broader mapping used across the app
  const map = {
    'high-protein': 'bg-purple-50 text-purple-700 border border-purple-200',
    'baked': 'bg-orange-50 text-orange-700 border border-orange-200',
    'shellfish-free': 'bg-teal-50 text-teal-700 border border-teal-200',
    'egg-free': 'bg-amber-50 text-amber-800 border border-amber-200',
    'fish-free': 'bg-cyan-50 text-cyan-700 border border-cyan-200',
    'dairy-free': 'bg-rose-50 text-rose-700 border border-rose-200',
    'pasta': 'bg-yellow-50 text-yellow-700 border border-yellow-200',
    'easy': 'bg-gray-100 text-gray-700 border border-gray-200',
    'italian': 'bg-red-50 text-red-700 border border-red-200',
    'dinner': 'bg-blue-50 text-blue-700 border border-blue-200',
    'healthy': 'bg-emerald-50 text-emerald-700 border border-emerald-200',
    'rice': 'bg-stone-50 text-stone-700 border border-stone-200',
    'american': 'bg-indigo-50 text-indigo-700 border border-indigo-200'
  };
  if (map[l]) return map[l];
  // Default subdued style
  return 'bg-gray-100 text-gray-700 border border-gray-200';
}

function normalizeTag(tag) {
  const k = String(tag || '').trim().toLowerCase();
  if (!k) return k;
  if (k === 'pescatarian') return 'pescatarian';
  return k;
}

function getRecipeTagSet(recipe) {
  const set = new Set();
  const rc = recipe?.recipe_content || {};
  const conv = rc.conversion || {};
  const presets = ((conv.constraints || {}).presets) || [];
  for (const raw of presets) {
    const key = normalizeTag(raw);
    if (!key || key.startsWith('add-') || key.startsWith('remove-')) continue;
    set.add(key);
  }
  try {
    const approved = (recipe?.tags?.approved || []).map(t => t.keyword);
    for (const raw of approved) {
      const key = normalizeTag(raw);
      if (key) set.add(key);
    }
  } catch {}
  return set;
}

// Skeletons
const Skeleton = ({ className }) => <div className={`animate-pulse bg-gray-200 rounded ${className}`} />;

// Message Drawer / Modal
const MessageDrawer = ({ isOpen, onClose, profileUser, onSend }) => {
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const [messages, setMessages] = useState([]); // TODO: wire to existing message thread selector
  const listRef = useRef(null);

  useEffect(() => {
    if (isOpen) {
      // TODO: wire openMessageThread(profileUser.id)
      // DEV-ONLY MOCK (remove)
      setMessages([
        { id: 1, byMe: false, body: 'Hi! 👋', ts: new Date(Date.now() - 3600_000) },
        { id: 2, byMe: true, body: 'Hey there, love your recipes!', ts: new Date(Date.now() - 3500_000) },
      ]);
    }
  }, [isOpen, profileUser]);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages, isOpen]);

  const handleSend = async () => {
    if (!input.trim()) return;
    setSending(true);
    setError(null);
    const optimistic = { id: `tmp-${Date.now()}`, byMe: true, body: input, ts: new Date() };
    setMessages(prev => [...prev, optimistic]);
    setInput('');
    try {
      // TODO: wire to existing message send service, keep same signature if available
      // await sendMessage(profileUser.id, optimistic.body)
      await new Promise(r => setTimeout(r, 500));
      onSend?.(optimistic.body);
    } catch (e) {
      setError('Failed to send.');
    } finally {
      setSending(false);
    }
  };

  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-[100]" aria-modal="true" role="dialog" onClick={(e)=>{ if (e.target===e.currentTarget) onClose?.(); }}>
      <div className="absolute inset-0 bg-black/40" />
      <div className="absolute bottom-0 left-0 right-0 md:inset-y-10 md:right-10 md:w-[420px] md:left-auto bg-white rounded-t-2xl md:rounded-2xl shadow-xl flex flex-col max-h-[90vh]">
        <div className="p-4 border-b flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-gray-200 overflow-hidden flex items-center justify-center">
            {profileUser?.avatar_url ? (
              <img src={normalizeBackendUrl(profileUser.avatar_url)} alt={`${profileUser?.username || 'user'} avatar`} className="w-full h-full object-cover" onError={(e)=>{ e.currentTarget.style.display='none'; }} />
            ) : (
                              <span className="font-semibold text-gray-600">{(profileUser?.username || profileUser?.full_name || '?').slice(0,1).toUpperCase()}</span>
            )}
          </div>
          <div className="flex-1 min-w-0">
                            <div className="font-semibold truncate">{profileUser?.username || profileUser?.full_name}</div>
            <a className="text-xs text-[#e87b35] hover:underline" href="#" onClick={(e)=>e.preventDefault()}>{/* TODO: link to full conversation view if exists */}View full conversation</a>
          </div>
          <button aria-label="Close" className="text-gray-500 hover:text-gray-700" onClick={onClose}>&times;</button>
        </div>
        <div ref={listRef} className="flex-1 overflow-auto p-4 space-y-2 bg-gray-50">
          {messages.map(m => (
            <div key={m.id} className={`max-w-[70%] px-3 py-2 rounded-2xl ${m.byMe ? 'ml-auto bg-[#e87b35] text-white' : 'bg-white border'}`}>{m.body}</div>
          ))}
          {error && <div className="text-xs text-red-600">{error}</div>}
        </div>
        <div className="p-3 border-t">
          <div className="flex items-end gap-2">
            <textarea
              value={input}
              onChange={(e)=>setInput(e.target.value)}
              onKeyDown={(e)=>{ if ((e.metaKey || e.ctrlKey) && e.key==='Enter') handleSend(); }}
              rows={1}
              placeholder="Write a message…"
              className="flex-1 resize-none max-h-32 border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#e87b35]"
            />
            <Button onClick={handleSend} disabled={sending || !input.trim()}>{sending ? 'Sending…' : 'Send'}</Button>
          </div>
          {/* TODO: attachment upload button */}
        </div>
      </div>
    </div>
  );
};

// Header with actions
const ProfileHeader = ({ profileUser, isOwn, stats, tags, onFollowToggle, following, onMessage, loadingFollow }) => {
  const [bioExpanded, setBioExpanded] = useState(false);
  const bio = profileUser?.bio || 'This cook has not added a bio yet.'; // TODO: wire to existing user.bio field if available
  const shortBio = useMemo(() => bioExpanded ? bio : (bio || '').slice(0, 140), [bio, bioExpanded]);

  const share = async () => {
    try {
      const url = window.location.href;
      const title = `${profileUser?.username || profileUser?.full_name}`;
      if (navigator.share) await navigator.share({ title, url });
      else {
        await navigator.clipboard.writeText(url);
        // TODO: use project toast/snackbar
        alert('Profile link copied to clipboard');
      }
    } catch {}
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-6">
      <div>
        <div className="flex items-start gap-4">
          <div className="w-28 h-28 md:w-32 md:h-32 rounded-full bg-gray-200 overflow-hidden flex items-center justify-center">
            {profileUser?.avatar_url ? (
              <img src={normalizeBackendUrl(profileUser.avatar_url)} alt={`${profileUser?.username || 'user'} avatar`} className="w-full h-full object-cover" onError={(e)=>{ e.currentTarget.style.display='none'; }} />
            ) : (
                              <span className="text-2xl font-bold text-gray-600">{(profileUser?.username || profileUser?.full_name || '?').slice(0,1).toUpperCase()}</span>
            )}
          </div>
          <div className="min-w-0">
                            <h1 className="text-2xl md:text-3xl font-extrabold text-gray-900 truncate">{profileUser?.username || profileUser?.full_name}</h1>
            <p className="text-gray-600 mt-2">
              <span className="align-top inline-block max-w-[60ch]">
                {shortBio}{!bioExpanded && bio.length > shortBio.length ? '…' : ''}
              </span>
              {bio.length > 140 && (
                <button className="ml-2 text-[#e87b35] hover:underline" onClick={()=>setBioExpanded(v=>!v)}>{bioExpanded ? 'Show less' : 'Show more'}</button>
              )}
            </p>
          </div>
        </div>

        {/* Stats */}
        <div className="mt-4 flex flex-wrap items-center gap-2 md:gap-4">
          <Stat label="Recipes" value={stats.recipes} onClick={()=>document.getElementById('tab-recipes')?.scrollIntoView({behavior:'smooth'})} />
          <Stat label="Followers" value={stats.followers} onClick={()=>{/* TODO: open followers list */}} />
          <Stat label="Following" value={stats.following} onClick={()=>{/* TODO: open following list */}} />
          <Stat label="Collections" value={stats.collections} onClick={()=>document.getElementById('tab-collections')?.scrollIntoView({behavior:'smooth'})} />
          <Stat label="Avg. rating" value={stats.avgRating ?? '–'} onClick={()=>{}} />
        </div>

        {/* Tags moved to filter panel */}
      </div>

      {/* Actions */}
      <div className="flex md:flex-col gap-3 md:items-end items-stretch md:justify-start">
        {isOwn && (
          <Link to="/profile" className="inline-flex items-center justify-center px-4 py-2 rounded-lg border bg-white hover:bg-gray-50 text-gray-800">
            My profile
          </Link>
        )}
        {!isOwn && (
          <Button onClick={onFollowToggle} disabled={loadingFollow} className="w-full md:w-48">
            {loadingFollow ? 'Please wait…' : (following ? 'Unfollow' : 'Follow')}
          </Button>
        )}
        {!isOwn && (
          <Button variant="outline" className="w-full md:w-48" onClick={onMessage}>Message</Button>
        )}
        <Button variant="ghost" className="w-full md:w-48" onClick={share}>Share</Button>
        <Button variant="subtle" className="w-full md:w-48" onClick={()=>{/* TODO: report user */}}>Report</Button>
      </div>
    </div>
  );
};

const StickyTabs = ({ active, onChange }) => {
  const tabs = [
    { key: 'recipes', label: 'Recipes' },
    { key: 'collections', label: 'Collections' },
    { key: 'activity', label: 'Activity' },
    { key: 'about', label: 'About' },
  ];
  return (
    <div className="sticky top-0 z-30 bg-[#FAF9F7]/90 backdrop-blur border-b mt-6">
      <div className="max-w-7xl mx-auto px-4 md:px-6">
        <div className="flex gap-6 overflow-x-auto">
          {tabs.map(t => (
            <button key={t.key} id={`tab-${t.key}`} onClick={()=>onChange(t.key)} className={`py-3 font-medium whitespace-nowrap border-b-2 ${active===t.key? 'border-[#e87b35] text-gray-900' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>{t.label}</button>
          ))}
        </div>
      </div>
    </div>
  );
};

// Filters (desktop side and mobile FAB)
const RecipeFilters = ({ open, onClose, filters, setFilters, onApply }) => {
  const content = (
    <div className="w-80 bg-white h-full flex flex-col">
      <div className="p-4 border-b flex items-center justify-between">
        <div className="font-semibold">Filters</div>
        <button className="text-gray-500" onClick={onClose}>&times;</button>
      </div>
      <div className="p-4 space-y-4 overflow-auto">
        {/* Category */}
        <div>
          <div className="text-sm font-semibold mb-2">Category</div>
          <div className="flex flex-wrap gap-2">
            {['Breakfast','Lunch','Dinner','Dessert','Snack'].map(c => (
              <button key={c} onClick={()=>setFilters(f=>({...f, category: f.category===c?null:c}))} className={`px-3 py-1.5 rounded-full text-sm border ${filters.category===c? 'bg-[#e87b35] text-white border-transparent' : 'bg-white hover:bg-gray-50'}`}>{c}</button>
            ))}
          </div>
        </div>
        {/* Diet */}
        <div>
          <div className="text-sm font-semibold mb-2">Diet</div>
          <div className="flex flex-wrap gap-2">
            {['Vegan','Vegetarian','Pescetarian'].map(d => (
              <button key={d} onClick={()=>setFilters(f=>({...f, diet: f.diet===d?null:d}))} className={`px-3 py-1.5 rounded-full text-sm border ${filters.diet===d? 'bg-[#e87b35] text-white border-transparent' : 'bg-white hover:bg-gray-50'}`}>{d}</button>
            ))}
          </div>
        </div>
        {/* Time */}
        <div>
          <div className="text-sm font-semibold mb-2">Time</div>
          <select value={filters.time||''} onChange={(e)=>setFilters(f=>({...f, time: e.target.value||null}))} className="w-full border rounded-lg px-3 py-2">
            <option value="">Any</option>
            <option value="15">Under 15 min</option>
            <option value="30">Under 30 min</option>
            <option value="60">Under 60 min</option>
          </select>
        </div>
        {/* Rating */}
        <div>
          <div className="text-sm font-semibold mb-2">Minimum rating</div>
          <select value={filters.rating||''} onChange={(e)=>setFilters(f=>({...f, rating: e.target.value||null}))} className="w-full border rounded-lg px-3 py-2">
            <option value="">Any</option>
            {[5,4,3,2,1].map(v => <option key={v} value={v}>{v}+</option>)}
          </select>
        </div>
      </div>
      <div className="p-4 border-t flex gap-2">
        <Button variant="ghost" className="flex-1" onClick={()=>{ setFilters({}); onApply?.(); }}>Clear</Button>
        <Button className="flex-1" onClick={()=>{ onApply?.(); onClose?.(); }}>Apply</Button>
      </div>
    </div>
  );

  return (
    <>
      {/* Drawer for mobile */}
      {open && (
        <div className="fixed inset-0 z-40 md:hidden" onClick={(e)=>{ if (e.target===e.currentTarget) onClose?.(); }}>
          <div className="absolute inset-0 bg-black/40" />
          <div className="absolute right-0 top-0 bottom-0">{content}</div>
        </div>
      )}
      {/* Desktop side panel placeholder (render handled by parent layout) */}
    </>
  );
};

const RecipeCard = ({ item }) => {
  const rc = item?.recipe_content || {};
  const title = rc.title || 'Untitled';
  const rawImage = rc.image_url || rc.thumbnail_path;
  const image = asThumbSrc(rawImage);
  const [rating, setRating] = useState(0);
  const [likes, setLikes] = useState(0);
  const time = rc.prep_time || rc.cook_time || null;
  const servings = rc.servings || rc.portions || null;
  const badges = (()=>{
    // Use same tag extraction and coloring as elsewhere
    const keys = Array.from(getRecipeTagSet(item));
    const pretty = (k) => k === 'pescetarian' ? 'Pescetarian' : k.split('-').map(w=>w? (w[0].toUpperCase()+w.slice(1)) : w).join('-');
    return keys.map(pretty);
  })();

  // Fetch rating summary once per card
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/recipes/${item.id}/ratings`, { credentials: 'include' });
        if (res.ok) {
          const json = await res.json();
          if (!cancelled) setRating(Number(json?.data?.average || 0));
        }
      } catch {}
      try {
        // likes not implemented separately; fall back to rating_count if present on item
        if (!cancelled) setLikes(Number(item?.rating_count || 0));
      } catch {}
    })();
    return () => { cancelled = true; };
  }, [item.id]);
  return (
    <button
      type="button"
      onClick={() => window.dispatchEvent(new CustomEvent('profile:open-recipe', { detail: { id: item.id } }))}
      className="group text-left relative rounded-2xl overflow-hidden border border-transparent bg-white/80 dark:bg-neutral-900/80 shadow-sm hover:shadow-lg hover:-translate-y-[1px] hover:scale-[1.01] transition focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[#e87b35]"
      aria-label={`Open recipe ${title}`}
    >
      <div className="relative aspect-square bg-gray-100">
        {image ? (
          <img src={image} alt={title} className="h-full w-full object-cover object-center aspect-square" onError={(e)=>{ e.currentTarget.src='https://placehold.co/640x640?text=No+Image'; }} />
        ) : null}

        {/* Rating chip */}
        <div className="absolute top-1 left-1 bg-white/95 text-gray-900 text-[11px] px-1.5 py-0.5 rounded-md flex items-center gap-0.5 shadow ring-1 ring-black/10">
          <svg viewBox="0 0 24 24" width="12" height="12" fill="#facc15" aria-hidden="true"><path d="M12 17.27L18.18 21 16.54 13.97 22 9.24l-7.19-.62L12 2 9.19 8.62 2 9.24l5.46 4.73L5.82 21z"/></svg>
          <span>{Number(rating||0).toFixed(1)}</span>
        </div>
        {/* Likes chip */}
        <div className="absolute top-1 right-1 bg-white/95 text-gray-900 text-[11px] px-1.5 py-0.5 rounded-md flex items-center gap-0.5 shadow ring-1 ring-black/10">
          <svg viewBox="0 0 24 24" width="12" height="12" fill="#ef4444" aria-hidden="true"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>
          <span>{Number(likes||0)}</span>
        </div>

        {/* Badges removed on profile cards per spec */}

        {/* Lightened gradient overlay for readability */}
        <div className="absolute inset-x-0 bottom-0 pointer-events-none after:content-[''] after:absolute after:inset-x-0 after:bottom-0 after:h-12 after:bg-gradient-to-t after:from-black/30 after:to-transparent"></div>
      </div>

      {/* Title moved to white lower area */}
      {/* Fixed-height title block for symmetric cards */}
      <div className="px-2 py-1 h-[36px] sm:h-[40px]">
        <div className="text-[12px] sm:text-[13px] tracking-tight leading-snug line-clamp-2 font-semibold" title={title}>{title}</div>
      </div>

      {/* Secondary info (hover on desktop) */}
      <div className="hidden sm:flex items-center gap-3 text-xs text-gray-600 px-2 pb-1 pt-0 opacity-0 group-hover:opacity-100 transition min-h-[18px]">
        {servings && (
          <span className="inline-flex items-center gap-1" title="Servings">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor" aria-hidden="true"><path d="M16 14a4 4 0 1 1-8 0"/><path d="M12 14a5 5 0 1 0-5-5M12 14a5 5 0 1 1 5-5"/></svg>
            {servings}
          </span>
        )}
        {time && (
          <span className="inline-flex items-center gap-1" title="Time">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor" aria-hidden="true"><path d="M12 6v6l3 3"/><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10Z"/></svg>
            {time}
          </span>
        )}
      </div>
    </button>
  );
};

const RecipesGrid = ({ recipes, loading }) => {
  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
        {Array.from({length:10}).map((_,i)=>(<Skeleton key={i} className="h-56 rounded-2xl" />))}
      </div>
    );
  }
  if (!recipes || recipes.length === 0) {
    return (
      <div className="text-center py-16">
        <div className="mx-auto w-24 h-24 bg-gray-100 rounded-full mb-4" />
        <div className="text-gray-600 mb-2">No recipes yet</div>
        <Link to="/" className="text-[#e87b35] hover:underline">Explore recipes</Link>
      </div>
    );
  }
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
      {recipes.map(r => <RecipeCard key={r.id} item={r} />)}
    </div>
  );
};

const CollectionsGrid = ({ items, loading }) => {
  if (loading) {
    return <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">{Array.from({length:6}).map((_,i)=>(<Skeleton key={i} className="h-40 rounded-2xl" />))}</div>;
  }
  if (!items || items.length === 0) {
    return <div className="text-center py-12 text-gray-600">No collections yet</div>;
  }
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
      {items.map((c,i)=> {
        const cover = asThumbSrc(c.image_url);
        return (
        <div key={i} className="rounded-2xl bg-white shadow-sm border overflow-hidden">
          <div className="aspect-[4/3] bg-gray-100">
            {cover && (
              <img src={cover} alt={c.title || 'collection cover'} className="h-full w-full object-cover object-center aspect-square" onError={(e)=>{ e.currentTarget.style.display='none'; }} />
            )}
          </div>
          <div className="p-3">
            <div className="font-semibold">{c.title || 'Untitled'}</div>
            <div className="text-xs text-gray-500">{c.recipes_count || 0} recipes • {c.followers_count || 0} followers</div>
            <div className="mt-2"><Button variant="outline">Follow collection</Button></div>
          </div>
        </div>
      );})}
    </div>
  );
};

const ActivityFeed = ({ items, loading }) => {
  if (loading) {
    return <div className="space-y-3">{Array.from({length:6}).map((_,i)=>(<Skeleton key={i} className="h-20 rounded-2xl" />))}</div>;
  }
  if (!items || items.length === 0) return <div className="text-center py-12 text-gray-600">No activity yet</div>;
  return (
    <div className="space-y-3">
      {items.map((a,i)=> (
        <div key={i} className="rounded-2xl bg-white shadow-sm border p-4 flex items-start gap-3">
          <div className="w-9 h-9 rounded-full bg-gray-100 flex items-center justify-center">{a.icon || '•'}</div>
          <div>
            <div className="text-sm">{a.text}</div>
            <div className="text-xs text-gray-500">{a.time || '2d ago'}</div>
          </div>
        </div>
      ))}
    </div>
  );
};

const AboutPanel = ({ user }) => {
  const [expanded, setExpanded] = useState(false);
  const raw = user?.bio || 'No bio yet.'; // TODO: bind to existing profile field
  const short = raw.slice(0, 260);
  return (
    <div className="rounded-2xl bg-white shadow-sm border p-4">
      <div className="prose max-w-none">
        <p>{expanded ? raw : short}{raw.length > short.length && !expanded ? '…' : ''}</p>
      </div>
      {raw.length > short.length && (
        <button className="mt-2 text-[#e87b35] hover:underline" onClick={()=>setExpanded(v=>!v)}>{expanded ? 'Read less' : 'Read more'}</button>
      )}
      <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
        {/* Public fields (TODO: wire to user fields) */}
        <div><span className="text-gray-500">Location:</span> {user?.location || '—'}</div>
        <div><span className="text-gray-500">Member since:</span> {user?.created_at ? new Date(user.created_at).toLocaleDateString() : '—'}</div>
        <div className="flex items-center gap-2">
          <span className="text-gray-500">Social:</span>
          {/* TODO: real links */}
          <a href="#" className="text-[#e87b35] hover:underline" onClick={(e)=>e.preventDefault()}>Instagram</a>
          <a href="#" className="text-[#e87b35] hover:underline" onClick={(e)=>e.preventDefault()}>YouTube</a>
        </div>
      </div>
    </div>
  );
};

export default function ProfilePage() {
  const { username } = useParams();
  const { currentUser } = useOutletContext?.() || { currentUser: null };

  const [profileUser, setProfileUser] = useState(null);
  const [recipes, setRecipes] = useState([]);
  const [collections, setCollections] = useState([]);
  const [activity, setActivity] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingFollow, setLoadingFollow] = useState(false);
  const [tab, setTab] = useState('recipes');
  const [filters, setFilters] = useState({ tags: [] });
  const [sort, setSort] = useState('latest');
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);
  const [messageOpen, setMessageOpen] = useState(false);
  const [selectedRecipe, setSelectedRecipe] = useState(null);

  const isOwn = !!currentUser && (currentUser.username && String(currentUser.username).toLowerCase() === String(username).toLowerCase());
  const [following, setFollowing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        // Prefer backend endpoints if available
        const [uRes, rRes] = await Promise.all([
          fetch(`${API_BASE}/users/${encodeURIComponent(username)}`),
          fetch(`${API_BASE}/users/${encodeURIComponent(username)}/recipes?sort=${encodeURIComponent(sort)}`)
        ]);
        if (!uRes.ok) throw new Error('User not found');
        const u = await uRes.json();
        const rs = rRes.ok ? await rRes.json() : [];
        if (cancelled) return;
        setProfileUser(u);
        setFollowing(Boolean(u?.followed_by_me));
        setRecipes(rs);
        // Collections
        try {
          const cRes = await fetch(`${API_BASE}/users/${encodeURIComponent(username)}/collections`, { credentials: 'include' });
          if (cRes.ok) {
            const cols = await cRes.json();
            setCollections(Array.isArray(cols) ? cols : []);
          } else {
            setCollections([]);
          }
        } catch { setCollections([]); }
        // DEV-ONLY MOCK (remove)
        setActivity([{icon:'🧑‍🍳', text:'Published a new recipe', time:'2d ago'}]);
      } catch (e) {
        // TODO: show toast
        setProfileUser(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [username, sort]);

  // Listen for open-recipe requests from cards
  useEffect(() => {
    const handler = async (e) => {
      const id = e?.detail?.id;
      if (!id) return;
      try {
        const direct = await fetch(`${API_BASE}/recipes/${id}`, { credentials: 'include' });
        const r = direct.ok ? await direct.json() : null;
        if (r) setSelectedRecipe(r);
      } catch {}
    };
    window.addEventListener('profile:open-recipe', handler);
    return () => window.removeEventListener('profile:open-recipe', handler);
  }, []);

  const stats = useMemo(() => ({
    recipes: recipes?.length || 0,
    followers: profileUser?.followers_count || 0, // TODO: wire
    following: profileUser?.following_count || 0, // TODO: wire
    collections: collections?.length || 0,
    avgRating: recipes && recipes.length>0 ? (recipes.reduce((s,r)=>s+(r.rating_average||0),0)/recipes.length).toFixed(1) : null,
  }), [recipes, profileUser, collections]);

  const tags = useMemo(() => {
    // Aggregate diet/theme presets from recipes but hide internal action presets like "add-*" / "remove-*"
    const pretty = (k) => k.split('-').map(w => w ? (w[0].toUpperCase()+w.slice(1)) : w).join('-');
    const set = new Set();
    (recipes||[]).slice(0,200).forEach(r=>{
      const keys = Array.from(getRecipeTagSet(r));
      for (const k of keys) {
        set.add(k === 'pescetarian' ? 'Pescetarian' : pretty(k));
      }
    });
    return Array.from(set).slice(0,16);
  }, [recipes]);

  const onFollowToggle = async () => {
    try {
      setLoadingFollow(true);
      setFollowing(v=>!v); // optimistic
      await fetch(`${API_BASE}/users/${encodeURIComponent(username)}/follow`, { method:'POST', credentials:'include' });
      // Refresh counts
      try {
        const res = await fetch(`${API_BASE}/users/${encodeURIComponent(username)}`);
        if (res.ok) {
          const u = await res.json();
          setProfileUser(u);
        }
      } catch {}
    } finally {
      setLoadingFollow(false);
    }
  };

  const filteredRecipes = useMemo(() => {
    let list = recipes || [];
    if (filters.category) list = list.filter(_=>true); // TODO: real filter mapping
    if (filters.diet) list = list.filter(r=>{
      const rc = r.recipe_content||{}; const t = String(rc.title||'').toLowerCase();
      if (filters.diet==='Vegan') return /\bvegan\b/.test(t);
      if (filters.diet==='Vegetarian') return /\bvegetarian\b/.test(t);
      if (filters.diet==='Pescetarian') return /\bpesc(etarian)?\b/.test(t);
      return true;
    });
    if (filters.rating) list = list.filter(r => (r.rating_average||0) >= Number(filters.rating));
    if (filters.tags && filters.tags.length > 0) {
      list = list.filter(r => {
        const tagSet = getRecipeTagSet(r);
        return (filters.tags || []).every(t => tagSet.has(t));
      });
    }
    // Sort
    if (sort==='most_liked') list = [...list].sort((a,b)=>(b.likes||0)-(a.likes||0));
    return list;
  }, [recipes, filters, sort]);

  return (
    <div className="max-w-7xl mx-auto px-4 md:px-6 py-6 md:py-10">
      {/* Header */}
      {loading && !profileUser ? (
        <div className="space-y-4">
          <Skeleton className="h-28 w-28 rounded-full" />
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-16 w-full" />
        </div>
      ) : profileUser ? (
        <ProfileHeader
          profileUser={profileUser}
          isOwn={isOwn}
          stats={stats}
          tags={tags}
          onFollowToggle={onFollowToggle}
          following={following}
          loadingFollow={loadingFollow}
          onMessage={()=>setMessageOpen(true)}
        />
      ) : (
        <div className="text-center text-gray-600">User not found</div>
      )}

      {/* Sticky tabs */}
      <StickyTabs active={tab} onChange={setTab} />

      {/* Tabs content */}
      {tab === 'recipes' && (
        <div className="grid grid-cols-1 md:grid-cols-[16rem_1fr] gap-6 mt-6">
          {/* Desktop side filters */}
          <div className="hidden md:block sticky top-20 self-start">
            <div className="rounded-2xl bg-white shadow-sm border p-4">
              <div className="font-semibold mb-3">Filters</div>
              <RecipeFilters open={false} onClose={()=>{}} filters={filters} setFilters={setFilters} onApply={()=>{}} />
              {/* Inline subset controls */}
              <div className="space-y-3">
                <div>
                  <div className="text-sm text-gray-600 mb-1">Sort by</div>
                  <select value={sort} onChange={(e)=>setSort(e.target.value)} className="w-full border rounded-lg px-3 py-2">
                    <option value="latest">Newest</option>
                    <option value="most_liked">Most liked</option>
                  </select>
                </div>
                {/* Profile tags */}
                {!!(tags && tags.length) && (
                  <div>
                    <div className="text-sm text-gray-600 mb-2">Tags</div>
                    <div className="flex flex-wrap gap-2">
                      {tags.map((t,i)=> {
                        const norm = normalizeTag(t);
                        const selected = (filters.tags || []).includes(norm);
                        const base = getTagClass(t);
                        return (
                          <button
                            key={`${t}-${i}`}
                            onClick={()=> setFilters(f=>{ const cur = new Set(f.tags || []); if (cur.has(norm)) cur.delete(norm); else cur.add(norm); return { ...f, tags: Array.from(cur) }; })}
                            className={`inline-flex items-center px-2 py-1 rounded-full text-xs border ${selected ? 'bg-[#e87b35] text-white border-transparent' : base} cursor-pointer hover:opacity-90 transition-opacity hover:scale-105`}
                            aria-pressed={selected}
                          >
                                                                {t.toLowerCase() === 'vegan' && <i className="fa-solid fa-leaf mr-1"></i>}
                        {t.toLowerCase() === 'vegetarian' && <i className="fa-solid fa-carrot mr-1"></i>}
                        {t.toLowerCase() === 'zesty' && <i className="fa-solid fa-lemon mr-1"></i>}
                        {t.toLowerCase() === 'pescatarian' && <i className="fa-solid fa-fish mr-1"></i>}
                        {t.toLowerCase() === 'seafood' && <i className="fa-solid fa-shrimp mr-1"></i>}
                        {t.toLowerCase() === 'fastfood' && <i className="fa-solid fa-burger mr-1"></i>}
                            {t}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
          <div>
            <RecipesGrid recipes={filteredRecipes} loading={loading} />
          </div>
        </div>
      )}

      {tab === 'collections' && (
        <div className="mt-6">
          <CollectionsGrid items={collections} loading={loading} />
        </div>
      )}

      {tab === 'activity' && (
        <div className="mt-6">
          <ActivityFeed items={activity} loading={loading} />
        </div>
      )}

      {tab === 'about' && (
        <div className="mt-6">
          <AboutPanel user={profileUser} />
        </div>
      )}

      {/* Mobile FAB for filters */}
      {tab==='recipes' && (
        <button
          className="md:hidden fixed bottom-5 right-5 z-40 rounded-full bg-[#e87b35] text-white shadow-lg w-14 h-14 text-sm font-semibold"
          onClick={()=>setMobileFiltersOpen(true)}
          aria-label="Open filters"
        >
          Filter
        </button>
      )}
      <RecipeFilters open={mobileFiltersOpen} onClose={()=>setMobileFiltersOpen(false)} filters={filters} setFilters={setFilters} onApply={()=>{}} />

      {/* Mobile sticky action bar */}
      {!isOwn && profileUser && (
        <div className="md:hidden fixed bottom-0 left-0 right-0 z-30 bg-white/95 backdrop-blur border-t p-3 flex items-center justify-around">
          <Button onClick={onFollowToggle} disabled={loadingFollow} className="px-3">{following? 'Unfollow':'Follow'}</Button>
          <Button variant="outline" className="px-3" onClick={()=>setMessageOpen(true)}>Message</Button>
          <Button variant="ghost" className="px-3" onClick={()=>{ /* share inside */ navigator.clipboard.writeText(window.location.href); }}>{'Share'}</Button>
          <a href="#" className="text-sm text-gray-600" onClick={(e)=>{ e.preventDefault(); window.scrollTo({top:0, behavior:'smooth'}); }}>Top</a>
        </div>
      )}

      <MessageDrawer isOpen={messageOpen} onClose={()=>setMessageOpen(false)} profileUser={profileUser} onSend={()=>{/* TODO: toast success */}} />

      {/* Recipe modal (reuse existing RecipeView) */}
      {selectedRecipe && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={()=>setSelectedRecipe(null)}>
          <div className="bg-white rounded-2xl w-full max-w-[1080px] max-h-[90vh] overflow-auto" onClick={(e)=>e.stopPropagation()}>
            <div className="p-4">
              <RecipeView
                recipeId={selectedRecipe.id}
                recipe={selectedRecipe.recipe_content}
                variant="modal"
                isSaved={true}
                currentUser={currentUser}
                onOpenRecipeInModal={(id)=> navigate(`/recipes/${id}`)}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
