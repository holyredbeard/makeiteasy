import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

const API_BASE = 'http://localhost:8001/api/v1';

function Chip({ label }) {
  return <span className="px-2 py-0.5 rounded-full text-xs bg-emerald-50 text-emerald-700 border border-emerald-200">{label}</span>;
}

export default function VariantsList({ parentId, onOpenRecipeInModal }) {
  const [items, setItems] = useState([]);
  const navigate = useNavigate();
  const [sort, setSort] = useState('newest'); // 'popular' | 'closest'
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [limit, setLimit] = useState(12);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const userPresets = []; // TODO: hook up to user filters if available
  const presetParam = userPresets.join(',');

  const fetchPage = async (p = page, s = sort) => {
    try {
      setLoading(true); setError('');
      const url = new URL(`${API_BASE}/recipes/${parentId}/variants`);
      url.searchParams.set('page', String(p));
      url.searchParams.set('limit', String(limit));
      url.searchParams.set('sort', s === 'closest' && presetParam ? 'closest' : s);
      if (presetParam) url.searchParams.set('presets', presetParam);
      const res = await fetch(url.toString(), { credentials: 'include' });
      const json = await res.json();
      if (!res.ok || !json.ok) throw new Error(json?.detail || 'Failed to load variants');
      setItems(json.data.items || []);
      setTotal(json.data.total || 0);
      setLimit(json.data.limit || 12);
      setPage(json.data.page || 1);
    } catch (e) {
      setError(String(e.message || e));
    } finally { setLoading(false); }
  };

  useEffect(() => { fetchPage(1, sort); /* eslint-disable-next-line */ }, [parentId, sort]);

  if (loading && items.length === 0) return (
    <div className="my-8">
      <h3 className="text-2xl font-bold text-gray-900 mb-4">Variants</h3>
      <div className="text-gray-500">Loading…</div>
    </div>
  );
  if (error) return null;
  if (!items || items.length === 0) return null;

  const totalPages = Math.max(1, Math.ceil(total / limit));

  return (
    <div className="my-8">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-2xl font-bold text-gray-900">Variants</h3>
        <select value={sort} onChange={(e)=>setSort(e.target.value)} className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm">
          <option value="popular">Most popular</option>
          <option value="newest">Newest</option>
          <option value="closest">Closest to your filters</option>
        </select>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {items.map(v => (
          <button
            key={v.id}
            className="text-left border border-gray-200 rounded-lg p-4 bg-white shadow-sm hover:shadow-md transition-shadow"
            onClick={(e)=>{
              e.preventDefault();
              if (typeof onOpenRecipeInModal === 'function') {
                onOpenRecipeInModal(v.id);
              } else {
                navigate(`/recipes/${v.id}`);
              }
            }}
          >
            <div className="flex items-center justify-between">
              <h4 className="font-semibold text-gray-900 truncate mr-3">{v.title}</h4>
              {v.ratingCount > 0 && (
                <div className="flex items-center gap-1 text-gray-700 text-sm">
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="#facc15" aria-hidden="true"><path d="M12 17.27L18.18 21 16.54 13.97 22 9.24l-7.19-.62L12 2 9.19 8.62 2 9.24l5.46 4.73L5.82 21z"/></svg>
                  <span>{Number(v.ratingAverage || 0).toFixed(1)}</span>
                </div>
              )}
            </div>
            <div className="mt-1 flex flex-wrap gap-2 text-xs">
              {((v.constraints || {}).presets || []).slice(0,4).map(k => (<Chip key={k} label={k} />))}
            </div>
            <div className="mt-2 text-xs text-gray-500 flex items-center gap-2">
              <span>By {v.owner?.username || v.owner?.displayName || 'Unknown'}</span>
              <span>•</span>
              <span>{new Date(v.createdAt).toLocaleDateString()}</span>
            </div>
          </button>
        ))}
      </div>
      {totalPages > 1 && (
        <div className="mt-4 flex items-center justify-center gap-2">
          <button className="px-3 py-1.5 border rounded-lg text-sm" disabled={page<=1} onClick={()=>fetchPage(page-1, sort)}>Prev</button>
          <span className="text-sm text-gray-600">Page {page} / {totalPages}</span>
          <button className="px-3 py-1.5 border rounded-lg text-sm" disabled={page>=totalPages} onClick={()=>fetchPage(page+1, sort)}>Next</button>
        </div>
      )}
    </div>
  );
}


