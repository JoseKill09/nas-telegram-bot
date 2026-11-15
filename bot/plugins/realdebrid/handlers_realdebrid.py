import asyncio
import logging
from datetime import datetime, timedelta
import uuid

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

import archive_utils
import db
import torrent_clients
from i18n import L
import real_debrid
from rich_ui import esc, progress_card, r_h, r_table, r_footer, rich
from utils import authorized_only, get_command_payload

logger = logging.getLogger(__name__)

rd_torrent_states: dict[str, dict] = {}


@authorized_only
async def torrent_command(update, context):
    payload = get_command_payload(update).strip()
    magnets = [line.strip() for line in payload.splitlines() if line.strip().startswith("magnet:?")]
    if not magnets and payload.startswith("magnet:?"):
        magnets = [payload]

    if not magnets:
        await update.effective_message.reply_text("Uso: /torrent <enlace magnet>")
        return

    for magnet in magnets:
        await handle_magnet(update, context, magnet)


def _file_list_text(files, selected, provider: str = "realdebrid") -> str:
    rows = []
    total_sel = 0
    for i, f in enumerate(files):
        name = f["path"].split("/")[-1]
        is_sel = f["id"] in selected
        if is_sel:
            total_sel += f["bytes"]
        rows.append([
            "✅" if is_sel else "⬜",
            f"<b>{i + 1}</b>",
            esc(name),
            esc(real_debrid.human_size(f["bytes"])),
        ])
    if torrent_clients.is_client(provider):
        note = L(f"{torrent_clients.label(provider)} descargará directamente al NAS solo los archivos marcados.",
                 f"{torrent_clients.label(provider)} will download only the selected files straight to the NAS.")
    elif provider == "torbox":
        note = "Torrent en caché de TorBox: cada archivo marcado se descargará al NAS por separado."
    else:
        note = ("Real-Debrid entregará varios archivos en un comprimido: te preguntaré si quieres descomprimirlo."
                if len(selected) > 1 else "Selecciona los archivos que quieres descargar.")
    return rich(
        r_h("Archivos del torrent", 2, "📦"),
        r_table(rows, header=["", "#", "Archivo", "Tamaño"],
                caption=f"{len(selected)} de {len(files)} seleccionados · {esc(real_debrid.human_size(total_sel))}"),
        r_footer(note),
    )


def _file_selection_keyboard(torrent_id, files, selected) -> InlineKeyboardMarkup:
    kb = []
    row = []
    for i, f in enumerate(files):
        label = f"{'✅' if f['id'] in selected else '⬜'} {i + 1}"
        row.append(InlineKeyboardButton(label, callback_data=f"rdfile:{torrent_id}:{f['id']}"))
        if len(row) == 3:
            kb.append(row)
            row = []
    if row:
        kb.append(row)

    kb.append([
        InlineKeyboardButton("✅ Todo", callback_data=f"rdall:{torrent_id}"),
        InlineKeyboardButton("❌ Ninguno", callback_data=f"rdnone:{torrent_id}"),
    ])
    kb.append([
        InlineKeyboardButton("📥 Continuar", callback_data=f"rdconfirm:{torrent_id}"),
        InlineKeyboardButton("🚫 Cancelar", callback_data=f"rdcancelsel:{torrent_id}"),
    ])
    return InlineKeyboardMarkup(kb)


async def _edit(context, chat_id, message_id, text, markup=None, html=False):
    try:
        await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup,
                                            parse_mode=ParseMode.HTML if html else None)
    except Exception:
        pass


async def add_magnet_get_files(token: str, magnet: str, requested_by: int | None = None) -> dict:
    torrent_id = await real_debrid.add_magnet(token, magnet)
    return await _finish_add_torrent(token, torrent_id, requested_by)


async def add_torrent_file_get_files(token: str, torrent_bytes: bytes, requested_by: int | None = None) -> dict:
    torrent_id = await real_debrid.add_torrent(token, torrent_bytes)
    return await _finish_add_torrent(token, torrent_id, requested_by)


async def _finish_add_torrent(token: str, torrent_id: str, requested_by: int | None = None) -> dict:
    info = await real_debrid.get_torrent_info(token, torrent_id)

    files = info.get("files", [])
    if not files:
        raise ValueError("Real-Debrid no encontró archivos en ese torrent.")

    largest = max(files, key=lambda f: f["bytes"])
    selected = {largest["id"]}

    rd_torrent_states[torrent_id] = {
        "provider": "realdebrid",
        "files": files,
        "selected": selected,
        "token": token,
        "chat_id": requested_by,
        "message_id": None,
        "torrent_name": info.get("filename", "torrent"),
        "requested_by": requested_by,
        "extract_after": False,
        "last_snapshot": {"status": info.get("status", "queued"), "progress": 0, "speed": 0, "seeders": 0},
    }
    return rd_torrent_states[torrent_id] | {"torrent_id": torrent_id}


@authorized_only
async def handle_magnet(update, context, magnet: str):
    import handlers_torbox
    status_msg = await update.effective_message.reply_text("⏳ Procesando magnet...")
    await handlers_torbox.offer_source(status_msg, "magnet", magnet, update.effective_user.id)


@authorized_only
async def rd_toggle_file(update, context):
    query = update.callback_query
    _, torrent_id, file_id = query.data.split(":")
    file_id = int(file_id)
    state = rd_torrent_states.get(torrent_id)
    if not state:
        await query.answer("Sesion expirada.", show_alert=True)
        return

    if file_id in state["selected"]:
        state["selected"].discard(file_id)
    else:
        state["selected"].add(file_id)

    await query.edit_message_text(
        _file_list_text(state["files"], state["selected"], state.get("provider", "realdebrid")),
        parse_mode=ParseMode.HTML,
        reply_markup=_file_selection_keyboard(torrent_id, state["files"], state["selected"]),
    )
    await query.answer()


@authorized_only
async def rd_select_all(update, context):
    query = update.callback_query
    torrent_id = query.data.split(":")[1]
    state = rd_torrent_states.get(torrent_id)
    if not state:
        await query.answer("Sesion expirada.", show_alert=True)
        return
    state["selected"] = {f["id"] for f in state["files"]}
    await query.edit_message_text(
        _file_list_text(state["files"], state["selected"], state.get("provider", "realdebrid")),
        parse_mode=ParseMode.HTML,
        reply_markup=_file_selection_keyboard(torrent_id, state["files"], state["selected"]),
    )
    await query.answer()


@authorized_only
async def rd_select_none(update, context):
    query = update.callback_query
    torrent_id = query.data.split(":")[1]
    state = rd_torrent_states.get(torrent_id)
    if not state:
        await query.answer("Sesion expirada.", show_alert=True)
        return
    state["selected"] = set()
    await query.edit_message_text(
        _file_list_text(state["files"], state["selected"], state.get("provider", "realdebrid")),
        parse_mode=ParseMode.HTML,
        reply_markup=_file_selection_keyboard(torrent_id, state["files"], state["selected"]),
    )
    await query.answer()


@authorized_only
async def rd_cancel_selection(update, context):
    query = update.callback_query
    await query.answer()
    torrent_id = query.data.split(":")[1]
    state = rd_torrent_states.pop(torrent_id, None)
    if state:
        if torrent_clients.is_client(state.get("provider")):
            import handlers_clients
            await handlers_clients.cancel(state)
        elif state.get("provider") == "torbox":
            import handlers_torbox
            await handlers_torbox.cancel(state)
        else:
            await real_debrid.delete_torrent(state["token"], torrent_id)
    await query.edit_message_text("🚫 Torrent cancelado.")


@authorized_only
async def rd_confirm_selection(update, context):
    query = update.callback_query
    torrent_id = query.data.split(":")[1]
    state = rd_torrent_states.get(torrent_id)
    if not state:
        await query.answer("Sesion expirada.", show_alert=True)
        return
    if state.get("select_files", True) and not state["selected"]:
        await query.answer("Selecciona al menos un archivo.", show_alert=True)
        return
    await query.answer()

    import handlers_downloads as h_dl
    auto = await h_dl.try_auto(context, f"T{torrent_id}", query)
    if auto:
        return
    await query.edit_message_text("Elige la carpeta destino:", reply_markup=await h_dl.dest_markup(f"T{torrent_id}"))


async def start_processing(context, torrent_id: str, dest_dir: str, dest_label: str,
                            chat_id: int | None = None, message_id: int | None = None,
                            extract_after: bool = False, requested_by: int | None = None,
                            schedule: str = "now"):
    state = rd_torrent_states.get(torrent_id)
    if not state:
        raise ValueError("Sesión de torrent expirada.")

    state["dest_folder"] = dest_label
    state["dest_path"] = dest_dir
    if chat_id is not None:
        state["chat_id"] = chat_id
    if message_id is not None:
        state["message_id"] = message_id
    if requested_by is not None:
        state["requested_by"] = requested_by
    if extract_after:
        state["extract_after"] = True
    if schedule and schedule != "now":
        state["schedule"] = schedule

    if torrent_clients.is_client(state.get("provider")):
        import handlers_clients
        if not state["selected"]:
            raise ValueError("Selecciona al menos un archivo.")
        state["monitor_task"] = asyncio.create_task(handlers_clients.run(context, torrent_id))
        return

    if state.get("provider") == "torbox":
        import handlers_torbox
        if state["select_files"] and not state["selected"]:
            raise ValueError("Selecciona al menos un archivo.")
        state["monitor_task"] = asyncio.create_task(handlers_torbox.run(context, torrent_id))
        return

    await real_debrid.select_files(state["token"], torrent_id, list(state["selected"]))
    state["monitor_task"] = asyncio.create_task(_monitor_torrent(context, torrent_id))


async def confirm_destination(context, query, torrent_id: str, dest_dir: str, dest_label: str):
    await query.edit_message_text("⏳ Preparando la descarga en el proveedor...")
    try:
        await start_processing(
            context, torrent_id, dest_dir, dest_label,
            chat_id=query.message.chat_id, message_id=query.message.message_id,
            requested_by=query.from_user.id if query.from_user else None,
        )
    except Exception as e:
        await query.edit_message_text(f"❌ Error al seleccionar archivos: {e}")
        rd_torrent_states.pop(torrent_id, None)


@authorized_only
async def rd_cancel_monitor(update, context):
    query = update.callback_query
    await query.answer()
    torrent_id = query.data.split(":")[1]
    state = rd_torrent_states.pop(torrent_id, None)
    if state:
        if torrent_clients.is_client(state.get("provider")):
            import handlers_clients
            await handlers_clients.cancel(state)
        elif state.get("provider") == "torbox":
            import handlers_torbox
            await handlers_torbox.cancel(state)
        else:
            task = state.get("monitor_task")
            if task:
                task.cancel()
            await real_debrid.delete_torrent(state["token"], torrent_id)
    try:
        await query.edit_message_text("🚫 Torrent cancelado.")
    except Exception:
        pass


rd_pending_extract: dict[str, dict] = {}


async def _ask_extract_for_resolved_file(context, chat_id, url, filename, dest_folder, dest_path, requested_by=None,
                                         client="realdebrid"):
    key = uuid.uuid4().hex[:10]
    rd_pending_extract[key] = {
        "url": url, "filename": filename, "dest_folder": dest_folder,
        "dest_path": dest_path, "chat_id": chat_id, "requested_by": requested_by or chat_id, "client": client,
    }
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Sí, descomprimir", callback_data=f"rdext:yes:{key}"),
        InlineKeyboardButton("❌ No, dejar así", callback_data=f"rdext:no:{key}"),
    ]])
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"📦 <b>{esc(filename)}</b>\n"
                "Este torrent se entregó como archivo comprimido (Real-Debrid junta varios "
                "archivos en uno solo). ¿Quieres descomprimirlo automáticamente al terminar la descarga?"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=kb,
        )
    except Exception:
        pass


@authorized_only
async def rd_extract_choice(update, context):
    query = update.callback_query
    await query.answer()
    _, choice, key = query.data.split(":", 2)
    info = rd_pending_extract.pop(key, None)
    if not info:
        await query.edit_message_text("⚠️ Esta solicitud ya expiró.")
        return

    import handlers_downloads as h_dl
    task_id = await h_dl.enqueue_link_task(
        context,
        url=info["url"],
        filename=info["filename"],
        dest_folder=info["dest_folder"],
        dest_path=info["dest_path"],
        chat_id=info["chat_id"],
        requested_by=info.get("requested_by"),
        client=info.get("client") or "realdebrid",
    )
    if choice == "yes":
        await db.update_task(task_id, extract_after=1)

    await query.edit_message_text(f"🕓 <b>{esc(info['filename'])}</b> añadido a la cola.", parse_mode=ParseMode.HTML)


async def _monitor_torrent(context, torrent_id: str):
    state = rd_torrent_states.get(torrent_id)
    if not state:
        return

    token = state["token"]
    chat_id = state["chat_id"]
    message_id = state["message_id"]
    req_by = state.get("requested_by") or chat_id
    pre_extract = state.get("extract_after", False)
    cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data=f"rdcancel:{torrent_id}")]])

    try:
        while True:
            try:
                info = await real_debrid.get_torrent_info(token, torrent_id)
            except Exception as e:
                await _edit(context, chat_id, message_id, f"❌ Error al consultar Real-Debrid: {e}")
                rd_torrent_states.pop(torrent_id, None)
                return

            status = info.get("status")

            if status == "downloading":
                progress = info.get("progress", 0)
                speed = info.get("speed", 0)
                seeders = info.get("seeders", 0)
                total_bytes = info.get("bytes", 0)
                if torrent_id in rd_torrent_states:
                    rd_torrent_states[torrent_id]["last_snapshot"] = {
                        "status": status, "progress": progress, "speed": speed,
                        "seeders": seeders, "total": total_bytes,
                    }
                text = progress_card(
                    "Descargando torrent en Real-Debrid", "⬇️", state["torrent_name"], progress, total_bytes, speed,
                    None, [("🌱 Seeders", str(seeders))],
                )
                await _edit(context, chat_id, message_id, text, markup=cancel_kb, html=True)
                await asyncio.sleep(5)

            elif status == "downloaded":
                links = info.get("links", [])
                if not links:
                    await _edit(context, chat_id, message_id, "⚠️ Real-Debrid termino pero no genero enlaces.")
                    rd_torrent_states.pop(torrent_id, None)
                    return

                await _edit(context, chat_id, message_id, "🔗 Resolviendo enlaces de descarga...")

                import handlers_downloads as h_dl
                created = 0
                failed_links = 0
                selected_count = len(state.get("selected") or [])
                bundled_by_rd = selected_count > 1 and len(links) < selected_count

                for link in links:
                    try:
                        data = await real_debrid.unrestrict_link(token, link)
                    except Exception as e:
                        logger.warning("Fallo al resolver enlace de Real-Debrid %s: %s", link, e)
                        failed_links += 1
                        continue
                    filename = data.get("filename") or "archivo"

                    if archive_utils.is_archive(filename) or bundled_by_rd:
                        if pre_extract:
                            task_id = await h_dl.enqueue_link_task(
                                context,
                                url=data["download"],
                                filename=filename,
                                dest_folder=state["dest_folder"],
                                dest_path=state["dest_path"],
                                chat_id=chat_id,
                                requested_by=req_by,
                                client="realdebrid",
                            )
                            update_kwargs = {"extract_after": 1}
                            sched_str = state.get("schedule")
                            if sched_str and sched_str != "now":
                                now = datetime.now(h_dl.LOCAL_TZ)
                                sched_dt = None
                                if sched_str == "1h":
                                    sched_dt = now + timedelta(hours=1)
                                elif sched_str == "2h":
                                    sched_dt = now + timedelta(hours=2)
                                elif sched_str == "4h":
                                    sched_dt = now + timedelta(hours=4)
                                elif sched_str.startswith("at:"):
                                    try:
                                        sched_dt = datetime.fromisoformat(sched_str[3:])
                                        if sched_dt.tzinfo is None:
                                            sched_dt = sched_dt.replace(tzinfo=h_dl.LOCAL_TZ)
                                    except ValueError:
                                        sched_dt = None
                                elif sched_str == "night":
                                    sched_dt = now.replace(hour=2, minute=0, second=0, microsecond=0)
                                    if sched_dt <= now:
                                        sched_dt += timedelta(days=1)
                                if sched_dt:
                                    update_kwargs["status"] = "scheduled"
                                    update_kwargs["scheduled_for"] = sched_dt.isoformat()
                            await db.update_task(task_id, **update_kwargs)
                            created += 1
                            continue
                        elif chat_id:
                            await _ask_extract_for_resolved_file(
                                context, chat_id, data["download"], filename, state["dest_folder"], state["dest_path"], requested_by=req_by,
                            )
                            created += 1
                            continue

                    task_id = await h_dl.enqueue_link_task(
                        context,
                        url=data["download"],
                        filename=filename,
                        dest_folder=state["dest_folder"],
                        dest_path=state["dest_path"],
                        chat_id=chat_id,
                        requested_by=req_by,
                        client="realdebrid",
                    )
                    update_kwargs = {}
                    if pre_extract:
                        update_kwargs["extract_after"] = 1
                    sched_str = state.get("schedule")
                    if sched_str and sched_str != "now":
                        now = datetime.now(h_dl.LOCAL_TZ)
                        sched_dt = None
                        if sched_str == "1h":
                            sched_dt = now + timedelta(hours=1)
                        elif sched_str == "2h":
                            sched_dt = now + timedelta(hours=2)
                        elif sched_str == "4h":
                            sched_dt = now + timedelta(hours=4)
                        elif sched_str.startswith("at:"):
                            try:
                                sched_dt = datetime.fromisoformat(sched_str[3:])
                                if sched_dt.tzinfo is None:
                                    sched_dt = sched_dt.replace(tzinfo=h_dl.LOCAL_TZ)
                            except ValueError:
                                sched_dt = None
                        elif sched_str == "night":
                            sched_dt = now.replace(hour=2, minute=0, second=0, microsecond=0)
                            if sched_dt <= now:
                                sched_dt += timedelta(days=1)
                        if sched_dt:
                            update_kwargs["status"] = "scheduled"
                            update_kwargs["scheduled_for"] = sched_dt.isoformat()
                    if update_kwargs:
                        await db.update_task(task_id, **update_kwargs)
                    created += 1

                rd_torrent_states.pop(torrent_id, None)

                if created == 0:
                    extra = f" ({failed_links} fallaron al resolverse)" if failed_links else ""
                    await _edit(context, chat_id, message_id, f"⚠️ No se pudo resolver ningun enlace de descarga.{extra}")
                    return

                warn = f"\n⚠️ {failed_links} enlace(s) no se pudieron resolver y se omitieron." if failed_links else ""
                await _edit(
                    context, chat_id, message_id,
                    f"✅ {created} archivo(s) listo(s) en Real-Debrid.\n"
                    f"Añadidos a la cola de descarga hacia `{state['dest_folder']}`.{warn}",
                )
                await h_dl.try_start_next(context)
                return

            elif status in ("magnet_error", "error", "virus", "dead"):
                await _edit(context, chat_id, message_id, f"❌ Real-Debrid no pudo procesar el torrent (estado: {status}).")
                rd_torrent_states.pop(torrent_id, None)
                return

            else:
                if torrent_id in rd_torrent_states:
                    rd_torrent_states[torrent_id]["last_snapshot"] = {
                        "status": status, "progress": info.get("progress", 0), "speed": 0, "seeders": 0,
                    }
                await _edit(context, chat_id, message_id, f"ℹ️ Estado: {status}...", markup=cancel_kb)
                await asyncio.sleep(5)

    except asyncio.CancelledError:
        return
