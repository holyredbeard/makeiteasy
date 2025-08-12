import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import RecipeView from './components/RecipeView';

const API_BASE = 'http://localhost:8001/api/v1';

export default function RecipePage() {
  const { id } = useParams();
  const [recipe, setRecipe] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(`${API_BASE}/recipes`, { credentials: 'include' });
        const list = await res.json();
        const r = (list || []).find(x => String(x.id) === String(id));
        setRecipe(r || null);
      } catch (e) {
        setError('Failed to load recipe');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id]);

  if (loading) return <div className="p-8 text-center">Loading…</div>;
  if (error || !recipe) return <div className="p-8 text-center text-red-600">{error || 'Recipe not found'}</div>;

  return (
    <div className="max-w-4xl mx-auto p-4 md:p-8">
      <RecipeView recipeId={recipe.id} recipe={recipe.recipe_content} variant="page" isSaved={true} currentUser={recipe.user || null} />
    </div>
  );
}


