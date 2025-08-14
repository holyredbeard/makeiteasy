import React, { useMemo, useState } from 'react';

const SUGGESTIONS = [
  'pasta','soup','salad','stirfry','baked','grilled','fried','breakfast','lunch','dinner','dessert',
  'italian','mexican','indian','thai','japanese','swedish','vegan','vegetarian','glutenfree','dairyfree',
  'quick','easy','healthy','highprotein','lowcarb'
];

export default function TagInput({ tags, setTags, placeholder = 'Add a tag...', required = false, onValidityChange }) {
  const [input, setInput] = useState('');
  const [open, setOpen] = useState(false);
  const normalized = useMemo(()=>String(input).trim().toLowerCase(), [input]);
  const matches = useMemo(()=>{
    if (!normalized) return [];
    return SUGGESTIONS.filter(s => s.startsWith(normalized) && !(tags||[]).some(t => (t.label||t)===s)).slice(0,8);
  }, [normalized, tags]);

  const add = (raw) => {
    const t = String(raw || '').trim().toLowerCase().replace(/\s+/g,'');
    if (!t) return;
    if (!tags.find(x => (x.label||x) === t)) setTags([...(tags||[]), { label: t }]);
    setInput('');
  };

  const remove = (val) => setTags((tags||[]).filter(x => (x.label||x) !== val));

  const isValid = (tags || []).length > 0 || !required;
  if (typeof onValidityChange === 'function') {
    try { onValidityChange(isValid); } catch {}
  }

  return (
    <div>
      <div className="flex flex-wrap gap-2 mb-3">
        {(tags||[]).map((t, idx) => (
          <span key={idx} className="inline-flex items-center px-2 py-1 rounded-full text-xs border bg-amber-50 text-amber-800 border-amber-200">
            <span className="font-medium">{t.label || t}</span>
            <button onClick={() => remove(t.label||t)} className="ml-1 text-amber-900/70 hover:text-amber-900">×</button>
          </span>
        ))}
      </div>
      <input
        value={input}
        onChange={(e)=>{ setInput(e.target.value); setOpen(true); }}
        onKeyDown={(e)=>{ if (e.key==='Enter'){ e.preventDefault(); add(input); }}}
        placeholder={placeholder}
        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
      />
      {open && matches.length > 0 && (
        <div className="mt-1 border border-gray-200 rounded-lg bg-white shadow-sm divide-y">
          {matches.map(m => (
            <button key={m} type="button" onClick={()=>{ add(m); setOpen(false); }} className="w-full text-left px-3 py-2 hover:bg-gray-50">
              {m}
            </button>
          ))}
        </div>
      )}
      <div className="flex items-center justify-between mt-2">
        {required && !isValid && (
          <span className="text-xs text-red-600">At least one tag is required</span>
        )}
        <button onClick={()=>add(input)} className="px-3 py-1.5 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-700">Add</button>
      </div>
    </div>
  );
}


