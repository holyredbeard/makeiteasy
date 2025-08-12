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

export function buildUserPayload(recipe, constraints) {
  return {
    recipe: {
      title: recipe?.title || '',
      description: recipe?.description || '',
      ingredients: (recipe?.ingredients || []).slice(0, 60).map((ing) => {
        if (typeof ing === 'string') return ing;
        if (ing && typeof ing === 'object') {
          const qty = (ing.quantity ?? '').toString().trim();
          const name = (ing.name ?? '').toString().trim();
          const notes = (ing.notes ?? '').toString().trim();
          const base = [qty, name].filter(Boolean).join(' ');
          return notes ? `${base} (${notes})` : base || name || qty || '';
        }
        return String(ing ?? '').trim();
      }),
      instructions: (recipe?.instructions || []).slice(0, 40).map((step) => {
        if (typeof step === 'string') return step;
        if (step && typeof step === 'object') return step.description ?? '';
        return String(step ?? '').trim();
      }),
      nutritionPerServing: recipe?.nutritionPerServing || { calories: null, protein: null, carbs: null, fat: null, sodium: null }
    },
    constraints: {
      presets: constraints?.presets || [],
      nutrition: constraints?.nutrition || { maxCalories: null, minProtein: null, maxCarbs: null, maxFat: null, maxSodium: null },
      excludeAllergens: constraints?.excludeAllergens || [],
      locale: constraints?.locale || 'sv'
    }
  };
}


