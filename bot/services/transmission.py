import base64
import logging

import httpx

import db
from qbittorrent import QbError as ClientError

logger = logging.getLogger(__name__)

DEFAULT_URL = "http://transmission:9091"
KEY = "transmission"
PREFIX = "tr"
NEEDS_USER = True

FIELDS = ["id", "hashString", "name", "totalSize", "percentDone", "status", "rateDownload",
          "peersSendingToUs", "eta", "error", "errorString", "files"]


async def is_enabled() -> bool:
    return await db.get_setting("tr_enabled", "0") == "1"


async def get_config() -> dict:
    return {
        "url": (await db.get_setting("tr_url", DEFAULT_URL) or DEFAULT_URL).rstrip("/"),
        "user": await db.get_setting("tr_user", "") or "",
        "password": await db.get_setting("tr_pass", "") or "",
        "keep_seeding": await db.get_setting("tr_keep_seeding", "0") == "1",
    }


class Session:
    def __init__(self, cfg: dict | None = None):
        self._cfg = cfg
        self.client: httpx.AsyncClient | None = None
        self.sid = ""

    async def __aenter__(self):
        cfg = self._cfg or await get_config()
        auth = (cfg["user"], cfg["password"]) if cfg["user"] else None
        self.client = httpx.AsyncClient(base_url=cfg["url"], timeout=20, auth=auth)
        try:
            await self._rpc("session-get")
        except ClientError:
            await self.client.aclose()
            raise
        return self

    async def __aexit__(self, *exc):
        if self.client:
            await self.client.aclose()

    async def _rpc(self, method: str, **arguments):
        payload = {"method": method, "arguments": arguments}
        for _ in range(2):
            try:
                resp = await self.client.post("/transmission/rpc", json=payload,
                                              headers={"X-Transmission-Session-Id": self.sid})
            except httpx.HTTPError as e:
                raise ClientError(f"Cannot reach Transmission at {self.client.base_url}: {e}")
            if resp.status_code == 409:
                self.sid = resp.headers.get("X-Transmission-Session-Id", "")
                continue
            if resp.status_code == 401:
                raise ClientError("Wrong Transmission username or password.")
            if resp.status_code >= 400:
                raise ClientError(f"Transmission: HTTP {resp.status_code}")
            data = resp.json()
            if data.get("result") != "success":
                raise ClientError(f"Transmission: {data.get('result')}")
            return data.get("arguments", {})
        raise ClientError("Transmission rejected the session id.")

    async def version(self) -> str:
        return str((await self._rpc("session-get")).get("version", "?"))

    async def add(self, *, magnet: str | None = None, torrent_bytes: bytes | None = None,
                  savepath: str | None = None, paused: bool = False) -> None:
        args = {"paused": paused}
        if savepath:
            args["download-dir"] = savepath
        if magnet:
            args["filename"] = magnet
        else:
            args["metainfo"] = base64.b64encode(torrent_bytes).decode()
        await self._rpc("torrent-add", **args)

    async def _get(self, h: str, fields=None) -> dict | None:
        out = await self._rpc("torrent-get", ids=[h.lower()], fields=fields or FIELDS)
        rows = out.get("torrents") or []
        return rows[0] if rows else None

    async def info(self, h: str) -> dict | None:
        return await self._get(h)

    async def status(self, h: str) -> dict | None:
        raw = await self._get(h)
        if raw is None:
            return None
        err = raw.get("errorString") if raw.get("error") else None
        return {
            "name": raw.get("name"), "size": raw.get("totalSize") or 0, "progress": float(raw.get("percentDone") or 0),
            "dlspeed": raw.get("rateDownload") or 0, "seeds": raw.get("peersSendingToUs") or 0,
            "eta": raw.get("eta") if (raw.get("eta") or 0) > 0 else None,
            "done": float(raw.get("percentDone") or 0) >= 1 or raw.get("status") in (5, 6),
            "error": err,
        }

    async def files(self, h: str) -> list[dict]:
        raw = await self._get(h, ["files"])
        return [{"name": f.get("name"), "size": f.get("length") or 0} for f in (raw or {}).get("files", [])]

    async def set_priority(self, h: str, ids: list[int], priority: int) -> None:
        if not ids:
            return
        key = "files-wanted" if priority > 0 else "files-unwanted"
        await self._rpc("torrent-set", ids=[h.lower()], **{key: ids})

    async def set_location(self, h: str, path: str) -> None:
        await self._rpc("torrent-set-location", ids=[h.lower()], location=path, move=False)

    async def pause(self, h: str) -> None:
        await self._rpc("torrent-stop", ids=[h.lower()])

    async def resume(self, h: str) -> None:
        await self._rpc("torrent-start", ids=[h.lower()])

    async def delete(self, h: str, delete_files: bool = False) -> None:
        await self._rpc("torrent-remove", ids=[h.lower()], **{"delete-local-data": delete_files})


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
