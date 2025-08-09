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
            conn.commit()
            logger.info("Database initialized successfully")

            # Seed canonical tags once
            self._seed_canonical_tags(cursor)
            conn.commit()

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
                cursor.execute("SELECT * FROM saved_recipes WHERE id = ?", (recipe_id,))
                row = cursor.fetchone()
                if row:
                    return SavedRecipe(
                        id=row['id'],
                        user_id=row['user_id'],
                        source_url=row['source_url'],
                        created_at=datetime.fromisoformat(row["created_at"]),
                        recipe_content=RecipeContent.model_validate_json(row['recipe_content'])
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
                cursor.execute(f"SELECT * FROM saved_recipes WHERE user_id = ? {order}", (user_id,))
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

                    recipes.append(
                        SavedRecipe(
                            id=row['id'],
                            user_id=row['user_id'],
                            source_url=row['source_url'],
                            created_at=datetime.fromisoformat(row["created_at"]),
                            recipe_content=RecipeContent.model_validate(content_dict)
                        )
                    )
                return recipes
        except Exception as e:
            logger.error(f"Error getting saved recipes for user {user_id}: {e}")
            return []

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
                'quick','easy','budget','festive','seasonal','holiday','summer','winter','autumn','spring','spicy','sweet','savory','comfortfood','healthy','kidfriendly','fingerfood','mealprep'
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
            average = (total / count) if count > 0 else 0
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
            SELECT c.id FROM comments c WHERE c.recipe_id = ? {where_extra} {order_clause} LIMIT ?
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

db = DatabaseManager()
