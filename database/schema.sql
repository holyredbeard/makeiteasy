-- Canonical ingredients system
CREATE TABLE IF NOT EXISTS canonical_ingredients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_en TEXT NOT NULL UNIQUE,
    fdc_id TEXT,
    category TEXT,
    synonyms TEXT, -- JSON array of English synonyms
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ingredient_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alias_text TEXT NOT NULL,
    lang TEXT NOT NULL, -- 'sv', 'en', etc.
    canonical_ingredient_id INTEGER NOT NULL,
    confidence REAL DEFAULT 1.0, -- 0.0 to 1.0
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (canonical_ingredient_id) REFERENCES canonical_ingredients(id),
    UNIQUE(alias_text, lang, canonical_ingredient_id)
);

CREATE TABLE IF NOT EXISTS translation_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_hash TEXT NOT NULL UNIQUE, -- hash of name_raw+lang
    name_raw TEXT NOT NULL,
    lang TEXT NOT NULL,
    name_en TEXT NOT NULL,
    source TEXT NOT NULL, -- 'lexicon', 'rule', 'mt'
    confidence REAL DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Update recipe_ingredients table to support translation
ALTER TABLE recipe_ingredients ADD COLUMN locale_raw TEXT DEFAULT 'en';
ALTER TABLE recipe_ingredients ADD COLUMN name_en TEXT;
ALTER TABLE recipe_ingredients ADD COLUMN modifiers_en TEXT;
ALTER TABLE recipe_ingredients ADD COLUMN canonical_ingredient_id INTEGER;
ALTER TABLE recipe_ingredients ADD COLUMN confidence REAL DEFAULT 1.0;
ALTER TABLE recipe_ingredients ADD COLUMN translation_source TEXT;
ALTER TABLE recipe_ingredients ADD COLUMN FOREIGN KEY (canonical_ingredient_id) REFERENCES canonical_ingredients(id);

-- Insert some common canonical ingredients
INSERT OR IGNORE INTO canonical_ingredients (name_en, category) VALUES
('light soy sauce', 'condiment'),
('soy sauce', 'condiment'),
('elbow macaroni', 'pasta'),
('garlic', 'vegetable'),
('crushed tomatoes', 'vegetable'),
('sour cream', 'dairy'),
('scallion', 'vegetable'),
('smoked tofu', 'protein'),
('vegan sausage', 'protein'),
('soy milk', 'beverage'),
('vegan cheese', 'dairy'),
('black pepper', 'spice'),
('salt', 'spice'),
('water', 'beverage'),
('flaxseed', 'seed'),
('olive oil', 'oil');

-- Insert common Swedish aliases
INSERT OR IGNORE INTO ingredient_aliases (alias_text, lang, canonical_ingredient_id, confidence) VALUES
('ljus soja', 'sv', (SELECT id FROM canonical_ingredients WHERE name_en = 'light soy sauce'), 1.0),
('soja', 'sv', (SELECT id FROM canonical_ingredients WHERE name_en = 'soy sauce'), 1.0),
('idealmakaroner', 'sv', (SELECT id FROM canonical_ingredients WHERE name_en = 'elbow macaroni'), 1.0),
('gammaldags idealmakaroner', 'sv', (SELECT id FROM canonical_ingredients WHERE name_en = 'elbow macaroni'), 1.0),
('vitlöksklyftor', 'sv', (SELECT id FROM canonical_ingredients WHERE name_en = 'garlic'), 1.0),
('vitlök', 'sv', (SELECT id FROM canonical_ingredients WHERE name_en = 'garlic'), 1.0),
('krossade tomater', 'sv', (SELECT id FROM canonical_ingredients WHERE name_en = 'crushed tomatoes'), 1.0),
('gräddfil', 'sv', (SELECT id FROM canonical_ingredients WHERE name_en = 'sour cream'), 1.0),
('salladslök', 'sv', (SELECT id FROM canonical_ingredients WHERE name_en = 'scallion'), 1.0),
('rökt tofu', 'sv', (SELECT id FROM canonical_ingredients WHERE name_en = 'smoked tofu'), 1.0),
('veganska korvar', 'sv', (SELECT id FROM canonical_ingredients WHERE name_en = 'vegan sausage'), 1.0),
('vegansk korv', 'sv', (SELECT id FROM canonical_ingredients WHERE name_en = 'vegan sausage'), 1.0),
('sojamjölk', 'sv', (SELECT id FROM canonical_ingredients WHERE name_en = 'soy milk'), 1.0),
('vegansk ost', 'sv', (SELECT id FROM canonical_ingredients WHERE name_en = 'vegan cheese'), 1.0),
('svartpeppar', 'sv', (SELECT id FROM canonical_ingredients WHERE name_en = 'black pepper'), 1.0),
('peppar', 'sv', (SELECT id FROM canonical_ingredients WHERE name_en = 'black pepper'), 1.0),
('salt', 'sv', (SELECT id FROM canonical_ingredients WHERE name_en = 'salt'), 1.0),
('vatten', 'sv', (SELECT id FROM canonical_ingredients WHERE name_en = 'water'), 1.0),
('linfrö', 'sv', (SELECT id FROM canonical_ingredients WHERE name_en = 'flaxseed'), 1.0),
('linfröägg', 'sv', (SELECT id FROM canonical_ingredients WHERE name_en = 'flaxseed'), 1.0);
