import asyncio
import logging
import re
import uuid
from datetime import datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

import archive_utils
import db
import torbox
from rich_ui import esc, progress_card
from utils import authorized_only

logger = logging.getLogger(__name__)

import torrent_clients

PROVIDER_LABELS = {"realdebrid": "💳 Real-Debrid", "torbox": "📦 TorBox",
                   **{k: f"{c['icon']} {c['label']}" for k, c in torrent_clients.CLIENTS.items()}}

pending_sources: dict[str, dict] = {}

TB_ERROR_STATES = {"error", "failed", "expired", "missingfiles"}


def _states() -> dict:
    import handlers_realdebrid as h_rd
    return h_rd.rd_torrent_states


def schedule_fields(sched_str: str | None) -> dict:
    if not sched_str or sched_str == "now":
        return {}
    import handlers_downloads as h_dl
    now = datetime.now(h_dl.LOCAL_TZ)
    dt = None
    if sched_str == "1h":
        dt = now + timedelta(hours=1)
    elif sched_str == "2h":
        dt = now + timedelta(hours=2)
    elif sched_str == "4h":
        dt = now + timedelta(hours=4)
    elif sched_str == "night":
        dt = now.replace(hour=2, minute=0, second=0, microsecond=0)
        if dt <= now:
            dt += timedelta(days=1)
    return {"status": "scheduled", "scheduled_for": dt.isoformat()} if dt else {}


def source_name(kind: str, value) -> str:
    if kind == "torrent_file":
        return torbox.torrent_info(value)[1] or "Torrent"
    return torbox.magnet_name(value) or "Torrent"


def stash_source(kind: str, value, requested_by) -> str:
    key = uuid.uuid4().hex[:10]
    pending_sources[key] = {"kind": kind, "value": value, "requested_by": requested_by,
                            "name": source_name(kind, value)}
    return key


async def prepare(provider: str, kind: str, value, requested_by) -> dict:
    import handlers_realdebrid as h_rd
    import handlers_settings as h_settings
    if provider == "torbox":
        return await prepare_torbox(kind, value, requested_by)
    if torrent_clients.is_client(provider):
        import handlers_clients
        return await handlers_clients.prepare(kind, value, requested_by, provider)
    token = await h_settings.get_rd_token()
    if kind == "torrent_file":
        return await h_rd.add_torrent_file_get_files(token, value, requested_by=requested_by)
    return await h_rd.add_magnet_get_files(token, value, requested_by=requested_by)


async def prepare_torbox(kind: str, value, requested_by) -> dict:
    import handlers_settings as h_settings
    token = await h_settings.get_tb_token()
    if kind == "torrent_file":
        info_hash, name = torbox.torrent_info(value)
    else:
        info_hash, name = torbox.magnet_infohash(value), torbox.magnet_name(value)

    cached = None
    try:
        cached = await torbox.check_cached(token, info_hash) if info_hash else None
    except torbox.TorBoxError as e:
        logger.warning("TorBox checkcached falló: %s", e)

    files = []
    if cached:
        for i, f in enumerate(cached["files"]):
            files.append({"id": i, "path": f.get("name") or f"archivo{i}", "bytes": f.get("size") or 0})
        name = cached.get("name") or name

    torrent_id = uuid.uuid4().hex[:10]
    state = {
        "provider": "torbox",
        "token": token,
        "source": (kind, value),
        "hash": info_hash,
        "cached": bool(cached),
        "files": files,
        "selected": {f["id"] for f in files},
        "select_files": bool(files),
        "torrent_name": name or "Torrent",
        "total": (cached or {}).get("size") or 0,
        "chat_id": requested_by,
        "message_id": None,
        "requested_by": requested_by,
        "extract_after": False,
        "last_snapshot": {"status": "esperando", "progress": 0, "speed": 0, "seeders": 0, "total": 0},
    }
    _states()[torrent_id] = state
    return state | {"torrent_id": torrent_id}


def uncached_note(name: str) -> str:
    return (
        f"📦 <b>{esc(name)}</b>\n\n"
        "Este torrent <b>no está en la caché de TorBox</b>, así que no se puede elegir archivos: "
        "TorBox lo descargará primero y después se bajará al NAS como un <b>ZIP</b> que se "
        "descomprimirá automáticamente en la carpeta que elijas.\n\nElige la carpeta destino:"
    )


async def present(message, torrent_id: str):
    import handlers_downloads as h_dl
    import handlers_realdebrid as h_rd
    state = _states()[torrent_id]
    state["chat_id"] = message.chat_id
    state["message_id"] = message.message_id
    if state.get("provider") == "torbox" and not state.get("select_files"):
        await message.edit_text(
            uncached_note(state["torrent_name"]), parse_mode=ParseMode.HTML,
            reply_markup=await h_dl.dest_markup(f"T{torrent_id}"),
        )
        return
    await message.edit_text(
        h_rd._file_list_text(state["files"], state["selected"], state.get("provider", "realdebrid")),
        parse_mode=ParseMode.HTML,
        reply_markup=h_rd._file_selection_keyboard(torrent_id, state["files"], state["selected"]),
    )


async def run_provider(message, key: str, provider: str):
    src = pending_sources.pop(key, None)
    if not src:
        await message.edit_text("⚠️ Esta solicitud ya expiró. Envía el torrent de nuevo.")
        return
    await message.edit_text(f"⏳ Añadiendo a {PROVIDER_LABELS[provider]}...")
    try:
        state = await prepare(provider, src["kind"], src["value"], src["requested_by"])
    except ValueError as e:
        await message.edit_text(f"⚠️ {e}")
        return
    except Exception as e:
        await message.edit_text(f"❌ Error al añadir el torrent a {PROVIDER_LABELS[provider]}: {e}")
        return
    await present(message, state["torrent_id"])


async def offer_source(message, kind: str, value, requested_by):
    import handlers_settings as h_settings
    providers = await h_settings.available_providers()
    if not providers:
        await message.edit_text(
            "⚠️ No hay ningún proveedor de descarga configurado.\n"
            "Ve a ⚙️ Ajustes → 📥 Proveedores de descarga y activa Real-Debrid, TorBox o un cliente local."
        )
        return
    key = stash_source(kind, value, requested_by)
    if len(providers) == 1:
        await run_provider(message, key, providers[0])
        return
    name = pending_sources[key]["name"]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(PROVIDER_LABELS[p], callback_data=f"provsel:{p}:{key}") for p in providers],
        [InlineKeyboardButton("🚫 Cancelar", callback_data=f"provsel:cancel:{key}")],
    ])
    await message.edit_text(
        f"🧲 <b>{esc(name)}</b>\n\n¿Con qué proveedor quieres descargar este torrent?",
        parse_mode=ParseMode.HTML, reply_markup=kb,
    )


@authorized_only
async def provider_selected(update, context):
    query = update.callback_query
    await query.answer()
    _, provider, key = query.data.split(":", 2)
    if provider == "cancel":
        pending_sources.pop(key, None)
        await query.edit_message_text("🚫 Cancelado.")
        return
    await run_provider(query.message, key, provider)


def _eta_text(seconds) -> str | None:
    if not seconds or seconds <= 0 or seconds >= 8640000:
        return None
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m {s:02d}s"


def _safe_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", name).strip() or "torrent"


async def _edit(context, state, text, markup=None, html=False):
    chat_id, message_id = state.get("chat_id"), state.get("message_id")
    if not chat_id or not message_id:
        return
    try:
        await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup,
                                            parse_mode=ParseMode.HTML if html else None)
    except Exception:
        pass


async def _enqueue(context, state, url: str, filename: str, size: int | None, force_extract: bool = False):
    import handlers_downloads as h_dl
    req_by = state.get("requested_by") or state.get("chat_id")
    task_id = await h_dl.enqueue_link_task(
        context, url=url, filename=filename, dest_folder=state["dest_folder"], dest_path=state["dest_path"],
        chat_id=state.get("chat_id"), requested_by=req_by, client="torbox",
    )
    fields = schedule_fields(state.get("schedule"))
    if size:
        fields["total_size"] = size
    if force_extract or state.get("extract_after"):
        fields["extract_after"] = 1
    if fields:
        await db.update_task(task_id, **fields)
    return task_id


async def run(context, torrent_id: str):
    state = _states().get(torrent_id)
    if not state:
        return
    try:
        if state["cached"]:
            try:
                await _run_cached(context, torrent_id, state)
                return
            except torbox.TorBoxError as e:
                if state.get("tb_id"):
                    raise
                logger.info("TorBox: ya no estaba en caché (%s); se descargará en su nube", e)
        await _run_uncached(context, torrent_id, state)
    except asyncio.CancelledError:
        return
    except torbox.TorBoxError as e:
        await _edit(context, state, f"❌ TorBox: {e}")
        _states().pop(torrent_id, None)
    except Exception as e:
        logger.exception("Error en el flujo TorBox")
        await _edit(context, state, f"❌ Error inesperado con TorBox: {e}")
        _states().pop(torrent_id, None)


async def _add_to_torbox(state, only_if_cached: bool) -> int:
    kind, value = state["source"]
    res = await torbox.create_torrent(
        state["token"],
        magnet=value if kind == "magnet" else None,
        torrent_bytes=value if kind == "torrent_file" else None,
        only_if_cached=only_if_cached,
    )
    tb_id = res.get("torrent_id")
    if not tb_id and state.get("hash"):
        found = await torbox.find_by_hash(state["token"], state["hash"])
        tb_id = found.get("id") if found else None
    if not tb_id:
        if res.get("queued_id"):
            raise torbox.TorBoxError("TorBox dejó el torrent en su cola (has alcanzado el límite de descargas activas de tu plan).")
        raise torbox.TorBoxError("TorBox no devolvió el identificador del torrent.")
    state["tb_id"] = tb_id
    return tb_id


async def _run_cached(context, torrent_id: str, state: dict):
    import handlers_downloads as h_dl
    import handlers_realdebrid as h_rd
    token = state["token"]
    await _edit(context, state, "⚡ Torrent en caché de TorBox: generando enlaces...")
    tb_id = state.get("tb_id") or await _add_to_torbox(state, only_if_cached=True)

    info = None
    for _ in range(6):
        info = await torbox.get_torrent(token, tb_id)
        if info and info.get("files"):
            break
        await asyncio.sleep(1.5)
    tb_files = (info or {}).get("files") or []
    if not tb_files:
        raise torbox.TorBoxError("TorBox no devolvió la lista de archivos del torrent.")

    if state["files"]:
        wanted = {state["files"][i]["path"] for i in state["selected"] if 0 <= i < len(state["files"])}
        chosen = [f for f in tb_files if f.get("name") in wanted]
        if not chosen:
            chosen = [f for idx, f in enumerate(tb_files) if idx in state["selected"]]
    else:
        chosen = tb_files
    if not chosen:
        raise torbox.TorBoxError("No hay archivos seleccionados.")

    short_names = [(f.get("short_name") or (f.get("name") or "").split("/")[-1] or "archivo") for f in chosen]
    dup = len(set(short_names)) != len(short_names)
    created = failed = 0
    for f, short in zip(chosen, short_names):
        filename = _safe_filename((f.get("name") or short).replace("/", " - ") if dup else short)
        try:
            url = await torbox.request_download(token, tb_id, f["id"])
        except torbox.TorBoxError as e:
            logger.warning("TorBox requestdl falló (%s): %s", filename, e)
            failed += 1
            continue
        if archive_utils.is_archive(filename) and not state.get("extract_after") and state.get("chat_id"):
            await h_rd._ask_extract_for_resolved_file(
                context, state["chat_id"], url, filename, state["dest_folder"], state["dest_path"],
                requested_by=state.get("requested_by"), client="torbox",
            )
            created += 1
            continue
        await _enqueue(context, state, url, filename, f.get("size"))
        created += 1

    _states().pop(torrent_id, None)
    if not created:
        await _edit(context, state, "⚠️ No se pudo generar ningún enlace de descarga en TorBox.")
        return
    warn = f"\n⚠️ {failed} archivo(s) no se pudieron resolver." if failed else ""
    await _edit(context, state,
                f"✅ {created} archivo(s) listos en TorBox.\nAñadidos a la cola de descarga hacia {state['dest_folder']}.{warn}")
    await h_dl.try_start_next(context)


async def _run_uncached(context, torrent_id: str, state: dict):
    import handlers_downloads as h_dl
    token = state["token"]
    cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data=f"rdcancel:{torrent_id}")]])
    await _edit(context, state, "⏳ Enviando el torrent a TorBox...")
    tb_id = state.get("tb_id") or await _add_to_torbox(state, only_if_cached=False)

    last_text = None
    while True:
        info = await torbox.get_torrent(token, tb_id)
        if info is None:
            raise torbox.TorBoxError("El torrent desapareció de TorBox.")
        dl_state = (info.get("download_state") or "").lower()
        progress = float(info.get("progress") or 0) * 100
        speed = info.get("download_speed") or 0
        seeds = info.get("seeds") or 0
        size = info.get("size") or state.get("total") or 0
        state["torrent_name"] = info.get("name") or state["torrent_name"]
        state["last_snapshot"] = {
            "status": dl_state or "descargando", "progress": progress, "speed": speed,
            "seeders": seeds, "total": size,
        }

        if info.get("download_finished") or dl_state in ("completed", "cached"):
            break
        if dl_state in TB_ERROR_STATES:
            raise torbox.TorBoxError(f"TorBox no pudo descargar el torrent (estado: {dl_state}).")

        eta = info.get("eta")
        text = progress_card(
            "Descargando torrent en TorBox", "⬇️", state["torrent_name"], progress, size, speed,
            _eta_text(eta), [("🌱 Seeders", str(seeds)), ("Estado", esc(dl_state or "..."))],
        )
        if text != last_text:
            await _edit(context, state, text, markup=cancel_kb, html=True)
            last_text = text
        await asyncio.sleep(5)

    await _edit(context, state, "🔗 Generando enlace de descarga...")
    files = info.get("files") or []
    name = _safe_filename(info.get("name") or state["torrent_name"])
    if len(files) <= 1:
        f = files[0] if files else {"id": 0, "name": name}
        url = await torbox.request_download(token, tb_id, f.get("id", 0))
        filename = _safe_filename(f.get("short_name") or (f.get("name") or name).split("/")[-1])
        await _enqueue(context, state, url, filename, info.get("size"))
        note = ""
    else:
        url = await torbox.request_download(token, tb_id, 0, zip_link=True)
        await _enqueue(context, state, url, f"{name}.zip", info.get("size"), force_extract=True)
        note = " como ZIP (se descomprimirá al terminar)"

    _states().pop(torrent_id, None)
    await _edit(context, state, f"✅ Listo en TorBox. Añadido a la cola de descarga{note} hacia {state['dest_folder']}.")
    await h_dl.try_start_next(context)


async def cancel(state: dict):
    task = state.get("monitor_task")
    if task:
        task.cancel()
    if state.get("tb_id") and not state.get("keep_remote"):
        try:
            await torbox.delete_torrent(state["token"], state["tb_id"])
        except Exception as e:
            logger.warning("No se pudo borrar el torrent de TorBox: %s", e)


@authorized_only
async def handle_torrent_document(update, context):
    msg = update.effective_message
    status = await msg.reply_text("⏳ Leyendo el archivo .torrent...")
    try:
        tg_file = await context.bot.get_file(msg.document.file_id)
        data = bytes(await tg_file.download_as_bytearray())
    except Exception as e:
        await status.edit_text(f"❌ No pude descargar el .torrent: {e}")
        return
    if not torbox.torrent_info(data)[0]:
        await status.edit_text("⚠️ Ese archivo no parece un .torrent válido.")
        return
    await offer_source(status, "torrent_file", data, update.effective_user.id)
