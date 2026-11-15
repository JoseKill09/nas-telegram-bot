import asyncio
import httpx

RD_API_BASE = "https://api.real-debrid.com/rest/1.0"


class RealDebridError(Exception):
    pass


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (compatible; NASDownloader/1.0)",
    }


async def check_token(token: str) -> bool:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{RD_API_BASE}/user", headers=_headers(token))
        return resp.status_code == 200


async def get_user_info(token: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{RD_API_BASE}/user", headers=_headers(token))
        if resp.status_code != 200:
            raise RealDebridError(_extract_error(resp))
        return resp.json()


async def add_magnet(token: str, magnet: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{RD_API_BASE}/torrents/addMagnet",
            headers=_headers(token),
            data={"magnet": magnet},
        )
        if resp.status_code != 201:
            raise RealDebridError(_extract_error(resp))
        return resp.json()["id"]


async def add_torrent(token: str, torrent_bytes: bytes) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.put(
            f"{RD_API_BASE}/torrents/addTorrent",
            headers={**_headers(token), "Content-Type": "application/octet-stream"},
            content=torrent_bytes,
        )
        if resp.status_code != 201:
            raise RealDebridError(_extract_error(resp))
        return resp.json()["id"]


async def get_torrent_info(token: str, torrent_id: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{RD_API_BASE}/torrents/info/{torrent_id}", headers=_headers(token))
        if resp.status_code != 200:
            raise RealDebridError(_extract_error(resp))
        return resp.json()


async def select_files(token: str, torrent_id: str, file_ids: list[int]):
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{RD_API_BASE}/torrents/selectFiles/{torrent_id}",
            headers=_headers(token),
            data={"files": ",".join(str(f) for f in file_ids)},
        )
        if resp.status_code != 204:
            raise RealDebridError(_extract_error(resp))


async def delete_torrent(token: str, torrent_id: str):
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            await client.delete(f"{RD_API_BASE}/torrents/delete/{torrent_id}", headers=_headers(token))
        except Exception:
            pass


async def list_torrents(token: str, page: int = 1, limit: int = 100) -> list:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{RD_API_BASE}/torrents", headers=_headers(token), params={"page": page, "limit": limit}
        )
        if resp.status_code != 200:
            raise RealDebridError(_extract_error(resp))
        return resp.json()


async def list_downloads(token: str, page: int = 1, limit: int = 100) -> list:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{RD_API_BASE}/downloads", headers=_headers(token), params={"page": page, "limit": limit}
        )
        if resp.status_code != 200:
            raise RealDebridError(_extract_error(resp))
        return resp.json()


async def delete_download(token: str, download_id: str):
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            await client.delete(f"{RD_API_BASE}/downloads/delete/{download_id}", headers=_headers(token))
        except Exception:
            pass


async def purge_account(token: str) -> dict:
    deleted_torrents = 0
    while True:
        torrents = await list_torrents(token, page=1, limit=100)
        if not torrents:
            break
        for t in torrents:
            await delete_torrent(token, t["id"])
            deleted_torrents += 1
            await asyncio.sleep(0.1)

    deleted_downloads = 0
    while True:
        downloads = await list_downloads(token, page=1, limit=100)
        if not downloads:
            break
        for d in downloads:
            await delete_download(token, d["id"])
            deleted_downloads += 1
            await asyncio.sleep(0.1)

    return {"torrents": deleted_torrents, "downloads": deleted_downloads}


async def unrestrict_link(token: str, link: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{RD_API_BASE}/unrestrict/link",
            headers=_headers(token),
            data={"link": link},
        )
        if resp.status_code != 200:
            raise RealDebridError(_extract_error(resp))
        return resp.json()


def _extract_error(resp: httpx.Response) -> str:
    try:
        data = resp.json()
        return data.get("error", f"HTTP {resp.status_code}")
    except Exception:
        return f"HTTP {resp.status_code}"


def human_size(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024:
            return f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} PB"
