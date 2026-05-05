import sqlite3
import json
import os
import time
from datetime import datetime
from config import DB_PATH, USERS_JSON_PATH, DATA_DIR

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT,
            full_name   TEXT,
            join_date   REAL,
            last_active REAL,
            is_banned   INTEGER DEFAULT 0,
            plan        TEXT DEFAULT 'free',
            premium_expiry REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS files (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            filename    TEXT,
            filepath    TEXT,
            size_bytes  INTEGER,
            uploaded_at REAL,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );
        CREATE TABLE IF NOT EXISTS activity_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            action      TEXT,
            detail      TEXT,
            timestamp   REAL
        );
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
        INSERT OR IGNORE INTO settings(key, value) VALUES ('maintenance', '0');
    """)
    conn.commit()
    conn.close()

def register_user(user_id, username, full_name):
    conn = get_conn()
    c = conn.cursor()
    now = time.time()
    c.execute("""
        INSERT OR IGNORE INTO users(user_id, username, full_name, join_date, last_active)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, username, full_name, now, now))
    c.execute("""
        UPDATE users SET username=?, full_name=?, last_active=? WHERE user_id=?
    """, (username, full_name, now, user_id))
    conn.commit()
    conn.close()
    _sync_json()

def update_last_active(user_id):
    conn = get_conn()
    conn.execute("UPDATE users SET last_active=? WHERE user_id=?", (time.time(), user_id))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_users():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def ban_user(user_id, ban=True):
    conn = get_conn()
    conn.execute("UPDATE users SET is_banned=? WHERE user_id=?", (1 if ban else 0, user_id))
    conn.commit()
    conn.close()
    _sync_json()

def set_premium(user_id, days=30):
    expiry = time.time() + days * 86400
    conn = get_conn()
    conn.execute("UPDATE users SET plan='premium', premium_expiry=? WHERE user_id=?", (expiry, user_id))
    conn.commit()
    conn.close()
    _sync_json()

def remove_premium(user_id):
    conn = get_conn()
    conn.execute("UPDATE users SET plan='free', premium_expiry=0 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    _sync_json()

def check_premium_expiry():
    now = time.time()
    conn = get_conn()
    expired = conn.execute(
        "SELECT user_id FROM users WHERE plan='premium' AND premium_expiry > 0 AND premium_expiry < ?", (now,)
    ).fetchall()
    for row in expired:
        conn.execute("UPDATE users SET plan='free', premium_expiry=0 WHERE user_id=?", (row["user_id"],))
    conn.commit()
    conn.close()
    return [r["user_id"] for r in expired]

def add_file_record(user_id, filename, filepath, size_bytes):
    conn = get_conn()
    conn.execute(
        "INSERT INTO files(user_id, filename, filepath, size_bytes, uploaded_at) VALUES(?,?,?,?,?)",
        (user_id, filename, filepath, size_bytes, time.time())
    )
    conn.commit()
    conn.close()

def delete_file_record(user_id, filename):
    conn = get_conn()
    conn.execute("DELETE FROM files WHERE user_id=? AND filename=?", (user_id, filename))
    conn.commit()
    conn.close()

def get_user_files(user_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM files WHERE user_id=?", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_user_file_count(user_id):
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM files WHERE user_id=?", (user_id,)).fetchone()[0]
    conn.close()
    return count

def get_user_storage_mb(user_id):
    conn = get_conn()
    total = conn.execute("SELECT COALESCE(SUM(size_bytes),0) FROM files WHERE user_id=?", (user_id,)).fetchone()[0]
    conn.close()
    return total / (1024 * 1024)

def log_activity(user_id, action, detail=""):
    conn = get_conn()
    conn.execute(
        "INSERT INTO activity_logs(user_id, action, detail, timestamp) VALUES(?,?,?,?)",
        (user_id, action, detail, time.time())
    )
    conn.commit()
    conn.close()

def get_setting(key):
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else None

def set_setting(key, value):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO settings(key, value) VALUES(?,?)", (key, str(value)))
    conn.commit()
    conn.close()

def get_global_stats():
    conn = get_conn()
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    premium_users = conn.execute("SELECT COUNT(*) FROM users WHERE plan='premium'").fetchone()[0]
    banned_users = conn.execute("SELECT COUNT(*) FROM users WHERE is_banned=1").fetchone()[0]
    total_files = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    conn.close()
    return {
        "total_users": total_users,
        "premium_users": premium_users,
        "banned_users": banned_users,
        "total_files": total_files,
    }

def _sync_json():
    users = get_all_users()
    with open(USERS_JSON_PATH, "w") as f:
        json.dump(users, f, indent=2, default=str)

init_db()
