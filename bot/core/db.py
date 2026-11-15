import sqlite3
import asyncio
import os
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import config

LOCAL_TZ = ZoneInfo(config.TIMEZONE)


def _now_str():
    return datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S")


def _connect():
    conn = sqlite3.connect(config.DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.row_factory = sqlite3.Row
    return conn


def _init_sync():
    os.makedirs(config.CONFIG_DIR, exist_ok=True)
    conn = _connect()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,               -- 'telegram' o 'link'
            source_chat_id INTEGER,
            source_message_id INTEGER,
            url TEXT,
            dest_folder TEXT,
            dest_path TEXT,
            filename TEXT,
            status TEXT NOT NULL DEFAULT 'pending_folder',
            progress_chat_id INTEGER,
            progress_message_id INTEGER,
            gid TEXT,
            error TEXT,
            created_at TEXT
        )
    """)
    try:
        cur.execute("ALTER TABLE tasks ADD COLUMN dest_path TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE tasks ADD COLUMN priority INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE tasks ADD COLUMN total_size INTEGER")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE tasks ADD COLUMN started_at TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE tasks ADD COLUMN finished_at TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE tasks ADD COLUMN batch_id TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE tasks ADD COLUMN extract_after INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE tasks ADD COLUMN delete_source INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE tasks ADD COLUMN requested_by INTEGER")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE tasks ADD COLUMN drive_temp_file_id TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE tasks ADD COLUMN drive_file_id TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE tasks ADD COLUMN scheduled_for TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE tasks ADD COLUMN tmdb_organize INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE tasks ADD COLUMN destination_type TEXT NOT NULL DEFAULT 'nas'")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE tasks ADD COLUMN format_id TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE tasks ADD COLUMN client TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE tasks ADD COLUMN name_locked INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    cur.execute("""
        CREATE TABLE IF NOT EXISTS batches (
            id TEXT PRIMARY KEY,
            chat_id INTEGER,
            message_id INTEGER
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS userbot_session (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            session_string TEXT
        )
    """)
    for column, decl in (
        ("user_id", "INTEGER"),
        ("username", "TEXT"),
        ("first_name", "TEXT"),
        ("connected_at", "TEXT"),
    ):
        try:
            cur.execute(f"ALTER TABLE userbot_session ADD COLUMN {column} {decl}")
        except sqlite3.OperationalError:
            pass
    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS authorized_users (
            user_id INTEGER PRIMARY KEY,
            added_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS channel_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            file_size INTEGER,
            channel_id INTEGER,
            message_id INTEGER,
            created_at TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_channel_files_fn ON channel_files (filename)")
    for column, decl in (("username", "TEXT"), ("first_name", "TEXT")):
        try:
            cur.execute(f"ALTER TABLE authorized_users ADD COLUMN {column} {decl}")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()


async def init_db():
    await asyncio.to_thread(_init_sync)


def _create_task_sync(fields):
    if "created_at" not in fields or not fields["created_at"]:
        fields["created_at"] = _now_str()
    conn = _connect()
    cur = conn.cursor()
    keys = ", ".join(fields.keys())
    placeholders = ", ".join("?" for _ in fields)
    cur.execute(f"INSERT INTO tasks ({keys}) VALUES ({placeholders})", tuple(fields.values()))
    conn.commit()
    task_id = cur.lastrowid
    conn.close()
    return task_id


async def create_task(**fields):
    task_id = await asyncio.to_thread(_create_task_sync, fields)
    if fields.get("status") in ("done", "error"):
        await _fire_listeners(task_id)
    return task_id


def _get_task_sync(task_id):
    conn = _connect()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


async def get_task(task_id):
    return await asyncio.to_thread(_get_task_sync, task_id)


def _update_task_sync(task_id, fields):
    conn = _connect()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", (*fields.values(), task_id))
    conn.commit()
    conn.close()


async def update_task(task_id, **fields):
    previous = None
    if _task_listeners and fields.get("status") in ("done", "error"):
        previous = await get_task(task_id)
    await asyncio.to_thread(_update_task_sync, task_id, fields)
    if fields.get("status") in ("done", "error") and (previous is None or previous.get("status") != fields["status"]):
        if previous is not None:
            await _fire_listeners(task_id)


def _get_tasks_by_status_sync(status):
    conn = _connect()
    rows = conn.execute("SELECT * FROM tasks WHERE status = ?", (status,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


async def get_tasks_by_status(status):
    return await asyncio.to_thread(_get_tasks_by_status_sync, status)


def _get_history_sync(limit, requested_by=None):
    conn = _connect()
    if requested_by is None:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE status IN ('done','cancelled','error') "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    elif requested_by == config.OWNER_ID:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE status IN ('done','cancelled','error') AND (requested_by = ? OR requested_by IS NULL) "
            "ORDER BY id DESC LIMIT ?",
            (config.OWNER_ID, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE status IN ('done','cancelled','error') AND requested_by = ? "
            "ORDER BY id DESC LIMIT ?",
            (requested_by, limit),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


async def get_history(limit: int = 50, requested_by: int | None = None):
    return await asyncio.to_thread(_get_history_sync, limit, requested_by)


def _clear_history_sync(requested_by=None):
    conn = _connect()
    if requested_by is None:
        conn.execute("DELETE FROM tasks WHERE status IN ('done','cancelled','error')")
    elif requested_by == config.OWNER_ID:
        conn.execute(
            "DELETE FROM tasks WHERE status IN ('done','cancelled','error') AND (requested_by = ? OR requested_by IS NULL)",
            (config.OWNER_ID,),
        )
    else:
        conn.execute(
            "DELETE FROM tasks WHERE status IN ('done','cancelled','error') AND requested_by = ?",
            (requested_by,),
        )
    conn.commit()
    conn.close()


async def clear_history(requested_by: int | None = None):
    await asyncio.to_thread(_clear_history_sync, requested_by)


def _delete_task_sync(task_id):
    conn = _connect()
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()


async def delete_task(task_id: int):
    await asyncio.to_thread(_delete_task_sync, task_id)


def _create_batch_sync(batch_id, chat_id, message_id):
    conn = _connect()
    conn.execute(
        "INSERT INTO batches (id, chat_id, message_id) VALUES (?, ?, ?)",
        (batch_id, chat_id, message_id),
    )
    conn.commit()
    conn.close()


async def create_batch(batch_id: str, chat_id: int, message_id: int):
    await asyncio.to_thread(_create_batch_sync, batch_id, chat_id, message_id)


def _get_batch_sync(batch_id):
    conn = _connect()
    row = conn.execute("SELECT * FROM batches WHERE id = ?", (batch_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


async def get_batch(batch_id: str):
    return await asyncio.to_thread(_get_batch_sync, batch_id)


def _get_tasks_by_batch_sync(batch_id):
    conn = _connect()
    rows = conn.execute("SELECT * FROM tasks WHERE batch_id = ?", (batch_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


async def get_tasks_by_batch(batch_id: str):
    return await asyncio.to_thread(_get_tasks_by_batch_sync, batch_id)


def _get_session_sync():
    conn = _connect()
    row = conn.execute("SELECT session_string FROM userbot_session WHERE id = 1").fetchone()
    conn.close()
    return row["session_string"] if row else None


async def get_session_string():
    return await asyncio.to_thread(_get_session_sync)


def _set_session_sync(value):
    conn = _connect()
    conn.execute(
        "INSERT INTO userbot_session (id, session_string) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET session_string = excluded.session_string",
        (value,),
    )
    conn.commit()
    conn.close()


async def set_session_string(value):
    await asyncio.to_thread(_set_session_sync, value)


def _set_userbot_meta_sync(user_id, username, first_name):
    conn = _connect()
    conn.execute(
        "UPDATE userbot_session SET user_id = ?, username = ?, first_name = ?, connected_at = ? WHERE id = 1",
        (user_id, username, first_name, _now_str()),
    )
    conn.commit()
    conn.close()


async def set_userbot_meta(user_id, username, first_name):
    await asyncio.to_thread(_set_userbot_meta_sync, user_id, username, first_name)


def _clear_userbot_meta_sync():
    conn = _connect()
    conn.execute(
        "UPDATE userbot_session SET user_id = NULL, username = NULL, first_name = NULL, connected_at = NULL WHERE id = 1"
    )
    conn.commit()
    conn.close()


async def clear_userbot_meta():
    await asyncio.to_thread(_clear_userbot_meta_sync)


def _get_userbot_meta_sync():
    conn = _connect()
    row = conn.execute(
        "SELECT user_id, username, first_name, connected_at FROM userbot_session WHERE id = 1"
    ).fetchone()
    conn.close()
    return dict(row) if row else None


async def get_userbot_meta():
    return await asyncio.to_thread(_get_userbot_meta_sync)


def _get_setting_sync(key):
    conn = _connect()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else None


async def get_setting(key, default=None):
    value = await asyncio.to_thread(_get_setting_sync, key)
    return value if value is not None else default


def _set_setting_sync(key, value):
    conn = _connect()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()


async def set_setting(key, value):
    await asyncio.to_thread(_set_setting_sync, key, value)


def _delete_setting_sync(key):
    conn = _connect()
    conn.execute("DELETE FROM settings WHERE key = ?", (key,))
    conn.commit()
    conn.close()


async def delete_setting(key):
    await asyncio.to_thread(_delete_setting_sync, key)


def _add_authorized_user_sync(user_id):
    conn = _connect()
    conn.execute(
        "INSERT OR REPLACE INTO authorized_users (user_id, added_at) VALUES (?, ?)",
        (user_id, _now_str()),
    )
    conn.commit()
    conn.close()


async def add_authorized_user(user_id: int):
    await asyncio.to_thread(_add_authorized_user_sync, user_id)


def _remove_authorized_user_sync(user_id):
    conn = _connect()
    conn.execute("DELETE FROM authorized_users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


async def remove_authorized_user(user_id: int):
    await asyncio.to_thread(_remove_authorized_user_sync, user_id)


def _list_authorized_users_sync():
    conn = _connect()
    rows = conn.execute("SELECT * FROM authorized_users ORDER BY added_at").fetchall()
    conn.close()
    return [dict(r) for r in rows]


async def list_authorized_users():
    return await asyncio.to_thread(_list_authorized_users_sync)


def _is_authorized_user_sync(user_id):
    conn = _connect()
    row = conn.execute("SELECT 1 FROM authorized_users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row is not None


async def is_authorized_user(user_id: int) -> bool:
    return await asyncio.to_thread(_is_authorized_user_sync, user_id)


def _update_authorized_user_info_sync(user_id, username, first_name):
    conn = _connect()
    conn.execute(
        "UPDATE authorized_users SET username = ?, first_name = ? WHERE user_id = ?",
        (username, first_name, user_id),
    )
    conn.commit()
    conn.close()


async def update_authorized_user_info(user_id: int, username, first_name):
    await asyncio.to_thread(_update_authorized_user_info_sync, user_id, username, first_name)


def _get_scheduled_tasks_ready_sync(now_str: str):
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE status = 'scheduled' AND (scheduled_for IS NULL OR scheduled_for <= ?) ORDER BY id ASC",
        (now_str,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


async def get_scheduled_tasks_ready(now_str: str):
    return await asyncio.to_thread(_get_scheduled_tasks_ready_sync, now_str)


def _get_scheduled_tasks_sync():
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE status = 'scheduled' ORDER BY id ASC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


async def get_scheduled_tasks():
    return await asyncio.to_thread(_get_scheduled_tasks_sync)


def _add_channel_file_sync(filename: str, file_size: int, channel_id: int, message_id: int):
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO channel_files (filename, file_size, channel_id, message_id, created_at) VALUES (?, ?, ?, ?, ?)",
        (filename, file_size, channel_id, message_id, _now_str()),
    )
    conn.commit()
    conn.close()


async def add_channel_file(filename: str, file_size: int, channel_id: int, message_id: int):
    await asyncio.to_thread(_add_channel_file_sync, filename, file_size, channel_id, message_id)


def _get_channel_file_sync(filename: str, file_size: Optional[int] = None) -> Optional[dict]:
    conn = _connect()
    cur = conn.cursor()
    if file_size is not None:
        cur.execute(
            "SELECT * FROM channel_files WHERE filename = ? AND file_size = ? ORDER BY id DESC LIMIT 1",
            (filename, file_size),
        )
    else:
        cur.execute(
            "SELECT * FROM channel_files WHERE filename = ? ORDER BY id DESC LIMIT 1",
            (filename,),
        )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


async def get_channel_file(filename: str, file_size: Optional[int] = None) -> Optional[dict]:
    return await asyncio.to_thread(_get_channel_file_sync, filename, file_size)


def _dump_settings_sync():
    conn = _connect()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


async def dump_settings() -> dict:
    return await asyncio.to_thread(_dump_settings_sync)


TABLES = ("tasks", "batches", "userbot_session", "authorized_users", "channel_files")


def _dump_table_sync(name):
    if name not in TABLES:
        raise ValueError(name)
    conn = _connect()
    rows = [dict(r) for r in conn.execute(f"SELECT * FROM {name}").fetchall()]
    conn.close()
    return rows


async def dump_table(name: str) -> list[dict]:
    return await asyncio.to_thread(_dump_table_sync, name)


def _replace_table_sync(name, rows):
    if name not in TABLES:
        raise ValueError(name)
    conn = _connect()
    cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({name})").fetchall()}
    conn.execute(f"DELETE FROM {name}")
    for row in rows:
        data = {k: v for k, v in row.items() if k in cols}
        if not data:
            continue
        keys = list(data)
        conn.execute(
            f"INSERT OR REPLACE INTO {name} ({', '.join(keys)}) VALUES ({', '.join('?' * len(keys))})",
            [data[k] for k in keys],
        )
    conn.commit()
    conn.close()


async def replace_table(name: str, rows: list[dict]) -> int:
    await asyncio.to_thread(_replace_table_sync, name, rows)
    return len(rows)


def _merge_table_sync(name, rows):
    if name not in TABLES:
        raise ValueError(name)
    conn = _connect()
    cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({name})").fetchall()}
    for row in rows:
        data = {k: v for k, v in row.items() if k in cols}
        if not data:
            continue
        keys = list(data)
        conn.execute(
            f"INSERT OR REPLACE INTO {name} ({', '.join(keys)}) VALUES ({', '.join('?' * len(keys))})",
            [data[k] for k in keys],
        )
    conn.commit()
    conn.close()


async def merge_table(name: str, rows: list[dict]) -> int:
    await asyncio.to_thread(_merge_table_sync, name, rows)
    return len(rows)


_task_listeners = []


def add_task_listener(fn) -> None:
    _task_listeners.append(fn)


async def _fire_listeners(task_id):
    if not _task_listeners:
        return
    task = await get_task(task_id)
    for fn in _task_listeners:
        try:
            await fn(task)
        except Exception:
            pass
