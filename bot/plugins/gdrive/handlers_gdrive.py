from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

import config
import db
import google_drive
import handlers_downloads as h_dl
from rich_ui import esc, header, r_h, r_p, r_kv_table, r_footer, rich
from utils import authorized_only, owner_only


@owner_only
async def gdrive_menu(update, context):
    query = update.callback_query
    await query.answer()

    if not google_drive.is_configured():
        import handlers_setup
        text, kb = handlers_setup.gdrive_creds_content(
            "Aún no hay credenciales de Google. Sigue el tutorial y envía el Client ID y el secret."
            if config.WEBAPP_URL else "Primero activa la web app y pon su URL HTTPS (Ajustes → Web app).",
            back_cb="settings:menu")
        await handlers_setup.show(update, text, InlineKeyboardMarkup(
            [[InlineKeyboardButton("🌐 Web app", callback_data="web:menu")]] + list(kb.inline_keyboard)))
        return

    connected = await google_drive.is_connected()
    blocks = [r_h("Google Drive", 2, "📁")]
    kb = []
    if connected:
        try:
            email = await db.get_setting("google_email") or await google_drive.get_account_email()
            await db.set_setting("google_email", email)
        except Exception:
            email = "desconocida"
        blocks.append(r_kv_table([("Estado", "🟢 Conectado"), ("Cuenta", f"<b>{esc(email)}</b>")]))
        blocks.append(r_footer("Los enlaces de Drive se descargan directo al NAS con esta cuenta (sin Real-Debrid)."))
        kb.append([InlineKeyboardButton("🔌 Cambiar cuenta", callback_data="gdrive:connect")])
        kb.append([InlineKeyboardButton("🗑️ Desconectar", callback_data="gdrive:disconnect")])
    else:
        blocks.append(r_kv_table([("Estado", "🔴 Desconectado")]))
        kb.append([InlineKeyboardButton("🔌 Conectar", callback_data="gdrive:connect")])
    kb.append([InlineKeyboardButton("🔑 Credenciales de Google", callback_data="gdrive:cfg"),
               InlineKeyboardButton("📖 Tutorial", callback_data="guide:gdrive:gdrive:menu")])
    if not (config.WEBAPP_ENABLED and config.WEBAPP_URL):
        blocks.append(r_footer("⚠️ Google Drive necesita la web app activada con su URL HTTPS para completar el acceso."))
    kb.append([InlineKeyboardButton("⬅️ Ajustes", callback_data="settings:menu")])

    await query.edit_message_text(rich(*blocks), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))


@owner_only
async def gdrive_connect(update, context):
    query = update.callback_query
    await query.answer()
    if not google_drive.is_configured():
        await query.edit_message_text("⚠️ Faltan las credenciales de Google en el servidor.")
        return
    state = google_drive.new_oauth_state()
    url = google_drive.build_auth_url(state)
    await query.edit_message_text(
        "🔌 Toca el enlace de abajo — se abrirá en tu navegador. Ahí eliges la cuenta de Google "
        "y apruebas el acceso (nunca te pediremos tu contraseña aquí).\n\n"
        f"{url}\n\n"
        "Cuando termines, vuelve a este menú para ver el estado.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Google Drive", callback_data="gdrive:menu")]]),
        disable_web_page_preview=True,
    )


@owner_only
async def gdrive_disconnect(update, context):
    query = update.callback_query
    await query.answer()
    await google_drive.disconnect()
    await gdrive_menu(update, context)


@authorized_only
async def handle_drive_link(update, context, url: str):
    msg = update.effective_message

    if not google_drive.is_configured() or not await google_drive.is_connected():
        await msg.reply_text(
            "⚠️ Google Drive no está conectado todavía. Pide al propietario del bot que lo "
            "conecte desde ⚙️ Ajustes → 📁 Google Drive."
        )
        return

    status_msg = await msg.reply_text("🔍 Consultando Google Drive...")

    try:
        items = await google_drive.list_drive_files(url)
    except google_drive.GoogleDriveError as e:
        await status_msg.edit_text(f"❌ {e}")
        return
    except Exception as e:
        await status_msg.edit_text(f"❌ Error inesperado al consultar Drive: {e}")
        return

    task_ids = []
    for item in items:
        task_id = await db.create_task(
            kind="gdrive",
            filename=item["name"],
            total_size=item["size"],
            requested_by=msg.chat_id,
            drive_file_id=item["file_id"],
        )
        task_ids.append(task_id)

    ref = ",".join(str(t) for t in task_ids)
    plural = len(task_ids) > 1
    names = "\n".join(f"• {item['name']}" for item in items[:20])
    more = f"\n… y {len(items) - 20} más" if len(items) > 20 else ""

    auto = await h_dl.try_auto(context, ref)
    if auto:
        await status_msg.edit_text(h_dl.auto_text(auto), parse_mode="HTML")
        return

    await status_msg.edit_text(
        f"✅ Encontrado{'s' if plural else ''} {len(items)} archivo{'s' if plural else ''} en Drive:\n"
        f"{names}{more}\n\nElige la carpeta destino:",
        reply_markup=await h_dl.dest_markup(ref),
    )
