import json
import os

from dotenv import load_dotenv

load_dotenv()

VERSION = "21.1"

CONFIG_DIR = "/config"
DB_PATH = os.path.join(CONFIG_DIR, "bot.db")


def _int(value, default=0):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID = _int(os.getenv("OWNER_ID"))

ARIA2_HOST = os.getenv("ARIA2_HOST", "http://aria2").strip()
if ARIA2_HOST and not ARIA2_HOST.startswith(("http://", "https://")):
    ARIA2_HOST = f"http://{ARIA2_HOST}"
ARIA2_PORT = _int(os.getenv("ARIA2_PORT"), 6800)
ARIA2_SECRET = os.getenv("ARIA2_SECRET", "")

WEBAPP_PORT = _int(os.getenv("WEBAPP_PORT"), 8080)
TIMEZONE = os.getenv("TZ", "UTC").strip() or "UTC"

API_ID = _int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH", "")
CHANNEL_ID = _int(os.getenv("CHANNEL_ID"))
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip().rstrip("/")
WEBAPP_ENABLED = os.getenv("WEBAPP_ENABLED", "0").strip().lower() in ("1", "true", "yes", "on")
LANGUAGE = os.getenv("LANGUAGE", "").strip().lower()
USERBOT_MAX_CONNECTIONS = _int(os.getenv("USERBOT_MAX_CONNECTIONS"), 20)

PROGRESS_EDIT_INTERVAL = 2

RUNTIME_KEYS = {
    "API_ID": int,
    "API_HASH": str,
    "CHANNEL_ID": int,
    "GOOGLE_CLIENT_ID": str,
    "GOOGLE_CLIENT_SECRET": str,
    "GOOGLE_REDIRECT_URI": str,
    "WEBAPP_URL": str,
    "WEBAPP_ENABLED": bool,
    "LANGUAGE": str,
    "USERBOT_MAX_CONNECTIONS": int,
}

DEFAULT_FOLDERS = [
    {"name": "Downloads", "path": "/media/Downloads", "media": ""},
    {"name": "Movies", "path": "/media/Movies", "media": "movie"},
    {"name": "Series", "path": "/media/Series", "media": "tv"},
]

FOLDERS: dict[str, str] = {}
FOLDER_MEDIA: dict[str, str] = {}


def _cast(key, raw):
    kind = RUNTIME_KEYS[key]
    if kind is bool:
        return str(raw).strip().lower() in ("1", "true", "yes", "on")
    if kind is int:
        return _int(raw)
    return str(raw).strip()


def set_folders(items: list[dict]) -> None:
    FOLDERS.clear()
    FOLDER_MEDIA.clear()
    for it in items:
        name = str(it.get("name", "")).strip()
        path = str(it.get("path", "")).strip()
        if not name or not path:
            continue
        FOLDERS[name] = path
        FOLDER_MEDIA[name] = it.get("media") or ""


def folders_as_list() -> list[dict]:
    return [{"name": n, "path": p, "media": FOLDER_MEDIA.get(n, "")} for n, p in FOLDERS.items()]


def folder_media(name: str) -> str:
    return FOLDER_MEDIA.get(name, "")


def default_download_folder() -> str:
    if "Downloads" in FOLDERS:
        return "Downloads"
    return next(iter(FOLDERS), "")


set_folders(DEFAULT_FOLDERS)


async def load_runtime() -> None:
    import db

    g = globals()
    for key in RUNTIME_KEYS:
        raw = await db.get_setting(f"cfg_{key}")
        if raw is not None:
            g[key] = _cast(key, raw)
    raw = await db.get_setting("cfg_FOLDERS")
    if raw:
        try:
            set_folders(json.loads(raw))
        except (ValueError, TypeError):
            pass
    if not g["GOOGLE_REDIRECT_URI"] and g["WEBAPP_URL"]:
        g["GOOGLE_REDIRECT_URI"] = f"{g['WEBAPP_URL']}/oauth2/google/callback"


async def set_runtime(key: str, value) -> None:
    import db

    if key not in RUNTIME_KEYS:
        raise KeyError(key)
    value = _cast(key, value)
    globals()[key] = value
    await db.set_setting(f"cfg_{key}", "1" if value is True else "0" if value is False else str(value))
    if key == "WEBAPP_URL" and not os.getenv("GOOGLE_REDIRECT_URI"):
        globals()["GOOGLE_REDIRECT_URI"] = f"{value}/oauth2/google/callback" if value else ""


async def clear_runtime(key: str) -> None:
    import db

    await db.delete_setting(f"cfg_{key}")
    default = {int: 0, str: "", bool: False}[RUNTIME_KEYS[key]]
    globals()[key] = default


async def save_folders() -> None:
    import db

    await db.set_setting("cfg_FOLDERS", json.dumps(folders_as_list()))
