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

        CREATE TABLE IF NOT EXISTS coupons (
            code        TEXT PRIMARY KEY,
            plan        TEXT DEFAULT 'premium',
            days        INTEGER DEFAULT 30,
            max_uses    INTEGER DEFAULT 1,
            used_count  INTEGER DEFAULT 0,
            created_at  REAL,
            expires_at  REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS coupon_uses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            code        TEXT,
            user_id     INTEGER,
            used_at     REAL
        );
        CREATE TABLE IF NOT EXISTS cron_jobs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            filename    TEXT,
            cron_expr   TEXT,
            enabled     INTEGER DEFAULT 1,
            last_run    REAL DEFAULT 0,
            created_at  REAL
        );
        CREATE TABLE IF NOT EXISTS env_vars (
            user_id     INTEGER,
            filename    TEXT,
            env_key     TEXT,
            env_value   TEXT,
            PRIMARY KEY (user_id, filename, env_key)
        );
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id         INTEGER PRIMARY KEY,
            auto_restart    INTEGER DEFAULT 0,
            crash_notify    INTEGER DEFAULT 1,
            cpu_limit       REAL DEFAULT 80.0,
            ram_limit_mb    REAL DEFAULT 256.0
        );
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

# ── Coupon System ─────────────────────────────────────────────────────────────
def create_coupon(code, plan="premium", days=30, max_uses=1, expires_days=0):
    conn = get_conn()
    now = time.time()
    expires_at = now + expires_days * 86400 if expires_days > 0 else 0
    try:
        conn.execute(
            "INSERT INTO coupons(code,plan,days,max_uses,used_count,created_at,expires_at) VALUES(?,?,?,?,0,?,?)",
            (code.upper(), plan, days, max_uses, now, expires_at)
        )
        conn.commit()
        return True, "✅ Coupon created"
    except:
        return False, "❌ Coupon already exists"
    finally:
        conn.close()

def redeem_coupon(code, user_id):
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM coupons WHERE code=?", (code.upper(),)).fetchone()
        if not row:
            return False, "❌ Invalid coupon code"
        row = dict(row)
        if row["expires_at"] > 0 and time.time() > row["expires_at"]:
            return False, "❌ Coupon has expired"
        if row["used_count"] >= row["max_uses"]:
            return False, "❌ Coupon has been fully used"
        already = conn.execute("SELECT id FROM coupon_uses WHERE code=? AND user_id=?", (code.upper(), user_id)).fetchone()
        if already:
            return False, "❌ You already used this coupon"
        conn.execute("UPDATE coupons SET used_count=used_count+1 WHERE code=?", (code.upper(),))
        conn.execute("INSERT INTO coupon_uses(code,user_id,used_at) VALUES(?,?,?)", (code.upper(), user_id, time.time()))
        conn.commit()
        return True, {"plan": row["plan"], "days": row["days"]}
    finally:
        conn.close()

def get_all_coupons():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM coupons ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_coupon(code):
    conn = get_conn()
    conn.execute("DELETE FROM coupons WHERE code=?", (code.upper(),))
    conn.commit()
    conn.close()

# ── Cron Jobs ─────────────────────────────────────────────────────────────────
def add_cron_job(user_id, filename, cron_expr):
    conn = get_conn()
    existing = conn.execute("SELECT id FROM cron_jobs WHERE user_id=? AND filename=?", (user_id, filename)).fetchone()
    if existing:
        conn.execute("UPDATE cron_jobs SET cron_expr=?,enabled=1 WHERE user_id=? AND filename=?", (cron_expr, user_id, filename))
    else:
        conn.execute("INSERT INTO cron_jobs(user_id,filename,cron_expr,enabled,last_run,created_at) VALUES(?,?,?,1,0,?)", (user_id, filename, cron_expr, time.time()))
    conn.commit()
    conn.close()

def remove_cron_job(user_id, filename):
    conn = get_conn()
    conn.execute("DELETE FROM cron_jobs WHERE user_id=? AND filename=?", (user_id, filename))
    conn.commit()
    conn.close()

def get_user_cron_jobs(user_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM cron_jobs WHERE user_id=?", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_cron_jobs():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM cron_jobs WHERE enabled=1").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_cron_last_run(job_id):
    conn = get_conn()
    conn.execute("UPDATE cron_jobs SET last_run=? WHERE id=?", (time.time(), job_id))
    conn.commit()
    conn.close()

# ── Env Vars ──────────────────────────────────────────────────────────────────
def set_env_var(user_id, filename, key, value):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO env_vars(user_id,filename,env_key,env_value) VALUES(?,?,?,?)", (user_id, filename, key, value))
    conn.commit()
    conn.close()

def get_env_vars(user_id, filename):
    conn = get_conn()
    rows = conn.execute("SELECT env_key,env_value FROM env_vars WHERE user_id=? AND filename=?", (user_id, filename)).fetchall()
    conn.close()
    return {r["env_key"]: r["env_value"] for r in rows}

def delete_env_var(user_id, filename, key):
    conn = get_conn()
    conn.execute("DELETE FROM env_vars WHERE user_id=? AND filename=? AND env_key=?", (user_id, filename, key))
    conn.commit()
    conn.close()

def delete_all_env_vars(user_id, filename):
    conn = get_conn()
    conn.execute("DELETE FROM env_vars WHERE user_id=? AND filename=?", (user_id, filename))
    conn.commit()
    conn.close()

# ── User Settings ─────────────────────────────────────────────────────────────
def get_user_settings(user_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM user_settings WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return {"user_id": user_id, "auto_restart": 0, "crash_notify": 1, "cpu_limit": 80.0, "ram_limit_mb": 256.0}

def update_user_settings(user_id, **kwargs):
    current = get_user_settings(user_id)
    current.update(kwargs)
    conn = get_conn()
    conn.execute("""INSERT OR REPLACE INTO user_settings(user_id,auto_restart,crash_notify,cpu_limit,ram_limit_mb)
                    VALUES(?,?,?,?,?)""",
                 (user_id, current["auto_restart"], current["crash_notify"], current["cpu_limit"], current["ram_limit_mb"]))
    conn.commit()
    conn.close()
