import sqlite3
import hashlib
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "easyphoneunlock.db")

class DatabaseManager:
    @staticmethod
    def get_connection():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def init_db():
        conn = DatabaseManager.get_connection()
        cursor = conn.cursor()

        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email TEXT,
                credits INTEGER DEFAULT 10,
                hwid TEXT,
                is_active INTEGER DEFAULT 1,
                is_admin INTEGER DEFAULT 0,
                last_ip TEXT,
                last_login TEXT,
                created_at TEXT
            )
        ''')

        # Credit Transactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS credit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                operation TEXT,
                hwid TEXT,
                ip TEXT,
                timestamp TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

        # System Settings & Maintenance table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        # Create default superadmin if not exists (username: admin, pass: admin123)
        cursor.execute("SELECT id FROM users WHERE username = 'admin'")
        if not cursor.fetchone():
            default_pass_hash = hashlib.sha256("admin123".encode()).hexdigest()
            now = datetime.utcnow().isoformat()
            cursor.execute('''
                INSERT INTO users (username, password_hash, email, credits, is_active, is_admin, created_at)
                VALUES ('admin', ?, 'admin@easyphoneunlock.com', 99999, 1, 1, ?)
            ''', (default_pass_hash, now))

        # Default system configs
        cursor.execute("INSERT OR IGNORE INTO system_config (key, value) VALUES ('maintenance_mode', '0')")
        cursor.execute("INSERT OR IGNORE INTO system_config (key, value) VALUES ('latest_version', '1.0.0')")
        cursor.execute("INSERT OR IGNORE INTO system_config (key, value) VALUES ('announcement', 'Welcome to EasyPhoneUnlock Universal MTK Tool!')")

        conn.commit()
        conn.close()

if __name__ == "__main__":
    DatabaseManager.init_db()
    print("[+] Database initialized successfully.")
