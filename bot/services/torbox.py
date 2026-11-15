import base64
import hashlib
import re
from urllib.parse import parse_qs, urlparse

import httpx

TB_API_BASE = "https://api.torbox.app/v1/api"


class TorBoxError(Exception):
    pass


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "User-Agent": "NASDownloader/1.0"}


def _raise_from(resp: httpx.Response):
    try:
        body = resp.json()
    except Exception:
        raise TorBoxError(f"TorBox respondió {resp.status_code}")
    detail = body.get("detail") or body.get("error") or f"HTTP {resp.status_code}"
    raise TorBoxError(str(detail))


async def _request(token: str, method: str, path: str, *, timeout: float = 30, **kwargs):
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(method, f"{TB_API_BASE}{path}", headers=_headers(token), **kwargs)
    except httpx.HTTPError as e:
        raise TorBoxError(f"No se pudo conectar con TorBox: {e}") from e
    try:
        body = resp.json()
    except Exception:
        body = None
    if resp.status_code >= 400 or not isinstance(body, dict) or body.get("success") is False:
        if isinstance(body, dict):
            raise TorBoxError(str(body.get("detail") or body.get("error") or f"HTTP {resp.status_code}"))
        raise TorBoxError(f"TorBox respondió {resp.status_code}")
    return body.get("data")


async def check_token(token: str) -> bool:
    try:
        await get_user_info(token)
        return True
    except Exception:
        return False


async def get_user_info(token: str) -> dict:
    data = await _request(token, "GET", "/user/me", timeout=15)
    return data or {}


PLAN_NAMES = {0: "Free", 1: "Essential", 2: "Pro", 3: "Standard"}


def plan_name(plan) -> str:
    return PLAN_NAMES.get(plan, f"Plan {plan}")


def magnet_infohash(magnet: str) -> str | None:
    try:
        qs = parse_qs(urlparse(magnet).query)
    except Exception:
        return None
    for xt in qs.get("xt", []):
        m = re.match(r"urn:btih:([A-Za-z0-9]+)$", xt)
        if not m:
            continue
        h = m.group(1)
        if len(h) == 40:
            return h.lower()
        if len(h) == 32:
            try:
                return base64.b32decode(h.upper()).hex()
            except Exception:
                return None
    return None


def magnet_name(magnet: str) -> str | None:
    try:
        dn = parse_qs(urlparse(magnet).query).get("dn", [None])[0]
        return dn.strip() if dn else None
    except Exception:
        return None


def _bdecode(data: bytes, i: int = 0):
    c = data[i:i + 1]
    if c == b"i":
        end = data.index(b"e", i)
        return int(data[i + 1:end]), end + 1
    if c == b"l":
        i += 1
        out = []
        while data[i:i + 1] != b"e":
            v, i = _bdecode(data, i)
            out.append(v)
        return out, i + 1
    if c == b"d":
        i += 1
        out = {}
        while data[i:i + 1] != b"e":
            k, i = _bdecode(data, i)
            start = i
            v, i = _bdecode(data, i)
            out[k] = v
            if k == b"info":
                out[b"__info_raw__"] = data[start:i]
        return out, i + 1
    colon = data.index(b":", i)
    n = int(data[i:colon])
    start = colon + 1
    return data[start:start + n], start + n


def torrent_info(torrent_bytes: bytes) -> tuple[str | None, str | None]:
    try:
        meta, _ = _bdecode(torrent_bytes, 0)
        raw = meta.get(b"__info_raw__")
        if not raw:
            return None, None
        name = meta.get(b"info", {}).get(b"name", b"")
        return hashlib.sha1(raw).hexdigest(), name.decode("utf-8", "replace") or None
    except Exception:
        return None, None


async def check_cached(token: str, info_hash: str) -> dict | None:
    if not info_hash:
        return None
    data = await _request(
        token, "GET", "/torrents/checkcached",
        params={"hash": info_hash, "format": "object", "list_files": "true"},
    )
    if not data or not isinstance(data, dict):
        return None
    entry = data.get(info_hash) or data.get(info_hash.lower()) or data.get(info_hash.upper())
    if not entry and len(data) == 1:
        entry = next(iter(data.values()))
    if not entry or not isinstance(entry, dict):
        return None
    return {
        "name": entry.get("name"),
        "size": entry.get("size") or 0,
        "files": entry.get("files") or [],
    }


async def check_cached_many(token: str, hashes: list[str]) -> set[str]:
    import asyncio
    clean = []
    for h in hashes:
        h = (h or "").strip().lower()
        if re.fullmatch(r"[0-9a-f]{40}", h) and h not in clean:
            clean.append(h)
    if not clean:
        return set()

    async def one(chunk):
        data = await _request(
            token, "GET", "/torrents/checkcached",
            params={"hash": ",".join(chunk), "format": "object", "list_files": "false"},
        )
        found = set()
        if isinstance(data, dict):
            for k, v in data.items():
                if v:
                    found.add(str(k).lower())
        elif isinstance(data, list):
            for v in data:
                if isinstance(v, str):
                    found.add(v.lower())
                elif isinstance(v, dict) and v.get("hash"):
                    found.add(str(v["hash"]).lower())
        return found

    chunks = [clean[i:i + 50] for i in range(0, len(clean), 50)]
    out: set[str] = set()
    results = await asyncio.gather(*(one(c) for c in chunks), return_exceptions=True)
    ok = [r for r in results if isinstance(r, set)]
    if not ok:
        raise results[0]
    for r in ok:
        out |= r
    return out


async def create_torrent(token: str, *, magnet: str | None = None, torrent_bytes: bytes | None = None,
                         only_if_cached: bool = False) -> dict:
    form = {
        "allow_zip": "true",
        "as_queued": "false",
        "add_only_if_cached": "true" if only_if_cached else "false",
        "seed": "3",
    }
    files = None
    if magnet:
        form["magnet"] = magnet
    elif torrent_bytes:
        files = {"file": ("file.torrent", torrent_bytes, "application/x-bittorrent")}
    else:
        raise TorBoxError("Falta el magnet o el archivo .torrent")
    data = await _request(token, "POST", "/torrents/createtorrent", data=form, files=files, timeout=60) or {}
    return {
        "torrent_id": data.get("torrent_id"),
        "queued_id": data.get("queued_id"),
        "hash": data.get("hash"),
        "name": data.get("name"),
    }


async def get_torrent(token: str, torrent_id: int) -> dict | None:
    data = await _request(token, "GET", "/torrents/mylist", params={"id": torrent_id, "bypass_cache": "true"})
    if isinstance(data, list):
        data = data[0] if data else None
    return data or None


async def list_torrents(token: str) -> list[dict]:
    data = await _request(token, "GET", "/torrents/mylist", params={"bypass_cache": "true"}, timeout=45)
    return [t for t in (data or []) if isinstance(t, dict)]


async def find_by_hash(token: str, info_hash: str) -> dict | None:
    data = await _request(token, "GET", "/torrents/mylist", params={"bypass_cache": "true"})
    for t in data or []:
        if (t.get("hash") or "").lower() == (info_hash or "").lower():
            return t
    return None


async def delete_torrent(token: str, torrent_id: int):
    await _request(token, "POST", "/torrents/controltorrent", json={"torrent_id": int(torrent_id), "operation": "delete"})


async def request_download(token: str, torrent_id: int, file_id: int = 0, zip_link: bool = False) -> str:
    params = {
        "token": token, "torrent_id": int(torrent_id), "file_id": int(file_id),
        "zip_link": "true" if zip_link else "false", "redirect": "false",
    }
    data = await _request(token, "GET", "/torrents/requestdl", params=params)
    if not data or not isinstance(data, str):
        raise TorBoxError("TorBox no devolvió un enlace de descarga")
    return data


async def create_webdownload(token: str, link: str, *, only_if_cached: bool = False) -> dict:
    """Asks TorBox to fetch a link (cloud storage, hosters...) into its cloud. Returns {id, hash, name}."""
    form = {"link": link, "add_only_if_cached": "true" if only_if_cached else "false", "as_queued": "false"}
    data = await _request(token, "POST", "/webdl/createwebdownload", data=form, timeout=60) or {}
    wid = data.get("webdownload_id") or data.get("queued_id")
    if not wid:
        raise TorBoxError("TorBox no aceptó el enlace")
    return {"id": wid, "hash": data.get("hash"), "name": data.get("name")}


async def get_webdownload(token: str, web_id: int) -> dict | None:
    data = await _request(token, "GET", "/webdl/mylist", params={"id": web_id, "bypass_cache": "true"})
    if isinstance(data, list):
        data = data[0] if data else None
    return data or None


async def delete_webdownload(token: str, web_id: int):
    await _request(token, "POST", "/webdl/controlwebdownload", json={"webdl_id": int(web_id), "operation": "delete"})


async def request_webdownload(token: str, web_id: int, file_id: int = 0) -> str:
    params = {"token": token, "web_id": int(web_id), "file_id": int(file_id), "zip_link": "false", "redirect": "false"}
    data = await _request(token, "GET", "/webdl/requestdl", params=params)
    if not data or not isinstance(data, str):
        raise TorBoxError("TorBox no devolvió un enlace de descarga")
    return data


def human_size(n) -> str:
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"
