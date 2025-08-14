export const SYSTEM_PROMPT = `Role: Senior culinary RD + dietitian.
Mission: Convert the provided recipe according to diet presets, allergies and per-serving nutrition goals.
Rules:
- Return ONLY JSON according to our schema. No extra text.
- Respect locale (sv/en).
- Replace ingredients with realistic Nordic-available alternatives when needed.
- Rewrite instructions to match substitutions.
- Recalculate per-serving nutrition and mark compliance ✓/✕ for goals.
- If a goal cannot be fully met, choose the best feasible solution and briefly explain in notes.
- Max 60 ingredients, 40 steps – if exceeded, trim and add a note.
 - If the recipe already satisfies the requested presets (e.g., vegan), STILL return the full ingredients and instructions copied from input (do not leave them empty). In this case, "substitutions" may be empty and add a short note like "Already compliant".

Diet enforcement (CRITICAL):
- When presets contain "vegan":
  - The final ingredients MUST NOT contain any animal-derived products: meat (beef, pork, chicken, turkey), fish/seafood (lax, torsk, räkor, tonfisk, musslor), gelatin, honey, eggs, dairy (milk, cheese, butter, cream, yoghurt), broth from animals, bacon, sausage (korv), skinka, kyckling, grädde, ost, ägg, mjölk.
  - Provide explicit substitutions in "substitutions" for each removed item (e.g., bacon → rökt tofu; mjölk → havredryck; grädde → havregrädde; ost → vegansk hårdost; ägg → kikärtsmjöl / tofu scramble / psyllium depending on use).
  - Ensure instructions no longer reference removed items.
- When presets contain "vegetarian": remove meat/fish/seafood but dairy/eggs may remain unless excluded by other presets.

Output schema (ALL keys must always be present; use empty arrays or nulls if needed):
{
  "title": string,
  "substitutions": [ { "from": string, "to": string, "reason": string } ],
  "ingredients": [ string ],
  "instructions": [ string ],
  "notes": [ string ],
  "nutritionPerServing": { "calories": number|null, "protein": number|null, "carbs": number|null, "fat": number|null, "sodium": number|null },
  "compliance": { "calories": boolean|null, "protein": boolean|null, "carbs": boolean|null, "fat": boolean|null, "sodium": boolean|null }
}
Return exact JSON only, no markdown fences.

Common substitutions (examples):
- bacon → rökt tofu or mushroom bacon (vegan)
- grädde → havregrädde (vegan/dairy-free)
- smör → rapsolja (vegan)
- parmesan → plant-based hard cheese (vegan)
- kycklingbuljong → grönsaksbuljong (vegan)
- vetepasta → glutenfri majs/ris-pasta (gluten-free)
- soja → tamari (gluten-free)
- honung → lönnsirap (vegan)
`;

// Build a dynamic system prompt segment derived from constraints to cover all combinations
export function buildSystemPrompt(constraints = {}, locale = 'sv') {
  // 1) Normalize presets: lower-case and replace spaces with dashes
  const normalizePreset = (k) => String(k || '').trim().toLowerCase().replace(/\s+/g, '-');
  const normalizedPresets = (constraints.presets || []).map(normalizePreset);
  const presets = new Set(normalizedPresets);

  // 4) Tolerance only from nutrition.tolerance; default ±5%
  const n = constraints.nutrition || {};
  const tol = Number(n.tolerance ?? 5);
  const sections = [];

  // Diet style
  if (presets.has('vegan')) {
    sections.push('- Enforce VEGAN: no meat, poultry, fish/seafood, eggs, dairy, gelatin or honey. Always provide explicit substitutions for removed items.');
  } else if (presets.has('vegetarian')) {
    sections.push('- Enforce VEGETARIAN: no meat, poultry or fish/seafood. Dairy and eggs allowed unless excluded elsewhere.');
  } else if (presets.has('pescetarian')) {
    sections.push('- Enforce PESCETARIAN: fish/seafood allowed; no meat/poultry.');
  }

  // Add-ons (only if diet allows)
  if (presets.has('add-fish') && !presets.has('vegan') && !presets.has('vegetarian')) {
    sections.push('- If reasonable, add a suitable fish/seafood component or swap to fish-based protein.');
  }
  if (presets.has('add-meat') && !presets.has('vegan') && !presets.has('vegetarian') && !presets.has('pescetarian')) {
    sections.push('- If reasonable, add a suitable meat-based protein (lean cut when nutrition requires).');
  }
  if (presets.has('add-dairy') && !presets.has('vegan')) {
    sections.push('- Allow dairy additions (e.g., cheese, yoghurt) unless excluded by allergies.');
  }

  // Exclusions
  const exclude = [];
  if (presets.has('dairy-free')) exclude.push('dairy');
  if (presets.has('egg-free')) exclude.push('eggs');
  if (presets.has('fish-free')) exclude.push('fish/seafood');
  if (presets.has('shellfish-free')) exclude.push('shellfish');
  if (presets.has('gluten-free')) exclude.push('gluten');
  if (presets.has('soy-free')) exclude.push('soy');
  if (presets.has('nut-free')) exclude.push('tree nuts/peanuts');
  if (presets.has('lactose-free')) exclude.push('lactose');

  // 2) Map excludeAllergens into same exclude list
  const allergenMap = {
    'nuts': 'tree nuts/peanuts',
    'soy': 'soy',
    'gluten': 'gluten',
    'dairy': 'dairy',
    'eggs': 'eggs',
    'fish': 'fish/seafood',
    'shellfish': 'shellfish',
    'sesame': 'sesame',
    'lactose': 'lactose',
  };
  const fromAllergens = (constraints.excludeAllergens || [])
    .map((a) => String(a || '').trim().toLowerCase())
    .map((a) => allergenMap[a])
    .filter(Boolean);
  if (fromAllergens.length) exclude.push(...fromAllergens);
  if (exclude.length) sections.push(`- Exclude: ${exclude.join(', ')}. Provide substitutions where relevant.`);

  if (presets.has('halal')) sections.push('- Enforce HALAL: no pork, no alcohol; use halal-compliant meat if present.');
  if (presets.has('kosher')) sections.push('- Enforce KOSHER: no pork/shellfish; avoid mixing meat and dairy; keep kosher handling conceptually.');

  // Programs
  if (presets.has('whole30')) sections.push(`- Program WHOLE30: whole foods only; no sugar, alcohol, grains, legumes or dairy${presets.has('vegan') ? '; apply in a fully VEGAN manner' : ''}.`);
  if (presets.has('mediterranean')) sections.push(`- Program MEDITERRANEAN: emphasize olive oil, vegetables, legumes, whole grains; prefer fish/poultry over red meat${presets.has('vegan') ? ' (use vegan alternatives only)' : ''}.`);

  // Macros priorities
  if (presets.has('keto') && !presets.has('vegan')) sections.push('- Macro focus: KETO. Keep carbs very low; prefer fats; protein moderate. If low-carb present, keto takes precedence.');
  else if (presets.has('low-carb')) sections.push('- Macro focus: LOW-CARB. Reduce carbohydrate sources; prefer non-starchy vegetables and proteins.');
  if (presets.has('low-fat')) sections.push('- Macro focus: LOW-FAT. Prefer lean proteins, low-fat cooking methods, reduce added oils.');
  if (presets.has('high-protein')) sections.push('- Macro focus: HIGH-PROTEIN. Increase protein-rich components and reduce low-protein fillers.');

  // Numeric targets and tolerance
  const lines = [];
  const pushRange = (name, min, max, unit) => {
    const haveMin = min != null && min !== '';
    const haveMax = max != null && max !== '';
    if (haveMin || haveMax) lines.push(`  - ${name}${haveMin ? ` ≥ ${min}${unit}` : ''}${haveMin && haveMax ? ',' : ''}${haveMax ? ` ≤ ${max}${unit}` : ''}`);
  };
  pushRange('Calories', n.minCalories, n.maxCalories, ' kcal');
  pushRange('Protein', n.minProtein, n.maxProtein, ' g');
  pushRange('Carbs', n.minCarbs, n.maxCarbs, ' g');
  pushRange('Fat', n.minFat, n.maxFat, ' g');
  if (lines.length) sections.push(`- Hit per-serving targets within ±${tol}% tolerance:\n${lines.join('\n')}`);

  const localeLine = `- Locale: ${locale || constraints.locale || 'sv'} (use appropriate units and ingredient names).`;
  sections.push(localeLine);
  sections.push('- Use metric units (g, ml) and Swedish ingredient names when locale=sv.');

  const dynamic = sections.length ? `\nDynamic constraints based on user choices:\n${sections.map(s=>`• ${s}`).join('\n')}` : '';
  return SYSTEM_PROMPT + dynamic;
}

export function buildUserPayload(recipe, constraints) {
  return {
    recipe: {
      title: recipe?.title || '',
      // Trim description for speed
      description: (recipe?.description || '').toString().slice(0, 400),
      // Limit payload size for speed
      ingredients: (recipe?.ingredients || []).slice(0, 25).map((ing) => {
        if (typeof ing === 'string') return ing;
        if (ing && typeof ing === 'object') {
          const qty = (ing.quantity ?? '').toString().trim();
          const name = (ing.name ?? '').toString().trim();
          const notes = (ing.notes ?? '').toString().trim();
          const base = [qty, name].filter(Boolean).join(' ');
          return notes ? `${base} (${notes})` : base || name || qty || '';
        }
        return String(ing ?? '').trim();
      }).filter(Boolean),
      instructions: (recipe?.instructions || []).slice(0, 20).map((step) => {
        if (typeof step === 'string') return step;
        if (step && typeof step === 'object') return step.description ?? '';
        return String(step ?? '').trim();
      }).filter(Boolean),
      nutritionPerServing: recipe?.nutritionPerServing || { calories: null, protein: null, carbs: null, fat: null, sodium: null }
    },
    constraints: {
      presets: constraints?.presets || [],
      nutrition: {
        minCalories: constraints?.nutrition?.minCalories ?? null,
        maxCalories: constraints?.nutrition?.maxCalories ?? null,
        minProtein: constraints?.nutrition?.minProtein ?? null,
        maxProtein: constraints?.nutrition?.maxProtein ?? null,
        minCarbs: constraints?.nutrition?.minCarbs ?? null,
        maxCarbs: constraints?.nutrition?.maxCarbs ?? null,
        minFat: constraints?.nutrition?.minFat ?? null,
        maxFat: constraints?.nutrition?.maxFat ?? null,
        tolerance: constraints?.nutrition?.tolerance ?? null,
      },
      excludeAllergens: constraints?.excludeAllergens || [],
      locale: constraints?.locale || 'sv'
    }
  };
}


