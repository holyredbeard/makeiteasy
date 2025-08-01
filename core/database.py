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
                    hashed_password TEXT,
                    google_id TEXT,
                    avatar_url TEXT,
                    auth_provider TEXT DEFAULT 'email',
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS saved_recipes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    source_url TEXT NOT NULL,
                    recipe_content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)
            conn.commit()
            logger.info("Database initialized successfully")

    def create_user(self, user_data: UserCreate) -> Optional[User]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if self.get_user_by_email(user_data.email):
                    return None
                
                hashed_password = get_password_hash(user_data.password)
                cursor.execute(
                    "INSERT INTO users (email, full_name, hashed_password) VALUES (?, ?, ?)",
                    (user_data.email, user_data.full_name, hashed_password)
                )
                user_id = cursor.lastrowid
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
                return UserInDB(**dict(row)) if row else None
        except Exception as e:
            logger.error(f"Error getting user by email '{email}': {e}")
            return None

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
                row = cursor.fetchone()
                return User(**dict(row)) if row else None
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
                conn.commit()
                return self.get_user_by_id(user_id)
        except Exception as e:
            logger.error(f"Error creating OAuth user: {e}")
            return None

    def save_recipe(self, user_id: int, source_url: str, recipe_content: RecipeContent) -> Optional[SavedRecipe]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                recipe_json = recipe_content.model_dump_json()
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

    def get_user_saved_recipes(self, user_id: int) -> List[SavedRecipe]:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM saved_recipes WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
                rows = cursor.fetchall()
                recipes = []
                for row in rows:
                    recipes.append(
                        SavedRecipe(
                            id=row['id'],
                            user_id=row['user_id'],
                            source_url=row['source_url'],
                            created_at=datetime.fromisoformat(row["created_at"]),
                            recipe_content=RecipeContent.model_validate_json(row['recipe_content'])
                        )
                    )
                return recipes
        except Exception as e:
            logger.error(f"Error getting saved recipes for user {user_id}: {e}")
            return []

db = DatabaseManager()
