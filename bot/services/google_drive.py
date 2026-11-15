import asyncio
import os
import re
import time

import httpx

import config
import db

AUTH_BASE = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
DRIVE_API = "https://www.googleapis.com/drive/v3"
SCOPE = "https://www.googleapis.com/auth/drive.readonly"

DOWNLOAD_WORKERS = 16
DOWNLOAD_MIN_SIZE_FOR_SPLIT = 8 * 1024 * 1024

GOOGLE_NATIVE_MIME_PREFIX = "application/vnd.google-apps."

_DRIVE_URL_RE = re.compile(r"drive\.google\.com", re.IGNORECASE)
_FILE_ID_PATTERNS = [
    re.compile(r"/file/d/([a-zA-Z0-9_-]+)"),
    re.compile(r"/folders/([a-zA-Z0-9_-]+)"),
    re.compile(r"[?&]id=([a-zA-Z0-9_-]+)"),
]


class GoogleDriveError(Exception):
    pass


def is_configured() -> bool:
    return bool(config.GOOGLE_CLIENT_ID and config.GOOGLE_CLIENT_SECRET and config.GOOGLE_REDIRECT_URI)


def is_drive_url(text: str) -> bool:
    return bool(_DRIVE_URL_RE.search(text or ""))


def extract_drive_id(url: str) -> tuple[str, bool] | None:
    is_folder_hint = "/folders/" in url
    for pattern in _FILE_ID_PATTERNS:
        m = pattern.search(url)
        if m:
            return m.group(1), is_folder_hint
    return None


def build_auth_url(state: str) -> str:
    from urllib.parse import urlencode
    params = {
        "client_id": config.GOOGLE_CLIENT_ID,
        "redirect_uri": config.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{AUTH_BASE}?{urlencode(params)}"


async def exchange_code(code: str):
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(TOKEN_URL, data={
            "client_id": config.GOOGLE_CLIENT_ID,
            "client_secret": config.GOOGLE_CLIENT_SECRET,
            "redirect_uri": config.GOOGLE_REDIRECT_URI,
            "code": code,
            "grant_type": "authorization_code",
        })
    if resp.status_code != 200:
        raise GoogleDriveError(f"No se pudo intercambiar el codigo: {resp.text}")
    data = resp.json()
    if "refresh_token" not in data:
        raise GoogleDriveError(
            "Google no devolvio un refresh_token (esto pasa si ya habias autorizado antes sin "
            "revocar el acceso). Ve a https://myaccount.google.com/permissions, quita el acceso "
            "a esta app, y vuelve a intentarlo."
        )
    await db.set_setting("google_access_token", data["access_token"])
    await db.set_setting("google_refresh_token", data["refresh_token"])
    await db.set_setting("google_token_expiry", str(time.time() + data.get("expires_in", 3600) - 60))
    return data


async def _refresh_access_token(refresh_token: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(TOKEN_URL, data={
            "client_id": config.GOOGLE_CLIENT_ID,
            "client_secret": config.GOOGLE_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        })
    if resp.status_code != 200:
        raise GoogleDriveError(f"No se pudo renovar el token de Google: {resp.text}")
    data = resp.json()
    await db.set_setting("google_access_token", data["access_token"])
    await db.set_setting("google_token_expiry", str(time.time() + data.get("expires_in", 3600) - 60))
    return data["access_token"]


async def is_connected() -> bool:
    return bool(await db.get_setting("google_refresh_token"))


async def get_access_token() -> str:
    refresh_token = await db.get_setting("google_refresh_token")
    if not refresh_token:
        raise GoogleDriveError("Google Drive no está conectado. Ve a Ajustes → Google Drive.")
    expiry = float(await db.get_setting("google_token_expiry", "0") or 0)
    if time.time() < expiry:
        token = await db.get_setting("google_access_token")
        if token:
            return token
    return await _refresh_access_token(refresh_token)


async def disconnect():
    for key in ("google_access_token", "google_refresh_token", "google_token_expiry", "google_email"):
        await db.delete_setting(key)


async def _headers() -> dict:
    token = await get_access_token()
    return {"Authorization": f"Bearer {token}"}


async def get_account_email() -> str:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            f"{DRIVE_API}/about", params={"fields": "user"}, headers=await _headers(),
        )
    if resp.status_code != 200:
        raise GoogleDriveError(f"No se pudo consultar la cuenta: {resp.text}")
    return resp.json().get("user", {}).get("emailAddress", "desconocida")


_pending_states: set[str] = set()


def new_oauth_state() -> str:
    import uuid
    state = uuid.uuid4().hex
    _pending_states.add(state)
    return state


def consume_oauth_state(state: str) -> bool:
    if state in _pending_states:
        _pending_states.discard(state)
        return True
    return False


async def get_file_metadata(file_id: str) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            f"{DRIVE_API}/files/{file_id}",
            params={"fields": "id,name,mimeType,size", "supportsAllDrives": "true"},
            headers=await _headers(),
        )
    if resp.status_code != 200:
        raise GoogleDriveError(
            "No se pudo acceder al archivo/carpeta de Drive (¿el enlace es correcto y está "
            f"compartido como 'cualquiera con el enlace'?): {resp.text}"
        )
    return resp.json()


async def _list_children(folder_id: str) -> list[dict]:
    files = []
    page_token = None
    while True:
        params = {
            "q": f"'{folder_id}' in parents and trashed = false",
            "fields": "nextPageToken, files(id,name,mimeType,size)",
            "pageSize": 200,
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        }
        if page_token:
            params["pageToken"] = page_token
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(f"{DRIVE_API}/files", params=params, headers=await _headers())
        if resp.status_code != 200:
            raise GoogleDriveError(f"No se pudo listar la carpeta: {resp.text}")
        data = resp.json()
        files.extend(data.get("files", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return files


async def _list_folder_recursive(folder_id: str, results: list):
    for child in await _list_children(folder_id):
        mime = child.get("mimeType", "")
        if mime == "application/vnd.google-apps.folder":
            await _list_folder_recursive(child["id"], results)
        elif mime.startswith(GOOGLE_NATIVE_MIME_PREFIX):
            continue
        else:
            results.append({
                "file_id": child["id"],
                "name": child["name"],
                "size": int(child["size"]) if child.get("size") else None,
            })


async def list_drive_files(url: str) -> list[dict]:
    parsed = extract_drive_id(url)
    if not parsed:
        raise GoogleDriveError("No reconozco ese enlace de Google Drive.")
    file_id, _hint = parsed

    meta = await get_file_metadata(file_id)
    mime = meta.get("mimeType", "")

    results = []
    if mime == "application/vnd.google-apps.folder":
        await _list_folder_recursive(file_id, results)
    elif mime.startswith(GOOGLE_NATIVE_MIME_PREFIX):
        raise GoogleDriveError(
            f"'{meta.get('name')}' es un documento nativo de Google (Docs/Sheets/Slides), "
            "no un archivo descargable."
        )
    else:
        results.append({
            "file_id": file_id,
            "name": meta.get("name") or "archivo",
            "size": int(meta["size"]) if meta.get("size") else None,
        })

    if not results:
        raise GoogleDriveError("No se encontró ningún archivo descargable en ese enlace.")
    return results


async def download_direct(file_id: str, dest_path: str, progress_callback=None, workers: int = DOWNLOAD_WORKERS):
    meta = await get_file_metadata(file_id)
    size = int(meta["size"]) if meta.get("size") else 0

    if size < DOWNLOAD_MIN_SIZE_FOR_SPLIT:
        await _download_sequential(file_id, dest_path, size, progress_callback)
        return

    headers = await _headers()
    workers = max(1, min(workers, 16))
    part_size = max(1024 * 1024, -(-size // workers))
    ranges = []
    start = 0
    while start < size:
        end = min(start + part_size, size) - 1
        ranges.append((start, end))
        start = end + 1

    downloaded = {"bytes": 0}
    fd = os.open(dest_path, os.O_CREAT | os.O_WRONLY, 0o644)
    os.ftruncate(fd, size)

    async def download_range(range_start, range_end):
        range_headers = {**headers, "Range": f"bytes={range_start}-{range_end}"}
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "GET", f"{DRIVE_API}/files/{file_id}",
                params={"alt": "media", "supportsAllDrives": "true"}, headers=range_headers,
            ) as resp:
                if resp.status_code not in (200, 206):
                    body = await resp.aread()
                    raise GoogleDriveError(f"Error al descargar (bytes {range_start}-{range_end}): {body[:200]}")
                offset = range_start
                async for chunk in resp.aiter_bytes(2 * 1024 * 1024):
                    await asyncio.to_thread(os.pwrite, fd, chunk, offset)
                    offset += len(chunk)
                    downloaded["bytes"] += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded["bytes"], size)

    tasks = [asyncio.create_task(download_range(s, e)) for s, e in ranges]
    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                raise r
    finally:
        for t in tasks:
            if not t.done():
                t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        os.close(fd)


async def _download_sequential(file_id: str, dest_path: str, known_size: int, progress_callback=None):
    headers = await _headers()
    downloaded = 0
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream(
            "GET", f"{DRIVE_API}/files/{file_id}",
            params={"alt": "media", "supportsAllDrives": "true"}, headers=headers,
        ) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                raise GoogleDriveError(f"No se pudo descargar el archivo: {body[:300]}")
            with open(dest_path, "wb") as f:
                async for chunk in resp.aiter_bytes(1024 * 1024):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, known_size or downloaded)
