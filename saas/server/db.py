"""SQLite — đủ cho một máy chủ; mọi truy cập đi qua một khoá để an toàn với thread worker."""
import datetime as dt
import json
import sqlite3
import threading

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT, pw_hash TEXT,
  role TEXT NOT NULL DEFAULT 'user', status TEXT NOT NULL DEFAULT 'active', google_sub TEXT,
  quota_projects INTEGER, quota_jobs_month INTEGER, session_ver INTEGER NOT NULL DEFAULT 1,
  created TEXT, last_login TEXT);
CREATE TABLE IF NOT EXISTS api_keys(
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, provider TEXT NOT NULL, label TEXT, key_enc TEXT NOT NULL,
  key_hint TEXT, model TEXT, is_default INTEGER NOT NULL DEFAULT 0, last_test TEXT, last_test_ok INTEGER, created TEXT);
CREATE TABLE IF NOT EXISTS projects(
  id INTEGER PRIMARY KEY, slug TEXT UNIQUE NOT NULL, user_id INTEGER NOT NULL, name TEXT NOT NULL, idea TEXT,
  country TEXT DEFAULT 'Việt Nam', status TEXT NOT NULL DEFAULT 'interview', brief_md TEXT, created TEXT, updated TEXT);
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL, room TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL,
  meta TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS interview(
  project_id INTEGER PRIMARY KEY, answers TEXT NOT NULL DEFAULT '{}', current_qid TEXT, done INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS decisions(
  id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL, title TEXT NOT NULL, detail TEXT, category TEXT,
  status TEXT NOT NULL DEFAULT 'proposed', source_msg INTEGER, created TEXT, updated TEXT);
CREATE TABLE IF NOT EXISTS agent_profiles(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, engine TEXT NOT NULL, auth_mode TEXT NOT NULL DEFAULT 'account',
  key_enc TEXT, key_hint TEXT, model TEXT, home_dir TEXT, enabled INTEGER NOT NULL DEFAULT 1, is_active INTEGER NOT NULL DEFAULT 0,
  priority INTEGER NOT NULL DEFAULT 100, account_label TEXT, status TEXT, models TEXT, quota_text TEXT, quota_checked TEXT,
  budget_tokens_month INTEGER, version TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS jobs(
  id INTEGER PRIMARY KEY, kind TEXT NOT NULL DEFAULT 'plan', project_id INTEGER, user_id INTEGER, engine TEXT,
  billing TEXT, profile_id INTEGER, api_key_id INTEGER, model TEXT, status TEXT NOT NULL DEFAULT 'queued',
  log TEXT NOT NULL DEFAULT '', usage TEXT, error TEXT, attempt INTEGER NOT NULL DEFAULT 1, pid INTEGER,
  created TEXT, started TEXT, finished TEXT);
CREATE TABLE IF NOT EXISTS usage(
  id INTEGER PRIMARY KEY, user_id INTEGER, project_id INTEGER, source TEXT, provider TEXT, model TEXT, profile_id INTEGER,
  input_tokens INTEGER DEFAULT 0, output_tokens INTEGER DEFAULT 0, cost_usd REAL, created TEXT);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, user_id INTEGER, action TEXT, target TEXT, detail TEXT, created TEXT);
CREATE INDEX IF NOT EXISTS ix_msg ON messages(project_id, room);
CREATE INDEX IF NOT EXISTS ix_usage ON usage(created);
"""

DEFAULT_SETTINGS = {
    "site_name": "Gen Planner",
    "allow_signup": "1",
    "plan_billing": "either",          # owner | user_key | either
    "default_quota_projects": "5",
    "default_quota_jobs_month": "3",
    "job_timeout_min": "120",
    "max_concurrent_jobs": "1",
    "auto_failover": "1",
    "allow_demo_engine": "1",
    "google_client_id": "",
    "google_client_secret_enc": "",
    "public_base_url": "",
}

_lock = threading.RLock()
_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
_conn.row_factory = sqlite3.Row
_conn.execute("PRAGMA journal_mode=WAL")
_conn.executescript(SCHEMA)
for k, v in DEFAULT_SETTINGS.items():
    _conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, v))
_conn.commit()


def now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def q(sql, args=()):
    with _lock:
        return [dict(r) for r in _conn.execute(sql, args).fetchall()]


def one(sql, args=()):
    r = q(sql, args)
    return r[0] if r else None


def x(sql, args=()):
    with _lock:
        cur = _conn.execute(sql, args)
        _conn.commit()
        return cur.lastrowid


def insert(table, **kw):
    cols = ",".join(kw)
    return x(f"INSERT INTO {table}({cols}) VALUES({','.join('?' * len(kw))})", tuple(kw.values()))


def update(table, id_, **kw):
    if kw:
        x(f"UPDATE {table} SET {','.join(k + '=?' for k in kw)} WHERE id=?", (*kw.values(), id_))


def setting(key, default=""):
    r = one("SELECT value FROM settings WHERE key=?", (key,))
    return r["value"] if r else default


def set_setting(key, value):
    x("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))


def audit(user_id, action, target="", detail=None):
    insert("audit", user_id=user_id, action=action, target=str(target),
           detail=json.dumps(detail, ensure_ascii=False) if detail is not None else None, created=now())


def append_log(job_id, text):
    with _lock:
        _conn.execute("UPDATE jobs SET log = substr(log || ?, -200000) WHERE id=?", (text, job_id))
        _conn.commit()
