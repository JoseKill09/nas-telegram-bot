from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

import config
import db
import i18n
import keyboards
from i18n import L
from rich_ui import esc, r_footer, r_h, r_hr, r_kv_table, r_p, r_ul, rich
from utils import authorized_only, is_owner, owner_only


def _welcome_text(owner: bool) -> str:
    hint = L("Usa los botones de abajo para el gestor de archivos, la cola, el historial o los ajustes."
             if owner else "Usa los botones de abajo para el gestor de archivos, la cola o el historial.",
             "Use the buttons below for the file manager, the queue, the history or the settings."
             if owner else "Use the buttons below for the file manager, the queue or the history.")
    return rich(
        r_h(L("Bot de descargas NAS", "NAS download bot"), 2, "🚀"),
        r_p(L("Envíame <b>archivos</b>, <b>enlaces directos</b>, <b>magnets</b> o enlaces de <b>Google Drive</b> y los guardo en el NAS.",
              "Send me <b>files</b>, <b>direct links</b>, <b>magnets</b> or <b>Google Drive</b> links and I save them to the NAS.")),
        r_h(L("Comandos", "Commands"), 4, "⌨️"),
        r_ul([
            L("<code>/buscar &lt;texto&gt;</code> — busca torrents (⚡ los ya cacheados en TorBox primero)",
              "<code>/search &lt;text&gt;</code> — search torrents (⚡ already cached on TorBox first)"),
            L("<code>/ytdl &lt;url&gt;</code> — YouTube, TikTok, Twitter/X…", "<code>/ytdl &lt;url&gt;</code> — YouTube, TikTok, Twitter/X…"),
            L("<code>/link &lt;url&gt;</code> — enlaces directos o Real-Debrid", "<code>/link &lt;url&gt;</code> — direct links or Real-Debrid"),
            L("<code>/torrent &lt;magnet&gt;</code> — torrent con el proveedor que elijas", "<code>/torrent &lt;magnet&gt;</code> — torrent with the provider you choose"),
            L("<code>/cola</code> — cola de descargas y descompresiones", "<code>/queue</code> — download and extraction queue"),
            L("<code>/historial</code> — descargas terminadas, canceladas o con error", "<code>/history</code> — finished, cancelled or failed downloads"),
            L("<code>/setup</code> — configuración del proyecto", "<code>/setup</code> — project setup"),
            L("<code>/disk</code> — espacio libre del NAS", "<code>/disk</code> — free NAS space"),
            L("<code>/backup</code> — copia de seguridad y restauración", "<code>/backup</code> — backup and restore"),
            L("<code>/notify</code> — avisos de descargas", "<code>/notify</code> — download alerts"),
            L("<code>/rich</code> — activa o desactiva el texto enriquecido", "<code>/rich</code> — turn rich text on or off"),
            L("<code>/version</code> — estado y módulos del bot", "<code>/version</code> — bot status and modules"),
        ]),
        r_footer(esc(hint)),
    )


def _rich_status():
    import rich_bot
    on = rich_bot.is_enabled()
    text = (
        "<b>" + L("Texto enriquecido", "Rich text") + "</b>\n\n"
        + L("Estado: ", "Status: ") + (L("🟢 Activado", "🟢 Enabled") if on else L("🔴 Desactivado", "🔴 Disabled")) + "\n\n"
        + L("Activado: tablas, títulos y botones integrados (Bot API 10.1+). Desactivado: formato clásico de Telegram.\n"
            "Uso: /rich on · /rich off",
            "Enabled: tables, headings and built-in buttons (Bot API 10.1+). Disabled: classic Telegram formatting.\n"
            "Usage: /rich on · /rich off")
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(
        L("🔴 Desactivar", "🔴 Disable") if on else L("🟢 Activar", "🟢 Enable"), callback_data="rich:toggle")]])
    return text, kb


async def _set_rich(value: bool):
    import rich_bot
    await db.set_setting("rich_enabled", "1" if value else "0")
    rich_bot.set_enabled(value)


@owner_only
async def rich_command(update, context):
    arg = (context.args[0].lower() if context.args else "")
    if arg in ("on", "off"):
        await _set_rich(arg == "on")
    text, kb = _rich_status()
    await update.effective_message.reply_text(text, parse_mode="HTML", reply_markup=kb)


@owner_only
async def rich_toggle(update, context):
    import rich_bot
    await _set_rich(not rich_bot.is_enabled())
    await update.callback_query.answer(L("Guardado", "Saved"))
    text, kb = _rich_status()
    await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)


@authorized_only
async def version_command(update, context):
    import torrent_clients
    import tmdb_helper
    import torrent_search
    n_src = len(await torrent_search.enabled_sources())
    has_tmdb = await tmdb_helper.is_enabled()
    client_keys = await torrent_clients.enabled_keys()
    text = rich(
        r_h(f"NAS Telegram Bot v{config.VERSION}", 2, "🧩"),
        r_kv_table([
            ("🌐 " + L("Idioma", "Language"), esc(i18n.LANGS[i18n.lang])),
            ("🎬 yt-dlp", L("✅ Activo", "✅ Active")),
            ("🔎 " + L("Buscadores", "Search sources"),
             L(f"✅ {n_src} activos", f"✅ {n_src} active") if n_src else L("⚠️ Ninguno activo", "⚠️ None active")),
            ("⬇️ " + L("Clientes locales", "Local clients"),
             ", ".join(torrent_clients.label(k) for k in client_keys) if client_keys else L("⚪ Ninguno", "⚪ None")),
            ("🖥️ Web app", L("✅ Activada", "✅ Enabled") if config.WEBAPP_ENABLED else L("⚪ Desactivada", "⚪ Disabled")),
            ("🎞️ TMDB", L("✅ Activado", "✅ Enabled") if has_tmdb else L("⚪ Desactivado", "⚪ Disabled")),
            ("⚡ Userbot", f"FastTelethon · {config.USERBOT_MAX_CONNECTIONS}"),
            ("⏰ " + L("Programador", "Scheduler"), L("✅ Activo", "✅ Active")),
        ]),
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


@authorized_only
async def start(update, context):
    owner = is_owner(update.effective_user.id)
    if owner and not config.LANGUAGE:
        import handlers_setup
        text, kb = handlers_setup.language_content(first_run=True)
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        return
    await update.effective_message.reply_text(
        _welcome_text(owner),
        parse_mode=ParseMode.HTML,
        reply_markup=keyboards.main_menu(owner),
    )


@authorized_only
async def main_menu_callback(update, context):
    query = update.callback_query
    await query.answer()
    owner = is_owner(update.effective_user.id)
    await query.edit_message_text(_welcome_text(owner), parse_mode=ParseMode.HTML, reply_markup=keyboards.main_menu(owner))


@authorized_only
async def cancel_pending(update, context):
    had_pending_user_picker = bool(context.user_data.get("pending_add_user"))
    for key in ("pending_action", "pending_limit", "pending_dl_mkdir", "pending_add_user",
                "pending_ub_connections", "pending_setup", "pending_mirror", "pending_proxy", "pending_src"):
        context.user_data.pop(key, None)
    if had_pending_user_picker:
        from telegram import ReplyKeyboardRemove
        await update.effective_message.reply_text(L("Operación cancelada.", "Cancelled."), reply_markup=ReplyKeyboardRemove())
    else:
        await update.effective_message.reply_text(
            L("Operación cancelada.", "Cancelled."), reply_markup=keyboards.main_menu(is_owner(update.effective_user.id))
        )


@authorized_only
async def help_callback(update, context):
    query = update.callback_query
    await query.answer()
    owner = is_owner(update.effective_user.id)
    blocks = [
        r_h(L("Ayuda", "Help"), 2, "ℹ️"),
        r_h(L("Descargas", "Downloads"), 4, "📥"),
        r_ul([
            L("<b>Archivos de Telegram:</b> reenvíalos y el Userbot los descarga a máxima velocidad.",
              "<b>Telegram files:</b> forward them and the Userbot downloads them at full speed."),
            L("<b>Enlaces directos / nubes:</b> pégalos en el chat o usa <code>/link</code>.",
              "<b>Direct links / clouds:</b> paste them in the chat or use <code>/link</code>."),
            L("<b>Magnets:</b> pégalos o envía un <code>.torrent</code>; elegirás el proveedor (Real-Debrid, TorBox o un cliente local).",
              "<b>Magnets:</b> paste them or send a <code>.torrent</code>; you pick the provider (Real-Debrid, TorBox or a local client)."),
            L("<b>Vídeos online:</b> <code>/ytdl &lt;url&gt;</code>.", "<b>Online videos:</b> <code>/ytdl &lt;url&gt;</code>."),
        ]),
        r_h(L("Gestión", "Management"), 4, "🗂️"),
        r_ul([
            L("<b>Cola:</b> pausa, reanuda, prioriza, reordena o cancela cada tarea.",
              "<b>Queue:</b> pause, resume, prioritise, reorder or cancel each task."),
            L("<b>Archivos:</b> navega, renombra, borra, sube a Telegram o extrae comprimidos.",
              "<b>Files:</b> browse, rename, delete, upload to Telegram or extract archives."),
            L("<b>Historial:</b> <code>/historial</code>.", "<b>History:</b> <code>/history</code>."),
        ]),
    ]
    if owner:
        blocks += [
            r_h(L("Administración", "Administration"), 4, "⚙️"),
            r_ul([
                L("<b>Ajustes:</b> idioma, carpetas, proveedores, buscadores, web app, Userbot, Google Drive, TMDB y usuarios, con tutoriales.",
                  "<b>Settings:</b> language, folders, providers, search sources, web app, Userbot, Google Drive, TMDB and users, with guides."),
            ]),
        ]
    blocks.append(r_hr())
    if config.WEBAPP_ENABLED and config.WEBAPP_URL:
        blocks.append(r_footer(L("También tienes el panel web con todas las funciones.", "You also have the web panel with every feature.")))
    await query.edit_message_text(rich(*blocks), parse_mode=ParseMode.HTML, reply_markup=keyboards.main_menu(owner))
