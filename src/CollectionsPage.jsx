import React, { useEffect, useState } from 'react';
import { XMarkIcon, UserGroupIcon, CalendarDaysIcon, BookOpenIcon, HeartIcon, StarIcon, PencilSquareIcon } from '@heroicons/react/24/outline';
import { useNavigate, Link, useParams, useLocation } from 'react-router-dom';
import RecipeView from './components/RecipeView';

const API_BASE = 'http://localhost:8001/api/v1';
const STATIC_BASE = 'http://localhost:8001';

const normalizeUrl = (url) => {
  if (!url || typeof url !== 'string') return null;
  let u = url;
  if (u.startsWith('http://127.0.0.1:8000')) u = u.replace('http://127.0.0.1:8000', STATIC_BASE);
  if (u.startsWith('http://localhost:8000')) u = u.replace('http://localhost:8000', STATIC_BASE);
  if (u.startsWith('/')) u = STATIC_BASE + u;
  return u;
};

export default function CollectionsPage() {
  const [collections, setCollections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [openId, setOpenId] = useState(null);
  const [recipes, setRecipes] = useState([]);
  const [selectedRecipe, setSelectedRecipe] = useState(null);
  const [openMeta, setOpenMeta] = useState(null);
  const [editMode, setEditMode] = useState(false);
  const [editImageUrl, setEditImageUrl] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [savingEdit, setSavingEdit] = useState(false);
  const [dragIndex, setDragIndex] = useState(null);
  const [dropIndex, setDropIndex] = useState(null);
  const [dropEdge, setDropEdge] = useState(null); // 'left' | 'right' | 'top' | 'bottom'
  const [sourceFrom, setSourceFrom] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ title: '', description: '', visibility: 'public', image_url: '' });
  const navigate = useNavigate();
  const location = useLocation();
  const quickModalRef = React.useRef(null);
  const closeBtnRef = React.useRef(null);
  const prevFocusRef = React.useRef(null);
  const { id: routeId } = useParams?.() || {};
  const [showFab, setShowFab] = useState(false);
  const sentinelRef = React.useRef(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/collections`, { credentials: 'include' });
        const data = await res.json();
        const list = Array.isArray(data) ? data : [];
        setCollections(list);
        // If on /collections/:id, load that collection detail page directly
        const activeId = routeId ? parseInt(routeId, 10) : null;
        if (activeId && !Number.isNaN(activeId)) {
          const r2 = await fetch(`${API_BASE}/collections/${activeId}/recipes`, { credentials: 'include' });
          const d2 = await r2.json();
          setRecipes(Array.isArray(d2) ? d2 : []);
          setOpenId(activeId);
          try { const m = list.find(x => String(x.id) === String(activeId)); if (m) setOpenMeta(m); } catch {}
        }
      } catch (e) {
        setError('Failed to load collections');
      } finally {
        setLoading(false);
      }
    })();
  }, [routeId]);

  // When leaving detail route back to overview, clear detail state so it doesn't render on overview
  useEffect(() => {
    if (!routeId) {
      setOpenId(null);
      setSelectedRecipe(null);
      setOpenMeta(null);
      setRecipes([]);
    }
  }, [routeId]);

  // Body scroll lock when modal is open
  useEffect(() => {
    const root = document.documentElement;
    if (showModal) root.classList.add('overflow-hidden');
    else root.classList.remove('overflow-hidden');
    return () => root.classList.remove('overflow-hidden');
  }, [showModal]);

  // Mobile FAB visibility with IntersectionObserver at top of detail view
  useEffect(() => {
    if (!routeId) { setShowFab(false); return; }
    const node = sentinelRef.current;
    if (!node) return;
    const io = new IntersectionObserver((entries) => {
      const e = entries[0];
      setShowFab(!e.isIntersecting);
    }, { root: null, threshold: 0 });
    io.observe(node);
    return () => io.disconnect();
  }, [routeId]);

  // Listen for cross-component requests to open a recipe in this modal (e.g., after saving a variant)
  useEffect(() => {
    const handler = (e) => {
      try {
        const d = e.detail || {};
        if (!d.id) return;
        openRecipeInModal(d.id, d.fromId ? { sourceRecipeId: d.fromId, sourceTitle: d.fromTitle } : {});
      } catch {}
    };
    window.addEventListener('collections:open-recipe', handler);
    return () => window.removeEventListener('collections:open-recipe', handler);
  }, [recipes]);

  const openCollection = async (id) => {
    navigate(`/collections/${id}`);
  };

  const openRecipeInModal = async (id, options = {}) => {
    try {
      // Try direct fetch by id first
      const direct = await fetch(`${API_BASE}/recipes/${id}`, { credentials: 'include' });
      let r = null;
      if (direct.ok) {
        r = await direct.json();
      } else {
        // Fallback to list scan of all recipes
        const listRes = await fetch(`${API_BASE}/recipes?scope=all`, { credentials: 'include' });
        const list = await listRes.json();
        r = (list || []).find(x => String(x.id) === String(id));
      }
      if (r) {
        setSelectedRecipe(r);
        if (options.clearSource) {
          setSourceFrom(null);
        } else if (options.sourceRecipeId) {
          setSourceFrom({ id: options.sourceRecipeId, title: options.sourceTitle || '' });
        }
      }
    } catch (e) {
      // noop
    }
  };

  const openQuickView = async (id) => {
    try {
      // Remember current focused element to restore on close
      prevFocusRef.current = typeof document !== 'undefined' ? document.activeElement : null;
      // Shallow history push to indicate quick modal is open
      const params = new URLSearchParams(location.search || '');
      if (!params.get('quick')) {
        params.set('quick', '1');
        navigate({ search: `?${params.toString()}` }, { replace: false, state: { fromCollection: true } });
      }
    } catch {}
    // Prefetch and open
    await openRecipeInModal(id);
    // Move focus to close button for a11y
    setTimeout(() => { try { closeBtnRef.current?.focus(); } catch {} }, 0);
  };

  const closeQuickView = () => {
    try {
      const params = new URLSearchParams(location.search || '');
      if (params.get('quick')) {
        // Go back one step in history to restore previous URL
        navigate(-1);
      }
    } catch {}
    setSelectedRecipe(null);
    setSourceFrom(null);
    // Restore focus to previously focused element
    try { prevFocusRef.current?.focus?.(); } catch {}
    prevFocusRef.current = null;
  };

  // Close quick view if URL loses ?quick=1 (e.g., browser Back)
  useEffect(() => {
    const params = new URLSearchParams(location.search || '');
    if (!params.get('quick') && selectedRecipe) {
      setSelectedRecipe(null);
      setSourceFrom(null);
    }
  }, [location.search]);

  // Body scroll lock and keyboard handlers while quick modal open
  useEffect(() => {
    if (!selectedRecipe) return;
    const root = document.documentElement;
    root.classList.add('overflow-hidden');
    const onKey = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        closeQuickView();
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
        const idx = (recipes || []).findIndex(x => String(x.id) === String(selectedRecipe.id));
        if (e.key === 'ArrowLeft' && idx > 0) {
          openQuickView(recipes[idx - 1].id);
        }
        if (e.key === 'ArrowRight' && idx >= 0 && idx < (recipes.length - 1)) {
          openQuickView(recipes[idx + 1].id);
        }
      } else if (e.key === 'Tab') {
        // Simple focus trap within modal
        try {
          const node = quickModalRef.current;
          if (!node) return;
          const focusables = node.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
          const list = Array.from(focusables).filter(el => !el.hasAttribute('disabled'));
          if (list.length === 0) return;
          const first = list[0];
          const last = list[list.length - 1];
          if (e.shiftKey) {
            if (document.activeElement === first) {
              e.preventDefault(); last.focus();
            }
          } else {
            if (document.activeElement === last) {
              e.preventDefault(); first.focus();
            }
          }
        } catch {}
      }
    };
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
      root.classList.remove('overflow-hidden');
    };
  }, [selectedRecipe, recipes]);

  const createCollection = async () => {
    const body = { ...form };
    try {
      const res = await fetch(`${API_BASE}/collections`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include', body: JSON.stringify(body) });
      const json = await res.json();
      if (json?.id) {
        const list = await (await fetch(`${API_BASE}/collections`, { credentials: 'include' })).json();
        setCollections(list);
        setShowModal(false);
        setForm({ title: '', description: '', visibility: 'public', image_url: '' });
      } else {
        alert(json.detail || 'Failed to create');
      }
    } catch (e) { alert('Failed to create'); }
  };

  if (loading) return <div>Loading…</div>;
  if (error) return <div className="text-red-500">{error}</div>;

  return (
    <div>
      {!routeId && (
        <>
          <div className="flex items-center justify-between mb-6">
            <h1 className="text-4xl font-bold text-gray-800">Collections</h1>
            <button className="bg-[#da8146] text-white px-4 py-2 rounded-lg" onClick={()=>setShowModal(true)}>+ New Collection</button>
          </div>
          {collections.length === 0 ? (
            <div className="text-gray-500">No collections yet</div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-3 gap-8">
              {collections.map(c => (
                <div
                  key={c.id}
                  className="relative rounded-2xl overflow-hidden cursor-pointer transition group"
                  onClick={() => openCollection(c.id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e)=>{ if(e.key==='Enter' || e.key===' '){ e.preventDefault(); openCollection(c.id);} }}
                >
                  <img
                    src={normalizeUrl(c.image_url) || 'https://placehold.co/800x600?text=Collection'}
                    alt={c.title}
                    className="w-full h-64 object-cover"
                    onError={(e)=>{ e.currentTarget.src = 'https://placehold.co/800x600?text=Collection'; }}
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/30 to-transparent" />
                  <button
                    onClick={async (e)=>{ e.stopPropagation(); try{ const r= await fetch(`${API_BASE}/collections/${c.id}/like`, { method:'POST', credentials:'include' }); const j = await r.json(); if(j.ok){ const list = await (await fetch(`${API_BASE}/collections`, { credentials:'include' })).json(); setCollections(list);} } catch{} }}
                    className={`absolute top-4 right-4 rounded-full px-3 py-1 text-sm font-semibold ${c.liked_by_me ? 'bg-red-600 text-white' : 'bg-white/90 text-gray-800'}`}
                    title={c.liked_by_me ? 'Unlike' : 'Like'}
                  >
                    <span className="inline-flex items-center gap-1">
                      <svg viewBox="0 0 24 24" width="14" height="14" fill="#ef4444"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41 0.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>
                      <span className="font-semibold">{c.likes_count || 0}</span>
                    </span>
                  </button>
                  <div className="absolute left-5 right-5 bottom-5 text-white">
                    <h3 className="text-2xl font-extrabold drop-shadow mb-1">{c.title}</h3>
                    <div className="text-sm opacity-95 mb-3">{c.recipes_count} recipes • {c.followers_count} followers</div>
                    <Link to={`/users/${encodeURIComponent(c.owner_username || (c.owner_name || '').split(' ')[0] || 'user')}`} className="flex items-center gap-3 group/owner" onClick={(e)=>e.stopPropagation()}>
                      <img src={normalizeUrl(c.owner_avatar) || 'https://placehold.co/48x48?text=%F0%9F%91%A4'} alt={c.owner_name || 'Owner'} className="h-9 w-9 rounded-full object-cover border-2 border-white/80 shadow-sm" onError={(e)=>{ e.currentTarget.src='https://placehold.co/48x48?text=%F0%9F%91%A4'; }} />
                      <div className="font-semibold drop-shadow underline-offset-2 group-hover/owner:underline">{c.owner_name || 'Unknown'}</div>
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {routeId && openId && (
        <div className="max-w-5xl mx-auto px-6 py-6">
          <div className="bg-white rounded-2xl w-full p-0 shadow-sm border border-gray-100 relative overflow-visible">
            {/* Top-right controls: desktop shows small Edit next to X; mobile keeps Edit below title */}
            <div className="absolute top-3 right-16 z-20 flex items-center gap-2">
              {!editMode && openMeta && (
                <button
                  className="hidden md:inline-flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-100"
                  onClick={()=>{ setEditMode(true); setEditImageUrl(openMeta?.image_url || ''); setEditDescription(openMeta?.description || ''); }}
                  title="Edit collection"
                >
                  <PencilSquareIcon aria-hidden="true" className="w-4 h-4" />
                  <span>Edit</span>
                </button>
              )}
              {editMode && openMeta && (
                <div className="hidden md:flex items-center gap-2">
                  <button disabled={savingEdit} className="px-3 py-1.5 text-sm rounded-lg bg-green-600 text-white hover:bg-green-700 disabled:opacity-60" onClick={async ()=>{
                    try {
                      setSavingEdit(true);
                      const body = {};
                      if (editDescription !== (openMeta?.description || '')) body.description = editDescription;
                      if (editImageUrl && editImageUrl !== (openMeta?.image_url || '')) body.image_url = editImageUrl;
                      if (Object.keys(body).length > 0) {
                        await fetch(`${API_BASE}/collections/${openMeta.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, credentials: 'include', body: JSON.stringify(body) });
                      }
                      const orderIds = (recipes||[]).map(r => r.id);
                      await fetch(`${API_BASE}/collections/${openMeta.id}/reorder`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include', body: JSON.stringify({ recipe_ids: orderIds }) });
                      const list = await (await fetch(`${API_BASE}/collections`, { credentials: 'include' })).json();
                      setCollections(list);
                      const updated = list.find(x=>String(x.id)===String(openMeta.id));
                      if (updated) setOpenMeta(updated);
                      setEditMode(false);
                    } catch (e) { alert('Failed to save changes'); }
                    finally { setSavingEdit(false); }
                  }}>Save</button>
                  <button className="px-3 py-1.5 text-sm rounded-lg bg-gray-100 text-gray-800 hover:bg-gray-200" onClick={()=>{ setEditMode(false); setEditImageUrl(''); setEditDescription(''); }}>Cancel</button>
                </div>
              )}
            </div>
            <div className="absolute top-3 right-4 z-20">
              <button className="h-9 w-9 rounded-full bg-gray-100 hover:bg-gray-200 text-gray-700 flex items-center justify-center" aria-label="Close" onClick={()=>{ setSelectedRecipe(null); setOpenId(null); navigate('/collections'); }}>
                <XMarkIcon className="w-5 h-5" />
              </button>
            </div>
            <div className="px-6 pt-6">
              {!selectedRecipe && (
                <div className="flex-1 pr-4">
                  <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2 mb-3 md:mb-4">
                    <h3 className="text-2xl font-bold">{openMeta?.title || 'Collection recipes'}</h3>
                    {!editMode && (
                      <button
                        className="inline-flex md:hidden items-center gap-2 px-3 py-1.5 text-sm rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-100 self-start md:self-auto"
                        onClick={()=>{ setEditMode(true); setEditImageUrl(openMeta?.image_url || ''); setEditDescription(openMeta?.description || ''); }}
                        title="Edit collection"
                      >
                        <PencilSquareIcon aria-hidden="true" className="w-4 h-4" />
                        <span>Edit</span>
                      </button>
                    )}
                    {editMode && (
                      <div className="flex md:hidden items-center gap-2 self-start md:self-auto">
                        <button disabled={savingEdit} className="px-3 py-1.5 text-sm rounded-lg bg-green-600 text-white hover:bg-green-700 disabled:opacity-60" onClick={async ()=>{
                          try {
                            setSavingEdit(true);
                            const body = {};
                            if (editDescription !== (openMeta?.description || '')) body.description = editDescription;
                            if (editImageUrl && editImageUrl !== (openMeta?.image_url || '')) body.image_url = editImageUrl;
                            if (Object.keys(body).length > 0) {
                              await fetch(`${API_BASE}/collections/${openMeta.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, credentials: 'include', body: JSON.stringify(body) });
                            }
                            const orderIds = (recipes||[]).map(r => r.id);
                            await fetch(`${API_BASE}/collections/${openMeta.id}/reorder`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include', body: JSON.stringify({ recipe_ids: orderIds }) });
                            const list = await (await fetch(`${API_BASE}/collections`, { credentials: 'include' })).json();
                            setCollections(list);
                            const updated = list.find(x=>String(x.id)===String(openMeta.id));
                            if (updated) setOpenMeta(updated);
                            setEditMode(false);
                          } catch (e) { alert('Failed to save changes'); }
                          finally { setSavingEdit(false); }
                        }}>Save</button>
                        <button className="px-3 py-1.5 text-sm rounded-lg bg-gray-100 text-gray-800 hover:bg-gray-200" onClick={()=>{ setEditMode(false); setEditImageUrl(''); setEditDescription(''); }}>Cancel</button>
                      </div>
                    )}
                  </div>
                  {openMeta && (
                    <>
                      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-3">
                        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-gray-600">
                          <Link to={`/users/${encodeURIComponent(openMeta?.owner_username || (openMeta?.owner_name || '').split(' ')[0] || 'user')}`} className="flex items-center gap-2 hover:underline underline-offset-2">
                            <img src={normalizeUrl(openMeta?.owner_avatar) || 'https://placehold.co/32x32?text=%F0%9F%91%A4'} alt={openMeta?.owner_name || 'Owner'} className="h-8 w-8 rounded-full object-cover" onError={(e)=>{ e.currentTarget.src='https://placehold.co/32x32?text=%F0%9F%91%A4'; }} />
                            <span>By <strong>{openMeta?.owner_name || 'Unknown'}</strong></span>
                          </Link>
                          {Number(openMeta?.recipes_count || 0) > 0 && (
                            <span className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-gray-100 text-gray-700">
                              <BookOpenIcon aria-hidden="true" className="w-4 h-4" />
                              <span>{openMeta.recipes_count} recipes</span>
                            </span>
                          )}
                          {Number(openMeta?.followers_count || 0) >= 0 && (
                            <span className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-gray-100 text-gray-700">
                              <UserGroupIcon aria-hidden="true" className="w-4 h-4" />
                              <span>{openMeta.followers_count} followers</span>
                            </span>
                          )}
                          {openMeta?.created_at && (
                            <span className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-gray-100 text-gray-700">
                              <CalendarDaysIcon aria-hidden="true" className="w-4 h-4" />
                              <span>{new Date(openMeta.created_at).toLocaleDateString()}</span>
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-3">
                          <button
                            onClick={async ()=>{ try{ const r= await fetch(`${API_BASE}/collections/${openMeta.id}/like`, { method:'POST', credentials:'include' }); const j= await r.json(); if(j.ok){ const list = await (await fetch(`${API_BASE}/collections`, { credentials:'include' })).json(); setCollections(list); const updated = list.find(x=>x.id===openMeta.id); if(updated) setOpenMeta(updated);} } catch{} }}
                            className={`px-3 py-1.5 rounded-full text-sm inline-flex items-center gap-1 ${openMeta.liked_by_me ? 'bg-[#cc7c2e] text-white' : 'bg-gray-100 text-gray-800'}`}
                            title={openMeta.liked_by_me ? 'Unlike' : 'Like'}
                          >
                            <HeartIcon aria-hidden="true" className="w-4 h-4" />
                            <span className="font-semibold">{openMeta.likes_count || 0}</span>
                          </button>
                          <button
                            onClick={async ()=>{ try{ const r= await fetch(`${API_BASE}/collections/${openMeta.id}/follow`, { method:'POST', credentials:'include' }); const j= await r.json(); if(j.ok){ const list = await (await fetch(`${API_BASE}/collections`, { credentials:'include' })).json(); setCollections(list); const updated = list.find(x=>x.id===openMeta.id); if(updated) setOpenMeta(updated);} } catch{} }}
                            className={`px-3 py-1.5 rounded-full text-sm ${openMeta.followed_by_me ? 'bg-gray-200 text-gray-800' : 'bg-[#5b8959] text-white'}`}
                          >{openMeta.followed_by_me ? 'Following' : 'Follow'}</button>
                        </div>
                      </div>
                      {openMeta?.description && (
                        <p className="text-gray-600 text-[15px] leading-relaxed mb-4 line-clamp-2">{openMeta.description}</p>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>
            {/* moved actions into header area above; sticky bar removed per new spec */}
            {/* Sentinel for mobile FAB visibility */}
            <div ref={sentinelRef} className="h-1 w-px" />

            {!selectedRecipe ? (
              <>
                {recipes.length === 0 ? (
                  <div className="text-gray-500">No recipes yet</div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 p-6 pt-4">
                    {recipes.map((r, idx) => (
                      !editMode ? (
                        <button
                          key={r.id}
                          type="button"
                          className="group relative rounded-2xl overflow-hidden bg-white shadow-sm hover:shadow-md hover:-translate-y-[1px] transition focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[#5b8959]"
                          onClick={()=> openQuickView(r.id)}
                          aria-label={`Open recipe ${r?.recipe_content?.title || ''}`}
                          title={r?.recipe_content?.title || ''}
                        >
                          <div className="relative aspect-[4/3]">
                            <img
                              src={normalizeUrl(r.recipe_content?.image_url) || 'https://placehold.co/800x600?text=No+Image'}
                              alt={r.recipe_content?.title}
                              className="h-full w-full object-cover object-center"
                              loading="lazy"
                              decoding="async"
                              onError={(e)=>{ e.currentTarget.src='https://placehold.co/800x600?text=No+Image'; }}
                            />
                            {/* Gradient overlay */}
                            <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-black/70 via-black/30 to-transparent" />
                            {/* Rating chip */}
                            <div className="absolute top-2 left-2 z-10 rounded-full bg-black/55 text-white text-[11px] px-1.5 py-0.5 flex items-center gap-1 drop-shadow">
                              <StarIcon className="w-3.5 h-3.5" />
                              <span>{Number(r?.rating_average || 0).toFixed(1)}</span>
                            </div>
                            {/* Likes chip */}
                            <div className="absolute top-2 right-2 z-10 rounded-full bg-black/55 text-white text-[11px] px-1.5 py-0.5 flex items-center gap-1 drop-shadow">
                              <HeartIcon className="w-3.5 h-3.5" />
                              <span>{Number(r?.rating_count || 0)}</span>
                            </div>
                            {/* Badges: max 1 +N */}
                            {Array.isArray(r?.tags?.approved) && r.tags.approved.length > 0 && (
                              <div className="absolute bottom-2 left-2 z-10 flex items-center gap-1">
                                {(() => { const vis = r.tags.approved.slice(0,1); const extra = Math.max(0, r.tags.approved.length - vis.length); return (
                                  <>
                                    {vis.map((t,i2)=> (
                                      <span key={i2} className="bg-black/35 backdrop-blur-sm text-white text-[10px] px-1.5 py-0.5 rounded">{t.keyword}</span>
                                    ))}
                                    {extra>0 && (<span className="bg-black/35 backdrop-blur-sm text-white text-[10px] px-1.5 py-0.5 rounded">+{extra}</span>)}
                                  </>
                                ); })()}
                              </div>
                            )}
                            {/* Title + meta in bottom area */}
                            <div className="absolute inset-x-0 bottom-0 z-10 p-3">
                              <div className="text-white font-semibold leading-snug line-clamp-2 text-left" title={r?.recipe_content?.title || ''}>
                                {r?.recipe_content?.title}
                              </div>
                              <div className="text-[11px] text-white/90 mt-1">
                                {(() => {
                                  const rc = r?.recipe_content || {};
                                  const time = rc.prep_time || rc.cook_time || rc.prep_time_minutes || rc.cook_time_minutes || null;
                                  const servings = rc.servings || rc.portions || rc.serves || null;
                                  const parts = [];
                                  if (time != null && String(time).trim() !== '') parts.push(String(time));
                                  if (servings != null && String(servings).trim() !== '') parts.push(`${servings} servings`);
                                  return parts.join(' • ');
                                })()}
                              </div>
                            </div>
                          </div>
                        </button>
                      ) : (
                        <div key={r.id}
                          className={`relative border border-gray-200 rounded-2xl overflow-hidden bg-white shadow-md hover:shadow-xl ${dragIndex===idx? 'ring-2 ring-amber-400' : ''} cursor-move transition`}
                          draggable
                          onDragStart={(e)=>{ setDragIndex(idx); try{ e.dataTransfer.effectAllowed='move'; e.dataTransfer.setData('text/plain', String(idx)); } catch{} }}
                          onDragOver={(e)=>{ 
                            e.preventDefault(); setDropIndex(idx); try{ e.dataTransfer.dropEffect='move'; } catch{}; 
                            const rect = e.currentTarget.getBoundingClientRect();
                            const x = e.clientX - rect.left; const y = e.clientY - rect.top;
                            const dLeft = x; const dRight = rect.width - x; const dTop = y; const dBottom = rect.height - y;
                            const min = Math.min(dLeft, dRight, dTop, dBottom);
                            let edge = 'right';
                            if (min === dLeft) edge = 'left'; else if (min === dRight) edge = 'right'; else if (min === dTop) edge = 'top'; else edge = 'bottom';
                            setDropEdge(edge);
                          }}
                          onDrop={(e)=>{ 
                            e.preventDefault(); const targetIdx = idx; const edge = dropEdge || 'right';
                            setRecipes(prev=>{ const list=[...prev]; const from=dragIndex; const remove=[...list]; const [m]=remove.splice(from,1);
                              let insert = (edge==='right' || edge==='bottom') ? targetIdx + 1 : targetIdx;
                              if (from < insert) insert -= 1; insert = Math.max(0, Math.min(insert, remove.length));
                              remove.splice(insert, 0, m); return remove; });
                            setDragIndex(null); setDropIndex(null); setDropEdge(null);
                          }}
                          onDragEnd={()=>{ setDragIndex(null); setDropIndex(null); setDropEdge(null); }}
                        >
                          <img src={normalizeUrl(r.recipe_content?.image_url) || 'https://placehold.co/800x600?text=No+Image'} alt={r.recipe_content?.title} className="w-full h-40 object-cover" />
                          <div className="absolute top-2 left-2 px-2 py-1 rounded bg-black/60 text-white text-xs font-semibold">{idx===0? 'Cover' : `#${idx+1}`}</div>
                          <button className="absolute top-2 right-2 bg-white/95 hover:bg-white text-gray-800 rounded-full w-8 h-8 flex items-center justify-center shadow-lg" title="Remove" onClick={(e)=>{ e.preventDefault(); e.stopPropagation(); setConfirmRemove({ id: r.id, title: r.recipe_content?.title }); }}>
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
                          </button>
                          {dropIndex===idx && dragIndex!==null && dropEdge && (
                            dropEdge==='left' || dropEdge==='right' ? (
                              <div className={`absolute inset-y-0 ${dropEdge==='left' ? 'left-0' : 'right-0'} w-[6px] bg-[#e87b35] shadow-[0_0_0_2px_rgba(0,0,0,0.08)]`} />
                            ) : (
                              <div className={`absolute inset-x-0 ${dropEdge==='top' ? 'top-0' : 'bottom-0'} h-[6px] bg-[#e87b35] shadow-[0_0_0_2px_rgba(0,0,0,0.08)]`} />
                            )
                          )}
                          <div className="p-4">
                            <div className="font-semibold mb-1">{r.recipe_content?.title}</div>
                            <div className="text-sm text-gray-600 line-clamp-2">{r.recipe_content?.description}</div>
                          </div>
                        </div>
                      )
                    ))}
                  </div>
                )}
              </>
            ) : (
              <div className="fixed inset-0 z-50 flex items-end md:items-center justify-center bg-black/50" onClick={closeQuickView} role="dialog" aria-modal="true">
                <div className="w-full md:max-w-[880px] bg-white rounded-t-2xl md:rounded-2xl shadow-xl max-h-[90vh] overflow-y-auto p-4 md:p-6" onClick={(e)=>e.stopPropagation()} ref={quickModalRef}>
                  <div className="flex items-center justify-between mb-3">
                    <button ref={closeBtnRef} className="h-9 w-9 rounded-full bg-gray-100 hover:bg-gray-200 text-gray-700 flex items-center justify-center focus:outline-none focus:ring-2 focus:ring-blue-500" aria-label="Close" onClick={closeQuickView}>
                      <XMarkIcon className="w-5 h-5" />
                    </button>
                    <button className="px-3 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700" onClick={()=>navigate(`/recipes/${selectedRecipe.id}`, { state: { fromCollection: true } })}>View full recipe</button>
                  </div>
                  <RecipeView
                    recipeId={selectedRecipe.id}
                    recipe={selectedRecipe.recipe_content}
                    variant="modal"
                    isSaved={false}
                    currentUser={selectedRecipe.user || null}
                    sourceFrom={sourceFrom}
                    onOpenRecipeInModal={(id, opts)=>openRecipeInModal(id, opts)}
                    onRequestCloseModal={closeQuickView}
                  />
                </div>
              </div>
            )}
            {!selectedRecipe && editMode && (
              <div className="mt-6 border-t pt-4">
                <h4 className="font-semibold mb-2">Collection settings</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-1">Description</label>
                    <textarea className="w-full border rounded-lg px-3 py-2" rows={4} value={editDescription} onChange={(e)=>setEditDescription(e.target.value)} placeholder="Describe this collection" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Custom cover image URL</label>
                    <input className="w-full border rounded-lg px-3 py-2" value={editImageUrl} onChange={(e)=>setEditImageUrl(e.target.value)} placeholder="Leave empty to use first recipe image" />
                    <p className="text-xs text-gray-500 mt-1">Tip: Drag a recipe to the first position to use its image as the cover.</p>
                  </div>
                </div>
              </div>
            )}
          </div>
          {/* Mobile floating action bar */}
          {openMeta && (
            <div className={`md:hidden fixed bottom-2 inset-x-4 z-40 transition-opacity ${showFab ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}>
              <div className="bg-white/90 backdrop-blur rounded-2xl shadow-lg border border-gray-200 p-2 flex items-center justify-center gap-3">
                <button
                  onClick={async ()=>{ try{ const r= await fetch(`${API_BASE}/collections/${openMeta.id}/follow`, { method:'POST', credentials:'include' }); const j= await r.json(); if(j.ok){ const list = await (await fetch(`${API_BASE}/collections`, { credentials:'include' })).json(); setCollections(list); const updated = list.find(x=>x.id===openMeta.id); if(updated) setOpenMeta(updated);} } catch{} }}
                  className={`px-3 py-2 rounded-lg text-sm ${openMeta.followed_by_me ? 'bg-gray-200 text-gray-800' : 'bg-blue-600 text-white'}`}
                >{openMeta.followed_by_me ? 'Following' : 'Follow'}</button>
                <button
                  onClick={()=>{ try { navigator.clipboard.writeText(window.location.href); } catch {} }}
                  className="px-3 py-2 rounded-lg text-sm bg-gray-100 text-gray-800"
                >Share</button>
              </div>
            </div>
          )}
        </div>
      )}

      {showModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={()=>setShowModal(false)}>
          <div className="bg-white rounded-2xl max-w-xl w-full p-6" onClick={(e)=>e.stopPropagation()}>
            <h3 className="text-2xl font-bold mb-4">Create Collection</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Title</label>
                <input className="w-full border rounded-lg px-3 py-2" value={form.title} onChange={(e)=>setForm({...form, title:e.target.value})} />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Description</label>
                <textarea className="w-full border rounded-lg px-3 py-2" value={form.description} onChange={(e)=>setForm({...form, description:e.target.value})} />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Visibility</label>
                <select className="w-full border rounded-lg px-3 py-2" value={form.visibility} onChange={(e)=>setForm({...form, visibility:e.target.value})}>
                  <option value="public">Public</option>
                  <option value="private">Private</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Image URL</label>
                <input className="w-full border rounded-lg px-3 py-2" value={form.image_url} onChange={(e)=>setForm({...form, image_url:e.target.value})} placeholder="Paste URL or leave empty" />
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button className="px-4 py-2 rounded-lg border" onClick={()=>setShowModal(false)}>Cancel</button>
              <button className="px-4 py-2 rounded-lg bg-green-600 text-white" onClick={createCollection}>Create</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


