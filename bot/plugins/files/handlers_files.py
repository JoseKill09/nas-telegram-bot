import asyncio
from datetime import datetime
import html
import logging
from pathlib import Path
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

import config
import db
import filemanager
import keyboards
from i18n import L
from rich_ui import r_h, r_p, r_ul, r_footer, rich
from utils import authorized_only

logger = logging.getLogger(__name__)


PAGE_SIZE = 20


def _parent_of(relpath: str) -> str:
    parent = Path(relpath).parent
    return "" if parent == Path(".") else str(parent)


async def render_folder(folder_key: str, relpath: str, page: int = 0) -> tuple[str, InlineKeyboardMarkup]:
    dirs, files = filemanager.list_dir(folder_key, relpath)
    entries = [(d, True) for d in dirs] + [(f, False) for f in files]

    total_pages = max(1, -(-len(entries) // PAGE_SIZE))
    page = max(0, min(page, total_pages - 1))
    start = page * PAGE_SIZE
    page_entries = entries[start:start + PAGE_SIZE]

    dir_rels = [
        str(Path(relpath) / entry.name) if relpath else entry.name
        for entry, is_dir in page_entries if is_dir
    ]
    dir_sizes = dict(zip(
        dir_rels,
        await asyncio.gather(*[filemanager.get_dir_size(folder_key, r) for r in dir_rels]) if dir_rels else [],
    ))

    kb = []
    for entry, is_dir in page_entries:
        rel = str(Path(relpath) / entry.name) if relpath else entry.name
        token = keyboards.token_for(folder_key, rel)
        name = entry.name if len(entry.name) <= 42 else entry.name[:39] + "..."

        if is_dir:
            size_bytes = dir_sizes.get(rel)
            size_label = filemanager.human_size(size_bytes) if size_bytes is not None else "…"
            label = f"📁 {name} · {size_label}"
            callback = f"fm:nav:{folder_key}:{token}"
        else:
            size_label = filemanager.human_size(entry.stat().st_size)
            label = f"📄 {name} · {size_label}"
            callback = f"fm:file:{folder_key}:{token}"

        kb.append([InlineKeyboardButton(label, callback_data=callback)])

    path_label = f"{folder_key}/{relpath}" if relpath else folder_key
    caption = f"{len(dirs)} carpeta(s) · {len(files)} archivo(s)"
    if total_pages > 1:
        caption += f" · página {page + 1}/{total_pages}"
    body = r_p(f"<i>{html.escape(caption)}</i>") if page_entries else r_p("<i>(carpeta vacía)</i>")
    text = rich(r_h(path_label, 2, "📂"), body, r_footer("Toca una carpeta o archivo para abrirlo."))

    here_token = keyboards.token_for(folder_key, relpath)

    if total_pages > 1:
        pager_row = []
        if page > 0:
            pager_row.append(InlineKeyboardButton("◀ Anterior", callback_data=f"fm:nav:{folder_key}:{here_token}:{page - 1}"))
        if page < total_pages - 1:
            pager_row.append(InlineKeyboardButton("Siguiente ▶", callback_data=f"fm:nav:{folder_key}:{here_token}:{page + 1}"))
        kb.append(pager_row)

    nav_row = [InlineKeyboardButton("➕ Nueva carpeta", callback_data=f"fm:mkdir:{folder_key}:{here_token}")]
    kb.append(nav_row)

    back_row = []
    if relpath:
        parent_token = keyboards.token_for(folder_key, _parent_of(relpath))
        back_row.append(InlineKeyboardButton("⬅️ Atrás", callback_data=f"fm:nav:{folder_key}:{parent_token}"))
    else:
        back_row.append(InlineKeyboardButton("⬅️ Raíz", callback_data="fm:root"))
    back_row.append(InlineKeyboardButton("🏠 Menú", callback_data="menu:main"))
    kb.append(back_row)

    return text, InlineKeyboardMarkup(kb)


@authorized_only
async def fm_root(update, context):
    query = update.callback_query
    await query.answer()
    row = [
        InlineKeyboardButton(name, callback_data=f"fm:nav:{name}:{keyboards.token_for(name, '')}")
        for name in config.FOLDERS
    ]
    kb = [row, [InlineKeyboardButton("🏠 Menú principal", callback_data="menu:main")]]
    folder_sizes = dict(zip(config.FOLDERS, await asyncio.gather(
        *[filemanager.get_dir_size(name, "") for name in config.FOLDERS]
    )))
    items = []
    for name in config.FOLDERS:
        size_label = filemanager.human_size(folder_sizes[name]) if folder_sizes[name] is not None else "…"
        try:
            info = filemanager.get_disk_space_info(name)
            free_label = html.escape(str(info.get("free_str", "?")))
            items.append(f"<b>{html.escape(name)}</b> — {size_label} usados · libre: {free_label}")
        except Exception:
            items.append(f"<b>{html.escape(name)}</b> — {size_label} usados")
    text = rich(r_h("Gestor de archivos", 2, "📂"), r_ul(items), r_footer("Elige una carpeta raíz."))
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))


@authorized_only
async def fm_nav(update, context):
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":", 4)
    folder_key, token = parts[2], parts[3]
    page = int(parts[4]) if len(parts) > 4 else 0
    resolved = keyboards.resolve_token(token)
    relpath = resolved[1] if resolved else ""
    try:
        text, kb = await render_folder(folder_key, relpath, page)
    except filemanager.PathError as e:
        await query.edit_message_text(f"⚠️ {e}")
        return
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


@authorized_only
async def fm_file_menu(update, context):
    query = update.callback_query
    await query.answer()
    _, _, folder_key, token = query.data.split(":", 3)
    relpath = keyboards.resolve_token(token)[1]
    info = filemanager.get_info(folder_key, relpath)
    parent_token = keyboards.token_for(folder_key, _parent_of(relpath))

    kb = []
    if not info.get("is_dir", False):
        row = [InlineKeyboardButton("📤 Subir a Telegram", callback_data=f"fm:upload:{folder_key}:{token}")]
        kb.append(row)
        import archive_utils
        if archive_utils.is_archive(relpath):
            kb.append([InlineKeyboardButton("📦 Extraer aquí", callback_data=f"fm:extract:{folder_key}:{token}")])
    kb.append([
        InlineKeyboardButton("✏️ Renombrar", callback_data=f"fm:rename:{folder_key}:{token}"),
        InlineKeyboardButton("ℹ️ Info", callback_data=f"fm:info:{folder_key}:{token}"),
    ])
    kb.append([InlineKeyboardButton(L("📋 Copiar / mover", "📋 Copy / move"), callback_data=f"fm:cp:{folder_key}:{token}")])
    kb.append([
        InlineKeyboardButton("🗑️ Eliminar", callback_data=f"fm:delconfirm:{folder_key}:{token}"),
        InlineKeyboardButton("⬅️ Volver", callback_data=f"fm:nav:{folder_key}:{parent_token}"),
    ])
    await query.edit_message_text(f"📄 {Path(relpath).name}", reply_markup=InlineKeyboardMarkup(kb))


@authorized_only
async def fm_extract_entry(update, context):
    query = update.callback_query
    await query.answer()
    _, _, folder_key, token = query.data.split(":", 3)
    relpath = keyboards.resolve_token(token)[1]

    import archive_utils
    import handlers_downloads as h_dl

    _base, target = filemanager.resolve_path(folder_key, relpath)
    if not target.is_file() or not archive_utils.is_archive(target.name):
        await query.answer("Este archivo ya no es un comprimido válido.", show_alert=True)
        return

    folder_name = archive_utils.archive_base_name(target.name)
    extract_dir = target.parent / folder_name
    parent_relpath = str(Path(relpath).parent)
    dest_label = f"{folder_key}/{parent_relpath}/{folder_name}" if parent_relpath not in ("", ".") else f"{folder_key}/{folder_name}"

    await query.edit_message_text(f"📦 Encolando descompresión de {html.escape(target.name)}...")
    await h_dl.enqueue_extract_task(
        context,
        file_path=str(target),
        filename=target.name,
        source_folder_key=folder_key,
        dest_folder=dest_label,
        dest_path=str(extract_dir),
        requested_by=update.effective_user.id,
        progress_message=query.message,
    )


@authorized_only
async def fm_info(update, context):
    query = update.callback_query
    await query.answer()
    _, _, folder_key, token = query.data.split(":", 3)
    relpath = keyboards.resolve_token(token)[1]
    try:
        info = filemanager.get_info(folder_key, relpath)
        _base, target = filemanager.resolve_path(folder_key, relpath)
        stat = target.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        is_dir = info.get("is_dir", False)
        tipo = "Carpeta" if is_dir else "Archivo"
        tamano = info.get("size") or "-"

        lines = [
            f"ℹ️ <b>Detalles de {tipo}</b>",
            "",
            f"<b>Nombre:</b> {html.escape(info['name'])}",
            f"<b>Ruta:</b> <code>{html.escape(relpath or '/')}</code>",
            f"<b>Carpeta base:</b> {html.escape(folder_key)}",
            f"<b>Tamaño:</b> {tamano}",
            f"<b>Modificado:</b> {mtime}",
        ]
    except Exception as e:
        lines = [f"⚠️ Error al obtener información: {html.escape(str(e))}"]

    kb = [[InlineKeyboardButton("⬅️ Volver", callback_data=f"fm:file:{folder_key}:{token}")]]
    await query.edit_message_text("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))


async def run_file_upload(
    context,
    task_id: int,
    chat_id: int | str,
    status_message_id: int | None,
    file_path: str,
    filename: str,
    total_size: int,
    user_id: int | None = None,
    force_document: bool = False,
):
    app = getattr(context, "application", context)
    bot = getattr(context, "bot", getattr(app, "bot", None))
    bot_data = getattr(app, "bot_data", {})
    manager = bot_data.get("userbot_manager")
    if not manager:
        await db.update_task(task_id, status="error", error="Userbot no disponible", finished_at=datetime.now().isoformat())
        return

    cancel_event = manager.register_upload(str(task_id), filename=filename, total_size=total_size, chat_id=chat_id)
    progress_dict = bot_data.setdefault("upload_progress", {})
    progress_dict[task_id] = {
        "bytes": 0,
        "total": total_size,
        "speed": 0.0,
        "status": "uploading",
    }

    last_edit = [0.0]
    last_bytes = [0]
    last_time = [time.time()]

    async def on_progress(current, total):
        now = time.time()
        dt = now - last_time[0]
        if dt >= 0.5:
            speed = max(0.0, (current - last_bytes[0]) / dt)
            last_bytes[0] = current
            last_time[0] = now
            progress_dict[task_id] = {
                "bytes": current,
                "total": total,
                "speed": speed,
                "status": "uploading",
            }
            manager.update_upload_progress(str(task_id), current, total, speed)

        if bot and status_message_id and (now - last_edit[0] >= config.PROGRESS_EDIT_INTERVAL):
            last_edit[0] = now
            pct = (current / total * 100) if total else 0.0
            cur_mb = current / (1024 * 1024)
            tot_mb = total / (1024 * 1024) if total else 0.0
            spd = progress_dict.get(task_id, {}).get("speed", 0.0)
            spd_mb = spd / (1024 * 1024)
            eta = f"{int((total - current) / spd)}s" if spd > 0 and total else "?"
            txt = (
                f"📤 <b>Subiendo a Telegram</b>\n\n"
                f"• <b>Archivo:</b> <code>{html.escape(filename)}</code>\n"
                f"• <b>Progreso:</b> <code>{pct:.1f}%</code> ({cur_mb:.1f}/{tot_mb:.1f} MB)\n"
                f"• <b>Velocidad:</b> 🚀 <code>{spd_mb:.2f} MB/s</code> (ETA: <code>{eta}</code>)"
            )
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancelar subida", callback_data=f"fm:cancelup:{task_id}")
            ]])
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=status_message_id,
                    text=txt,
                    parse_mode=ParseMode.HTML,
                    reply_markup=kb,
                )
            except Exception:
                pass

    try:
        channel_id = getattr(config, "CHANNEL_ID", None)
        if not channel_id:
            raise RuntimeError("CHANNEL_ID no está configurado en el archivo .env")

        target_user = user_id or (chat_id if str(chat_id) != str(channel_id) else config.OWNER_ID)

        existing_msg_id = None
        cached = await db.get_channel_file(filename, total_size)
        if cached and cached.get("message_id"):
            existing_msg_id = cached["message_id"]

        if not existing_msg_id and manager:
            try:
                found_id = await manager.find_file_in_channel(channel_id, filename, total_size)
                if found_id:
                    existing_msg_id = found_id
                    await db.add_channel_file(filename, total_size, int(channel_id), found_id)
            except Exception as e:
                logger.warning("Error buscando duplicados en canal vía Userbot: %s", e)

        if existing_msg_id:
            delivered = False
            if target_user and str(target_user) != str(channel_id) and bot:
                try:
                    await bot.copy_message(
                        chat_id=target_user,
                        from_chat_id=channel_id,
                        message_id=existing_msg_id,
                    )
                    delivered = True
                except Exception as e:
                    logger.warning("Error copiando mensaje existente a chat privado %s: %s", target_user, e)

            await db.update_task(task_id, status="done", finished_at=datetime.now().isoformat())
            if bot and status_message_id:
                dest_desc = "y entregado en tu chat privado al instante ⚡" if delivered else "en el canal ⚡"
                try:
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=status_message_id,
                        text=f"⚡ El archivo <b>{html.escape(filename)}</b> ya existía {dest_desc}",
                        parse_mode=ParseMode.HTML,
                    )
                except Exception:
                    pass
            return

        sent_msg = await manager.send_file_to_chat(
            chat_id=channel_id,
            file_path=file_path,
            caption=f"📁 {filename}",
            progress_callback=on_progress,
            cancel_event=cancel_event,
            force_document=force_document,
        )

        if sent_msg and hasattr(sent_msg, "id"):
            await db.add_channel_file(filename, total_size, int(channel_id), sent_msg.id)

        delivered_to_private = False
        if target_user and str(target_user) != str(channel_id) and sent_msg and hasattr(sent_msg, "id") and bot:
            try:
                await bot.copy_message(
                    chat_id=target_user,
                    from_chat_id=channel_id,
                    message_id=sent_msg.id,
                )
                delivered_to_private = True
            except Exception as e:
                logger.warning("No se pudo copiar el mensaje al chat privado %s: %s", target_user, e)

        await db.update_task(task_id, status="done", finished_at=datetime.now().isoformat())
        if bot and status_message_id:
            dest_desc = "al canal y entregado en tu chat privado" if delivered_to_private else "al canal"
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=status_message_id,
                    text=f"✅ ¡Archivo <b>{html.escape(filename)}</b> subido con éxito {dest_desc}!",
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass
    except asyncio.CancelledError:
        await db.update_task(task_id, status="cancelled", finished_at=datetime.now().isoformat())
        if bot and status_message_id:
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=status_message_id,
                    text=f"🚫 Subida de <b>{html.escape(filename)}</b> cancelada.",
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass
    except Exception as e:
        await db.update_task(task_id, status="error", error=str(e), finished_at=datetime.now().isoformat())
        if bot and status_message_id:
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=status_message_id,
                    text=f"❌ Error al subir <b>{html.escape(filename)}</b>: {html.escape(str(e))}",
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass
    finally:
        manager.unregister_upload(str(task_id))
        bot_data.get("upload_progress", {}).pop(task_id, None)
        bot_data.get("active_upload_tasks", {}).pop(task_id, None)


_IMAGE_UPLOAD_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


@authorized_only
async def fm_upload_entry(update, context):
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":", 3)
    folder_key, token = parts[2], parts[3]
    resolved = keyboards.resolve_token(token)
    if not resolved:
        await query.answer("Elemento no encontrado.", show_alert=True)
        return
    relpath = resolved[1]

    manager = context.application.bot_data.get("userbot_manager")
    if not manager or not await manager.is_connected():
        await query.answer(
            "⚠️ El Userbot no está conectado.\n\nConéctalo desde el menú 🤖 Userbot para subir archivos a Telegram.",
            show_alert=True,
        )
        return

    try:
        _base, target = filemanager.resolve_path(folder_key, relpath)
    except filemanager.PathError as e:
        await query.answer(str(e), show_alert=True)
        return

    if not target.is_file():
        await query.answer("El archivo no existe.", show_alert=True)
        return

    if target.suffix.lower() in _IMAGE_UPLOAD_EXTS:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("📷 Como foto (HD)", callback_data=f"fm:uploadas:photo:{folder_key}:{token}"),
            InlineKeyboardButton("📄 Como archivo", callback_data=f"fm:uploadas:doc:{folder_key}:{token}"),
        ], [
            InlineKeyboardButton("❌ Cancelar", callback_data=f"fm:file:{folder_key}:{token}"),
        ]])
        await query.edit_message_text(
            f"🖼️ <b>{html.escape(target.name)}</b>\n\n¿Cómo quieres enviarla a Telegram?",
            parse_mode=ParseMode.HTML,
            reply_markup=kb,
        )
        return

    await _start_upload(query, context, folder_key, relpath, force_document=False)


@authorized_only
async def fm_upload_as(update, context):
    query = update.callback_query
    await query.answer()
    _, _, choice, folder_key, token = query.data.split(":", 4)
    resolved = keyboards.resolve_token(token)
    if not resolved:
        await query.answer("Elemento no encontrado.", show_alert=True)
        return
    await _start_upload(query, context, folder_key, resolved[1], force_document=(choice == "doc"))


async def _start_upload(query, context, folder_key: str, relpath: str, force_document: bool):
    manager = context.application.bot_data.get("userbot_manager")
    try:
        _base, target = filemanager.resolve_path(folder_key, relpath)
    except filemanager.PathError as e:
        await query.answer(str(e), show_alert=True)
        return
    if not target.is_file():
        await query.answer("El archivo no existe.", show_alert=True)
        return

    file_size = target.stat().st_size
    size_str = filemanager.human_size(file_size)
    chat_id = query.message.chat_id
    user_id = query.from_user.id

    task_id = await db.create_task(
        kind="upload",
        filename=target.name,
        dest_folder="Telegram",
        dest_path=str(target),
        status="downloading",
        total_size=file_size,
        requested_by=user_id,
        source_chat_id=chat_id,
        started_at=datetime.now().isoformat(),
    )

    status_text = (
        f"📤 <b>Subiendo a Telegram</b>\n\n"
        f"• <b>Archivo:</b> <code>{html.escape(target.name)}</code>\n"
        f"• <b>Tamaño:</b> <code>{size_str}</code>\n"
        f"• <b>Progreso:</b> <code>0.0%</code>\n\n"
        f"<i>Iniciando transferencia con Userbot...</i>"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("❌ Cancelar subida", callback_data=f"fm:cancelup:{task_id}")
    ]])

    status_msg = await query.edit_message_text(
        status_text,
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )

    await db.update_task(
        task_id,
        progress_chat_id=status_msg.chat_id,
        progress_message_id=status_msg.message_id,
    )

    async_task = asyncio.create_task(
        run_file_upload(
            context=context,
            task_id=task_id,
            chat_id=chat_id,
            status_message_id=status_msg.message_id,
            file_path=str(target),
            filename=target.name,
            total_size=file_size,
            user_id=user_id,
            force_document=force_document,
        )
    )
    context.application.bot_data.setdefault("active_upload_tasks", {})[task_id] = async_task


@authorized_only
async def fm_cancel_upload(update, context):
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    task_id = int(parts[2])

    manager = context.application.bot_data.get("userbot_manager")
    if manager:
        manager.cancel_upload(str(task_id))

    active = context.application.bot_data.get("active_upload_tasks", {})
    running = active.get(task_id)
    if running:
        running.cancel()
    else:
        await db.update_task(task_id, status="cancelled", finished_at=datetime.now().isoformat())

    await query.answer("Cancelando subida...", show_alert=False)
    query = update.callback_query
    _, _, folder_key, token = query.data.split(":", 3)
    relpath = keyboards.resolve_token(token)[1]
    info = filemanager.get_info(folder_key, relpath)
    text = f"{info['name']}\n" + ("Tipo: Carpeta" if info["is_dir"] else f"Tamaño: {info['size']}")
    await query.answer(text, show_alert=True)


@authorized_only
async def fm_delete_confirm(update, context):
    query = update.callback_query
    await query.answer()
    _, _, folder_key, token = query.data.split(":", 3)
    kb = [[
        InlineKeyboardButton("✅ Sí, eliminar", callback_data=f"fm:delete:{folder_key}:{token}"),
        InlineKeyboardButton("❌ Cancelar", callback_data=f"fm:file:{folder_key}:{token}"),
    ]]
    await query.edit_message_text(
        "¿Seguro que quieres eliminarlo? Esta acción no se puede deshacer.",
        reply_markup=InlineKeyboardMarkup(kb),
    )


@authorized_only
async def fm_delete(update, context):
    query = update.callback_query
    _, _, folder_key, token = query.data.split(":", 3)
    relpath = keyboards.resolve_token(token)[1]
    parent = _parent_of(relpath)
    try:
        filemanager.delete(folder_key, relpath)
        filemanager.invalidate_dir_size_cache(folder_key, parent)
        await query.answer("Eliminado ✅")
    except filemanager.PathError as e:
        await query.answer(str(e), show_alert=True)

    text, kb = await render_folder(folder_key, parent)
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


@authorized_only
async def fm_rename_entry(update, context):
    query = update.callback_query
    await query.answer()
    _, _, folder_key, token = query.data.split(":", 3)
    relpath = keyboards.resolve_token(token)[1]
    context.user_data["pending_action"] = {"type": "rename", "folder_key": folder_key, "relpath": relpath}
    await query.edit_message_text(f"✏️ Envía el nuevo nombre para <b>{html.escape(Path(relpath).name)}</b>:", parse_mode=ParseMode.HTML)


@authorized_only
async def fm_mkdir_entry(update, context):
    query = update.callback_query
    await query.answer()
    _, _, folder_key, token = query.data.split(":", 3)
    relpath = keyboards.resolve_token(token)[1]
    context.user_data["pending_action"] = {"type": "mkdir", "folder_key": folder_key, "relpath": relpath}
    await query.edit_message_text("➕ Envía el nombre de la nueva carpeta:")


async def handle_pending_text(update, context) -> bool:
    pending = context.user_data.get("pending_action")
    if not pending:
        return False

    text_in = update.effective_message.text.strip()
    folder_key = pending["folder_key"]
    relpath = pending["relpath"]

    try:
        if pending["type"] == "rename":
            filemanager.rename(folder_key, relpath, text_in)
            filemanager.invalidate_dir_size_cache(folder_key, _parent_of(relpath))
            await update.effective_message.reply_text("✅ Renombrado correctamente.")
        elif pending["type"] == "mkdir":
            filemanager.mkdir(folder_key, relpath, text_in)
            filemanager.invalidate_dir_size_cache(folder_key, relpath)
            await update.effective_message.reply_text("✅ Carpeta creada correctamente.")
    except filemanager.PathError as e:
        await update.effective_message.reply_text(f"⚠️ {e}")
    except FileExistsError:
        await update.effective_message.reply_text("⚠️ Ya existe un archivo o carpeta con ese nombre.")
    except Exception as e:
        await update.effective_message.reply_text(f"⚠️ Error: {e}")
    finally:
        context.user_data.pop("pending_action", None)

    show_path = relpath if pending["type"] == "mkdir" else _parent_of(relpath)
    text, kb = await render_folder(folder_key, show_path)
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    return True


# ---------------------------------------------------------------------------
# Copiar / mover (19.0)
# ---------------------------------------------------------------------------
_POLICY_LABELS = {
    "skip": ("Omitir", "Skip"),
    "replace": ("Reemplazar", "Replace"),
    "rename": ("Renombrar", "Rename"),
}


def _cp_state(context) -> dict:
    return context.user_data.setdefault("cp", {})


async def _render_cp_picker(query, context, dst_folder: str, dst_rel: str):
    st = _cp_state(context)
    st["dst_folder"], st["dst_rel"] = dst_folder, dst_rel
    dirs, _files = filemanager.list_dir(dst_folder, dst_rel)
    kb = []
    for d in dirs[:40]:
        rel = f"{dst_rel}/{d.name}" if dst_rel else d.name
        token = keyboards.token_for(dst_folder, rel)
        name = d.name if len(d.name) <= 40 else d.name[:37] + "..."
        kb.append([InlineKeyboardButton(f"📁 {name}", callback_data=f"fm:cpnav:{dst_folder}:{token}")])
    pol = st.get("policy", "skip")
    mv = st.get("move", False)
    kb.append([
        InlineKeyboardButton(L("Si existe: ", "If exists: ") + L(*_POLICY_LABELS[pol]), callback_data="fm:cppol"),
        InlineKeyboardButton(L("♻️ Mover", "♻️ Move") + (" ✅" if mv else " ⬜"), callback_data="fm:cpmv"),
    ])
    kb.append([InlineKeyboardButton(L("✅ Copiar aquí", "✅ Copy here") if not mv else L("✅ Mover aquí", "✅ Move here"),
                                    callback_data="fm:cpgo")])
    nav = []
    if dst_rel:
        nav.append(InlineKeyboardButton("⬅️ " + L("Atrás", "Back"), callback_data=f"fm:cpnav:{dst_folder}:{keyboards.token_for(dst_folder, _parent_of(dst_rel))}"))
    else:
        nav.append(InlineKeyboardButton("⬅️ " + L("Raíz", "Root"), callback_data="fm:cproots"))
    nav.append(InlineKeyboardButton("✖️ " + L("Cancelar", "Cancel"), callback_data="fm:cpcancel"))
    kb.append(nav)
    n = len(st.get("src_paths", []))
    label = f"{dst_folder}/{dst_rel}" if dst_rel else dst_folder
    text = L(f"📋 Destino para {n} elemento(s):\n<b>{html.escape(label)}</b>",
             f"📋 Destination for {n} item(s):\n<b>{html.escape(label)}</b>")
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))


@authorized_only
async def fm_cp_start(update, context):
    query = update.callback_query
    await query.answer()
    _, _, folder_key, token = query.data.split(":", 3)
    relpath = keyboards.resolve_token(token)[1]
    context.user_data["cp"] = {"src_folder": folder_key, "src_paths": [relpath], "policy": "skip", "move": False}
    await fm_cp_roots(update, context)


@authorized_only
async def fm_cp_roots(update, context):
    query = update.callback_query
    await query.answer()
    kb = [[InlineKeyboardButton(name, callback_data=f"fm:cpnav:{name}:{keyboards.token_for(name, '')}")]
          for name in config.FOLDERS]
    kb.append([InlineKeyboardButton("✖️ " + L("Cancelar", "Cancel"), callback_data="fm:cpcancel")])
    await query.edit_message_text(L("📋 Elige la carpeta de destino:", "📋 Choose the destination folder:"),
                                  reply_markup=InlineKeyboardMarkup(kb))


@authorized_only
async def fm_cp_nav(update, context):
    query = update.callback_query
    await query.answer()
    _, _, folder_key, token = query.data.split(":", 3)
    rel = keyboards.resolve_token(token)[1]
    try:
        await _render_cp_picker(query, context, folder_key, rel)
    except filemanager.PathError as e:
        await query.edit_message_text(f"⚠️ {e}")


@authorized_only
async def fm_cp_toggle(update, context):
    query = update.callback_query
    await query.answer()
    st = _cp_state(context)
    if query.data.endswith("cppol"):
        order = ["skip", "replace", "rename"]
        st["policy"] = order[(order.index(st.get("policy", "skip")) + 1) % 3]
    else:
        st["move"] = not st.get("move", False)
    await _render_cp_picker(query, context, st.get("dst_folder", ""), st.get("dst_rel", ""))


@authorized_only
async def fm_cp_cancel(update, context):
    query = update.callback_query
    await query.answer()
    context.user_data.pop("cp", None)
    await query.edit_message_text(L("Operación cancelada.", "Operation cancelled."))


def _fmt_cp(job: dict) -> str:
    total = job["total"] or 1
    pct = min(100, int(job["done"] * 100 / total))
    elapsed = max(1, time.time() - job["started"])
    speed = filemanager.human_size(job["done"] / elapsed) + "/s"
    verb = L("Moviendo", "Moving") if job["move"] else L("Copiando", "Copying")
    return (f"📋 {verb} → <b>{html.escape(job['dest'])}</b>\n"
            f"{pct}% · {filemanager.human_size(job['done'])} / {filemanager.human_size(job['total'])} · {speed}\n"
            f"<code>{html.escape(job['current'][:60])}</code>")


@authorized_only
async def fm_cp_go(update, context):
    query = update.callback_query
    await query.answer()
    st = _cp_state(context)
    if not st.get("src_paths"):
        await query.edit_message_text(L("La operación ha caducado.", "The operation has expired."))
        return
    try:
        job_id = await filemanager.start_copy(st["src_folder"], st["src_paths"], st["dst_folder"],
                                              st.get("dst_rel", ""), st.get("policy", "skip"), st.get("move", False))
    except filemanager.PathError as e:
        await query.edit_message_text(f"⚠️ {e}")
        return
    context.user_data.pop("cp", None)
    job = filemanager.COPY_JOBS[job_id]
    cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("✖️ " + L("Cancelar", "Cancel"), callback_data=f"fm:cpstop:{job_id}")]])
    context.application.create_task(_cp_progress_loop(query, job, cancel_kb))


async def _cp_progress_loop(query, job, cancel_kb):
    last = ""
    while not job["finished"]:
        text = _fmt_cp(job)
        if text != last:
            try:
                await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=cancel_kb)
            except Exception:
                pass
            last = text
        await asyncio.sleep(2)
    if job.get("cancelled"):
        final = L("⛔ Operación cancelada.", "⛔ Operation cancelled.")
    else:
        done = L("movidos", "moved") if job["move"] else L("copiados", "copied")
        final = f"✅ {job['copied']} {L('elemento(s)', 'item(s)')} {done} → <b>{html.escape(job['dest'])}</b>"
        if job["skipped"]:
            final += "\n" + L(f"Omitidos: {job['skipped']}", f"Skipped: {job['skipped']}")
        if job["errors"]:
            final += "\n⚠️ " + html.escape("; ".join(job["errors"][:3]))
    await query.edit_message_text(final, parse_mode=ParseMode.HTML)


@authorized_only
async def fm_cp_stop(update, context):
    query = update.callback_query
    job = filemanager.COPY_JOBS.get(int(query.data.rsplit(":", 1)[1]))
    if job:
        job["cancel"] = True
    await query.answer(L("Cancelando…", "Cancelling…"))
