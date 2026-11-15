import asyncio
import logging

import httpx

import db

logger = logging.getLogger(__name__)

DEFAULT_URL = "http://qbittorrent:8081"
KEY = "qbittorrent"
PREFIX = "qb"
NEEDS_USER = True
DONE_STATES = {"uploading", "stalledUP", "pausedUP", "stoppedUP", "queuedUP", "forcedUP", "checkingUP"}
ERROR_STATES = {"error", "missingFiles"}


class QbError(Exception):
    pass


async def is_enabled() -> bool:
    return await db.get_setting("qb_enabled", "0") == "1"


async def get_config() -> dict:
    return {
        "url": (await db.get_setting("qb_url", DEFAULT_URL) or DEFAULT_URL).rstrip("/"),
        "user": await db.get_setting("qb_user", "admin") or "admin",
        "password": await db.get_setting("qb_pass", "") or "",
        "keep_seeding": await db.get_setting("qb_keep_seeding", "0") == "1",
    }


class Session:
    def __init__(self, cfg: dict | None = None):
        self._cfg = cfg
        self.client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        cfg = self._cfg or await get_config()
        self.client = httpx.AsyncClient(base_url=cfg["url"] + "/api/v2", timeout=20, headers={"Referer": cfg["url"]})
        try:
            resp = await self.client.post("/auth/login", data={"username": cfg["user"], "password": cfg["password"]})
        except httpx.HTTPError as e:
            await self.client.aclose()
            raise QbError(f"Cannot reach qBittorrent at {cfg['url']}: {e}")
        if resp.status_code == 403:
            await self.client.aclose()
            raise QbError("qBittorrent banned this IP after failed logins (wait a few minutes).")
        if resp.status_code != 200 or resp.text.strip() != "Ok.":
            await self.client.aclose()
            raise QbError("Wrong qBittorrent username or password.")
        return self

    async def __aexit__(self, *exc):
        if self.client:
            await self.client.aclose()

    async def _req(self, method: str, path: str, **kw):
        try:
            resp = await self.client.request(method, path, **kw)
        except httpx.HTTPError as e:
            raise QbError(str(e))
        if resp.status_code >= 400:
            raise QbError(f"qBittorrent {path}: HTTP {resp.status_code} {resp.text[:120]}")
        return resp

    async def version(self) -> str:
        return (await self._req("GET", "/app/version")).text.strip()

    async def add(self, *, magnet: str | None = None, torrent_bytes: bytes | None = None,
                  savepath: str | None = None, paused: bool = False) -> None:
        data = {"tags": "nasbot", "autoTMM": "false"}
        if savepath:
            data["savepath"] = savepath
        if paused:
            data["paused"] = "true"
            data["stopped"] = "true"
        if magnet:
            data["urls"] = magnet
            await self._req("POST", "/torrents/add", data=data)
        else:
            await self._req("POST", "/torrents/add", data=data,
                            files={"torrents": ("file.torrent", torrent_bytes, "application/x-bittorrent")})

    async def status(self, h: str) -> dict | None:
        raw = await self.info(h)
        if raw is None:
            return None
        state = raw.get("state", "")
        return {
            "name": raw.get("name"), "size": raw.get("size") or 0, "progress": float(raw.get("progress") or 0),
            "dlspeed": raw.get("dlspeed") or 0, "seeds": raw.get("num_seeds") or 0, "eta": raw.get("eta"),
            "done": state in DONE_STATES, "error": state if state in ERROR_STATES else None,
        }

    async def info(self, h: str) -> dict | None:
        rows = (await self._req("GET", "/torrents/info", params={"hashes": h})).json()
        return rows[0] if rows else None

    async def files(self, h: str) -> list[dict]:
        try:
            return (await self._req("GET", "/torrents/files", params={"hash": h})).json()
        except QbError:
            return []

    async def set_priority(self, h: str, ids: list[int], priority: int) -> None:
        if ids:
            await self._req("POST", "/torrents/filePrio",
                            data={"hash": h, "id": "|".join(str(i) for i in ids), "priority": priority})

    async def set_location(self, h: str, path: str) -> None:
        await self._req("POST", "/torrents/setLocation", data={"hashes": h, "location": path})

    async def pause(self, h: str) -> None:
        try:
            await self._req("POST", "/torrents/pause", data={"hashes": h})
        except QbError:
            await self._req("POST", "/torrents/stop", data={"hashes": h})

    async def resume(self, h: str) -> None:
        try:
            await self._req("POST", "/torrents/resume", data={"hashes": h})
        except QbError:
            await self._req("POST", "/torrents/start", data={"hashes": h})

    async def delete(self, h: str, delete_files: bool = False) -> None:
        await self._req("POST", "/torrents/delete",
                        data={"hashes": h, "deleteFiles": "true" if delete_files else "false"})


async def test_connection(cfg: dict | None = None) -> str:
    async with Session(cfg) as q:
        return await q.version()


async def wait_metadata(q: Session, h: str, timeout: float = 90) -> list[dict]:
    loop = asyncio.get_event_loop()
    end = loop.time() + timeout
    while loop.time() < end:
        files = await q.files(h)
        if files:
            return files
        await asyncio.sleep(2)
    return []
