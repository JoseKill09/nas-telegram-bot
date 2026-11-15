import logging
import os
import re
import urllib.parse

from telegram import InlineKeyboardButton as Btn, InlineKeyboardMarkup as Markup
from telegram.constants import ParseMode
from telegram.error import BadRequest

import config
import db
import guides
import i18n
import torrent_search
import tunnel
import webserver
from i18n import L
from rich_ui import esc, r_footer, r_h, r_kv_table, r_p, r_quote, r_table, r_ul, rich
from utils import authorized_only, owner_only

logger = logging.getLogger(__name__)

MEDIA_LABELS = {"": "—", "movie": "🎬", "tv": "📺"}
MEDIA_NEXT = {"": "movie", "movie": "tv", "tv": ""}


def _media_name(kind: str) -> str:
    return {"": L("Otros", "Other"), "movie": L("Películas", "Movies"), "tv": "Series"}[kind]


def _on(flag: bool) -> str:
    return L("🟢 Activado", "🟢 Enabled") if flag else L("⚪ Desactivado", "⚪ Disabled")


def back(callback: str, label: str | None = None) -> list:
    return [Btn(label or L("⬅️ Atrás", "⬅️ Back"), callback_data=callback)]


async def show(update, text: str, kb: Markup | None = None):
    query = update.callback_query
    try:
        if query:
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        else:
            await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    except BadRequest as e:
        if "not modified" in str(e).lower():
            return
        if not query:
            raise
        # The menu message cannot be edited into this screen (e.g. it holds the screenshot carousel):
        # send the screen as a new message and remove the old one.
        await query.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        try:
            await query.message.delete()
        except BadRequest:
            pass


async def push(context, pending: dict, text: str, kb: Markup | None):
    try:
        await context.bot.edit_message_text(
            chat_id=pending["chat_id"], message_id=pending["message_id"],
            text=text, parse_mode=ParseMode.HTML, reply_markup=kb,
        )
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            await context.bot.send_message(
                chat_id=pending["chat_id"], text=text, parse_mode=ParseMode.HTML, reply_markup=kb
            )


async def hub_content() -> tuple[str, Markup]:
    import handlers_settings as hs

    rd_token, tb_token = await db.get_setting("rd_token"), await db.get_setting("tb_token")
    rd_on, tb_on = await hs.rd_is_enabled(), await hs.tb_is_enabled()
    import torrent_clients
    client_keys = await torrent_clients.enabled_keys()
    n_src = len(await torrent_search.enabled_sources())
    ub_ok = bool(await db.get_session_string())
    drive_ok = bool(await db.get_setting("google_refresh_token"))
    import tmdb_helper
    tmdb_on = await tmdb_helper.is_enabled()

    providers = []
    if rd_token and rd_on:
        providers.append("Real-Debrid")
    if tb_token and tb_on:
        providers.append("TorBox")
    for k in client_keys:
        providers.append(torrent_clients.label(k))

    text = rich(
        r_h(L("Configuración del proyecto", "Project setup"), 2, "🧭"),
        r_p(L("Todo se configura desde aquí, sin tocar código ni el archivo .env. "
              "Cada apartado tiene un tutorial paso a paso.",
              "Everything is configured from here, without touching code or the .env file. "
              "Every section has a step-by-step guide.")),
        r_kv_table([
            ("🌐 " + L("Idioma", "Language"), esc(i18n.LANGS[i18n.lang])),
            ("📁 " + L("Carpetas", "Folders"), str(len(config.FOLDERS))),
            ("🖥️ Web app", _on(config.WEBAPP_ENABLED) + (f" · <code>{esc(config.WEBAPP_URL)}</code>" if config.WEBAPP_URL else "")),
            ("📥 " + L("Proveedores de descarga", "Download providers"), esc(", ".join(providers)) if providers else L("⚠️ Ninguno", "⚠️ None")),
            ("🔎 " + L("Buscadores activos", "Active search sources"),
             f"🟢 {n_src}" if n_src else L("🔴 Ninguno (actívalos para buscar)", "🔴 None (enable some to search)")),
            ("🤖 Userbot", L("🟢 Conectado", "🟢 Connected") if ub_ok else L("⚪ Sin conectar", "⚪ Not connected")),
            ("☁️ Google Drive", L("🟢 Conectado", "🟢 Connected") if drive_ok else L("⚪ Sin conectar", "⚪ Not connected")),
            ("🎞️ TMDB", _on(tmdb_on)),
        ]),
        r_footer(L("Empieza por Carpetas y Proveedores de descarga; el resto es opcional.",
                   "Start with Folders and Download providers; the rest is optional.")),
    )
    kb = Markup([
        [Btn("📁 " + L("Carpetas", "Folders"), callback_data="fld:menu"),
         Btn("📥 " + L("Proveedores de descarga", "Download providers"), callback_data="prov:menu")],
        [Btn("🔎 " + L("Buscadores", "Search sources"), callback_data="src:menu"),
         Btn("🖥️ Web app", callback_data="web:menu")],
        [Btn("🤖 Userbot", callback_data="ub:menu"),
         Btn("☁️ Google Drive", callback_data="gdrive:menu")],
        [Btn("🎞️ TMDB", callback_data="tmdb:menu"),
         Btn("👥 " + L("Usuarios", "Users"), callback_data="users:menu")],
        [Btn("⚙️ " + L("Límites de descargas", "Download limits"), callback_data="limits:menu"),
         Btn("🌐 " + L("Idioma", "Language"), callback_data="lang:menu")],
        [Btn("📦 " + L("Descompresión", "Extraction"), callback_data="extract:menu"),
         Btn("🔔 " + L("Notificaciones", "Notifications"), callback_data="nt:menu")],
        [Btn("💾 " + L("Espacio en disco", "Disk space"), callback_data="dk:menu"),
         Btn("🧭 " + L("Reglas de destino", "Destination rules"), callback_data="ru:menu")],
        [Btn("💽 " + L("Copia de seguridad", "Backup"), callback_data="bk:menu"),
         Btn("📖 " + L("Tutoriales", "Guides"), callback_data="guide:menu")],
        [Btn(L("⬅️ Menú principal", "⬅️ Main menu"), callback_data="menu:main")],
    ])
    return text, kb


@owner_only
async def settings_menu(update, context):
    if update.callback_query:
        await update.callback_query.answer()
    context.user_data.pop("pending_setup", None)
    text, kb = await hub_content()
    await show(update, text, kb)


def language_content(first_run: bool = False) -> tuple[str, Markup]:
    text = rich(
        r_h("Language / Idioma", 2, "🌐"),
        r_p("Choose the language of the whole interface (chat and web app).<br/>"
            "Elige el idioma de toda la interfaz (chat y web app)."),
    )
    kb = [[Btn("🇬🇧 English", callback_data="lang:set:en"), Btn("🇪🇸 Español", callback_data="lang:set:es")]]
    if not first_run:
        kb.append(back("settings:menu"))
    return text, Markup(kb)


@owner_only
async def language_menu(update, context):
    await update.callback_query.answer()
    text, kb = language_content()
    await show(update, text, kb)


@owner_only
async def language_set(update, context):
    code = update.callback_query.data.split(":")[2]
    if code not in i18n.LANGS:
        return
    first_run = not config.LANGUAGE
    await config.set_runtime("LANGUAGE", code)
    i18n.set_lang(code)
    await update.callback_query.answer(i18n.LANGS[code])
    if first_run:
        text = rich(
            r_h(L("¡Todo listo para empezar!", "You're all set to start!"), 2, "🚀"),
            r_p(L("Abre la configuración del proyecto para conectar tus servicios paso a paso, "
                  "o ve directo al menú principal.",
                  "Open the project setup to connect your services step by step, "
                  "or go straight to the main menu.")),
        )
        kb = Markup([
            [Btn("🧭 " + L("Configuración del proyecto", "Project setup"), callback_data="settings:menu")],
            [Btn(L("🏠 Menú principal", "🏠 Main menu"), callback_data="menu:main")],
        ])
        await show(update, text, kb)
        return
    text, kb = await hub_content()
    await show(update, text, kb)


def guide_index_content() -> tuple[str, Markup]:
    names = {
        "folders": "📁 " + L("Carpetas", "Folders"),
        "webapp": "🖥️ Web app",
        "cloudflare": "☁️ Cloudflare",
        "lan": "🏠 " + L("Red local", "Local network"),
        "gdrive": "☁️ Google Drive",
        "userbot": "🤖 Userbot",
        "qbit": "⬇️ qBittorrent",
        "transmission": "📡 Transmission",
        "deluge": "🌊 Deluge",
        "rules": "🧭 " + L("Reglas de destino", "Destination rules"),
        "backup": "💽 " + L("Copia de seguridad", "Backup"),
        "torbox": "📦 TorBox",
        "realdebrid": "💳 Real-Debrid",
        "sources": "🔎 " + L("Buscadores", "Search sources"),
        "prowlarr": "🧭 Prowlarr",
        "tmdb": "🎞️ TMDB",
    }
    kb, row = [], []
    for topic in guides.TOPICS:
        row.append(Btn(names[topic], callback_data=f"guide:{topic}:guide:menu"))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append(back("settings:menu"))
    return rich(r_h(L("Tutoriales", "Guides"), 2, "📖"), r_p(L("Elige un tema.", "Pick a topic."))), Markup(kb)


@owner_only
async def guide_view(update, context):
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":", 2)
    topic = parts[1] if len(parts) > 1 else "menu"
    if topic == "menu":
        text, kb = guide_index_content()
        await show(update, text, kb)
        return
    back_cb = parts[2] if len(parts) > 2 else "settings:menu"
    if topic not in guides.TOPICS:
        return
    if topic == "webapp":
        import tutorial_media
        try:
            sent = await tutorial_media.send(context.bot, query.message.chat_id, guides.guide_text(topic), Markup([back(back_cb)]))
        except Exception:
            logger.warning("Tutorial de la web app: fallo con el carrusel; se muestra el texto.", exc_info=True)
            sent = False
        if sent:
            try:
                await query.message.delete()
            except BadRequest:
                pass
            return
    await show(update, guides.guide_text(topic), Markup([back(back_cb)]))


def _guide_btn(topic: str, back_cb: str) -> list:
    return Btn("📖 " + L("Tutorial", "Guide"), callback_data=f"guide:{topic}:{back_cb}")


def path_status(path: str) -> str:
    try:
        if not os.path.isdir(path):
            return L("❌ No existe", "❌ Missing")
        if not os.access(path, os.W_OK):
            return L("⚠️ Solo lectura", "⚠️ Read-only")
        if os.stat(path).st_dev == os.stat("/").st_dev:
            return L("⚠️ Dentro del contenedor", "⚠️ Inside container")
        return L("✅ Montada", "✅ Mounted")
    except OSError:
        return "❌"


def folders_content(note: str | None = None) -> tuple[str, Markup]:
    rows = [[esc(n), f"<code>{esc(p)}</code>", MEDIA_LABELS[config.folder_media(n)], path_status(p)]
            for n, p in config.FOLDERS.items()]
    blocks = [
        r_h(L("Carpetas", "Folders"), 2, "📁"),
        r_p(L("Tus carpetas con el nombre que quieras (Música, Proyectos…). Todo lo que haya dentro de la carpeta compartida "
              "(<code>/media</code> en el contenedor) se puede usar: pulsa ➕ y elígela navegando, sin tocar archivos.",
              "Your folders, with any name you like (Music, Projects…). Anything inside the shared folder "
              "(<code>/media</code> in the container) can be used: tap ➕ and pick it by browsing, no files to edit.")),
        r_table(rows, header=[L("Nombre", "Name"), L("Ruta", "Path"), "TMDB", L("Estado", "Status")]) if rows
        else r_p(L("No hay carpetas.", "No folders.")),
    ]
    if note:
        blocks.append(r_quote(note))
    blocks.append(r_footer(L("🎬 Películas / 📺 Series: TMDB crea carpetas por título en su raíz.",
                             "🎬 Movies / 📺 Series: TMDB creates title folders at their root.")))
    kb = []
    row = []
    for i, name in enumerate(config.FOLDERS):
        row.append(Btn(f"{MEDIA_LABELS[config.folder_media(name)]} {name}"[:30], callback_data=f"fld:o:{i}"))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([Btn("♻️ " + L("Ejemplos", "Examples"), callback_data="fld:reset")])
    kb.append([_guide_btn("folders", "fld:menu")])
    kb.append(back("settings:menu"))
    return rich(*blocks), Markup(kb)


@owner_only
async def folders_menu(update, context):
    await update.callback_query.answer()
    context.user_data.pop("pending_setup", None)
    text, kb = folders_content()
    await show(update, text, kb)


def _folder_by_index(idx: str) -> str | None:
    names = list(config.FOLDERS)
    return names[int(idx)] if idx.isdigit() and int(idx) < len(names) else None


@owner_only
async def folder_open(update, context):
    query = update.callback_query
    name = _folder_by_index(query.data.split(":")[2])
    if not name:
        await query.answer()
        return
    await query.answer()
    idx = query.data.split(":")[2]
    text = rich(
        r_h(name, 2, "📁"),
        r_kv_table([
            (L("Ruta", "Path"), f"<code>{esc(config.FOLDERS[name])}</code>"),
            (L("Estado", "Status"), path_status(config.FOLDERS[name])),
            ("TMDB", MEDIA_LABELS[config.folder_media(name)] + " " + _media_name(config.folder_media(name))),
        ]),
    )
    kb = Markup([
        [Btn("✏️ " + L("Cambiar nombre", "Rename"), callback_data=f"fld:r:{idx}"),
         Btn("📂 " + L("Cambiar ruta", "Change path"), callback_data=f"fld:p:{idx}")],
        [Btn("🎞️ " + L("Cambiar tipo (TMDB)", "Change type (TMDB)"), callback_data=f"fld:m:{idx}")],
        [Btn("🗑️ " + L("Quitar del bot", "Remove from bot"), callback_data=f"fld:d:{idx}")],
        back("fld:menu"),
    ])
    await show(update, text, kb)


@owner_only
async def folder_media(update, context):
    query = update.callback_query
    name = _folder_by_index(query.data.split(":")[2])
    if name:
        config.FOLDER_MEDIA[name] = MEDIA_NEXT[config.folder_media(name)]
        await config.save_folders()
    await folder_open(update, context)


@owner_only
async def folder_delete(update, context):
    query = update.callback_query
    name = _folder_by_index(query.data.split(":")[2])
    if name and len(config.FOLDERS) > 1:
        config.FOLDERS.pop(name, None)
        config.FOLDER_MEDIA.pop(name, None)
        await config.save_folders()
        await query.answer(L("Quitada (los archivos no se borran)", "Removed (files are not deleted)"))
    else:
        await query.answer(L("Debe quedar al menos una carpeta", "At least one folder must remain"), show_alert=True)
    text, kb = folders_content()
    await show(update, text, kb)


@owner_only
async def folders_reset(update, context):
    config.set_folders(config.DEFAULT_FOLDERS)
    await config.save_folders()
    await update.callback_query.answer(L("Carpetas de ejemplo restauradas", "Example folders restored"))
    text, kb = folders_content()
    await show(update, text, kb)


PAGE = 12


def _browse_state(context) -> dict | None:
    return context.user_data.get("fld_browse")


def browse_content(st: dict):
    import folders
    subs = folders.list_subdirs(st["path"])
    st["subs"] = subs
    page = max(0, min(st.get("page", 0), max(0, (len(subs) - 1) // PAGE)))
    st["page"] = page
    rel = os.path.relpath(st["path"], folders.BASE)
    shown = "/" if rel == "." else "/" + rel
    title = L("Elegir carpeta", "Pick a folder")
    if st["mode"] == "path":
        title = L(f"Nueva ruta de {esc(st['name'])}", f"New path for {esc(st['name'])}")
    text = rich(
        r_h(title, 2, "📂"),
        r_kv_table([(L("Estás en", "You are in"), f"<code>{esc(shown)}</code>")]),
        r_p(L("Entra en una carpeta, o pulsa «Usar esta» para elegir la actual. «Nueva» crea una subcarpeta.",
              "Open a folder, or press “Use this” to pick the current one. “New” creates a subfolder.")),
        r_footer(L("Solo se ve lo que hay dentro de la carpeta compartida (MEDIA_ROOT en .env).",
                   "Only what is inside the shared folder (MEDIA_ROOT in .env) is visible.")),
    )
    kb, row = [], []
    for i, name in enumerate(subs[page * PAGE:(page + 1) * PAGE], page * PAGE):
        row.append(Btn(f"📁 {name}"[:30], callback_data=f"fld:b:{i}"))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    nav = []
    if page > 0:
        nav.append(Btn("◀️", callback_data=f"fld:pg:{page - 1}"))
    if (page + 1) * PAGE < len(subs):
        nav.append(Btn("▶️", callback_data=f"fld:pg:{page + 1}"))
    if nav:
        kb.append(nav)
    ctrl = []
    if st["path"] != folders.BASE:
        ctrl.append(Btn("⬆️ " + L("Subir", "Up"), callback_data="fld:up"))
    ctrl.append(Btn("➕ " + L("Nueva", "New"), callback_data="fld:new"))
    ctrl.append(Btn("✅ " + L("Usar esta", "Use this"), callback_data="fld:pick"))
    kb.append(ctrl)
    kb.append([Btn("⌨️ " + L("Escribir ruta", "Type a path"), callback_data="fld:typed")])
    kb.append(back("fld:menu", L("✖️ Cancelar", "✖️ Cancel")))
    return text, Markup(kb)


@owner_only
async def folder_add_prompt(update, context):
    import folders
    await update.callback_query.answer()
    context.user_data.pop("pending_setup", None)
    context.user_data["fld_browse"] = {"path": folders.BASE, "mode": "add", "page": 0}
    text, kb = browse_content(context.user_data["fld_browse"])
    await show(update, text, kb)


@owner_only
async def folder_path_start(update, context):
    import folders
    query = update.callback_query
    name = _folder_by_index(query.data.split(":")[2])
    await query.answer()
    if not name:
        return
    start = config.FOLDERS[name]
    try:
        start = folders.inside_base(start) if os.path.isdir(start) else folders.BASE
    except folders.FolderError:
        start = folders.BASE
    context.user_data["fld_browse"] = {"path": start, "mode": "path", "name": name, "page": 0}
    text, kb = browse_content(context.user_data["fld_browse"])
    await show(update, text, kb)


@owner_only
async def folder_browse(update, context):
    import folders
    query = update.callback_query
    st = _browse_state(context)
    parts = query.data.split(":")
    action = parts[1]
    if not st:
        await query.answer(L("Sesión expirada", "Session expired"), show_alert=True)
        text, kb = folders_content()
        await show(update, text, kb)
        return
    if action == "b":
        subs = st.get("subs", [])
        if parts[2].isdigit() and int(parts[2]) < len(subs):
            st["path"] = os.path.join(st["path"], subs[int(parts[2])])
            st["page"] = 0
        await query.answer()
    elif action == "up":
        st["path"] = os.path.dirname(st["path"]) if st["path"] != folders.BASE else folders.BASE
        st["page"] = 0
        await query.answer()
    elif action == "pg":
        st["page"] = int(parts[2])
        await query.answer()
    elif action == "new":
        await query.answer()
        context.user_data["pending_setup"] = {
            "kind": "folder_mkdir", "chat_id": query.message.chat_id, "message_id": query.message.message_id, "back": "fld:browse",
        }
        text, kb = _prompt_content(L("Nueva subcarpeta", "New subfolder"),
                                   [L("Envía el nombre de la carpeta que quieres crear aquí.", "Send the name of the folder to create here.")],
                                   "fld:browse")
        await show(update, text, kb)
        return
    elif action == "browse":
        await query.answer()
        context.user_data.pop("pending_setup", None)
    elif action == "typed":
        await query.answer()
        context.user_data.pop("fld_browse", None)
        context.user_data["pending_setup"] = {
            "kind": "folder", "chat_id": query.message.chat_id, "message_id": query.message.message_id, "back": "fld:menu",
        }
        text, kb = _prompt_content(L("Añadir carpeta", "Add folder"),
                                   [L("Envía el <b>nombre</b> y la <b>ruta del contenedor</b>: <code>Music /media/Music</code>",
                                      "Send the <b>name</b> and the <b>container path</b>: <code>Music /media/Music</code>")],
                                   "fld:menu", "folders")
        await show(update, text, kb)
        return
    elif action == "pick":
        await query.answer()
        if st["mode"] == "path":
            await folders.set_path(st["name"], st["path"])
            context.user_data.pop("fld_browse", None)
            text, kb = folders_content(L(f"✅ {esc(st['name'])} ahora apunta a {esc(st['path'])}",
                                         f"✅ {esc(st['name'])} now points to {esc(st['path'])}"))
            await show(update, text, kb)
            return
        default = os.path.basename(st["path"]) or "Media"
        context.user_data["pending_setup"] = {
            "kind": "folder_name", "chat_id": query.message.chat_id, "message_id": query.message.message_id,
            "back": "fld:browse", "path": st["path"],
        }
        text, kb = _prompt_content(
            L("Nombre de la carpeta", "Folder name"),
            [L(f"Envía el nombre con el que quieres verla en el bot (por ejemplo Música). Ruta: <code>{esc(st['path'])}</code>",
               f"Send the name you want it to have in the bot (for example Music). Path: <code>{esc(st['path'])}</code>")],
            "fld:browse")
        kb = Markup([[Btn(L(f"Usar «{default}»", f"Use “{default}”"), callback_data="fld:nm")], *kb.inline_keyboard])
        await show(update, text, kb)
        return
    elif action == "nm":
        await query.answer()
        pending = context.user_data.pop("pending_setup", None) or {}
        if pending.get("kind") != "folder_name":
            return
        await _add_named_folder(update, context, pending, os.path.basename(pending["path"]) or "Media")
        return
    text, kb = browse_content(st)
    await show(update, text, kb)


async def _add_named_folder(update, context, pending, name):
    import folders
    try:
        await folders.add(name, pending["path"])
        context.user_data.pop("fld_browse", None)
        text, kb = folders_content(L(f"✅ Añadida: {esc(name)} → {esc(pending['path'])}",
                                     f"✅ Added: {esc(name)} → {esc(pending['path'])}"))
    except folders.FolderError as e:
        text, kb = _prompt_content(L("Inténtalo de nuevo", "Try again"),
                                   [L("Nombre no válido o repetido (sin / : \\, máx. 30 caracteres).",
                                      "Invalid or duplicate name (no / : \\, max 30 characters).")], "fld:browse")
        context.user_data["pending_setup"] = pending
    if update.callback_query:
        await show(update, text, kb)
    else:
        await push(context, pending, text, kb)


@owner_only
async def folder_rename_prompt(update, context):
    query = update.callback_query
    name = _folder_by_index(query.data.split(":")[2])
    await query.answer()
    if not name:
        return
    context.user_data["pending_setup"] = {
        "kind": "folder_rename", "chat_id": query.message.chat_id, "message_id": query.message.message_id,
        "back": "fld:menu", "old": name,
    }
    text, kb = _prompt_content(L(f"Renombrar {esc(name)}", f"Rename {esc(name)}"),
                               [L("Envía el nuevo nombre (por ejemplo Música).", "Send the new name (for example Music).")], "fld:menu")
    await show(update, text, kb)


def web_content(note: str | None = None) -> tuple[str, Markup]:
    running = webserver.running()
    blocks = [
        r_h("Web app", 2, "🖥️"),
        r_p(L("Panel visual opcional dentro de Telegram. Todo lo que hace también está en este chat.",
              "Optional visual panel inside Telegram. Everything it does is also available in this chat.")),
        r_kv_table([
            (L("Estado", "Status"), _on(config.WEBAPP_ENABLED) + (" · " + L("servidor en marcha", "server running") if running else "")),
            ("URL HTTPS", f"<code>{esc(config.WEBAPP_URL)}</code>" if config.WEBAPP_URL else L("⚠️ Sin configurar", "⚠️ Not set")),
            (L("Puerto interno", "Internal port"), f"<code>{config.WEBAPP_PORT}</code>"),
        ]),
    ]
    if config.WEBAPP_ENABLED and not config.WEBAPP_URL:
        blocks.append(r_quote(L("Falta la URL HTTPS pública: sin ella Telegram no puede abrir el panel. Mira el tutorial de Cloudflare.",
                                "The public HTTPS URL is missing: Telegram cannot open the panel without it. See the Cloudflare guide.")))
    if note:
        blocks.append(r_quote(note))
    kb = [
        [Btn("🔴 " + L("Desactivar", "Disable") if config.WEBAPP_ENABLED else "🟢 " + L("Activar", "Enable"), callback_data="web:toggle")],
        [Btn("☁️ " + L("Túnel de Cloudflare", "Cloudflare Tunnel"), callback_data="web:tn"),
         Btn("🏠 " + L("Red local", "Local network"), callback_data="lan:menu")],
        [Btn("🔗 " + L("Poner URL", "Set URL"), callback_data="web:url")]
        + ([Btn("🗑️ " + L("Quitar URL", "Clear URL"), callback_data="web:urlclear")] if config.WEBAPP_URL else []),
        [Btn("📖 " + L("Tutorial web app", "Web app guide"), callback_data="guide:webapp:web:menu"),
         Btn("📖 " + L("Tutorial Cloudflare", "Cloudflare guide"), callback_data="guide:cloudflare:web:menu")],
        back("settings:menu"),
    ]
    return rich(*blocks), Markup(kb)


@owner_only
async def web_menu(update, context):
    await update.callback_query.answer()
    context.user_data.pop("pending_setup", None)
    text, kb = web_content()
    await show(update, text, kb)


@owner_only
async def web_toggle(update, context):
    query = update.callback_query
    enable = not config.WEBAPP_ENABLED
    await config.set_runtime("WEBAPP_ENABLED", enable)
    note = None
    if enable:
        ok = await webserver.start()
        note = L("Servidor iniciado.", "Server started.") if ok else L("⚠️ No se pudo iniciar el servidor (¿puerto ocupado?).", "⚠️ The server could not start (port in use?).")
    else:
        import lan_access
        if await lan_access.is_enabled():
            note = L("Web app de Telegram desactivada. El servidor sigue en marcha para el acceso por red local.",
                     "Telegram web app disabled. The server keeps running for local network access.")
        else:
            await webserver.stop()
            note = L("Servidor detenido.", "Server stopped.")
    await query.answer()
    text, kb = web_content(note)
    await show(update, text, kb)


@owner_only
# ── Local network access (browser without Telegram) ────────────────────────────
async def lan_content(note: str | None = None) -> tuple[str, Markup]:
    import lan_access
    import webserver
    enabled = await lan_access.is_enabled()
    url = await lan_access.get_url()
    sessions = await lan_access.list_sessions()
    blocks = [
        r_h(L("Acceso desde la red local", "Local network access"), 2, "🏠"),
        r_p(L("Abre el panel web en el navegador de tu casa (o desde fuera con tu propia VPN) sin Cloudflare ni dominio. "
              "Para entrar, el bot te envía un enlace de un solo uso; la sesión dura 30 días.",
              "Open the web panel in a browser at home (or from outside with your own VPN) without Cloudflare or a domain. "
              "To sign in, the bot sends you a single-use link; the session lasts 30 days.")),
        r_kv_table([
            (L("Estado", "Status"), L("🟢 Activado", "🟢 Enabled") if enabled else L("🔴 Desactivado", "🔴 Disabled")),
            (L("Dirección local", "Local address"), f"<code>{esc(url)}</code>" if url else L("⚠️ Sin configurar", "⚠️ Not set")),
            (L("Servidor", "Server"), L("🟢 en marcha", "🟢 running") if webserver.running() else L("⚪ parado", "⚪ stopped")),
            (L("Sesiones abiertas", "Open sessions"), str(len(sessions))),
        ]),
    ]
    if sessions:
        blocks.append(r_ul([f"{esc(x['name'])} · {esc(x['agent'][:40] or '—')}" for x in sessions[:8]]))
    if note:
        blocks.append(r_quote(note))
    blocks.append(r_footer(L("Solo se instala como app si entras por HTTPS (Cloudflare o Tailscale). Mira el tutorial.",
                             "It installs as an app only over HTTPS (Cloudflare or Tailscale). See the guide.")))
    kb = [[Btn("🔴 " + L("Desactivar", "Disable") if enabled else "🟢 " + L("Activar", "Enable"), callback_data="lan:toggle"),
           Btn("✏️ " + L("Dirección local", "Local address"), callback_data="lan:url")]]
    if enabled and url:
        kb.append([Btn("🔗 " + L("Enviarme un enlace de acceso", "Send me an access link"), callback_data="lan:link")])
    if sessions:
        kb.append([Btn("🚪 " + L("Cerrar todas las sesiones", "Close every session"), callback_data="lan:revoke")])
    kb.append([_guide_btn("lan", "lan:menu")])
    kb.append(back("web:menu"))
    return rich(*blocks), Markup(kb)


@owner_only
async def lan_menu(update, context):
    query = update.callback_query
    await query.answer()
    text, kb = await lan_content()
    await show(update, text, kb)


@owner_only
async def lan_toggle(update, context):
    import lan_access
    import webserver
    query = update.callback_query
    enable = not await lan_access.is_enabled()
    await lan_access.set_enabled(enable)
    if enable:
        ok = webserver.running() or await webserver.start()
        note = (L("Activado. Ahora pulsa «Enviarme un enlace de acceso».", "Enabled. Now press «Send me an access link».")
                if await lan_access.get_url() else
                L("Activado. Falta la dirección local (✏️).", "Enabled. The local address is missing (✏️)."))
        if not ok:
            note = L("⚠️ No se pudo iniciar el servidor (¿puerto ocupado?).", "⚠️ The server could not start (port in use?).")
    else:
        if not config.WEBAPP_ENABLED:
            await webserver.stop()
        note = L("Desactivado. Se han cerrado todas las sesiones del navegador.", "Disabled. Every browser session was closed.")
    await query.answer()
    text, kb = await lan_content(note)
    await show(update, text, kb)


@owner_only
async def lan_url_prompt(update, context):
    await _prompt(update, context, "lan_url", L("Dirección local", "Local address"),
                  [L("Envía la dirección con la que abres el NAS en tu red y el puerto de la web app "
                     "(<code>WEBAPP_LAN_PORT</code>, 8080 por defecto), por ejemplo:",
                     "Send the address of your NAS on your network and the web app port "
                     "(<code>WEBAPP_LAN_PORT</code>, 8080 by default), for example:"),
                   "<code>http://192.168.1.50:8080</code>"], "lan:menu", "lan")


async def _send_access_link(update, context) -> None:
    import lan_access
    link = await lan_access.login_link(update.effective_user)
    if not link:
        await context.bot.send_message(update.effective_chat.id, L(
            "El acceso por red local está desactivado o falta la dirección local. El propietario lo activa en Ajustes → Web app → 🏠 Red local.",
            "Local network access is off or the local address is missing. The owner enables it in Settings → Web app → 🏠 Local network."))
        return
    await context.bot.send_message(
        update.effective_chat.id,
        rich(r_h(L("Enlace de acceso", "Access link"), 2, "🔗"),
             r_p(L("Ábrelo en el navegador de un dispositivo conectado a tu red (o a tu VPN). Sirve <b>una sola vez</b> y caduca en 5 minutos.",
                   "Open it in a browser on a device connected to your network (or your VPN). It works <b>once</b> and expires in 5 minutes.")),
             r_p(f"<code>{esc(link)}</code>"),
             r_footer(L("No lo compartas: da acceso a tu panel.", "Do not share it: it gives access to your panel."))),
        parse_mode=ParseMode.HTML,
        reply_markup=Markup([[Btn("🌐 " + L("Abrir", "Open"), url=link)]]),
    )


@owner_only
async def lan_link_cb(update, context):
    await update.callback_query.answer()
    await _send_access_link(update, context)


@owner_only
async def lan_revoke_cb(update, context):
    import lan_access
    await lan_access.revoke_all()
    await update.callback_query.answer(L("Sesiones cerradas", "Sessions closed"))
    text, kb = await lan_content(L("🚪 Se han cerrado todas las sesiones del navegador.", "🚪 Every browser session was closed."))
    await show(update, text, kb)


@authorized_only
async def web_link_command(update, context):
    """/web — sends a single-use link to open the web panel in a browser on the local network."""
    await _send_access_link(update, context)


async def web_url_prompt(update, context):
    query = update.callback_query
    await query.answer()
    context.user_data["pending_setup"] = {
        "kind": "web_url", "chat_id": query.message.chat_id, "message_id": query.message.message_id,
    }
    text = rich(
        r_h(L("URL de la web app", "Web app URL"), 2, "🔗"),
        r_p(L("Envía la dirección HTTPS pública que apunta al puerto del bot, por ejemplo:",
              "Send the public HTTPS address that points to the bot's port, for example:")),
        r_ul(["<code>https://panel.example.com</code>"]),
    )
    await show(update, text, Markup([[_guide_btn("cloudflare", "web:menu")], back("web:menu", L("✖️ Cancelar", "✖️ Cancel"))]))


@owner_only
async def web_url_clear(update, context):
    await config.set_runtime("WEBAPP_URL", "")
    await update.callback_query.answer()
    text, kb = web_content()
    await show(update, text, kb)


async def tunnel_content(note: str | None = None) -> tuple[str, Markup]:
    st = tunnel.status()
    has_token = bool(await tunnel.get_token())
    if not st["installed"]:
        state = L("⚠️ cloudflared no está instalado en el contenedor (reconstruye con --build)",
                  "⚠️ cloudflared is not installed in the container (rebuild with --build)")
    elif st["connected"]:
        state = "🟢 " + L("Conectado", "Connected")
    elif st["running"]:
        state = "🟡 " + L("Conectando…", "Connecting…")
    else:
        state = "🔴 " + L("Detenido", "Stopped")
    blocks = [
        r_h(L("Túnel de Cloudflare", "Cloudflare Tunnel"), 2, "☁️"),
        r_p(L("Da una dirección HTTPS pública a la web app sin abrir puertos. El túnel se ejecuta dentro del propio bot.",
              "Gives the web app a public HTTPS address without opening ports. The tunnel runs inside the bot itself.")),
        r_kv_table([
            (L("Estado", "Status"), state),
            ("Token", L("✅ Guardado", "✅ Saved") if has_token else L("⚠️ Sin configurar", "⚠️ Not set")),
            (L("Destino en Cloudflare", "Target in Cloudflare"), "<code>http://bot:8080</code>"),
        ]),
    ]
    if st["last"] and not st["connected"]:
        blocks.append(r_quote(L("Último aviso: ", "Last message: ") + esc(st["last"])))
    if note:
        blocks.append(r_quote(note))
    kb = []
    if has_token:
        kb.append([Btn("⏹ " + L("Detener", "Stop") if st["running"] else "▶️ " + L("Iniciar", "Start"), callback_data="web:tntog")])
    kb.append([Btn("🔑 " + (L("Cambiar token", "Change token") if has_token else L("Poner token", "Set token")), callback_data="web:tntok")]
              + ([Btn("🗑️ " + L("Quitar token", "Remove token"), callback_data="web:tnclear")] if has_token else []))
    kb.append([_guide_btn("cloudflare", "web:tn")])
    kb.append(back("web:menu"))
    return rich(*blocks), Markup(kb)


@owner_only
async def tunnel_menu(update, context):
    await update.callback_query.answer()
    context.user_data.pop("pending_setup", None)
    text, kb = await tunnel_content()
    await show(update, text, kb)


@owner_only
async def tunnel_toggle(update, context):
    query = update.callback_query
    await query.answer()
    if tunnel.running():
        await tunnel.stop(persist=True)
        note = L("Túnel detenido.", "Tunnel stopped.")
    else:
        ok, why = await tunnel.start()
        note = (L("Túnel iniciado; tarda unos segundos en conectar.", "Tunnel started; it takes a few seconds to connect.") if ok else
                L("⚠️ Falta el token.", "⚠️ The token is missing.") if why == "notoken" else
                L("⚠️ cloudflared no está instalado.", "⚠️ cloudflared is not installed."))
    text, kb = await tunnel_content(note)
    await show(update, text, kb)


@owner_only
async def tunnel_token_prompt(update, context):
    query = update.callback_query
    await query.answer()
    context.user_data["pending_setup"] = {
        "kind": "tunnel_token", "chat_id": query.message.chat_id, "message_id": query.message.message_id,
    }
    text = rich(
        r_h(L("Token del túnel", "Tunnel token"), 2, "🔑"),
        r_p(L("Envía el token del túnel (panel de Cloudflare → Networking → Tunnels → tu túnel). Borraré tu mensaje al guardarlo.",
              "Send the tunnel token (Cloudflare dashboard → Networking → Tunnels → your tunnel). I will delete your message once saved.")),
    )
    await show(update, text, Markup([[_guide_btn("cloudflare", "web:tn")], back("web:tn", L("✖️ Cancelar", "✖️ Cancel"))]))


@owner_only
async def tunnel_token_clear(update, context):
    await update.callback_query.answer()
    await tunnel.stop(persist=True)
    await db.delete_setting("cf_token")
    text, kb = await tunnel_content(L("Token eliminado y túnel detenido.", "Token removed and tunnel stopped."))
    await show(update, text, kb)


def userbot_creds_content(note: str | None = None) -> tuple[str, Markup]:
    api_ok = bool(config.API_ID and config.API_HASH)
    blocks = [
        r_h(L("Credenciales del Userbot", "Userbot credentials"), 2, "🔑"),
        r_kv_table([
            ("API ID / API HASH", L("🟢 Configurados", "🟢 Set") if api_ok else L("⚪ Sin configurar", "⚪ Not set")),
            (L("ID del canal privado", "Private channel ID"), f"<code>{config.CHANNEL_ID}</code>" if config.CHANNEL_ID else L("⚪ Sin configurar", "⚪ Not set")),
        ]),
    ]
    if note:
        blocks.append(r_quote(note))
    kb = [
        [Btn("🔑 API ID / HASH", callback_data="cfg:api"), Btn("📣 " + L("ID del canal", "Channel ID"), callback_data="cfg:channel")],
        [_guide_btn("userbot", "ub:cfg")],
        back("ub:menu"),
    ]
    return rich(*blocks), Markup(kb)


@owner_only
async def userbot_creds_menu(update, context):
    await update.callback_query.answer()
    context.user_data.pop("pending_setup", None)
    text, kb = userbot_creds_content()
    await show(update, text, kb)


def _prompt_content(title: str, lines: list[str], back_cb: str, guide: str | None = None):
    text = rich(r_h(title, 2, "✍️"), r_p(*lines))
    rows = []
    if guide:
        rows.append([_guide_btn(guide, back_cb)])
    rows.append(back(back_cb, L("✖️ Cancelar", "✖️ Cancel")))
    return text, Markup(rows)


async def _prompt(update, context, kind: str, title: str, lines: list[str], back_cb: str, guide: str | None = None):
    query = update.callback_query
    await query.answer()
    context.user_data["pending_setup"] = {
        "kind": kind, "chat_id": query.message.chat_id, "message_id": query.message.message_id, "back": back_cb,
    }
    text, kb = _prompt_content(title, lines, back_cb, guide)
    await show(update, text, kb)


@owner_only
async def cfg_api_prompt(update, context):
    await _prompt(
        update, context, "api", L("API ID y API HASH", "API ID and API HASH"),
        [L("Envía los dos valores en un mensaje, separados por un espacio. Los consigues en <code>my.telegram.org</code> → API development tools.",
           "Send both values in one message, separated by a space. Get them at <code>my.telegram.org</code> → API development tools."),
         "<code>1234567 0123456789abcdef0123456789abcdef</code>"],
        "ub:cfg", "userbot",
    )


async def handle_pending_forward(update, context):
    """While the channel setup is waiting, a message forwarded from the channel connects it."""
    pending = context.user_data.get("pending_setup")
    msg = update.effective_message
    if not pending or pending.get("kind") != "channel" or not msg:
        return
    user = update.effective_user
    if not user or user.id != config.OWNER_ID:
        return
    chat = None
    origin = getattr(msg, "forward_origin", None)
    if origin is not None and getattr(origin, "chat", None) is not None:
        chat = origin.chat
    if chat is None:
        chat = getattr(msg, "forward_from_chat", None)
    from telegram.ext import ApplicationHandlerStop
    if chat is None or getattr(chat, "type", "") != "channel":
        await msg.reply_text(L("Ese mensaje no viene de un canal. Reenvía un mensaje del canal privado.",
                               "That message is not from a channel. Forward a message from the private channel."))
        raise ApplicationHandlerStop
    note = None
    try:
        member = await context.bot.get_chat_member(chat.id, context.bot.id)
        if getattr(member, "status", "") not in ("administrator", "creator"):
            note = L("⚠️ Guardado, pero el bot no es administrador del canal; hazlo administrador para que pueda publicar.",
                     "⚠️ Saved, but the bot is not an administrator of the channel; make it an admin so it can post.")
    except Exception:
        text, kb = _prompt_content(
            L("Canal privado", "Private channel"),
            [L("No veo ese canal: añade el bot al canal como administrador y vuelve a reenviar un mensaje.",
               "I cannot see that channel: add the bot to it as an administrator and forward a message again.")],
            pending.get("back", "ub:cfg"), "userbot")
        await push(context, pending, text, kb)
        raise ApplicationHandlerStop
    await config.set_runtime("CHANNEL_ID", str(chat.id))
    context.user_data.pop("pending_setup", None)
    title = esc(getattr(chat, "title", "") or str(chat.id))
    text, kb = userbot_creds_content(L(f"✅ Canal conectado: <b>{title}</b> (<code>{chat.id}</code>).", f"✅ Channel connected: <b>{title}</b> (<code>{chat.id}</code>).")
                                     + (("<br/>" + note) if note else ""))
    await push(context, pending, text, kb)
    raise ApplicationHandlerStop


@owner_only
async def cfg_channel_prompt(update, context):
    await _prompt(
        update, context, "channel", L("Canal privado", "Private channel"),
        [L("1. Añade el bot al canal como <b>administrador</b> (y tu cuenta userbot también).<br/>"
           "2. <b>Reenvíame aquí cualquier mensaje del canal</b> y lo detecto solo.",
           "1. Add the bot to the channel as an <b>administrator</b> (and your userbot account too).<br/>"
           "2. <b>Forward me any message from the channel</b> and I will detect it by myself."),
         L("¿Prefieres el ID? Envíalo como texto (empieza por <code>-100</code>), por ejemplo:",
           "Prefer the ID? Send it as text (starts with <code>-100</code>), for example:") + " <code>-1001234567890</code>"],
        "ub:cfg", "userbot",
    )


def gdrive_creds_content(note: str | None = None, back_cb: str = "gdrive:menu") -> tuple[str, Markup]:
    ok = bool(config.GOOGLE_CLIENT_ID and config.GOOGLE_CLIENT_SECRET)
    redirect = config.GOOGLE_REDIRECT_URI or (f"{config.WEBAPP_URL}/oauth2/google/callback" if config.WEBAPP_URL else "")
    blocks = [
        r_h(L("Credenciales de Google", "Google credentials"), 2, "🔑"),
        r_kv_table([
            ("Client ID", L("🟢 Configurado", "🟢 Set") if config.GOOGLE_CLIENT_ID else L("⚪ Sin configurar", "⚪ Not set")),
            ("Client secret", L("🟢 Configurado", "🟢 Set") if config.GOOGLE_CLIENT_SECRET else L("⚪ Sin configurar", "⚪ Not set")),
            (L("URI de redirección", "Redirect URI"), f"<code>{esc(redirect)}</code>" if redirect else L("⚠️ Pon antes la URL de la web app", "⚠️ Set the web app URL first")),
        ]),
        r_footer(L("Registra esa URI de redirección exactamente igual en Google Cloud.",
                   "Register that redirect URI exactly as shown in Google Cloud.")),
    ]
    if note:
        blocks.insert(2, r_quote(note))
    kb = [
        [Btn("🔑 Client ID / secret", callback_data="cfg:gid")],
        [_guide_btn("gdrive", "gdrive:cfg")],
        back(back_cb),
    ]
    return rich(*blocks), Markup(kb)


@owner_only
async def gdrive_creds_menu(update, context):
    await update.callback_query.answer()
    context.user_data.pop("pending_setup", None)
    text, kb = gdrive_creds_content()
    await show(update, text, kb)


@owner_only
async def cfg_gid_prompt(update, context):
    await _prompt(
        update, context, "gid", "Google Client ID / secret",
        [L("Envía el <b>Client ID</b> y el <b>Client secret</b> en un mensaje, separados por un espacio.",
           "Send the <b>Client ID</b> and the <b>Client secret</b> in one message, separated by a space."),
         "<code>1234-abc.apps.googleusercontent.com GOCSPX-xxxxxxxx</code>"],
        "gdrive:cfg", "gdrive",
    )


async def _finish(update, context, pending: dict, text: str, kb: Markup):
    context.user_data.pop("pending_setup", None)
    await push(context, pending, text, kb)


async def handle_pending_text(update, context) -> bool:
    pending = context.user_data.get("pending_setup")
    if not pending:
        return False
    raw = (update.effective_message.text or "").strip()
    try:
        await update.effective_message.delete()
    except Exception:
        pass
    kind = pending["kind"]
    manager = context.bot_data.get("userbot_manager")

    async def retry(msg: str):
        text, kb = _prompt_content(L("Inténtalo de nuevo", "Try again"), [esc(msg)], pending.get("back", "settings:menu"))
        await push(context, pending, text, kb)

    if kind in ("folder_name", "folder_rename", "folder_mkdir"):
        import folders
        if kind == "folder_name":
            context.user_data.pop("pending_setup", None)
            await _add_named_folder(update, context, pending, raw)
        elif kind == "folder_rename":
            try:
                await folders.rename(pending["old"], raw)
                text, kb = folders_content(L(f"✅ Renombrada: {esc(pending['old'])} → {esc(raw)}",
                                             f"✅ Renamed: {esc(pending['old'])} → {esc(raw)}"))
            except folders.FolderError:
                text, kb = folders_content(L("⚠️ Nombre no válido o repetido (sin / : \\, máx. 30 caracteres).",
                                             "⚠️ Invalid or duplicate name (no / : \\, max 30 characters)."))
            await _finish(update, context, pending, text, kb)
        else:
            context.user_data.pop("pending_setup", None)
            st = _browse_state(context)
            if st:
                try:
                    st["path"] = folders.make_subdir(st["path"], raw)
                    st["page"] = 0
                except (folders.FolderError, OSError):
                    pass
                text, kb = browse_content(st)
                await push(context, pending, text, kb)
        return True

    if kind == "folder":
        m = re.match(r"^(.+?)\s+(/\S.*)$", raw)
        if not m:
            text, kb = folders_content(L("⚠️ Formato: <code>Nombre /media/ruta</code>", "⚠️ Format: <code>Name /media/path</code>"))
            await _finish(update, context, pending, text, kb)
            return True
        name, path = m.group(1).strip(), os.path.normpath(m.group(2).strip())
        if re.search(r"[:/\\]", name) or len(name.encode()) > 30:
            text, kb = folders_content(L("⚠️ Nombre no válido (sin / : \\ y corto).", "⚠️ Invalid name (no / : \\ and keep it short)."))
        elif name in config.FOLDERS:
            text, kb = folders_content(L("⚠️ Ya existe una carpeta con ese nombre.", "⚠️ A folder with that name already exists."))
        else:
            try:
                os.makedirs(path, exist_ok=True)
            except OSError:
                pass
            config.FOLDERS[name] = path
            config.FOLDER_MEDIA[name] = ""
            await config.save_folders()
            text, kb = folders_content(L(f"✅ Añadida: {esc(name)} → {esc(path)} · {path_status(path)}",
                                         f"✅ Added: {esc(name)} → {esc(path)} · {path_status(path)}"))
        await _finish(update, context, pending, text, kb)
        return True

    if kind == "tunnel_token":
        token = raw.replace("cloudflared service install", "").replace("cloudflared tunnel run --token", "").strip()
        if not tunnel.valid_token(token):
            text, kb = await tunnel_content(L("⚠️ Ese token no parece válido (es una cadena larga sin espacios).",
                                              "⚠️ That does not look like a valid token (a long string without spaces)."))
        else:
            await db.set_setting("cf_token", token)
            ok, why = await tunnel.start()
            text, kb = await tunnel_content(L("✅ Token guardado y túnel iniciado.", "✅ Token saved and tunnel started.") if ok
                                            else L("✅ Token guardado.", "✅ Token saved."))
        await _finish(update, context, pending, text, kb)
        return True

    if kind == "lan_url":
        import lan_access
        url = lan_access.normalize_url(raw)
        if url:
            await lan_access.set_url(url)
            text, kb = await lan_content(L("✅ Dirección guardada.", "✅ Address saved."))
        else:
            text, kb = await lan_content(L("⚠️ Esa dirección no es válida.", "⚠️ That address is not valid."))
        await _finish(update, context, pending, text, kb)
        return True

    if kind == "web_url":
        url = raw.rstrip("/")
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            text, kb = web_content(L("⚠️ Debe ser una URL que empiece por https://", "⚠️ It must be a URL starting with https://"))
        else:
            await config.set_runtime("WEBAPP_URL", url)
            text, kb = web_content(L("✅ URL guardada.", "✅ URL saved."))
        await _finish(update, context, pending, text, kb)
        return True

    if kind == "api":
        parts = raw.split()
        if len(parts) != 2 or not parts[0].isdigit() or not re.fullmatch(r"[0-9a-fA-F]{32}", parts[1]):
            await retry(L("Formato esperado: API_ID (números) y API_HASH (32 caracteres hex).",
                          "Expected format: API_ID (digits) and API_HASH (32 hex characters)."))
            return True
        await config.set_runtime("API_ID", parts[0])
        await config.set_runtime("API_HASH", parts[1])
        if manager:
            manager.api_id, manager.api_hash = config.API_ID, config.API_HASH
        text, kb = userbot_creds_content(L("✅ Credenciales guardadas.", "✅ Credentials saved."))
        await _finish(update, context, pending, text, kb)
        return True

    if kind == "channel":
        if not re.fullmatch(r"-?\d{5,}", raw):
            await retry(L("El ID del canal es un número, normalmente empieza por -100.",
                          "The channel ID is a number, usually starting with -100."))
            return True
        value = raw if raw.startswith("-") else f"-100{raw}" if len(raw) < 13 else raw
        await config.set_runtime("CHANNEL_ID", value)
        text, kb = userbot_creds_content(L("✅ Canal guardado.", "✅ Channel saved."))
        await _finish(update, context, pending, text, kb)
        return True

    if kind == "gid":
        parts = raw.split()
        if len(parts) != 2:
            await retry(L("Envía Client ID y Client secret separados por un espacio.",
                          "Send the Client ID and Client secret separated by a space."))
            return True
        await config.set_runtime("GOOGLE_CLIENT_ID", parts[0])
        await config.set_runtime("GOOGLE_CLIENT_SECRET", parts[1])
        text, kb = gdrive_creds_content(L("✅ Credenciales guardadas.", "✅ Credentials saved."))
        await _finish(update, context, pending, text, kb)
        return True

    import handlers_clients
    handled = await handlers_clients.handle_pending(update, context, pending, raw, _finish, retry)
    if handled:
        return True

    import handlers_tools
    handled = await handlers_tools.handle_pending(update, context, pending, raw, _finish, retry)
    if handled:
        return True

    context.user_data.pop("pending_setup", None)
    return False


@authorized_only
async def setup_command(update, context):
    if update.effective_user.id != config.OWNER_ID:
        return
    if not config.LANGUAGE:
        text, kb = language_content(first_run=True)
        await show(update, text, kb)
        return
    text, kb = await hub_content()
    await show(update, text, kb)
