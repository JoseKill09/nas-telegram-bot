import json
import re
import unicodedata
import uuid
from datetime import datetime

import config
import db
from i18n import L

MODES = ("off", "suggest", "auto")

EXT_GROUPS = {
    "video": {"mkv", "mp4", "avi", "mov", "wmv", "m4v", "ts", "webm", "flv", "mpg", "mpeg"},
    "audio": {"mp3", "flac", "wav", "aac", "m4a", "ogg", "opus", "wma"},
    "image": {"jpg", "jpeg", "png", "gif", "webp", "bmp", "tiff", "heic"},
    "archive": {"zip", "rar", "7z", "tar", "gz", "bz2", "xz", "tgz"},
    "document": {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "epub", "mobi", "csv"},
    "subtitle": {"srt", "ass", "sub", "vtt"},
    "disc": {"iso", "img", "bin", "cue"},
}
SOURCES = ("any", "telegram", "link", "torrent", "gdrive", "ytdlp")
EXTRACT = ("ask", "yes", "no")
EPISODE_RE = re.compile(r"(?i)\bS\d{1,2}[ ._-]?E\d{1,3}\b|\b\d{1,2}x\d{2}\b|\bTemporada\b|\bSeason[ ._-]?\d")


async def get_mode() -> str:
    m = await db.get_setting("rules_mode", "suggest")
    return m if m in MODES else "suggest"


async def set_mode(mode: str) -> None:
    await db.set_setting("rules_mode", mode if mode in MODES else "suggest")


async def get_options() -> dict:
    return {
        "conflict": await db.get_setting("rules_conflict", "first"),
        "fallback": await db.get_setting("rules_fallback", ""),
        "multi": await db.get_setting("rules_multi", "ask"),
    }


async def set_option(key: str, value: str) -> None:
    await db.set_setting(f"rules_{key}", value)


async def load() -> list[dict]:
    raw = await db.get_setting("rules_data")
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except ValueError:
        return []
    return [normalize(r) for r in data if isinstance(r, dict)]


async def save(rules: list[dict]) -> None:
    await db.set_setting("rules_data", json.dumps(rules, ensure_ascii=False))


def normalize(r: dict) -> dict:
    return {
        "id": r.get("id") or uuid.uuid4().hex[:6],
        "name": str(r.get("name") or "Rule")[:40],
        "enabled": bool(r.get("enabled", True)),
        "keywords": [k.strip().lower() for k in (r.get("keywords") or []) if str(k).strip()],
        "exclude": [k.strip().lower() for k in (r.get("exclude") or []) if str(k).strip()],
        "regex": str(r.get("regex") or ""),
        "exts": [e.strip().lower().lstrip(".") for e in (r.get("exts") or []) if str(e).strip()],
        "types": [t for t in (r.get("types") or []) if t in EXT_GROUPS],
        "min_mb": _num(r.get("min_mb")),
        "max_mb": _num(r.get("max_mb")),
        "source": r.get("source") if r.get("source") in SOURCES else "any",
        "episode": r.get("episode") if r.get("episode") in ("yes", "no") else "any",
        "users": [int(u) for u in (r.get("users") or []) if str(u).lstrip("-").isdigit()],
        "folder": str(r.get("folder") or ""),
        "subpath": str(r.get("subpath") or "").strip("/"),
        "extract": r.get("extract") if r.get("extract") in EXTRACT else "ask",
        "stop": bool(r.get("stop", True)),
    }


def _num(v):
    try:
        n = float(v)
        return n if n > 0 else 0
    except (TypeError, ValueError):
        return 0


def _ext(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def _norm(text: str) -> str:
    # lower-case, accent-free; . _ - + count as spaces
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"[._\-+]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def kind_to_source(kind: str | None) -> str:
    return {"telegram": "telegram", "link": "link", "rd_link": "link", "gdrive": "gdrive", "ytdlp": "ytdlp",
            "torrent": "torrent"}.get(kind or "", "any")


def matches(rule: dict, name: str, size: int = 0, source: str = "any", user: int | None = None,
            files: list[str] | None = None) -> bool:
    # files = names inside a torrent; ext/type conditions pass if ANY matches
    if not rule["enabled"]:
        return False
    names = [name or ""] + [f for f in (files or []) if f]
    hay = " | ".join(_norm(n) for n in names)
    kws = [_norm(k) for k in rule["keywords"] if _norm(k)]
    if kws and not any(k in hay for k in kws):
        return False
    exc = [_norm(k) for k in rule["exclude"] if _norm(k)]
    if exc and any(k in hay for k in exc):
        return False
    if rule["regex"]:
        try:
            if not any(re.search(rule["regex"], n, re.I) for n in names):
                return False
        except re.error:
            return False
    known = set().union(*EXT_GROUPS.values())
    exts = {_ext(n.lower()) for n in (files or [name or ""]) if n}
    if not files and not (exts & (known | set(rule["exts"]))):
        exts = None  # e.g. a torrent name without extension and no file list yet: can't tell, don't block
    if exts is not None:
        if rule["exts"] and not (exts & set(rule["exts"])):
            return False
        if rule["types"] and not any(e in EXT_GROUPS[t] for e in exts for t in rule["types"]):
            return False
    mb = (size or 0) / 1048576
    if rule["min_mb"] and (not size or mb < rule["min_mb"]):
        return False
    if rule["max_mb"] and (not size or mb > rule["max_mb"]):
        return False
    if rule["source"] != "any" and source != rule["source"]:
        return False
    is_ep = any(bool(EPISODE_RE.search(n)) for n in names)
    if rule["episode"] == "yes" and not is_ep:
        return False
    if rule["episode"] == "no" and is_ep:
        return False
    if rule["users"] and (user is None or int(user) not in rule["users"]):
        return False
    return True


def render_subpath(template: str, name: str, user: int | None = None) -> str:
    now = datetime.now()
    stem = name.rsplit(".", 1)[0] if "." in name else name
    values = {
        "year": f"{now.year}", "month": f"{now.month:02d}", "day": f"{now.day:02d}",
        "ext": _ext(name) or "other", "user": str(user or ""), "name": re.sub(r'[\\/:*?"<>|]', "_", stem)[:60],
        "first": (re.sub(r"[^A-Za-z0-9]", "", stem)[:1] or "_").upper(),
    }
    out = re.sub(r"\{(\w+)\}", lambda m: values.get(m.group(1), m.group(0)), template)
    parts = [re.sub(r'[\\:*?"<>|]', "_", p).strip() for p in out.split("/")]
    return "/".join(p for p in parts if p and p not in (".", ".."))


def destination(rule: dict, name: str, user: int | None = None) -> tuple[str, str]:
    folder = rule["folder"]
    if folder not in config.FOLDERS:
        return "", ""
    return folder, render_subpath(rule["subpath"], name, user) if rule["subpath"] else ""


async def find(name: str, size: int = 0, source: str = "any", user: int | None = None,
               files: list[str] | None = None) -> list[dict]:
    if await get_mode() == "off":
        return []
    out = []
    for r in await load():
        if matches(r, name, size, source, user, files) and destination(r, name, user)[0]:
            out.append(r)
            if r["stop"]:
                break
    return out


async def best(name: str, size: int = 0, source: str = "any", user: int | None = None,
               files: list[str] | None = None) -> dict | None:
    found = await find(name, size, source, user, files)
    if found:
        return found[0]
    fb = (await get_options())["fallback"]
    if fb and fb in config.FOLDERS and await get_mode() != "off":
        return normalize({"id": "fallback", "name": L("Carpeta por defecto", "Default folder"), "folder": fb})
    return None


def describe(rule: dict) -> str:
    conds = []
    if rule["keywords"]:
        conds.append(L("contiene ", "contains ") + "/".join(rule["keywords"]))
    if rule["exclude"]:
        conds.append(L("sin ", "without ") + "/".join(rule["exclude"]))
    if rule["regex"]:
        conds.append("regex")
    if rule["exts"]:
        conds.append("." + "/.".join(rule["exts"]))
    if rule["types"]:
        conds.append("/".join(rule["types"]))
    if rule["min_mb"]:
        conds.append(f"≥{rule['min_mb']:g} MB")
    if rule["max_mb"]:
        conds.append(f"≤{rule['max_mb']:g} MB")
    if rule["source"] != "any":
        conds.append(rule["source"])
    if rule["episode"] == "yes":
        conds.append(L("es episodio", "is episode"))
    if rule["episode"] == "no":
        conds.append(L("no es episodio", "not episode"))
    if rule["users"]:
        conds.append(L("usuarios ", "users ") + ",".join(str(u) for u in rule["users"]))
    return ", ".join(conds) or L("todo", "everything")


def dest_label(rule: dict) -> str:
    return rule["folder"] + (f"/{rule['subpath']}" if rule["subpath"] else "")
