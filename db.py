import os
import sqlite3
from datetime import datetime, timezone

from flask import g
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH") or os.path.join(BASE_DIR, "data", "dashboard.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    store TEXT NOT NULL DEFAULT 'all',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS goals (
    store TEXT NOT NULL,
    month TEXT NOT NULL,
    target REAL NOT NULL,
    updated_by INTEGER,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (store, month)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    details TEXT,
    created_at TEXT NOT NULL
);
"""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_conn():
    if "conn" not in g:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        g.conn = conn
    return g.conn


def close_conn(_=None):
    conn = g.pop("conn", None)
    if conn is not None:
        conn.close()


def init_app(app):
    app.teardown_appcontext(close_conn)
    with app.app_context():
        conn = get_conn()
        conn.executescript(SCHEMA)
        conn.commit()


def get_user_by_id(user_id):
    return get_conn().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def get_user_by_email(email):
    return get_conn().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()


def list_users():
    return get_conn().execute("SELECT * FROM users ORDER BY id").fetchall()


def create_user(name, email, password_hash, role, store):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO users (name, email, password_hash, role, store, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (name, email, password_hash, role, store, now()),
    )
    conn.commit()
    return cur.lastrowid


def set_user_active(user_id, active):
    conn = get_conn()
    conn.execute("UPDATE users SET active = ? WHERE id = ?", (1 if active else 0, user_id))
    conn.commit()


def log_action(user_id, action, details=""):
    conn = get_conn()
    conn.execute(
        "INSERT INTO audit_log (user_id, action, details, created_at) VALUES (?, ?, ?, ?)",
        (user_id, action, details, now()),
    )
    conn.commit()


def list_audit(limit=200):
    return get_conn().execute(
        "SELECT a.*, u.email AS user_email FROM audit_log a "
        "LEFT JOIN users u ON u.id = a.user_id ORDER BY a.id DESC LIMIT ?",
        (limit,),
    ).fetchall()


def seed_owner_if_empty():
    """ينشئ حساب المالك الأول من متغيرات البيئة لو قاعدة البيانات فاضية."""
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count:
        return
    email = os.environ.get("OWNER_EMAIL", "").strip().lower()
    password = os.environ.get("OWNER_PASSWORD", "")
    if not email or len(password) < 8:
        raise SystemExit("لازم تضبط OWNER_EMAIL و OWNER_PASSWORD (8 أحرف على الأقل) في ملف .env قبل أول تشغيل.")
    create_user("المالك", email, generate_password_hash(password, method="pbkdf2:sha256"), "owner", "all")
    log_action(None, "owner_seeded", f"إنشاء حساب المالك: {email}")


def get_goal(store, month):
    row = get_conn().execute("SELECT target FROM goals WHERE store = ? AND month = ?", (store, month)).fetchone()
    return row["target"] if row else None


def set_goal(store, month, target, user_id):
    conn = get_conn()
    conn.execute(
        "INSERT INTO goals (store, month, target, updated_by, updated_at) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(store, month) DO UPDATE SET target = excluded.target, updated_by = excluded.updated_by, "
        "updated_at = excluded.updated_at",
        (store, month, target, user_id, now()),
    )
    conn.commit()
