"""Optional Prowlarr connection: one call searches every indexer configured in Prowlarr.

Settings (database): prowlarr_url, prowlarr_key, search_mode ("builtin" | "prowlarr" | "both").
The API key never leaves the server: download links coming from Prowlarr are stored WITHOUT it
and `sign()` adds it back only when the bot itself fetches the .torrent.
"""
import logging
import re
import urllib.parse

import httpx

import db

logger = logging.getLogger(__name__)

MODES = ("builtin", "prowlarr", "both")
TIMEOUT = 45  # Prowlarr waits for every indexer (and FlareSolverr) before answering


async def get_config() -> tuple[str, str]:
    url = (await db.get_setting("prowlarr_url") or "").strip().rstrip("/")
    key = (await db.get_setting("prowlarr_key") or "").strip()
    return url, key


async def is_configured() -> bool:
    url, key = await get_config()
    return bool(url and key)


async def get_mode() -> str:
    mode = await db.get_setting("search_mode") or "builtin"
    if mode != "builtin" and not await is_configured():
        return "builtin"
    return mode if mode in MODES else "builtin"


async def set_mode(mode: str) -> None:
    if mode not in MODES:
        raise ValueError(mode)
    await db.set_setting("search_mode", mode)


async def uses_prowlarr() -> bool:
    return await get_mode() in ("prowlarr", "both")


async def uses_builtin() -> bool:
    return await get_mode() in ("builtin", "both")


def normalize_url(url: str) -> str | None:
    u = (url or "").strip().rstrip("/")
    if not u:
        return None
    if not re.match(r"^https?://", u, re.I):
        u = "http://" + u
    p = urllib.parse.urlparse(u)
    return u if p.netloc and " " not in u else None


async def save(url: str | None = None, key: str | None = None) -> None:
    if url is not None:
        await db.set_setting("prowlarr_url", url)
    if key is not None:
        await db.set_setting("prowlarr_key", key.strip())


async def clear() -> None:
    await db.delete_setting("prowlarr_url")
    await db.delete_setting("prowlarr_key")
    await db.set_setting("search_mode", "builtin")
    _indexers_cache.clear()


def _headers(key: str) -> dict:
    return {"X-Api-Key": key, "Accept": "application/json"}


def friendly_error(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        if code == 401:
            return "API key incorrecta (HTTP 401)"
        return f"Prowlarr respondió HTTP {code}"
    if isinstance(e, (httpx.ConnectError, httpx.ConnectTimeout)):
        return "no se puede conectar con Prowlarr (¿URL correcta y contenedor en marcha?)"
    if isinstance(e, httpx.TimeoutException):
        return "Prowlarr tardó demasiado en responder"
    return str(e)[:120] or e.__class__.__name__


_indexers_cache: dict[str, list[dict]] = {}


async def indexers(refresh: bool = False) -> list[dict]:
    """Enabled torrent indexers in Prowlarr: [{"id": 1, "name": "…"}]."""
    url, key = await get_config()
    if not (url and key):
        return []
    if not refresh and url in _indexers_cache:
        return _indexers_cache[url]
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{url}/api/v1/indexer", headers=_headers(key))
        r.raise_for_status()
        items = [
            {"id": i["id"], "name": i.get("name") or f"#{i['id']}"}
            for i in r.json()
            if i.get("enable") and (i.get("protocol") or "torrent") == "torrent"
        ]
    _indexers_cache[url] = items
    return items


async def test(url: str | None = None, key: str | None = None) -> dict:
    """{"ok", "version", "indexers", "ms", "error"}. With url/key it tests those values (before saving)."""
    import time
    cur_url, cur_key = await get_config()
    url, key = (url or cur_url).rstrip("/"), (key or cur_key)
    if not (url and key):
        return {"ok": False, "error": "falta la URL o la API key", "version": None, "indexers": 0, "ms": 0}
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{url}/api/v1/system/status", headers=_headers(key))
            r.raise_for_status()
            version = r.json().get("version")
            r2 = await c.get(f"{url}/api/v1/indexer", headers=_headers(key))
            r2.raise_for_status()
            n = sum(1 for i in r2.json() if i.get("enable") and (i.get("protocol") or "torrent") == "torrent")
        _indexers_cache.pop(url, None)
        return {"ok": True, "version": version, "indexers": n, "ms": int((time.monotonic() - t0) * 1000), "error": None}
    except Exception as e:
        return {"ok": False, "version": None, "indexers": 0, "ms": int((time.monotonic() - t0) * 1000),
                "error": friendly_error(e)}


def _strip_key(link: str) -> str:
    """Removes apikey=… from a Prowlarr link before it is stored or sent to any client."""
    p = urllib.parse.urlparse(link)
    q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True) if k.lower() != "apikey"]
    return urllib.parse.urlunparse(p._replace(query=urllib.parse.urlencode(q)))


def redact(text: str) -> str:
    """For logs: hides any apikey=… value."""
    return re.sub(r"(?i)(apikey=)[^&\s]+", r"\1***", text or "")


async def sign(link: str) -> str:
    """Adds the API key back to a Prowlarr link, only for links that point to the configured Prowlarr."""
    url, key = await get_config()
    if not (url and key and link):
        return link
    if urllib.parse.urlparse(link).netloc.lower() != urllib.parse.urlparse(url).netloc.lower():
        return link
    p = urllib.parse.urlparse(link)
    q = urllib.parse.parse_qsl(p.query, keep_blank_values=True) + [("apikey", key)]
    return urllib.parse.urlunparse(p._replace(query=urllib.parse.urlencode(q)))


async def search(query: str, indexer_ids: list[int] | None = None) -> list[dict]:
    """Raw Prowlarr results (torrents only). Raises on connection/HTTP errors so the caller can explain them."""
    url, key = await get_config()
    if not (url and key):
        return []
    params = [("query", query), ("type", "search"), ("limit", "100")]
    for i in indexer_ids or []:
        params.append(("indexerIds", str(i)))
    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        r = await c.get(f"{url}/api/v1/search", params=params, headers=_headers(key))
        r.raise_for_status()
        data = r.json()
    out = []
    for it in data if isinstance(data, list) else []:
        if (it.get("protocol") or "torrent") != "torrent":
            continue
        out.append({
            "title": it.get("title") or "",
            "indexer": it.get("indexer") or "Prowlarr",
            "indexer_id": it.get("indexerId"),
            "size": int(it.get("size") or 0),
            "seeders": int(it.get("seeders") or 0),
            "leechers": int(it.get("leechers") or 0),
            "info_hash": (it.get("infoHash") or "").lower() or None,
            "magnet": it.get("magnetUrl") if str(it.get("magnetUrl") or "").startswith("magnet:") else None,
            "link": _strip_key(it.get("magnetUrl") or it.get("downloadUrl") or "") or None,
            "details_url": it.get("infoUrl") or None,
            "category": ((it.get("categories") or [{}])[0] or {}).get("name") or "General",
        })
    return out
