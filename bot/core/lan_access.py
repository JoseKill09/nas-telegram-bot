"""Web app access from a normal browser (local network / VPN), without Telegram and without a domain.

* Off by default. The owner enables it in Settings → Web app → 🏠 Local network and sets the local address
  (e.g. http://192.168.1.50:8080), because from inside Docker the bot cannot know the NAS IP.
* Login: the bot sends a single-use link (valid 5 minutes). Opening it creates a session cookie (30 days).
* Only a SHA-256 hash of each session id is stored in the database; sessions can be closed from the bot.

Settings (database): lan_enabled ("1"/"0"), lan_url, lan_sessions (JSON {hash: info}).
"""
import hashlib
import json
import secrets
import time

import config
import db

TOKEN_TTL = 300                 # single-use login link: 5 minutes
SESSION_TTL = 30 * 24 * 3600    # browser session: 30 days
COOKIE = "nasbot_session"

_tokens: dict[str, tuple[dict, float]] = {}


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


async def is_enabled() -> bool:
    return (await db.get_setting("lan_enabled", "0")) == "1"


async def set_enabled(value: bool) -> None:
    await db.set_setting("lan_enabled", "1" if value else "0")
    if not value:
        await revoke_all()


async def get_url() -> str:
    return (await db.get_setting("lan_url") or "").strip().rstrip("/")


async def set_url(url: str) -> None:
    await db.set_setting("lan_url", url.strip().rstrip("/"))


def normalize_url(raw: str) -> str | None:
    import re
    import urllib.parse
    u = (raw or "").strip().rstrip("/")
    if not u:
        return None
    if not re.match(r"^https?://", u, re.I):
        u = "http://" + u
    p = urllib.parse.urlparse(u)
    return u if p.hostname and " " not in u else None


async def server_needed() -> bool:
    """The web server must run if the Telegram web app OR local network access is enabled."""
    return bool(config.WEBAPP_ENABLED) or await is_enabled()


def _user_info(user) -> dict:
    return {"id": user.id, "username": getattr(user, "username", None) or "",
            "first_name": getattr(user, "first_name", None) or ""}


async def login_link(user) -> str | None:
    """Single-use link for this Telegram user, or None if access is off or the address is not set."""
    url = await get_url()
    if not url or not await is_enabled():
        return None
    now = time.time()
    for t, (_, exp) in list(_tokens.items()):
        if exp < now:
            _tokens.pop(t, None)
    token = secrets.token_urlsafe(24)
    _tokens[token] = (_user_info(user), now + TOKEN_TTL)
    return f"{url}/login?t={token}"


def consume_token(token: str) -> dict | None:
    item = _tokens.pop(token or "", None)
    if not item or item[1] < time.time():
        return None
    return item[0]


async def _sessions() -> dict:
    try:
        return json.loads(await db.get_setting("lan_sessions") or "{}")
    except ValueError:
        return {}


async def _save(sessions: dict) -> None:
    await db.set_setting("lan_sessions", json.dumps(sessions))


async def create_session(user: dict, agent: str = "") -> str:
    sid = secrets.token_urlsafe(32)
    sessions = await _sessions()
    now = int(time.time())
    sessions = {h: s for h, s in sessions.items() if s.get("exp", 0) > now}
    sessions[_hash(sid)] = {"user": user, "created": now, "last": now, "exp": now + SESSION_TTL,
                            "agent": (agent or "")[:80]}
    await _save(sessions)
    return sid


async def session_user(sid: str) -> dict | None:
    if not sid or not await is_enabled():
        return None
    sessions = await _sessions()
    key = _hash(sid)
    s = sessions.get(key)
    now = int(time.time())
    if not s or s.get("exp", 0) < now:
        return None
    if now - s.get("last", 0) > 3600:   # update "last seen" at most once per hour
        s["last"] = now
        await _save(sessions)
    return s["user"]


async def list_sessions() -> list[dict]:
    now = int(time.time())
    out = []
    for key, s in (await _sessions()).items():
        if s.get("exp", 0) > now:
            u = s.get("user") or {}
            out.append({"id": key[:10], "user_id": u.get("id"), "name": u.get("first_name") or u.get("username") or str(u.get("id")),
                        "created": s.get("created"), "last": s.get("last"), "agent": s.get("agent", "")})
    return sorted(out, key=lambda x: x["last"] or 0, reverse=True)


async def revoke(short_id: str) -> bool:
    sessions = await _sessions()
    keys = [k for k in sessions if k.startswith(short_id or "#")]
    for k in keys:
        sessions.pop(k, None)
    await _save(sessions)
    return bool(keys)


async def revoke_sid(sid: str) -> None:
    sessions = await _sessions()
    sessions.pop(_hash(sid or ""), None)
    await _save(sessions)


async def revoke_all() -> None:
    await _save({})
