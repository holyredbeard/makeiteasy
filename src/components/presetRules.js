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
  dietStyle: ["omnivore", "plant-based", "vegan", "vegetarian", "pescetarian"],
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
  macros: ["low-carb", "keto", "low-fat", "high-protein", "low-sodium"],
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

  // Macros / Programs
  if (selected.has("keto")) disabled.add("low-carb");
  if (selected.has("Whole30")) disabled.add("vegan");

  return [...disabled];
}

// Contextual visibility for add-ons; keep simple and permissive (disabled will still apply)
export function getVisibleAddOns() {
  return PRESET_GROUPS.addOns;
}

export default { PRESET_GROUPS, resolvePresets, getDisabledPresets };


