import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pathlib import Path
from models.types import User, UserCreate, UserInDB
import logging

logger = logging.getLogger(__name__)

# Database file path
DB_PATH = Path("users.db")

class DatabaseManager:
    def __init__(self):
        self.db_path = DB_PATH
        self.init_database()
    
    def get_connection(self):
        """Get a database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        return conn
    
    def init_database(self):
        """Initialize the database with required tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Users table
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    usage_count INTEGER DEFAULT 0
                )
            """)
            
            # User sessions table for PDF access
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_pdfs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    job_id TEXT NOT NULL,
                    pdf_path TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)
            
            conn.commit()
            logger.info("Database initialized successfully")
    
    def hash_password(self, password: str) -> str:
        """Hash a password using SHA-256 with salt"""
        salt = secrets.token_hex(16)
        password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return f"{salt}:{password_hash}"
    
    def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        try:
            salt, password_hash = hashed_password.split(":")
            verify_hash = hashlib.sha256((password + salt).encode()).hexdigest()
            return password_hash == verify_hash
        except ValueError:
            return False
    
    def create_user(self, user_data: UserCreate) -> Optional[User]:
        """Create a new user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if user already exists
                cursor.execute("SELECT id FROM users WHERE email = ?", (user_data.email,))
                if cursor.fetchone():
                    return None  # User already exists
                
                # Hash password and create user
                hashed_password = self.hash_password(user_data.password)
                cursor.execute("""
                    INSERT INTO users (email, full_name, hashed_password)
                    VALUES (?, ?, ?)
                """, (user_data.email, user_data.full_name, hashed_password))
                
                user_id = cursor.lastrowid
                conn.commit()
                
                # Return created user
                if user_id:
                    return self.get_user_by_id(user_id)
                return None
                
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None
    
    def get_user_by_email(self, email: str) -> Optional[UserInDB]:
        """Get user by email"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
                row = cursor.fetchone()
                
                if row:
                    return UserInDB(
                        id=row["id"],
                        email=row["email"],
                        full_name=row["full_name"],
                        hashed_password=row["hashed_password"],
                        is_active=bool(row["is_active"]),
                        created_at=datetime.fromisoformat(row["created_at"])
                    )
                return None
                
        except Exception as e:
            logger.error(f"Error getting user by email: {e}")
            return None
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
                row = cursor.fetchone()
                
                if row:
                    return User(
                        id=row["id"],
                        email=row["email"],
                        full_name=row["full_name"],
                        is_active=bool(row["is_active"]),
                        created_at=datetime.fromisoformat(row["created_at"])
                    )
                return None
                
        except Exception as e:
            logger.error(f"Error getting user by ID: {e}")
            return None
    
    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password"""
        user = self.get_user_by_email(email)
        if user and self.verify_password(password, user.hashed_password):
            return User(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                is_active=user.is_active,
                created_at=user.created_at
            )
        return None
    
    def create_oauth_user(self, email: str, full_name: str, google_id: str, avatar_url: Optional[str] = None) -> Optional[User]:
        """Create a new OAuth user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if user already exists
                cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
                if cursor.fetchone():
                    return None  # User already exists
                
                # Create OAuth user
                cursor.execute("""
                    INSERT INTO users (email, full_name, google_id, avatar_url, auth_provider)
                    VALUES (?, ?, ?, ?, 'google')
                """, (email, full_name, google_id, avatar_url))
                
                user_id = cursor.lastrowid
                conn.commit()
                
                # Return created user
                if user_id:
                    return self.get_user_by_id(user_id)
                return None
                
        except Exception as e:
            logger.error(f"Error creating OAuth user: {e}")
            return None
    
    def get_user_by_google_id(self, google_id: str) -> Optional[User]:
        """Get user by Google ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE google_id = ?", (google_id,))
                row = cursor.fetchone()
                
                if row:
                    return User(
                        id=row["id"],
                        email=row["email"],
                        full_name=row["full_name"],
                        is_active=bool(row["is_active"]),
                        created_at=datetime.fromisoformat(row["created_at"])
                    )
                return None
                
        except Exception as e:
            logger.error(f"Error getting user by Google ID: {e}")
            return None

    def increment_user_usage(self, user_id: int):
        """Increment the usage count for a user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET usage_count = usage_count + 1 WHERE id = ?", (user_id,))
                conn.commit()
                logger.info(f"Incremented usage count for user {user_id}")
        except Exception as e:
            logger.error(f"Error incrementing usage count for user {user_id}: {e}")

    def link_pdf_to_user(self, user_id: int, job_id: str, pdf_path: str):
        """Link a generated PDF to a user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO user_pdfs (user_id, job_id, pdf_path)
                    VALUES (?, ?, ?)
                """, (user_id, job_id, pdf_path))
                conn.commit()
                logger.info(f"Linked PDF {pdf_path} to user {user_id}")
                
        except Exception as e:
            logger.error(f"Error linking PDF to user: {e}")
    
    def get_user_pdfs(self, user_id: int) -> list[Dict[str, Any]]:
        """Get all PDFs for a user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT job_id, pdf_path, created_at 
                    FROM user_pdfs 
                    WHERE user_id = ? 
                    ORDER BY created_at DESC
                """, (user_id,))
                
                return [
                    {
                        "job_id": row["job_id"],
                        "pdf_path": row["pdf_path"],
                        "created_at": row["created_at"]
                    }
                    for row in cursor.fetchall()
                ]
                
        except Exception as e:
            logger.error(f"Error getting user PDFs: {e}")
            return []

# Global database instance
db = DatabaseManager() 