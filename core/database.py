import sqlite3
from datetime import datetime
from typing import Optional, List
from pathlib import Path
from models.types import User, UserCreate, UserInDB, SavedRecipe, RecipeContent
import logging
import json
from core.password import verify_password, get_password_hash, needs_rehash

logger = logging.getLogger(__name__)
DB_PATH = Path("users.db")

class DatabaseManager:
    def __init__(self):
        self.db_path = DB_PATH
        self.init_database()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_database(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    full_name TEXT NOT NULL,
                    username TEXT UNIQUE,
                    hashed_password TEXT,
                    google_id TEXT,
                    avatar_url TEXT,
                    auth_provider TEXT DEFAULT 'email',
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Ensure new columns exist for already-created databases
            cursor.execute("PRAGMA table_info(users)")
            user_cols = {row[1] for row in cursor.fetchall()}
            if 'username' not in user_cols:
                # SQLite cannot add a UNIQUE constraint via ALTER TABLE
                cursor.execute("ALTER TABLE users ADD COLUMN username TEXT")
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username)")
            if 'avatar_url' not in user_cols:
                cursor.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT")
            if 'google_id' not in user_cols:
                cursor.execute("ALTER TABLE users ADD COLUMN google_id TEXT")
            if 'auth_provider' not in user_cols:
                cursor.execute("ALTER TABLE users ADD COLUMN auth_provider TEXT DEFAULT 'email'")
            if 'is_active' not in user_cols:
                cursor.execute("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1")
            if 'created_at' not in user_cols:
                cursor.execute("ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            # New optional profile fields
            for col in ['location','instagram_url','youtube_url','facebook_url','tiktok_url','website_url']:
                if col not in user_cols:
                    try:
                        cursor.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT")
                    except Exception:
                        pass
            # Roles mapping
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_roles (
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    PRIMARY KEY (user_id, role),
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
                """
            )
            # User follows (user to user)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_follows (
                    follower_id INTEGER NOT NULL,
                    followee_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (follower_id, followee_id),
                    FOREIGN KEY (follower_id) REFERENCES users (id),
                    FOREIGN KEY (followee_id) REFERENCES users (id)
                )
                """
            )
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS saved_recipes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    source_url TEXT NOT NULL,
                    recipe_content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    rating_average REAL DEFAULT 0,
                    rating_count INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)
            # Ensure new columns exist (for migrated DBs)
            cursor.execute("PRAGMA table_info(saved_recipes)")
            cols = [row[1] for row in cursor.fetchall()]
            if 'rating_average' not in cols:
                cursor.execute("ALTER TABLE saved_recipes ADD COLUMN rating_average REAL DEFAULT 0")
            if 'rating_count' not in cols:
                cursor.execute("ALTER TABLE saved_recipes ADD COLUMN rating_count INTEGER DEFAULT 0")
            if 'likes_count' not in cols:
                cursor.execute("ALTER TABLE saved_recipes ADD COLUMN likes_count INTEGER DEFAULT 0")

            # Ratings table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS ratings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipe_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    value INTEGER NOT NULL CHECK(value >= 1 AND value <= 5),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(recipe_id, user_id),
                    FOREIGN KEY (recipe_id) REFERENCES saved_recipes (id),
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ratings_recipe_id ON ratings(recipe_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ratings_recipe_value ON ratings(recipe_id, value)")

            # Recipe likes table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS recipe_likes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipe_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(recipe_id, user_id),
                    FOREIGN KEY (recipe_id) REFERENCES saved_recipes (id),
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_recipe_likes_recipe_id ON recipe_likes(recipe_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_recipe_likes_user_id ON recipe_likes(user_id)")

            # Comments table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipe_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    body TEXT NOT NULL,
                    parent_id INTEGER,
                    deleted BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (recipe_id) REFERENCES saved_recipes (id),
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (parent_id) REFERENCES comments (id)
                )
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_comments_recipe_created ON comments(recipe_id, created_at DESC, id DESC)")

            # Comment likes table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS comment_likes (
                    comment_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (comment_id, user_id),
                    FOREIGN KEY (comment_id) REFERENCES comments (id),
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_comment_likes_comment ON comment_likes(comment_id)")

            # Comment reports table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS comment_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    comment_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (comment_id) REFERENCES comments (id),
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
                """
            )

            # --- Nutrition snapshots for fast recipe page loads ---
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS nutrition_snapshots (
                    recipe_id INTEGER PRIMARY KEY,
                    snapshot TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    meta TEXT
                )
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nutrition_snapshots_status ON nutrition_snapshots(status)")

            # --- USDA FDC foods cache (json response), for 14-day reuse ---
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS fdc_foods (
                    fdc_id INTEGER PRIMARY KEY,
                    json TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # --- Density catalog (learned/fallback) ---
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS density_catalog (
                    category TEXT,
                    form TEXT,
                    g_per_ml REAL,
                    source TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (category, form)
                )
                """
            )

            # --- Collections ---
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS collections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    image_url TEXT,
                    visibility TEXT NOT NULL DEFAULT 'public',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    rating_average REAL DEFAULT 0,
                    rating_count INTEGER DEFAULT 0,
                    likes_count INTEGER DEFAULT 0,
                    followers_count INTEGER DEFAULT 0,
                    FOREIGN KEY (owner_id) REFERENCES users (id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS collection_recipes (
                    collection_id INTEGER NOT NULL,
                    recipe_id INTEGER NOT NULL,
                    position INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (collection_id, recipe_id),
                    FOREIGN KEY (collection_id) REFERENCES collections (id),
                    FOREIGN KEY (recipe_id) REFERENCES saved_recipes (id)
                )
                """
            )
            # Ensure new column exists for already-created databases
            cursor.execute("PRAGMA table_info(collection_recipes)")
            cr_cols = {row[1] for row in cursor.fetchall()}
            if 'position' not in cr_cols:
                try:
                    cursor.execute("ALTER TABLE collection_recipes ADD COLUMN position INTEGER")
                except Exception:
                    pass
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS collection_likes (
                    collection_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (collection_id, user_id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS collection_follows (
                    collection_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (collection_id, user_id)
                )
                """
            )

            # --- Tagging tables ---
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT UNIQUE NOT NULL,
                    type TEXT NOT NULL,
                    active BOOLEAN DEFAULT 1
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS tag_synonyms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alias TEXT UNIQUE NOT NULL,
                    tag_id INTEGER NOT NULL,
                    FOREIGN KEY (tag_id) REFERENCES tags (id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS recipe_tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipe_id INTEGER NOT NULL,
                    tag_id INTEGER NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('approved','pending','rejected')),
                    suggested_by INTEGER,
                    approved_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(recipe_id, tag_id),
                    FOREIGN KEY (recipe_id) REFERENCES saved_recipes (id),
                    FOREIGN KEY (tag_id) REFERENCES tags (id),
                    FOREIGN KEY (suggested_by) REFERENCES users (id),
                    FOREIGN KEY (approved_by) REFERENCES users (id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS tag_change_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipe_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    tag_id INTEGER,
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (recipe_id) REFERENCES saved_recipes (id),
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (tag_id) REFERENCES tags (id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS recipe_tag_locks (
                    recipe_id INTEGER PRIMARY KEY,
                    locked BOOLEAN NOT NULL DEFAULT 0,
                    locked_by INTEGER,
                    reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (recipe_id) REFERENCES saved_recipes (id),
                    FOREIGN KEY (locked_by) REFERENCES users (id)
                )
                """
            )
            # --- Canonical ingredients & translation tables ---
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS canonical_ingredients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name_en TEXT NOT NULL UNIQUE,
                    fdc_id TEXT,
                    category TEXT,
                    synonyms TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS ingredient_aliases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alias_text TEXT NOT NULL,
                    lang TEXT NOT NULL,
                    canonical_ingredient_id INTEGER NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (canonical_ingredient_id) REFERENCES canonical_ingredients(id),
                    UNIQUE(alias_text, lang, canonical_ingredient_id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS ingredient_translations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    canonical_ingredient_id INTEGER NOT NULL,
                    lang TEXT NOT NULL,
                    translated_name TEXT NOT NULL,
                    source TEXT,
                    confidence REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (canonical_ingredient_id) REFERENCES canonical_ingredients(id),
                    UNIQUE(canonical_ingredient_id, lang)
                )
                """
            )
            # Ensure new columns exist for migrated DBs
            cursor.execute("PRAGMA table_info(ingredient_translations)")
            _it_cols = {row[1] for row in cursor.fetchall()}
            if 'source' not in _it_cols:
                try:
                    cursor.execute("ALTER TABLE ingredient_translations ADD COLUMN source TEXT")
                except Exception:
                    pass
            if 'confidence' not in _it_cols:
                try:
                    cursor.execute("ALTER TABLE ingredient_translations ADD COLUMN confidence REAL")
                except Exception:
                    pass
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS recipe_ingredients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipe_id INTEGER NOT NULL,
                    canonical_ingredient_id INTEGER,
                    original_text TEXT NOT NULL,
                    confidence REAL,
                    source TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (recipe_id) REFERENCES saved_recipes(id),
                    FOREIGN KEY (canonical_ingredient_id) REFERENCES canonical_ingredients(id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS translation_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_hash TEXT NOT NULL UNIQUE,
                    name_raw TEXT NOT NULL,
                    lang TEXT NOT NULL,
                    name_en TEXT NOT NULL,
                    source TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            # Seed some canonical ingredients
            try:
                seed_items = [
                    ("light soy sauce", "condiment"),
                    ("soy sauce", "condiment"),
                    ("elbow macaroni", "pasta"),
                    ("garlic", "vegetable"),
                    ("crushed tomatoes", "vegetable"),
                    ("sour cream", "dairy"),
                    ("scallion", "vegetable"),
                    ("smoked tofu", "protein"),
                    ("vegan sausage", "protein"),
                    ("soy milk", "beverage"),
                    ("vegan cheese", "dairy"),
                    ("black pepper", "spice"),
                    ("salt", "spice"),
                    ("water", "beverage"),
                    ("flaxseed", "seed"),
                    ("olive oil", "oil")
                ]
                for name_en, category in seed_items:
                    cursor.execute(
                        "INSERT OR IGNORE INTO canonical_ingredients (name_en, category) VALUES (?, ?)",
                        (name_en, category)
                    )
                # Seed Swedish aliases
                alias_rows = [
                    ("ljus soja", "sv", "light soy sauce"),
                    ("soja", "sv", "soy sauce"),
                    ("idealmakaroner", "sv", "elbow macaroni"),
                    ("gammaldags idealmakaroner", "sv", "elbow macaroni"),
                    ("vitlöksklyftor", "sv", "garlic"),
                    ("vitlök", "sv", "garlic"),
                    ("krossade tomater", "sv", "crushed tomatoes"),
                    ("gräddfil", "sv", "sour cream"),
                    ("salladslök", "sv", "scallion"),
                    ("rökt tofu", "sv", "smoked tofu"),
                    ("veganska korvar", "sv", "vegan sausage"),
                    ("vegansk korv", "sv", "vegan sausage"),
                    ("sojamjölk", "sv", "soy milk"),
                    ("vegansk ost", "sv", "vegan cheese"),
                    ("svartpeppar", "sv", "black pepper"),
                    ("peppar", "sv", "black pepper"),
                    ("salt", "sv", "salt"),
                    ("vatten", "sv", "water"),
                    ("linfrö", "sv", "flaxseed"),
                    ("linfröägg", "sv", "flaxseed")
                ]
                for alias_text, lang, canonical_name in alias_rows:
                    cursor.execute(
                        "INSERT OR IGNORE INTO ingredient_aliases (alias_text, lang, canonical_ingredient_id, confidence) "
                        "VALUES (?, ?, (SELECT id FROM canonical_ingredients WHERE name_en = ?), 1.0)",
                        (alias_text, lang, canonical_name)
                    )
            except Exception as _seed_err:
                logger.warning(f"Seeding canonical ingredients failed: {_seed_err}")
            conn.commit()
            logger.info("Database initialized successfully")

            # Seed canonical tags once
            self._seed_canonical_tags(cursor)
            conn.commit()

            # --- Lightweight crawler caches ---
            try:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS domain_fingerprints (
                        domain TEXT PRIMARY KEY,
                        selectors_json TEXT,
                        schema_json TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ingredient_parse_cache (
                        key TEXT PRIMARY KEY,
                        original TEXT NOT NULL,
                        parsed_json TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS domain_stats (
                        domain TEXT PRIMARY KEY,
                        last_3_fail_rates_json TEXT,
                        prefer_html_list INT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                conn.commit()
            except Exception as _crawl_err:
                logger.warning(f"Crawler cache tables init failed: {_crawl_err}")

    def create_user(self, user_data: UserCreate) -> Optional[User]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if self.get_user_by_email(user_data.email):
                    return None
                
                hashed_password = get_password_hash(user_data.password)
                cursor.execute(
                    "INSERT INTO users (email, full_name, username, hashed_password) VALUES (?, ?, ?, ?)",
                    (user_data.email, user_data.full_name, getattr(user_data, 'username', None), hashed_password)
                )
                user_id = cursor.lastrowid
                if user_id:
                    cursor.execute("INSERT OR IGNORE INTO user_roles (user_id, role) VALUES (?, ?)", (user_id, 'user'))
                conn.commit()
                return self.get_user_by_id(user_id) if user_id else None
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None

    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        user = self.get_user_by_email(email)
        if not user or not user.hashed_password:
            return None

        if not verify_password(password, user.hashed_password):
            return None

        if needs_rehash(user.hashed_password):
            self.update_password(user.id, get_password_hash(password))

        return self.get_user_by_id(user.id)

    def get_user_by_email(self, email: str) -> Optional[UserInDB]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
                row = cursor.fetchone()
                if not row:
                    return None
                user_dict = dict(row)
                cursor.execute("SELECT role FROM user_roles WHERE user_id = ?", (user_dict['id'],))
                roles = [r[0] for r in cursor.fetchall()]
                user_dict['roles'] = roles
                return UserInDB(**user_dict)
        except Exception as e:
            logger.error(f"Error getting user by email '{email}': {e}")
            return None

    # --- Crawler cache helpers ---
    def get_domain_fingerprint(self, domain: str) -> Optional[dict]:
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT selectors_json, schema_json FROM domain_fingerprints WHERE domain=?", (domain,))
                row = c.fetchone()
                if not row:
                    return None
                import json as _json
                selectors = None
                schema = None
                try:
                    selectors = _json.loads(row[0]) if row[0] else None
                except Exception:
                    selectors = None
                try:
                    schema = _json.loads(row[1]) if row[1] else None
                except Exception:
                    schema = None
                return {"selectors": selectors, "schema": schema}
        except Exception as e:
            logger.warning(f"get_domain_fingerprint failed for {domain}: {e}")
            return None

    def upsert_domain_fingerprint(self, domain: str, selectors: Optional[list] = None, schema: Optional[dict] = None):
        try:
            import json as _json
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute(
                    """
                    INSERT INTO domain_fingerprints(domain, selectors_json, schema_json, updated_at)
                    VALUES(?,?,?,CURRENT_TIMESTAMP)
                    ON CONFLICT(domain) DO UPDATE SET
                        selectors_json=COALESCE(excluded.selectors_json, domain_fingerprints.selectors_json),
                        schema_json=COALESCE(excluded.schema_json, domain_fingerprints.schema_json),
                        updated_at=CURRENT_TIMESTAMP
                    """,
                    (domain, _json.dumps(selectors) if selectors else None, _json.dumps(schema) if schema else None)
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"upsert_domain_fingerprint failed for {domain}: {e}")

    def get_ingredient_parse_cache(self, key: str) -> Optional[str]:
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT parsed_json FROM ingredient_parse_cache WHERE key=?", (key,))
                row = c.fetchone()
                return row[0] if row else None
        except Exception:
            return None

    def upsert_ingredient_parse_cache(self, key: str, original: str, parsed_json: str):
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute(
                    """
                    INSERT INTO ingredient_parse_cache(key, original, parsed_json, created_at)
                    VALUES(?,?,?,CURRENT_TIMESTAMP)
                    ON CONFLICT(key) DO UPDATE SET parsed_json=excluded.parsed_json
                    """,
                    (key, original, parsed_json)
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"upsert_ingredient_parse_cache failed: {e}")

    # --- Ingredient utilities ---
    def get_all_canonical(self) -> list[dict]:
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT id, name_en FROM canonical_ingredients")
            rows = c.fetchall()
            return [{"id": int(r[0]), "name_en": r[1]} for r in rows]

    def get_or_create_canonical(self, name_en: str) -> Optional[int]:
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT id FROM canonical_ingredients WHERE LOWER(name_en)=LOWER(?)", (name_en,))
                row = c.fetchone()
                if row:
                    return int(row[0])
                c.execute("INSERT INTO canonical_ingredients (name_en) VALUES (?)", (name_en,))
                conn.commit()
                return int(c.lastrowid)
        except Exception as e:
            logger.error(f"get_or_create_canonical failed for '{name_en}': {e}")
            return None

    def upsert_alias(self, alias_text: str, lang: str, canonical_id: int, confidence: float, source: str = "auto"):
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute(
                    "INSERT OR IGNORE INTO ingredient_aliases (alias_text, lang, canonical_ingredient_id, confidence, notes) VALUES (?, ?, ?, ?, ?)",
                    (alias_text.strip().lower(), lang.strip().lower(), canonical_id, confidence, source),
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"upsert_alias failed: {e}")

    def upsert_translation(self, canonical_id: int, lang: str, translated_name: str, source: Optional[str] = None, confidence: Optional[float] = None):
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute(
                    "INSERT OR REPLACE INTO ingredient_translations (canonical_ingredient_id, lang, translated_name, source, confidence) VALUES (?, ?, ?, ?, ?)",
                    (canonical_id, lang.strip().lower(), translated_name.strip(), source, confidence),
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"upsert_translation failed: {e}")

    def get_translations_for_lang(self, lang: str) -> dict[int, str]:
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute(
                "SELECT canonical_ingredient_id, translated_name FROM ingredient_translations WHERE lang = ?",
                (lang.strip().lower(),),
            )
            return {int(row[0]): row[1] for row in c.fetchall()}

    def get_translation_for(self, canonical_id: int, lang: str) -> Optional[str]:
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT translated_name FROM ingredient_translations WHERE canonical_ingredient_id=? AND lang=? LIMIT 1", (canonical_id, lang.strip().lower()))
                row = c.fetchone()
                return row[0] if row else None
        except Exception:
            return None

    def get_alias_for_canonical(self, canonical_id: int, lang: str) -> Optional[tuple[str, float]]:
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute(
                    "SELECT ia.alias_text, ia.confidence FROM ingredient_aliases ia WHERE ia.canonical_ingredient_id=? AND ia.lang=? ORDER BY ia.confidence DESC LIMIT 1",
                    (canonical_id, lang.strip().lower()),
                )
                row = c.fetchone()
                if row:
                    return (row[0], float(row[1] or 0.9))
        except Exception:
            pass
        return None

    def get_canonical_name(self, canonical_id: int) -> Optional[str]:
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT name_en FROM canonical_ingredients WHERE id=?", (canonical_id,))
                row = c.fetchone()
                return row[0] if row else None
        except Exception:
            return None

    def insert_recipe_ingredient(self, recipe_id: int, original_text: str, canonical_id: Optional[int], confidence: Optional[float], source: Optional[str]):
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute(
                    "INSERT INTO recipe_ingredients (recipe_id, original_text, canonical_ingredient_id, confidence, source) VALUES (?, ?, ?, ?, ?)",
                    (recipe_id, original_text, canonical_id, confidence, source),
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"insert_recipe_ingredient failed: {e}")

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
                row = cursor.fetchone()
                if not row:
                    return None
                user_dict = dict(row)
                cursor.execute("SELECT role FROM user_roles WHERE user_id = ?", (user_id,))
                roles = [r[0] for r in cursor.fetchall()]
                user_dict['roles'] = roles
                return User(**user_dict)
        except Exception as e:
            logger.error(f"Error getting user by ID {user_id}: {e}")
            return None

    def get_user_by_username(self, username: str) -> Optional[User]:
        try:
            if not username:
                return None
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (username,))
                row = cursor.fetchone()
                if not row:
                    return None
                user_dict = dict(row)
                # followers/following counts
                try:
                    cursor.execute("SELECT COUNT(*) FROM user_follows WHERE followee_id = ?", (user_dict['id'],))
                    user_dict['followers_count'] = int(cursor.fetchone()[0] or 0)
                    cursor.execute("SELECT COUNT(*) FROM user_follows WHERE follower_id = ?", (user_dict['id'],))
                    user_dict['following_count'] = int(cursor.fetchone()[0] or 0)
                except Exception:
                    user_dict['followers_count'] = 0
                    user_dict['following_count'] = 0
                # roles
                cursor.execute("SELECT role FROM user_roles WHERE user_id = ?", (user_dict['id'],))
                roles = [r[0] for r in cursor.fetchall()]
                user_dict['roles'] = roles
                return User(**user_dict)
        except Exception as e:
            logger.error(f"Error getting user by username '{username}': {e}")
            return None
    
    def update_password(self, user_id: int, new_hashed_password: str):
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET hashed_password = ? WHERE id = ?",
                    (new_hashed_password, user_id)
                )
                conn.commit()
                logger.info(f"Password for user {user_id} has been securely updated.")
        except Exception as e:
            logger.error(f"Error updating password for user {user_id}: {e}")

    def create_oauth_user(self, email: str, full_name: str, google_id: str, avatar_url: Optional[str] = None) -> Optional[User]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # Some older DBs may have NOT NULL constraint on hashed_password. Insert empty string to satisfy it.
                try:
                    cursor.execute(
                        "INSERT INTO users (email, full_name, username, hashed_password, google_id, avatar_url, auth_provider) VALUES (?, ?, ?, ?, ?, ?, 'google')",
                        (email, full_name, None, '', google_id, avatar_url)
                    )
                except Exception:
                    # Fallback for schema without NOT NULL on hashed_password
                    cursor.execute(
                        "INSERT INTO users (email, full_name, google_id, avatar_url, auth_provider) VALUES (?, ?, ?, ?, 'google')",
                        (email, full_name, google_id, avatar_url)
                    )
                user_id = cursor.lastrowid
                cursor.execute("INSERT OR IGNORE INTO user_roles (user_id, role) VALUES (?, ?)", (user_id, 'user'))
                conn.commit()
                return self.get_user_by_id(user_id)
        except Exception as e:
            logger.error(f"Error creating OAuth user: {e}")
            return None

    def save_recipe(self, user_id: int, source_url: str, recipe_content: dict) -> Optional[SavedRecipe]:
        try:
            # Normalize recipe content before saving
            if recipe_content.get('img'):
                recipe_content['image_url'] = recipe_content.pop('img')
            if recipe_content.get('prep_time_minutes') is not None:
                recipe_content['prep_time'] = f"{recipe_content.pop('prep_time_minutes')} min"
            if recipe_content.get('cook_time_minutes') is not None:
                recipe_content['cook_time'] = f"{recipe_content.pop('cook_time_minutes')} min"
            if recipe_content.get('nutrition'):
                recipe_content['nutritional_information'] = recipe_content.pop('nutrition')
            
            # Ensure image_url is preserved and not overwritten
            if recipe_content.get('image_url') and not recipe_content.get('thumbnail_path'):
                recipe_content['thumbnail_path'] = recipe_content['image_url']

            # Coerce ingredients/instructions into structured objects if strings were provided
            def _coerce_ingredients(items):
                coerced = []
                for item in items or []:
                    if isinstance(item, dict):
                        name = (item.get('name') or item.get('ingredient') or '').strip()
                        quantity = (item.get('quantity') or '').strip()
                        notes = item.get('notes')
                        coerced.append({ 'name': name, 'quantity': quantity, 'notes': notes })
                    else:
                        text = str(item).strip()
                        if not text:
                            continue
                        coerced.append({ 'name': text, 'quantity': '', 'notes': None })
                return coerced
            def _coerce_instructions(items):
                coerced = []
                for idx, item in enumerate(items or [], start=1):
                    if isinstance(item, dict):
                        step_num = int(item.get('step') or idx)
                        desc = (item.get('description') or '').strip() or f'Step {idx}'
                        coerced.append({ 'step': step_num, 'description': desc, 'image_path': item.get('image_path') })
                    else:
                        text = str(item).strip()
                        if not text:
                            continue
                        coerced.append({ 'step': idx, 'description': text, 'image_path': None })
                return coerced

            if isinstance(recipe_content.get('ingredients'), list):
                recipe_content['ingredients'] = _coerce_ingredients(recipe_content['ingredients'])
            if isinstance(recipe_content.get('instructions'), list):
                recipe_content['instructions'] = _coerce_instructions(recipe_content['instructions'])

            # Validate with Pydantic model before serializing
            validated_content = RecipeContent.model_validate(recipe_content)
            recipe_json = validated_content.model_dump_json()

            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO saved_recipes (user_id, source_url, recipe_content) VALUES (?, ?, ?)",
                    (user_id, source_url, recipe_json)
                )
                recipe_id = cursor.lastrowid
                conn.commit()
                return self.get_saved_recipe(recipe_id) if recipe_id else None
        except Exception as e:
            logger.error(f"Error saving recipe for user {user_id}: {e}")
            return None

    def get_saved_recipe(self, recipe_id: int) -> Optional[SavedRecipe]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT sr.*, u.username as owner_username, u.full_name as owner_full_name, u.avatar_url as owner_avatar
                    FROM saved_recipes sr
                    LEFT JOIN users u ON u.id = sr.user_id
                    WHERE sr.id = ?
                """, (recipe_id,))
                row = cursor.fetchone()
                if row:
                    try:
                        tags = self.list_recipe_tags(row['id'])
                    except Exception:
                        tags = {"approved": [], "pending": []}
                    
                    # Debug: Print the row data
                    print(f"DEBUG: Recipe {recipe_id} - owner_username: {row['owner_username']}, owner_full_name: {row['owner_full_name']}, owner_avatar: {row['owner_avatar']}")
                    
                    return SavedRecipe(
                        id=row['id'],
                        user_id=row['user_id'],
                        source_url=row['source_url'],
                        created_at=datetime.fromisoformat(row["created_at"]),
                        recipe_content=RecipeContent.model_validate_json(row['recipe_content']),
                        tags=tags,
                        owner_username=row['owner_username'] if row['owner_username'] else None,
                        owner_full_name=row['owner_full_name'] if row['owner_full_name'] else None,
                        owner_avatar=row['owner_avatar'] if row['owner_avatar'] else None
                    )
                return None
        except Exception as e:
            logger.error(f"Error getting saved recipe {recipe_id}: {e}")
            return None

    def get_user_saved_recipes(self, user_id: int, sort: str = "latest") -> List[SavedRecipe]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if sort == 'rating_desc':
                    order = "ORDER BY rating_average DESC, rating_count DESC, created_at DESC"
                elif sort == 'rating_count_desc':
                    order = "ORDER BY rating_count DESC, rating_average DESC, created_at DESC"
                else:
                    order = "ORDER BY created_at DESC"
                cursor.execute(f"""
                    SELECT sr.*, u.username as owner_username, u.full_name as owner_full_name, u.avatar_url as owner_avatar
                    FROM saved_recipes sr
                    LEFT JOIN users u ON u.id = sr.user_id
                    WHERE sr.user_id = ? {order}
                """, (user_id,))
                rows = cursor.fetchall()
                recipes = []
                for row in rows:
                    content_dict = json.loads(row['recipe_content'])

                    # Definitive image URL normalization
                    def _normalize_port(url: str) -> str:
                        try:
                            if isinstance(url, str):
                                if url.startswith('http://127.0.0.1:8000'):
                                    return url.replace('http://127.0.0.1:8000', 'http://127.0.0.1:8001')
                                if url.startswith('http://localhost:8000'):
                                    return url.replace('http://localhost:8000', 'http://localhost:8001')
                        except Exception:
                            pass
                        return url

                    image = content_dict.get('image_url') or content_dict.get('img') or content_dict.get('thumbnail_path')
                    image = _normalize_port(image) if image else image
                    if image:
                        content_dict['image_url'] = image
                        content_dict['thumbnail_path'] = image

                    # Normalize instruction step images if present
                    if isinstance(content_dict.get('instructions'), list):
                        for inst in content_dict['instructions']:
                            if isinstance(inst, dict) and inst.get('image_path'):
                                inst['image_path'] = _normalize_port(inst['image_path'])

                    # Attach tags so frontend cards can show chips immediately
                    try:
                        tags = self.list_recipe_tags(row['id'])
                    except Exception:
                        tags = {"approved": [], "pending": []}

                    recipes.append(
                        SavedRecipe(
                            id=row['id'],
                            user_id=row['user_id'],
                            source_url=row['source_url'],
                            created_at=datetime.fromisoformat(row["created_at"]),
                            recipe_content=RecipeContent.model_validate(content_dict),
                            tags=tags,
                            owner_username=row['owner_username'] if row['owner_username'] else None,
                            owner_full_name=row['owner_full_name'] if row['owner_full_name'] else None,
                            owner_avatar=row['owner_avatar'] if row['owner_avatar'] else None
                        )
                    )

                return recipes
        except Exception as e:
            logger.error(f"Error getting saved recipes for user {user_id}: {e}")
            return []

    def get_all_saved_recipes(self, sort: str = "latest") -> List[SavedRecipe]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if sort == 'rating_desc':
                    order = "ORDER BY rating_average DESC, rating_count DESC, created_at DESC"
                elif sort == 'rating_count_desc':
                    order = "ORDER BY rating_count DESC, rating_average DESC, created_at DESC"
                else:
                    order = "ORDER BY created_at DESC"
                cursor.execute(f"""
                    SELECT sr.*, u.username as owner_username, u.full_name as owner_full_name, u.avatar_url as owner_avatar
                    FROM saved_recipes sr
                    LEFT JOIN users u ON u.id = sr.user_id
                    {order}
                """)
                rows = cursor.fetchall()
                recipes: List[SavedRecipe] = []
                for row in rows:
                    content_dict = json.loads(row['recipe_content'])
                    def _normalize_port(url: str) -> str:
                        try:
                            if isinstance(url, str):
                                if url.startswith('http://127.0.0.1:8000'):
                                    return url.replace('http://127.0.0.1:8000', 'http://127.0.0.1:8001')
                                if url.startswith('http://localhost:8000'):
                                    return url.replace('http://localhost:8000', 'http://localhost:8001')
                        except Exception:
                            pass
                        return url
                    image = content_dict.get('image_url') or content_dict.get('img') or content_dict.get('thumbnail_path')
                    image = _normalize_port(image) if image else image
                    if image:
                        content_dict['image_url'] = image
                        content_dict['thumbnail_path'] = image
                    if isinstance(content_dict.get('instructions'), list):
                        for inst in content_dict['instructions']:
                            if isinstance(inst, dict) and inst.get('image_path'):
                                inst['image_path'] = _normalize_port(inst['image_path'])
                    try:
                        tags = self.list_recipe_tags(row['id'])
                    except Exception:
                        tags = {"approved": [], "pending": []}
                    recipes.append(
                        SavedRecipe(
                            id=row['id'],
                            user_id=row['user_id'],
                            source_url=row['source_url'],
                            created_at=datetime.fromisoformat(row["created_at"]),
                            recipe_content=RecipeContent.model_validate(content_dict),
                            tags=tags,
                            owner_username=row['owner_username'] if 'owner_username' in row else None,
                            owner_full_name=row['owner_full_name'] if 'owner_full_name' in row else None,
                            owner_avatar=row['owner_avatar'] if 'owner_avatar' in row else None
                        )
                    )
                return recipes
        except Exception as e:
            logger.error(f"Error getting all saved recipes: {e}")
            return []

    # Collections API
    def create_collection(self, owner_id: int, title: str, description: Optional[str], visibility: str, image_url: Optional[str]) -> Optional[int]:
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO collections (owner_id, title, description, visibility, image_url) VALUES (?,?,?,?,?)", (owner_id, title, description, visibility, image_url))
            conn.commit()
            return c.lastrowid

    def list_collections(self, viewer_id: Optional[int]) -> List[dict]:
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute(
                """
                SELECT col.id, col.owner_id, col.title, col.description, col.image_url, col.visibility, col.created_at,
                       col.rating_average, col.rating_count, col.likes_count, col.followers_count,
                       u.full_name as owner_name, u.avatar_url as owner_avatar, u.username as owner_username,
                       (SELECT COUNT(*) FROM collection_recipes cr WHERE cr.collection_id = col.id) as recipes_count,
                       CASE WHEN ? IS NULL THEN 0 ELSE EXISTS(SELECT 1 FROM collection_likes cl WHERE cl.collection_id = col.id AND cl.user_id = ?) END as liked_by_me,
                       CASE WHEN ? IS NULL THEN 0 ELSE EXISTS(SELECT 1 FROM collection_follows cf WHERE cf.collection_id = col.id AND cf.user_id = ?) END as followed_by_me
                FROM collections col
                LEFT JOIN users u ON u.id = col.owner_id
                WHERE col.visibility = 'public' OR col.owner_id = ?
                ORDER BY col.created_at DESC
                """,
                (viewer_id, viewer_id, viewer_id, viewer_id, viewer_id or 0,)
            )
            rows = c.fetchall()
            out = []
            for r in rows:
                d = dict(r)
                # Fallback cover: adopt first recipe image if collection has no image yet
                if not d.get('image_url'):
                    try:
                        c.execute(
                            """
                            SELECT sr.recipe_content FROM saved_recipes sr
                            JOIN collection_recipes cr ON cr.recipe_id = sr.id
                            WHERE cr.collection_id = ?
                            ORDER BY cr.created_at ASC LIMIT 1
                            """,
                            (d['id'],)
                        )
                        rr = c.fetchone()
                        if rr:
                            content = json.loads(rr[0]) if isinstance(rr[0], str) else (rr[0] or {})
                            image = content.get('image_url') or content.get('img') or content.get('thumbnail_path')
                            def _normalize_port(url: str) -> str:
                                try:
                                    if isinstance(url, str):
                                        if url.startswith('http://127.0.0.1:8000'):
                                            return url.replace('http://127.0.0.1:8000', 'http://127.0.0.1:8001')
                                        if url.startswith('http://localhost:8000'):
                                            return url.replace('http://localhost:8000', 'http://localhost:8001')
                                except Exception:
                                    pass
                                return url
                            image = _normalize_port(image) if image else image
                            if image:
                                d['image_url'] = image
                    except Exception:
                        pass
                d['liked_by_me'] = bool(d.get('liked_by_me'))
                d['followed_by_me'] = bool(d.get('followed_by_me'))
                from models.types import Collection
                out.append(Collection(**d))
            return out

    def list_user_public_collections(self, owner_username: str, viewer_id: Optional[int]) -> List[dict]:
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute(
                """
                SELECT col.id, col.owner_id, col.title, col.description, col.image_url, col.visibility, col.created_at,
                       col.rating_average, col.rating_count, col.likes_count, col.followers_count,
                       u.full_name as owner_name, u.avatar_url as owner_avatar, u.username as owner_username,
                       (SELECT COUNT(*) FROM collection_recipes cr WHERE cr.collection_id = col.id) as recipes_count,
                       CASE WHEN ? IS NULL THEN 0 ELSE EXISTS(SELECT 1 FROM collection_likes cl WHERE cl.collection_id = col.id AND cl.user_id = ?) END as liked_by_me,
                       CASE WHEN ? IS NULL THEN 0 ELSE EXISTS(SELECT 1 FROM collection_follows cf WHERE cf.collection_id = col.id AND cf.user_id = ?) END as followed_by_me
                FROM collections col
                JOIN users u ON u.id = col.owner_id
                WHERE (col.visibility = 'public' OR col.owner_id = ?) AND LOWER(u.username) = LOWER(?)
                ORDER BY col.created_at DESC
                """,
                (viewer_id, viewer_id, viewer_id, viewer_id, viewer_id or 0, owner_username,)
            )
            rows = c.fetchall()
            out = []
            for r in rows:
                d = dict(r)
                # Fallback cover from first recipe if missing
                if not d.get('image_url'):
                    try:
                        c.execute(
                            """
                            SELECT sr.recipe_content FROM saved_recipes sr
                            JOIN collection_recipes cr ON cr.recipe_id = sr.id
                            WHERE cr.collection_id = ?
                            ORDER BY cr.created_at ASC LIMIT 1
                            """,
                            (d['id'],)
                        )
                        rr = c.fetchone()
                        if rr:
                            content = json.loads(rr[0]) if isinstance(rr[0], str) else (rr[0] or {})
                            image = content.get('image_url') or content.get('img') or content.get('thumbnail_path')
                            def _normalize_port(url: str) -> str:
                                try:
                                    if isinstance(url, str):
                                        if url.startswith('http://127.0.0.1:8000'):
                                            return url.replace('http://127.0.0.1:8000', 'http://127.0.0.1:8001')
                                        if url.startswith('http://localhost:8000'):
                                            return url.replace('http://localhost:8000', 'http://localhost:8001')
                                except Exception:
                                    pass
                                return url
                            image = _normalize_port(image) if image else image
                            if image:
                                d['image_url'] = image
                    except Exception:
                        pass
                d['liked_by_me'] = bool(d.get('liked_by_me'))
                d['followed_by_me'] = bool(d.get('followed_by_me'))
                from models.types import Collection
                out.append(Collection(**d))
            return out

    def add_recipe_to_collection(self, collection_id: int, recipe_id: int):
        with self.get_connection() as conn:
            c = conn.cursor()
            try:
                c.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM collection_recipes WHERE collection_id = ?", (collection_id,))
                next_pos_row = c.fetchone()
                next_pos = int(next_pos_row[0] if next_pos_row and next_pos_row[0] is not None else 0)
            except Exception:
                next_pos = 0
            c.execute("INSERT OR IGNORE INTO collection_recipes (collection_id, recipe_id, position) VALUES (?,?,?)", (collection_id, recipe_id, next_pos))
            # If the collection has no cover image yet, adopt the recipe's image as cover
            try:
                c.execute("SELECT image_url FROM collections WHERE id = ?", (collection_id,))
                row = c.fetchone()
                current_cover = row[0] if row else None
                if not current_cover:
                    c.execute("SELECT recipe_content FROM saved_recipes WHERE id = ?", (recipe_id,))
                    r = c.fetchone()
                    if r:
                        try:
                            content = json.loads(r[0])
                        except Exception:
                            content = {}
                        image = content.get('image_url') or content.get('img') or content.get('thumbnail_path')
                        # Normalize port like elsewhere
                        def _normalize_port(url: str) -> str:
                            try:
                                if isinstance(url, str):
                                    if url.startswith('http://127.0.0.1:8000'):
                                        return url.replace('http://127.0.0.1:8000', 'http://127.0.0.1:8001')
                                    if url.startswith('http://localhost:8000'):
                                        return url.replace('http://localhost:8000', 'http://localhost:8001')
                            except Exception:
                                pass
                            return url
                        image = _normalize_port(image) if image else image
                        if image:
                            c.execute("UPDATE collections SET image_url = ? WHERE id = ?", (image, collection_id))
            except Exception:
                pass
            conn.commit()
            return {"ok": True}

    def list_collection_recipes(self, collection_id: int, user_id: Optional[int] = None) -> List[SavedRecipe]:
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute(
                    """
                    SELECT sr.*, 
                           u.username as owner_username,
                           u.full_name as owner_full_name,
                           COALESCE(r.avg_rating, 0.0) as rating_average,
                           COALESCE(r.rating_count, 0) as rating_count,
                           COALESCE(l.likes_count, 0) as likes_count,
                           CASE WHEN rl.recipe_id IS NOT NULL THEN 1 ELSE 0 END as liked_by_me
                    FROM saved_recipes sr
                    JOIN collection_recipes cr ON cr.recipe_id = sr.id
                    LEFT JOIN users u ON u.id = sr.user_id
                    LEFT JOIN (
                        SELECT recipe_id,
                               ROUND(AVG(CAST(value AS FLOAT)), 2) as avg_rating,
                               COUNT(*) as rating_count
                        FROM ratings
                        GROUP BY recipe_id
                    ) r ON r.recipe_id = sr.id
                    LEFT JOIN (
                        SELECT recipe_id,
                               COUNT(*) as likes_count
                        FROM recipe_likes
                        GROUP BY recipe_id
                    ) l ON l.recipe_id = sr.id
                    LEFT JOIN recipe_likes rl ON rl.recipe_id = sr.id AND rl.user_id = ?
                    WHERE cr.collection_id = ?
                    ORDER BY COALESCE(cr.position, 1000000) ASC, cr.created_at DESC
                    """,
                    (user_id, collection_id)
                )
                rows = c.fetchall()
                items: List[SavedRecipe] = []
                for row in rows:
                    content_dict = json.loads(row['recipe_content'])
                    # Normalize image url
                    def _normalize_port(url: str) -> str:
                        try:
                            if isinstance(url, str):
                                if url.startswith('http://127.0.0.1:8000'):
                                    return url.replace('http://127.0.0.1:8000', 'http://127.0.0.1:8001')
                                if url.startswith('http://localhost:8000'):
                                    return url.replace('http://localhost:8000', 'http://localhost:8001')
                        except Exception:
                            pass
                        return url
                    image = content_dict.get('image_url') or content_dict.get('img') or content_dict.get('thumbnail_path')
                    image = _normalize_port(image) if image else image
                    if image:
                        content_dict['image_url'] = image
                        content_dict['thumbnail_path'] = image
                    try:
                        tags = self.list_recipe_tags(row['id'])
                    except Exception:
                        tags = {"approved": [], "pending": []}
                    items.append(
                        SavedRecipe(
                            id=row['id'],
                            user_id=row['user_id'],
                            source_url=row['source_url'],
                            created_at=datetime.fromisoformat(row['created_at']),
                            recipe_content=RecipeContent.model_validate(content_dict),
                            tags=tags,
                            rating_average=row['rating_average'] if 'rating_average' in row else 0.0,
                            rating_count=row['rating_count'] if 'rating_count' in row else 0,
                            likes_count=row['likes_count'] if 'likes_count' in row else 0,
                            liked_by_me=bool(row['liked_by_me']) if 'liked_by_me' in row else False,
                            owner_username=row['owner_username'] if 'owner_username' in row else None,
                            owner_full_name=row['owner_full_name'] if 'owner_full_name' in row else None
                        )
                    )
                return items
        except Exception as e:
            logger.error(f"Error listing recipes for collection {collection_id}: {e}")
            return []

    def update_collection(self, collection_id: int, **fields) -> bool:
        allowed = {'title', 'description', 'visibility', 'image_url'}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return False
        sets = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [collection_id]
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute(f"UPDATE collections SET {sets} WHERE id = ?", values)
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update collection {collection_id}: {e}")
            return False

    def remove_recipe_from_collection(self, collection_id: int, recipe_id: int) -> bool:
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute("DELETE FROM collection_recipes WHERE collection_id = ? AND recipe_id = ?", (collection_id, recipe_id))
                # Compact positions
                try:
                    c.execute("SELECT recipe_id FROM collection_recipes WHERE collection_id = ? ORDER BY COALESCE(position, 1000000) ASC, created_at DESC", (collection_id,))
                    ids = [row[0] for row in c.fetchall()]
                    for idx, rid in enumerate(ids):
                        c.execute("UPDATE collection_recipes SET position = ? WHERE collection_id = ? AND recipe_id = ?", (idx, collection_id, rid))
                except Exception:
                    pass
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to remove recipe {recipe_id} from collection {collection_id}: {e}")
            return False

    def reorder_collection_recipes(self, collection_id: int, recipe_ids: List[int]) -> bool:
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                for idx, rid in enumerate(recipe_ids or []):
                    c.execute("UPDATE collection_recipes SET position = ? WHERE collection_id = ? AND recipe_id = ?", (idx, collection_id, rid))
                # Update cover image from first recipe
                if recipe_ids:
                    top_id = recipe_ids[0]
                    try:
                        c.execute("SELECT recipe_content FROM saved_recipes WHERE id = ?", (top_id,))
                        r = c.fetchone()
                        if r:
                            content = json.loads(r[0]) if isinstance(r[0], str) else (r[0] or {})
                            image = content.get('image_url') or content.get('img') or content.get('thumbnail_path')
                            def _normalize_port(url: str) -> str:
                                try:
                                    if isinstance(url, str):
                                        if url.startswith('http://127.0.0.1:8000'):
                                            return url.replace('http://127.0.0.1:8000', 'http://127.0.0.1:8001')
                                        if url.startswith('http://localhost:8000'):
                                            return url.replace('http://localhost:8000', 'http://localhost:8001')
                                except Exception:
                                    pass
                                return url
                            image = _normalize_port(image) if image else image
                            if image:
                                c.execute("UPDATE collections SET image_url = ? WHERE id = ?", (image, collection_id))
                    except Exception:
                        pass
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to reorder recipes for collection {collection_id}: {e}")
            return False

    # --- Tagging helpers ---
    def _normalize_keyword(self, raw: str) -> Optional[str]:
        if not raw or not isinstance(raw, str):
            return None
        s = raw.strip().lower()
        try:
            s = s.encode('ascii', 'ignore').decode('ascii')
        except Exception:
            pass
        # keep only letters/numbers
        import re
        s = re.sub(r'[^a-z0-9]+', '', s)
        return s or None

    def _seed_canonical_tags(self, cursor):
        canonical = {
            'dish': [
                'pasta','soup','stew','salad','sandwich','wrap','pizza','pie','casserole','burger','tacos','stirfry','bowl','onepot','baked','pancake','crepe','waffle','omelette','sushi','rice','noodle','curry','gratin','skewer','stewpot','flatbread','quiche','stirred','dumpling','stewpan'
            ],
            'method': [
                'grilled','fried','roasted','boiled','steamed','baked','raw','poached','braised','slowcooked','barbecue','smoked','blanched','seared'
            ],
            'meal': [
                'breakfast','brunch','lunch','dinner','snack','dessert','side','appetizer','main','drink','cocktail','mocktail'
            ],
            'cuisine': [
                'italian','mexican','indian','thai','japanese','chinese','french','greek','turkish','mediterranean','swedish','vietnamese','korean','moroccan','american','british','german','spanish','middleeastern'
            ],
            'diet': [
                'vegan','vegetarian','pescatarian','glutenfree','dairyfree','lowcarb','highprotein','keto','paleo','sugarfree'
            ],
            'theme': [
                'quick','easy','budget','festive','seasonal','holiday','summer','winter','autumn','spring','spicy','sweet','savory','comfortfood','healthy','kidfriendly','fingerfood','mealprep','zesty','seafood','fastfood'
            ],
            'ingredient': [
                'chicken','eggs','cheese','fruits','wine'
            ]
        }
        for ttype, words in canonical.items():
            for kw in words:
                try:
                    cursor.execute("INSERT OR IGNORE INTO tags (keyword, type, active) VALUES (?, ?, 1)", (kw, ttype))
                except Exception:
                    pass

    def search_tags(self, query: Optional[str] = None) -> List[dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if query:
                q = f"%{self._normalize_keyword(query) or ''}%"
                cursor.execute("SELECT id, keyword, type FROM tags WHERE active=1 AND keyword LIKE ? ORDER BY type, keyword", (q,))
            else:
                cursor.execute("SELECT id, keyword, type FROM tags WHERE active=1 ORDER BY type, keyword")
            rows = cursor.fetchall()
            return [dict(id=r[0], keyword=r[1], type=r[2]) for r in rows]

    def _map_to_canonical_tag_id(self, keyword: str) -> Optional[int]:
        key = self._normalize_keyword(keyword)
        if not key:
            return None
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT id FROM tags WHERE keyword = ? AND active=1", (key,))
            row = c.fetchone()
            if row:
                return row[0]
            c.execute("SELECT tag_id FROM tag_synonyms WHERE alias = ?", (key,))
            row = c.fetchone()
            return row[0] if row else None

    def get_recipe_owner_id(self, recipe_id: int) -> Optional[int]:
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT user_id FROM saved_recipes WHERE id = ?", (recipe_id,))
            r = c.fetchone()
            return r[0] if r else None

    def is_tag_edit_locked(self, recipe_id: int) -> bool:
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT locked FROM recipe_tag_locks WHERE recipe_id = ?", (recipe_id,))
            r = c.fetchone()
            return bool(r[0]) if r else False

    def set_tag_lock(self, recipe_id: int, locked: bool, by_user_id: Optional[int], reason: Optional[str]):
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO recipe_tag_locks (recipe_id, locked, locked_by, reason) VALUES (?, ?, ?, ?) ON CONFLICT(recipe_id) DO UPDATE SET locked=excluded.locked, locked_by=excluded.locked_by, reason=excluded.reason, created_at=CURRENT_TIMESTAMP", (recipe_id, int(locked), by_user_id, reason))
            conn.commit()

    def list_recipe_tags(self, recipe_id: int) -> dict:
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT rt.id, rt.status, t.id, t.keyword, t.type FROM recipe_tags rt JOIN tags t ON t.id=rt.tag_id WHERE rt.recipe_id = ?", (recipe_id,))
            rows = c.fetchall()
            approved = []
            pending = []
            for rid, status, tag_id, keyword, ttype in rows:
                item = {"id": rid, "tagId": tag_id, "keyword": keyword, "type": ttype, "status": status}
                (approved if status == 'approved' else pending).append(item)
            return {"approved": approved, "pending": pending}

    def add_recipe_tags(self, recipe_id: int, user_id: int, keywords: List[str], direct: bool) -> dict:
        if not keywords:
            return {"added": [], "pending": [], "invalid": []}
        owner_id = self.get_recipe_owner_id(recipe_id)
        status = 'approved' if direct else 'pending'
        added, pend, invalid = [], [], []
        with self.get_connection() as conn:
            c = conn.cursor()
            for kw in keywords:
                tag_id = self._map_to_canonical_tag_id(kw)
                if not tag_id:
                    invalid.append(kw)
                    continue
                try:
                    c.execute("INSERT OR IGNORE INTO recipe_tags (recipe_id, tag_id, status, suggested_by, approved_by) VALUES (?, ?, ?, ?, NULL)", (recipe_id, tag_id, status, user_id))
                    c.execute("INSERT INTO tag_change_log (recipe_id, user_id, action, tag_id, details) VALUES (?, ?, ?, ?, ?)", (recipe_id, user_id, 'add' if direct else 'suggest', tag_id, None))
                    if status == 'approved':
                        added.append(kw)
                    else:
                        pend.append(kw)
                except Exception:
                    pass
            conn.commit()
        return {"added": added, "pending": pend, "invalid": invalid}

    def remove_recipe_tag(self, recipe_id: int, user_id: int, keyword: str):
        tag_id = self._map_to_canonical_tag_id(keyword)
        if not tag_id:
            return {"removed": False, "reason": "invalid"}
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM recipe_tags WHERE recipe_id = ? AND tag_id = ?", (recipe_id, tag_id))
            c.execute("INSERT INTO tag_change_log (recipe_id, user_id, action, tag_id, details) VALUES (?, ?, 'remove', ?, NULL)", (recipe_id, user_id, tag_id))
            conn.commit()
            return {"removed": True}

    def approve_recipe_tag(self, recipe_id: int, user_id: int, keyword: str):
        tag_id = self._map_to_canonical_tag_id(keyword)
        if not tag_id:
            return {"ok": False, "reason": "invalid"}
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE recipe_tags SET status='approved', approved_by=? WHERE recipe_id=? AND tag_id=?", (user_id, recipe_id, tag_id))
            c.execute("INSERT INTO tag_change_log (recipe_id, user_id, action, tag_id, details) VALUES (?, ?, 'approve', ?, NULL)", (recipe_id, user_id, tag_id))
            conn.commit()
            return {"ok": True}

    def reject_recipe_tag(self, recipe_id: int, user_id: int, keyword: str):
        tag_id = self._map_to_canonical_tag_id(keyword)
        if not tag_id:
            return {"ok": False, "reason": "invalid"}
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE recipe_tags SET status='rejected', approved_by=NULL WHERE recipe_id=? AND tag_id=?", (recipe_id, tag_id))
            c.execute("INSERT INTO tag_change_log (recipe_id, user_id, action, tag_id, details) VALUES (?, ?, 'reject', ?, NULL)", (recipe_id, user_id, tag_id))
            conn.commit()
            return {"ok": True}

    def list_tag_history(self, recipe_id: int) -> List[dict]:
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute(
                """
                SELECT l.id, l.user_id, u.full_name, l.action, l.tag_id, t.keyword, l.details, l.created_at
                FROM tag_change_log l
                LEFT JOIN users u ON u.id = l.user_id
                LEFT JOIN tags t ON t.id = l.tag_id
                WHERE l.recipe_id = ?
                ORDER BY l.created_at DESC, l.id DESC
                """,
                (recipe_id,)
            )
            rows = c.fetchall()
            return [
                {
                    "id": r[0],
                    "userId": r[1],
                    "userName": r[2],
                    "action": r[3],
                    "tagId": r[4],
                    "keyword": r[5],
                    "details": r[6],
                    "createdAt": r[7],
                }
                for r in rows
            ]

    def add_tag_synonym(self, alias: str, canonical_keyword: str) -> dict:
        alias_norm = self._normalize_keyword(alias)
        tag_id = self._map_to_canonical_tag_id(canonical_keyword)
        if not alias_norm or not tag_id:
            return {"ok": False}
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO tag_synonyms (alias, tag_id) VALUES (?, ?)", (alias_norm, tag_id))
            conn.commit()
            return {"ok": True}

    def remove_tag_synonym(self, alias: str) -> dict:
        alias_norm = self._normalize_keyword(alias)
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM tag_synonyms WHERE alias = ?", (alias_norm,))
            conn.commit()
            return {"ok": True}

    # --- Ratings ---
    def get_ratings_summary(self, recipe_id: int, user_id: Optional[int] = None) -> dict:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT rating_average, rating_count FROM saved_recipes WHERE id = ?", (recipe_id,))
            row = cursor.fetchone()
            average = row[0] if row else 0
            count = row[1] if row else 0
            user_value = None
            if user_id:
                cursor.execute("SELECT value FROM ratings WHERE recipe_id = ? AND user_id = ?", (recipe_id, user_id))
                r = cursor.fetchone()
                user_value = r[0] if r else None
            return {"average": round(average or 0, 2), "count": count or 0, "userValue": user_value}

    def _recalculate_recipe_rating(self, recipe_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*), COALESCE(SUM(value), 0) FROM ratings WHERE recipe_id = ?", (recipe_id,))
            row = cursor.fetchone()
            count = row[0] or 0
            total = row[1] or 0
            average = round((total / count), 2) if count > 0 else 0
            cursor.execute("UPDATE saved_recipes SET rating_average = ?, rating_count = ? WHERE id = ?", (average, count, recipe_id))
            conn.commit()

    def upsert_rating(self, recipe_id: int, user_id: int, value: int) -> dict:
        if value < 1 or value > 5:
            raise ValueError("Rating must be between 1 and 5")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM ratings WHERE recipe_id = ? AND user_id = ?", (recipe_id, user_id))
            row = cursor.fetchone()
            if row:
                cursor.execute("UPDATE ratings SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (value, row[0]))
            else:
                cursor.execute("INSERT INTO ratings (recipe_id, user_id, value) VALUES (?, ?, ?)", (recipe_id, user_id, value))
            conn.commit()
        self._recalculate_recipe_rating(recipe_id)
        return self.get_ratings_summary(recipe_id, user_id)

    def delete_rating(self, recipe_id: int, user_id: int) -> dict:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM ratings WHERE recipe_id = ? AND user_id = ?", (recipe_id, user_id))
            conn.commit()
        self._recalculate_recipe_rating(recipe_id)
        return self.get_ratings_summary(recipe_id, user_id)

    # --- Comments ---
    def create_comment(self, recipe_id: int, user_id: int, body: str, parent_id: Optional[int] = None) -> dict:
        body = (body or '').strip()
        if len(body) < 1 or len(body) > 2000:
            raise ValueError("Comment length must be 1-2000 characters")
        # simple banned words filter
        banned = ["http://", "https://", "<script", "</script>"]
        lowered = body.lower()
        if any(b in lowered for b in banned):
            raise ValueError("Comment contains forbidden content")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO comments (recipe_id, user_id, body, parent_id) VALUES (?, ?, ?, ?)",
                (recipe_id, user_id, body, parent_id)
            )
            comment_id = cursor.lastrowid
            conn.commit()
            return self.get_comment_dto(comment_id)

    def get_comment_dto(self, comment_id: int, viewer_user_id: Optional[int] = None) -> Optional[dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Check user table columns to avoid selecting non-existent columns
            cursor.execute("PRAGMA table_info(users)")
            user_cols = {r[1] for r in cursor.fetchall()}
            select_avatar = 'avatar_url' in user_cols
            select_username = 'username' in user_cols
            select_clause = (
                "SELECT c.id, c.recipe_id, c.user_id, c.body, c.deleted, c.parent_id, "
                "c.created_at, c.updated_at, u.full_name AS user_full_name"
            )
            if select_avatar:
                select_clause += ", u.avatar_url AS user_avatar"
            if select_username:
                select_clause += ", u.username AS user_username"
            query = (
                select_clause +
                " FROM comments c JOIN users u ON u.id = c.user_id WHERE c.id = ?"
            )
            cursor.execute(query, (comment_id,))
            row = cursor.fetchone()
            if not row:
                return None
            # Access using alias keys to avoid index brittleness
            row_d = dict(row)
            body_text = "(raderad)" if row_d.get('deleted') else row_d.get('body')
            display_name = row_d.get('user_username') or row_d.get('user_full_name')
            avatar_value = row_d.get('user_avatar') if select_avatar else None

            # Likes summary
            cursor.execute("SELECT COUNT(*) FROM comment_likes WHERE comment_id = ?", (comment_id,))
            likes_count = cursor.fetchone()[0] or 0
            liked_by_me = False
            if viewer_user_id:
                cursor.execute("SELECT 1 FROM comment_likes WHERE comment_id = ? AND user_id = ?", (comment_id, viewer_user_id))
                liked_by_me = cursor.fetchone() is not None
            return {
                "id": row_d.get('id'),
                "recipeId": row_d.get('recipe_id'),
                "user": {"id": row_d.get('user_id'), "displayName": display_name, "username": row_d.get('user_username'), "avatar": avatar_value},
                "body": body_text,
                "createdAt": row_d.get('created_at'),
                "updatedAt": row_d.get('updated_at'),
                "parentId": row_d.get('parent_id'),
                "likesCount": likes_count,
                "likedByMe": liked_by_me
            }

    def update_comment(self, comment_id: int, user_id: int, body: str, is_admin: bool) -> dict:
        body = (body or '').strip()
        if len(body) < 1 or len(body) > 2000:
            raise ValueError("Comment length must be 1-2000 characters")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM comments WHERE id = ?", (comment_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError("Comment not found")
            if row[0] != user_id and not is_admin:
                raise PermissionError("Forbidden")
            cursor.execute("UPDATE comments SET body = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (body, comment_id))
            conn.commit()
        dto = self.get_comment_dto(comment_id)
        return dto

    def soft_delete_comment(self, comment_id: int, user_id: int, is_admin: bool) -> dict:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM comments WHERE id = ?", (comment_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError("Comment not found")
            if row[0] != user_id and not is_admin:
                raise PermissionError("Forbidden")
            cursor.execute("UPDATE comments SET deleted = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (comment_id,))
            conn.commit()
        dto = self.get_comment_dto(comment_id)
        return dto

    def list_comments(self, recipe_id: int, after_cursor: Optional[str], limit: int, sort: str, viewer_user_id: Optional[int] = None) -> dict:
        # Cursor is base64 of "createdAt|id"
        import base64
        created_after = None
        id_after = None
        if after_cursor:
            try:
                decoded = base64.b64decode(after_cursor.encode()).decode()
                parts = decoded.split('|')
                created_after = parts[0]
                id_after = int(parts[1]) if len(parts) > 1 else None
            except Exception:
                pass
        order_clause = "ORDER BY c.created_at DESC, c.id DESC" if sort == 'newest' else ("ORDER BY c.created_at ASC, c.id ASC" if sort == 'oldest' else "ORDER BY c.created_at DESC, c.id DESC")
        params = [recipe_id]
        where_extra = ""
        if created_after and id_after is not None:
            # For DESC order
            if 'DESC' in order_clause:
                where_extra = " AND (c.created_at < ? OR (c.created_at = ? AND c.id < ?))"
            else:
                where_extra = " AND (c.created_at > ? OR (c.created_at = ? AND c.id > ?))"
            params.extend([created_after, created_after, id_after])
        query = f"""
            SELECT c.id FROM comments c 
            WHERE c.recipe_id = ? AND (c.deleted IS NULL OR c.deleted = 0)
            {where_extra} {order_clause} LIMIT ?
        """
        params.append(limit + 1)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            ids = [r[0] for r in rows]
            has_more = len(ids) > limit
            ids = ids[:limit]
            items: List[dict] = []
            for cid in ids:
                try:
                    dto = self.get_comment_dto(cid, viewer_user_id)
                    if dto:
                        items.append(dto)
                except Exception as _e:
                    # Skip malformed rows instead of failing the whole request
                    continue
            next_cursor = None
            if has_more and len(items) > 0:
                last = items[-1]
                try:
                    raw = f"{last['createdAt']}|{last['id']}"
                    next_cursor = base64.b64encode(raw.encode()).decode()
                except Exception:
                    next_cursor = None
            return {"items": items, "nextCursor": next_cursor}

    def report_comment(self, comment_id: int, user_id: int, reason: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO comment_reports (comment_id, user_id, reason) VALUES (?, ?, ?)",
                (comment_id, user_id, reason)
            )
            conn.commit()
            return {"ok": True}

    def toggle_comment_like(self, comment_id: int, user_id: int) -> dict:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM comment_likes WHERE comment_id = ? AND user_id = ?", (comment_id, user_id))
            existing = cursor.fetchone()
            if existing:
                cursor.execute("DELETE FROM comment_likes WHERE comment_id = ? AND user_id = ?", (comment_id, user_id))
                liked = False
            else:
                cursor.execute("INSERT OR IGNORE INTO comment_likes (comment_id, user_id) VALUES (?, ?)", (comment_id, user_id))
                liked = True
            conn.commit()
            cursor.execute("SELECT COUNT(*) FROM comment_likes WHERE comment_id = ?", (comment_id,))
            count = cursor.fetchone()[0] or 0
            return {"liked": liked, "count": count}

    # --- Roles Management ---
    def get_roles_for_user(self, user_id: int) -> List[str]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT role FROM user_roles WHERE user_id = ?", (user_id,))
            return [r[0] for r in cursor.fetchall()]

    def set_roles_for_user(self, user_id: int, roles: List[str]):
        allowed = {"guest", "user", "creator", "trusted", "moderator", "admin"}
        roles = [r for r in roles if r in allowed]
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_roles WHERE user_id = ?", (user_id,))
            for role in roles:
                cursor.execute("INSERT OR IGNORE INTO user_roles (user_id, role) VALUES (?, ?)", (user_id, role))
            conn.commit()

    # ---------------------- Nutrition Snapshots API ----------------------
    def get_nutrition_snapshot(self, recipe_id: int) -> Optional[dict]:
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT snapshot, status, updated_at, meta FROM nutrition_snapshots WHERE recipe_id=?", (recipe_id,))
                row = c.fetchone()
                if not row:
                    return None
                snapshot_json, status, updated_at, meta_json = row
                try:
                    snapshot = json.loads(snapshot_json) if snapshot_json else None
                except Exception:
                    snapshot = None
                try:
                    meta = json.loads(meta_json) if meta_json else None
                except Exception:
                    meta = None
                return {"recipe_id": recipe_id, "snapshot": snapshot, "status": status, "updated_at": updated_at, "meta": meta}
        except Exception as e:
            logger.error(f"get_nutrition_snapshot failed: {e}")
            return None

    def upsert_nutrition_snapshot(self, recipe_id: int, status: str, snapshot: Optional[dict] = None, meta: Optional[dict] = None):
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute(
                    "INSERT INTO nutrition_snapshots (recipe_id, snapshot, status, updated_at, meta) VALUES (?,?,?,?,?)\n                     ON CONFLICT(recipe_id) DO UPDATE SET snapshot=excluded.snapshot, status=excluded.status, updated_at=CURRENT_TIMESTAMP, meta=excluded.meta",
                    (
                        recipe_id,
                        json.dumps(snapshot) if snapshot is not None else None,
                        status,
                        datetime.now().isoformat(sep=' ', timespec='seconds'),
                        json.dumps(meta) if meta is not None else None,
                    ),
                )
                conn.commit()
        except Exception as e:
            logger.error(f"upsert_nutrition_snapshot failed: {e}")

    # ---------------------- FDC Cache Helpers ----------------------
    def get_fdc_food(self, fdc_id: int) -> Optional[dict]:
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT json, updated_at FROM fdc_foods WHERE fdc_id=?", (fdc_id,))
                row = c.fetchone()
                if not row:
                    return None
                data_json, updated_at = row
                try:
                    data = json.loads(data_json)
                except Exception:
                    data = None
                return {"fdc_id": fdc_id, "json": data, "updated_at": updated_at}
        except Exception as e:
            logger.error(f"get_fdc_food failed: {e}")
            return None

    def upsert_fdc_food(self, fdc_id: int, data: dict):
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute(
                    "INSERT INTO fdc_foods (fdc_id, json, updated_at) VALUES (?,?,?)\n                     ON CONFLICT(fdc_id) DO UPDATE SET json=excluded.json, updated_at=excluded.updated_at",
                    (fdc_id, json.dumps(data), datetime.now().isoformat(sep=' ', timespec='seconds')),
                )
                conn.commit()
        except Exception as e:
            logger.error(f"upsert_fdc_food failed: {e}")

    # ---------------------- Density Catalog Helpers ----------------------
    def upsert_density(self, category: str, form: str, g_per_ml: float, source: str):
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute(
                    "INSERT INTO density_catalog (category, form, g_per_ml, source, updated_at) VALUES (?,?,?,?,CURRENT_TIMESTAMP)\n                     ON CONFLICT(category, form) DO UPDATE SET g_per_ml=excluded.g_per_ml, source=excluded.source, updated_at=CURRENT_TIMESTAMP",
                    (category, form, g_per_ml, source),
                )
                conn.commit()
        except Exception as e:
            logger.error(f"upsert_density failed: {e}")

    def get_density(self, category: str, form: str) -> Optional[float]:
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT g_per_ml FROM density_catalog WHERE category=? AND form=?", (category, form))
                row = c.fetchone()
                return float(row[0]) if row else None
        except Exception:
            return None

db = DatabaseManager()
