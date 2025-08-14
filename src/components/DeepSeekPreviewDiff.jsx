import React from 'react';

export default function DeepSeekPreviewDiff({ result, baseIngredients = [], baseInstructions = [], constraints }) {
  if (!result) return null;
  const { substitutions = [], ingredients = [], instructions = [], notes = [], nutritionPerServing = {}, compliance = {} } = result;
  // Normalize notes to array to avoid "notes.map is not a function" when a string is returned
  const noteList = Array.isArray(notes) ? notes : (notes ? [String(notes)] : []);
  const hasSubs = Array.isArray(substitutions) && substitutions.length > 0;
  const presetList = (constraints?.presets || []).map(String);
  return (
    <div className="grid gap-4">
      {hasSubs && (
        <section>
          <h4 className="font-semibold mb-2">Substitutions</h4>
          <ul className="list-disc pl-5 text-sm">
            {substitutions.map((s, i) => (
              <li key={i}><strong>{s.from}</strong> → <strong>{s.to}</strong> – {s.reason}</li>
            ))}
          </ul>
        </section>
      )}
      {!hasSubs && (Array.isArray(baseIngredients) && baseIngredients.length > 0) && (
        <section>
          <h4 className="font-semibold mb-2">Substitutions</h4>
          <p className="text-sm text-gray-600">
            {presetList.includes('vegan') || presetList.includes('plant-based') ?
              'Converted to vegan: Base ingredients kept but ensure no animal products remain.' :
              'No explicit substitutions provided. If the recipe was already compliant, ingredients are copied as-is.'}
          </p>
        </section>
      )}
      <section>
        <h4 className="font-semibold mb-2">Ingredients (updated)</h4>
        <ul className="list-disc pl-5 text-sm space-y-1">
          {ingredients.map((line, i) => (<li key={i}>{line}</li>))}
        </ul>
      </section>
      <section>
        <h4 className="font-semibold mb-2">Instructions (updated)</h4>
        <ol className="list-decimal pl-5 text-sm space-y-1">
          {instructions.map((line, i) => (<li key={i}>{line}</li>))}
        </ol>
      </section>
      <section>
        <h4 className="font-semibold mb-2">Nutrition per serving</h4>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-center">
          {[
            ['Calories', nutritionPerServing.calories],
            ['Protein', nutritionPerServing.protein],
            ['Carbs', nutritionPerServing.carbs],
            ['Fat', nutritionPerServing.fat],
            ['Sodium', nutritionPerServing.sodium]
          ].map(([label, val]) => (
            <div key={label} className="border rounded-lg p-2">
              <div className="text-xs text-gray-500">{label}</div>
              <div className="font-semibold">{val ?? '—'}</div>
            </div>
          ))}
        </div>
        <div className="text-sm mt-2 text-gray-700">
          <span className={compliance.calories === false ? 'text-red-600' : 'text-green-600'}>Calories: {mark(compliance.calories)}</span>{' · '}
          <span className={compliance.protein === false ? 'text-red-600' : 'text-green-600'}>Protein: {mark(compliance.protein)}</span>{' · '}
          <span className={compliance.carbs === false ? 'text-red-600' : 'text-green-600'}>Carbs: {mark(compliance.carbs)}</span>{' · '}
          <span className={compliance.fat === false ? 'text-red-600' : 'text-green-600'}>Fat: {mark(compliance.fat)}</span>{' · '}
          <span className={compliance.sodium === false ? 'text-red-600' : 'text-green-600'}>Sodium: {mark(compliance.sodium)}</span>
        </div>
      </section>
      {noteList.length > 0 && (
        <section>
          <h4 className="font-semibold mb-2">Notes</h4>
          <ul className="list-disc pl-5 text-sm space-y-1">
            {noteList.map((n, i) => (<li key={i}>{n}</li>))}
          </ul>
        </section>
      )}
    </div>
  );
}

function mark(b) {
  if (b === true) return '✓';
  if (b === false) return '✕';
  return '—';
}


