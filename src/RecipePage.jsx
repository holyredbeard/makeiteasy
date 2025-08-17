import React, { useEffect, useState } from 'react';
import { useParams, useLocation, useNavigate } from 'react-router-dom';
import RecipeView from './components/RecipeView';

const API_BASE = 'http://localhost:8001/api/v1';
const STATIC_BASE = 'http://localhost:8001';
const SITE_NAME = 'Food2Guide';
const TW_SITE = '@Food2Guide';
const TW_CREATOR = '@Food2Guide';

export default function RecipePage() {
  const { id } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [recipe, setRecipe] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const load = async () => {
      try {
        // Try direct fetch by id first (fixes navigation from Collections modal)
        const direct = await fetch(`${API_BASE}/recipes/${id}`, { credentials: 'include' });
        if (direct.ok) {
          const r = await direct.json();
          setRecipe(r || null);
          return;
        }
        // Fallback to list scan
        const res = await fetch(`${API_BASE}/recipes?scope=all`, { credentials: 'include' });
        const list = await res.json();
        const params = new URLSearchParams(location.search);
        const variantId = params.get('variant');
        const targetId = variantId || id;
        let r = (list || []).find(x => String(x.id) === String(targetId));
        if (!r && variantId) {
          r = (list || []).find(x => String(x.id) === String(id));
        }
        setRecipe(r || null);
      } catch (e) {
        setError('Failed to load recipe');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id, location.search]);

  // SEO: page title + Recipe JSON-LD (must be declared before any early returns to keep hook order stable)
  useEffect(() => {
    try {
      const content = recipe?.recipe_content || {};
      const title = content.title || 'Recipe';
      if (typeof document !== 'undefined') document.title = `${title} – Food2Guide`;
      const img = content.image_url || content.thumbnail_path || content.img || '';
      const absImage = img ? (String(img).startsWith('http') ? img : `${STATIC_BASE}${img}`) : undefined;
      const ingredients = Array.isArray(content.ingredients) ? content.ingredients.map((i)=>{
        if (typeof i === 'string') return i;
        const qty = i?.quantity ? String(i.quantity) + ' ' : '';
        const name = i?.name ? String(i.name) : '';
        const notes = i?.notes ? ` (${i.notes})` : '';
        return (qty + name + notes).trim();
      }) : [];
      const instructions = Array.isArray(content.instructions) ? content.instructions.map((s)=>({
        '@type': 'HowToStep',
        text: typeof s === 'string' ? s : (s?.description || '')
      })) : [];
      const jsonLd = {
        '@context': 'https://schema.org',
        '@type': 'Recipe',
        name: title,
        description: content.description || undefined,
        image: absImage ? [absImage] : undefined,
        recipeIngredient: ingredients.length ? ingredients : undefined,
        recipeInstructions: instructions.length ? instructions : undefined,
        url: typeof window !== 'undefined' ? window.location.href : undefined,
        author: recipe?.user?.username || recipe?.user?.displayName ? { '@type': 'Person', name: recipe.user.username || recipe.user.displayName } : undefined,
      };
      // Insert/replace script tag
      const id = 'recipe-jsonld';
      const prev = document.getElementById(id);
      if (prev && prev.parentNode) prev.parentNode.removeChild(prev);
      const script = document.createElement('script');
      script.type = 'application/ld+json';
      script.id = id;
      script.text = JSON.stringify(jsonLd, null, 2);
      document.head.appendChild(script);

      // Open Graph / Twitter meta
      const upsertMeta = (id, attrName, attrValue, contentValue) => {
        let tag = document.getElementById(id);
        if (!tag) {
          tag = document.createElement('meta');
          tag.id = id;
          tag.setAttribute(attrName, attrValue);
          document.head.appendChild(tag);
        }
        tag.setAttribute('content', contentValue || '');
        return tag;
      };
      const metaIds = [];
      const desc = (content.description || '').toString();
      const url = typeof window !== 'undefined' ? window.location.href : '';
      const card = absImage ? 'summary_large_image' : 'summary';
      // OG
      metaIds.push('og-title'); upsertMeta('og-title', 'property', 'og:title', title);
      metaIds.push('og-desc'); upsertMeta('og-desc', 'property', 'og:description', desc);
      metaIds.push('og-type'); upsertMeta('og-type', 'property', 'og:type', 'article');
      metaIds.push('og-url'); upsertMeta('og-url', 'property', 'og:url', url);
      metaIds.push('og-site'); upsertMeta('og-site', 'property', 'og:site_name', SITE_NAME);
      if (absImage) { metaIds.push('og-image'); upsertMeta('og-image', 'property', 'og:image', absImage); }
      // Twitter
      metaIds.push('tw-card'); upsertMeta('tw-card', 'name', 'twitter:card', card);
      metaIds.push('tw-title'); upsertMeta('tw-title', 'name', 'twitter:title', title);
      metaIds.push('tw-desc'); upsertMeta('tw-desc', 'name', 'twitter:description', desc);
      metaIds.push('tw-site'); upsertMeta('tw-site', 'name', 'twitter:site', TW_SITE);
      metaIds.push('tw-creator'); upsertMeta('tw-creator', 'name', 'twitter:creator', TW_CREATOR);
      if (absImage) { metaIds.push('tw-image'); upsertMeta('tw-image', 'name', 'twitter:image', absImage); }

      return () => {
        try {
          const el = document.getElementById(id);
          if (el && el.parentNode) el.parentNode.removeChild(el);
        } catch {}
        try {
          metaIds.forEach((mid) => { const m = document.getElementById(mid); if (m && m.parentNode) m.parentNode.removeChild(m); });
        } catch {}
      };
    } catch {}
  }, [recipe?.id]);

  if (loading) return <div className="p-8 text-center">Loading…</div>;
  if (error || !recipe) return <div className="p-8 text-center text-red-600">{error || 'Recipe not found'}</div>;

  return (
    <div className="min-h-screen py-1 md:py-2">
      <div className="max-w-3xl lg:max-w-4xl mx-auto px-4">
        <div className="mb-2 flex justify-between items-center">
          <button
            onClick={() => {
              const s = location.state || {};
              if (s.fromCollection) return navigate(-1);
              if (s.fromMyRecipes) return navigate(-1);
              // Default fallback
              return navigate('/collections');
            }}
            className="px-3 py-2 rounded-lg bg-gray-200 text-gray-700 hover:bg-gray-300 border border-gray-300"
          >Back</button>
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                // This will trigger the edit function in RecipeView
                const editButton = document.querySelector('[data-save-button]');
                if (editButton) editButton.click();
              }}
              className="px-5 py-2.5 rounded-lg bg-yellow-500 text-white hover:bg-yellow-600 font-semibold flex items-center justify-center text-sm"
              id="top-edit-button"
            >
              Edit Recipe
            </button>
            <button
              onClick={() => {
                // This will trigger the save function in RecipeView
                const saveButton = document.querySelector('[data-save-button]');
                if (saveButton) saveButton.click();
              }}
              className="px-5 py-2.5 rounded-lg bg-[#7ab87a] text-white hover:bg-[#659a63] font-semibold hidden flex items-center justify-center text-sm"
              id="top-save-button"
            >
              Save
            </button>
            <button
              onClick={() => {
                // This will trigger the cancel function in RecipeView
                const cancelButton = document.querySelector('[data-cancel-button]');
                if (cancelButton) cancelButton.click();
              }}
              className="px-5 py-2.5 rounded-lg bg-gray-500 text-white hover:bg-gray-600 font-semibold hidden flex items-center justify-center text-sm"
              id="top-cancel-button"
            >
              Cancel
            </button>
          </div>
        </div>
        <div className="bg-white rounded-2xl shadow px-5 md:px-6 lg:px-8 py-6 md:py-8">
          <RecipeView 
            recipeId={recipe.id} 
            recipe={recipe.recipe_content} 
            variant="page" 
            isSaved={true} 
            currentUser={recipe.user || null}
            onEditStateChange={(isEditing) => {
              const topSaveButton = document.getElementById('top-save-button');
              const topEditButton = document.getElementById('top-edit-button');
              const topCancelButton = document.getElementById('top-cancel-button');
              if (topSaveButton) {
                topSaveButton.classList.toggle('hidden', !isEditing);
              }
              if (topEditButton) {
                topEditButton.classList.toggle('hidden', isEditing);
              }
              if (topCancelButton) {
                topCancelButton.classList.toggle('hidden', !isEditing);
              }
            }}
          />
        </div>
      </div>
    </div>
  );
}


