import React, { useEffect, useState } from 'react';
import { XMarkIcon, UserGroupIcon, CalendarDaysIcon, BookOpenIcon, PencilSquareIcon } from '@heroicons/react/24/outline';
import { StarIcon, HeartIcon } from '@heroicons/react/24/solid';
import { useNavigate, Link, useParams, useLocation } from 'react-router-dom';
import RecipeView from './components/RecipeView';
import PageContainer from './components/PageContainer';
import CollectionCard from './components/CollectionCard';
import TagList from './components/TagList';

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

// RecipeCard component that fetches ratings from API
const RecipeCard = ({ recipe, onClick, isEditMode = false, dragIndex, dropIndex, dropEdge, onDragStart, onDragOver, onDrop, onDragEnd, onRemove, idx }) => {
  const [rating, setRating] = useState(0);
  const [likes, setLikes] = useState(recipe?.likes_count || 0);
  const [likedByMe, setLikedByMe] = useState(recipe?.liked_by_me || false);

  // Fetch rating summary once per card
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/recipes/${recipe.id}/ratings`, { credentials: 'include' });
        if (res.ok) {
          const json = await res.json();
          if (!cancelled) setRating(Number(json?.data?.average || 0));
        }
      } catch {}
      try {
        // likes are now fetched from recipe object
        if (!cancelled) {
          setLikes(Number(recipe?.likes_count || 0));
          setLikedByMe(Boolean(recipe?.liked_by_me || false));
        }
      } catch {}
    })();
    return () => { cancelled = true; };
  }, [recipe.id]);

  const handleLikeClick = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      const res = await fetch(`${API_BASE}/recipes/${recipe.id}/like`, { 
        method: 'POST', 
        credentials: 'include' 
      });
      const json = await res.json();
      if (json.ok) {
        setLikedByMe(json.data.liked);
        setLikes(prev => json.data.liked ? prev + 1 : Math.max(0, prev - 1));
      }
    } catch {}
  };

  if (isEditMode) {
    return (
      <div
        className={`relative border border-gray-200 rounded-2xl overflow-hidden bg-white shadow-[4px_4px_0_rgba(0,0,0,0.06)] hover:shadow-[6px_6px_0_rgba(0,0,0,0.08)] hover:-translate-y-0.5 transition-transform transition-shadow duration-200 ease-out ${dragIndex===idx? 'ring-2 ring-amber-400' : ''} cursor-move`}
        draggable
        onDragStart={onDragStart}
        onDragOver={onDragOver}
        onDrop={onDrop}
        onDragEnd={onDragEnd}
      >
        <img src={normalizeUrl(recipe.recipe_content?.image_url) || 'https://placehold.co/800x600?text=No+Image'} alt={recipe.recipe_content?.title} className="w-full h-full object-cover aspect-square" />
        <div className="absolute top-2 left-2 px-2 py-1 rounded bg-black/60 text-white text-xs font-semibold">{idx===0? 'Cover' : `#${idx+1}`}</div>
        <button className="absolute top-2 right-2 bg-white/95 hover:bg-white text-gray-800 rounded-full w-8 h-8 flex items-center justify-center shadow-lg opacity-90 hover:opacity-100 transition-opacity" title="Remove" onClick={onRemove}>
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
          <div className="font-semibold mb-1">{recipe.recipe_content?.title}</div>
          <div className="text-sm text-gray-600 line-clamp-2">{recipe.recipe_content?.description}</div>
        </div>
      </div>
    );
  }

  return (
    <div 
      className="group relative bg-white rounded-2xl border border-gray-200 shadow-[4px_4px_0_rgba(0,0,0,0.06)] hover:shadow-[6px_6px_0_rgba(0,0,0,0.08)] hover:-translate-y-0.5 transition-transform transition-shadow duration-200 ease-out overflow-hidden cursor-pointer flex flex-col" 
      onClick={onClick}
    >
      {/* Image with overlay */}
      <div className="relative w-full aspect-square">
        <img
          src={normalizeUrl(recipe.recipe_content?.image_url) || 'https://placehold.co/800x600?text=No+Image'}
          alt={recipe.recipe_content?.title}
          className="w-full h-full object-cover rounded-t-lg aspect-square"
          loading="lazy"
          decoding="async"
          onError={(e)=>{ e.currentTarget.src='https://placehold.co/800x600?text=No+Image'; }}
        />
        <div className="absolute inset-0 rounded-t-lg bg-gradient-to-t from-black/70 via-black/25 to-transparent" />
        {/* Rating chip */}
        <div className="absolute top-3 left-3">
          <div className="flex items-center bg-white/95 rounded-full px-2 py-0.5 text-xs shadow">
            <StarIcon className="w-3.5 h-3.5 text-yellow-400 mr-1" />
            <span className="text-gray-800 font-semibold">{rating && rating > 0 ? Number(rating || 0).toFixed(1) : '-'}</span>
          </div>
        </div>
        {/* Likes chip */}
        <button
          onClick={handleLikeClick}
          className="absolute top-3 right-3 z-10 rounded-full bg-white/95 text-gray-800 text-xs px-2 py-0.5 flex items-center gap-1 shadow hover:bg-white transition-colors opacity-90 hover:opacity-100"
          title={likedByMe ? 'Unlike' : 'Like'}
        >
          <HeartIcon className={`w-3.5 h-3.5 ${likedByMe ? 'text-red-500' : 'text-gray-600'}`} />
          <span className="font-semibold">{Number(likes || 0)}</span>
        </button>
        {/* Title + author in bottom area */}
        <div className="absolute bottom-3 left-4 right-4 flex items-end justify-between">
          <div>
            <h2 className="text-white text-lg font-extrabold drop-shadow-sm">{recipe?.recipe_content?.title}</h2>
            <p className="text-white/90 text-xs mt-2">
              By {recipe?.owner_username || 'Unknown'}
            </p>
          </div>
        </div>
      </div>
      {/* Bottom section with chips and description */}
      <div className="p-5">
        {/* Chips */}
        {Array.isArray(recipe?.tags?.approved) && recipe.tags.approved.length > 0 && (
          <div className="mb-2">
            <TagList 
              tags={recipe.tags.approved.map(t => ({ keyword: t.keyword }))}
              maxVisible={3}
            />
          </div>
        )}
        {/* Description */}
        <p className="text-sm text-gray-600 line-clamp-2">{recipe?.recipe_content?.description}</p>
      </div>
      {/* Metadata section */}
      <div className="px-5 pb-5 mt-auto">
        <div className="flex items-center justify-between text-xs pt-4 border-t border-gray-100">
          <span className="text-gray-400">Saved {new Date(recipe.created_at).toLocaleDateString()}</span>
          <button className="text-[#e87b35] font-medium hover:underline" onClick={(e)=>{ e.stopPropagation(); }}>
            + Add to Collection
          </button>
        </div>
      </div>
    </div>
  );
};

export default function CollectionsPage() {
  const [collections, setCollections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [openId, setOpenId] = useState(null);
  const [recipes, setRecipes] = useState([]);
  const [openMeta, setOpenMeta] = useState(null);
  const [editMode, setEditMode] = useState(false);
  const [editImageUrl, setEditImageUrl] = useState('');
  const [editDescription, setEditDescription] = useState('');
  // Inline edit like RecipeView
  const [edited, setEdited] = useState(null);
  const [activeEditField, setActiveEditField] = useState(null);
  const [savingEdit, setSavingEdit] = useState(false);
  const [dragIndex, setDragIndex] = useState(null);
  const [dropIndex, setDropIndex] = useState(null);
  const [dropEdge, setDropEdge] = useState(null); // 'left' | 'right' | 'top' | 'bottom'
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ title: '', description: '', visibility: 'public', image_url: '' });
  const navigate = useNavigate();
  const location = useLocation();
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
        
        // Check for open parameter in URL
        const searchParams = new URLSearchParams(location.search);
        const openParam = searchParams.get('open');
        
        // If on /collections/:id, load that collection detail page directly
        const activeId = routeId ? parseInt(routeId, 10) : null;
        if (activeId && !Number.isNaN(activeId)) {
          const r2 = await fetch(`${API_BASE}/collections/${activeId}/recipes`, { credentials: 'include' });
          const d2 = await r2.json();
          setRecipes(Array.isArray(d2) ? d2 : []);
          setOpenId(activeId);
          try { const m = list.find(x => String(x.id) === String(activeId)); if (m) setOpenMeta(m); } catch {}
        }
        // If open parameter is present, open that collection
        else if (openParam) {
          const openId = parseInt(openParam, 10);
          if (!Number.isNaN(openId)) {
            const r2 = await fetch(`${API_BASE}/collections/${openId}/recipes`, { credentials: 'include' });
            const d2 = await r2.json();
            setRecipes(Array.isArray(d2) ? d2 : []);
            setOpenId(openId);
            try { const m = list.find(x => String(x.id) === String(openId)); if (m) setOpenMeta(m); } catch {}
            // Clear the open parameter from URL
            navigate(`/collections?open=${openId}`, { replace: true });
          }
        }
      } catch (e) {
        setError('Failed to load collections');
      } finally {
        setLoading(false);
      }
    })();
  }, [routeId, location.search, navigate]);

// When leaving detail route back to overview, clear detail state so it doesn't render on overview
useEffect(() => {
  if (!routeId) {
    setOpenId(null);
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
    // Navigate directly to the recipe page instead of opening modal
    navigate(`/recipes/${id}`);
  };




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

  const handleKeyDown = (e, field) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      setActiveEditField(null);
    }
  };

  const handleSave = async () => {
    try {
      setSavingEdit(true);
      const body = {};
      if (edited && edited.description !== (openMeta?.description || '')) body.description = edited.description;
      if (edited && edited.title !== (openMeta?.title || '')) body.title = edited.title;
      if (edited && edited.image_url && edited.image_url !== (openMeta?.image_url || '')) body.image_url = edited.image_url;
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
      setEdited(null);
      setActiveEditField(null);
    } catch (e) { alert('Failed to save changes'); }
    finally { setSavingEdit(false); }
  };

  return (
    <div>
      {!routeId && (
        <>
          <PageContainer>
            <div className="flex items-center justify-between mb-6">
              <h1 className="text-4xl font-bold text-gray-800">Collections</h1>
              <button className="bg-[#da8146] text-white px-4 py-2 rounded-lg" onClick={()=>setShowModal(true)}>+ New Collection</button>
            </div>
            {collections.length === 0 ? (
              <div className="text-gray-500">No collections yet</div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-6">
                {collections.map(c => (
                  <CollectionCard
                    key={c.id}
                    id={c.id}
                    title={c.title}
                    image_url={normalizeUrl(c.image_url)}
                    recipes_count={c.recipes_count}
                    followers_count={c.followers_count}
                    creator_name={c.owner_name}
              creator_username={c.owner_username}
                    creator_avatar={normalizeUrl(c.owner_avatar)}
                    likes_count={c.likes_count || 0}
                    onClick={() => openCollection(c.id)}
                  />
                ))}
              </div>
            )}
          </PageContainer>
        </>
      )}

      {routeId && openId && (
        <>
          <div className="max-w-5xl mx-auto px-6 mb-0">
            <div className="mb-2 flex justify-between items-center">
              <button
                onClick={() => {
                  const s = location.state || {};
                  if (s.fromCollection) return navigate(-1);
                  if (s.fromMyRecipes) return navigate(-1);
                  return navigate('/collections');
                }}
                className="px-3 py-2 rounded-lg bg-gray-200 text-gray-700 hover:bg-gray-300 border border-gray-300"
              >Back</button>

              <div className="flex items-center gap-2">
                {!editMode && openMeta && (
                  <button
                    className="hidden md:inline-flex items-center px-5 py-2.5 text-sm rounded-lg bg-amber-500 text-white hover:bg-amber-600 font-semibold"
                    onClick={()=>{ setEditMode(true); setEditImageUrl(openMeta?.image_url || ''); setEditDescription(openMeta?.description || ''); setEdited({ title: openMeta?.title || '', description: openMeta?.description || '', image_url: openMeta?.image_url || '' }); }}
                    title="Edit collection"
                  >
                    <span>Edit Collection</span>
                  </button>
                )}
                {editMode && openMeta && (
                  <div className="hidden md:flex items-center gap-2">
                    <button disabled={savingEdit} className="px-5 py-2.5 text-sm rounded-lg bg-[#7ab87a] text-white hover:bg-[#659a63] disabled:opacity-60 font-semibold" onClick={handleSave}>Save</button>
                    <button className="px-3 py-2.5 text-sm rounded-lg bg-gray-500 text-white hover:bg-gray-600" onClick={()=>{ setEditMode(false); setEditImageUrl(''); setEditDescription(''); setEdited(null); setActiveEditField(null); }}>Cancel</button>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="max-w-5xl mx-auto px-6 pt-0 pb-6">
            <div className="bg-white rounded-2xl w-full p-0 shadow-sm border border-gray-100 relative overflow-visible">
              <div className="px-6 pt-6">
                {(
                  <div className="flex-1 pr-4">
                    <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2 mb-3 md:mb-4">
                      <h3 className="text-2xl font-bold">
                        {editMode && activeEditField === 'title' ? (
                          <div data-edit-field="title">
                            <input
                              value={edited?.title || ''}
                              onChange={(e)=>setEdited(v=>({...(v||{}), title: e.target.value}))}
                              className="text-2xl font-bold border-b-2 border-amber-300 focus:outline-none focus:border-amber-500 px-1"
                              placeholder="Title"
                              onBlur={() => setActiveEditField(null)}
                              onKeyDown={(e) => handleKeyDown(e, 'title')}
                            />
                          </div>
                        ) : (
                          <span className={editMode ? 'cursor-pointer hover:bg-yellow-50 rounded px-1 transition-colors' : ''} onClick={editMode ? () => { if (!edited) setEdited({ title: openMeta?.title || '', description: openMeta?.description || '', image_url: openMeta?.image_url || '' }); setActiveEditField('title'); } : undefined}>
                            {edited?.title || openMeta?.title || 'Collection recipes'}
                          </span>
                        )}
                      </h3>
                      {!editMode && (
                        <button
                          className="inline-flex md:hidden items-center px-5 py-2.5 text-sm rounded-lg bg-amber-500 text-white hover:bg-amber-600 font-semibold self-start md:self-auto"
                          onClick={()=>{ setEditMode(true); setEditImageUrl(openMeta?.image_url || ''); setEditDescription(openMeta?.description || ''); }}
                          title="Edit collection"
                        >
                          <span>Edit Collection</span>
                        </button>
                      )}
                      {editMode && (
                        <div className="flex md:hidden items-center gap-2 self-start md:self-auto">
                          <button disabled={savingEdit} className="px-5 py-2.5 text-sm rounded-lg bg-[#7ab87a] text-white hover:bg-[#659a63] disabled:opacity-60 font-semibold" onClick={handleSave}>Save</button>
                          <button className="px-3 py-2.5 text-sm rounded-lg bg-gray-500 text-white hover:bg-gray-600" onClick={()=>{ setEditMode(false); setEditImageUrl(''); setEditDescription(''); }}>Cancel</button>
                        </div>
                      )}
                    </div>
                    {openMeta && (
                      <>
                        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-3">
                          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-gray-600">
                                            <Link to={`/users/${encodeURIComponent(openMeta?.owner_username || 'user')}`} className="flex items-center gap-2 hover:underline underline-offset-2">
                  <img src={normalizeUrl(openMeta?.owner_avatar) || 'https://placehold.co/32x32?text=%F0%9F%91%A4'} alt={openMeta?.owner_username || 'Owner'} className="h-8 w-8 rounded-full object-cover" onError={(e)=>{ e.currentTarget.src='https://placehold.co/32x32?text=%F0%9F%91%A4'; }} />
                  <span>By <strong>{openMeta?.owner_username || 'Unknown'}</strong></span>
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
                          editMode && activeEditField === 'description' ? (
                            <div data-edit-field="description">
                              <textarea
                                value={edited?.description || ''}
                                onChange={(e)=>setEdited(v=>({...(v||{}), description: e.target.value}))}
                                className="w-full border rounded-lg px-4 py-3 text-base leading-relaxed min-h-[100px] resize-y ring-amber-200 focus:ring-2"
                                rows={4}
                                placeholder="Description"
                                onBlur={() => setActiveEditField(null)}
                              />
                            </div>
                          ) : (
                            <p className={`text-gray-600 text-[15px] leading-relaxed mb-4 line-clamp-2 ${editMode ? 'cursor-pointer hover:bg-yellow-50 rounded-lg p-2 transition-colors' : ''}`} onClick={editMode ? () => { if (!edited) setEdited({ title: openMeta?.title || '', description: openMeta?.description || '', image_url: openMeta?.image_url || '' }); setActiveEditField('description'); } : undefined}>
                              {edited?.description || openMeta.description}
                            </p>
                          )
                        )}
                      </>
                    )}
                  </div>
                )}
              </div>
              {/* moved actions into header area above; sticky bar removed per new spec */}
              {/* Sentinel for mobile FAB visibility */}
              <div ref={sentinelRef} className="h-1 w-px" />

              {(
                <>
                  {recipes.length === 0 ? (
                    <div className="text-gray-500">No recipes yet</div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 p-6 pt-4">
                      {recipes.map((r, idx) => (
                        !editMode ? (
                          <RecipeCard
                            key={r.id}
                            recipe={r}
                            onClick={() => navigate(`/recipes/${r.id}`)}
                          />
                        ) : (
                          <RecipeCard
                            key={r.id}
                            recipe={r}
                            isEditMode={true}
                            idx={idx}
                            dragIndex={dragIndex}
                            dropIndex={dropIndex}
                            dropEdge={dropEdge}
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
                            onRemove={(e)=>{ e.preventDefault(); e.stopPropagation(); setConfirmRemove({ id: r.id, title: r.recipe_content?.title }); }}
                          />
                        )
                      ))}
                    </div>
                  )}
                </>
              )}
              {editMode && (
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
                <div className="bg-white/90 backdrop-blur rounded-2xl shadow-[4px_4px_0_rgba(0,0,0,0.06)] hover:shadow-[6px_6px_0_rgba(0,0,0,0.08)] hover:-translate-y-0.5 transition-transform transition-shadow duration-200 ease-out border border-gray-200 p-2 flex items-center justify-center gap-3">
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
        </>
      )}

      {showModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={()=>setShowModal(false)}>
          <div className="bg-white rounded-2xl border border-gray-200 shadow-[4px_4px_0_rgba(0,0,0,0.06)] hover:shadow-[6px_6px_0_rgba(0,0,0,0.08)] hover:-translate-y-0.5 transition-transform transition-shadow duration-200 ease-out max-w-xl w-full p-6" onClick={(e)=>e.stopPropagation()}>
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


