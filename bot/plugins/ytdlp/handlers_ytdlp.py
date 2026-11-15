import asyncio
from datetime import datetime
import os
import shutil
import uuid
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest

import config
import db
import filemanager
import ytdlp_downloader
from rich_ui import esc

TEMP_YTDLP_DIR = Path(config.CONFIG_DIR) / "temp_ytdlp"

_sessions = {}


def _get_session(session_id: str) -> dict | None:
    return _sessions.get(session_id)


def _cleanup_session(session_id: str):
    _sessions.pop(session_id, None)


async def handle_ytdlp_url(update: Update, context, url: str):
    msg = update.effective_message
    status_msg = await msg.reply_text("🔍 Analizando vídeo con yt-dlp...", parse_mode=ParseMode.HTML)

    try:
        info = await asyncio.to_thread(ytdlp_downloader.extract_video_info, url)
    except Exception as e:
        await status_msg.edit_text(f"❌ No se pudo obtener información del vídeo: {esc(e)}")
        return

    session_id = uuid.uuid4().hex[:8]
    _sessions[session_id] = {
        "url": url,
        "title": info["title"],
        "duration_str": info["duration_str"],
        "options": info["options"],
        "dest": None,
        "selected_opt": None,
        "user_id": update.effective_user.id,
    }

    title_clean = info["title"][:80]
    text = (
        f"🎬 <b>{esc(title_clean)}</b>\n"
        f"⏱ Duración: <code>{esc(info['duration_str'] or 'Desconocida')}</code>\n\n"
        "📥 <b>¿A dónde deseas descargar este contenido?</b>"
    )

    kb = [
        [InlineKeyboardButton("📱 A este chat de Telegram", callback_data=f"ytdl:dest:tg:{session_id}")],
        [InlineKeyboardButton("📁 Guardar en el NAS", callback_data=f"ytdl:dest:nas:{session_id}")],
        [InlineKeyboardButton("❌ Cancelar", callback_data=f"ytdl:cancel:{session_id}")],
    ]

    await status_msg.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)


async def ytdl_dest_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    target = parts[2]
    session_id = parts[3]

    session = _get_session(session_id)
    if not session:
        await query.edit_message_text("⚠️ La sesión de descarga ha expirado. Vuelve a enviar el enlace.")
        return

    session["dest"] = target
    text = (
        f"🎬 <b>{esc(session['title'][:80])}</b>\n\n"
        "🎞 <b>Elige la resolución / formato de descarga:</b>"
    )

    kb = []
    for idx, opt in enumerate(session["options"]):
        kb.append([InlineKeyboardButton(opt["label"], callback_data=f"ytdl:opt:{session_id}:{idx}")])
    kb.append([InlineKeyboardButton("❌ Cancelar", callback_data=f"ytdl:cancel:{session_id}")])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)


async def ytdl_opt_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    session_id = parts[2]
    opt_idx = int(parts[3])

    session = _get_session(session_id)
    if not session:
        await query.edit_message_text("⚠️ La sesión de descarga ha expirado.")
        return

    selected_opt = session["options"][opt_idx]
    session["selected_opt"] = selected_opt

    if session["dest"] == "tg":
        await query.edit_message_text(
            f"⏳ Descargando <b>{esc(session['title'][:60])}</b> ({esc(selected_opt['quality'])}) para enviarlo a Telegram...",
            parse_mode=ParseMode.HTML,
        )
        asyncio.create_task(_download_and_send_tg(context, session, query.message.chat_id, query.message.message_id))
        _cleanup_session(session_id)
        return

    kb = [
        [InlineKeyboardButton(f"📁 {name}", callback_data=f"ytdl:folder:{session_id}:{name}")]
        for name in config.FOLDERS
    ]
    kb.append([InlineKeyboardButton("❌ Cancelar", callback_data=f"ytdl:cancel:{session_id}")])

    await query.edit_message_text(
        f"💾 Selecciona la carpeta del NAS donde guardar <b>{esc(session['title'][:60])}</b>:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode=ParseMode.HTML,
    )


async def ytdl_folder_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    session_id = parts[2]
    folder_name = parts[3]

    session = _get_session(session_id)
    if not session:
        await query.edit_message_text("⚠️ La sesión de descarga ha expirado.")
        return

    selected_opt = session["selected_opt"]
    dest_dir = config.FOLDERS.get(folder_name) or config.FOLDERS[config.default_download_folder()]

    ok, err_msg = filemanager.check_disk_space(folder_name, selected_opt.get("size_bytes", 0))
    if not ok:
        await query.edit_message_text(err_msg, parse_mode=ParseMode.HTML)
        _cleanup_session(session_id)
        return

    await query.edit_message_text(
        f"⬇️ Descargando <b>{esc(session['title'][:60])}</b> al NAS (<code>{esc(folder_name)}</code>)...\n"
        "Recibirás un aviso cuando se complete.",
        parse_mode=ParseMode.HTML,
    )

    asyncio.create_task(
        _download_to_nas(context, session, dest_dir, folder_name, query.message.chat_id, query.message.message_id)
    )
    _cleanup_session(session_id)


async def ytdl_cancel_callback(update: Update, context):
    query = update.callback_query
    await query.answer("Cancelado")
    parts = query.data.split(":")
    if len(parts) >= 3:
        _cleanup_session(parts[2])
    await query.edit_message_text("❌ Descarga de vídeo cancelada.")


async def _download_and_send_tg(context, session: dict, chat_id: int, status_message_id: int):
    url = session["url"]
    selected_opt = session["selected_opt"]
    temp_dir = TEMP_YTDLP_DIR / uuid.uuid4().hex[:6]
    temp_dir.mkdir(parents=True, exist_ok=True)

    last_update = [0]

    async def on_progress(downloaded, total, speed):
        import time
        now = time.time()
        if now - last_update[0] >= config.PROGRESS_EDIT_INTERVAL:
            last_update[0] = now
            pct = (downloaded / total * 100) if total else 0
            mb_c, mb_t = downloaded / (1024 * 1024), total / (1024 * 1024) if total else 0
            speed_mb = speed / (1024 * 1024) if speed else 0
            txt = (
                f"⬇️ Descargando: <b>{esc(session['title'][:60])}</b>\n"
                f"{pct:.1f}% ({mb_c:.1f}MB / {mb_t:.1f}MB)\n"
                f"🚀 {speed_mb:.2f} MB/s"
            )
            asyncio.create_task(_safe_edit_text(context, chat_id, status_message_id, txt))

    try:
        file_path = await ytdlp_downloader.download_video(
            url,
            selected_opt["format_spec"],
            str(temp_dir),
            is_audio=selected_opt["is_audio"],
            progress_callback=on_progress,
        )

        file_size = os.path.getsize(file_path)
        size_str = filemanager.human_size(file_size)
        MAX_BOT_API_SIZE = 50 * 1024 * 1024
        sent_success = False

        if file_size <= MAX_BOT_API_SIZE:
            await _safe_edit_text(context, chat_id, status_message_id, "📤 Subiendo archivo a Telegram...")
            with open(file_path, "rb") as f:
                if selected_opt["is_audio"]:
                    await context.bot.send_audio(
                        chat_id=chat_id,
                        audio=f,
                        title=session["title"][:60],
                        filename=os.path.basename(file_path),
                    )
                else:
                    await context.bot.send_video(
                        chat_id=chat_id,
                        video=f,
                        caption=f"🎬 {session['title'][:100]}",
                        supports_streaming=True,
                    )
            sent_success = True
            await _safe_edit_text(context, chat_id, status_message_id, "✅ ¡Contenido enviado con éxito a Telegram!")
        else:
            userbot_manager = context.bot_data.get("userbot_manager")
            has_userbot = False
            if userbot_manager:
                try:
                    has_userbot = await userbot_manager.is_connected()
                except Exception:
                    has_userbot = False

            if has_userbot:
                await _safe_edit_text(
                    context,
                    chat_id,
                    status_message_id,
                    f"📤 El archivo supera los 50 MB (<code>{esc(size_str)}</code>).\n"
                    "Subiendo a Telegram mediante <b>Userbot</b> (soporte hasta 2 GB)...",
                )
                last_ub_update = [0]

                async def on_ub_progress(current, total):
                    import time
                    now = time.time()
                    if now - last_ub_update[0] >= config.PROGRESS_EDIT_INTERVAL:
                        last_ub_update[0] = now
                        pct = (current / total * 100) if total else 0
                        mb_c = current / (1024 * 1024)
                        mb_t = total / (1024 * 1024) if total else 0
                        txt = (
                            f"📤 Subiendo vía Userbot: <b>{esc(session['title'][:60])}</b>\n"
                            f"{pct:.1f}% ({mb_c:.1f}MB / {mb_t:.1f}MB)"
                        )
                        asyncio.create_task(_safe_edit_text(context, chat_id, status_message_id, txt))

                try:
                    await userbot_manager.send_file_to_chat(
                        chat_id=chat_id,
                        file_path=file_path,
                        caption=f"🎬 {session['title'][:100]}",
                        progress_callback=on_ub_progress,
                        is_audio=selected_opt["is_audio"],
                        is_video=not selected_opt["is_audio"],
                    )
                    sent_success = True
                    await _safe_edit_text(
                        context,
                        chat_id,
                        status_message_id,
                        f"✅ ¡Archivo enviado con éxito a Telegram vía Userbot! (<code>{esc(size_str)}</code>)",
                    )
                except Exception:
                    has_userbot = False

            if not sent_success:
                nas_folder_name = config.default_download_folder()
                nas_dir = config.FOLDERS[nas_folder_name]
                os.makedirs(nas_dir, exist_ok=True)
                base_name = os.path.basename(file_path)
                dest_file = os.path.join(nas_dir, base_name)

                count = 1
                name_stem, name_ext = os.path.splitext(base_name)
                while os.path.exists(dest_file):
                    dest_file = os.path.join(nas_dir, f"{name_stem}_{count}{name_ext}")
                    count += 1

                shutil.move(file_path, dest_file)
                saved_final_name = os.path.basename(dest_file)

                msg_text = (
                    f"⚠️ <b>Archivo superior a 50 MB</b> (<code>{esc(size_str)}</code>)\n\n"
                    "La API estándar de bots de Telegram no permite enviar archivos que superen los 50 MB y el Userbot no está conectado.\n\n"
                    f"💾 <b>El archivo ha sido guardado de forma segura en el NAS:</b>\n"
                    f"• Carpeta: <code>{esc(nas_folder_name)}</code>\n"
                    f"• Archivo: <code>{esc(saved_final_name)}</code>\n"
                    f"• Ruta: <code>{esc(dest_file)}</code>\n\n"
                    "💡 <i>Puedes conectar tu Userbot desde el menú 🤖 Userbot para enviar archivos de hasta 2 GB directamente a Telegram.</i>"
                )
                await _safe_edit_text(context, chat_id, status_message_id, msg_text)

                try:
                    await db.create_task(
                        kind="ytdl",
                        url=url,
                        filename=saved_final_name,
                        dest_folder=nas_folder_name,
                        dest_path=dest_file,
                        status="done",
                        total_size=file_size,
                        requested_by=session.get("user_id"),
                        finished_at=datetime.now().isoformat(),
                    )
                except Exception:
                    pass
                return

        try:
            await db.create_task(
                kind="ytdl",
                url=url,
                filename=os.path.basename(file_path),
                dest_folder="Telegram",
                dest_path=file_path,
                status="done",
                total_size=file_size,
                requested_by=session.get("user_id"),
                finished_at=datetime.now().isoformat(),
            )
        except Exception:
            pass

    except Exception as e:
        await _safe_edit_text(context, chat_id, status_message_id, f"❌ Error al procesar vídeo: {esc(e)}")
        try:
            await db.create_task(
                kind="ytdl",
                url=url,
                filename=session.get("title", "video"),
                dest_folder="Telegram",
                dest_path=str(temp_dir),
                status="error",
                error=str(e),
                requested_by=session.get("user_id"),
                finished_at=datetime.now().isoformat(),
            )
        except Exception:
            pass
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


async def _download_to_nas(context, session: dict, dest_dir: str, folder_name: str, chat_id: int, status_message_id: int):
    url = session["url"]
    selected_opt = session["selected_opt"]
    last_update = [0]

    async def on_progress(downloaded, total, speed):
        import time
        now = time.time()
        if now - last_update[0] >= config.PROGRESS_EDIT_INTERVAL:
            last_update[0] = now
            pct = (downloaded / total * 100) if total else 0
            mb_c, mb_t = downloaded / (1024 * 1024), total / (1024 * 1024) if total else 0
            speed_mb = speed / (1024 * 1024) if speed else 0
            txt = (
                f"⬇️ Descargando al NAS (<code>{esc(folder_name)}</code>): <b>{esc(session['title'][:60])}</b>\n"
                f"{pct:.1f}% ({mb_c:.1f}MB / {mb_t:.1f}MB) — 🚀 {speed_mb:.2f} MB/s"
            )
            asyncio.create_task(_safe_edit_text(context, chat_id, status_message_id, txt))

    try:
        file_path = await ytdlp_downloader.download_video(
            url,
            selected_opt["format_spec"],
            dest_dir,
            is_audio=selected_opt["is_audio"],
            progress_callback=on_progress,
        )
        saved_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        size_str = filemanager.human_size(file_size)
        await _safe_edit_text(
            context,
            chat_id,
            status_message_id,
            f"✅ <b>Descarga completada en el NAS</b>\n\n"
            f"• Archivo: <code>{esc(saved_name)}</code>\n"
            f"• Carpeta: <code>{esc(folder_name)}</code>\n"
            f"• Tamaño: <code>{esc(size_str)}</code>",
        )
        try:
            await db.create_task(
                kind="ytdl",
                url=url,
                filename=saved_name,
                dest_folder=folder_name,
                dest_path=file_path,
                status="done",
                total_size=file_size,
                requested_by=session.get("user_id"),
                finished_at=datetime.now().isoformat(),
            )
        except Exception:
            pass
    except Exception as e:
        await _safe_edit_text(context, chat_id, status_message_id, f"❌ Error al descargar al NAS: {esc(e)}")
        try:
            await db.create_task(
                kind="ytdl",
                url=url,
                filename=session.get("title", "video"),
                dest_folder=folder_name,
                dest_path=dest_dir,
                status="error",
                error=str(e),
                requested_by=session.get("user_id"),
                finished_at=datetime.now().isoformat(),
            )
        except Exception:
            pass


async def _safe_edit_text(context, chat_id: int, message_id: int, text: str):
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode=ParseMode.HTML,
        )
    except BadRequest:
        pass
    except Exception:
        pass


async def ytdl_command(update: Update, context):
    text = update.effective_message.text or ""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await update.effective_message.reply_text("Uso: /ytdl <enlace de YouTube, TikTok, Twitter...>")
        return
    url = parts[1].strip()
    await handle_ytdlp_url(update, context, url)
