import logging
import _pathsetup

import asyncio
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path as PyPath
from typing import Optional, Dict, Any, List, Union

from fastapi import FastAPI, Header, HTTPException, Depends, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneNumberInvalidError

import archive_utils
import config
import db
import downloader
import filemanager
import google_drive
import handlers_downloads as h_dl
import handlers_files as h_files
import handlers_realdebrid as h_rd
import handlers_settings as h_settings
import handlers_torbox as h_tb
import real_debrid
import tmdb_helper
import torbox
import torrent_search
import torrent_clients
import backup as backup_svc
import disk as disk_svc
import folders as folders_svc
import notifier
import rules as rules_svc
import ytdlp_downloader
from utils import task_client, client_label
from webapp_auth import validate_init_data

STATIC_DIR = PyPath(__file__).parent / "static"

import mimetypes
mimetypes.add_type("application/manifest+json", ".webmanifest")

_state = {"application": None}


def set_application(application):
    _state["application"] = application


def _get_context():
    application = _state["application"]
    if application is None:
        raise HTTPException(status_code=503, detail="El bot todavía no está listo")
    return application


app = FastAPI(title="NAS Telegram Bot - Panel")


@app.get("/healthz", include_in_schema=False)
@app.get("/api/health", include_in_schema=False)
async def health_check():
    return JSONResponse({"status": "ok", "app": "nas-telegram-bot"})


@app.get("/privacy", include_in_schema=False)
@app.get("/terms", include_in_schema=False)
async def legal_page(request: Request):
    name = "terms.html" if request.url.path.startswith("/terms") else "privacy.html"
    return FileResponse(str(PyPath(__file__).parent / "static" / name), media_type="text/html")


@app.middleware("http")
async def no_cache_static(request: Request, call_next):
    response = await call_next(request)
    if request.url.path in ("/", "/index.html", "/style.css", "/app.js", "/i18n.js", "/sw.js", "/manifest.webmanifest"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


# ── Optional API token for external apps / services ─────────────────────────────
# If API_TOKEN is set in .env, the REST API also accepts «Authorization: Bearer <API_TOKEN>» and acts as
# the owner. Leave it empty (default) to only allow the Telegram web app. Use a long random value
# (e.g. `openssl rand -hex 32`) and never expose it publicly.
_API_TOKEN = os.environ.get("API_TOKEN", "").strip()
if _API_TOKEN and len(_API_TOKEN) < 24:
    logging.getLogger(__name__).warning("API_TOKEN is too short (<24 chars): external API access disabled")
    _API_TOKEN = ""


def _api_token_user(authorization: str):
    import hmac as _hmac
    if _API_TOKEN and authorization.startswith("Bearer ") and _hmac.compare_digest(authorization[7:].strip(), _API_TOKEN):
        return {"id": config.OWNER_ID, "username": "api", "first_name": "API"}
    return None


def _validate_or_403(x_telegram_init_data: str, init_data: str) -> dict:
    user = validate_init_data(x_telegram_init_data or init_data, config.BOT_TOKEN)
    if not user:
        raise HTTPException(status_code=403, detail="Autenticación de Telegram inválida")
    return user


async def _browser_user(request: Request | None, x_telegram_init_data: str, init_data: str) -> dict | None:
    """Session cookie of local-network access, used only when the request lacks a Telegram signature."""
    if request is None or x_telegram_init_data or init_data:
        return None
    import lan_access
    sid = request.cookies.get(lan_access.COOKIE)
    return await lan_access.session_user(sid) if sid else None


async def require_owner(
    request: Request,
    x_telegram_init_data: str = Header(default=""),
    init_data: str = Query(default=""),
    authorization: str = Header(default=""),
) -> dict:
    api_user = _api_token_user(authorization)
    if api_user:
        return api_user
    user = await _browser_user(request, x_telegram_init_data, init_data) or _validate_or_403(x_telegram_init_data, init_data)
    if user.get("id") != config.OWNER_ID:
        raise HTTPException(status_code=403, detail="No autorizado")
    return user


async def require_authorized(
    request: Request,
    x_telegram_init_data: str = Header(default=""),
    init_data: str = Query(default=""),
    authorization: str = Header(default=""),
) -> dict:
    api_user = _api_token_user(authorization)
    if api_user:
        return api_user
    user = await _browser_user(request, x_telegram_init_data, init_data) or _validate_or_403(x_telegram_init_data, init_data)
    user_id = user.get("id")
    if user_id != config.OWNER_ID:
        if not await db.is_authorized_user(user_id):
            raise HTTPException(status_code=403, detail="No autorizado")
        try:
            await db.update_authorized_user_info(user_id, user.get("username"), user.get("first_name"))
        except Exception:
            pass
    return user


def _ensure_task_owner(task: dict, user: dict):
    if user.get("id") != config.OWNER_ID and task.get("requested_by") != user.get("id"):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta tarea")


def _safe(fn, fallback=None):
    try:
        return fn()
    except Exception:
        return fallback


def _task_public(
    task: dict,
    telegram_progress: dict | None = None,
    gdrive_progress: dict | None = None,
    extract_progress: dict | None = None,
    upload_progress: dict | None = None,
) -> dict:
    data = {
        "id": task["id"],
        "kind": task["kind"],
        "filename": task["filename"],
        "status": task["status"],
        "dest_folder": task["dest_folder"],
        "priority": task.get("priority") or 0,
        "error": task.get("error"),
        "progress": None,
        "speed": None,
        "eta": None,
        "size": filemanager.human_size(task["total_size"]) if task.get("total_size") else None,
        "downloaded": None,
        "extract_after": bool(task.get("extract_after")),
        "url": task.get("url"),
        "scheduled_for": task.get("scheduled_for"),
        "client": task_client(task),
        "client_label": client_label(task, with_emoji=False),
    }

    if task["kind"] in ("telegram", "gdrive", "extract", "upload"):
        if task["kind"] == "telegram":
            source = telegram_progress
        elif task["kind"] == "gdrive":
            source = gdrive_progress
        elif task["kind"] == "extract":
            source = extract_progress
        else:
            source = upload_progress

        prog = (source or {}).get(task["id"])
        if prog:
            current, total, speed = prog.get("bytes", 0), prog.get("total", 0), prog.get("speed", 0)
            if total:
                data["progress"] = round(current / total * 100, 1)
                data["size"] = filemanager.human_size(total)
                if speed and speed > 0 and total > current:
                    data["eta"] = _format_duration((total - current) / speed)
            data["downloaded"] = filemanager.human_size(current)
            if speed:
                data["speed"] = f"{speed / (1024 * 1024):.2f} MB/s"
        return data

    if task["gid"] and task["status"] in ("downloading", "paused"):
        dl = _safe(lambda: downloader.get_download(task["gid"]))
        if dl is not None:
            progress = _safe(lambda: dl.progress)
            if progress is not None:
                data["progress"] = round(progress, 1)
            data["speed"] = _safe(lambda: dl.download_speed_string())
            data["eta"] = _safe(lambda: dl.eta_string())
            size_str = _safe(lambda: dl.total_length_string())
            if not size_str:
                total = _safe(lambda: dl.total_length)
                if total:
                    size_str = filemanager.human_size(total)
            if size_str:
                data["size"] = size_str
            downloaded_str = _safe(lambda: dl.completed_length_string())
            if not downloaded_str:
                completed = _safe(lambda: dl.completed_length)
                if completed is not None:
                    downloaded_str = filemanager.human_size(completed)
            if downloaded_str:
                data["downloaded"] = downloaded_str
    return data


@app.get("/api/state")
async def get_state(_user: dict = Depends(require_authorized)):
    all_tasks = []
    for status in ("downloading", "paused", "queued", "scheduled"):
        all_tasks.extend(await db.get_tasks_by_status(status))

    is_owner_user = _user.get("id") == config.OWNER_ID
    tasks = [t for t in all_tasks if t["kind"] in ("link", "rd_link", "tb_link", "telegram", "gdrive", "extract", "upload")]
    if not is_owner_user:
        tasks = [t for t in tasks if t.get("requested_by") == _user.get("id")]
    status_rank = {"downloading": 0, "paused": 1, "queued": 2, "scheduled": 3}
    tasks.sort(key=lambda t: (status_rank.get(t["status"], 4), -(t.get("priority") or 0), t["id"]))

    application = _state["application"]
    telegram_progress = application.bot_data.get("telegram_progress", {}) if application else {}
    gdrive_progress = application.bot_data.get("gdrive_progress", {}) if application else {}
    extract_progress = application.bot_data.get("extract_progress", {}) if application else {}
    upload_progress = application.bot_data.get("upload_progress", {}) if application else {}

    rd_torrents = []
    for torrent_id, state in h_rd.rd_torrent_states.items():
        if "dest_folder" not in state:
            continue
        if not is_owner_user and state.get("requested_by") != _user.get("id"):
            continue
        snap = state.get("last_snapshot", {})
        total = snap.get("total") or 0
        pct = snap.get("progress", 0)
        bytes_done = total * pct / 100
        speed = snap.get("speed", 0)
        rd_torrents.append({
            "torrent_id": torrent_id,
            "provider": state.get("provider", "realdebrid"),
            "name": state.get("torrent_name", "torrent"),
            "dest_folder": state.get("dest_folder"),
            "status": snap.get("status", "queued"),
            "progress": pct,
            "speed": speed,
            "seeders": snap.get("seeders", 0),
            "size": filemanager.human_size(total) if total else None,
            "downloaded": filemanager.human_size(bytes_done) if total else None,
            "eta": _format_duration((total - bytes_done) / speed) if (speed and total > bytes_done) else None,
        })

    return {
        "tasks": [_task_public(t, telegram_progress, gdrive_progress, extract_progress, upload_progress) for t in tasks],
        "rd_torrents": rd_torrents,
        "max_parallel_telegram": await h_dl.get_max_parallel("telegram"),
        "max_parallel_aria2": await h_dl.get_max_parallel("aria2"),
        "max_parallel_gdrive": await h_dl.get_max_parallel("gdrive"),
        "aria2_workers": int(await db.get_setting("aria2_workers", "16")),
        "extract_delete_original": await db.get_setting("extract_delete_original", "0") == "1",
        "folders": list(config.FOLDERS.keys()),
        "folder_media": dict(config.FOLDER_MEDIA),
        "is_owner": is_owner_user,
        "disk_free": filemanager.get_disk_space_info(next(iter(config.FOLDERS), "Downloads")).get("free_str"),
    }


@app.get("/api/torrent/providers")
async def torrent_providers(_user: dict = Depends(require_authorized)):
    return {
        "providers": await torrent_search.provider_chips(),
        "torbox_check": bool(await db.get_setting("tb_enabled", "0") == "1" and await db.get_setting("tb_token")),
    }


@app.get("/api/torrent/search")
async def search_torrents_endpoint(
    query: str,
    provider: str = "all",
    _user: dict = Depends(require_authorized)
):
    query = query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Escribe un término de búsqueda")

    if provider == "all" and not await torrent_search.has_search_backend():
        # Every search source comes OFF by default: tell the web app so it can explain it.
        return {"query": query, "provider": provider, "count": 0, "results": [], "no_sources": True}
    results, info = await torrent_search.search_torrents_ex(query, provider=provider)
    return {
        "query": query,
        "provider": provider,
        "count": len(results),
        "results": results,
        "prowlarr_error": info.get("prowlarr_error"),
    }


# ── Prowlarr (optional) and search mode ─────────────────────────────────────────
class ProwlarrBody(BaseModel):
    url: str | None = None
    apikey: str | None = None


class SearchModeBody(BaseModel):
    mode: str


@app.get("/api/prowlarr")
async def prowlarr_get(_user: dict = Depends(require_owner)):
    import prowlarr
    url, key = await prowlarr.get_config()
    return {"url": url, "has_key": bool(key), "configured": bool(url and key),
            "mode": await prowlarr.get_mode(), "modes": list(prowlarr.MODES)}


@app.post("/api/prowlarr")
async def prowlarr_set(body: ProwlarrBody, _user: dict = Depends(require_owner)):
    import prowlarr
    cur_url, cur_key = await prowlarr.get_config()
    url = prowlarr.normalize_url(body.url) if body.url is not None else cur_url
    if body.url is not None and not url:
        raise HTTPException(status_code=400, detail="URL no válida")
    key = (body.apikey or "").strip() or cur_key
    result = await prowlarr.test(url, key)
    if result["ok"]:
        await prowlarr.save(url=url, key=key)
    return result


@app.post("/api/prowlarr/test")
async def prowlarr_test(_user: dict = Depends(require_owner)):
    import prowlarr
    return await prowlarr.test()


@app.post("/api/prowlarr/delete")
async def prowlarr_delete(_user: dict = Depends(require_owner)):
    import prowlarr
    await prowlarr.clear()
    return {"ok": True}


@app.post("/api/search_mode")
async def search_mode_set(body: SearchModeBody, _user: dict = Depends(require_owner)):
    import prowlarr
    if body.mode not in prowlarr.MODES:
        raise HTTPException(status_code=400, detail="Modo no válido")
    if body.mode != "builtin" and not await prowlarr.is_configured():
        raise HTTPException(status_code=400, detail="Primero conecta Prowlarr")
    await prowlarr.set_mode(body.mode)
    return {"ok": True, "mode": body.mode}


class ResolveMagnetBody(BaseModel):
    magnet: str | None = None
    details_url: str | None = None


@app.post("/api/torrent/resolve_magnet")
async def resolve_magnet_endpoint(body: ResolveMagnetBody, _user: dict = Depends(require_authorized)):
    if body.magnet:
        return {"kind": "torrent", "magnet": body.magnet}
    if not body.details_url:
        raise HTTPException(status_code=400, detail="Falta el enlace del contenido")

    magnet = await torrent_search.resolve_magnet_if_needed({"details_url": body.details_url})
    if not magnet:
        raise HTTPException(status_code=400, detail="No se pudo resolver el enlace del torrent")
    return {"kind": "torrent", "magnet": magnet}


class PrepareTorrentBody(BaseModel):
    magnet: str | None = None
    details_url: str | None = None
    torrent_file_url: str | None = None


@app.post("/api/torrent/prepare")
async def prepare_torrent_endpoint(body: PrepareTorrentBody, _user: dict = Depends(require_authorized)):
    providers = await h_settings.available_providers()
    if not providers:
        raise HTTPException(
            status_code=400,
            detail="No hay ningún proveedor configurado. Ve a Ajustes → Proveedores y añade tu API Token de Real-Debrid o TorBox.",
        )
    source = await torrent_search.resolve_torrent_source({
        "magnet": body.magnet,
        "details_url": body.details_url,
        "torrent_file_url": body.torrent_file_url,
    })
    if not source:
        raise HTTPException(status_code=400, detail="No se pudo extraer el enlace magnet ni el .torrent para este resultado")
    kind, value = source
    key = h_tb.stash_source(kind, value, _user.get("id"))
    return {
        "key": key,
        "name": h_tb.pending_sources[key]["name"],
        "providers": [{"id": p, "label": h_settings.PROVIDER_LABELS[p]} for p in providers],
    }


class AddTorrentBody(BaseModel):
    key: str
    provider: str


@app.post("/api/torrent/add")
async def add_torrent_endpoint(body: AddTorrentBody, _user: dict = Depends(require_authorized)):
    src = h_tb.pending_sources.get(body.key)
    if not src:
        raise HTTPException(status_code=404, detail="Esta solicitud expiró. Vuelve a empezar.")
    if _user.get("id") != config.OWNER_ID and src.get("requested_by") != _user.get("id"):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta solicitud")
    if body.provider not in await h_settings.available_providers():
        raise HTTPException(status_code=400, detail="Ese proveedor no está configurado o está desactivado")
    h_tb.pending_sources.pop(body.key, None)

    try:
        result = await h_tb.prepare(body.provider, src["kind"], src["value"], _user.get("id"))
    except real_debrid.RealDebridError as e:
        raise HTTPException(status_code=400, detail=f"Error al añadir el torrent: {e}")
    except torbox.TorBoxError as e:
        raise HTTPException(status_code=400, detail=f"Error de TorBox: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error inesperado: {e}")

    select_files = result.get("select_files", True)
    return {
        "provider": body.provider,
        "torrent_id": result["torrent_id"],
        "torrent_name": result["torrent_name"],
        "select_files": select_files,
        "cached": result.get("cached", body.provider == "realdebrid"),
        "files": [
            {"id": f["id"], "name": f["path"].split("/")[-1], "size": filemanager.human_size(f["bytes"])}
            for f in result["files"]
        ] if select_files else [],
        "selected": list(result["selected"]) if select_files else [],
    }


def _recent_pending(t: dict) -> bool:
    # pending requests older than 3 days are considered abandoned
    try:
        created = datetime.strptime((t.get("created_at") or "")[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return False
    return (datetime.now(h_dl.LOCAL_TZ).replace(tzinfo=None) - created).total_seconds() < 3 * 86400


@app.get("/api/pending")
async def get_pending(_user: dict = Depends(require_authorized)):
    # requests started in the chat that still wait for a destination folder
    is_owner_user = _user.get("id") == config.OWNER_ID
    uid = _user.get("id")
    tasks = []
    for t in await db.get_tasks_by_status("pending_folder"):
        if t["kind"] not in ("link", "gdrive", "telegram"):
            continue
        if not is_owner_user and t.get("requested_by") != uid:
            continue
        if not _recent_pending(t):
            continue
        tasks.append({"id": t["id"], "filename": t["filename"], "kind": t["kind"],
                      "size": filemanager.human_size(t["total_size"]) if t.get("total_size") else None})
    torrents = []
    for tid, st in list(h_rd.rd_torrent_states.items()):
        if "dest_folder" in st or not st.get("files"):
            continue
        if not is_owner_user and st.get("requested_by") != uid:
            continue
        torrents.append({"torrent_id": tid, "name": st.get("torrent_name", "torrent"), "provider": st.get("provider", "realdebrid")})
    sources = []
    for key, src in list(h_tb.pending_sources.items()):
        if not is_owner_user and src.get("requested_by") != uid:
            continue
        sources.append({"key": key, "name": src.get("name", "Torrent")})
    return {"tasks": tasks, "torrents": torrents, "sources": sources}


class DiscardPendingBody(BaseModel):
    ids: list[int] = []
    key: Optional[str] = None
    torrent_id: Optional[str] = None      # torrent ya añadido al proveedor que espera carpeta


@app.post("/api/pending/discard")
async def discard_pending(body: DiscardPendingBody, _user: dict = Depends(require_authorized)):
    for tid in body.ids:
        task = await db.get_task(tid)
        if task and task["status"] == "pending_folder":
            _ensure_task_owner(task, _user)
            await db.update_task(tid, status="cancelled")
    if body.key:
        src = h_tb.pending_sources.get(body.key)
        if src and (_user.get("id") == config.OWNER_ID or src.get("requested_by") == _user.get("id")):
            h_tb.pending_sources.pop(body.key, None)
    if body.torrent_id:
        # Antes no se podía quitar: se borra del proveedor (TorBox…) y se olvida, igual que «Cancelar» en el chat
        st = h_rd.rd_torrent_states.get(body.torrent_id)
        if st and "dest_folder" not in st:
            _ensure_torrent_owner(st, _user)
            h_rd.rd_torrent_states.pop(body.torrent_id, None)
            try:
                if torrent_clients.is_client(st.get("provider")):
                    import handlers_clients
                    await handlers_clients.cancel(st)
                elif st.get("provider") == "torbox":
                    await h_tb.cancel(st)
                else:
                    await real_debrid.delete_torrent(st["token"], body.torrent_id)
            except Exception as e:  # noqa: BLE001 — ya no está pendiente aunque el proveedor falle
                logging.getLogger(__name__).warning("No se pudo borrar el torrent %s del proveedor: %s", body.torrent_id, e)
    return {"ok": True}


@app.get("/api/pending/source/{key}")
async def pending_source(key: str, _user: dict = Depends(require_authorized)):
    src = h_tb.pending_sources.get(key)
    if not src:
        raise HTTPException(status_code=404, detail="Esta solicitud expiró. Vuelve a empezar.")
    if _user.get("id") != config.OWNER_ID and src.get("requested_by") != _user.get("id"):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta solicitud")
    providers = await h_settings.available_providers()
    return {"key": key, "name": src.get("name", "Torrent"),
            "providers": [{"id": p, "label": h_settings.PROVIDER_LABELS[p]} for p in providers]}


@app.get("/api/pending/torrent/{torrent_id}")
async def pending_torrent(torrent_id: str, _user: dict = Depends(require_authorized)):
    st = h_rd.rd_torrent_states.get(torrent_id)
    if not st or "dest_folder" in st:
        raise HTTPException(status_code=404, detail="Esta solicitud expiró. Vuelve a empezar.")
    _ensure_torrent_owner(st, _user)
    files = st.get("files", [])
    return {
        "provider": st.get("provider", "realdebrid"), "torrent_id": torrent_id,
        "torrent_name": st.get("torrent_name", "torrent"), "select_files": len(files) > 1,
        "files": [{"id": f["id"], "name": (f.get("path") or f.get("name") or "").split("/")[-1],
                   "size": filemanager.human_size(f.get("bytes", 0))} for f in files],
        "selected": list(st.get("selected", [])),
    }


class MaxParallelBody(BaseModel):
    value: int


@app.post("/api/settings/max_parallel_telegram")
async def set_max_parallel_telegram(body: MaxParallelBody, _user: dict = Depends(require_owner)):
    await h_dl.set_max_parallel("telegram", body.value)
    return {"ok": True}


@app.post("/api/settings/max_parallel_aria2")
async def set_max_parallel_aria2(body: MaxParallelBody, _user: dict = Depends(require_owner)):
    await h_dl.set_max_parallel("aria2", body.value)
    return {"ok": True}


@app.post("/api/settings/max_parallel_gdrive")
async def set_max_parallel_gdrive(body: MaxParallelBody, _user: dict = Depends(require_owner)):
    await h_dl.set_max_parallel("gdrive", body.value)
    return {"ok": True}


class ExtractDeleteBody(BaseModel):
    enabled: bool


@app.post("/api/settings/extract_delete_original")
async def set_extract_delete(body: ExtractDeleteBody, _user: dict = Depends(require_owner)):
    await db.set_setting("extract_delete_original", "1" if body.enabled else "0")
    return {"ok": True}


class WorkersBody(BaseModel):
    value: int


@app.post("/api/settings/aria2_workers")
async def set_aria2_workers(body: WorkersBody, _user: dict = Depends(require_owner)):
    value = max(1, min(16, body.value))
    await db.set_setting("aria2_workers", str(value))
    return {"ok": True}


def _src_or_404(key: str):
    if key not in torrent_search.SOURCES:
        raise HTTPException(status_code=404, detail="Buscador desconocido")


@app.get("/api/sources")
async def sources_list(_user: dict = Depends(require_owner)):
    return {"sources": await torrent_search.describe_sources()}


class ToggleBody(BaseModel):
    enabled: bool


class ProxyBody(BaseModel):
    enabled: bool | None = None
    url: str | None = None


@app.get("/api/sources/proxy")
async def sources_proxy_get(_user: dict = Depends(require_owner)):
    return {
        "enabled": (await db.get_setting("src_proxy_enabled", "0")) == "1",
        "url": await db.get_setting("src_proxy_url", torrent_search.DEFAULT_PROXY_URL),
        "default_url": torrent_search.DEFAULT_PROXY_URL,
    }


@app.post("/api/sources/proxy")
async def sources_proxy_set(body: ProxyBody, _user: dict = Depends(require_owner)):
    if body.url is not None:
        url = body.url.strip() or torrent_search.DEFAULT_PROXY_URL
        if "://" not in url or url.split("://")[0].lower() not in ("socks5", "socks5h", "http", "https"):
            raise HTTPException(status_code=400, detail="La dirección debe empezar por socks5://, socks5h://, http:// o https://")
        await db.set_setting("src_proxy_url", url)
    if body.enabled is not None:
        await db.set_setting("src_proxy_enabled", "1" if body.enabled else "0")
    return {"ok": True}


@app.post("/api/sources/proxy/test")
async def sources_proxy_test(_user: dict = Depends(require_owner)):
    return await torrent_search.test_proxy()


@app.post("/api/sources/{key}/toggle")
async def sources_toggle(key: str, body: ToggleBody, _user: dict = Depends(require_owner)):
    _src_or_404(key)
    await torrent_search.set_enabled(key, body.enabled)
    return {"ok": True}


@app.post("/api/sources/{key}/test")
async def sources_test(key: str, _user: dict = Depends(require_owner)):
    _src_or_404(key)
    return await torrent_search.test_source(key)


@app.post("/api/sources/test_all")
async def sources_test_all(_user: dict = Depends(require_owner)):
    keys = await torrent_search.enabled_sources()
    results = await asyncio.gather(*(torrent_search.test_source(k) for k in keys))
    return {"results": {k: r for k, r in zip(keys, results)}}


class MirrorBody(BaseModel):
    url: str
    force: bool = False


@app.post("/api/sources/{key}/mirrors")
async def sources_add_mirror(key: str, body: MirrorBody, _user: dict = Depends(require_owner)):
    _src_or_404(key)
    candidates = torrent_search.clean_candidates(key, body.url)
    if not candidates:
        raise HTTPException(status_code=400, detail="No hay ninguna URL válida")
    tests = await asyncio.gather(*(torrent_search.test_source(key, only_url=u) for u in candidates))
    urls = await torrent_search.get_admin_urls(key)
    results, saved_any = [], False
    for u, t in zip(candidates, tests):
        saved = t["ok"] or body.force
        if saved and u not in urls:
            urls.append(u)
        saved_any = saved_any or saved
        results.append({"url": u, "saved": saved, "test": t})
    await torrent_search.set_admin_urls(key, urls)
    return {"saved": saved_any, "results": results}


class MirrorDeleteBody(BaseModel):
    url: str | None = None


@app.post("/api/sources/{key}/mirrors/delete")
async def sources_delete_mirror(key: str, body: MirrorDeleteBody, _user: dict = Depends(require_owner)):
    _src_or_404(key)
    if body.url:
        urls = [u for u in await torrent_search.get_admin_urls(key) if u != body.url]
    else:
        urls = []
        await db.delete_setting(f"src_last_{key}")
    await torrent_search.set_admin_urls(key, urls)
    return {"ok": True}


class CustomSourceBody(BaseModel):
    name: str
    kind: str
    url: str
    apikey: str = ""
    parser: str = ""


@app.post("/api/sources/custom")
async def sources_add_custom(body: CustomSourceBody, _user: dict = Depends(require_owner)):
    kind = body.kind.strip().lower()
    if kind not in ("torznab", "clone"):
        raise HTTPException(status_code=400, detail="Invalid source type")
    name = body.name.strip()
    url = torrent_search.normalize_url(body.url, local_ok=True)
    if not name or not url:
        raise HTTPException(status_code=400, detail="Name and a valid URL are required")
    if kind == "torznab" and not body.apikey.strip():
        raise HTTPException(status_code=400, detail="Torznab sources need an API key")
    if kind == "clone" and body.parser not in torrent_search.BUILTIN_KEYS:
        raise HTTPException(status_code=400, detail="Choose which built-in source to copy")
    key = await torrent_search.add_custom(name, kind, url, body.apikey.strip(), body.parser)
    result = await torrent_search.test_source(key)
    return {"ok": True, "key": key, "test": result}


@app.post("/api/sources/restore")
async def sources_restore(_user: dict = Depends(require_owner)):
    await torrent_search.restore_defaults()
    return {"ok": True}


@app.post("/api/sources/{key}/delete")
async def sources_remove(key: str, _user: dict = Depends(require_owner)):
    _src_or_404(key)
    await torrent_search.remove_source(key)
    return {"ok": True}


@app.get("/api/i18n")
async def get_i18n():
    import i18n
    return {"lang": i18n.lang, "languages": i18n.LANGS, "catalog": i18n.catalog_json() if i18n.lang == "en" else {}}


class LanguageBody(BaseModel):
    lang: str


@app.post("/api/settings/language")
async def set_language(body: LanguageBody, _user: dict = Depends(require_owner)):
    import i18n
    if body.lang not in i18n.LANGS:
        raise HTTPException(status_code=400, detail="Unknown language")
    await config.set_runtime("LANGUAGE", body.lang)
    i18n.set_lang(body.lang)
    return {"ok": True}


class FolderBody(BaseModel):
    name: str
    path: str = ""
    media: str = ""


@app.get("/api/folders")
async def folders_get(_user: dict = Depends(require_owner)):
    out = []
    for f in config.folders_as_list():
        out.append({**f, "exists": os.path.isdir(f["path"]),
                    "writable": os.path.isdir(f["path"]) and os.access(f["path"], os.W_OK)})
    return {"folders": out}


@app.post("/api/folders")
async def folders_add(body: FolderBody, _user: dict = Depends(require_owner)):
    try:
        await folders_svc.add(body.name, os.path.normpath(body.path.strip()), body.media)
    except folders_svc.FolderError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


class FolderRenameBody(BaseModel):
    name: str
    new_name: str = ""
    path: str = ""


@app.post("/api/folders/rename")
async def folders_rename(body: FolderRenameBody, _user: dict = Depends(require_owner)):
    try:
        await folders_svc.rename(body.name, body.new_name)
    except folders_svc.FolderError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@app.post("/api/folders/path")
async def folders_path(body: FolderRenameBody, _user: dict = Depends(require_owner)):
    try:
        await folders_svc.set_path(body.name, os.path.normpath(body.path.strip()))
    except folders_svc.FolderError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@app.get("/api/folders/browse")
async def folders_browse(path: str = "/media", _user: dict = Depends(require_owner)):
    try:
        real = folders_svc.inside_base(path)
        return {"path": real, "parent": real if real == folders_svc.BASE else os.path.dirname(real),
                "dirs": folders_svc.list_subdirs(real)}
    except folders_svc.FolderError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/folders/mkdir")
async def folders_mkdir(body: FolderRenameBody, _user: dict = Depends(require_owner)):
    try:
        return {"ok": True, "path": folders_svc.make_subdir(body.path, body.new_name)}
    except folders_svc.FolderError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/folders/media")
async def folders_media(body: FolderBody, _user: dict = Depends(require_owner)):
    if body.name not in config.FOLDERS:
        raise HTTPException(status_code=404, detail="Unknown folder")
    config.FOLDER_MEDIA[body.name] = body.media if body.media in ("movie", "tv") else ""
    await config.save_folders()
    return {"ok": True}


@app.post("/api/folders/delete")
async def folders_delete(body: FolderBody, _user: dict = Depends(require_owner)):
    if body.name not in config.FOLDERS:
        raise HTTPException(status_code=404, detail="Unknown folder")
    if len(config.FOLDERS) <= 1:
        raise HTTPException(status_code=400, detail="At least one folder is required")
    config.FOLDERS.pop(body.name, None)
    config.FOLDER_MEDIA.pop(body.name, None)
    await config.save_folders()
    return {"ok": True}


@app.post("/api/folders/reset")
async def folders_reset(_user: dict = Depends(require_owner)):
    config.set_folders(config.DEFAULT_FOLDERS)
    await config.save_folders()
    return {"ok": True}


class QbitBody(BaseModel):
    url: str | None = None
    user: str | None = None
    password: str | None = None
    keep_seeding: bool | None = None


def _client(key: str):
    if not torrent_clients.is_client(key):
        raise HTTPException(status_code=404, detail="Unknown client")
    return torrent_clients.module(key)


@app.get("/api/clients/{key}")
async def client_get(key: str, _user: dict = Depends(require_owner)):
    mod = _client(key)
    cfg = await mod.get_config()
    return {"enabled": await mod.is_enabled(), "url": cfg["url"], "user": cfg["user"],
            "has_password": bool(cfg["password"]), "keep_seeding": cfg["keep_seeding"],
            "needs_user": mod.NEEDS_USER, "label": torrent_clients.label(key)}


@app.post("/api/clients/{key}")
async def client_set(key: str, body: QbitBody, _user: dict = Depends(require_owner)):
    mod = _client(key)
    prefix = mod.PREFIX
    if body.url is not None:
        url = torrent_search.normalize_url(body.url, local_ok=True) if body.url.strip() else mod.DEFAULT_URL
        if not url:
            raise HTTPException(status_code=400, detail="Invalid URL")
        await db.set_setting(f"{prefix}_url", url.rstrip("/"))
    if body.user is not None:
        await db.set_setting(f"{prefix}_user", body.user.strip())
    if body.password is not None and body.password != "":
        await db.set_setting(f"{prefix}_pass", body.password)
    if body.keep_seeding is not None:
        await db.set_setting(f"{prefix}_keep_seeding", "1" if body.keep_seeding else "0")
    return {"ok": True}


@app.post("/api/clients/{key}/test")
async def client_test(key: str, _user: dict = Depends(require_owner)):
    mod = _client(key)
    try:
        version = await mod.test_connection()
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "version": version}



class BackupBody(BaseModel):
    groups: list[str]
    password: str | None = None


@app.get("/api/backup/groups")
async def backup_groups(_user: dict = Depends(require_owner)):
    meta = backup_svc.info()
    return {"groups": [{"key": g, "icon": meta[g][0], "name": meta[g][1], "desc": meta[g][2]} for g in backup_svc.GROUP_ORDER],
            "presets": backup_svc.PRESETS, "auto": await db.get_setting("bk_auto", "off")}


@app.post("/api/backup/create")
async def backup_create(body: BackupBody, _user: dict = Depends(require_owner)):
    import base64
    groups = [g for g in body.groups if g in backup_svc.GROUP_ORDER]
    if not groups:
        raise HTTPException(status_code=400, detail="Select at least one group")
    new_key = None
    if not body.password and not await db.get_setting("bk_key"):
        new_key = await backup_svc.get_key()
    blob, name = await backup_svc.build(groups, body.password or None)
    return {"name": name, "data": base64.b64encode(blob).decode(), "new_key": new_key}


@app.get("/api/backup/key")
async def backup_key(_user: dict = Depends(require_owner)):
    return {"key": await backup_svc.get_key()}


class BackupAutoBody(BaseModel):
    mode: str
    groups: list[str] = []


@app.post("/api/backup/auto")
async def backup_auto(body: BackupAutoBody, _user: dict = Depends(require_owner)):
    if body.mode not in ("off", "daily", "weekly"):
        raise HTTPException(status_code=400, detail="Invalid mode")
    await db.set_setting("bk_auto", body.mode)
    if body.groups:
        await db.set_setting("bk_auto_groups", ",".join(g for g in body.groups if g in backup_svc.GROUP_ORDER))
    return {"ok": True}


_restore_sessions: dict[str, tuple] = {}


class BackupInspectBody(BaseModel):
    data: str
    password: str | None = None


@app.post("/api/backup/inspect")
async def backup_inspect(body: BackupInspectBody, _user: dict = Depends(require_owner)):
    import base64
    try:
        blob = base64.b64decode(body.data)
        password = body.password or (await backup_svc.get_key(create=False))
        manifest, data = backup_svc.read(blob, password)
    except backup_svc.BackupError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid file")
    token = uuid.uuid4().hex
    _restore_sessions.clear()
    _restore_sessions[token] = (manifest, data)
    meta = backup_svc.info()
    return {"token": token, "created": manifest.get("created"), "version": manifest.get("app_version"),
            "encrypted": backup_svc.is_encrypted(blob),
            "groups": [{"key": g, "icon": meta[g][0], "name": meta[g][1], "count": manifest["counts"].get(g, 0)}
                       for g in backup_svc.GROUP_ORDER if g in manifest["groups"]]}


class BackupRestoreBody(BaseModel):
    token: str
    groups: list[str]


@app.post("/api/backup/restore")
async def backup_restore(body: BackupRestoreBody, _user: dict = Depends(require_owner)):
    session = _restore_sessions.pop(body.token, None)
    if not session:
        raise HTTPException(status_code=400, detail="Session expired")
    manifest, data = session
    safety, name = await backup_svc.build(list(backup_svc.GROUP_ORDER))
    folder = os.path.join(config.CONFIG_DIR, "backups")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, name.replace("nas-bot-backup", "before-restore")), "wb") as f:
        f.write(safety)
    done = await backup_svc.restore(manifest, data, body.groups)
    return {"ok": True, "restored": done}


@app.get("/api/notifications")
async def notif_get(_user: dict = Depends(require_owner)):
    return await notifier.get()


class NotifBody(BaseModel):
    enabled: bool | None = None
    done: bool | None = None
    failed: bool | None = None
    disk: bool | None = None
    quiet_on: bool | None = None
    min_mb: int | None = None
    to: str | None = None
    quiet_from: int | None = None
    quiet_to: int | None = None


@app.post("/api/notifications")
async def notif_set(body: NotifBody, _user: dict = Depends(require_owner)):
    for key, value in body.model_dump().items():
        if value is None:
            continue
        if key == "to" and value not in notifier.TARGETS:
            raise HTTPException(status_code=400, detail="Invalid recipient")
        if key in ("quiet_from", "quiet_to"):
            value = int(value) % 24
        if key == "min_mb":
            value = max(0, int(value))
        await notifier.set_value(key, value)
    return {"ok": True}


@app.get("/api/disk")
async def disk_get(_user: dict = Depends(require_owner)):
    cfg = await disk_svc.settings()
    vols = [{"folders": v["folders"], "total": v["total"], "used": v["used"], "free": v["free"]} for v in disk_svc.volumes()]
    return {"settings": cfg, "volumes": vols}


class DiskBody(BaseModel):
    guard: str | None = None
    reserve_gb: float | None = None
    alert_on: bool | None = None
    alert_gb: float | None = None


@app.post("/api/disk")
async def disk_set(body: DiskBody, _user: dict = Depends(require_owner)):
    if body.guard is not None:
        if body.guard not in disk_svc.MODES:
            raise HTTPException(status_code=400, detail="Invalid mode")
        await db.set_setting("disk_guard", body.guard)
    if body.reserve_gb is not None:
        await db.set_setting("disk_reserve_gb", f"{max(0.0, body.reserve_gb):g}")
    if body.alert_on is not None:
        await db.set_setting("disk_alert_on", "1" if body.alert_on else "0")
    if body.alert_gb is not None:
        await db.set_setting("disk_alert_gb", f"{max(0.0, body.alert_gb):g}")
    return {"ok": True}


@app.get("/api/rules")
async def rules_get(_user: dict = Depends(require_owner)):
    return {"mode": await rules_svc.get_mode(), "options": await rules_svc.get_options(), "rules": await rules_svc.load(),
            "folders": list(config.FOLDERS), "types": list(rules_svc.EXT_GROUPS), "sources": list(rules_svc.SOURCES)}


class RulesBody(BaseModel):
    mode: str | None = None
    conflict: str | None = None
    fallback: str | None = None
    rules: list[dict] | None = None


@app.post("/api/rules")
async def rules_set(body: RulesBody, _user: dict = Depends(require_owner)):
    if body.mode is not None:
        await rules_svc.set_mode(body.mode)
    if body.conflict in ("first", "ask"):
        await rules_svc.set_option("conflict", body.conflict)
    if body.fallback is not None:
        await rules_svc.set_option("fallback", body.fallback if body.fallback in config.FOLDERS else "")
    if body.rules is not None:
        await rules_svc.save([rules_svc.normalize(r) for r in body.rules])
    return {"ok": True}


class RuleTestBody(BaseModel):
    name: str
    size_mb: float = 0
    source: str = "any"


@app.post("/api/rules/test")
async def rules_test(body: RuleTestBody, _user: dict = Depends(require_owner)):
    found = await rules_svc.find(body.name, int(body.size_mb * 1048576), body.source, None)
    return {"matches": [{"name": r["name"], "destination": "/".join(x for x in rules_svc.destination(r, body.name, None) if x)} for r in found]}

@app.get("/api/providers")
async def get_providers(_user: dict = Depends(require_owner)):
    out = {}

    rd_token = await h_settings.get_rd_token()
    rd = {"configured": bool(rd_token), "enabled": await h_settings.rd_is_enabled(), "account": None}
    if rd_token:
        try:
            info = await real_debrid.get_user_info(rd_token)
            rd["account"] = {
                "username": info.get("username"), "type": info.get("type"),
                "premium_days_left": (info.get("premium") or 0) // 86400,
                "expiration": (info.get("expiration") or "")[:10], "points": info.get("points"),
            }
        except Exception:
            pass
    out["realdebrid"] = rd

    tb_token = await h_settings.get_tb_token()
    tb = {"configured": bool(tb_token), "enabled": await h_settings.tb_is_enabled(), "account": None}
    if tb_token:
        try:
            info = await torbox.get_user_info(tb_token)
            tb["account"] = {
                "email": info.get("email"), "plan": torbox.plan_name(info.get("plan")),
                "expiration": str(info.get("premium_expires_at") or "")[:10],
            }
        except Exception:
            pass
    out["torbox"] = tb

    for k, c in torrent_clients.CLIENTS.items():
        cfg = await c["module"].get_config()
        out[k] = {"configured": True, "enabled": await c["module"].is_enabled(), "client": True,
                  "label": c["label"], "icon": c["icon"], "url": cfg["url"], "keep_seeding": cfg["keep_seeding"]}
    return out


@app.get("/api/tmdb")
async def get_tmdb_settings(_user: dict = Depends(require_owner)):
    key = await tmdb_helper.get_api_key()
    return {"configured": bool(key), "enabled": bool(key) and await db.get_setting("tmdb_enabled", "0") == "1"}


class TmdbKeyBody(BaseModel):
    token: str


@app.post("/api/tmdb/token")
async def set_tmdb_token(body: TmdbKeyBody, _user: dict = Depends(require_owner)):
    key = body.token.strip()
    if not await tmdb_helper.check_key(key):
        raise HTTPException(status_code=400, detail="Esa clave no parece válida")
    await db.set_setting("tmdb_token", key)
    await db.set_setting("tmdb_enabled", "1")
    return {"ok": True}


@app.post("/api/tmdb/token/delete")
async def delete_tmdb_token(_user: dict = Depends(require_owner)):
    await db.delete_setting("tmdb_token")
    await db.set_setting("tmdb_enabled", "0")
    return {"ok": True}


class TmdbToggleBody(BaseModel):
    enabled: bool


@app.post("/api/tmdb/toggle")
async def toggle_tmdb(body: TmdbToggleBody, _user: dict = Depends(require_owner)):
    if body.enabled and not await tmdb_helper.get_api_key():
        raise HTTPException(status_code=400, detail="Primero configura el API Token")
    await db.set_setting("tmdb_enabled", "1" if body.enabled else "0")
    return {"ok": True}


class ProviderToggleBody(BaseModel):
    enabled: bool


@app.post("/api/providers/{provider}/toggle")
async def toggle_provider(provider: str, body: ProviderToggleBody, _user: dict = Depends(require_owner)):
    key = {"realdebrid": ("rd_token", "rd_enabled"), "torbox": ("tb_token", "tb_enabled"),
           **{k: (None, f"{c['prefix']}_enabled") for k, c in torrent_clients.CLIENTS.items()}}.get(provider)
    if not key:
        raise HTTPException(status_code=404, detail="Unknown provider")
    if body.enabled and key[0] and not await db.get_setting(key[0]):
        raise HTTPException(status_code=400, detail="Primero configura el API Token")
    await db.set_setting(key[1], "1" if body.enabled else "0")
    return {"ok": True}


class RdTokenBody(BaseModel):
    token: str


@app.post("/api/tb/token")
async def tb_set_token(body: RdTokenBody, _user: dict = Depends(require_owner)):
    token = body.token.strip()
    if not await torbox.check_token(token):
        raise HTTPException(status_code=400, detail="Ese token no parece válido")
    await db.set_setting("tb_token", token)
    await db.set_setting("tb_enabled", "1")
    return {"ok": True}


@app.post("/api/tb/token/delete")
async def tb_delete_token(_user: dict = Depends(require_owner)):
    await db.delete_setting("tb_token")
    await db.set_setting("tb_enabled", "0")
    return {"ok": True}


@app.get("/api/rd/account")
async def rd_account(_user: dict = Depends(require_owner)):
    token = await h_settings.get_rd_token()
    if not token:
        raise HTTPException(status_code=400, detail="No hay token de Real-Debrid configurado")
    try:
        info = await real_debrid.get_user_info(token)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No se pudo consultar Real-Debrid: {e}")

    return {
        "username": info.get("username"),
        "type": info.get("type"),
        "premium_days_left": (info.get("premium") or 0) // 86400,
        "expiration": (info.get("expiration") or "")[:10],
        "points": info.get("points"),
    }


@app.post("/api/rd/token")
async def rd_set_token(body: RdTokenBody, _user: dict = Depends(require_owner)):
    token = body.token.strip()
    try:
        valid = await real_debrid.check_token(token)
    except Exception:
        valid = False
    if not valid:
        raise HTTPException(status_code=400, detail="Ese token no parece válido")
    await db.set_setting("rd_token", token)
    await db.set_setting("rd_enabled", "1")
    return {"ok": True}


@app.post("/api/rd/token/delete")
async def rd_delete_token(_user: dict = Depends(require_owner)):
    await db.delete_setting("rd_token")
    await db.set_setting("rd_enabled", "0")
    return {"ok": True}


@app.post("/api/rd/purge")
async def rd_purge(_user: dict = Depends(require_owner)):
    token = await h_settings.get_rd_token()
    if not token:
        raise HTTPException(status_code=400, detail="No hay token de Real-Debrid configurado")
    try:
        result = await real_debrid.purge_account(token)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al vaciar la cuenta: {e}")
    return {"ok": True, **result}


def _format_duration(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


def _task_avg_speed(task: dict) -> str | None:
    started, finished, size = task.get("started_at"), task.get("finished_at"), task.get("total_size")
    if not started or not finished or not size:
        return None
    try:
        secs = (datetime.fromisoformat(finished) - datetime.fromisoformat(started)).total_seconds()
        if secs < 1:
            return None
        return filemanager.human_size(size / secs) + "/s"
    except Exception:
        return None


def _task_duration(task: dict) -> str | None:
    started, finished = task.get("started_at"), task.get("finished_at")
    if not started or not finished:
        return None
    try:
        delta = (datetime.fromisoformat(finished) - datetime.fromisoformat(started)).total_seconds()
        if delta < 0:
            return None
        return _format_duration(delta)
    except Exception:
        return None


@app.get("/api/history")
async def get_history(user_id: int | None = None, _user: dict = Depends(require_authorized)):
    is_owner_user = _user.get("id") == config.OWNER_ID
    target_user_id = user_id if is_owner_user else _user.get("id")
    tasks = await db.get_history(limit=100, requested_by=target_user_id)

    user_names = {}
    users_list = []
    if is_owner_user:
        user_names[config.OWNER_ID] = "Tú"
        users_list.append({"id": config.OWNER_ID, "name": "Tú (Owner)"})
        users = await db.list_authorized_users()
        for u in users:
            uid = u.get("user_id")
            if uid == config.OWNER_ID:
                continue
            name = u.get("first_name") or u.get("username") or f"Usuario {uid}"
            user_names[uid] = name
            users_list.append({"id": uid, "name": name})

    return {
        "history": [
            {
                "id": t["id"],
                "filename": t["filename"],
                "status": t["status"],
                "dest_folder": t["dest_folder"],
                "kind": t["kind"],
                "client": task_client(t),
                "client_label": client_label(t, with_emoji=False),
                "size": filemanager.human_size(t["total_size"]) if t.get("total_size") else None,
                "duration": _task_duration(t),
                "avg_speed": _task_avg_speed(t),
                "started_at": t.get("started_at"),
                "finished_at": t.get("finished_at"),
                "error": t.get("error"),
                "url": t.get("url"),
                "user_name": "Tú" if (is_owner_user and (t.get("requested_by") == config.OWNER_ID or t.get("requested_by") is None)) else (user_names.get(t.get("requested_by")) if is_owner_user and t.get("requested_by") else None),
                "created_at": t["created_at"],
            }
            for t in tasks
        ],
        "users": users_list if is_owner_user else []
    }


@app.post("/api/history/clear")
async def clear_history(user_id: int | None = None, _user: dict = Depends(require_authorized)):
    is_owner_user = _user.get("id") == config.OWNER_ID
    target_user_id = user_id if is_owner_user else _user.get("id")
    await db.clear_history(requested_by=target_user_id)
    return {"ok": True}


class CreateLinksBody(BaseModel):
    urls: list[str]


@app.post("/api/tasks/create_links")
async def create_links(body: CreateLinksBody, _user: dict = Depends(require_authorized)):
    urls = [u.strip() for u in body.urls if u.strip()]
    if not urls:
        raise HTTPException(status_code=400, detail="No se recibió ningún enlace")

    if any(ytdlp_downloader.is_ytdlp_url(u) for u in urls):
        raise HTTPException(status_code=400, detail="Los enlaces de yt-dlp se descargan solo con yt-dlp")

    tasks = []
    probes = await asyncio.gather(*(h_dl.probe_link(u) for u in urls))
    for url, (probed_name, probed_size) in zip(urls, probes):
        filename = probed_name or url.split("/")[-1].split("?")[0] or "archivo"
        task_id = await db.create_task(
            kind="link", url=url, filename=filename, total_size=probed_size, requested_by=_user.get("id"),
        )
        tasks.append({"id": task_id, "filename": filename,
                      "size": filemanager.human_size(probed_size) if probed_size else None})

    return {"tasks": tasks, "rd_available": await h_settings.rd_is_enabled(), "tb_available": await h_settings.tb_is_enabled()}


@app.post("/api/tasks/create_telegram")
async def create_telegram_tasks(body: CreateLinksBody, _user: dict = Depends(require_authorized)):
    """Enlaces de mensajes de Telegram (t.me/…), descargados con la cuenta conectada (userbot)."""
    import tg_links
    urls = [u.strip() for u in body.urls if u.strip() and tg_links.is_tg_link(u)]
    if not urls:
        raise HTTPException(status_code=400, detail="No hay ningún enlace de mensaje de Telegram")
    manager = _state["application"].bot_data.get("userbot_manager") if _state["application"] else None
    tasks, errors = [], []
    for url in urls:
        try:
            for f in await tg_links.resolve(manager, url):
                tid = await db.create_task(kind="telegram", source_chat_id=f["chat_id"], source_message_id=f["message_id"],
                                           filename=f["filename"], total_size=f["size"] or None, requested_by=_user.get("id"))
                tasks.append({"id": tid, "filename": f["filename"], "size": filemanager.human_size(f["size"]) if f["size"] else None})
        except Exception as e:
            errors.append({"url": url, "error": str(e)})
    if not tasks and errors:
        raise HTTPException(status_code=400, detail=errors[0]["error"])
    return {"tasks": tasks, "errors": errors}


@app.post("/api/tasks/create_gdrive")
async def create_gdrive_tasks(body: CreateLinksBody, _user: dict = Depends(require_authorized)):
    urls = [u.strip() for u in body.urls if u.strip() and google_drive.is_drive_url(u)]
    if not urls:
        raise HTTPException(status_code=400, detail="No se recibió ningún enlace de Google Drive")

    if not google_drive.is_configured() or not await google_drive.is_connected():
        raise HTTPException(status_code=400, detail="Google Drive no está conectado (Ajustes → Google Drive)")

    all_items = []
    errors = []
    for u in urls:
        try:
            all_items.extend(await google_drive.list_drive_files(u))
        except google_drive.GoogleDriveError as e:
            errors.append(str(e))

    tasks = []
    for item in all_items:
        task_id = await db.create_task(
            kind="gdrive", filename=item["name"], total_size=item["size"],
            requested_by=_user.get("id"), drive_file_id=item["file_id"],
        )
        tasks.append({"id": task_id, "filename": item["name"]})

    if not tasks and errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))

    return {"tasks": tasks, "errors": errors}


class SetMethodBody(BaseModel):
    ids: list[int]
    method: str


@app.post("/api/tasks/set_method")
async def set_method(body: SetMethodBody, _user: dict = Depends(require_authorized)):
    if body.method not in ("aria2", "rd", "tb"):
        raise HTTPException(status_code=400, detail="Método no válido")
    tasks = [await db.get_task(i) for i in body.ids]
    for t in tasks:
        if t:
            _ensure_task_owner(t, _user)
    await h_dl.apply_method(body.ids, body.method)
    tasks = [await db.get_task(i) for i in body.ids]
    return {"tasks": [{"id": t["id"], "filename": t["filename"]} for t in tasks if t]}


class SetDestinationBody(BaseModel):
    ids: list[int]
    folder: str
    path: str = ""
    extract: bool = False
    schedule: str = "now"
    schedule_at: Optional[str] = None
    new_name: Optional[str] = None


@app.post("/api/tasks/set_destination")
async def set_destination(body: SetDestinationBody, _user: dict = Depends(require_authorized)):
    context = _get_context()
    for tid in body.ids:
        task = await db.get_task(tid)
        if task:
            _ensure_task_owner(task, _user)

    if body.new_name and len(body.ids) == 1:
        task = await db.get_task(body.ids[0])
        if task and task.get("kind") in ("link", "gdrive", "rd_link", "tb_link", "telegram"):
            await db.update_task(task["id"], filename=filemanager.apply_new_name(task["filename"], body.new_name), name_locked=1)

    if body.schedule and body.schedule != "now":
        now = datetime.now(h_dl.LOCAL_TZ)
        sched_dt = None
        if body.schedule == "at" and body.schedule_at:
            try:
                sched_dt = datetime.fromisoformat(body.schedule_at)
            except ValueError:
                raise HTTPException(status_code=400, detail="Fecha no válida")
            if sched_dt.tzinfo is None:
                sched_dt = sched_dt.replace(tzinfo=h_dl.LOCAL_TZ)
            if sched_dt <= now:
                raise HTTPException(status_code=400, detail="La hora ya ha pasado")
        elif body.schedule == "1h":
            sched_dt = now + timedelta(hours=1)
        elif body.schedule == "2h":
            sched_dt = now + timedelta(hours=2)
        elif body.schedule == "4h":
            sched_dt = now + timedelta(hours=4)
        elif body.schedule == "night":
            sched_dt = now.replace(hour=2, minute=0, second=0, microsecond=0)
            if sched_dt <= now:
                sched_dt += timedelta(days=1)

        if sched_dt:
            rel = await tmdb_helper.adjust_relpath(body.folder, body.path, await h_dl._hint_from_tasks(body.ids))
            try:
                _base, target_dir = filemanager.resolve_path(body.folder, rel)
            except filemanager.PathError as e:
                raise HTTPException(status_code=400, detail=str(e))
            target_dir.mkdir(parents=True, exist_ok=True)
            dest_dir = str(target_dir)
            dest_label = f"{body.folder}/{rel}" if rel else body.folder
            sched_iso = sched_dt.isoformat()

            for tid in body.ids:
                fields = {
                    "dest_folder": dest_label,
                    "dest_path": dest_dir,
                    "status": "scheduled",
                    "scheduled_for": sched_iso,
                }
                if body.extract:
                    fields["extract_after"] = 1
                await db.update_task(tid, **fields)

            return {"ok": True, "dest_folder": dest_label, "scheduled_for": sched_iso}

    try:
        _dest_dir, dest_label = await h_dl.set_destination(
            context, body.ids, body.folder, body.path,
            extract=body.extract
        )
    except filemanager.PathError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "dest_folder": dest_label}


class YtdlInfoBody(BaseModel):
    url: str


class YtdlDownloadBody(BaseModel):
    url: str
    format_spec: str
    folder: str = ""
    path: str = ""
    is_audio: bool = False
    title: str = ""
    schedule: str = "now"


_ytdl_active_tasks: dict[str, dict] = {}


@app.post("/api/ytdl/info")
async def ytdl_info(body: YtdlInfoBody, _user: dict = Depends(require_authorized)):
    url = body.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL no válida")
    try:
        info = await asyncio.to_thread(ytdlp_downloader.extract_video_info, url)
        return {
            "ok": True,
            "title": info.get("title", "Vídeo"),
            "duration_str": info.get("duration_str", ""),
            "thumbnail": info.get("thumbnail"),
            "options": info.get("options", []),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al analizar vídeo: {e}")


@app.post("/api/ytdl/download")
async def ytdl_download(body: YtdlDownloadBody, _user: dict = Depends(require_authorized)):
    url = body.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL no válida")

    folder_key = body.folder if body.folder in config.FOLDERS else config.default_download_folder()
    try:
        _base, target_dir = filemanager.resolve_path(folder_key, body.path)
    except filemanager.PathError as e:
        raise HTTPException(status_code=400, detail=str(e))
    target_dir.mkdir(parents=True, exist_ok=True)
    dest_dir = str(target_dir)
    dest_label = f"{folder_key}/{body.path}" if body.path else folder_key
    task_id = uuid.uuid4().hex[:8]

    if body.schedule and body.schedule != "now":
        now = datetime.now(h_dl.LOCAL_TZ)
        sched_dt = None
        if body.schedule == "1h":
            sched_dt = now + timedelta(hours=1)
        elif body.schedule == "2h":
            sched_dt = now + timedelta(hours=2)
        elif body.schedule == "4h":
            sched_dt = now + timedelta(hours=4)
        elif body.schedule == "night":
            sched_dt = now.replace(hour=2, minute=0, second=0, microsecond=0)
            if sched_dt <= now:
                sched_dt += timedelta(days=1)

        if sched_dt:
            sched_iso = sched_dt.isoformat()
            _ytdl_active_tasks[task_id] = {
                "id": task_id,
                "title": body.title or "Vídeo",
                "url": url,
                "folder": dest_label,
                "dest_path": dest_dir,
                "status": "scheduled",
                "pct": 0.0,
                "speed_mb": 0.0,
                "downloaded_mb": 0.0,
                "total_mb": 0.0,
                "filename": "",
                "error": None,
                "created_at": datetime.now().isoformat(),
                "requested_by": _user.get("id"),
                "is_audio": body.is_audio,
                "scheduled_for": sched_iso,
                "format_spec": body.format_spec,
            }
            try:
                await db.create_task(
                    kind="ytdl",
                    url=url,
                    filename=body.title or "Vídeo",
                    dest_folder=dest_label,
                    dest_path=dest_dir,
                    status="scheduled",
                    scheduled_for=sched_iso,
                    requested_by=_user.get("id"),
                )
            except Exception:
                pass
            return {"ok": True, "task_id": task_id, "scheduled_for": sched_iso}

    _ytdl_active_tasks[task_id] = {
        "id": task_id,
        "title": body.title or "Vídeo",
        "url": url,
        "folder": dest_label,
        "dest_path": dest_dir,
        "status": "downloading",
        "pct": 0.0,
        "speed_mb": 0.0,
        "downloaded_mb": 0.0,
        "total_mb": 0.0,
        "filename": "",
        "error": None,
        "created_at": datetime.now().isoformat(),
        "requested_by": _user.get("id"),
        "is_audio": body.is_audio,
        "format_spec": body.format_spec,
    }

    loop = asyncio.get_running_loop()

    def progress_cb(downloaded, total, speed):
        pct = (downloaded / total * 100) if total else 0.0
        mb_d = downloaded / (1024 * 1024)
        mb_t = total / (1024 * 1024) if total else 0.0
        sp_mb = speed / (1024 * 1024) if speed else 0.0

        def _update():
            if task_id in _ytdl_active_tasks:
                _ytdl_active_tasks[task_id].update({
                    "pct": round(pct, 1),
                    "downloaded_mb": round(mb_d, 1),
                    "total_mb": round(mb_t, 1),
                    "speed_mb": round(sp_mb, 2),
                })

        loop.call_soon_threadsafe(_update)

    async def _run_download():
        try:
            file_path = await ytdlp_downloader.download_video(
                url,
                body.format_spec,
                dest_dir,
                is_audio=body.is_audio,
                progress_callback=progress_cb,
            )
            saved_name = os.path.basename(file_path)
            total_size = 0
            try:
                total_size = os.path.getsize(file_path)
            except Exception:
                pass
            if task_id in _ytdl_active_tasks:
                _ytdl_active_tasks[task_id].update({
                    "status": "completed",
                    "pct": 100.0,
                    "filename": saved_name,
                    "total_mb": round(total_size / (1024 * 1024), 1) if total_size else _ytdl_active_tasks[task_id]["total_mb"],
                })
            try:
                await db.create_task(
                    kind="ytdl",
                    url=url,
                    filename=saved_name,
                    dest_folder=dest_label,
                    dest_path=dest_dir,
                    status="done",
                    total_size=total_size,
                    requested_by=_user.get("id"),
                    finished_at=datetime.now().isoformat(),
                )
            except Exception:
                pass
        except Exception as e:
            if task_id in _ytdl_active_tasks:
                _ytdl_active_tasks[task_id].update({
                    "status": "error",
                    "error": str(e),
                })
            try:
                await db.create_task(
                    kind="ytdl",
                    url=url,
                    filename=body.title or "Vídeo",
                    dest_folder=dest_label,
                    dest_path=dest_dir,
                    status="error",
                    error=str(e),
                    requested_by=_user.get("id"),
                    finished_at=datetime.now().isoformat(),
                )
            except Exception:
                pass

    asyncio.create_task(_run_download())
    return {"ok": True, "task_id": task_id}


@app.get("/api/ytdl/tasks")
async def ytdl_tasks(_user: dict = Depends(require_authorized)):
    is_owner = _user.get("id") == config.OWNER_ID
    tasks = [
        t for t in _ytdl_active_tasks.values()
        if is_owner or t.get("requested_by") == _user.get("id")
    ]
    tasks.reverse()
    return {"tasks": tasks}


@app.delete("/api/ytdl/tasks/{task_id}")
async def ytdl_delete_task(task_id: str, _user: dict = Depends(require_authorized)):
    task = _ytdl_active_tasks.get(task_id)
    if task:
        if _user.get("id") != config.OWNER_ID and task.get("requested_by") != _user.get("id"):
            raise HTTPException(status_code=403, detail="No tienes acceso a esta tarea")
        _ytdl_active_tasks.pop(task_id, None)
    return {"ok": True}


@app.get("/api/services/status")
async def services_status(_user: dict = Depends(require_authorized)):
    return {
        "ytdlp": {
            "available": True,
            "name": "yt-dlp",
        },
        "folders": list(config.FOLDERS.keys()),
    }


def _ensure_torrent_owner(state: dict, user: dict):
    if user.get("id") != config.OWNER_ID and state.get("requested_by") != user.get("id"):
        raise HTTPException(status_code=403, detail="No tienes acceso a este torrent")


class MagnetSelectBody(BaseModel):
    torrent_id: str
    selected: list[int]


@app.post("/api/rd/magnet/select")
async def rd_magnet_select(body: MagnetSelectBody, _user: dict = Depends(require_authorized)):
    state = h_rd.rd_torrent_states.get(body.torrent_id)
    if not state:
        raise HTTPException(status_code=404, detail="Sesión de torrent expirada")
    _ensure_torrent_owner(state, _user)
    if not body.selected:
        raise HTTPException(status_code=400, detail="Selecciona al menos un archivo")
    state["selected"] = set(body.selected)
    return {"ok": True}


class MagnetConfirmBody(BaseModel):
    torrent_id: str
    folder: str
    path: str = ""
    extract: bool = False
    schedule: str = "now"
    schedule_at: Optional[str] = None


@app.post("/api/rd/magnet/confirm")
async def rd_magnet_confirm(body: MagnetConfirmBody, _user: dict = Depends(require_authorized)):
    context = _get_context()
    state = h_rd.rd_torrent_states.get(body.torrent_id)
    if not state:
        raise HTTPException(status_code=404, detail="Sesión de torrent expirada")
    _ensure_torrent_owner(state, _user)
    rel = await tmdb_helper.adjust_relpath(body.folder, body.path, state.get("torrent_name", ""))
    try:
        _base, target_dir = filemanager.resolve_path(body.folder, rel)
    except filemanager.PathError as e:
        raise HTTPException(status_code=400, detail=str(e))
    target_dir.mkdir(parents=True, exist_ok=True)
    dest_dir = str(target_dir)
    dest_label = f"{body.folder}/{rel}" if rel else body.folder

    try:
        await h_rd.start_processing(
            context, body.torrent_id, dest_dir, dest_label,
            extract_after=body.extract, requested_by=_user.get("id"),
            schedule=(f"at:{body.schedule_at}" if body.schedule == "at" and body.schedule_at else (body.schedule or "now")),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"ok": True}


@app.post("/api/tasks/{task_id}/pause")
async def pause_task(task_id: int, _user: dict = Depends(require_authorized)):
    context = _get_context()
    task = await db.get_task(task_id)
    if not task or task["kind"] != "link" or task["status"] != "downloading" or not task["gid"]:
        raise HTTPException(status_code=400, detail="No se puede pausar esta tarea")
    _ensure_task_owner(task, _user)
    downloader.pause(task["gid"])
    await db.update_task(task_id, status="paused")
    await h_dl._safe_edit(
        context, task, f"⏸️ *{task['filename']}* pausada manualmente.",
        markup=h_dl._paused_markup(task_id),
    )
    return {"ok": True}


@app.post("/api/tasks/{task_id}/resume")
async def resume_task(task_id: int, _user: dict = Depends(require_authorized)):
    context = _get_context()
    task = await db.get_task(task_id)
    if not task or task["status"] != "paused":
        raise HTTPException(status_code=400, detail="No se puede reanudar esta tarea")
    _ensure_task_owner(task, _user)
    ok, message = await h_dl.resume_task_by_id(context, task_id)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"ok": True}


@app.post("/api/tasks/{task_id}/start_now")
async def start_now_task(task_id: int, _user: dict = Depends(require_authorized)):
    context = _get_context()
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    _ensure_task_owner(task, _user)
    if task["status"] == "scheduled":
        await db.update_task(task_id, status="queued", scheduled_for=None)
        await h_dl.try_start_next(context)
        return {"ok": True}
    elif task["status"] == "paused":
        await h_dl._resume_download(context, task)
        return {"ok": True}
    elif task["status"] == "queued":
        await h_dl.try_start_next(context)
        return {"ok": True}
    else:
        raise HTTPException(status_code=400, detail=f"No se puede iniciar inmediatamente una tarea en estado '{task['status']}'")


@app.post("/api/tasks/{task_id}/prioritize")
async def prioritize_task(task_id: int, _user: dict = Depends(require_authorized)):
    context = _get_context()
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    _ensure_task_owner(task, _user)
    ok, message = await h_dl.prioritize_task(context, task_id)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"ok": True}


@app.post("/api/tasks/{task_id}/move_up")
async def move_task_up(task_id: int, _user: dict = Depends(require_authorized)):
    context = _get_context()
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    _ensure_task_owner(task, _user)
    ok, message = await h_dl.move_task(context, task_id, "up")
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"ok": True}


@app.post("/api/tasks/{task_id}/move_down")
async def move_task_down(task_id: int, _user: dict = Depends(require_authorized)):
    context = _get_context()
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    _ensure_task_owner(task, _user)
    ok, message = await h_dl.move_task(context, task_id, "down")
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"ok": True}


@app.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: int, _user: dict = Depends(require_authorized)):
    context = _get_context()
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    _ensure_task_owner(task, _user)
    ok, message = await h_dl.cancel_task_by_id(context, task_id)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"ok": True}


@app.post("/api/tasks/{task_id}/force_remove")
async def force_remove_task(task_id: int, _user: dict = Depends(require_authorized)):
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    _ensure_task_owner(task, _user)
    if task["gid"]:
        try:
            downloader.remove_download(task["gid"])
        except Exception:
            pass
    active = context_active_telegram_task(task_id) or context_active_gdrive_task(task_id) or context_active_extract_task(task_id) or context_active_upload_task(task_id)
    if active:
        active.cancel()
    manager = _state["application"].bot_data.get("userbot_manager") if _state["application"] else None
    if manager:
        manager.cancel_upload(str(task_id))
    await db.delete_task(task_id)
    return {"ok": True}


def context_active_telegram_task(task_id: int):
    application = _state["application"]
    if application is None:
        return None
    return application.bot_data.get("active_telegram_tasks", {}).get(task_id)


def context_active_gdrive_task(task_id: int):
    application = _state["application"]
    if application is None:
        return None
    return application.bot_data.get("active_gdrive_tasks", {}).get(task_id)


def context_active_extract_task(task_id: int):
    application = _state["application"]
    if application is None:
        return None
    return application.bot_data.get("active_extract_tasks", {}).get(task_id)


def context_active_upload_task(task_id: int):
    application = _state["application"]
    if application is None:
        return None
    return application.bot_data.get("active_upload_tasks", {}).get(task_id)


class ReorderBody(BaseModel):
    order: list[int]


@app.post("/api/queue/reorder")
async def reorder_queue(body: ReorderBody, _user: dict = Depends(require_authorized)):
    n = len(body.order)
    for idx, task_id in enumerate(body.order):
        task = await db.get_task(task_id)
        if task and task["status"] in ("queued", "paused"):
            _ensure_task_owner(task, _user)
            await db.update_task(task_id, priority=n - idx)
    return {"ok": True}


@app.get("/api/files")
async def list_files(folder: str, path: str = "", sizes: bool = True, _user: dict = Depends(require_authorized)):
    try:
        dirs, files = filemanager.list_dir(folder, path)
    except filemanager.PathError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if sizes:
        dir_rels = [f"{path}/{d.name}" if path else d.name for d in dirs]
        dir_sizes = await asyncio.gather(*[filemanager.get_dir_size(folder, r) for r in dir_rels])
    else:
        dir_sizes = [None] * len(dirs)

    return {
        "dirs": [
            {"name": d.name, "size": filemanager.human_size(sz) if sz is not None else None}
            for d, sz in zip(dirs, dir_sizes)
        ],
        "files": [
            {"name": f.name, "size": filemanager.human_size(f.stat().st_size)}
            for f in files
        ],
    }


class MkdirBody(BaseModel):
    folder: str
    path: str = ""
    name: str


@app.post("/api/files/mkdir")
async def mkdir(body: MkdirBody, _user: dict = Depends(require_authorized)):
    try:
        filemanager.mkdir(body.folder, body.path, body.name)
        filemanager.invalidate_dir_size_cache(body.folder, body.path)
    except filemanager.PathError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileExistsError:
        raise HTTPException(status_code=400, detail="Ya existe una carpeta con ese nombre")
    return {"ok": True}


class RenameBody(BaseModel):
    folder: str
    path: str
    new_name: str


@app.post("/api/files/rename")
async def rename(body: RenameBody, _user: dict = Depends(require_authorized)):
    try:
        parent = str(PyPath(body.path).parent) if PyPath(body.path).parent != PyPath(".") else ""
        filemanager.rename(body.folder, body.path, body.new_name)
        filemanager.invalidate_dir_size_cache(body.folder, parent)
    except filemanager.PathError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileExistsError:
        raise HTTPException(status_code=400, detail="Ya existe un archivo con ese nombre")
    return {"ok": True}


class DeleteBody(BaseModel):
    folder: str
    path: str


@app.post("/api/files/delete")
async def delete(body: DeleteBody, _user: dict = Depends(require_authorized)):
    try:
        parent = str(PyPath(body.path).parent) if PyPath(body.path).parent != PyPath(".") else ""
        filemanager.delete(body.folder, body.path)
        filemanager.invalidate_dir_size_cache(body.folder, parent)
    except filemanager.PathError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


class ExtractBody(BaseModel):
    folder: str
    path: str
    dest_folder: str
    dest_path: str = ""
    password: str | None = None


@app.post("/api/files/extract")
async def extract_file(body: ExtractBody, _user: dict = Depends(require_authorized)):
    try:
        _base_src, src_target = filemanager.resolve_path(body.folder, body.path)
    except filemanager.PathError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not src_target.is_file() or not archive_utils.is_archive(src_target.name):
        raise HTTPException(status_code=400, detail="El archivo seleccionado no es un comprimido válido")

    if not body.password and await asyncio.to_thread(archive_utils.check_password_needed, str(src_target)):
        return {"ok": False, "needs_password": True, "error": "Contraseña requerida"}

    try:
        _base_dst, dst_target = filemanager.resolve_path(body.dest_folder, body.dest_path)
    except filemanager.PathError as e:
        raise HTTPException(status_code=400, detail=str(e))

    folder_name = archive_utils.archive_base_name(src_target.name)
    extract_dir = dst_target / folder_name

    dest_label = f"{body.dest_folder}/{body.dest_path}/{folder_name}" if body.dest_path else f"{body.dest_folder}/{folder_name}"
    total_uncompressed = await asyncio.to_thread(archive_utils.get_uncompressed_size, str(src_target), password=body.password)

    task_id = await db.create_task(
        kind="extract",
        filename=src_target.name,
        url=str(src_target),
        dest_folder=dest_label,
        dest_path=str(extract_dir),
        status="queued",
        total_size=total_uncompressed,
        requested_by=_user.get("id"),
    )

    if body.password:
        await db.set_setting(f"extract_pwd_{task_id}", body.password)

    context = _get_context()
    await h_dl.try_start_next(context)

    return {"ok": True, "queued": True, "task_id": task_id, "extracted_to": dest_label}


class CopyBody(BaseModel):
    folder: str
    paths: List[str]
    dest_folder: str
    dest_path: str = ""
    policy: str = "skip"
    move: bool = False


@app.post("/api/files/copy")
async def copy_files(body: CopyBody, _user: dict = Depends(require_authorized)):
    if not body.paths:
        raise HTTPException(status_code=400, detail="Nada seleccionado")
    try:
        job_id = await filemanager.start_copy(
            body.folder, body.paths, body.dest_folder, body.dest_path, body.policy, body.move
        )
    except filemanager.PathError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "job_id": job_id}


@app.get("/api/files/copy/{job_id}")
async def copy_status(job_id: int, _user: dict = Depends(require_authorized)):
    job = filemanager.COPY_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    return filemanager.job_public(job)


@app.post("/api/files/copy/{job_id}/cancel")
async def copy_cancel(job_id: int, _user: dict = Depends(require_authorized)):
    job = filemanager.COPY_JOBS.get(job_id)
    if job:
        job["cancel"] = True
    return {"ok": True}


@app.get("/api/files/download")
async def download_file(folder: str, path: str, _user: dict = Depends(require_authorized)):
    try:
        _base, target = filemanager.resolve_path(folder, path)
    except filemanager.PathError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(str(target), filename=target.name)


class UploadToTelegramBody(BaseModel):
    folder: str
    path: str
    chat_id: int | str | None = None


@app.post("/api/files/upload_to_telegram")
async def upload_file_to_telegram(body: UploadToTelegramBody, _user: dict = Depends(require_authorized)):
    manager = _get_userbot_manager()
    if not await manager.is_connected():
        raise HTTPException(
            status_code=400,
            detail="El Userbot no está conectado. Conéctalo desde Ajustes → Userbot para subir archivos a Telegram.",
        )

    try:
        _base, target = filemanager.resolve_path(body.folder, body.path)
    except filemanager.PathError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not target.is_file():
        raise HTTPException(status_code=400, detail="El archivo no existe")

    file_size = target.stat().st_size
    is_owner = _user.get("id") == config.OWNER_ID
    target_chat_id = body.chat_id if (is_owner and body.chat_id) else _user.get("id")

    task_id = await db.create_task(
        kind="upload",
        filename=target.name,
        dest_folder="Telegram",
        dest_path=str(target),
        status="downloading",
        total_size=file_size,
        requested_by=_user.get("id"),
        source_chat_id=target_chat_id,
        started_at=datetime.now().isoformat(),
    )

    context = _get_context()
    async_task = asyncio.create_task(
        h_files.run_file_upload(
            context=context,
            task_id=task_id,
            chat_id=target_chat_id,
            status_message_id=None,
            file_path=str(target),
            filename=target.name,
            total_size=file_size,
            user_id=_user.get("id"),
        )
    )
    context.bot_data.setdefault("active_upload_tasks", {})[task_id] = async_task

    return {"ok": True, "task_id": task_id, "filename": target.name}


@app.post("/api/userbot/uploads/{upload_id}/cancel")
async def cancel_userbot_upload(upload_id: str, _user: dict = Depends(require_authorized)):
    manager = _get_userbot_manager()
    manager.cancel_upload(upload_id)
    try:
        tid = int(upload_id)
        context = _get_context()
        await h_dl.cancel_task_by_id(context, tid)
    except Exception:
        pass
    return {"ok": True}


def _get_userbot_manager():
    application = _state["application"]
    if application is None:
        raise HTTPException(status_code=503, detail="El bot todavía no está listo")
    manager = application.bot_data.get("userbot_manager")
    if manager is None:
        raise HTTPException(status_code=503, detail="El userbot no está disponible ahora mismo")
    return manager


@app.get("/api/userbot")
async def get_userbot_info(_user: dict = Depends(require_owner)):
    manager = _get_userbot_manager()
    connected = await manager.is_connected()
    meta = await db.get_userbot_meta() or {}
    return {
        "connected": connected,
        "user_id": meta.get("user_id"),
        "username": meta.get("username"),
        "first_name": meta.get("first_name"),
        "connected_at": meta.get("connected_at"),
    }


@app.post("/api/userbot/disconnect")
async def userbot_disconnect(_user: dict = Depends(require_owner)):
    manager = _get_userbot_manager()
    await manager.disconnect_and_forget()
    return {"ok": True}


class PhoneBody(BaseModel):
    phone: str


@app.post("/api/userbot/connect/start")
async def userbot_connect_start(body: PhoneBody, _user: dict = Depends(require_owner)):
    manager = _get_userbot_manager()
    try:
        await manager.start_login(body.phone.strip())
    except PhoneNumberInvalidError:
        raise HTTPException(status_code=400, detail="Número de teléfono no válido")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"ok": True}


class CodeBody(BaseModel):
    code: str


@app.post("/api/userbot/connect/code")
async def userbot_connect_code(body: CodeBody, _user: dict = Depends(require_owner)):
    manager = _get_userbot_manager()
    try:
        await manager.submit_code(body.code.strip().replace(" ", ""))
    except SessionPasswordNeededError:
        return {"ok": True, "needs_password": True}
    except PhoneCodeInvalidError:
        raise HTTPException(status_code=400, detail="Código incorrecto")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"ok": True, "needs_password": False}


class PasswordBody(BaseModel):
    password: str


@app.post("/api/userbot/connect/password")
async def userbot_connect_password(body: PasswordBody, _user: dict = Depends(require_owner)):
    manager = _get_userbot_manager()
    try:
        await manager.submit_password(body.password)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Contraseña incorrecta o error: {e}")
    return {"ok": True}


@app.get("/api/users")
async def list_users(_user: dict = Depends(require_owner)):
    users = await db.list_authorized_users()
    return {
        "owner_id": config.OWNER_ID,
        "users": [
            {
                "user_id": u["user_id"],
                "username": u.get("username"),
                "first_name": u.get("first_name"),
                "added_at": u.get("added_at"),
            }
            for u in users
        ],
    }


class UserIdBody(BaseModel):
    user_id: int


@app.post("/api/users/add")
async def add_user(body: UserIdBody, _user: dict = Depends(require_owner)):
    await db.add_authorized_user(body.user_id)
    application = _state["application"]
    if application:
        try:
            await application.bot.send_message(
                chat_id=body.user_id,
                text="🎉 Ahora tienes acceso a este bot de descargas. Usa /start para empezar.",
            )
        except Exception:
            pass
    return {"ok": True}


@app.post("/api/users/remove")
async def remove_user(body: UserIdBody, _user: dict = Depends(require_owner)):
    await db.remove_authorized_user(body.user_id)
    return {"ok": True}


_OAUTH_PAGE = """<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Google Drive</title>
<style>
  body {{ font-family: -apple-system, sans-serif; background:#0d0d0f; color:#fff;
         display:flex; align-items:center; justify-content:center; height:100vh; margin:0; }}
  .box {{ text-align:center; padding:24px; max-width:420px; }}
  h1 {{ font-size:20px; margin-bottom:8px; }}
  p {{ color:#9a9a9e; font-size:14px; line-height:1.6; }}
</style></head>
<body><div class="box"><h1>{title}</h1><p>{message}</p></div></body></html>"""


@app.get("/oauth2/google/callback", response_class=HTMLResponse)
async def google_oauth_callback(code: str = "", state: str = "", error: str = ""):
    if error:
        return _OAUTH_PAGE.format(title="❌ Cancelled / Cancelado", message=f"Google returned an error / Google devolvió un error: {error}")
    if not code or not state or not google_drive.consume_oauth_state(state):
        return _OAUTH_PAGE.format(
            title="❌ Invalid request / Solicitud inválida",
            message="This link has expired or is not valid. Press \"Connect\" again in the bot or the web app. / "
                    "Este enlace ya expiró o no es válido. Vuelve a pulsar \"Conectar\" desde el bot o la web.",
        )
    try:
        await google_drive.exchange_code(code)
    except Exception as e:
        return _OAUTH_PAGE.format(title="❌ Error", message=str(e))
    return _OAUTH_PAGE.format(
        title="✅ Account connected / Cuenta conectada",
        message="You can close this tab and go back to Telegram. / Ya puedes cerrar esta pestaña y volver a Telegram.",
    )


@app.get("/api/gdrive/status")
async def gdrive_status(_user: dict = Depends(require_owner)):
    configured = google_drive.is_configured()
    connected = await google_drive.is_connected() if configured else False
    email = None
    if connected:
        try:
            email = await db.get_setting("google_email") or await google_drive.get_account_email()
            await db.set_setting("google_email", email)
        except Exception:
            email = None
    return {"configured": configured, "connected": connected, "email": email}


@app.post("/api/gdrive/connect/start")
async def gdrive_connect_start(_user: dict = Depends(require_owner)):
    if not google_drive.is_configured():
        raise HTTPException(status_code=400, detail="Faltan las credenciales de Google en el servidor")
    state = google_drive.new_oauth_state()
    return {"url": google_drive.build_auth_url(state)}


@app.post("/api/gdrive/disconnect")
async def gdrive_disconnect_endpoint(_user: dict = Depends(require_owner)):
    await google_drive.disconnect()
    return {"ok": True}


# ── Local network access (browser without Telegram) ─────────────────────────────
_LOGIN_PAGE = """<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NAS Telegram Bot</title><style>body{{font-family:-apple-system,sans-serif;background:#0d0d0f;color:#fff;display:flex;
align-items:center;justify-content:center;height:100vh;margin:0}}.box{{text-align:center;padding:24px;max-width:440px}}
p{{color:#9a9a9e;font-size:14px;line-height:1.6}}</style></head><body><div class="box"><h1>{title}</h1><p>{message}</p></div></body></html>"""


def _secure_request(request: Request) -> bool:
    return request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "").lower() == "https"


@app.get("/login", include_in_schema=False)
async def lan_login(request: Request, t: str = ""):
    import lan_access
    from fastapi.responses import RedirectResponse
    user = lan_access.consume_token(t) if await lan_access.is_enabled() else None
    if not user:
        return HTMLResponse(_LOGIN_PAGE.format(
            title="🔒 Link expired / Enlace caducado",
            message="This access link has expired, was already used or local network access is off. "
                    "Ask the bot for a new one (/web). / Este enlace de acceso ha caducado, ya se usó o el acceso "
                    "por red local está desactivado. Pide uno nuevo al bot (/web)."), status_code=403)
    if user["id"] != config.OWNER_ID and not await db.is_authorized_user(user["id"]):
        return HTMLResponse(_LOGIN_PAGE.format(title="⛔", message="No autorizado / Not authorised"), status_code=403)
    sid = await lan_access.create_session(user, request.headers.get("user-agent", ""))
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie(lan_access.COOKIE, sid, max_age=lan_access.SESSION_TTL, httponly=True, samesite="strict",
                    secure=_secure_request(request), path="/")
    return resp


@app.get("/api/session")
async def session_info(_user: dict = Depends(require_authorized)):
    return {"user": {"id": _user.get("id"), "first_name": _user.get("first_name")}, "owner": _user.get("id") == config.OWNER_ID}


@app.post("/api/session/logout")
async def session_logout(request: Request):
    import lan_access
    sid = request.cookies.get(lan_access.COOKIE)
    if sid:
        await lan_access.revoke_sid(sid)
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(lan_access.COOKIE, path="/")
    return resp


class LanBody(BaseModel):
    enabled: bool | None = None
    url: str | None = None


class LanRevokeBody(BaseModel):
    id: str = ""
    all: bool = False


@app.get("/api/lan")
async def lan_get(_user: dict = Depends(require_owner)):
    import lan_access
    return {"enabled": await lan_access.is_enabled(), "url": await lan_access.get_url(),
            "sessions": await lan_access.list_sessions()}


@app.post("/api/lan")
async def lan_set(body: LanBody, _user: dict = Depends(require_owner)):
    import lan_access
    import webserver
    if body.url is not None:
        url = lan_access.normalize_url(body.url)
        if not url:
            raise HTTPException(status_code=400, detail="Dirección no válida")
        await lan_access.set_url(url)
    if body.enabled is not None:
        await lan_access.set_enabled(body.enabled)
        if not await lan_access.server_needed():
            asyncio.get_running_loop().call_later(1, lambda: asyncio.ensure_future(webserver.stop()))
    return await lan_get(_user)


@app.post("/api/lan/link")
async def lan_link(_user: dict = Depends(require_authorized)):
    import lan_access
    from types import SimpleNamespace
    link = await lan_access.login_link(SimpleNamespace(id=_user.get("id"), username=_user.get("username"),
                                                       first_name=_user.get("first_name")))
    if not link:
        raise HTTPException(status_code=400, detail="El acceso por red local está desactivado o falta la dirección local")
    return {"url": link, "expires_in": lan_access.TOKEN_TTL}


@app.post("/api/lan/sessions/revoke")
async def lan_revoke(body: LanRevokeBody, _user: dict = Depends(require_owner)):
    import lan_access
    if body.all:
        await lan_access.revoke_all()
    elif not await lan_access.revoke(body.id):
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    return {"ok": True}


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
