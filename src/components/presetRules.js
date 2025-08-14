// Centraliserade preset-regler för både UI och backend-paritet
// Exporterar PRESET_GROUPS, resolvePresets(selected), getDisabledPresets(selected)

const DIET_PRIORITY = [
  "vegan",
  "plant-based",
  "vegetarian",
  "pescetarian",
  "omnivore",
];

export const PRESET_GROUPS = {
  dietStyle: ["vegan", "vegetarian", "pescetarian"],
  addOns: ["add-meat", "add-fish", "add-dairy"],
  exclusions: [
    "dairy-free",
    "lactose-free",
    "gluten-free",
    "nut-free",
    "soy-free",
    "egg-free",
    "fish-free",
    "shellfish-free",
    "halal",
    "kosher",
    "paleo",
  ],
  macros: ["low-carb", "keto", "low-fat", "high-protein"],
  programs: ["Mediterranean", "Whole30"],
};

// Backwards-compat alias used by UI
export const GROUPS = PRESET_GROUPS;

function pickHighestPriorityDiet(selected) {
  for (const diet of DIET_PRIORITY) {
    if (selected.has(diet)) return diet;
  }
  return null;
}

function applyDietConflicts(selected, adjustments) {
  const disabled = new Set();
  if (selected.has("vegan")) {
    ["vegetarian", "pescetarian", "add-meat", "add-fish", "add-dairy"].forEach((k) => {
      disabled.add(k);
      if (selected.delete(k)) adjustments.autoUnselected.push(k);
    });
  }
  if (selected.has("vegetarian")) {
    ["pescetarian", "add-meat"].forEach((k) => {
      disabled.add(k);
      if (selected.delete(k)) adjustments.autoUnselected.push(k);
    });
  }
  if (selected.has("plant-based")) {
    ["add-meat", "add-fish"].forEach((k) => {
      disabled.add(k);
      if (selected.delete(k)) adjustments.autoUnselected.push(k);
    });
  }
  if (selected.has("pescetarian")) {
    ["add-meat"].forEach((k) => {
      disabled.add(k);
      if (selected.delete(k)) adjustments.autoUnselected.push(k);
    });
  }
  return disabled;
}

function applyExclusionConflicts(selected, adjustments) {
  const disabled = new Set();
  // dairy-free ↔ add-dairy (vice versa)
  if (selected.has("dairy-free")) {
    disabled.add("add-dairy");
    if (selected.delete("add-dairy")) adjustments.autoUnselected.push("add-dairy");
  }
  if (selected.has("add-dairy")) {
    disabled.add("dairy-free");
    if (selected.delete("dairy-free")) adjustments.autoUnselected.push("dairy-free");
  }
  // fish-free disables add-fish
  if (selected.has("fish-free")) {
    disabled.add("add-fish");
    if (selected.delete("add-fish")) adjustments.autoUnselected.push("add-fish");
  }
  // lactose-free can coexist; no special conflict beyond dairy-free rule
  return disabled;
}

function applyMacrosPrograms(selected, adjustments) {
  const disabled = new Set();
  // keto implies low-carb → auto-unselect low-carb
  if (selected.has("keto") && selected.has("low-carb")) {
    selected.delete("low-carb");
    adjustments.autoUnselected.push("low-carb");
    disabled.add("low-carb");
  }
  // Whole30 auto-disables vegan (keep Whole30)
  if (selected.has("Whole30") && selected.has("vegan")) {
    selected.delete("vegan");
    adjustments.autoUnselected.push("vegan");
    disabled.add("vegan");
  }
  // dietStyle precedence over programs is generally true, but explicit Whole30 rule above applies
  return disabled;
}

function toArraySafe(maybeIterable) {
  if (!maybeIterable) return [];
  if (Array.isArray(maybeIterable)) return maybeIterable;
  try {
    if (typeof maybeIterable[Symbol.iterator] === 'function') return Array.from(maybeIterable);
  } catch (_e) {
    // ignore
  }
  return [];
}

export function resolvePresets(inputSelected) {
  const base = toArraySafe(inputSelected);
  const selected = new Set(base);
  const adjustments = { autoUnselected: [], autoDisabled: [], autoAdded: [] };

  // Ensure dietStyle is single-select according to priority
  const presentDiets = PRESET_GROUPS.dietStyle.filter((k) => selected.has(k));
  if (presentDiets.length > 1) {
    const keep = pickHighestPriorityDiet(new Set(presentDiets));
    for (const diet of presentDiets) {
      if (diet !== keep) {
        selected.delete(diet);
        adjustments.autoUnselected.push(diet);
      }
    }
  }

  // Apply conflict rules
  const disabledDiet = applyDietConflicts(selected, adjustments);
  const disabledExcl = applyExclusionConflicts(selected, adjustments);
  const disabledMacroProg = applyMacrosPrograms(selected, adjustments);

  // Vegan auto-add and lock exclusions (UI lock handled separately)
  if (selected.has('vegan')) {
    ["dairy-free", "egg-free", "fish-free", "shellfish-free"].forEach((k) => {
      if (!selected.has(k)) {
        selected.add(k);
        adjustments.autoAdded.push(k);
      }
    });
  }

  const autoDisabled = new Set([...disabledDiet, ...disabledExcl, ...disabledMacroProg]);
  adjustments.autoDisabled = [...autoDisabled];

  return { resolved: [...selected], adjustments };
}

export function getDisabledPresets(inputSelected) {
  const base = toArraySafe(inputSelected);
  const selected = new Set(base);
  const disabled = new Set();

  // Diet conflicts (mirror of resolve)
  if (selected.has("vegan")) ["vegetarian", "pescetarian", "add-meat", "add-fish", "add-dairy"].forEach((k) => disabled.add(k));
  if (selected.has("vegetarian")) ["pescetarian", "add-meat"].forEach((k) => disabled.add(k));
  if (selected.has("plant-based")) ["add-meat", "add-fish"].forEach((k) => disabled.add(k));
  if (selected.has("pescetarian")) ["add-meat"].forEach((k) => disabled.add(k));

  // Exclusions
  if (selected.has("dairy-free")) disabled.add("add-dairy");
  if (selected.has("add-dairy")) disabled.add("dairy-free");
  if (selected.has("fish-free")) disabled.add("add-fish");

  // Macros / Programs
  if (selected.has("keto")) disabled.add("low-carb");
  if (selected.has("Whole30")) disabled.add("vegan");

  return [...disabled];
}

// Locked presets (non-clickable) derived from current selection (UI enforcement)
export function getLockedPresets(inputSelected) {
  const selected = new Set(toArraySafe(inputSelected));
  const locked = new Set();
  if (selected.has('vegan')) {
    ["dairy-free", "egg-free", "fish-free", "shellfish-free"].forEach(k => locked.add(k));
  }
  return [...locked];
}

// UI label mapping
export function labelForPreset(key) {
  if (!key) return '';
  if (key === 'Whole30' || key === 'Mediterranean') return key; // keep proper names
  const map = {
    'add-meat': 'Add meat',
    'add-fish': 'Add fish',
    'add-dairy': 'Add dairy',
  };
  if (map[key]) return map[key];
  const pretty = String(key).replace(/-/g, ' ');
  return pretty.charAt(0).toUpperCase() + pretty.slice(1);
}

// Contextual visibility for add-ons; keep simple and permissive (disabled will still apply)
export function getVisibleAddOns() {
  return PRESET_GROUPS.addOns;
}

export default { PRESET_GROUPS, resolvePresets, getDisabledPresets, getLockedPresets, labelForPreset };


