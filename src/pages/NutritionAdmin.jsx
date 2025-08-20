import React, { useEffect, useState, useMemo } from 'react';

const API = 'http://localhost:8000/api/v1';

export default function NutritionAdmin(){
  const [summary, setSummary] = useState({ ready: 0, pending: 0, error: 0, lastRun: null });
  const [rows, setRows] = useState([]);
  const [status, setStatus] = useState('');
  const [query, setQuery] = useState('');

  const fetchAll = async () => {
    try {
      const s = await fetch(`${API}/nutrition/admin/summary`).then(r=>r.json());
      setSummary(s || {});
      const l = await fetch(`${API}/nutrition/admin/list?status=${status}&q=${encodeURIComponent(query)}`).then(r=>r.json());
      setRows(Array.isArray(l) ? l : []);
    } catch {}
  };

  useEffect(()=>{
    fetchAll();
    const id = setInterval(fetchAll, 5000);
    return ()=>clearInterval(id);
  },[status, query]);

  const recomputeAllErrors = async () => {
    try {
      await fetch(`${API}/nutrition/admin/recompute-errors`, { method: 'POST' });
      fetchAll();
    } catch {}
  };

  const recomputeOne = async (id) => {
    try { await fetch(`${API}/nutrition/${id}/recompute`, { method: 'POST' }); fetchAll(); } catch {}
  };

  const viewMeta = async (id) => {
    try {
      const data = await fetch(`${API}/nutrition/${id}/meta`).then(r=>r.json());
      alert(JSON.stringify(data, null, 2));
    } catch {}
  };

  return (
    <div className="p-4">
      <h1 className="text-xl font-semibold mb-4">Nutrition Jobs</h1>
      <div className="flex items-center gap-4 mb-4">
        <div className="px-3 py-2 rounded bg-green-50 border border-green-200">READY {summary.ready||0}</div>
        <div className="px-3 py-2 rounded bg-yellow-50 border border-yellow-200">PENDING {summary.pending||0}</div>
        <div className="px-3 py-2 rounded bg-red-50 border border-red-200">ERROR {summary.error||0}</div>
        <button className="ml-auto px-3 py-2 border rounded" onClick={recomputeAllErrors}>Beräkna alla fel</button>
      </div>

      <div className="flex items-center gap-2 mb-3">
        <select value={status} onChange={e=>setStatus(e.target.value)} className="border rounded px-2 py-1">
          <option value="">Alla</option>
          <option value="ready">READY</option>
          <option value="pending">PENDING</option>
          <option value="error">ERROR</option>
        </select>
        <input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Filter" className="border rounded px-2 py-1 flex-1"/>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b">
              <th className="text-left p-2">Recipe ID</th>
              <th className="text-left p-2">Title</th>
              <th className="text-left p-2">Status</th>
              <th className="text-left p-2">Updated</th>
              <th className="text-left p-2">Anomaly</th>
              <th className="text-left p-2">Skipped</th>
              <th className="text-left p-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.id} className="border-b hover:bg-gray-50">
                <td className="p-2">{r.id}</td>
                <td className="p-2">{r.title || '-'}</td>
                <td className="p-2">{r.status}</td>
                <td className="p-2">{r.updated_at || '-'}</td>
                <td className="p-2">{r.anomaly || 0}</td>
                <td className="p-2">{(r.skipped_count||0)}</td>
                <td className="p-2 flex gap-2">
                  <button className="px-2 py-1 border rounded" onClick={()=>recomputeOne(r.id)}>Beräkna igen</button>
                  <a className="px-2 py-1 border rounded" href={`/recipes/${r.id}`} target="_blank" rel="noreferrer">Open</a>
                  <button className="px-2 py-1 border rounded" onClick={()=>viewMeta(r.id)}>View snapshot meta</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}




