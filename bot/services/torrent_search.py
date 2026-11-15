import asyncio
import html
import json
import logging
import re
import secrets
import time
import unicodedata
import xml.etree.ElementTree as ET
import urllib.parse
from bs4 import BeautifulSoup
import httpx

import db
import prowlarr
import torbox

logger = logging.getLogger(__name__)

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,application/json,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
    "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Upgrade-Insecure-Requests": "1",
}

DEFAULT_TRACKERS = [
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://open.tracker.cl:1337/announce",
    "udp://9.rarbg.to:2920/announce",
    "udp://tracker.openbittorrent.com:80/announce",
    "udp://opentracker.i2p.rocks:6969/announce",
    "udp://tracker.torrent.eu.org:451/announce",
    "udp://open.stealth.si:80/announce",
    "udp://tracker.tiny-vps.com:6969/announce",
    "udp://explodie.org:6969/announce",
]


def normalize_query(text: str) -> str:
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).strip()


def _build_magnet(info_hash: str, name: str) -> str:
    xt = f"urn:btih:{info_hash.lower()}"
    dn = urllib.parse.quote(name)
    trs = "".join(f"&tr={urllib.parse.quote(tr)}" for tr in DEFAULT_TRACKERS)
    return f"magnet:?xt={xt}&dn={dn}{trs}"


def _calc_health(seeders: int, leechers: int) -> dict:
    if seeders >= 25:
        return {"level": "excellent", "label": "Excelente", "color": "green", "icon": "🟢"}
    elif seeders >= 6:
        return {"level": "good", "label": "Buena", "color": "green", "icon": "🟢"}
    elif seeders >= 1:
        return {"level": "medium", "label": "Media", "color": "yellow", "icon": "🟡"}
    else:
        return {"level": "dead", "label": "Baja", "color": "red", "icon": "🔴"}


def _human_size(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024:
            return f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} PB"


def _parse_size(size_str: str) -> int:
    if not size_str:
        return 0
    match = re.search(r"([\d.]+)\s*([KMGTP]?i?B)", size_str, re.IGNORECASE)
    if not match:
        return 0
    val = float(match.group(1))
    unit = match.group(2).upper().replace("I", "")
    mults = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4, "PB": 1024**5}
    return int(val * mults.get(unit, 1))


def parse_media_metadata(title: str) -> dict:
    t = " " + re.sub(r"[\._\-\[\]\(\)\+]", " ", title or "") + " "
    t_lower = t.lower()

    resolution = None
    if re.search(r"\b(2160p|4k|uhd|ultra[\s\._\-]?hd)\b", t_lower):
        resolution = "2160p"
    elif re.search(r"\b(1080p|1080i|full[\s\._\-]?hd|fhd)\b", t_lower):
        resolution = "1080p"
    elif re.search(r"\b(720p|hd)\b", t_lower):
        resolution = "720p"
    elif re.search(r"\b(576p|480p|sd)\b", t_lower):
        resolution = "480p"

    source = "Unknown"
    is_cam = bool(re.search(r"\b(hd[\s\._\-]?cam|camrip|cam|telesync|ts|telecine|tc|screener|scr|dvdscr|hdts)\b", t_lower))
    is_bluray = bool(re.search(r"\b(bluray|blu[\s\._\-]?ray|bdrip|brrip|remux|uhd[\s\._\-]?rip)\b", t_lower))
    is_web = bool(re.search(r"\b(web[\s\._\-]?dl|webrip|web|amzn|nf|hmax|dsnp|atvp|itunes)\b", t_lower))
    is_hdtv = bool(re.search(r"\b(hdtv|pdtv|dsr)\b", t_lower))
    is_dvd = bool(re.search(r"\b(dvdrip|dvd|dvd9|dvd5)\b", t_lower))

    if is_cam:
        source = "CAM/TS"
    elif is_bluray:
        source = "BluRay"
    elif is_web:
        source = "WEB-DL"
    elif is_hdtv:
        source = "HDTV"
    elif is_dvd:
        source = "DVD"

    codec = None
    if re.search(r"\b(hevc|x265|h[\s\._\-]?265|265)\b", t_lower):
        codec = "x265"
    elif re.search(r"\b(avc|x264|h[\s\._\-]?264|264)\b", t_lower):
        codec = "x264"
    elif re.search(r"\b(av1)\b", t_lower):
        codec = "AV1"
    elif re.search(r"\b(xvid|divx)\b", t_lower):
        codec = "XviD"

    hdr_type = None
    is_dv = bool(re.search(r"\b(dolby[\s\._\-]?vision|dovi|dv)\b", t_lower))
    is_hdr10plus = bool(re.search(r"\b(hdr10\+|hdr10plus)\b", t_lower))
    is_hdr = bool(re.search(r"\b(hdr10|hdr)\b", t_lower)) or is_dv or is_hdr10plus
    is_10bit = bool(re.search(r"\b(10bit|10[\s\._\-]?bit|hi10p)\b", t_lower))

    if is_dv and is_hdr:
        hdr_type = "DV HDR"
    elif is_dv:
        hdr_type = "Dolby Vision"
    elif is_hdr10plus:
        hdr_type = "HDR10+"
    elif is_hdr:
        hdr_type = "HDR"

    is_atmos = bool(re.search(r"\b(atmos|dolby[\s\._\-]?atmos)\b", t_lower))
    is_truehd = bool(re.search(r"\b(truehd)\b", t_lower))
    is_dtshd = bool(re.search(r"\b(dts[\s\._\-]?hd|dts[\s\._\-]?ma|dts[\s\._\-]?x)\b", t_lower))
    is_dts = bool(re.search(r"\b(dts)\b", t_lower))
    is_ddp = bool(re.search(r"\b(ddp|dd\+|eac3|e[\s\._\-]?ac[\s\._\-]?3)\b", t_lower))
    is_ac3 = bool(re.search(r"\b(ac3|dd5\.1|dolby[\s\._\-]?digital)\b", t_lower))
    is_5_1 = bool(re.search(r"\b(5[\s\._\-]?1|6ch|7[\s\._\-]?1|8ch)\b", t_lower)) or is_atmos or is_truehd or is_dtshd or is_dts or is_ddp or is_ac3

    audio_features = []
    if is_atmos:
        audio_features.append("Atmos")
    elif is_truehd:
        audio_features.append("TrueHD")
    elif is_dtshd:
        audio_features.append("DTS-HD")
    elif is_dts:
        audio_features.append("DTS")
    elif is_ddp:
        audio_features.append("DD+")
    elif is_ac3:
        audio_features.append("AC3")

    if is_5_1 and not is_atmos and not is_truehd and not is_dtshd:
        audio_features.append("5.1")

    languages = []
    if re.search(r"\b(castellano|spanish|español|spa|esp|es)\b", t_lower):
        languages.append("SPA")
    if re.search(r"\b(latino|lat|latam)\b", t_lower):
        languages.append("LAT")
    if re.search(r"\b(english|eng|en)\b", t_lower):
        languages.append("ENG")
    if re.search(r"\b(italian|ita|it)\b", t_lower):
        languages.append("ITA")
    if re.search(r"\b(french|french|vff|vfi|fre|fr)\b", t_lower):
        languages.append("FRE")
    if re.search(r"\b(german|deutsch|ger|de)\b", t_lower):
        languages.append("GER")
    if re.search(r"\b(japanese|jap|jpn|jp)\b", t_lower):
        languages.append("JAP")
    if re.search(r"\b(dual|multi|multisub|tri[\s\._\-]?audio)\b", t_lower):
        if "DUAL" not in languages:
            languages.append("DUAL")

    if not languages:
        languages.append("ENG")

    score = 6.0

    if is_cam:
        score = 2.0
        if resolution == "2160p" or resolution == "1080p":
            score = 2.5
    else:
        if is_bluray:
            score = 8.5
            if "remux" in t_lower:
                score += 0.8
        elif is_web:
            score = 7.5
        elif is_hdtv:
            score = 6.5
        elif is_dvd:
            score = 5.5

        if resolution == "2160p":
            score += 1.0
        elif resolution == "1080p":
            score += 0.4
        elif resolution == "720p":
            score += 0.0
        elif resolution == "480p":
            score -= 1.0

        if codec in ("x265", "AV1"):
            score += 0.4
        elif codec == "x264":
            score += 0.2
        elif codec == "XviD":
            score -= 0.8

        if is_10bit:
            score += 0.2

        if is_dv or is_hdr10plus:
            score += 0.5
        elif is_hdr:
            score += 0.3

        if is_atmos or is_truehd or is_dtshd:
            score += 0.4
        elif is_5_1:
            score += 0.2

    score = max(1.0, min(10.0, round(score, 1)))

    score_color = "green"
    if score < 4.0:
        score_color = "red"
    elif score < 7.0:
        score_color = "yellow"

    return {
        "resolution": resolution or "N/D",
        "source": source,
        "codec": codec or "N/D",
        "hdr": hdr_type,
        "is_10bit": is_10bit,
        "is_atmos": is_atmos,
        "audio_features": audio_features,
        "languages": languages,
        "quality_score": score,
        "quality_color": score_color,
    }


def is_valid_magnet(value: str | None) -> bool:
    if not value or not isinstance(value, str):
        return False
    v = value.strip().lower()
    return v.startswith("magnet:?") and "xt=urn:btih:" in v


def enrich_item(item: dict) -> dict:
    meta = parse_media_metadata(item.get("title", ""))
    item["meta"] = meta
    return item


_doh_cache: dict[str, tuple[float, str | None]] = {}
_DOH_SERVERS = ("https://1.1.1.1/dns-query", "https://8.8.8.8/resolve")


def _needs_doh(e: Exception) -> bool:
    low = f"{type(e).__name__} {e}".lower()
    return any(m in low for m in (
        "wrong_version_number", "wrong version number", "ssl", "certificate", "getaddrinfo", "name or service",
        "nodename", "temporary failure", "connecterror", "connection refused", "connection reset",
    ))


async def doh_resolve(host: str) -> str | None:
    now = time.monotonic()
    hit = _doh_cache.get(host)
    if hit and hit[0] > now:
        return hit[1]
    ip = None
    for server in _DOH_SERVERS:
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.get(server, params={"name": host, "type": "A"}, headers={"accept": "application/dns-json"})
            for ans in r.json().get("Answer", []) or []:
                if ans.get("type") == 1 and re.fullmatch(r"\d+\.\d+\.\d+\.\d+", ans.get("data", "")):
                    ip = ans["data"]
                    break
        except Exception:
            continue
        if ip:
            break
    _doh_cache[host] = (now + 600, ip)
    return ip


async def dns_diag(host: str) -> str:
    import socket
    try:
        local = await asyncio.to_thread(socket.gethostbyname, host)
    except Exception:
        local = None
    public = await doh_resolve(host)
    if local and public and local != public:
        return f"tu DNS resuelve {host} a {local}, pero el DNS público a {public} (tu DNS lo está redirigiendo/bloqueando)"
    if not local and public:
        return f"tu DNS no resuelve {host}, pero el DNS público sí ({public})"
    if local and not public:
        return f"DNS local {local}; no se pudo consultar el DNS público"
    return ""


DEFAULT_PROXY_URL = "socks5://warp:1080"
_via_proxy: dict[str, float] = {}
_proxy_warned = False


async def get_proxy() -> str | None:
    if (await db.get_setting("src_proxy_enabled", "0")) != "1":
        return None
    return ((await db.get_setting("src_proxy_url", DEFAULT_PROXY_URL)) or "").strip() or None


def _proxy_client(proxy: str, timeout: float, follow_redirects: bool):
    global _proxy_warned
    try:
        return httpx.AsyncClient(proxy=proxy, timeout=timeout, headers=dict(BROWSER_HEADERS), follow_redirects=follow_redirects)
    except Exception as e:
        if not _proxy_warned:
            logger.warning("No se pudo crear el cliente con proxy %s: %s", proxy, e)
            _proxy_warned = True
        return None


class SmartClient:

    def __init__(self, timeout: float = 8, follow_redirects: bool = True, proxy: str | None = None):
        self._timeout, self._fr, self._proxy = timeout, follow_redirects, proxy
        self._c = httpx.AsyncClient(timeout=timeout, headers=dict(BROWSER_HEADERS), follow_redirects=follow_redirects)
        self._pc = None

    async def __aenter__(self):
        await self._c.__aenter__()
        return self

    async def __aexit__(self, *exc):
        if self._pc is not None:
            try:
                await self._pc.__aexit__(*exc)
            except Exception:
                pass
        return await self._c.__aexit__(*exc)

    async def _via_proxy_call(self, method: str, url: str, **kw):
        if self._pc is None:
            self._pc = _proxy_client(self._proxy, self._timeout, self._fr)
            if self._pc is None:
                raise SourceError("proxy no disponible (¿falta reconstruir la imagen?)")
            await self._pc.__aenter__()
        return await getattr(self._pc, method)(url, **kw)

    async def _do(self, method: str, url: str, **kw):
        host = urllib.parse.urlparse(url).hostname or ""
        if self._proxy and _via_proxy.get(host, 0) > time.monotonic():
            try:
                return await self._via_proxy_call(method, url, **dict(kw))
            except Exception:
                _via_proxy.pop(host, None)
        try:
            return await self._direct(method, url, **dict(kw))
        except Exception as e:
            if self._proxy and _needs_doh(e):
                try:
                    resp = await self._via_proxy_call(method, url, **dict(kw))
                    _via_proxy[host] = time.monotonic() + 600
                    return resp
                except Exception:
                    pass
            raise

    async def _direct(self, method: str, url: str, **kw):
        try:
            return await getattr(self._c, method)(url, **kw)
        except Exception as e:
            p = urllib.parse.urlparse(url)
            if p.scheme != "https" or not p.hostname or not _needs_doh(e) or re.fullmatch(r"[\d.]+", p.hostname):
                raise
            ip = await doh_resolve(p.hostname)
            if not ip:
                raise
            hdrs = dict(kw.pop("headers", None) or {})
            hdrs["Host"] = p.netloc
            ext = dict(kw.pop("extensions", None) or {})
            ext["sni_hostname"] = p.hostname
            new_url = url.replace(f"//{p.netloc}", f"//{ip}" + (f":{p.port}" if p.port else ""), 1)
            return await getattr(self._c, method)(new_url, headers=hdrs, extensions=ext, **kw)

    async def get(self, url, **kw):
        return await self._do("get", url, **kw)

    async def post(self, url, **kw):
        return await self._do("post", url, **kw)


async def test_proxy(url: str | None = None) -> dict:
    url = (url or "").strip() or await get_proxy() or DEFAULT_PROXY_URL
    out = {"ok": False, "url": url, "detail": "", "nyaa": None}
    cl = _proxy_client(url, 12, True)
    if cl is None:
        out["detail"] = "no se pudo usar el proxy (falta soporte SOCKS: reconstruye con docker compose up -d --build)"
        return out
    try:
        async with cl as c:
            try:
                r = await c.get("https://www.cloudflare.com/cdn-cgi/trace")
                info = dict(l.split("=", 1) for l in r.text.splitlines() if "=" in l)
                out["ok"] = True
                out["detail"] = f"IP de salida {info.get('ip', '?')} · WARP: {info.get('warp', '?')}"
            except Exception as e:
                out["detail"] = friendly_error(e)
                return out
            try:
                r = await c.head("https://nyaa.si")
                out["nyaa"] = f"nyaa.si responde HTTP {r.status_code}"
            except Exception as e:
                out["nyaa"] = "nyaa.si: " + friendly_error(e)
    except Exception as e:
        out["detail"] = friendly_error(e)
    return out


class SourceError(Exception):
    pass


_BLOCK_MARKERS = (
    "just a moment", "cf-chl", "attention required", "enable javascript and cookies",
    "domain for sale", "this domain may be for sale", "buy this domain", "domain is parked",
)


_last_diag: dict[str, str] = {}


def friendly_error(e: Exception | str) -> str:
    msg = str(e) or type(e).__name__
    low = msg.lower()
    if "wrong_version_number" in low or "wrong version number" in low:
        return ("el servidor no responde por HTTPS (suele ser el DNS del contenedor/router bloqueando o "
                "redirigiendo el dominio). Prueba con http:// o cambia el DNS")
    if "certificate" in low or "ssl" in low:
        return "error de certificado SSL: " + msg[:70]
    if "name or service not known" in low or "getaddrinfo" in low or "nodename" in low or "temporary failure" in low:
        return "no se pudo resolver el dominio (DNS)"
    if "timed out" in low or "timeout" in low:
        return "tiempo de espera agotado"
    if "connection refused" in low:
        return "conexión rechazada"
    return msg[:90]


def _diag_empty(base: str, text: str) -> None:
    m = re.search(r"<title[^>]*>(.*?)</title>", text[:6000], re.I | re.S)
    title = re.sub(r"\s+", " ", m.group(1)).strip()[:60] if m else "sin título"
    _last_diag[base] = f"la web responde pero no reconozco resultados (título: «{title}», {len(text)} bytes)"


def _check_html(resp) -> None:
    if resp.status_code != 200:
        raise SourceError(f"HTTP {resp.status_code}")
    low = resp.text[:4000].lower()
    if any(m in low for m in _BLOCK_MARKERS):
        raise SourceError("Cloudflare o dominio aparcado")


def _mk(key: str, title: str, *, magnet=None, details_url=None, torrent_file_url=None, size_bytes=0,
        size=None, seeders=0, leechers=0, category="General") -> dict:
    spec = SOURCES[key]
    return enrich_item({
        "title": title,
        "provider": spec["name"],
        "provider_key": key,
        "kind": "torrent",
        "magnet": magnet,
        "details_url": details_url,
        "torrent_file_url": torrent_file_url,
        "size_bytes": size_bytes,
        "size": size or _human_size(size_bytes),
        "seeders": seeders,
        "leechers": leechers,
        "category": category,
        "health": _calc_health(seeders, leechers),
    })


def _int(text) -> int | None:
    t = (text or "").strip().replace(",", "")
    return int(t) if t.isdigit() else None


def _parse_apibay_json(items) -> list[dict]:
    out, seen = [], set()
    if not isinstance(items, list) or not items:
        return out
    if str(items[0].get("id")) in ("0", "None") or items[0].get("name") == "No results returned":
        return out
    for it in items:
        name = it.get("name", "")
        h = (it.get("info_hash") or "").strip()
        if not name or not h or h == "0" * 40 or h in seen:
            continue
        seen.add(h)
        size_bytes = int(it.get("size") or 0)
        out.append(_mk("apibay", name, magnet=_build_magnet(h, name), size_bytes=size_bytes,
                       seeders=int(it.get("seeders") or 0), leechers=int(it.get("leechers") or 0),
                       category=str(it.get("category", "General"))))
    return out


def _parse_tpb_html(text: str) -> list[dict]:
    soup = BeautifulSoup(text, "html.parser")
    out, seen = [], set()
    for r in soup.select("table#searchResult tr"):
        name_el = r.select_one(".detName a.detLink, .detName a")
        mag_el = r.select_one('a[href^="magnet:?"]')
        if not name_el or not mag_el:
            continue
        name = name_el.get_text(strip=True)
        magnet = mag_el.get("href")
        m = re.search(r"urn:btih:([a-zA-Z0-9]+)", magnet)
        h = m.group(1).lower() if m else name
        if h in seen:
            continue
        seen.add(h)
        desc = r.select_one(".detDesc")
        size_m = re.search(r"Size\s*([\d\.]+\s*[KMGT]?i?B)", desc.get_text() if desc else "", re.I)
        size_str = size_m.group(1) if size_m else "Desconocido"
        tds = r.select("td")
        seeds = _int(tds[-2].get_text()) if len(tds) >= 2 else None
        leech = _int(tds[-1].get_text()) if tds else None
        out.append(_mk("apibay", name, magnet=magnet, size_bytes=_parse_size(size_str), size=size_str,
                       seeders=seeds or 0, leechers=leech or 0))
    return out


async def _fetch_apibay(client, base: str, query: str) -> list[dict]:
    clean = normalize_query(query)
    target = re.sub(r"[^\w\s\.-]", " ", clean).strip() or query
    enc = urllib.parse.quote(target)
    for url in (f"{base}/q.php?q={enc}", f"{base}/api.php?url=/q.php?q={enc}"):
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                continue
            res = _parse_apibay_json(resp.json())
            if res:
                return res
        except Exception:
            continue
    resp = await client.get(f"{base}/search/{enc}/1/99/0")
    _check_html(resp)
    out = _parse_tpb_html(resp.text)
    if not out:
        _diag_empty(base, resp.text)
    return out


_KNABEN_1337X: dict[str, tuple[float, list[dict]]] = {}


async def _knaben_1337x(client, query: str) -> list[dict]:
    """1337x a través de Knaben (que guarda copia de 1337x): sirve cuando Cloudflare bloquea la web de 1337x.
    Solo se quedan los resultados cuyo origen es 1337x. Se cachea 2 min (los espejos se piden a la vez)."""
    q = normalize_query(query)
    hit = _KNABEN_1337X.get(q)
    if hit and time.monotonic() - hit[0] < 120:
        return [dict(x) for x in hit[1]]
    resp = await client.post("https://api.knaben.org/v1", json={
        "search_type": "100%", "search_field": "title", "query": q, "order_by": "seeders", "order_direction": "desc",
        "from": 0, "size": 300, "hide_unsafe": True})
    if resp.status_code != 200:
        raise SourceError(f"Cloudflare bloquea 1337x y Knaben respondió HTTP {resp.status_code}")
    out, seen = [], set()
    for h in resp.json().get("hits", []) or []:
        if "1337x" not in str(h.get("tracker") or "").lower():
            continue
        title = h.get("title"); ih = (h.get("hash") or "").lower()
        magnet = h.get("magnetUrl") or (_build_magnet(ih, title or ih) if ih else None)
        if not title or not magnet or (ih or magnet) in seen:
            continue
        seen.add(ih or magnet)
        out.append(_mk("1337x", title, magnet=magnet, details_url=h.get("details"), size_bytes=int(h.get("bytes") or 0),
                       seeders=int(h.get("seeders") or 0), leechers=int(h.get("peers") or 0), category=str(h.get("category") or "General")))
    _KNABEN_1337X[q] = (time.monotonic(), out)
    return [dict(x) for x in out]


async def _fetch_1337x(client, base: str, query: str) -> list[dict]:
    resp = await client.get(f"{base}/search/{urllib.parse.quote(normalize_query(query))}/1/")
    try:
        _check_html(resp)
    except SourceError:
        # Todos los dominios de 1337x están detrás del desafío de Cloudflare (403): se usa la copia de Knaben
        if resp.status_code in (403, 503) or "just a moment" in resp.text[:4000].lower():
            return await _knaben_1337x(client, query)
        raise
    soup = BeautifulSoup(resp.text, "html.parser")
    out = []
    for row in soup.select("table.table-list tbody tr, table.ranking tbody tr, .box-info-detail tr"):
        a = row.select_one("td.name a:nth-of-type(2)") or row.select_one("td.name a")
        if not a:
            continue
        href = a.get("href", "")
        size_el = row.select_one("td.size")
        parts = size_el.get_text(strip=True).split() if size_el else []
        size_str = f"{parts[0]} {parts[1]}" if len(parts) > 1 else (parts[0] + " MB" if parts else "Desconocido")
        seeds = row.select_one("td.seeds")
        leech = row.select_one("td.leeches")
        out.append(_mk("1337x", a.get_text(strip=True), details_url=href if href.startswith("http") else f"{base}{href}",
                       size_bytes=_parse_size(size_str), size=size_str,
                       seeders=_int(seeds.get_text()) or 0 if seeds else 0,
                       leechers=_int(leech.get_text()) or 0 if leech else 0))
    if not out:
        _diag_empty(base, resp.text)
    return out


async def _fetch_limetorrents(client, base: str, query: str) -> list[dict]:
    resp = await client.get(f"{base}/search/all/{urllib.parse.quote(normalize_query(query))}/seeds/1/")
    _check_html(resp)
    soup = BeautifulSoup(resp.text, "html.parser")
    out = []
    for r in soup.select(".table2 tr"):
        a = r.select_one(".tt-name a:nth-of-type(2)") or r.select_one(".tt-name a")
        if not a:
            continue
        href = a.get("href", "")
        size_el = r.select_one("td.tdnormal:nth-of-type(3)")
        size_str = size_el.get_text(strip=True) if size_el else "Desconocido"
        sd, lc = r.select_one("td.tdseed"), r.select_one("td.tdleech")
        out.append(_mk("limetorrents", a.get_text(strip=True), details_url=href if href.startswith("http") else f"{base}{href}",
                       size_bytes=_parse_size(size_str), size=size_str,
                       seeders=(_int(sd.get_text()) if sd else None) or 0,
                       leechers=(_int(lc.get_text()) if lc else None) or 0))
    if not out:
        _diag_empty(base, resp.text)
    return out


async def _fetch_eztv(client, base: str, query: str) -> list[dict]:
    resp = await client.get(f"{base}/api/get-torrents?keyword={urllib.parse.quote(normalize_query(query))}&limit=60")
    if resp.status_code != 200:
        raise SourceError(f"HTTP {resp.status_code}")
    out = []
    for t in resp.json().get("torrents", []) or []:
        title = t.get("title") or t.get("filename", "")
        magnet = t.get("magnet_url")
        if not title or not magnet:
            continue
        out.append(_mk("eztv", title, magnet=magnet, size_bytes=int(t.get("size_bytes") or 0),
                       seeders=int(t.get("seeds") or 0), leechers=int(t.get("peers") or 0), category="TV Shows"))
    return out


async def _fetch_yts(client, base: str, query: str) -> list[dict]:
    clean = re.sub(r"\b(1080p|720p|2160p|4k|latino|castellano|spanish|español|dual|bluray|web-dl|hevc|x265|x264|temporada|capitulo)\b",
                   "", query, flags=re.I).strip()
    target = normalize_query(clean) if len(clean) >= 2 else normalize_query(query)
    tokens = [w.lower() for w in target.split() if len(w) >= 3]
    resp = await client.get(f"{base}/api/v2/list_movies.json?query_term={urllib.parse.quote(target)}&limit=30")
    if resp.status_code != 200:
        raise SourceError(f"HTTP {resp.status_code}")
    out = []
    for movie in (resp.json().get("data") or {}).get("movies") or []:
        mt = movie.get("title_long") or movie.get("title", "")
        if tokens and not any(t in mt.lower() for t in tokens):
            continue
        for tor in movie.get("torrents", []):
            title = f"{mt} [{tor.get('quality', '')}] [{(tor.get('type') or '').upper()}] [YTS]"
            size_bytes = int(tor.get("size_bytes") or 0)
            out.append(_mk("yts", title, magnet=_build_magnet(tor.get("hash", ""), title), size_bytes=size_bytes,
                           size=tor.get("size") or None, seeders=int(tor.get("seeds") or 0),
                           leechers=int(tor.get("peers") or 0), category="Movies"))
    return out


async def _fetch_nyaa(client, base: str, query: str) -> list[dict]:
    resp = await client.get(f"{base}/?f=0&c=0_0&q={urllib.parse.quote(normalize_query(query))}&s=seeders&o=desc")
    _check_html(resp)
    soup = BeautifulSoup(resp.text, "html.parser")
    out = []
    for r in soup.select("table.torrent-list tbody tr"):
        links = r.select("td:nth-of-type(2) a:not(.comments)")
        if not links:
            continue
        mag_a = r.select_one('a[href^="magnet:?"]')
        magnet = mag_a.get("href") if mag_a else None
        tor_a = r.select_one('a[href$=".torrent"]')
        tor_url = f"{base}{tor_a.get('href')}" if tor_a and not magnet else None
        if not (magnet or tor_url):
            continue
        size_td, sd, lc, cat_a = (r.select_one(f"td:nth-of-type({n})") for n in (4, 6, 7, 1))
        size_str = size_td.get_text(strip=True) if size_td else "Desconocido"
        ca = cat_a.select_one("a") if cat_a else None
        out.append(_mk("nyaa", links[-1].get_text(strip=True), magnet=magnet, torrent_file_url=tor_url,
                       size_bytes=_parse_size(size_str), size=size_str,
                       seeders=(_int(sd.get_text()) if sd else None) or 0,
                       leechers=(_int(lc.get_text()) if lc else None) or 0,
                       category=(ca.get("title", "Anime") if ca else "Anime")))
    if not out:
        _diag_empty(base, resp.text)
    return out


async def _fetch_knaben(client, base: str, query: str) -> list[dict]:
    resp = await client.post(base, json={
        "search_type": "100%", "search_field": "title", "query": normalize_query(query),
        "order_by": "seeders", "order_direction": "desc", "from": 0, "size": 50, "hide_unsafe": True,
    })
    if resp.status_code != 200:
        raise SourceError(f"HTTP {resp.status_code}")
    out, seen = [], set()
    for h in resp.json().get("hits", []) or []:
        title = h.get("title")
        magnet = h.get("magnetUrl")
        ih = (h.get("hash") or "").lower()
        if not magnet and ih:
            magnet = _build_magnet(ih, title or ih)
        if not title or not magnet:
            continue
        key = ih or magnet
        if key in seen:
            continue
        seen.add(key)
        out.append(_mk("knaben", title, magnet=magnet, size_bytes=int(h.get("bytes") or 0),
                       seeders=int(h.get("seeders") or 0), leechers=int(h.get("peers") or 0),
                       category=str(h.get("category") or "General")))
    return out


async def _fetch_torrentscsv(client, base: str, query: str) -> list[dict]:
    resp = await client.get(f"{base}/service/search?q={urllib.parse.quote(normalize_query(query))}&size=40")
    if resp.status_code != 200:
        raise SourceError(f"HTTP {resp.status_code}")
    data = resp.json()
    items = data.get("torrents", []) if isinstance(data, dict) else data
    out = []
    for t in items or []:
        name, ih = t.get("name"), (t.get("infohash") or "").lower()
        if not name or not ih:
            continue
        out.append(_mk("torrentscsv", name, magnet=_build_magnet(ih, name), size_bytes=int(t.get("size_bytes") or 0),
                       seeders=int(t.get("seeders") or 0), leechers=int(t.get("leechers") or 0)))
    return out


# Built-in sources. All of them are OFF by default: each user decides which ones to enable.
# test_query is what "Test" searches for: a neutral word for general sites and an EMPTY query
# (= latest uploads) for specialised catalogues, so no title is ever hard-coded here.
SOURCES = {
    "apibay": {"label": "🔎 The Pirate Bay", "name": "The Pirate Bay", "main": "https://apibay.org",
               "mirrors": ["https://thepiratebay10.org", "https://tpb.party", "https://thehiddenbay.com"],
               "fn": _fetch_apibay, "test_query": "ubuntu", "about": "General (API)"},
    "yts": {"label": "🔎 YTS", "name": "YTS", "main": "https://yts.mx",
            "mirrors": ["https://yts.lt", "https://yts.am", "https://yts.do"],
            "fn": _fetch_yts, "test_query": "", "about": "Catálogo especializado (API)"},
    "nyaa": {"label": "🔎 Nyaa", "name": "Nyaa", "main": "https://nyaa.si",
             "mirrors": ["https://nyaa.net", "https://nyaa.iss.one"],
             "fn": _fetch_nyaa, "test_query": "", "about": "Catálogo especializado (web)"},
    "knaben": {"label": "🧲 Knaben", "name": "Knaben", "main": "https://api.knaben.org/v1",
               "mirrors": [], "fn": _fetch_knaben, "test_query": "ubuntu", "about": "Agregador de varios índices (API)"},
    "torrentscsv": {"label": "📚 torrents-csv", "name": "torrents-csv", "main": "https://torrents-csv.com",
                    "mirrors": ["https://torrents-csv.ml"], "fn": _fetch_torrentscsv, "test_query": "ubuntu",
                    "about": "Índice abierto (API)"},
    "eztv": {"label": "🔎 EZTV", "name": "EZTV", "main": "https://eztv.re",
             "mirrors": ["https://eztv1.xyz", "https://eztv.wf", "https://eztv.tf"],
             "fn": _fetch_eztv, "test_query": "", "about": "Catálogo especializado (API)"},
    "1337x": {"label": "🔎 1337x", "name": "1337x", "main": "https://1337x.to",
              "mirrors": ["https://1337x.st", "https://1337x.ws", "https://1337x.gd", "https://1337xx.to"],
              "fn": _fetch_1337x, "test_query": "ubuntu", "about": "Web; si Cloudflare la bloquea, sus resultados vía Knaben"},
    "limetorrents": {"label": "🔎 LimeTorrents", "name": "LimeTorrents", "main": "https://www.limetorrents.lol",
                     "mirrors": ["https://limetorrents.pro", "https://limetorrents.cc"],
                     "fn": _fetch_limetorrents, "test_query": "ubuntu", "about": "Web (sin API)"},
}

BUILTIN_KEYS = tuple(SOURCES)
PROVIDERS: dict[str, str] = {}
_removed: set[str] = set()
_TORZNAB_NS = "{http://torznab.com/schemas/2015/feed}"


def _refresh_providers() -> None:
    PROVIDERS.clear()
    PROVIDERS["all"] = "🌐 Todos los buscadores"
    for k, v in SOURCES.items():
        if k not in _removed:
            PROVIDERS[k] = v["label"]


def _torznab_fn(key: str, apikey: str):
    async def fetch(client, base: str, query: str) -> list[dict]:
        url = base if base.rstrip("/").endswith("/api") else base.rstrip("/") + "/api"
        resp = await client.get(url, params={"t": "search", "q": normalize_query(query), "apikey": apikey, "limit": 60})
        if resp.status_code in (401, 403):
            raise SourceError("API key rechazada")
        if resp.status_code != 200:
            raise SourceError(f"HTTP {resp.status_code}")
        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError:
            raise SourceError("la respuesta no es un feed Torznab válido")
        if root.tag == "error":
            raise SourceError(root.get("description") or "error de Torznab")
        out = []
        for it in root.iter("item"):
            title = (it.findtext("title") or "").strip()
            attrs = {a.get("name"): a.get("value") for a in it.findall(f"{_TORZNAB_NS}attr")}
            link = (it.findtext("link") or "").strip()
            enclosure = it.find("enclosure")
            if not link and enclosure is not None:
                link = enclosure.get("url") or ""
            magnet = attrs.get("magneturl") or (link if link.startswith("magnet:") else None)
            ih = (attrs.get("infohash") or "").lower()
            if not magnet and len(ih) == 40:
                magnet = _build_magnet(ih, title)
            size = int(attrs.get("size") or (enclosure.get("length") if enclosure is not None else 0) or it.findtext("size") or 0)
            seeders = int(attrs.get("seeders") or 0)
            peers = int(attrs.get("peers") or 0)
            leechers = int(attrs.get("leechers") or max(0, peers - seeders))
            if not title or not (magnet or link):
                continue
            out.append(_mk(key, title, magnet=magnet,
                           torrent_file_url=None if magnet else link, details_url=it.findtext("comments"),
                           size_bytes=size, seeders=seeders, leechers=leechers,
                           category=(it.findtext("category") or "General")))
        return out

    return fetch


def _clone_fn(key: str, parser: str):
    parent = SOURCES[parser]["fn"]
    name = None

    async def fetch(client, base: str, query: str) -> list[dict]:
        nonlocal name
        res = await parent(client, base, query)
        name = name or SOURCES[key]["name"]
        for r in res:
            r["provider"], r["provider_key"] = name, key
        return res

    return fetch


def _register_custom(entry: dict) -> None:
    key = entry["key"]
    kind = entry["type"]
    if kind == "torznab":
        SOURCES[key] = {
            "label": f"🧩 {entry['name']}", "name": entry["name"], "main": entry["url"], "mirrors": [],
            "fn": _torznab_fn(key, entry.get("apikey", "")), "test_query": "ubuntu", "about": "Torznab",
            "custom": True, "type": kind,
        }
    elif kind == "clone" and entry.get("parser") in BUILTIN_KEYS:
        parent = SOURCES[entry["parser"]]
        SOURCES[key] = {
            "label": f"🧩 {entry['name']}", "name": entry["name"], "main": entry["url"], "mirrors": [],
            "fn": _clone_fn(key, entry["parser"]), "test_query": parent["test_query"],
            "about": parent["about"], "custom": True, "type": kind, "parser": entry["parser"],
            "needs_detail": entry["parser"] in _NEEDS_DETAIL,
        }


async def _custom_entries() -> list[dict]:
    try:
        return json.loads(await db.get_setting("src_custom") or "[]")
    except ValueError:
        return []


async def load_custom() -> None:
    for k in [k for k in SOURCES if k not in BUILTIN_KEYS]:
        SOURCES.pop(k)
    for entry in await _custom_entries():
        _register_custom(entry)
    try:
        _removed.clear()
        _removed.update(json.loads(await db.get_setting("src_removed") or "[]"))
    except ValueError:
        pass
    _refresh_providers()


async def add_custom(name: str, kind: str, url: str, apikey: str = "", parser: str = "") -> str:
    entries = await _custom_entries()
    slug = re.sub(r"[^a-z0-9]", "", name.lower())[:10] or "src"
    key = f"c_{slug}"
    while key in SOURCES:
        key = f"c_{slug}{secrets.token_hex(2)}"
    entry = {"key": key, "name": name.strip()[:30], "type": kind, "url": url, "apikey": apikey, "parser": parser}
    entries.append(entry)
    await db.set_setting("src_custom", json.dumps(entries))
    _register_custom(entry)
    _refresh_providers()
    return key


async def remove_source(key: str) -> None:
    if key in BUILTIN_KEYS:
        _removed.add(key)
        await db.set_setting("src_removed", json.dumps(sorted(_removed)))
    else:
        entries = [e for e in await _custom_entries() if e["key"] != key]
        await db.set_setting("src_custom", json.dumps(entries))
        SOURCES.pop(key, None)
        await db.delete_setting(f"src_urls_{key}")
        await db.delete_setting(f"src_last_{key}")
    _refresh_providers()


async def restore_defaults() -> None:
    _removed.clear()
    await db.delete_setting("src_removed")
    _refresh_providers()


def removed_sources() -> list[str]:
    return sorted(_removed)


_refresh_providers()
_NEEDS_DETAIL = ("1337x", "limetorrents")
_DETAIL_TOP = 8

_fail_count: dict[str, int] = {}
_paused_until: dict[str, float] = {}


def normalize_url(url: str, local_ok: bool = False) -> str | None:
    u = (url or "").strip().rstrip("/")
    if not u:
        return None
    if not re.match(r"^https?://", u, re.I):
        u = "https://" + u
    p = urllib.parse.urlparse(u)
    if not p.netloc or " " in u or ("." not in p.netloc and not local_ok):
        return None
    return u


def _split_urls(raw: str | None, origin_only: bool = False, local_ok: bool = False) -> list[str]:
    out = []
    for part in re.split(r"[\s,]+", raw or ""):
        n = normalize_url(part, local_ok)
        if n and origin_only:
            p = urllib.parse.urlparse(n)
            n = f"{p.scheme}://{p.netloc}"
        if n and n not in out:
            out.append(n)
    return out


def clean_candidates(key: str, raw: str) -> list[str]:
    has_path = bool(urllib.parse.urlparse(SOURCES[key]["main"]).path.strip("/"))
    return _split_urls(raw, origin_only=not has_path, local_ok=bool(SOURCES[key].get("custom")))


async def get_admin_urls(key: str) -> list[str]:
    return _split_urls(await db.get_setting(f"src_urls_{key}"), local_ok=True)


async def set_admin_urls(key: str, urls: list[str]) -> None:
    if urls:
        await db.set_setting(f"src_urls_{key}", "\n".join(urls))
    else:
        await db.delete_setting(f"src_urls_{key}")


async def is_enabled(key: str) -> bool:
    """Built-in sources start OFF (the user enables the ones they want); sources the user adds start ON."""
    if key not in SOURCES or key in _removed:
        return False
    default = "1" if SOURCES[key].get("custom") else "0"
    return (await db.get_setting(f"src_enabled_{key}", default)) != "0"


async def set_enabled(key: str, value: bool) -> None:
    await db.set_setting(f"src_enabled_{key}", "1" if value else "0")


async def enabled_sources() -> list[str]:
    return [k for k in SOURCES if await is_enabled(k)]


async def get_bases(key: str) -> list[str]:
    spec = SOURCES[key]
    ordered = list(await get_admin_urls(key))
    last = normalize_url(await db.get_setting(f"src_last_{key}") or "", True)
    if last:
        ordered.append(last)
    ordered.append(spec["main"].rstrip("/"))
    ordered.extend(m.rstrip("/") for m in spec["mirrors"])
    seen, out = set(), []
    for u in ordered:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out[:8]


async def _race(key: str, bases: list[str], query: str) -> tuple[list[dict], str | None, list[str]]:
    fn = SOURCES[key]["fn"]
    errors: list[str] = []
    async with SmartClient(timeout=8, proxy=await get_proxy()) as client:
        pending: dict[asyncio.Task, str] = {}
        idx = 0

        def launch():
            nonlocal idx
            base = bases[idx]
            idx += 1
            pending[asyncio.ensure_future(fn(client, base, query))] = base

        launch()
        try:
            while pending:
                done, _ = await asyncio.wait(list(pending), timeout=2 if idx < len(bases) else None,
                                             return_when=asyncio.FIRST_COMPLETED)
                if not done:
                    launch()
                    continue
                for t in done:
                    base = pending.pop(t)
                    host = urllib.parse.urlparse(base).netloc
                    try:
                        res = t.result()
                    except Exception as e:
                        errors.append(f"{host}: {friendly_error(e)}")
                        continue
                    if res:
                        return res, base, errors
                    errors.append(f"{host}: {_last_diag.pop(base, 'sin resultados')}")
                if not pending and idx < len(bases):
                    launch()
        finally:
            for t in pending:
                t.cancel()
    return [], None, errors


async def _fill_magnets(items: list[dict]) -> None:
    sem = asyncio.Semaphore(4)

    async def one(it):
        async with sem:
            try:
                m = await asyncio.wait_for(resolve_magnet_if_needed(it), timeout=7)
            except Exception:
                return
            if is_valid_magnet(m):
                it["magnet"] = m

    await asyncio.gather(*(one(i) for i in items))


async def run_source(key: str, query: str, *, respect_pause: bool = True) -> list[dict]:
    if key not in SOURCES:
        return []
    if respect_pause and _paused_until.get(key, 0) > time.monotonic():
        return []
    bases = await get_bases(key)
    results, base, errors = await _race(key, bases, query)
    if results and base:
        _fail_count[key] = 0
        if await db.get_setting(f"src_last_{key}") != base:
            await db.set_setting(f"src_last_{key}", base)
        if key in _NEEDS_DETAIL or SOURCES[key].get("needs_detail"):
            await _fill_magnets([r for r in results[:_DETAIL_TOP] if not r.get("magnet")])
        return results
    _fail_count[key] = _fail_count.get(key, 0) + 1
    if _fail_count[key] >= 3:
        _paused_until[key] = time.monotonic() + 120
        _fail_count[key] = 0
        logger.warning("Buscador %s en pausa 2 min (3 fallos seguidos): %s", key, "; ".join(errors[:3]))
    return []


async def test_source(key: str, only_url: str | None = None) -> dict:
    spec = SOURCES[key]
    q = spec["test_query"]
    t0 = time.monotonic()
    if only_url:
        base = normalize_url(only_url, True)
        if not base:
            return {"ok": False, "count": 0, "base": only_url, "ms": 0, "error": "URL no válida"}
        try:
            async with SmartClient(timeout=10, proxy=await get_proxy()) as client:
                res = await spec["fn"](client, base, q)
            err = None if res else _last_diag.pop(base, "la web responde pero sin resultados (¿cambió la web?)")
        except Exception as e:
            res, err = [], friendly_error(e)
            if _needs_doh(e):
                hint = await dns_diag(urllib.parse.urlparse(base).hostname or "")
                if hint:
                    err += " — " + hint
        return {"ok": bool(res), "count": len(res), "base": base, "ms": int((time.monotonic() - t0) * 1000), "error": err}
    results, base, errors = await _race(key, await get_bases(key), q)
    if results:
        await db.set_setting(f"src_last_{key}", base)
        _fail_count[key] = 0
        _paused_until.pop(key, None)
    return {"ok": bool(results), "count": len(results), "base": base,
            "ms": int((time.monotonic() - t0) * 1000), "error": None if results else "; ".join(errors[:3]) or "sin respuesta"}


async def describe_sources() -> list[dict]:
    out = []
    for key, spec in SOURCES.items():
        if key in _removed:
            continue
        out.append({
            "key": key, "label": spec["label"], "name": spec["name"], "about": spec["about"],
            "custom": bool(spec.get("custom")), "type": spec.get("type", "builtin"),
            "enabled": await is_enabled(key),
            "admin_urls": await get_admin_urls(key),
            "factory_urls": [spec["main"]] + list(spec["mirrors"]),
            "last": await db.get_setting(f"src_last_{key}"),
            "paused": _paused_until.get(key, 0) > time.monotonic(),
        })
    return out


async def _torbox_token() -> str | None:
    if (await db.get_setting("tb_enabled", "0")) == "1":
        return await db.get_setting("tb_token")
    return None


def _item_hash(item: dict) -> str | None:
    m = item.get("magnet")
    return torbox.magnet_infohash(m) if m else None


async def mark_cached(items: list[dict]) -> bool:
    token = await _torbox_token()
    if not token or not items:
        return False
    hashes = {h for h in (_item_hash(i) for i in items) if h}
    if not hashes:
        return False
    try:
        cached = await asyncio.wait_for(torbox.check_cached_many(token, sorted(hashes)), timeout=10)
    except Exception as e:
        logger.warning("No se pudo comprobar la caché de TorBox: %s", e)
        return False
    for i in items:
        h = _item_hash(i)
        i["cached"] = bool(h and h in cached)
    return True


def _prowlarr_item(r: dict) -> dict:
    magnet = r.get("magnet")
    if not is_valid_magnet(magnet) and r.get("info_hash") and len(r["info_hash"]) == 40:
        magnet = _build_magnet(r["info_hash"], r["title"])
    return enrich_item({
        "title": r["title"],
        "provider": f"Prowlarr · {r['indexer']}",
        "provider_key": "prowlarr",
        "kind": "torrent",
        "magnet": magnet if is_valid_magnet(magnet) else None,
        "details_url": r.get("details_url"),
        "torrent_file_url": None if is_valid_magnet(magnet) else r.get("link"),
        "size_bytes": r["size"],
        "size": _human_size(r["size"]),
        "seeders": r["seeders"],
        "leechers": r["leechers"],
        "category": r.get("category") or "General",
        "health": _calc_health(r["seeders"], r["leechers"]),
    })


async def has_search_backend() -> bool:
    """True if a search can return anything: enabled built-in sources and/or a configured Prowlarr."""
    mode = await prowlarr.get_mode()
    if mode in ("prowlarr", "both") and await prowlarr.is_configured():
        return True
    return mode in ("builtin", "both") and bool(await enabled_sources())


async def provider_chips() -> dict[str, str]:
    """Filter chips for the search screen, depending on the search mode."""
    mode = await prowlarr.get_mode()
    chips = {"all": PROVIDERS.get("all", "🌐 Todos los buscadores")}
    if mode in ("builtin", "both"):
        for k in await enabled_sources():
            chips[k] = SOURCES[k]["label"]
    if mode in ("prowlarr", "both"):
        try:
            for ix in await prowlarr.indexers():
                chips[f"prowlarr:{ix['id']}"] = f"🧭 {ix['name']}"
        except Exception as e:
            logger.info("Prowlarr: no se pudo leer la lista de indexadores: %s", e)
    return chips


async def search_torrents_ex(query: str, provider: str = "all", check_torbox: bool = True) -> tuple[list[dict], dict]:
    """Like search_torrents() but also returns {"prowlarr_error": str | None} so the UI can explain a failure."""
    info = {"prowlarr_error": None}
    query = query.strip()
    if not query:
        return [], info

    mode = await prowlarr.get_mode()
    keys, px_ids, use_px = [], None, False
    if provider == "all":
        if mode in ("builtin", "both"):
            keys = await enabled_sources()
        use_px = mode in ("prowlarr", "both")
    elif provider == "builtin":  # fallback button when Prowlarr fails: the enabled built-in sources only
        keys = await enabled_sources()
    elif provider.startswith("prowlarr"):
        use_px = mode in ("prowlarr", "both")
        tail = provider.partition(":")[2]
        px_ids = [int(tail)] if tail.isdigit() else None
    elif provider in SOURCES and await is_enabled(provider):
        keys = [provider]
    if not keys and not use_px:
        return [], info

    async def _px() -> list[dict]:
        try:
            return [_prowlarr_item(r) for r in await prowlarr.search(query, px_ids) if r.get("title")]
        except Exception as e:
            info["prowlarr_error"] = prowlarr.friendly_error(e)
            logger.warning("Prowlarr: la búsqueda falló: %s", info["prowlarr_error"])
            return []

    jobs = [run_source(k, query) for k in keys] + ([_px()] if use_px else [])
    nested = await asyncio.gather(*jobs, return_exceptions=True)
    all_results = []
    for res in nested:
        if isinstance(res, list):
            all_results.extend(res)

    seen = set()
    deduped = []
    for item in all_results:
        raw_key = item.get("magnet") or item.get("details_url") or item["title"]
        m_hash = re.search(r"urn:btih:([a-zA-Z0-9]+)", str(raw_key), re.IGNORECASE)
        key = m_hash.group(1).lower() if m_hash else re.sub(r"[^\w]", "", item["title"].lower())
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    checked = await mark_cached(deduped) if check_torbox else False

    query_words = [w.lower() for w in normalize_query(query).split() if len(w) >= 2]
    min_match = max(1, (len(query_words) + 1) // 2) if query_words else 0

    def score_item(item: dict) -> tuple:
        title_norm = normalize_query(item.get("title", "")).lower()
        matches = sum(1 for w in query_words if w in title_norm)
        seeders = min(item.get("seeders", 0), 200)
        quality = item.get("meta", {}).get("quality_score", 5.0)
        has_magnet = 1 if item.get("magnet") else 0
        cached_first = bool(item.get("cached")) and matches >= min_match
        return (cached_first, matches, quality >= 4.0, quality, seeders, has_magnet)

    deduped.sort(key=score_item, reverse=True)
    if checked:
        for i in deduped:
            i.setdefault("cached", False)
    return deduped, info


async def search_torrents(query: str, provider: str = "all", check_torbox: bool = True) -> list[dict]:
    results, _info = await search_torrents_ex(query, provider, check_torbox)
    return results


async def _fetch_torrent_or_magnet(url: str) -> tuple[str, str | bytes] | None:
    current = await prowlarr.sign(url)  # Prowlarr links are stored without their API key
    try:
        async with SmartClient(timeout=25, follow_redirects=False, proxy=await get_proxy()) as client:
            for _hop in range(6):
                resp = await client.get(current)
                if resp.status_code in (301, 302, 303, 307, 308):
                    location = (resp.headers.get("location") or "").strip()
                    if is_valid_magnet(location):
                        return ("magnet", location)
                    if not location:
                        break
                    current = urllib.parse.urljoin(current, location)
                    continue
                if resp.status_code == 200:
                    body = resp.content
                    if body[:1] == b"d":
                        return ("torrent_file", body)
                    text = body[:4096].decode("utf-8", "ignore").strip()
                    if is_valid_magnet(text):
                        return ("magnet", text)
                    m = re.search(r"magnet:\?xt=urn:btih:[^\"'<>\s]+", text)
                    if m:
                        return ("magnet", html.unescape(m.group(0)))
                logger.warning("Enlace sin .torrent ni magnet (HTTP %s, inicio=%r): %s", resp.status_code, resp.content[:24], prowlarr.redact(current))
                break
    except Exception as e:
        logger.warning("Fallo al resolver enlace de torrent %s: %s", prowlarr.redact(current), prowlarr.redact(str(e)))
    return None


async def resolve_torrent_source(item: dict) -> tuple[str, str | bytes] | None:
    if is_valid_magnet(item.get("magnet")):
        return ("magnet", item["magnet"].strip())

    url = item.get("torrent_file_url")
    if url:
        found = await _fetch_torrent_or_magnet(url)
        if found:
            return found

    magnet = await resolve_magnet_if_needed(item)
    if is_valid_magnet(magnet):
        return ("magnet", magnet.strip())
    if magnet and magnet.startswith("http"):
        return await _fetch_torrent_or_magnet(magnet)
    return None


async def resolve_magnet_if_needed(item: dict) -> str | None:
    if item.get("magnet"):
        return item["magnet"]
    details = item.get("details_url") or ""
    if not details:
        return None

    try:
        async with SmartClient(timeout=8, proxy=await get_proxy()) as client:
            resp = await client.get(details)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")

                mag_a = soup.find("a", href=re.compile(r"^magnet:\?"))
                if mag_a:
                    return mag_a.get("href")

                tor_a = soup.find("a", href=re.compile(r"\.torrent$|/descargar/|/download/"))
                if tor_a:
                    href = tor_a.get("href")
                    if href.startswith("magnet:?"):
                        return href
                    if not href.startswith("http"):
                        base = urllib.parse.urlsplit(details).scheme + "://" + urllib.parse.urlsplit(details).netloc
                        href = urllib.parse.urljoin(base, href)
                    return href

                m_hash = re.search(r"urn:btih:([a-fA-F0-9]{40}|[a-zA-Z2-7]{32})", resp.text)
                if m_hash:
                    return _build_magnet(m_hash.group(1), item.get("title", "torrent"))
    except Exception:
        pass

    return None
