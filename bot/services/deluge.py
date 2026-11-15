import base64
import logging

import httpx

import db
from qbittorrent import QbError as ClientError

logger = logging.getLogger(__name__)

DEFAULT_URL = "http://deluge:8112"
KEY = "deluge"
PREFIX = "dg"
NEEDS_USER = False

KEYS = ["name", "total_size", "progress", "state", "download_payload_rate", "num_seeds", "eta", "files", "message"]


async def is_enabled() -> bool:
    return await db.get_setting("dg_enabled", "0") == "1"


async def get_config() -> dict:
    return {
        "url": (await db.get_setting("dg_url", DEFAULT_URL) or DEFAULT_URL).rstrip("/"),
        "user": "",
        "password": await db.get_setting("dg_pass", "deluge") or "deluge",
        "keep_seeding": await db.get_setting("dg_keep_seeding", "0") == "1",
    }


class Session:
    def __init__(self, cfg: dict | None = None):
        self._cfg = cfg
        self.client: httpx.AsyncClient | None = None
        self._id = 0

    async def __aenter__(self):
        cfg = self._cfg or await get_config()
        self.client = httpx.AsyncClient(base_url=cfg["url"], timeout=30)
        try:
            ok = await self._rpc("auth.login", cfg["password"])
            if not ok:
                raise ClientError("Wrong Deluge password.")
            if not await self._rpc("web.connected"):
                hosts = await self._rpc("web.get_hosts") or []
                if not hosts:
                    raise ClientError("Deluge Web UI has no daemon connection configured.")
                await self._rpc("web.connect", hosts[0][0])
        except Exception:
            await self.client.aclose()
            raise
        return self

    async def __aexit__(self, *exc):
        if self.client:
            await self.client.aclose()

    async def _rpc(self, method: str, *params):
        self._id += 1
        try:
            resp = await self.client.post("/json", json={"method": method, "params": list(params), "id": self._id})
        except httpx.HTTPError as e:
            raise ClientError(f"Cannot reach Deluge at {self.client.base_url}: {e}")
        if resp.status_code >= 400:
            raise ClientError(f"Deluge: HTTP {resp.status_code}")
        data = resp.json()
        if data.get("error"):
            raise ClientError(f"Deluge: {data['error'].get('message')}")
        return data.get("result")

    async def version(self) -> str:
        try:
            return str(await self._rpc("daemon.info"))
        except ClientError:
            return str(await self._rpc("daemon.get_version"))

    async def add(self, *, magnet: str | None = None, torrent_bytes: bytes | None = None,
                  savepath: str | None = None, paused: bool = False) -> None:
        options = {"add_paused": paused}
        if savepath:
            options["download_location"] = savepath
        if magnet:
            await self._rpc("core.add_torrent_magnet", magnet, options)
        else:
            await self._rpc("core.add_torrent_file", "file.torrent", base64.b64encode(torrent_bytes).decode(), options)

    async def _get(self, h: str, keys=None) -> dict | None:
        out = await self._rpc("core.get_torrent_status", h.lower(), keys or KEYS)
        return out or None

    async def info(self, h: str) -> dict | None:
        return await self._get(h)

    async def status(self, h: str) -> dict | None:
        raw = await self._get(h)
        if raw is None:
            return None
        state = str(raw.get("state", ""))
        progress = float(raw.get("progress") or 0) / 100
        eta = raw.get("eta") or None
        return {
            "name": raw.get("name"), "size": raw.get("total_size") or 0, "progress": progress,
            "dlspeed": raw.get("download_payload_rate") or 0, "seeds": raw.get("num_seeds") or 0,
            "eta": eta if eta and eta > 0 else None,
            "done": progress >= 1 or state == "Seeding",
            "error": (raw.get("message") or state) if state == "Error" else None,
        }

    async def files(self, h: str) -> list[dict]:
        raw = await self._get(h, ["files"])
        return [{"name": f.get("path"), "size": f.get("size") or 0} for f in (raw or {}).get("files", [])]

    async def set_priority(self, h: str, ids: list[int], priority: int) -> None:
        if not ids:
            return
        raw = await self._get(h, ["file_priorities", "files"]) or {}
        count = len(raw.get("files") or [])
        prios = list(raw.get("file_priorities") or [1] * count)
        prios += [1] * (count - len(prios))
        for i in ids:
            if 0 <= i < len(prios):
                prios[i] = 1 if priority > 0 else 0
        await self._rpc("core.set_torrent_options", [h.lower()], {"file_priorities": prios})

    async def set_location(self, h: str, path: str) -> None:
        await self._rpc("core.move_storage", [h.lower()], path)

    async def pause(self, h: str) -> None:
        await self._rpc("core.pause_torrent", [h.lower()])

    async def resume(self, h: str) -> None:
        await self._rpc("core.resume_torrent", [h.lower()])

    async def delete(self, h: str, delete_files: bool = False) -> None:
        await self._rpc("core.remove_torrent", h.lower(), delete_files)


async def test_connection(cfg: dict | None = None) -> str:
    async with Session(cfg) as q:
        return await q.version()


async def wait_metadata(q: Session, h: str, timeout: float = 90) -> list[dict]:
    import asyncio
    loop = asyncio.get_event_loop()
    end = loop.time() + timeout
    while loop.time() < end:
        files = await q.files(h)
        if files:
            return files
        await asyncio.sleep(2)
    return []
