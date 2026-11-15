import asyncio
import os
import html
import mimetypes
import re
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import BadRequest

import config
import db
import downloader
import archive_utils
import filemanager
import google_drive
from i18n import L
import keyboards
import real_debrid
import rules
import tmdb_helper
from rich_ui import esc, r_h, r_p, r_ul, r_table, r_footer, r_details, rich
import ytdlp_downloader
from utils import authorized_only, get_command_payload, client_label

LOCAL_TZ = ZoneInfo(config.TIMEZONE)


def _now_iso() -> str:
    return datetime.now(LOCAL_TZ).isoformat()


async def _mark_started(task_id: int):
    await db.update_task(task_id, started_at=_now_iso())


async def _mark_finished(task_id: int, status: str, error: str | None = None):
    fields = {"status": status, "finished_at": _now_iso()}
    if error is not None:
        fields["error"] = error
    await db.update_task(task_id, **fields)
    if status == "done":
        try:
            task = await db.get_task(task_id)
            if task and task.get("dest_path"):
                filemanager.invalidate_dir_size_cache_path(task["dest_path"])
        except Exception:
            pass


async def probe_link(url: str) -> tuple[str | None, int | None]:
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
            resp = await client.head(url)
            if resp.status_code >= 400:
                async with client.stream("GET", url) as stream:
                    resp = stream
                    filename = _filename_from_headers(resp.headers, url)
                    size = _content_length(resp.headers)
                    return filename, size
            filename = _filename_from_headers(resp.headers, url)
            size = _content_length(resp.headers)
            return filename, size
    except Exception:
        return None, None


def _content_length(headers) -> int | None:
    value = headers.get("content-length")
    if value and value.isdigit():
        return int(value)
    return None


def _filename_from_headers(headers, url: str) -> str | None:
    disposition = headers.get("content-disposition", "")
    match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";\n]+)"?', disposition)
    if match:
        return match.group(1).strip()
    return None


def extract_http_urls(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip().startswith(("http://", "https://"))]


def extract_magnet_links(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip().startswith("magnet:?")]


def _cancel_button(task_id):
    return InlineKeyboardButton("❌ Cancelar", callback_data=f"dlcancel:{task_id}")


def dest_root_keyboard(ref: str) -> InlineKeyboardMarkup:
    folders_row = [
        InlineKeyboardButton(f"📁 {name}", callback_data=f"dlnav:{ref}:{name}:{keyboards.token_for(name, '')}")
        for name in config.FOLDERS
    ]
    tools_row = [
        InlineKeyboardButton("⏰ Programar", callback_data=f"dlsched:{ref}:Downloads:{keyboards.token_for('Downloads', '')}"),
    ]
    if not ref.startswith("T") and "," not in ref and len(f"dlrn:{ref}") < 60:
        tools_row.append(InlineKeyboardButton(L("✏️ Renombrar", "✏️ Rename"), callback_data=f"dlrn:{ref}"))
    return InlineKeyboardMarkup([folders_row, tools_row])


async def ref_info(ref: str) -> dict | None:
    if ref.startswith("T"):
        import handlers_realdebrid as h_rd
        state = h_rd.rd_torrent_states.get(ref[1:])
        if not state:
            return None
        files = state.get("files") or []
        selected = state.get("selected") or set()
        size = sum((f.get("bytes") or f.get("size") or 0) for i, f in enumerate(files)
                   if not selected or f.get("id", i) in selected or i in selected)
        names = []
        for i, f in enumerate(files):
            if not selected or f.get("id", i) in selected or i in selected:
                n = f.get("path") or f.get("name") or f.get("short_name") or ""
                if n:
                    names.append(str(n).split("/")[-1])
        return {"name": state.get("torrent_name", ""), "size": size, "source": "torrent",
                "user": state.get("requested_by"), "archive": False, "torrent": True, "files": names}
    ids = [int(x) for x in ref.split(",") if x.strip().isdigit()]
    tasks = [t for t in [await db.get_task(i) for i in ids] if t]
    if not tasks:
        return None
    first = tasks[0]
    return {"name": first.get("filename") or "", "size": sum(t.get("total_size") or 0 for t in tasks),
            "source": rules.kind_to_source(first.get("kind")), "user": first.get("requested_by"),
            "archive": any(archive_utils.is_archive(t.get("filename") or "") for t in tasks), "torrent": False,
            "files": [t.get("filename") or "" for t in tasks] if len(tasks) > 1 else None}


async def rule_matches(ref: str) -> list[dict]:
    info = await ref_info(ref)
    if not info:
        return []
    found = await rules.find(info["name"], info["size"], info["source"], info["user"], info.get("files"))
    if not found:
        fb = await rules.best(info["name"], info["size"], info["source"], info["user"], info.get("files"))
        found = [fb] if fb else []
    return found


async def dest_markup(ref: str) -> InlineKeyboardMarkup:
    base = dest_root_keyboard(ref)
    try:
        found = await rule_matches(ref)
        info = await ref_info(ref)
    except Exception:
        return base
    if not found or not info or await rules.get_mode() == "off":
        return base
    rows = []
    for r in found[:3]:
        folder, sub = rules.destination(r, info["name"], info["user"])
        if not folder:
            continue
        label = f"{folder}/{sub}" if sub else folder
        rows.append([InlineKeyboardButton(f"⭐ {label}"[:60],
                                          callback_data=f"dlsave:{ref}:{folder}:{keyboards.token_for(folder, sub)}")])
    return InlineKeyboardMarkup(rows + list(base.inline_keyboard))


async def try_auto(context, ref: str, query=None):
    if await rules.get_mode() != "auto":
        return None
    info = await ref_info(ref)
    if not info:
        return None
    found = await rules.find(info["name"], info["size"], info["source"], info["user"], info.get("files"))
    opts = await rules.get_options()
    if not found and opts["fallback"]:
        fb = await rules.best(info["name"], info["size"], info["source"], info["user"], info.get("files"))
        found = [fb] if fb else []
    if not found or (len(found) > 1 and opts["conflict"] == "ask"):
        return None
    rule = found[0]
    folder, sub = rules.destination(rule, info["name"], info["user"])
    if not folder:
        return None
    if info["archive"] and rule["extract"] == "ask":
        return None
    if info["torrent"]:
        if query is None:
            return None
        relpath = await tmdb_helper.adjust_relpath(folder, sub, info["name"])
        _base, target = filemanager.resolve_path(folder, relpath)
        target.mkdir(parents=True, exist_ok=True)
        label = f"{folder}/{relpath}" if relpath else folder
        import handlers_realdebrid as h_rd
        await h_rd.confirm_destination(context, query, ref[1:], str(target), label)
        return {"label": label, "rule": rule["name"], "handled": True}
    ids = [int(x) for x in ref.split(",") if x.strip().isdigit()]
    _dir, label = await set_destination(context, ids, folder, sub, extract=rule["extract"] == "yes")
    return {"label": label, "rule": rule["name"], "name": info["name"], "handled": False}


def auto_text(auto: dict) -> str:
    return L(f"📍 <b>{esc(auto.get('name', ''))}</b>\nDestino automático: <code>{esc(auto['label'])}</code> (regla «{esc(auto['rule'])}»)",
             f"📍 <b>{esc(auto.get('name', ''))}</b>\nAutomatic destination: <code>{esc(auto['label'])}</code> (rule “{esc(auto['rule'])}”)")


DEST_PAGE_SIZE = 16


def dest_nav_keyboard(ref: str, folder_key: str, relpath: str, page: int = 0) -> InlineKeyboardMarkup:
    dirs, _files = filemanager.list_dir(folder_key, relpath)
    kb = []

    total_pages = max(1, -(-len(dirs) // DEST_PAGE_SIZE))
    page = max(0, min(page, total_pages - 1))
    start = page * DEST_PAGE_SIZE
    page_dirs = dirs[start:start + DEST_PAGE_SIZE]

    row = []
    for d in page_dirs:
        rel = str(Path(relpath) / d.name) if relpath else d.name
        token = keyboards.token_for(folder_key, rel)
        row.append(InlineKeyboardButton(f"📁 {d.name}", callback_data=f"dlnav:{ref}:{folder_key}:{token}"))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)

    here_token = keyboards.token_for(folder_key, relpath)

    if total_pages > 1:
        pager_row = []
        if page > 0:
            pager_row.append(InlineKeyboardButton("◀ Anterior", callback_data=f"dlnav:{ref}:{folder_key}:{here_token}:{page - 1}"))
        if page < total_pages - 1:
            pager_row.append(InlineKeyboardButton("Siguiente ▶", callback_data=f"dlnav:{ref}:{folder_key}:{here_token}:{page + 1}"))
        kb.append(pager_row)

    kb.append([
        InlineKeyboardButton("📥 Guardar aquí", callback_data=f"dlsave:{ref}:{folder_key}:{here_token}"),
        InlineKeyboardButton("➕ Nueva carpeta", callback_data=f"dlmkdir:{ref}:{folder_key}:{here_token}"),
    ])
    kb.append([
        InlineKeyboardButton("⏰ Programar", callback_data=f"dlsched:{ref}:{folder_key}:{here_token}"),
    ])

    if relpath:
        parent = Path(relpath).parent
        parent = "" if parent == Path(".") else str(parent)
        parent_token = keyboards.token_for(folder_key, parent)
        kb.append([InlineKeyboardButton("⬅️ Atrás", callback_data=f"dlnav:{ref}:{folder_key}:{parent_token}")])
    else:
        kb.append([InlineKeyboardButton("⬅️ Cambiar carpeta raíz", callback_data=f"dlroot:{ref}")])

    return InlineKeyboardMarkup(kb)


FILE_BATCH_DELAY = 1.0


def _derive_filename(msg, file_obj) -> str:
    existing_name = getattr(file_obj, "file_name", None)
    if existing_name:
        return existing_name

    mime_type = getattr(file_obj, "mime_type", None)
    ext = mimetypes.guess_extension(mime_type) if mime_type else None
    if not ext:
        ext = {
            "video/x-matroska": ".mkv", "video/quicktime": ".mov", "video/mp4": ".mp4",
            "audio/mpeg": ".mp3", "audio/ogg": ".ogg", "audio/x-m4a": ".m4a",
            "image/jpeg": ".jpg", "image/webp": ".webp",
        }.get(mime_type, "")
    if ext == ".jpe":
        ext = ".jpg"

    if msg.photo:
        ext = ext or ".jpg"

    base = None
    if msg.caption:
        base = re.sub(r"[\\/:*?\"<>|\n\r]+", " ", msg.caption).strip()[:60]
    if not base:
        date_str = msg.date.strftime("%Y%m%d_%H%M%S") if msg.date else str(msg.message_id)
        kind = "video" if msg.video else ("audio" if msg.audio else ("foto" if msg.photo else "archivo"))
        base = f"{kind}_{date_str}"

    return f"{base}{ext}" if ext and not base.lower().endswith(ext.lower()) else (base or f"archivo_{msg.message_id}{ext}")


@authorized_only
async def handle_incoming_file(update, context):
    msg = update.effective_message
    chat_id = msg.chat_id

    doc = msg.document
    if doc and context.user_data.get("pending_restore"):
        import handlers_tools
        if await handlers_tools.handle_restore_document(update, context):
            return
    if doc and ((doc.file_name or "").lower().endswith(".torrent") or doc.mime_type == "application/x-bittorrent"):
        import handlers_torbox
        await handlers_torbox.handle_torrent_document(update, context)
        return

    pending = context.bot_data.setdefault("pending_incoming_files", {})
    pending.setdefault(chat_id, []).append(msg)

    timers = context.bot_data.setdefault("pending_incoming_timers", {})
    old_timer = timers.get(chat_id)
    if old_timer and not old_timer.done():
        old_timer.cancel()
    timers[chat_id] = asyncio.create_task(_flush_pending_files(context, chat_id))


async def _flush_pending_files(context, chat_id, delay: float = FILE_BATCH_DELAY):
    try:
        await asyncio.sleep(delay)
    except asyncio.CancelledError:
        return

    pending = context.bot_data.get("pending_incoming_files", {})
    messages = pending.pop(chat_id, [])
    if not messages:
        return

    created = []
    for msg in messages:
        file_obj = msg.document or msg.video or msg.audio or (msg.photo[-1] if msg.photo else None)
        filename = _derive_filename(msg, file_obj)
        try:
            copied = await context.bot.copy_message(
                chat_id=config.CHANNEL_ID,
                from_chat_id=msg.chat_id,
                message_id=msg.message_id,
            )
        except Exception as e:
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"❌ No se pudo copiar <b>{esc(filename)}</b> al canal privado: {esc(e)}\n\n"
                    "Comprueba que CHANNEL_ID sea correcto y que el bot sea administrador del canal."
                ),
                parse_mode=ParseMode.HTML,
            )
            continue

        task_id = await db.create_task(
            kind="telegram",
            source_chat_id=config.CHANNEL_ID,
            source_message_id=copied.message_id,
            filename=filename,
            requested_by=chat_id,
        )
        created.append(task_id)

    await _ask_destination(context, chat_id, created)


async def _ask_destination(context, chat_id, created):
    """Tras crear tareas de archivos (reenviados o por enlace de Telegram): carpeta de destino."""
    if not created:
        return

    if len(created) == 1:
        task_id = created[0]
        task = await db.get_task(task_id)
        auto = await try_auto(context, str(task_id))
        if auto:
            await context.bot.send_message(chat_id=chat_id, text=auto_text(auto), parse_mode=ParseMode.HTML)
            return
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"📄 <b>{esc(task['filename'])}</b>\nElige la carpeta destino:",
            parse_mode=ParseMode.HTML,
            reply_markup=await dest_markup(str(task_id)),
        )
        return

    ref = ",".join(str(t) for t in created)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("📁 Misma carpeta", callback_data=f"fbatch:same:{ref}"),
        InlineKeyboardButton("🗂 Carpeta distinta", callback_data=f"fbatch:diff:{ref}"),
    ]])
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"📦 Recibí {len(created)} archivos.\n¿Los guardo todos en la misma carpeta, o eliges una distinta para cada uno?",
        reply_markup=kb,
    )


@authorized_only
async def handle_tg_links(update, context, urls: list[str]):
    """Enlaces de mensajes de Telegram: se descargan con la cuenta conectada (userbot)."""
    import tg_links
    msg = update.effective_message
    manager = context.bot_data.get("userbot_manager")
    status = await msg.reply_text("🔎 Buscando el mensaje con tu cuenta…")
    created, errors = [], []
    for url in urls:
        try:
            for f in await tg_links.resolve(manager, url):
                created.append(await db.create_task(
                    kind="telegram", source_chat_id=f["chat_id"], source_message_id=f["message_id"],
                    filename=f["filename"], total_size=f["size"] or None, requested_by=msg.chat_id,
                ))
        except Exception as e:
            errors.append(f"• {esc(url)}: {esc(e)}")
    try:
        await status.delete()
    except Exception:
        pass
    if errors:
        await msg.reply_text("❌ No pude con estos enlaces:\n" + "\n".join(errors[:5]), parse_mode=ParseMode.HTML)
    await _ask_destination(context, msg.chat_id, created)


@authorized_only
async def file_batch_same(update, context):
    query = update.callback_query
    await query.answer()
    ref = query.data.split(":", 2)[2]
    auto = await try_auto(context, ref)
    if auto:
        await query.edit_message_text(auto_text(auto), parse_mode=ParseMode.HTML)
        return
    await query.edit_message_text("Elige la carpeta destino:", reply_markup=await dest_markup(ref))


@authorized_only
async def file_batch_diff(update, context):
    query = update.callback_query
    await query.answer()
    ref = query.data.split(":", 2)[2]
    task_ids = [int(x) for x in ref.split(",")]
    context.user_data["pending_diff_queue"] = {"remaining": task_ids[1:], "total": len(task_ids)}

    first_id = task_ids[0]
    task = await db.get_task(first_id)
    await query.edit_message_text(
        f"📄 Archivo 1/{len(task_ids)}: <b>{esc(task['filename'])}</b>\nElige la carpeta destino:",
        parse_mode=ParseMode.HTML,
        reply_markup=await dest_markup(str(first_id)),
    )


async def _continue_diff_queue(context, chat_id):
    queue_state = context.user_data.get("pending_diff_queue")
    if not queue_state:
        return
    remaining = queue_state["remaining"]
    total = queue_state["total"]
    if not remaining:
        context.user_data.pop("pending_diff_queue", None)
        return

    next_id = remaining.pop(0)
    task = await db.get_task(next_id)
    if not task:
        await _continue_diff_queue(context, chat_id)
        return

    idx = total - len(remaining)
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"📄 Archivo {idx}/{total}: <b>{esc(task['filename'])}</b>\nElige la carpeta destino:",
        parse_mode=ParseMode.HTML,
        reply_markup=await dest_markup(str(next_id)),
    )
    if not remaining:
        context.user_data.pop("pending_diff_queue", None)


@authorized_only
async def link_command(update, context):
    payload = get_command_payload(update)
    urls = extract_http_urls(payload)
    if not urls and payload.strip().startswith(("http://", "https://")):
        urls = [payload.strip()]

    if not urls:
        await update.effective_message.reply_text(
            "Uso: /link <url>\n\nPuedes poner varios enlaces, uno por línea, en el mismo mensaje."
        )
        return

    import tg_links
    tg = [u for u in urls if tg_links.is_tg_link(u)]
    if tg:
        await handle_tg_links(update, context, tg)
        urls = [u for u in urls if u not in tg]
    normal_urls = []
    for u in urls:
        if google_drive.is_drive_url(u):
            import handlers_gdrive
            await handlers_gdrive.handle_drive_link(update, context, u)
        elif ytdlp_downloader.is_ytdlp_url(u):
            import handlers_ytdlp as h_ytdl
            await h_ytdl.handle_ytdlp_url(update, context, u)
        else:
            normal_urls.append(u)

    if normal_urls:
        await handle_incoming_links(update, context, normal_urls)


@authorized_only
async def handle_incoming_links(update, context, urls: list[str]):
    msg = update.effective_message
    # yt-dlp sources are handled only by yt-dlp, never by aria2 / Real-Debrid / TorBox
    ytdlp_urls = [u for u in urls if ytdlp_downloader.is_ytdlp_url(u)]
    if ytdlp_urls:
        import handlers_ytdlp as h_ytdl
        for u in ytdlp_urls:
            await h_ytdl.handle_ytdlp_url(update, context, u)
        urls = [u for u in urls if u not in ytdlp_urls]
        if not urls:
            return
    probes = await asyncio.gather(*(probe_link(u) for u in urls))

    task_ids = []
    for url, (probed_name, probed_size) in zip(urls, probes):
        filename = probed_name or url.split("/")[-1].split("?")[0] or "archivo"
        tid = await db.create_task(
            kind="link", url=url, filename=filename, total_size=probed_size, requested_by=msg.chat_id,
        )
        task_ids.append(tid)
    ref = ",".join(str(t) for t in task_ids)

    plural = "1 enlace" if len(urls) == 1 else f"{len(urls)} enlaces"

    import handlers_settings as h_settings
    row = [InlineKeyboardButton("⚡ Aria2 (directo)", callback_data=f"method:aria2:{ref}")]
    if await h_settings.rd_is_enabled():
        row.append(InlineKeyboardButton("💳 Real-Debrid", callback_data=f"method:rd:{ref}"))
    if await h_settings.tb_is_enabled():
        row.append(InlineKeyboardButton("📦 TorBox", callback_data=f"method:tb:{ref}"))
    if len(row) > 1:
        await msg.reply_text(
            f"🔗 {plural} recibido(s).\n¿Con qué método quieres descargarlos?\n"
            "<i>Real-Debrid y TorBox sirven para nubes y webs que aria2 no soporta directamente.</i>",
            parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([row]))
    else:
        auto = await try_auto(context, ref)
        if auto:
            await msg.reply_text(auto_text(auto), parse_mode=ParseMode.HTML)
            return
        await msg.reply_text(f"🔗 {plural} recibido(s).\nElige la carpeta destino:", reply_markup=await dest_markup(ref))


async def apply_method(task_ids: list[int], method: str):
    if method not in ("rd", "tb"):
        return
    import handlers_settings as h_settings
    token = await h_settings.get_rd_token() if method == "rd" else await db.get_setting("tb_token")
    for task_id in task_ids:
        task = await db.get_task(task_id)
        if not task or ytdlp_downloader.is_ytdlp_url(task.get("url") or ""):
            continue  # yt-dlp links are never sent to debrid services
        if method == "tb":
            await db.update_task(task_id, kind="tb_link", client="torbox")
            continue
        if token:
            try:
                data = await real_debrid.unrestrict_link(token, task["url"])
                await db.update_task(
                    task_id, kind="link", url=data["download"],
                    filename=data.get("filename") or task["filename"],
                    total_size=data.get("filesize"), client="realdebrid",
                )
                continue
            except Exception:
                pass
        await db.update_task(task_id, kind="rd_link", client="realdebrid")


@authorized_only
async def choose_method(update, context):
    query = update.callback_query
    await query.answer()
    _, method, ref = query.data.split(":", 2)
    await apply_method([int(x) for x in ref.split(",")], method)
    await query.edit_message_text("Elige la carpeta destino:", reply_markup=await dest_markup(ref))


async def _hint_from_tasks(task_ids) -> str:
    for tid in task_ids:
        t = await db.get_task(tid)
        if t and t.get("filename"):
            return t["filename"]
    return ""


async def set_destination(context, task_ids: list[int], folder_key: str, relpath: str, extract: bool = False):
    relpath = await tmdb_helper.adjust_relpath(folder_key, relpath, await _hint_from_tasks(task_ids))
    _base, target_dir = filemanager.resolve_path(folder_key, relpath)
    target_dir.mkdir(parents=True, exist_ok=True)
    dest_dir = str(target_dir)
    dest_label = f"{folder_key}/{relpath}" if relpath else folder_key

    for tid in task_ids:
        task = await db.get_task(tid)
        if task:
            fields = {"dest_folder": dest_label, "dest_path": dest_dir, "status": "queued"}
            if extract:
                fields["extract_after"] = 1
            await db.update_task(tid, **fields)

    await try_start_next(context)
    return dest_dir, dest_label


@authorized_only
async def dl_root(update, context):
    query = update.callback_query
    await query.answer()
    ref = query.data.split(":", 1)[1]
    await query.edit_message_text("Elige la carpeta destino:", reply_markup=await dest_markup(ref))


@authorized_only
async def dl_nav(update, context):
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":", 4)
    ref, folder_key, token = parts[1], parts[2], parts[3]
    page = int(parts[4]) if len(parts) > 4 else 0
    resolved = keyboards.resolve_token(token)
    relpath = resolved[1] if resolved else ""
    title = f"📂 {folder_key}/{relpath}" if relpath else f"📂 {folder_key}"
    await query.edit_message_text(
        f"{title}\nElige la carpeta destino:",
        reply_markup=dest_nav_keyboard(ref, folder_key, relpath, page),
    )


@authorized_only
async def dl_mkdir_entry(update, context):
    query = update.callback_query
    await query.answer()
    _, ref, folder_key, token = query.data.split(":", 3)
    relpath = keyboards.resolve_token(token)[1]
    context.user_data["pending_dl_mkdir"] = {"ref": ref, "folder_key": folder_key, "relpath": relpath}
    await query.edit_message_text("➕ Envía el nombre de la nueva carpeta:")


@authorized_only
async def dl_rename_entry(update, context):
    query = update.callback_query
    await query.answer()
    ref = query.data.split(":", 1)[1]
    task = await db.get_task(int(ref)) if ref.isdigit() else None
    if not task:
        await query.edit_message_text(L("⚠️ Tarea no encontrada.", "⚠️ Task not found."))
        return
    context.user_data["pending_dl_rename"] = {"ref": ref}
    await query.edit_message_text(
        L(f"✏️ Nombre actual: <code>{esc(task['filename'])}</code>\nEnvía el nombre nuevo (la extensión se mantiene).",
          f"✏️ Current name: <code>{esc(task['filename'])}</code>\nSend the new name (the extension is kept)."),
        parse_mode=ParseMode.HTML)


async def handle_pending_text(update, context) -> bool:
    sa = context.user_data.get("pending_dl_sched_at")
    if sa:
        try:
            sched_dt = _parse_exact_time(update.effective_message.text)
        except ValueError:
            sched_dt = None
        if not sched_dt:
            await update.effective_message.reply_text(L("⚠️ Hora no válida. Prueba con 23:30 o 25/12 08:00.",
                                                         "⚠️ Invalid time. Try 23:30 or 25/12 08:00."))
            return True
        context.user_data.pop("pending_dl_sched_at", None)
        relpath = keyboards.resolve_token(sa["token"])[1]
        ids = [int(x) for x in sa["ref"].split(",") if x.strip().isdigit()]
        relpath = await tmdb_helper.adjust_relpath(sa["folder_key"], relpath, await _hint_from_tasks(ids))
        _b, target_dir = filemanager.resolve_path(sa["folder_key"], relpath)
        target_dir.mkdir(parents=True, exist_ok=True)
        label = f"{sa['folder_key']}/{relpath}" if relpath else sa["folder_key"]
        for tid in ids:
            await db.update_task(tid, dest_folder=label, dest_path=str(target_dir), status="scheduled",
                                 scheduled_for=sched_dt.isoformat())
        await update.effective_message.reply_text(
            L(f"⏰ Descarga programada para {sched_dt.strftime('%d/%m %H:%M')} → {label}",
              f"⏰ Download scheduled for {sched_dt.strftime('%d/%m %H:%M')} → {label}"))
        return True
    rn = context.user_data.pop("pending_dl_rename", None)
    if rn:
        task = await db.get_task(int(rn["ref"]))
        if task:
            new = filemanager.apply_new_name(task["filename"], update.effective_message.text)
            await db.update_task(task["id"], filename=new, name_locked=1)
            await update.effective_message.reply_text(
                L(f"✅ Se guardará como: {new}\nElige la carpeta destino:", f"✅ Will be saved as: {new}\nChoose the destination folder:"),
                reply_markup=await dest_markup(rn["ref"]))
        return True
    pending = context.user_data.get("pending_dl_mkdir")
    if not pending:
        return False

    text = update.effective_message.text.strip()
    folder_key = pending["folder_key"]
    relpath = pending["relpath"]
    ref = pending["ref"]

    try:
        filemanager.mkdir(folder_key, relpath, text)
        await update.effective_message.reply_text("✅ Carpeta creada.")
    except filemanager.PathError as e:
        await update.effective_message.reply_text(f"⚠️ {e}")
    except FileExistsError:
        await update.effective_message.reply_text("⚠️ Ya existe una carpeta con ese nombre.")
    except Exception as e:
        await update.effective_message.reply_text(f"⚠️ Error: {esc(e)}")
    finally:
        context.user_data.pop("pending_dl_mkdir", None)

    await update.effective_message.reply_text(
        "Elige la carpeta destino:",
        reply_markup=dest_nav_keyboard(ref, folder_key, relpath),
    )
    return True


@authorized_only
async def dl_save(update, context):
    query = update.callback_query
    await query.answer()
    _, ref, folder_key, token = query.data.split(":", 3)
    relpath = keyboards.resolve_token(token)[1]

    if ref.startswith("T"):
        import handlers_realdebrid as h_rd_
        hint = (h_rd_.rd_torrent_states.get(ref[1:]) or {}).get("torrent_name", "")
    else:
        hint = await _hint_from_tasks([int(x) for x in ref.split(",")])
    relpath = await tmdb_helper.adjust_relpath(folder_key, relpath, hint)

    _base, target_dir = filemanager.resolve_path(folder_key, relpath)
    target_dir.mkdir(parents=True, exist_ok=True)
    dest_dir = str(target_dir)
    dest_label = f"{folder_key}/{relpath}" if relpath else folder_key

    if ref.startswith("T"):
        import handlers_realdebrid as h_rd
        await h_rd.confirm_destination(context, query, ref[1:], dest_dir, dest_label)
        return

    task_ids = [int(x) for x in ref.split(",")]
    tasks = [t for t in [await db.get_task(tid) for tid in task_ids] if t]
    if not tasks:
        await query.edit_message_text("⚠️ Tarea(s) no encontrada(s) (puede que el bot se haya reiniciado).")
        return

    archive_tasks = [t for t in tasks if archive_utils.is_archive(t["filename"])]
    if archive_tasks:
        names = "\n".join(f"• {html.escape(t['filename'])}" for t in archive_tasks)
        plural = len(archive_tasks) > 1
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Sí, descomprimir", callback_data=f"dlextract:yes:{ref}:{folder_key}:{token}"),
            InlineKeyboardButton("❌ No, dejar así", callback_data=f"dlextract:no:{ref}:{folder_key}:{token}"),
        ]])
        await query.edit_message_text(
            f"📦 Detecté {'estos archivos comprimidos' if plural else 'un archivo comprimido'}:\n{names}\n\n"
            f"¿Quieres descomprimirlo{'s' if plural else ''} automáticamente al terminar la descarga?",
            parse_mode=ParseMode.HTML,
            reply_markup=kb,
        )
        return

    await _finalize_destination(query, context, tasks, dest_dir, dest_label)


@authorized_only
async def dl_extract_choice(update, context):
    query = update.callback_query
    await query.answer()
    _, choice, ref, folder_key, token = query.data.split(":", 4)
    relpath = keyboards.resolve_token(token)[1]
    relpath = await tmdb_helper.adjust_relpath(
        folder_key, relpath, await _hint_from_tasks([int(x) for x in ref.split(",")]))

    _base, target_dir = filemanager.resolve_path(folder_key, relpath)
    target_dir.mkdir(parents=True, exist_ok=True)
    dest_dir = str(target_dir)
    dest_label = f"{folder_key}/{relpath}" if relpath else folder_key

    task_ids = [int(x) for x in ref.split(",")]
    tasks = [t for t in [await db.get_task(tid) for tid in task_ids] if t]
    if not tasks:
        await query.edit_message_text("⚠️ Tarea(s) no encontrada(s).")
        return

    if choice == "yes":
        for t in tasks:
            if archive_utils.is_archive(t["filename"]):
                await db.update_task(t["id"], extract_after=1)

    await _finalize_destination(query, context, tasks, dest_dir, dest_label)


@authorized_only
async def dl_sched_menu(update, context):
    query = update.callback_query
    await query.answer()
    _, ref, folder_key, token = query.data.split(":", 3)
    kb = [
        [InlineKeyboardButton("⏱️ En 1 hora", callback_data=f"dlschedset:1h:{ref}:{folder_key}:{token}")],
        [InlineKeyboardButton("⏱️ En 2 horas", callback_data=f"dlschedset:2h:{ref}:{folder_key}:{token}")],
        [InlineKeyboardButton("⏱️ En 4 horas", callback_data=f"dlschedset:4h:{ref}:{folder_key}:{token}")],
        [InlineKeyboardButton("🌙 Modo Nocturno (02:00 AM)", callback_data=f"dlschedset:night:{ref}:{folder_key}:{token}")],
        [InlineKeyboardButton(L("🗓️ Hora exacta", "🗓️ Exact time"), callback_data=f"dlschedat:{ref}:{folder_key}:{token}")],
        [InlineKeyboardButton("▶️ Iniciar ahora mismo", callback_data=f"dlschedset:now:{ref}:{folder_key}:{token}")],
        [InlineKeyboardButton("⬅️ Volver", callback_data=f"dlnav:{ref}:{folder_key}:{token}")],
    ]
    await query.edit_message_text(
        "⏰ <b>Programación de descarga</b>\n\n"
        "Selecciona cuándo quieres que comience la descarga en el NAS:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(kb),
    )


@authorized_only
async def dl_sched_at(update, context):
    query = update.callback_query
    await query.answer()
    _, ref, folder_key, token = query.data.split(":", 3)
    context.user_data["pending_dl_sched_at"] = {"ref": ref, "folder_key": folder_key, "token": token}
    await query.edit_message_text(L(
        "🗓️ Envía la hora de inicio: <code>HH:MM</code> (hoy o mañana) o <code>DD/MM HH:MM</code>.",
        "🗓️ Send the start time: <code>HH:MM</code> (today or tomorrow) or <code>DD/MM HH:MM</code>."),
        parse_mode=ParseMode.HTML)


def _parse_exact_time(text: str):
    import re as _re
    now = datetime.now(LOCAL_TZ)
    m = _re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", text)
    if m:
        dt = now.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
        return dt + timedelta(days=1) if dt <= now else dt
    m = _re.fullmatch(r"\s*(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})\s*", text)
    if m:
        dt = now.replace(month=int(m.group(2)), day=int(m.group(1)), hour=int(m.group(3)), minute=int(m.group(4)),
                         second=0, microsecond=0)
        return dt if dt > now else None
    return None


@authorized_only
async def dl_sched_apply(update, context):
    query = update.callback_query
    await query.answer()
    _, option, ref, folder_key, token = query.data.split(":", 4)
    relpath = keyboards.resolve_token(token)[1]
    if ref.startswith("T"):
        import handlers_realdebrid as h_rd_
        hint = (h_rd_.rd_torrent_states.get(ref[1:]) or {}).get("torrent_name", "")
    else:
        hint = await _hint_from_tasks([int(x) for x in ref.split(",")])
    relpath = await tmdb_helper.adjust_relpath(folder_key, relpath, hint)
    _base, target_dir = filemanager.resolve_path(folder_key, relpath)
    target_dir.mkdir(parents=True, exist_ok=True)
    dest_dir = str(target_dir)
    dest_label = f"{folder_key}/{relpath}" if relpath else folder_key

    task_ids = [int(x) for x in ref.split(",")]
    tasks = [t for t in [await db.get_task(tid) for tid in task_ids] if t]
    if not tasks:
        await query.edit_message_text("⚠️ Tarea(s) no encontrada(s).")
        return

    now = datetime.now(LOCAL_TZ)
    sched_dt = None
    if option == "1h":
        sched_dt = now + timedelta(hours=1)
    elif option == "2h":
        sched_dt = now + timedelta(hours=2)
    elif option == "4h":
        sched_dt = now + timedelta(hours=4)
    elif option == "night":
        sched_dt = now.replace(hour=2, minute=0, second=0, microsecond=0)
        if sched_dt <= now:
            sched_dt += timedelta(days=1)
    elif option == "now":
        await _finalize_destination(query, context, tasks, dest_dir, dest_label)
        return

    sched_iso = sched_dt.isoformat()
    for t in tasks:
        await db.update_task(t["id"], dest_folder=dest_label, dest_path=dest_dir, status="scheduled", scheduled_for=sched_iso)

    sched_display = sched_dt.strftime("%d/%m %H:%M")
    names = ", ".join(t["filename"] for t in tasks)
    await query.edit_message_text(
        f"⏰ <b>Descarga programada con éxito</b>\n\n"
        f"• Contenido: <code>{esc(names)}</code>\n"
        f"• Inicio previsto: <code>{esc(sched_display)}</code>\n"
        f"• Destino: <code>{esc(dest_label)}</code>\n\n"
        "El bot iniciará la descarga automáticamente a la hora indicada.",
        parse_mode=ParseMode.HTML,
    )


async def _finalize_destination(query, context, tasks, dest_dir, dest_label):
    folder_base = dest_label.split("/")[0]
    total_size = sum(t.get("total_size") or 0 for t in tasks)

    ok, err_msg = filemanager.check_disk_space(folder_base, total_size)
    if not ok:
        await query.edit_message_text(err_msg, parse_mode=ParseMode.HTML)
        return

    for t in tasks:
        await db.update_task(t["id"], dest_folder=dest_label, dest_path=dest_dir, status="queued")

    if len(tasks) == 1:
        t = await db.get_task(tasks[0]["id"])
        extract_tag = " 📦" if t.get("extract_after") else ""
        await query.edit_message_text(
            f"🕓 <b>{esc(t['filename'])}</b>{extract_tag}\nEn cola para descargar a <code>{esc(dest_label)}</code>...",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[_cancel_button(t["id"])]]),
        )
        await db.update_task(
            t["id"],
            progress_chat_id=query.message.chat_id,
            progress_message_id=query.message.message_id,
        )
        await _continue_diff_queue(context, query.message.chat_id)
    else:
        batch_id = uuid.uuid4().hex[:12]
        for t in tasks:
            await db.update_task(t["id"], batch_id=batch_id)

        text, markup = await _render_batch_message(context, batch_id, dest_label)
        sent_msg = await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
        await db.create_batch(batch_id, sent_msg.chat_id, sent_msg.message_id)

    await try_start_next(context)


DEFAULT_MAX_PARALLEL = 1
ARIA2_KINDS = ("link", "rd_link", "tb_link")


def _kind_group(kind: str) -> str:
    if kind == "telegram":
        return "telegram"
    if kind == "gdrive":
        return "gdrive"
    if kind == "extract":
        return "extract"
    if kind == "upload":
        return "upload"
    return "aria2"


def _kinds_for_group(group: str) -> tuple:
    if group == "telegram":
        return ("telegram",)
    if group == "gdrive":
        return ("gdrive",)
    if group == "extract":
        return ("extract",)
    if group == "upload":
        return ("upload",)
    return ARIA2_KINDS


async def get_active_count(group: str) -> int:
    downloading = await db.get_tasks_by_status("downloading")
    kinds = _kinds_for_group(group)
    return len([t for t in downloading if t["kind"] in kinds])


async def get_max_parallel(group: str) -> int:
    if group == "extract":
        return 1
    key = {"telegram": "max_parallel_telegram", "gdrive": "max_parallel_gdrive"}.get(group, "max_parallel_aria2")
    value = await db.get_setting(key, str(DEFAULT_MAX_PARALLEL))
    try:
        return max(1, min(4, int(value)))
    except (TypeError, ValueError):
        return DEFAULT_MAX_PARALLEL


async def set_max_parallel(group: str, value: int):
    if group == "extract":
        return
    key = {"telegram": "max_parallel_telegram", "gdrive": "max_parallel_gdrive"}.get(group, "max_parallel_aria2")
    await db.set_setting(key, str(max(1, min(4, int(value)))))


async def get_max_priority() -> int:
    tasks = (
        await db.get_tasks_by_status("queued")
        + await db.get_tasks_by_status("paused")
        + await db.get_tasks_by_status("downloading")
    )
    if not tasks:
        return 0
    return max((t.get("priority") or 0) for t in tasks)


async def queue_position(task_id: int) -> int:
    queued = await db.get_tasks_by_status("queued")
    ordered = sorted(queued, key=lambda t: (-(t.get("priority") or 0), t["id"]))
    for idx, t in enumerate(ordered):
        if t["id"] == task_id:
            return idx
    return 0


_space_blocked: set = set()
_space_warned: set = set()


async def _space_guard(context, task) -> bool:
    import disk
    size = task.get("total_size") or 0
    if not size or not task.get("dest_path"):
        return False
    res = await disk.check_fit(task["dest_path"], size)
    if res["ok"] or res["guard"] == "off":
        _space_blocked.discard(task["id"])
        return False
    text = disk.no_space_text(esc(task["filename"]), res)
    if res["guard"] == "warn":
        if task["id"] not in _space_warned:
            _space_warned.add(task["id"])
            await _safe_edit(context, task, "⚠️ " + text + L("\nSe descargará igualmente.", "\nIt will download anyway."))
        return False
    if res["guard"] == "reject":
        await _mark_finished(task["id"], "error", error="No space")
        await _safe_edit(context, task, "❌ " + text)
        return True
    if task["id"] not in _space_warned:
        _space_warned.add(task["id"])
        await _safe_edit(context, task, "⏸️ " + text + L("\nQueda en cola hasta que haya espacio.", "\nIt stays queued until there is space."))
    return True


async def release_space_blocks():
    import disk
    for tid in list(_space_blocked):
        task = await db.get_task(tid)
        if not task or task["status"] != "queued":
            _space_blocked.discard(tid)
            continue
        res = await disk.check_fit(task.get("dest_path") or "", task.get("total_size") or 0)
        if res["ok"] or res["guard"] != "pause":
            _space_blocked.discard(tid)


async def try_start_next(context):
    await release_space_blocks()
    for group in ("telegram", "aria2", "gdrive", "extract"):
        max_parallel = await get_max_parallel(group)
        kinds = _kinds_for_group(group)
        while await get_active_count(group) < max_parallel:
            paused = [t for t in await db.get_tasks_by_status("paused") if t.get("error") == "auto_paused"]
            candidates = await db.get_tasks_by_status("queued") + paused
            candidates = [t for t in candidates if t["kind"] in kinds]
            if not candidates:
                break
            candidates = [t for t in candidates if t["id"] not in _space_blocked]
            if not candidates:
                break
            candidates.sort(key=lambda t: (-(t.get("priority") or 0), t["id"]))
            task = candidates[0]
            if task["status"] != "paused" and await _space_guard(context, task):
                _space_blocked.add(task["id"])
                continue
            try:
                if task["status"] == "paused":
                    await _resume_download(context, task)
                else:
                    await _start_download(context, task)
            except Exception as e:
                await _mark_finished(task["id"], "error", error=str(e))
                await _safe_edit(context, task, f"❌ Error inesperado al procesar <b>{esc(task['filename'])}</b>: {esc(e)}")


async def queue_worker(context):
    try:
        ready_tasks = await db.get_scheduled_tasks_ready(_now_iso())
        for t in ready_tasks:
            await db.update_task(t["id"], status="queued", scheduled_for=None)
            notify_chat = t.get("requested_by") or config.OWNER_ID
            try:
                await context.bot.send_message(
                    chat_id=notify_chat,
                    text=f"⏰ <b>Descarga programada iniciada</b>: <code>{esc(t['filename'])}</code>\nDestino: <code>{esc(t['dest_folder'])}</code>",
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass
    except Exception as e:
        pass
    await try_start_next(context)


async def prioritize_task(context, task_id: int) -> tuple[bool, str]:
    task = await db.get_task(task_id)
    if not task:
        return False, "Tarea no encontrada."
    if task["kind"] not in ("link", "rd_link", "tb_link"):
        return False, "Solo se puede priorizar descargas de aria2."
    if task["status"] == "downloading":
        return True, "Ya está descargando."
    if task["status"] not in ("queued", "paused"):
        return False, "Esa tarea ya no está activa."

    active = await db.get_tasks_by_status("downloading")
    for t in active:
        if t["kind"] == "link" and t["gid"]:
            try:
                downloader.pause(t["gid"])
            except Exception:
                continue
            await db.update_task(t["id"], status="paused", error="auto_paused")
            await _safe_edit(
                context, t,
                f"⏸️ <b>{esc(t['filename'])}</b> pausada temporalmente (otra descarga tiene prioridad).",
                markup=_paused_markup(t["id"]),
            )

    top_priority = await get_max_priority() + 1
    await db.update_task(task_id, priority=top_priority)
    await _refresh_batch_message(context, task.get("batch_id"))
    await try_start_next(context)
    return True, "Prioridad asignada."


async def move_task(context, task_id: int, direction: str) -> tuple[bool, str]:
    task = await db.get_task(task_id)
    if not task:
        return False, "Tarea no encontrada."
    if task["status"] != "queued":
        return False, "Solo se puede reordenar una tarea que esté en cola."

    kinds = _kinds_for_group(_kind_group(task["kind"]))
    queued = [t for t in await db.get_tasks_by_status("queued") if t["kind"] in kinds]
    ordered = sorted(queued, key=lambda t: (-(t.get("priority") or 0), t["id"]))

    idx = next((i for i, t in enumerate(ordered) if t["id"] == task_id), None)
    if idx is None:
        return False, "Tarea no encontrada en la cola."

    if direction == "up":
        if idx == 0:
            return False, "Ya es la primera de la cola."
        swap_idx = idx - 1
    else:
        if idx == len(ordered) - 1:
            return False, "Ya es la última de la cola."
        swap_idx = idx + 1

    ordered[idx], ordered[swap_idx] = ordered[swap_idx], ordered[idx]
    n = len(ordered)
    for i, t in enumerate(ordered):
        await db.update_task(t["id"], priority=n - i)

    batch_ids = {t.get("batch_id") for t in ordered if t.get("batch_id")}
    for bid in batch_ids:
        await _refresh_batch_message(context, bid)

    return True, "Reordenado."


async def enqueue_link_task(context, url: str, filename: str, dest_folder: str, dest_path: str,
                             chat_id: int | None = None, kind: str = "link", requested_by: int | None = None,
                             client: str | None = None):
    req_by = requested_by if requested_by is not None else chat_id
    fields = dict(kind=kind, url=url, filename=filename, dest_folder=dest_folder, dest_path=dest_path,
                  status="queued", requested_by=req_by)
    if client:
        fields["client"] = client
    task_id = await db.create_task(**fields)
    if chat_id:
        try:
            sent = await context.bot.send_message(
                chat_id=chat_id,
                text=f"🕓 <b>{esc(filename)}</b>\nEn cola para descargar a <code>{esc(dest_folder)}</code>...",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[_cancel_button(task_id)]]),
            )
            await db.update_task(task_id, progress_chat_id=sent.chat_id, progress_message_id=sent.message_id)
        except Exception:
            pass
    return task_id


def _paused_markup(task_id):
    return InlineKeyboardMarkup([[_cancel_button(task_id)]])


async def _resume_download(context, task):
    task_id = task["id"]
    if task.get("error") == "auto_paused":
        await db.update_task(task_id, error=None)
    if task["kind"] == "link" and task["gid"]:
        try:
            downloader.resume(task["gid"])
        except Exception as e:
            await _mark_finished(task_id, "error", error=str(e))
            await _safe_edit(context, task, f"❌ Error al reanudar <b>{esc(task['filename'])}</b>: {esc(e)}")
            await try_start_next(context)
            return
        await db.update_task(task_id, status="downloading")
        await _safe_edit(
            context, task,
            f"⬇️ Descargando <b>{esc(task['filename'])}</b> con aria2 a <code>{esc(task['dest_folder'])}</code>...",
            markup=InlineKeyboardMarkup([[_cancel_button(task_id)]]),
        )
    else:
        await db.update_task(task_id, status="queued")
        await try_start_next(context)


async def pause_task_by_id(context, task_id: int) -> tuple[bool, str]:
    task = await db.get_task(task_id)
    if not task:
        return False, "Tarea no encontrada."
    if task["status"] == "paused":
        return True, "Ya estaba pausada."
    if task["status"] == "queued":
        await db.update_task(task_id, status="paused")
        await _safe_edit(context, task, f"⏸️ <b>{esc(task['filename'])}</b> pausada.", markup=_paused_markup(task_id))
        if task.get("batch_id"):
            await _refresh_batch_message(context, task["batch_id"])
        return True, "Pausada."
    if task["status"] == "downloading" and task["kind"] in ARIA2_KINDS and task.get("gid"):
        try:
            downloader.pause(task["gid"])
        except Exception as e:
            return False, f"No se pudo pausar: {e}"
        await db.update_task(task_id, status="paused")
        await _safe_edit(context, task, f"⏸️ <b>{esc(task['filename'])}</b> pausada.", markup=_paused_markup(task_id))
        await try_start_next(context)
        return True, "Pausada."
    return False, "Esta descarga no admite pausa (solo Aria2 y tareas en cola)."


async def resume_task_by_id(context, task_id: int) -> tuple[bool, str]:
    task = await db.get_task(task_id)
    if not task:
        return False, "Tarea no encontrada."
    if task["status"] != "paused":
        return False, "Esta tarea no está pausada."
    await _resume_download(context, task)
    return True, "Reanudada."


async def _start_download(context, task):
    task_id = task["id"]
    dest_dir = task["dest_path"]

    if task["kind"] == "extract":
        await db.update_task(task_id, status="downloading")
        await _mark_started(task_id)
        if task.get("batch_id"):
            await _refresh_batch_message(context, task["batch_id"])
        else:
            await _safe_edit(
                context, task,
                f"📦 Descomprimiendo <b>{esc(task['filename'])}</b> {L('en', 'in')} `{task['dest_folder']}`...",
                markup=InlineKeyboardMarkup([[_cancel_button(task_id)]]),
            )
        active = context.bot_data.setdefault("active_extract_tasks", {})
        active[task_id] = asyncio.create_task(_process_extract_task(context, task_id))
        return

    if task["kind"] == "tb_link":
        token = await db.get_setting("tb_token")
        if not token:
            await _mark_finished(task_id, "error", error="Falta el token de TorBox")
            await _safe_edit(context, task, "⚠️ No hay token de TorBox configurado.")
            await try_start_next(context)
            return
        await db.update_task(task_id, status="downloading")
        await _mark_started(task_id)
        await _safe_edit(context, task, f"📦 TorBox está preparando <b>{esc(task['filename'])}</b>…",
                         markup=InlineKeyboardMarkup([[_cancel_button(task_id)]]))
        active = context.bot_data.setdefault("active_tb_tasks", {})
        active[task_id] = asyncio.create_task(_prepare_tb_link(context, task_id, token))
        return

    if task["kind"] == "rd_link":
        import handlers_settings as h_settings
        token = await h_settings.get_rd_token()
        if not token:
            await _mark_finished(task_id, "error", error="Falta el token de Real-Debrid")
            await _safe_edit(context, task, "⚠️ No hay token de Real-Debrid configurado.")
            await try_start_next(context)
            return
        try:
            data = await real_debrid.unrestrict_link(token, task["url"])
        except Exception as e:
            await _mark_finished(task_id, "error", error=str(e))
            await _safe_edit(context, task, f"❌ Error al resolver el enlace con Real-Debrid: {esc(e)}")
            await try_start_next(context)
            return
        keep = task["filename"] if task.get("name_locked") else (data.get("filename") or task["filename"])
        await db.update_task(task_id, url=data["download"], filename=keep,
                             kind="link", client="realdebrid")
        task = await db.get_task(task_id)

    if task["kind"] == "link":
        connections = int(await db.get_setting("aria2_workers", "16"))
        try:
            gid = downloader.add_uri(task["url"], dest_dir, task["filename"], connections=connections)
        except Exception as e:
            await _mark_finished(task_id, "error", error=str(e))
            await _safe_edit(context, task, f"❌ Error al añadir la descarga a aria2: {esc(e)}")
            await try_start_next(context)
            return
        await db.update_task(task_id, status="downloading", gid=gid)
        await _mark_started(task_id)
        if task.get("batch_id"):
            await _refresh_batch_message(context, task["batch_id"])
        else:
            await _safe_edit(
                context, task,
                f"⬇️ Descargando <b>{esc(task['filename'])}</b> {L('con aria2 a', 'with aria2 to')} `{task['dest_folder']}`...",
                markup=InlineKeyboardMarkup([[_cancel_button(task_id)]]),
            )
        return

    if task["kind"] == "gdrive":
        if not await google_drive.is_connected():
            await _mark_finished(task_id, "error", error="google_drive_disconnected")
            await _safe_edit(context, task, "⚠️ Google Drive se desconectó. Ve a Ajustes → Google Drive para reconectarlo.")
            await try_start_next(context)
            return
        await db.update_task(task_id, status="downloading")
        await _mark_started(task_id)
        if task.get("batch_id"):
            await _refresh_batch_message(context, task["batch_id"])
        else:
            await _safe_edit(
                context, task,
                f"⬇️ Descargando <b>{esc(task['filename'])}</b> {L('desde Google Drive a', 'from Google Drive to')} `{task['dest_folder']}`...",
                markup=InlineKeyboardMarkup([[_cancel_button(task_id)]]),
            )
        active = context.bot_data.setdefault("active_gdrive_tasks", {})
        active[task_id] = asyncio.create_task(_download_gdrive_task(context, task_id, dest_dir))
        return

    manager = context.bot_data.get("userbot_manager")
    if manager is None or not await manager.is_connected():
        await _mark_finished(task_id, "error", error="userbot_disconnected")
        await _safe_edit(context, task, "⚠️ El userbot no está conectado. Ve a 🤖 Userbot en el menú principal para conectarlo.")
        await try_start_next(context)
        return

    await db.update_task(task_id, status="downloading")
    await _mark_started(task_id)
    if task.get("batch_id"):
        await _refresh_batch_message(context, task["batch_id"])
    else:
        await _safe_edit(
            context, task,
            f"⬇️ Descargando <b>{esc(task['filename'])}</b> {L('a', 'to')} `{task['dest_folder']}`...",
            markup=InlineKeyboardMarkup([[_cancel_button(task_id)]]),
        )

    active = context.bot_data.setdefault("active_telegram_tasks", {})
    active[task_id] = asyncio.create_task(_download_telegram_task(context, task_id, dest_dir))


async def _active_progress_html(context, task) -> str:
    filename = html.escape(task["filename"])

    if task["kind"] == "extract":
        progress_state = context.bot_data.get("extract_progress", {})
        prog = progress_state.get(task["id"])
        if not prog or not prog.get("total"):
            return f"📦 Descomprimiendo ahora: <b>{filename}</b>..."
        current, total, speed = prog["bytes"], prog["total"], prog["speed"]
        pct = (current / total * 100) if total else 0
        mb_c, mb_t = current / (1024 * 1024), total / (1024 * 1024)
        speed_mb = speed / (1024 * 1024)
        eta = f"{int((total - current) / speed)}s" if speed > 0 else "?"
        return (
            f"📦 Descomprimiendo ahora: <b>{filename}</b>\n"
            f"{pct:.1f}% ({mb_c:.1f}MB / {mb_t:.1f}MB)\n"
            f"🚀 {speed_mb:.2f} MB/s — ETA {eta}"
        )

    if task["kind"] == "upload":
        progress_state = context.bot_data.get("upload_progress", {})
        prog = progress_state.get(task["id"])
        if not prog or not prog.get("total"):
            return f"📤 Subiendo a Telegram: <b>{filename}</b>..."
        current, total, speed = prog["bytes"], prog["total"], prog["speed"]
        pct = (current / total * 100) if total else 0
        mb_c, mb_t = current / (1024 * 1024), total / (1024 * 1024)
        speed_mb = speed / (1024 * 1024)
        eta = f"{int((total - current) / speed)}s" if speed > 0 else "?"
        return (
            f"📤 Subiendo a Telegram: <b>{filename}</b>\n"
            f"{pct:.1f}% ({mb_c:.1f}MB / {mb_t:.1f}MB)\n"
            f"🚀 {speed_mb:.2f} MB/s — ETA {eta}"
        )

    if task["kind"] == "telegram":
        progress_state = context.bot_data.get("telegram_progress", {})
        prog = progress_state.get(task["id"])
        if not prog or not prog.get("total"):
            return f"⬇️ Descargando ahora: <b>{filename}</b>..."
        current, total, speed = prog["bytes"], prog["total"], prog["speed"]
        pct = (current / total * 100) if total else 0
        mb_c, mb_t = current / (1024 * 1024), total / (1024 * 1024)
        speed_mb = speed / (1024 * 1024)
        eta = f"{int((total - current) / speed)}s" if speed > 0 else "?"
        return (
            f"⬇️ Descargando ahora: <b>{filename}</b>\n"
            f"{pct:.1f}% ({mb_c:.1f}MB / {mb_t:.1f}MB)\n"
            f"🚀 {speed_mb:.2f} MB/s — ETA {eta}"
        )

    if not task["gid"]:
        return f"⬇️ Descargando ahora: <b>{filename}</b>..."
    try:
        dl = downloader.get_download(task["gid"])
        return (
            f"⬇️ Descargando ahora: <b>{filename}</b>\n"
            f"{dl.progress:.1f}% — 🚀 {dl.download_speed_string()} — ETA {dl.eta_string()}"
        )
    except Exception:
        return f"⬇️ Descargando ahora: <b>{filename}</b>..."


async def _render_batch_message(context, batch_id: str, dest_label: str) -> tuple[str, InlineKeyboardMarkup | None]:
    all_tasks = await db.get_tasks_by_batch(batch_id)
    queued = [t for t in all_tasks if t["status"] == "queued"]
    queued.sort(key=lambda t: (-(t.get("priority") or 0), t["id"]))
    active = next((t for t in all_tasks if t["status"] == "downloading"), None)

    if not queued and not active:
        return "✅ Todas las tareas de este lote ya se han procesado.", None

    blocks = [
        r_h(f"Lote de {len(all_tasks)} tarea(s)", 3, "📦"),
        r_p(f"Destino: <code>{html.escape(dest_label)}</code>"),
    ]
    markup = None
    if active:
        progress = await _active_progress_html(context, active)
        blocks.append(r_p(progress.replace("\n", "<br/>")))
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data=f"dlcancel:{active['id']}")]])
    if queued:
        items = [html.escape(t["filename"]) for t in queued]
        blocks.append(r_details(f"🕓 {len(queued)} en cola", r_ul(items, ordered=True)))

    return rich(*blocks), markup


async def _refresh_batch_message(context, batch_id: str | None):
    if not batch_id:
        return
    batch = await db.get_batch(batch_id)
    if not batch:
        return
    all_tasks = await db.get_tasks_by_batch(batch_id)
    if not all_tasks:
        return
    dest_label = all_tasks[0]["dest_folder"] or ""
    text, markup = await _render_batch_message(context, batch_id, dest_label)
    try:
        await context.bot.edit_message_text(
            chat_id=batch["chat_id"],
            message_id=batch["message_id"],
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=markup,
        )
    except Exception:
        pass


async def _safe_edit(context, task, text, markup=None):
    if task.get("progress_chat_id") and task.get("progress_message_id"):
        try:
            await context.bot.edit_message_text(
                chat_id=task["progress_chat_id"],
                message_id=task["progress_message_id"],
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
            return
        except BadRequest as e:
            msg = str(e).lower()
            if "message is not modified" in msg:
                return
            if "can't parse entities" in msg or "parse entities" in msg:
                try:
                    await context.bot.edit_message_text(
                        chat_id=task["progress_chat_id"],
                        message_id=task["progress_message_id"],
                        text=text,
                        parse_mode=None,
                        reply_markup=markup,
                    )
                    return
                except Exception:
                    pass
        except Exception:
            pass

    notify_chat_id = task.get("requested_by") or config.OWNER_ID
    try:
        sent = await context.bot.send_message(
            chat_id=notify_chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=markup,
        )
        await db.update_task(task["id"], progress_chat_id=sent.chat_id, progress_message_id=sent.message_id)
    except BadRequest as e:
        if "can't parse entities" in str(e).lower() or "parse entities" in str(e).lower():
            try:
                sent = await context.bot.send_message(
                    chat_id=notify_chat_id, text=text, parse_mode=None, reply_markup=markup,
                )
                await db.update_task(task["id"], progress_chat_id=sent.chat_id, progress_message_id=sent.message_id)
            except Exception:
                pass
    except Exception:
        pass


async def _download_telegram_task(context, task_id, dest_dir):
    manager = context.bot_data.get("userbot_manager")
    task = await db.get_task(task_id)
    if manager is None:
        await _mark_finished(task_id, "error", error="userbot_manager no disponible")
        await _safe_edit(context, task, "⚠️ El userbot no está disponible ahora mismo. Inténtalo de nuevo en unos segundos.")
        await try_start_next(context)
        return
    dest_path = str(Path(dest_dir) / task["filename"])
    progress_state = context.bot_data.setdefault("telegram_progress", {})

    def sync_progress(current, total):
        prog = progress_state.get(task_id, {})
        prog["bytes"] = max(current, prog.get("bytes", 0))
        prog["total"] = total
        progress_state[task_id] = prog

    try:
        try:
            await manager.download_message_media_fast(
                task["source_chat_id"],
                task["source_message_id"],
                dest_path,
                progress_callback=sync_progress,
            )
        except Exception:
            progress_state.pop(task_id, None)
            await manager.download_message_media(
                task["source_chat_id"],
                task["source_message_id"],
                dest_path,
                progress_callback=sync_progress,
            )
        await _mark_finished(task_id, "done")
        asyncio.create_task(_finalize_done(context, task_id))
    except asyncio.CancelledError:
        Path(dest_path).unlink(missing_ok=True)
        await _mark_finished(task_id, "cancelled")
        if task.get("batch_id"):
            await _refresh_batch_message(context, task["batch_id"])
        else:
            await _safe_edit(context, task, f"🚫 Descarga de <b>{esc(task['filename'])}</b> cancelada.")
    except Exception as e:
        await _mark_finished(task_id, "error", error=str(e))
        if task.get("batch_id"):
            await _refresh_batch_message(context, task["batch_id"])
        else:
            await _safe_edit(context, task, f"❌ Error al descargar <b>{esc(task['filename'])}</b>: {esc(e)}")
    finally:
        active = context.bot_data.get("active_telegram_tasks", {})
        active.pop(task_id, None)
        progress_state.pop(task_id, None)
        await try_start_next(context)


TB_LINK_TIMEOUT = 3 * 3600


async def _prepare_tb_link(context, task_id: int, token: str):
    """TorBox fetches the link into its cloud; when ready, hands the direct URL to aria2."""
    import torbox
    task = await db.get_task(task_id)
    web_id = None
    try:
        created = await torbox.create_webdownload(token, task["url"])
        web_id = created["id"]
        waited, last_pct = 0, -1
        while True:
            item = await torbox.get_webdownload(token, web_id)
            if item is None:
                raise torbox.TorBoxError("TorBox no encuentra la descarga")
            state = str(item.get("download_state") or "").lower()
            if item.get("download_finished") or state in ("completed", "cached", "uploading"):
                break
            if "error" in state or "fail" in state:
                raise torbox.TorBoxError(f"TorBox: {state}")
            pct = int(float(item.get("progress") or 0) * 100)
            if pct != last_pct:
                last_pct = pct
                await _safe_edit(context, task, f"📦 TorBox descarga <b>{esc(task['filename'])}</b> a su nube… {pct}%",
                                 markup=InlineKeyboardMarkup([[_cancel_button(task_id)]]))
            await asyncio.sleep(5)
            waited += 5
            if waited > TB_LINK_TIMEOUT:
                raise torbox.TorBoxError("TorBox tardó demasiado en preparar el enlace")
        files = item.get("files") or []
        best = max(files, key=lambda f: f.get("size") or 0) if files else {}
        url = await torbox.request_webdownload(token, web_id, int(best.get("id") or 0))
        name = (best.get("short_name") or best.get("name") or item.get("name") or task["filename"]).split("/")[-1]
        if task.get("name_locked"):
            name = task["filename"]
        await db.update_task(task_id, kind="link", url=url, filename=name or task["filename"],
                             total_size=best.get("size") or item.get("size") or task.get("total_size"),
                             client="torbox", status="queued")
        context.bot_data.get("active_tb_tasks", {}).pop(task_id, None)
        await try_start_next(context)
    except asyncio.CancelledError:
        if web_id:
            try:
                await torbox.delete_webdownload(token, web_id)
            except Exception:
                pass
        await _mark_finished(task_id, "cancelled")
        await _safe_edit(context, task, f"🚫 Descarga de <b>{esc(task['filename'])}</b> cancelada.")
    except Exception as e:
        await _mark_finished(task_id, "error", error=str(e))
        await _safe_edit(context, task, f"❌ Error con TorBox: {esc(e)}")
        await try_start_next(context)
    finally:
        context.bot_data.get("active_tb_tasks", {}).pop(task_id, None)


async def _download_gdrive_task(context, task_id, dest_dir):
    task = await db.get_task(task_id)
    dest_path = str(Path(dest_dir) / task["filename"])
    progress_state = context.bot_data.setdefault("gdrive_progress", {})

    def sync_progress(current, total):
        prog = progress_state.get(task_id, {})
        prog["bytes"] = max(current, prog.get("bytes", 0))
        prog["total"] = total
        progress_state[task_id] = prog

    try:
        await google_drive.download_direct(task["drive_file_id"], dest_path, progress_callback=sync_progress)
        await _mark_finished(task_id, "done")
        asyncio.create_task(_finalize_done(context, task_id))
    except asyncio.CancelledError:
        Path(dest_path).unlink(missing_ok=True)
        await _mark_finished(task_id, "cancelled")
        if task.get("batch_id"):
            await _refresh_batch_message(context, task["batch_id"])
        else:
            await _safe_edit(context, task, f"🚫 Descarga de <b>{esc(task['filename'])}</b> cancelada.")
    except Exception as e:
        await _mark_finished(task_id, "error", error=str(e))
        if task.get("batch_id"):
            await _refresh_batch_message(context, task["batch_id"])
        else:
            await _safe_edit(context, task, f"❌ Error al descargar <b>{esc(task['filename'])}</b>: {esc(e)}")
    finally:
        active = context.bot_data.get("active_gdrive_tasks", {})
        active.pop(task_id, None)
        progress_state.pop(task_id, None)
        await try_start_next(context)


async def _process_extract_task(context, task_id: int):
    task = await db.get_task(task_id)
    if not task:
        return

    file_path = task["url"]
    extract_dir = task["dest_path"]
    progress_state = context.bot_data.setdefault("extract_progress", {})

    def sync_progress(current, total):
        prog = progress_state.get(task_id, {})
        prog["bytes"] = max(current, prog.get("bytes", 0))
        prog["total"] = total
        progress_state[task_id] = prog

    after_dl = await db.get_setting(f"extract_after_dl_{task_id}") == "1"
    await db.delete_setting(f"extract_after_dl_{task_id}")
    task["after_download"] = after_dl
    if after_dl:
        context.bot_data.setdefault("extract_after_dl", set()).add(task_id)

    pwd = await db.get_setting(f"extract_pwd_{task_id}")
    await db.delete_setting(f"extract_pwd_{task_id}")

    try:
        await archive_utils.extract_archive_with_progress(
            file_path, extract_dir, password=pwd, progress_callback=sync_progress,
        )
        await _mark_finished(task_id, "done")
        if task.get("delete_source"):
            for part in archive_utils.archive_volumes(file_path):
                try:
                    os.remove(part)
                except OSError:
                    pass
            filemanager.invalidate_dir_size_cache(str(task["dest_folder"]).split("/")[0], "")
        if task.get("batch_id"):
            await _refresh_batch_message(context, task["batch_id"])
        else:
            await _safe_edit(
                context, task,
                (f"✅ <b>{esc(task['filename'])}</b> descargado y descomprimido en <code>{esc(task['dest_folder'])}</code>."
                 if after_dl else
                 f"✅ <b>{esc(task['filename'])}</b> descomprimido correctamente en <code>{esc(task['dest_folder'])}</code>.")
            )
    except asyncio.CancelledError:
        await _mark_finished(task_id, "cancelled")
        if task.get("batch_id"):
            await _refresh_batch_message(context, task["batch_id"])
        else:
            await _safe_edit(context, task, f"🚫 Descompresión de <b>{esc(task['filename'])}</b> cancelada (archivos parciales eliminados).")
    except archive_utils.PasswordRequiredError:
        await _mark_finished(task_id, "error", error="Contraseña requerida")
        notify_chat_id = task.get("requested_by") or config.OWNER_ID
        try:
            sent = await context.bot.send_message(
                chat_id=notify_chat_id,
                text=(
                    f"🔒 <b>{esc(task['filename'])}</b> está protegido con contraseña.\n"
                    "Responde a este mensaje con la contraseña para descomprimirlo."
                ),
                parse_mode=ParseMode.HTML,
            )
            _pending_extract_password[sent.message_id] = {
                "task_id": task_id, "file_path": file_path, "extract_dir": extract_dir,
                "folder_name": Path(extract_dir).name, "chat_id": notify_chat_id,
            }
        except Exception:
            pass
    except archive_utils.WrongPasswordError:
        await _mark_finished(task_id, "error", error="Contraseña incorrecta")
        if task.get("batch_id"):
            await _refresh_batch_message(context, task["batch_id"])
        else:
            await _safe_edit(context, task, f"❌ Contraseña incorrecta para <b>{esc(task['filename'])}</b>.")
    except Exception as e:
        await _mark_finished(task_id, "error", error=str(e))
        if task.get("batch_id"):
            await _refresh_batch_message(context, task["batch_id"])
        else:
            await _safe_edit(context, task, f"❌ Error al descomprimir <b>{esc(task['filename'])}</b>: {esc(e)}")
    finally:
        active = context.bot_data.get("active_extract_tasks", {})
        active.pop(task_id, None)
        progress_state.pop(task_id, None)
        context.bot_data.get("extract_after_dl", set()).discard(task_id)
        await try_start_next(context)


async def push_extract_progress(context):
    progress_state = context.bot_data.get("extract_progress", {})
    if not progress_state:
        return

    extracting = {t["id"]: t for t in await db.get_tasks_by_status("downloading") if t["kind"] == "extract"}
    samples = context.bot_data.setdefault("extract_speed_samples", {})

    for task_id, prog in list(progress_state.items()):
        task = extracting.get(task_id)
        if not task:
            progress_state.pop(task_id, None)
            samples.pop(task_id, None)
            continue

        speed = _sample_speed(context, "extract_speed_samples", task_id, prog["bytes"])
        prog["speed"] = speed
        progress_state[task_id] = prog

        if task.get("batch_id"):
            await _refresh_batch_message(context, task["batch_id"])
            continue

        current, total = prog["bytes"], prog["total"]
        pct = (current / total * 100) if total else 0
        mb_current = current / (1024 * 1024)
        mb_total = total / (1024 * 1024) if total else 0
        speed_mb = speed / (1024 * 1024)
        eta_text = f"{int((total - current) / speed)}s" if speed > 0 and total else "?"

        text = (
            (f"✅ Descargado\n" if task_id in context.bot_data.get("extract_after_dl", set()) else "")
            + f"📦 Descomprimiendo <b>{esc(task['filename'])}</b>\n"
            f"{pct:.1f}% ({mb_current:.1f}MB / {mb_total:.1f}MB)\n"
            f"🚀 {speed_mb:.2f} MB/s — ETA {eta_text}"
        )
        await _safe_edit(context, task, text, markup=InlineKeyboardMarkup([[_cancel_button(task_id)]]))


async def push_gdrive_progress(context):
    progress_state = context.bot_data.get("gdrive_progress", {})
    if not progress_state:
        return

    downloading = {t["id"]: t for t in await db.get_tasks_by_status("downloading") if t["kind"] == "gdrive"}
    samples = context.bot_data.setdefault("gdrive_speed_samples", {})

    for task_id, prog in list(progress_state.items()):
        task = downloading.get(task_id)
        if not task:
            progress_state.pop(task_id, None)
            samples.pop(task_id, None)
            continue

        speed = _sample_speed(context, "gdrive_speed_samples", task_id, prog["bytes"])
        prog["speed"] = speed
        progress_state[task_id] = prog

        if task.get("batch_id"):
            await _refresh_batch_message(context, task["batch_id"])
            continue

        current, total = prog["bytes"], prog["total"]
        pct = (current / total * 100) if total else 0
        mb_current = current / (1024 * 1024)
        mb_total = total / (1024 * 1024) if total else 0
        speed_mb = speed / (1024 * 1024)
        eta_text = f"{int((total - current) / speed)}s" if speed > 0 and total else "?"

        text = (
            f"⬇️ Descargando <b>{esc(task['filename'])}</b> desde Google Drive\n"
            f"{pct:.1f}% ({mb_current:.1f}MB / {mb_total:.1f}MB)\n"
            f"🚀 {speed_mb:.2f} MB/s — ETA {eta_text}"
        )
        await _safe_edit(context, task, text, markup=InlineKeyboardMarkup([[_cancel_button(task_id)]]))


async def enqueue_extract_task(context, *, file_path: str, filename: str, source_folder_key: str,
                                dest_folder: str, dest_path: str, requested_by: int | None,
                                progress_message=None) -> int:
    total_uncompressed = await asyncio.to_thread(archive_utils.get_uncompressed_size, file_path)
    task_id = await db.create_task(
        kind="extract",
        filename=filename,
        url=file_path,
        dest_folder=dest_folder,
        dest_path=dest_path,
        status="queued",
        total_size=total_uncompressed,
        requested_by=requested_by,
    )
    if progress_message:
        await db.update_task(task_id, progress_chat_id=progress_message.chat_id, progress_message_id=progress_message.message_id)
    await try_start_next(context)
    return task_id


async def _finalize_done(context, task_id: int):
    task = await db.get_task(task_id)
    if not task:
        return

    if not task.get("extract_after"):
        if task.get("batch_id"):
            await _refresh_batch_message(context, task["batch_id"])
        else:
            await _safe_edit(context, task, f"✅ <b>{esc(task['filename'])}</b> descargado correctamente en <code>{esc(task['dest_folder'])}</code>.")
        return

    file_path = str(Path(task["dest_path"]) / task["filename"])
    folder_name = archive_utils.archive_base_name(task["filename"])
    extract_dir = str(Path(task["dest_path"]) / folder_name)
    dest_label = f"{task['dest_folder']}/{folder_name}"

    total_uncompressed = await asyncio.to_thread(archive_utils.get_uncompressed_size, file_path)

    ext_id = await db.create_task(
        kind="extract",
        filename=task["filename"],
        url=file_path,
        dest_folder=dest_label,
        dest_path=extract_dir,
        status="queued",
        total_size=total_uncompressed,
        requested_by=task.get("requested_by"),
        batch_id=task.get("batch_id"),
        delete_source=1 if await db.get_setting("extract_delete_original", "0") == "1" else 0,
    )
    # one single status message: the extraction keeps editing the download's message
    await db.set_setting(f"extract_after_dl_{ext_id}", "1")
    if task.get("progress_chat_id") and task.get("progress_message_id"):
        await db.update_task(ext_id, progress_chat_id=task["progress_chat_id"], progress_message_id=task["progress_message_id"])

    if task.get("batch_id"):
        await _refresh_batch_message(context, task["batch_id"])
    else:
        await _safe_edit(
            context, task,
            f"✅ <b>{esc(task['filename'])}</b> descargado.\n"
            f"📦 Descompresión en cola hacia <code>{esc(dest_label)}</code>…",
            markup=InlineKeyboardMarkup([[_cancel_button(ext_id)]]),
        )

    await try_start_next(context)


_pending_extract_password: dict[int, dict] = {}


async def handle_password_reply(update, context) -> bool:
    msg = update.effective_message
    if not msg.reply_to_message:
        return False
    pending = _pending_extract_password.pop(msg.reply_to_message.message_id, None)
    if not pending:
        return False

    password = msg.text.strip() if msg.text else ""
    task_id = pending["task_id"]

    await db.set_setting(f"extract_pwd_{task_id}", password)
    await db.update_task(task_id, status="queued", error=None)
    await try_start_next(context)
    await msg.reply_text("🔑 Contraseña recibida. Tarea de descompresión reanudada en la cola.")
    return True


def _sample_speed(context, samples_key: str, task_id: int, current_bytes: int) -> float:
    samples = context.bot_data.setdefault(samples_key, {})
    now = time.monotonic()
    prev = samples.get(task_id)
    samples[task_id] = (current_bytes, now)
    if not prev:
        return 0.0
    prev_bytes, prev_t = prev
    elapsed = max(now - prev_t, 0.001)
    return max((current_bytes - prev_bytes) / elapsed, 0.0)


async def push_telegram_progress(context):
    progress_state = context.bot_data.get("telegram_progress", {})
    if not progress_state:
        return

    downloading = {t["id"]: t for t in await db.get_tasks_by_status("downloading") if t["kind"] == "telegram"}
    samples = context.bot_data.setdefault("telegram_speed_samples", {})

    for task_id, prog in list(progress_state.items()):
        task = downloading.get(task_id)
        if not task:
            progress_state.pop(task_id, None)
            samples.pop(task_id, None)
            continue

        speed = _sample_speed(context, "telegram_speed_samples", task_id, prog["bytes"])
        prog["speed"] = speed
        progress_state[task_id] = prog

        if task.get("batch_id"):
            await _refresh_batch_message(context, task["batch_id"])
            continue

        current, total = prog["bytes"], prog["total"]
        pct = (current / total * 100) if total else 0
        mb_current = current / (1024 * 1024)
        mb_total = total / (1024 * 1024) if total else 0
        speed_mb = speed / (1024 * 1024)
        eta_text = f"{int((total - current) / speed)}s" if speed > 0 and total else "?"

        text = (
            f"⬇️ Descargando <b>{esc(task['filename'])}</b>\n"
            f"{pct:.1f}% ({mb_current:.1f}MB / {mb_total:.1f}MB)\n"
            f"🚀 {speed_mb:.2f} MB/s — ETA {eta_text}"
        )
        await _safe_edit(context, task, text, markup=InlineKeyboardMarkup([[_cancel_button(task_id)]]))


async def cancel_task_by_id(context, task_id: int) -> tuple[bool, str]:
    task = await db.get_task(task_id)
    if not task:
        return False, "Tarea no encontrada."

    if task["status"] in ("done", "cancelled", "error"):
        return True, "Esta tarea ya estaba finalizada."

    if task["kind"] == "extract":
        active = context.bot_data.get("active_extract_tasks", {})
        running = active.get(task_id)
        if running:
            running.cancel()
        else:
            await _mark_finished(task_id, "cancelled")
            archive_utils._safe_clean_dest(task["dest_path"], task["url"])
            if task.get("batch_id"):
                await _refresh_batch_message(context, task["batch_id"])
            else:
                await _safe_edit(context, task, f"🚫 Descompresión de <b>{esc(task['filename'])}</b> cancelada.")
            await try_start_next(context)
        return True, "Descompresión cancelada."

    if task["kind"] == "tb_link":
        running = context.bot_data.get("active_tb_tasks", {}).get(task_id)
        if running:
            running.cancel()
        else:
            await _mark_finished(task_id, "cancelled")
            await _safe_edit(context, task, "🚫 Tarea cancelada.")
            await try_start_next(context)
        return True, "Cancelada."

    if task["kind"] == "link" and task["gid"]:
        try:
            downloader.remove_download(task["gid"])
        except Exception:
            pass
        await _mark_finished(task_id, "cancelled")
        if task.get("batch_id"):
            await _refresh_batch_message(context, task["batch_id"])
        else:
            await _safe_edit(context, task, f"🚫 Descarga de <b>{esc(task['filename'])}</b> cancelada.")
        await try_start_next(context)
        return True, "Cancelada."

    if task["kind"] == "telegram":
        active = context.bot_data.get("active_telegram_tasks", {})
        running = active.get(task_id)
        if running:
            running.cancel()
        else:
            await _mark_finished(task_id, "cancelled")
            if task.get("batch_id"):
                await _refresh_batch_message(context, task["batch_id"])
            else:
                await _safe_edit(context, task, "🚫 Tarea cancelada.")
            await try_start_next(context)
        return True, "Cancelada."

    if task["kind"] == "gdrive":
        active = context.bot_data.get("active_gdrive_tasks", {})
        running = active.get(task_id)
        if running:
            running.cancel()
        else:
            await _mark_finished(task_id, "cancelled")
            if task.get("batch_id"):
                await _refresh_batch_message(context, task["batch_id"])
            else:
                await _safe_edit(context, task, "🚫 Tarea cancelada.")
            await try_start_next(context)
        return True, "Cancelada."

    if task["kind"] == "upload":
        manager = context.bot_data.get("userbot_manager")
        if manager:
            manager.cancel_upload(str(task_id))
        active = context.bot_data.get("active_upload_tasks", {})
        running = active.get(task_id)
        if running:
            running.cancel()
        else:
            await _mark_finished(task_id, "cancelled")
        if task.get("progress_chat_id") and task.get("progress_message_id"):
            try:
                await context.bot.edit_message_text(
                    chat_id=task["progress_chat_id"],
                    message_id=task["progress_message_id"],
                    text=f"🚫 Subida de <b>{esc(task['filename'])}</b> cancelada.",
                )
            except Exception:
                pass
        await try_start_next(context)
        return True, "Subida cancelada."

    await _mark_finished(task_id, "cancelled")
    if task.get("batch_id"):
        await _refresh_batch_message(context, task["batch_id"])
    else:
        await _safe_edit(context, task, "🚫 Tarea cancelada.")
    await try_start_next(context)
    return True, "Cancelada."


@authorized_only
async def dl_cancel(update, context):
    query = update.callback_query
    await query.answer()
    task_id = int(query.data.split(":")[1])
    ok, message = await cancel_task_by_id(context, task_id)
    if not ok:
        await query.answer(message, show_alert=True)


@authorized_only
async def dl_pause(update, context):
    query = update.callback_query
    task_id = int(query.data.split(":")[1])
    ok, message = await pause_task_by_id(context, task_id)
    await query.answer(message, show_alert=not ok)
    await queue_view_callback(update, context)


@authorized_only
async def dl_resume(update, context):
    query = update.callback_query
    task_id = int(query.data.split(":")[1])
    ok, message = await resume_task_by_id(context, task_id)
    await query.answer(message, show_alert=not ok)
    await queue_view_callback(update, context)


@authorized_only
async def dl_prioritize(update, context):
    query = update.callback_query
    task_id = int(query.data.split(":")[1])
    ok, message = await prioritize_task(context, task_id)
    await query.answer(message, show_alert=not ok)
    await queue_view_callback(update, context)


@authorized_only
async def dl_move_up(update, context):
    query = update.callback_query
    task_id = int(query.data.split(":")[1])
    ok, message = await move_task(context, task_id, "up")
    await query.answer(message, show_alert=not ok)
    await queue_view_callback(update, context)


@authorized_only
async def dl_move_down(update, context):
    query = update.callback_query
    task_id = int(query.data.split(":")[1])
    ok, message = await move_task(context, task_id, "down")
    await query.answer(message, show_alert=not ok)
    await queue_view_callback(update, context)


async def poll_aria2_downloads(context):
    tasks = await db.get_tasks_by_status("downloading")
    aria2_tasks = [t for t in tasks if t.get("gid")]
    if not aria2_tasks:
        return

    active_map = downloader.get_active_downloads_dict()

    for task in aria2_tasks:
        gid = task["gid"]
        dl = active_map.get(gid)
        if dl is None:
            try:
                dl = downloader.get_download(gid)
            except Exception:
                continue

        batch_id = task.get("batch_id")
        kb = InlineKeyboardMarkup([[_cancel_button(task["id"])]])
        try:
            if dl.is_complete:
                await _mark_finished(task["id"], "done")
                asyncio.create_task(_finalize_done(context, task["id"]))
                await try_start_next(context)
            elif dl.has_failed:
                await _mark_finished(task["id"], "error", error=dl.error_message)
                if batch_id:
                    await _refresh_batch_message(context, batch_id)
                else:
                    await _safe_edit(context, task, f"❌ Error al descargar <b>{esc(task['filename'])}</b>: {esc(dl.error_message)}")
                await try_start_next(context)
            elif batch_id:
                await _refresh_batch_message(context, batch_id)
            else:
                await _safe_edit(
                    context, task,
                    f"⬇️ Descargando <b>{esc(task['filename'])}</b>\n"
                    f"{dl.progress:.1f}% — 🚀 {dl.download_speed_string()} — ETA {dl.eta_string()}",
                    markup=kb,
                )
        except Exception:
            pass


_SECTION_RE = re.compile(r"^\s*(\S+)\s+<b>(.+?):</b>\s*$")


def _queue_sections_to_rich(sections: list[str], total: int, footer: str | None) -> str:
    blocks = [r_h(f"Cola de descargas · {total} tarea(s)", 2, "📥")]
    items: list[str] = []

    def flush():
        if items:
            blocks.append(r_ul(list(items)))
            items.clear()

    for raw in sections[1:]:
        text = raw.strip("\n")
        if not text:
            continue
        m = _SECTION_RE.match(text)
        if m:
            flush()
            blocks.append(r_h(m.group(2), 3, m.group(1)))
            continue
        text = re.sub(r"^(•|<b>\d+\.</b>)\s*", "", text)
        items.append(text.replace("\n  └ ", "<br/>└ ").replace("\n", "<br/>"))
    flush()
    if footer:
        blocks.append(r_footer(esc(footer)))
    return rich(*blocks)


def _eta_string(bytes_done: float, total: float, speed_bps: float) -> str:
    if not speed_bps or speed_bps <= 0 or not total or total <= bytes_done:
        return "—"
    seconds = (total - bytes_done) / speed_bps
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        m, s = divmod(int(seconds), 60)
        return f"{m}m {s}s"
    h, rem = divmod(int(seconds), 3600)
    return f"{h}h {rem // 60}m"


def _progress_block(bytes_done: float, total: float, speed_bps: float) -> str:
    pct = (bytes_done / total * 100) if total else 0
    size_str = f"{filemanager.human_size(bytes_done)}/{filemanager.human_size(total)}" if total else filemanager.human_size(bytes_done)
    speed_str = f"{filemanager.human_size(speed_bps)}/s" if speed_bps else "—"
    return f"<code>{pct:.1f}%</code> ({size_str}) 🚀 {speed_str} · ⏱ ETA {_eta_string(bytes_done, total, speed_bps)}"


async def _render_queue_overview(context, user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    import handlers_realdebrid as h_rd

    is_owner_user = (user_id == config.OWNER_ID)
    active_tasks = await db.get_tasks_by_status("downloading")
    paused_tasks = await db.get_tasks_by_status("paused")
    queued_tasks = await db.get_tasks_by_status("queued")

    if not is_owner_user:
        active_tasks = [t for t in active_tasks if t.get("requested_by") == user_id]
        paused_tasks = [t for t in paused_tasks if t.get("requested_by") == user_id]
        queued_tasks = [t for t in queued_tasks if t.get("requested_by") == user_id]

    rd_active = []
    for tid, st in h_rd.rd_torrent_states.items():
        if "dest_folder" not in st:
            continue
        if not is_owner_user and st.get("requested_by") != user_id:
            continue
        rd_active.append((tid, st))

    total_items = len(active_tasks) + len(paused_tasks) + len(queued_tasks) + len(rd_active)
    if total_items == 0:
        text = rich(r_h("Cola de descargas", 2, "📥"), r_p("<i>No hay tareas activas ni en cola en este momento.</i>"))
        kb = [
            [InlineKeyboardButton("🔄 Actualizar", callback_data="queue:refresh")],
            [InlineKeyboardButton("🏠 Menú principal", callback_data="menu:main")],
        ]
        return text, InlineKeyboardMarkup(kb)

    sections = ["📥 <b>Cola de descargas y procesos</b>\n"]
    task_rows = []
    MAX_TASK_CONTROLS = 8

    def _controls_left():
        return len(task_rows) < MAX_TASK_CONTROLS

    if active_tasks:
        sections.append("⚙️ <b>En proceso:</b>")
        for t in active_tasks:
            fname = html.escape(t["filename"])
            dest = html.escape(t.get("dest_folder") or "")

            if t["kind"] == "extract":
                prog = context.bot_data.get("extract_progress", {}).get(t["id"])
                if prog and prog.get("total"):
                    line = _progress_block(prog["bytes"], prog["total"], prog.get("speed", 0))
                    sections.append(f"• 📦 <b>{fname}</b> <i>(Descomprimiendo)</i>\n  └ {line} → <code>{dest}</code>")
                else:
                    sections.append(f"• 📦 <b>{fname}</b> <i>(Descomprimiendo...)</i> → <code>{dest}</code>")
                if _controls_left():
                    task_rows.append([InlineKeyboardButton(f"❌ Cancelar {t['filename'][:14]}", callback_data=f"dlcancel:{t['id']}")])

            elif t["kind"] == "telegram":
                prog = context.bot_data.get("telegram_progress", {}).get(t["id"])
                if prog and prog.get("total"):
                    line = _progress_block(prog["bytes"], prog["total"], prog.get("speed", 0))
                    sections.append(f"• 🤖 <b>{fname}</b> <i>(Telegram)</i>\n  └ {line} → <code>{dest}</code>")
                else:
                    sections.append(f"• 🤖 <b>{fname}</b> <i>(Descargando Telegram...)</i> → <code>{dest}</code>")
                if _controls_left():
                    task_rows.append([InlineKeyboardButton(f"❌ Cancelar {t['filename'][:14]}", callback_data=f"dlcancel:{t['id']}")])

            elif t["kind"] == "gdrive":
                prog = context.bot_data.get("gdrive_progress", {}).get(t["id"])
                if prog and prog.get("total"):
                    line = _progress_block(prog["bytes"], prog["total"], prog.get("speed", 0))
                    sections.append(f"• 📁 <b>{fname}</b> <i>(Google Drive)</i>\n  └ {line} → <code>{dest}</code>")
                else:
                    sections.append(f"• 📁 <b>{fname}</b> <i>(Descargando Drive...)</i> → <code>{dest}</code>")
                if _controls_left():
                    task_rows.append([InlineKeyboardButton(f"❌ Cancelar {t['filename'][:14]}", callback_data=f"dlcancel:{t['id']}")])

            elif t["kind"] == "upload":
                prog = context.bot_data.get("upload_progress", {}).get(t["id"])
                if prog and prog.get("total"):
                    line = _progress_block(prog["bytes"], prog["total"], prog.get("speed", 0))
                    sections.append(f"• 📤 <b>{fname}</b> <i>(Subiendo a Telegram)</i>\n  └ {line}")
                else:
                    sections.append(f"• 📤 <b>{fname}</b> <i>(Subiendo a Telegram...)</i>")
                if _controls_left():
                    task_rows.append([InlineKeyboardButton(f"❌ Cancelar {t['filename'][:14]}", callback_data=f"dlcancel:{t['id']}")])

            else:
                tag = {"realdebrid": "💳 RD → Aria2", "torbox": "📦 TorBox → Aria2"}.get(
                    t.get("client") or ("realdebrid" if t["kind"] == "rd_link" else "torbox" if t["kind"] == "tb_link" else ""), "⚡ Aria2")
                info_line = f"• {tag} <b>{fname}</b>"
                if t.get("gid"):
                    try:
                        dl = downloader.get_download(t["gid"])
                        line = _progress_block(dl.completed_length, dl.total_length, dl.download_speed)
                        info_line += f"\n  └ {line} → <code>{dest}</code>"
                    except Exception:
                        info_line += f" → <code>{dest}</code>"
                else:
                    info_line += f" → <code>{dest}</code>"
                sections.append(info_line)
                if _controls_left():
                    task_rows.append([
                        InlineKeyboardButton(f"⏸️ Pausar {t['filename'][:10]}", callback_data=f"dlpause:{t['id']}"),
                        InlineKeyboardButton("❌ Cancelar", callback_data=f"dlcancel:{t['id']}"),
                    ])

    if rd_active:
        sections.append("\n☁️ <b>Torrents en la nube (proveedor):</b>")
        for tid, st in rd_active:
            snap = st.get("last_snapshot", {})
            total = snap.get("total") or 0
            pct = snap.get("progress", 0)
            bytes_done = total * pct / 100
            name = html.escape(st.get("torrent_name", "Torrent"))
            line = _progress_block(bytes_done, total, snap.get("speed", 0))
            seeders = snap.get("seeders", 0)
            prov = "📦 TorBox" if st.get("provider") == "torbox" else "💳 Real-Debrid"
            sections.append(f"• {prov} <b>{name}</b> ({html.escape(snap.get('status', 'procesando'))})\n  └ {line} · 🌱 {seeders}")
            if _controls_left():
                task_rows.append([InlineKeyboardButton(f"❌ {name[:18]}", callback_data=f"rdcancel:{tid}")])

    if queued_tasks:
        queued_tasks.sort(key=lambda t: (-(t.get("priority") or 0), t["id"]))
        sections.append("\n🕓 <b>En cola:</b>")
        for i, t in enumerate(queued_tasks, start=1):
            icon_kind = {
                "extract": "📦 [Descompresión]", "telegram": "🤖 [Telegram]", "gdrive": "📁 [GDrive]",
            }.get(t["kind"]) or "[" + client_label(t) + "]"
            sections.append(f"<b>{i}.</b> {icon_kind} {html.escape(t['filename'])} → <code>{html.escape(t.get('dest_folder') or '')}</code>")
            if _controls_left():
                task_rows.append([
                    InlineKeyboardButton("⬆️", callback_data=f"dlmoveup:{t['id']}"),
                    InlineKeyboardButton("⬇️", callback_data=f"dlmovedown:{t['id']}"),
                    InlineKeyboardButton("▶️ Ya", callback_data=f"dlprio:{t['id']}"),
                    InlineKeyboardButton("⏸️", callback_data=f"dlpause:{t['id']}"),
                    InlineKeyboardButton("❌", callback_data=f"dlcancel:{t['id']}"),
                ])

    if paused_tasks:
        sections.append("\n⏸️ <b>Pausadas:</b>")
        for t in paused_tasks:
            sections.append(f"• ⏸️ {html.escape(t['filename'])} <i>({client_label(t)})</i>")
            if _controls_left():
                task_rows.append([
                    InlineKeyboardButton(f"▶️ Reanudar {t['filename'][:10]}", callback_data=f"dlresume:{t['id']}"),
                    InlineKeyboardButton("❌ Cancelar", callback_data=f"dlcancel:{t['id']}"),
                ])

    kb = list(task_rows)
    footer = None
    if total_items > MAX_TASK_CONTROLS:
        footer = f"Mostrando controles para las primeras {MAX_TASK_CONTROLS} tareas. Actualiza tras completar alguna para ver el resto."

    kb.append([
        InlineKeyboardButton("🔄 Actualizar", callback_data="queue:refresh"),
        InlineKeyboardButton("🏠 Menú principal", callback_data="menu:main"),
    ])

    return _queue_sections_to_rich(sections, total_items, footer), InlineKeyboardMarkup(kb)


@authorized_only
async def queue_command(update, context):
    text, kb = await _render_queue_overview(context, update.effective_user.id)
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


@authorized_only
async def queue_view_callback(update, context):
    query = update.callback_query
    await query.answer()
    text, kb = await _render_queue_overview(context, update.effective_user.id)
    try:
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    except BadRequest as e:
        if "message is not modified" not in str(e).lower():
            await query.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


HISTORY_PAGE_SIZE = 10
STATUS_ICON = {"done": "✅", "cancelled": "🚫", "error": "❌"}


def _history_task_duration(task: dict) -> str | None:
    started, finished = task.get("started_at"), task.get("finished_at")
    if not started or not finished:
        return None
    try:
        delta = (datetime.fromisoformat(finished) - datetime.fromisoformat(started)).total_seconds()
    except Exception:
        return None
    if delta < 0:
        return None
    if delta < 60:
        return f"{int(delta)}s"
    if delta < 3600:
        return f"{int(delta // 60)}m"
    return f"{delta / 3600:.1f}h"


async def _render_history(context, user_id: int, page: int = 0) -> tuple[str, InlineKeyboardMarkup]:
    is_owner_user = (user_id == config.OWNER_ID)
    tasks = await db.get_history(limit=200, requested_by=(config.OWNER_ID if is_owner_user else user_id))

    total = len(tasks)
    start = page * HISTORY_PAGE_SIZE
    end = min(start + HISTORY_PAGE_SIZE, total)
    page_items = tasks[start:end]
    total_pages = max(1, -(-total // HISTORY_PAGE_SIZE))

    if total == 0:
        text = rich(r_h("Historial de descargas", 2, "🗂️"), r_p("<i>Todavía no hay descargas completadas, canceladas o con error.</i>"))
        kb = [[InlineKeyboardButton("🏠 Menú principal", callback_data="menu:main")]]
        return text, InlineKeyboardMarkup(kb)

    rows = []
    for t in page_items:
        icon = STATUS_ICON.get(t["status"], "•")
        fname = html.escape(t["filename"] or "?")
        size = filemanager.human_size(t["total_size"]) if t.get("total_size") else "—"
        dur = _history_task_duration(t) or "—"
        if t["status"] == "error" and t.get("error"):
            detail = f"<i>{html.escape(str(t['error'])[:80])}</i>"
        else:
            detail = f"<code>{html.escape(t.get('dest_folder') or '')}</code>" if t.get("dest_folder") else "—"
        rows.append([icon, f"<b>{fname}</b>", esc(client_label(t)), esc(size), esc(dur), detail])

    kb = []
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀ Anterior", callback_data=f"hist:page:{page - 1}"))
    if end < total:
        nav_row.append(InlineKeyboardButton("Siguiente ▶", callback_data=f"hist:page:{page + 1}"))
    if nav_row:
        kb.append(nav_row)
    kb.append([InlineKeyboardButton("🗑️ Vaciar historial", callback_data="hist:clear_confirm")])
    kb.append([InlineKeyboardButton("🏠 Menú principal", callback_data="menu:main")])

    text = rich(
        r_h("Historial de descargas", 2, "🗂️"),
        r_table(rows, header=["", "Archivo", "Cliente", "Tamaño", "Duración", "Destino / error"],
                caption=f"{start + 1}–{end} de {total} · Página {page + 1}/{total_pages}"),
        r_footer("✅ completada · 🚫 cancelada · ❌ error"),
    )
    return text, InlineKeyboardMarkup(kb)


@authorized_only
async def history_command(update, context):
    text, kb = await _render_history(context, update.effective_user.id, page=0)
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


@authorized_only
async def history_page_callback(update, context):
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":")[2])
    text, kb = await _render_history(context, update.effective_user.id, page=page)
    try:
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    except BadRequest as e:
        if "message is not modified" not in str(e).lower():
            raise


@authorized_only
async def history_clear_confirm(update, context):
    query = update.callback_query
    await query.answer()
    kb = [
        [InlineKeyboardButton("✅ Sí, vaciar", callback_data="hist:clear_do")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="hist:page:0")],
    ]
    await query.edit_message_text(
        rich(r_h("Vaciar historial", 2, "🗑️"), r_p("¿Seguro que quieres borrar todo tu historial de descargas?"), r_footer("Esto no borra archivos del NAS, solo el registro.")),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(kb),
    )


@authorized_only
async def history_clear_do(update, context):
    query = update.callback_query
    await query.answer("Historial vaciado.")
    is_owner_user = (update.effective_user.id == config.OWNER_ID)
    await db.clear_history(requested_by=config.OWNER_ID if is_owner_user else update.effective_user.id)
    text, kb = await _render_history(context, update.effective_user.id, page=0)
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
