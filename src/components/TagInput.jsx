import React, { useMemo, useState } from 'react';

const SUGGESTIONS = [
  'pasta','soup','salad','stirfry','baked','grilled','fried','breakfast','lunch','dinner','dessert',
  'italian','mexican','indian','thai','japanese','swedish','vegan','vegetarian','pescatarian','glutenfree','dairyfree',
  'quick','easy','healthy','highprotein','lowcarb','zesty','seafood','fastfood','spicy','chicken','eggs','cheese','fruits','wine'
];

export default function TagInput({ tags, setTags, placeholder = 'Type to add a tag...', required = false, onValidityChange }) {
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
        {(tags||[]).map((t, idx) => {
          const label = t.label || t;
          const labelLower = label.toLowerCase();
          let tagClass = 'bg-amber-50 text-amber-800 border-amber-200';
          
          // Apply specific styling for known tags
          if (labelLower === 'vegan') tagClass = 'bg-emerald-600 text-white border-emerald-600';
          else if (labelLower === 'vegetarian') tagClass = 'bg-lime-600 text-white border-lime-600';
          else if (labelLower === 'pescatarian') tagClass = 'bg-sky-600 text-white border-sky-600';
          else if (labelLower === 'zesty') tagClass = 'bg-yellow-500 text-white border-yellow-500';
          else if (labelLower === 'seafood') tagClass = 'bg-blue-600 text-white border-blue-600';
          else if (labelLower === 'fastfood') tagClass = 'bg-orange-500 text-white border-orange-500';
          else if (labelLower === 'spicy') tagClass = 'bg-red-600 text-white border-red-600';
          else if (labelLower === 'chicken') tagClass = 'bg-amber-600 text-white border-amber-600';
          else if (labelLower === 'eggs') tagClass = 'bg-yellow-400 text-white border-yellow-400';
          else if (labelLower === 'cheese') tagClass = 'bg-yellow-300 text-gray-800 border-yellow-300';
          else if (labelLower === 'fruits') tagClass = 'bg-pink-500 text-white border-pink-500';
          else if (labelLower === 'wine') tagClass = 'bg-purple-600 text-white border-purple-600';
          else if (labelLower === 'pasta') tagClass = 'bg-orange-600 text-white border-orange-600';
          
          return (
            <span key={idx} className={`inline-flex items-center px-2 py-1 rounded-full text-xs border ${tagClass}`}>
              {labelLower === 'vegan' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'vegetarian' && <i className="fa-solid fa-carrot mr-1"></i>}
              {labelLower === 'zesty' && <i className="fa-solid fa-lemon mr-1"></i>}
              {labelLower === 'pescatarian' && <i className="fa-solid fa-fish mr-1"></i>}
              {labelLower === 'seafood' && <i className="fa-solid fa-shrimp mr-1"></i>}
              {labelLower === 'fastfood' && <i className="fa-solid fa-burger mr-1"></i>}
              {labelLower === 'spicy' && <i className="fa-solid fa-pepper-hot mr-1"></i>}
              {labelLower === 'chicken' && <i className="fa-solid fa-drumstick-bite mr-1"></i>}
              {labelLower === 'eggs' && <i className="fa-solid fa-egg mr-1"></i>}
              {labelLower === 'cheese' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'fruits' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'wine' && <i className="fa-solid fa-wine-bottle mr-1"></i>}
              {labelLower === 'pasta' && <i className="fa-solid fa-bacon mr-1"></i>}
              <span className="font-medium">{label.charAt(0).toUpperCase() + label.slice(1)}</span>
              <button onClick={() => remove(label)} className="ml-1 opacity-70 hover:opacity-100">×</button>
            </span>
          );
        })}
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
            <button key={m} type="button" onClick={()=>{ add(m); setOpen(false); }} className="w-full text-left px-3 py-2 hover:bg-gray-50 flex items-center">
              {m.toLowerCase() === 'vegan' && <i className="fa-solid fa-leaf mr-2 text-emerald-600"></i>}
              {m.toLowerCase() === 'vegetarian' && <i className="fa-solid fa-carrot mr-2 text-lime-600"></i>}
              {m.toLowerCase() === 'zesty' && <i className="fa-solid fa-lemon mr-2 text-yellow-500"></i>}
              {m.toLowerCase() === 'pescatarian' && <i className="fa-solid fa-fish mr-2 text-sky-600"></i>}
              {m.toLowerCase() === 'seafood' && <i className="fa-solid fa-shrimp mr-2 text-blue-600"></i>}
              {m.toLowerCase() === 'fastfood' && <i className="fa-solid fa-burger mr-2 text-orange-500"></i>}
              {m.toLowerCase() === 'spicy' && <i className="fa-solid fa-pepper-hot mr-2 text-red-600"></i>}
              {m.toLowerCase() === 'chicken' && <i className="fa-solid fa-drumstick-bite mr-2 text-amber-600"></i>}
              {m.toLowerCase() === 'eggs' && <i className="fa-solid fa-egg mr-2 text-yellow-400"></i>}
              {m.toLowerCase() === 'cheese' && <i className="fa-solid fa-cheese mr-2 text-yellow-300"></i>}
              {m.toLowerCase() === 'fruits' && <i className="fa-solid fa-apple-whole mr-2 text-pink-500"></i>}
              {m.toLowerCase() === 'wine' && <i className="fa-solid fa-wine-bottle mr-2 text-purple-600"></i>}
              {m.toLowerCase() === 'pasta' && <i className="fa-solid fa-bacon mr-2 text-orange-600"></i>}
              {m.charAt(0).toUpperCase() + m.slice(1)}
            </button>
          ))}
        </div>
      )}
      {required && !isValid && (
        <div className="mt-2">
          <span className="text-xs text-red-600">At least one tag is required</span>
        </div>
      )}
    </div>
  );
}


