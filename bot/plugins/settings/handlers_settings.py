import asyncio
import logging
import urllib.parse

from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, KeyboardButtonRequestUsers, ReplyKeyboardMarkup, ReplyKeyboardRemove,
)
from telegram.constants import ParseMode
from telegram.ext import ConversationHandler, MessageHandler, CommandHandler, CallbackQueryHandler, filters

import config
import db
import prowlarr
import keyboards
import real_debrid
import torbox
import tmdb_helper
import torrent_search
from i18n import L
from rich_ui import esc, header, r_h, r_p, r_kv_table, r_table, r_footer, r_ul, r_quote, rich
from utils import owner_only

logger = logging.getLogger(__name__)

RD_TOKEN_INPUT, TB_TOKEN_INPUT, TMDB_TOKEN_INPUT = range(3)


async def rd_is_enabled() -> bool:
    enabled = await db.get_setting("rd_enabled", "0")
    token = await db.get_setting("rd_token")
    return enabled == "1" and bool(token)


async def get_rd_token():
    return await db.get_setting("rd_token")


async def tb_is_enabled() -> bool:
    enabled = await db.get_setting("tb_enabled", "0")
    token = await db.get_setting("tb_token")
    return enabled == "1" and bool(token)


async def get_tb_token():
    return await db.get_setting("tb_token")


async def available_providers() -> list[str]:
    out = []
    if await rd_is_enabled():
        out.append("realdebrid")
    if await tb_is_enabled():
        out.append("torbox")
    import torrent_clients
    out.extend(await torrent_clients.enabled_keys())
    return out


def _labels() -> dict:
    import torrent_clients
    out = {"realdebrid": "💳 Real-Debrid", "torbox": "📦 TorBox"}
    for k, c in torrent_clients.CLIENTS.items():
        out[k] = f"{c['icon']} {c['label']}"
    return out


PROVIDER_LABELS = _labels()


@owner_only
async def rd_menu(update, context):
    query = update.callback_query
    await query.answer()
    token = await db.get_setting("rd_token")
    enabled = await db.get_setting("rd_enabled", "0") == "1"

    blocks = [r_h("Real-Debrid", 2, "💳")]
    kb = []

    if not token:
        blocks.append(r_p("No tienes ningún token configurado."))
        kb.append([InlineKeyboardButton("🔑 Configurar token", callback_data="rd:set_token")])
    else:
        pairs = [("Estado", "🟢 Activado" if enabled else "🔴 Desactivado")]
        try:
            info = await real_debrid.get_user_info(token)
            tipo = info.get("type", "?")
            pairs.append(("Cuenta", esc(tipo)))
            if tipo == "premium":
                dias = (info.get("premium") or 0) // 86400
                vencimiento = (info.get("expiration") or "")[:10]
                pairs.append(("Premium", f"{dias} día(s) · vence {esc(vencimiento)}"))
            puntos = info.get("points")
            if puntos is not None:
                pairs.append(("Puntos", esc(puntos)))
            if info.get("username"):
                pairs.append(("Usuario", esc(info.get("username"))))
        except Exception:
            pairs.append(("Cuenta", "<i>No se pudo consultar ahora mismo</i>"))
        blocks.append(r_kv_table(pairs))

        toggle_label = "🔴 Desactivar" if enabled else "🟢 Activar"
        kb.append([InlineKeyboardButton(toggle_label, callback_data="rd:toggle")])
        kb.append([InlineKeyboardButton("🔑 Cambiar token", callback_data="rd:set_token")])
        kb.append([InlineKeyboardButton("🗑️ Eliminar token", callback_data="rd:remove_token")])
        kb.append([InlineKeyboardButton("🧹 Vaciar cuenta RD", callback_data="rd:purge_confirm")])

    kb.append([InlineKeyboardButton("⬅️ Proveedores", callback_data="prov:menu")])

    await query.edit_message_text(rich(*blocks), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))


@owner_only
async def providers_menu(update, context):
    query = update.callback_query
    await query.answer()
    import torrent_clients
    rd_token = await db.get_setting("rd_token")
    rd_on = await rd_is_enabled()
    tb_token = await db.get_setting("tb_token")
    tb_on = await tb_is_enabled()
    client_rows = [
        (f"{c['icon']} {c['label']}", "🟢 activado" if await c["module"].is_enabled() else "⚪ desactivado")
        for c in torrent_clients.CLIENTS.values()
    ]

    def state(token, on):
        if not token:
            return "⚪ sin token"
        return "🟢 activado" if on else "🔴 desactivado"

    text = rich(
        r_h("Proveedores de descarga", 2, "📥"),
        r_p("Cómo se descargan tus torrents antes de llegar al NAS. Al enviar un torrent, el bot te preguntará "
            "cuál usar (si hay más de uno activo)."),
        r_kv_table([
            ("💳 Real-Debrid", state(rd_token, rd_on)),
            ("📦 TorBox", state(tb_token, tb_on)),
            *client_rows,
        ]),
        r_footer("Real-Debrid y TorBox descargan en su nube; los clientes locales (qBittorrent, Transmission, Deluge) descargan directo con tu conexión."),
    )
    kb = [
        [InlineKeyboardButton("💳 Real-Debrid", callback_data="rd:menu"),
         InlineKeyboardButton("📦 TorBox", callback_data="tb:menu")],
        [InlineKeyboardButton("⬇️ qBittorrent", callback_data="cl:qbittorrent:menu"),
         InlineKeyboardButton("📡 Transmission", callback_data="cl:transmission:menu"),
         InlineKeyboardButton("🌊 Deluge", callback_data="cl:deluge:menu")],
        [InlineKeyboardButton("📖 Tutorial TorBox", callback_data="guide:torbox:prov:menu"),
         InlineKeyboardButton("📖 Tutorial Real-Debrid", callback_data="guide:realdebrid:prov:menu")],
        [InlineKeyboardButton("⬅️ Ajustes", callback_data="settings:menu")],
    ]
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))


@owner_only
async def tb_menu(update, context):
    query = update.callback_query
    await query.answer()
    token = await db.get_setting("tb_token")
    enabled = await db.get_setting("tb_enabled", "0") == "1"

    blocks = [r_h("TorBox", 2, "📦")]
    kb = []
    if not token:
        blocks.append(r_p("No tienes ningún API Token configurado."))
        kb.append([InlineKeyboardButton("🔑 Configurar token", callback_data="tb:set_token")])
    else:
        pairs = [("Estado", "🟢 Activado" if enabled else "🔴 Desactivado")]
        try:
            info = await torbox.get_user_info(token)
            pairs.append(("Plan", esc(torbox.plan_name(info.get("plan")))))
            if info.get("email"):
                pairs.append(("Cuenta", esc(info.get("email"))))
            if info.get("premium_expires_at"):
                pairs.append(("Vence", esc(str(info["premium_expires_at"])[:10])))
        except Exception:
            pairs.append(("Cuenta", "<i>No se pudo consultar ahora mismo</i>"))
        blocks.append(r_kv_table(pairs))
        kb.append([InlineKeyboardButton("🔴 Desactivar" if enabled else "🟢 Activar", callback_data="tb:toggle")])
        kb.append([InlineKeyboardButton("📦 Mi TorBox (ver y gestionar)", callback_data="tbl:p:0")])
        kb.append([InlineKeyboardButton("🔑 Cambiar token", callback_data="tb:set_token")])
        kb.append([InlineKeyboardButton("🗑️ Eliminar token", callback_data="tb:remove_token")])
    kb.append([InlineKeyboardButton("⬅️ Proveedores", callback_data="prov:menu")])
    await query.edit_message_text(rich(*blocks), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))


def _host(url: str) -> str:
    return urllib.parse.urlparse(url).netloc or url


def _src_state(src: dict) -> str:
    if not src["enabled"]:
        return "🔴 desactivado"
    return "⏸️ en pausa" if src["paused"] else "🟢 activo"


MODE_LABELS = {
    "builtin": ("🔎", L("Buscadores integrados", "Built-in sources")),
    "prowlarr": ("🧭", "Prowlarr"),
    "both": ("🔀", L("Ambos", "Both")),
}


def _mode_label(mode: str) -> str:
    icon, name = MODE_LABELS.get(mode, MODE_LABELS["builtin"])
    return f"{icon} {name}"


async def _sources_menu_content() -> tuple[str, InlineKeyboardMarkup]:
    sources = await torrent_search.describe_sources()
    mode = await prowlarr.get_mode()
    px_ok = await prowlarr.is_configured()
    rows = [[esc(s["label"]), _src_state(s), esc(_host(s["last"])) if s["last"] else "—"] for s in sources]
    text = rich(
        r_h("Buscadores de torrents", 2, "🔎"),
        r_p(L("Webs donde busca el bot. <b>Vienen todas apagadas</b>: activa las que quieras. Cada una tiene una URL "
              "principal y espejos de respaldo; si la principal falla, prueba los espejos y recuerda el que funcionó. "
              "También puedes buscar con tu propio <b>Prowlarr</b>.",
              "Sites the bot searches. <b>They all come switched off</b>: enable the ones you want. Each one has a main "
              "URL plus backup mirrors; if the main one fails the bot tries the mirrors and remembers the one that worked. "
              "You can also search with your own <b>Prowlarr</b>.")),
        r_kv_table([
            (L("Modo de búsqueda", "Search mode"), _mode_label(mode)),
            ("Prowlarr", L("🟢 Conectado", "🟢 Connected") if px_ok else L("⚪ Sin conectar", "⚪ Not connected")),
        ]),
        r_table(rows, header=["Buscador", "Estado", "Último host"]),
        r_footer("Toca un buscador para activarlo, probarlo o gestionar sus espejos."),
    )
    kb = [[InlineKeyboardButton("🔀 " + L("Modo de búsqueda", "Search mode"), callback_data="src:modes"),
           InlineKeyboardButton("🧭 Prowlarr", callback_data="px:menu")]]
    row = []
    for s in sources:
        dot = "🟢" if s["enabled"] else "🔴"
        row.append(InlineKeyboardButton(f"{dot} {s['name']}", callback_data=f"src:p:{s['key']}"))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton("🩺 Probar todos", callback_data="src:all"),
               InlineKeyboardButton("🌐 Salida alternativa", callback_data="src:px")])
    removed = torrent_search.removed_sources()
    kb.append([InlineKeyboardButton("➕ Añadir buscador", callback_data="src:new")]
              + ([InlineKeyboardButton(f"♻️ Restaurar de fábrica ({len(removed)})", callback_data="src:restore")] if removed else []))
    kb.append([InlineKeyboardButton("📖 Tutorial", callback_data="guide:sources:src:menu")])
    kb.append([InlineKeyboardButton("⬅️ Ajustes", callback_data="settings:menu")])
    return text, InlineKeyboardMarkup(kb)


async def _source_content(key: str, note: str | None = None) -> tuple[str, InlineKeyboardMarkup]:
    src = next(s for s in await torrent_search.describe_sources() if s["key"] == key)
    blocks = [
        r_h(src["name"], 2, "🔎"),
        r_kv_table([
            ("Estado", _src_state(src)),
            ("Tipo", esc(src["about"])),
            ("Último host que funcionó", esc(_host(src["last"])) if src["last"] else "—"),
        ]),
    ]
    if note:
        blocks.append(note)
    if src["admin_urls"]:
        blocks.append(r_p("<b>Espejos añadidos por ti</b> (se prueban primero):"))
        blocks.append(r_ul([f"<code>{esc(u)}</code>" for u in src["admin_urls"]]))
    if src["custom"]:
        blocks.append(r_p("<b>URL</b>:"))
        blocks.append(r_ul([f"<code>{esc(u)}</code>" for u in src["factory_urls"]]))
    else:
        blocks.append(r_p("<b>Espejos de fábrica</b>:"))
        blocks.append(r_ul([f"<code>{esc(u)}</code>" for u in src["factory_urls"]]))
        blocks.append(r_footer("Los de fábrica están escritos de memoria y pueden estar caídos o haber cambiado."))

    kb = [
        [InlineKeyboardButton("🔴 Desactivar" if src["enabled"] else "🟢 Activar", callback_data=f"src:tog:{key}"),
         InlineKeyboardButton("🧪 Probar", callback_data=f"src:t:{key}")],
        [InlineKeyboardButton("➕ Añadir espejo", callback_data=f"src:madd:{key}")],
    ]
    for i, u in enumerate(src["admin_urls"]):
        kb.append([InlineKeyboardButton(f"🗑️ Quitar {_host(u)}"[:60], callback_data=f"src:mdel:{key}:{i}")])
    if src["admin_urls"]:
        kb.append([InlineKeyboardButton("♻️ Quitar todos los míos", callback_data=f"src:mrst:{key}")])
    kb.append([InlineKeyboardButton("🗑️ Eliminar buscador", callback_data=f"src:del:{key}")])
    kb.append([InlineKeyboardButton("⬅️ Buscadores", callback_data="src:menu")])
    return rich(*blocks), InlineKeyboardMarkup(kb)


def _test_line(r: dict) -> str:
    if r["ok"]:
        return f"✅ <b>{r['count']}</b> resultados en {r['ms']} ms · <code>{esc(_host(r['base']))}</code>"
    return f"❌ {esc(r['error'] or 'sin respuesta')}"


@owner_only
async def sources_menu(update, context):
    query = update.callback_query
    await query.answer()
    context.user_data.pop("pending_mirror", None)
    text, kb = await _sources_menu_content()
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


@owner_only
async def source_menu(update, context):
    query = update.callback_query
    await query.answer()
    context.user_data.pop("pending_mirror", None)
    key = query.data.split(":")[2]
    if key not in torrent_search.SOURCES:
        return
    text, kb = await _source_content(key)
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


@owner_only
async def source_toggle(update, context):
    query = update.callback_query
    key = query.data.split(":")[2]
    on = await torrent_search.is_enabled(key)
    await torrent_search.set_enabled(key, not on)
    await query.answer("Desactivado" if on else "Activado")
    text, kb = await _source_content(key)
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


@owner_only
async def source_test(update, context):
    query = update.callback_query
    key = query.data.split(":")[2]
    await query.answer("Probando...")
    await query.edit_message_text(f"🧪 Probando <b>{esc(torrent_search.SOURCES[key]['name'])}</b>…", parse_mode=ParseMode.HTML)
    r = await torrent_search.test_source(key)
    text, kb = await _source_content(key, note=r_quote(_test_line(r)))
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


@owner_only
async def sources_test_all(update, context):
    query = update.callback_query
    await query.answer("Probando...")
    await query.edit_message_text("🩺 Probando todos los buscadores activos…")
    keys = await torrent_search.enabled_sources()
    results = await asyncio.gather(*(torrent_search.test_source(k) for k in keys))
    rows = []
    for k, r in zip(keys, results):
        rows.append([esc(torrent_search.SOURCES[k]["name"]), "✅" if r["ok"] else "❌",
                     str(r["count"]) if r["ok"] else "—", esc(_host(r["base"])) if r["ok"] else esc((r["error"] or "")[:60])])
    ok = sum(1 for r in results if r["ok"])
    text = rich(
        r_h("Resultado de las pruebas", 2, "🩺"),
        r_p(f"<b>{ok}</b> de <b>{len(keys)}</b> buscadores responden."),
        r_table(rows, header=["Buscador", "", "Result.", "Host / error"]),
        r_footer("Desactiva los que fallen o añade un espejo que funcione."),
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Buscadores", callback_data="src:menu")]])
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


@owner_only
async def source_mirror_prompt(update, context):
    query = update.callback_query
    await query.answer()
    key = query.data.split(":")[2]
    context.user_data["pending_mirror"] = {
        "key": key, "chat_id": query.message.chat_id, "message_id": query.message.message_id,
    }
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("✖️ Cancelar", callback_data=f"src:p:{key}")]])
    await query.edit_message_text(
        rich(
            r_h("Añadir espejo", 2, "➕"),
            r_p(f"Envía la URL del espejo de <b>{esc(torrent_search.SOURCES[key]['name'])}</b> "
                "(puedes mandar varias separadas por espacio). Lo probaré antes de guardarlo."),
            r_footer("Ejemplo: https://1337x.to"),
        ),
        parse_mode=ParseMode.HTML, reply_markup=kb,
    )


@owner_only
async def source_mirror_delete(update, context):
    query = update.callback_query
    _, _, key, idx = query.data.split(":")
    urls = await torrent_search.get_admin_urls(key)
    if idx.isdigit() and int(idx) < len(urls):
        urls.pop(int(idx))
        await torrent_search.set_admin_urls(key, urls)
    await query.answer("Quitado")
    text, kb = await _source_content(key)
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


@owner_only
async def source_mirror_reset(update, context):
    query = update.callback_query
    key = query.data.split(":")[2]
    await torrent_search.set_admin_urls(key, [])
    await db.delete_setting(f"src_last_{key}")
    await query.answer("Restablecido")
    text, kb = await _source_content(key)
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


@owner_only
async def source_mirror_save_anyway(update, context):
    query = update.callback_query
    key = query.data.split(":")[2]
    failed = context.user_data.pop("mirror_failed", {}).get(key, [])
    urls = await torrent_search.get_admin_urls(key)
    for u in failed:
        if u not in urls:
            urls.append(u)
    await torrent_search.set_admin_urls(key, urls)
    await query.answer("Guardado")
    text, kb = await _source_content(key, note=r_quote("💾 Guardado sin superar la prueba."))
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def _handle_mirror_text(update, context) -> bool:
    pending = context.user_data.pop("pending_mirror", None)
    if not pending:
        return False
    key = pending["key"]
    raw = update.effective_message.text or ""
    try:
        await update.effective_message.delete()
    except Exception:
        pass
    candidates = torrent_search.clean_candidates(key, raw)

    async def show(note, extra_kb=None):
        text, kb = await _source_content(key, note=note)
        if extra_kb:
            kb = InlineKeyboardMarkup([extra_kb] + list(kb.inline_keyboard))
        await context.bot.edit_message_text(
            chat_id=pending["chat_id"], message_id=pending["message_id"],
            text=text, parse_mode=ParseMode.HTML, reply_markup=kb,
        )

    if not candidates:
        await show(r_quote("⚠️ Eso no parece una URL válida."))
        return True
    await context.bot.edit_message_text(
        chat_id=pending["chat_id"], message_id=pending["message_id"], text="🧪 Probando el espejo…")
    saved = await torrent_search.get_admin_urls(key)
    lines, failed = [], []
    for u in candidates:
        r = await torrent_search.test_source(key, only_url=u)
        if r["ok"]:
            if u not in saved:
                saved.append(u)
            lines.append(f"✅ <code>{esc(_host(u))}</code> — {r['count']} resultados · guardado")
        else:
            failed.append(u)
            lines.append(f"❌ <code>{esc(_host(u))}</code> — {esc(r['error'] or 'sin respuesta')}")
    await torrent_search.set_admin_urls(key, saved)
    extra = None
    if failed:
        context.user_data.setdefault("mirror_failed", {})[key] = failed
        extra = [InlineKeyboardButton("💾 Guardar los fallidos igualmente", callback_data=f"src:msave:{key}")]
    await show(r_quote("<br/>".join(lines)), extra)
    return True


async def _proxy_content(note: str | None = None) -> tuple[str, InlineKeyboardMarkup]:
    enabled = (await db.get_setting("src_proxy_enabled", "0")) == "1"
    url = await db.get_setting("src_proxy_url", torrent_search.DEFAULT_PROXY_URL)
    blocks = [
        r_h("Salida alternativa", 2, "🌐"),
        r_p("Si una web de torrents no se puede abrir directamente desde tu red (bloqueos por nombre o por IP), "
            "el bot reintenta por este proxy. Solo lo usan los buscadores, no tus descargas."),
        r_kv_table([
            ("Estado", "🟢 Activada" if enabled else "🔴 Desactivada"),
            ("Proxy", f"<code>{esc(url)}</code>"),
        ]),
    ]
    if note:
        blocks.append(note)
    blocks.append(r_footer("Por defecto usa el contenedor WARP de Cloudflare incluido en el docker-compose (socks5://warp:1080)."))
    kb = [
        [InlineKeyboardButton("🔴 Desactivar" if enabled else "🟢 Activar", callback_data="src:pxtog"),
         InlineKeyboardButton("🧪 Probar", callback_data="src:pxtest")],
        [InlineKeyboardButton("✏️ Cambiar proxy", callback_data="src:pxurl"),
         InlineKeyboardButton("♻️ Valor por defecto", callback_data="src:pxrst")],
        [InlineKeyboardButton("⬅️ Buscadores", callback_data="src:menu")],
    ]
    return rich(*blocks), InlineKeyboardMarkup(kb)


@owner_only
async def proxy_menu(update, context):
    query = update.callback_query
    await query.answer()
    context.user_data.pop("pending_proxy", None)
    text, kb = await _proxy_content()
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


@owner_only
async def proxy_toggle(update, context):
    query = update.callback_query
    on = (await db.get_setting("src_proxy_enabled", "0")) == "1"
    await db.set_setting("src_proxy_enabled", "0" if on else "1")
    await query.answer("Desactivada" if on else "Activada")
    text, kb = await _proxy_content()
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


@owner_only
async def proxy_reset(update, context):
    query = update.callback_query
    await db.set_setting("src_proxy_url", torrent_search.DEFAULT_PROXY_URL)
    await db.set_setting("src_proxy_enabled", "1")
    await query.answer("Restablecido")
    text, kb = await _proxy_content()
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


@owner_only
async def proxy_test(update, context):
    query = update.callback_query
    await query.answer("Probando...")
    await query.edit_message_text("🧪 Probando la salida alternativa…")
    r = await torrent_search.test_proxy()
    lines = [("✅ " if r["ok"] else "❌ ") + esc(r["detail"] or "sin respuesta")]
    if r.get("nyaa"):
        lines.append(esc(r["nyaa"]))
    text, kb = await _proxy_content(note=r_quote("<br/>".join(lines)))
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


@owner_only
async def proxy_url_prompt(update, context):
    query = update.callback_query
    await query.answer()
    context.user_data["pending_proxy"] = {"chat_id": query.message.chat_id, "message_id": query.message.message_id}
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("✖️ Cancelar", callback_data="src:px")]])
    await query.edit_message_text(
        rich(
            r_h("Cambiar proxy", 2, "✏️"),
            r_p("Envía la dirección del proxy (SOCKS5 o HTTP)."),
            r_footer("Ejemplos: socks5://warp:1080 · socks5://192.168.1.10:1080 · http://usuario:clave@host:8080"),
        ),
        parse_mode=ParseMode.HTML, reply_markup=kb,
    )


async def _handle_proxy_text(update, context) -> bool:
    pending = context.user_data.pop("pending_proxy", None)
    if not pending:
        return False
    raw = (update.effective_message.text or "").strip()
    try:
        await update.effective_message.delete()
    except Exception:
        pass
    ok = bool(raw) and raw.split("://")[0].lower() in ("socks5", "socks5h", "http", "https") and "://" in raw
    if ok:
        await db.set_setting("src_proxy_url", raw)
        await db.set_setting("src_proxy_enabled", "1")
        note = r_quote("💾 Guardado y activado. Pulsa 🧪 Probar para comprobarlo.")
    else:
        note = r_quote("⚠️ La dirección debe empezar por socks5://, socks5h://, http:// o https://")
    text, kb = await _proxy_content(note=note)
    await context.bot.edit_message_text(chat_id=pending["chat_id"], message_id=pending["message_id"],
                                        text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
    return True


# ── Search mode and Prowlarr ────────────────────────────────────────────────────
async def _modes_content(note: str | None = None) -> tuple[str, InlineKeyboardMarkup]:
    mode = await prowlarr.get_mode()
    px_ok = await prowlarr.is_configured()
    blocks = [
        r_h(L("Modo de búsqueda", "Search mode"), 2, "🔀"),
        r_ul([
            L("<b>🔎 Buscadores integrados</b>: las webs que actives en Ajustes → Buscadores.",
              "<b>🔎 Built-in sources</b>: the sites you enable in Settings → Search sources."),
            L("<b>🧭 Prowlarr</b>: solo tu Prowlarr, que busca en todos sus indexadores.",
              "<b>🧭 Prowlarr</b>: only your Prowlarr, which searches all its indexers."),
            L("<b>🔀 Ambos</b>: junta los resultados de los dos y quita duplicados.",
              "<b>🔀 Both</b>: merges both result lists and removes duplicates."),
        ]),
        r_kv_table([(L("Modo actual", "Current mode"), _mode_label(mode))]),
    ]
    if not px_ok:
        blocks.append(r_quote(L("Para usar Prowlarr o Ambos, primero conecta Prowlarr.",
                                "To use Prowlarr or Both, connect Prowlarr first.")))
    if note:
        blocks.append(note)
    kb = []
    for m in prowlarr.MODES:
        if m != "builtin" and not px_ok:
            continue
        mark = "✅ " if m == mode else ""
        kb.append([InlineKeyboardButton(mark + _mode_label(m), callback_data=f"src:mode:{m}")])
    if not px_ok:
        kb.append([InlineKeyboardButton("🧭 " + L("Conectar Prowlarr", "Connect Prowlarr"), callback_data="px:menu")])
    kb.append([InlineKeyboardButton("⬅️ Buscadores", callback_data="src:menu")])
    return rich(*blocks), InlineKeyboardMarkup(kb)


@owner_only
async def search_modes_menu(update, context):
    query = update.callback_query
    await query.answer()
    text, kb = await _modes_content()
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


@owner_only
async def search_mode_set(update, context):
    query = update.callback_query
    mode = query.data.split(":")[2]
    if mode != "builtin" and not await prowlarr.is_configured():
        await query.answer(L("Primero conecta Prowlarr", "Connect Prowlarr first"), show_alert=True)
        return
    await prowlarr.set_mode(mode)
    await query.answer(_mode_label(mode))
    text, kb = await _modes_content()
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def _prowlarr_content(note: str | None = None) -> tuple[str, InlineKeyboardMarkup]:
    url, key = await prowlarr.get_config()
    blocks = [
        r_h("Prowlarr", 2, "🧭"),
        r_p(L("Opcional. Conecta tu Prowlarr y el bot buscará en todos sus indexadores con una sola consulta. "
              "Prowlarr se encarga de sus espejos y, con FlareSolverr, de las webs protegidas por Cloudflare.",
              "Optional. Connect your Prowlarr and the bot searches all its indexers with a single query. "
              "Prowlarr takes care of their mirrors and, with FlareSolverr, of sites protected by Cloudflare.")),
        r_kv_table([
            ("URL", f"<code>{esc(url)}</code>" if url else L("⚪ Sin configurar", "⚪ Not set")),
            ("API key", L("🔑 Guardada", "🔑 Saved") if key else L("⚪ Sin configurar", "⚪ Not set")),
            (L("Modo de búsqueda", "Search mode"), _mode_label(await prowlarr.get_mode())),
        ]),
    ]
    if note:
        blocks.append(note)
    blocks.append(r_footer(L("Si Prowlarr va en el mismo Docker que el bot (perfil prowlarr), la URL es http://prowlarr:9696.",
                             "If Prowlarr runs in the same Docker as the bot (prowlarr profile), the URL is http://prowlarr:9696.")))
    kb = [[InlineKeyboardButton("🔗 URL", callback_data="px:url"),
           InlineKeyboardButton("🔑 API key", callback_data="px:key")]]
    if url and key:
        kb.append([InlineKeyboardButton("🧪 " + L("Probar", "Test"), callback_data="px:test"),
                   InlineKeyboardButton("🔀 " + L("Modo de búsqueda", "Search mode"), callback_data="src:modes")])
        kb.append([InlineKeyboardButton("🗑️ " + L("Desconectar", "Disconnect"), callback_data="px:del")])
    kb.append([InlineKeyboardButton("📖 Tutorial", callback_data="guide:prowlarr:px:menu")])
    kb.append([InlineKeyboardButton("⬅️ Buscadores", callback_data="src:menu")])
    return rich(*blocks), InlineKeyboardMarkup(kb)


def _px_test_note(r: dict) -> str:
    if r["ok"]:
        return r_quote(L(f"✅ Conectado: Prowlarr {esc(r['version'] or '')} con <b>{r['indexers']}</b> indexadores de torrents activos ({r['ms']} ms).",
                         f"✅ Connected: Prowlarr {esc(r['version'] or '')} with <b>{r['indexers']}</b> enabled torrent indexers ({r['ms']} ms).")
                       + ("" if r["indexers"] else L(" Añade indexadores en Prowlarr para tener resultados.",
                                                     " Add indexers in Prowlarr to get results.")))
    return r_quote(L("❌ No funciona: ", "❌ Not working: ") + esc(r["error"] or ""))


@owner_only
async def prowlarr_menu(update, context):
    query = update.callback_query
    await query.answer()
    context.user_data.pop("pending_prowlarr", None)
    text, kb = await _prowlarr_content()
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


@owner_only
async def prowlarr_prompt(update, context):
    query = update.callback_query
    await query.answer()
    field = query.data.split(":")[1]
    context.user_data["pending_prowlarr"] = {"field": field, "chat_id": query.message.chat_id,
                                             "message_id": query.message.message_id}
    if field == "url":
        body = [r_p(L("Envía la URL de tu Prowlarr.", "Send the URL of your Prowlarr.")),
                r_footer(L("Ejemplos: http://prowlarr:9696 (perfil prowlarr de este proyecto) · http://192.168.1.10:9696",
                           "Examples: http://prowlarr:9696 (this project's prowlarr profile) · http://192.168.1.10:9696"))]
    else:
        body = [r_p(L("Envía la API key de Prowlarr. Está en Prowlarr → Settings → General → Security → API Key. "
                      "Borraré tu mensaje al guardarla.",
                      "Send the Prowlarr API key. It is in Prowlarr → Settings → General → Security → API Key. "
                      "I will delete your message once saved."))]
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("✖️ Cancelar", callback_data="px:menu")]])
    await query.edit_message_text(rich(r_h("Prowlarr", 2, "🧭"), *body), parse_mode=ParseMode.HTML, reply_markup=kb)


async def _handle_prowlarr_text(update, context) -> bool:
    pending = context.user_data.pop("pending_prowlarr", None)
    if not pending:
        return False
    raw = (update.effective_message.text or "").strip()
    try:
        await update.effective_message.delete()
    except Exception:
        pass
    note = None
    if pending["field"] == "url":
        url = prowlarr.normalize_url(raw)
        if url:
            await prowlarr.save(url=url)
        else:
            note = r_quote(L("⚠️ Esa URL no es válida.", "⚠️ That URL is not valid."))
    elif raw:
        await prowlarr.save(key=raw)
    if note is None and await prowlarr.is_configured():
        note = _px_test_note(await prowlarr.test())
    elif note is None:
        note = r_quote(L("💾 Guardado. Falta el otro dato para conectar.", "💾 Saved. The other value is still missing."))
    text, kb = await _prowlarr_content(note=note)
    await context.bot.edit_message_text(chat_id=pending["chat_id"], message_id=pending["message_id"],
                                        text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
    return True


@owner_only
async def prowlarr_test_cb(update, context):
    query = update.callback_query
    await query.answer(L("Probando…", "Testing…"))
    text, kb = await _prowlarr_content(note=_px_test_note(await prowlarr.test()))
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


@owner_only
async def prowlarr_delete_cb(update, context):
    query = update.callback_query
    await prowlarr.clear()
    await query.answer(L("Prowlarr desconectado", "Prowlarr disconnected"))
    text, kb = await _prowlarr_content(note=r_quote(L("🗑️ Desconectado. El modo de búsqueda vuelve a «Buscadores integrados».",
                                                      "🗑️ Disconnected. The search mode is back to «Built-in sources».")))
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


@owner_only
async def tmdb_menu(update, context):
    query = update.callback_query
    await query.answer()
    key = await tmdb_helper.get_api_key()
    enabled = await db.get_setting("tmdb_enabled", "0") == "1"
    blocks = [
        r_h("TMDB", 2, "🎞️"),
        r_p("Opcional. Al descargar en la raíz de Peliculas o Series, crea la carpeta con el nombre "
            "del título según TMDB (en español si el original es español, si no en inglés). "
            "No renombra archivos y no actúa dentro de subcarpetas."),
        r_kv_table([
            ("API Token", "🔑 configurado" if key else "⚪ sin configurar"),
            ("Estado", "🟢 Activado" if (key and enabled) else "🔴 Desactivado"),
        ]),
    ]
    kb = []
    if key:
        kb.append([InlineKeyboardButton("🔴 Desactivar" if enabled else "🟢 Activar", callback_data="tmdb:toggle")])
    kb.append([InlineKeyboardButton("🔑 Cambiar token" if key else "🔑 Configurar token", callback_data="tmdb:set_token")])
    if key:
        kb.append([InlineKeyboardButton("🗑️ Eliminar token", callback_data="tmdb:remove_token")])
    kb.append([InlineKeyboardButton("⬅️ Ajustes", callback_data="settings:menu")])
    await query.edit_message_text(rich(*blocks), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))


@owner_only
async def tmdb_toggle(update, context):
    query = update.callback_query
    if not await tmdb_helper.get_api_key():
        await query.answer("Primero configura el API Token.", show_alert=True)
        return
    enabled = await db.get_setting("tmdb_enabled", "0") == "1"
    await db.set_setting("tmdb_enabled", "0" if enabled else "1")
    await query.answer("Desactivado" if enabled else "Activado")
    await tmdb_menu(update, context)


@owner_only
async def tmdb_remove_token(update, context):
    query = update.callback_query
    await query.answer()
    await db.delete_setting("tmdb_token")
    await db.set_setting("tmdb_enabled", "0")
    await tmdb_menu(update, context)


@owner_only
async def tmdb_set_token_entry(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🔑 Envía tu API Key de TMDB (la clave de API v3).\n\n"
        "Gratis en https://www.themoviedb.org/settings/api\n\nEnvía /cancel para cancelar."
    )
    return TMDB_TOKEN_INPUT


@owner_only
async def tmdb_set_token_receive(update, context):
    key = update.message.text.strip()
    if not await tmdb_helper.check_key(key):
        await update.message.reply_text("❌ Esa clave no parece válida. Inténtalo de nuevo o /cancel.")
        return TMDB_TOKEN_INPUT
    await db.set_setting("tmdb_token", key)
    await db.set_setting("tmdb_enabled", "1")
    await update.message.reply_text("✅ Clave guardada y TMDB activado.", reply_markup=keyboards.main_menu())
    return ConversationHandler.END


def build_tmdb_token_conversation():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(tmdb_set_token_entry, pattern="^tmdb:set_token$")],
        states={TMDB_TOKEN_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, tmdb_set_token_receive)]},
        fallbacks=[CommandHandler("cancel", rd_cancel)],
    )


@owner_only
async def tb_toggle(update, context):
    query = update.callback_query
    if not await db.get_setting("tb_token"):
        await query.answer("Primero configura un token.", show_alert=True)
        return
    enabled = await db.get_setting("tb_enabled", "0") == "1"
    await db.set_setting("tb_enabled", "0" if enabled else "1")
    await query.answer("Desactivado" if enabled else "Activado")
    await tb_menu(update, context)


@owner_only
async def tb_remove_token(update, context):
    query = update.callback_query
    await query.answer()
    await db.delete_setting("tb_token")
    await db.set_setting("tb_enabled", "0")
    await tb_menu(update, context)


@owner_only
async def rd_toggle(update, context):
    query = update.callback_query
    token = await db.get_setting("rd_token")
    if not token:
        await query.answer("Primero configura un token.", show_alert=True)
        return
    enabled = await db.get_setting("rd_enabled", "0") == "1"
    await db.set_setting("rd_enabled", "0" if enabled else "1")
    await query.answer("Desactivado" if enabled else "Activado")
    await rd_menu(update, context)


@owner_only
async def rd_remove_token(update, context):
    query = update.callback_query
    await query.answer()
    await db.delete_setting("rd_token")
    await db.set_setting("rd_enabled", "0")
    await rd_menu(update, context)


@owner_only
async def rd_purge_confirm(update, context):
    query = update.callback_query
    await query.answer()
    kb = [
        [InlineKeyboardButton("✅ Sí, borrar todo", callback_data="rd:purge_do")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="rd:menu")],
    ]
    await query.edit_message_text(
        header("🧹", "Vaciar cuenta de Real-Debrid") + "\n\n"
        "Esto borrará TODOS los torrents y TODO el historial de descargas de tu "
        "cuenta de Real-Debrid. No se puede deshacer.\n\n¿Seguro?",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(kb),
    )


@owner_only
async def rd_purge_do(update, context):
    query = update.callback_query
    await query.answer()
    token = await db.get_setting("rd_token")
    if not token:
        await query.edit_message_text("⚠️ No hay token de Real-Debrid configurado.")
        return
    await query.edit_message_text("🧹 Vaciando cuenta de Real-Debrid, esto puede tardar un poco...")
    try:
        result = await real_debrid.purge_account(token)
        await query.edit_message_text(
            f"✅ Cuenta vaciada: {result['torrents']} torrent(s) y {result['downloads']} descarga(s) eliminados."
        )
    except Exception as e:
        await query.edit_message_text(f"❌ Error al vaciar la cuenta: {e}")


@owner_only
async def rd_set_token_entry(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🔑 Envia tu API Token de Real-Debrid.\n\n"
        "Puedes generarlo en https://real-debrid.com/apitoken\n\n"
        "Envia /cancel para cancelar."
    )
    return RD_TOKEN_INPUT


@owner_only
async def rd_set_token_receive(update, context):
    token = update.message.text.strip()
    valid = False
    try:
        valid = await real_debrid.check_token(token)
    except Exception:
        valid = False

    if not valid:
        await update.message.reply_text("❌ Ese token no parece valido. Intentalo de nuevo o /cancel.")
        return RD_TOKEN_INPUT

    await db.set_setting("rd_token", token)
    await db.set_setting("rd_enabled", "1")
    await update.message.reply_text(
        "✅ Token guardado y plugin de Real-Debrid activado.",
        reply_markup=keyboards.main_menu(),
    )
    return ConversationHandler.END


@owner_only
async def rd_cancel(update, context):
    await update.message.reply_text("Operacion cancelada.", reply_markup=keyboards.main_menu())
    return ConversationHandler.END


@owner_only
async def tb_set_token_entry(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🔑 Envía tu API Token de TorBox.\n\n"
        "Lo encuentras en https://torbox.app/settings (sección API).\n\n"
        "Envía /cancel para cancelar."
    )
    return TB_TOKEN_INPUT


@owner_only
async def tb_set_token_receive(update, context):
    token = update.message.text.strip()
    if not await torbox.check_token(token):
        await update.message.reply_text("❌ Ese token no parece válido. Inténtalo de nuevo o /cancel.")
        return TB_TOKEN_INPUT
    await db.set_setting("tb_token", token)
    await db.set_setting("tb_enabled", "1")
    await update.message.reply_text("✅ Token guardado y TorBox activado.", reply_markup=keyboards.main_menu())
    return ConversationHandler.END


def build_tb_token_conversation():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(tb_set_token_entry, pattern="^tb:set_token$")],
        states={TB_TOKEN_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, tb_set_token_receive)]},
        fallbacks=[CommandHandler("cancel", rd_cancel)],
    )


def build_rd_token_conversation():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(rd_set_token_entry, pattern="^rd:set_token$")],
        states={
            RD_TOKEN_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, rd_set_token_receive)],
        },
        fallbacks=[CommandHandler("cancel", rd_cancel)],
    )


LIMIT_RANGES = {
    ("aria2", "parallel"): (1, 4),
    ("aria2", "workers"): (1, 16),
    ("telegram", "parallel"): (1, 4),
    ("gdrive", "parallel"): (1, 4),
}

LIMIT_KEYS = {
    ("aria2", "parallel"): "max_parallel_aria2",
    ("aria2", "workers"): "aria2_workers",
    ("telegram", "parallel"): "max_parallel_telegram",
    ("gdrive", "parallel"): "max_parallel_gdrive",
}

LIMIT_DEFAULTS = {
    ("aria2", "parallel"): 1,
    ("aria2", "workers"): 16,
    ("telegram", "parallel"): 1,
    ("gdrive", "parallel"): 1,
}

LIMIT_LABELS = {"parallel": "Descargas paralelas", "workers": "Hilos por descarga"}
GROUP_LABELS = {"aria2": "Aria2", "telegram": "Telegram (userbot)", "gdrive": "Google Drive"}


async def _get_limit(group: str, kind: str) -> int:
    key = LIMIT_KEYS[(group, kind)]
    value = await db.get_setting(key, str(LIMIT_DEFAULTS[(group, kind)]))
    try:
        return int(value)
    except (TypeError, ValueError):
        return LIMIT_DEFAULTS[(group, kind)]


async def extract_content() -> tuple[str, InlineKeyboardMarkup]:
    on = await db.get_setting("extract_delete_original", "0") == "1"
    text = rich(
        r_h(L("Descompresión automática", "Automatic extraction"), 2, "📦"),
        r_p(L("Cuando una descarga se descomprime automáticamente al terminar, ¿qué se hace con el archivo comprimido original?",
              "When a download is extracted automatically after finishing, what should happen to the original archive?")),
        r_kv_table([(L("Archivo original", "Original archive"),
                     L("🗑️ Se elimina", "🗑️ Deleted") if on else L("📁 Se conserva", "📁 Kept"))]),
        r_footer(L("Descomprimir a mano un archivo desde el gestor de archivos nunca borra el original.",
                   "Extracting a file manually from the file manager never deletes the original.")),
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(L("📁 Conservar el original", "📁 Keep the original") if on else L("🗑️ Eliminar el original", "🗑️ Delete the original"),
                              callback_data="extract:toggle")],
        [InlineKeyboardButton(L("⬅️ Ajustes", "⬅️ Settings"), callback_data="settings:menu")],
    ])
    return text, kb


@owner_only
async def extract_menu(update, context):
    await update.callback_query.answer()
    text, kb = await extract_content()
    await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


@owner_only
async def extract_toggle(update, context):
    on = await db.get_setting("extract_delete_original", "0") == "1"
    await db.set_setting("extract_delete_original", "0" if on else "1")
    await update.callback_query.answer(L("Guardado", "Saved"))
    text, kb = await extract_content()
    await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


@owner_only
async def limits_menu(update, context):
    query = update.callback_query
    await query.answer()
    kb = [
        [InlineKeyboardButton("⚙️ Aria2", callback_data="limits:group:aria2")],
        [InlineKeyboardButton("⚙️ Telegram", callback_data="limits:group:telegram")],
        [InlineKeyboardButton("⚙️ Google Drive", callback_data="limits:group:gdrive")],
        [InlineKeyboardButton("⬅️ Ajustes", callback_data="settings:menu")],
    ]
    await query.edit_message_text(
        header("⚙️", "Límites de descargas") + "\n\n¿Qué motor quieres ajustar?",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(kb),
    )


@owner_only
async def limits_group_menu(update, context):
    query = update.callback_query
    await query.answer()
    group = query.data.split(":")[2]

    parallel = await _get_limit(group, "parallel")
    lo_p, hi_p = LIMIT_RANGES[(group, "parallel")]

    rows = [["Descargas paralelas", f"<b>{parallel}</b>", f"{lo_p}–{hi_p}"]]
    kb = [[InlineKeyboardButton("🔢 Descargas paralelas", callback_data=f"limits:set:{group}:parallel")]]

    if group == "aria2":
        workers = await _get_limit(group, "workers")
        lo_w, hi_w = LIMIT_RANGES[(group, "workers")]
        rows.append(["Conexiones por descarga", f"<b>{workers}</b>", f"{lo_w}–{hi_w}"])
        kb.append([InlineKeyboardButton("🧵 Conexiones por descarga", callback_data=f"limits:set:{group}:workers")])

    kb.append([InlineKeyboardButton("⬅️ Límites", callback_data="limits:menu")])
    text = rich(r_h(GROUP_LABELS[group], 2, "⚙️"), r_table(rows, header=["Ajuste", "Valor", "Rango"]))
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))


@owner_only
async def limits_set_entry(update, context):
    query = update.callback_query
    await query.answer()
    _, _, group, kind = query.data.split(":", 3)
    lo, hi = LIMIT_RANGES[(group, kind)]
    context.user_data["pending_limit"] = {"group": group, "kind": kind}
    await query.edit_message_text(
        f"Envía un número entre <b>{lo}</b> y <b>{hi}</b> para <b>{esc(LIMIT_LABELS[kind])}</b> de {esc(GROUP_LABELS[group])}.\n\n"
        "Envía /cancel para cancelar.",
        parse_mode=ParseMode.HTML,
    )


async def handle_pending_text(update, context) -> bool:
    if context.user_data.get("pending_src"):
        return await _handle_new_source_text(update, context)

    if context.user_data.get("pending_mirror"):
        return await _handle_mirror_text(update, context)

    if context.user_data.get("pending_proxy"):
        return await _handle_proxy_text(update, context)

    if context.user_data.get("pending_prowlarr"):
        return await _handle_prowlarr_text(update, context)


    if context.user_data.get("pending_add_user"):
        raw = update.effective_message.text.strip()
        try:
            new_id = int(raw)
        except ValueError:
            await update.effective_message.reply_text("⚠️ Eso no es un ID numérico válido. Envíamelo de nuevo, o /cancel.")
            return True
        context.user_data.pop("pending_add_user", None)
        await db.add_authorized_user(new_id)
        await update.effective_message.reply_text(
            f"✅ Usuario <code>{new_id}</code> añadido. Ya puede usar el bot (sin acceso a Ajustes).",
            parse_mode=ParseMode.HTML,
            reply_markup=ReplyKeyboardRemove(),
        )
        try:
            await context.bot.send_message(
                chat_id=new_id,
                text="🎉 Ahora tienes acceso a este bot de descargas. Usa /start para empezar.",
            )
        except Exception:
            pass
        return True

    pending = context.user_data.get("pending_limit")
    if not pending:
        return False

    group, kind = pending["group"], pending["kind"]
    lo, hi = LIMIT_RANGES[(group, kind)]
    raw = update.effective_message.text.strip()

    try:
        value = int(raw)
    except ValueError:
        await update.effective_message.reply_text(f"⚠️ Eso no es un número. Envía un valor entre {lo} y {hi}.")
        return True

    if not (lo <= value <= hi):
        await update.effective_message.reply_text(f"⚠️ Debe estar entre {lo} y {hi}. Inténtalo de nuevo.")
        return True

    await db.set_setting(LIMIT_KEYS[(group, kind)], str(value))
    context.user_data.pop("pending_limit", None)

    await update.effective_message.reply_text(
        f"✅ <b>{esc(LIMIT_LABELS[kind])}</b> de {esc(GROUP_LABELS[group])} ajustado a <b>{value}</b>.",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboards.main_menu(),
    )
    return True


@owner_only
async def users_menu(update, context):
    query = update.callback_query
    await query.answer()
    users = await db.list_authorized_users()

    rows = [["👑", f"<code>{config.OWNER_ID}</code>", "Propietario", "—"]]
    # Note: tg://user?id=... buttons are rejected by Telegram (Button_user_invalid) unless the bot can
    # resolve the user, so profile links are only offered when a public @username is known.
    kb = []
    for u in users:
        added = (u.get("added_at") or "")[:10]
        name = u.get("first_name") or u.get("username") or ""
        rows.append(["👤", f"<code>{u['user_id']}</code>", esc(name) or "Usuario", esc(added)])
        row = [InlineKeyboardButton(f"🗑️ Quitar {name or u['user_id']}"[:40], callback_data=f"users:remove:{u['user_id']}")]
        if u.get("username"):
            row.insert(0, InlineKeyboardButton(f"👤 @{u['username']}"[:36], url=f"https://t.me/{u['username']}"))
        kb.append(row)

    kb.append([InlineKeyboardButton("➕ Añadir usuario", callback_data="users:add")])
    kb.append([InlineKeyboardButton("⬅️ Ajustes", callback_data="settings:menu")])

    blocks = [r_h("Usuarios con acceso", 2, "👥"), r_table(rows, header=["", "ID", "Rol", "Desde"])]
    if not users:
        blocks.append(r_p("<i>No hay usuarios adicionales todavía.</i>"))
    blocks.append(r_footer("Los usuarios normales no tienen acceso a Ajustes."))
    await query.edit_message_text(rich(*blocks), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))


@owner_only
async def users_add_entry(update, context):
    query = update.callback_query
    await query.answer()
    context.user_data["pending_add_user"] = True
    await query.edit_message_text(
        "Envíame el ID numérico de Telegram del usuario que quieres añadir, o usa el botón de "
        "abajo para elegirlo directamente de tus contactos.\n\n"
        "Envía /cancel para cancelar."
    )
    kb = ReplyKeyboardMarkup(
        [[KeyboardButton(
            text="📇 Elegir usuario de mis contactos",
            request_users=KeyboardButtonRequestUsers(request_id=1, user_is_bot=False),
        )]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="👇 O toca aquí para elegirlo de la lista:",
        reply_markup=kb,
    )


@owner_only
async def users_pick_received(update, context):
    if not context.user_data.get("pending_add_user"):
        return

    shared = update.message.users_shared
    user_ids = getattr(shared, "user_ids", None)
    if not user_ids:
        users = getattr(shared, "users", None) or []
        user_ids = [u.user_id for u in users]

    if not user_ids:
        await update.message.reply_text(
            "⚠️ No se pudo obtener el ID de ese usuario (a veces Telegram no lo comparte si la "
            "privacidad de esa cuenta lo restringe). Escríbeme el ID manualmente en su lugar.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    context.user_data.pop("pending_add_user", None)
    for uid in user_ids:
        await db.add_authorized_user(uid)
        try:
            await context.bot.send_message(
                chat_id=uid, text="🎉 Ahora tienes acceso a este bot de descargas. Usa /start para empezar."
            )
        except Exception:
            pass

    ids_text = ", ".join(f"<code>{uid}</code>" for uid in user_ids)
    await update.message.reply_text(
        f"✅ Usuario(s) añadido(s): {ids_text}",
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardRemove(),
    )


@owner_only
async def users_remove(update, context):
    query = update.callback_query
    await query.answer()
    user_id = int(query.data.split(":", 2)[2])
    await db.remove_authorized_user(user_id)
    await users_menu(update, context)


@owner_only
async def source_delete_confirm(update, context):
    query = update.callback_query
    await query.answer()
    key = query.data.split(":")[2]
    if key not in torrent_search.SOURCES:
        return
    spec = torrent_search.SOURCES[key]
    note = ("Se podrá recuperar con «Restaurar de fábrica»." if not spec.get("custom")
            else "Se eliminará por completo.")
    await query.edit_message_text(
        rich(r_h("Eliminar buscador", 2, "🗑️"), r_p(f"¿Eliminar <b>{esc(spec['name'])}</b>? {note}")),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑️ Sí, eliminar", callback_data=f"src:delok:{key}"),
             InlineKeyboardButton("✖️ No", callback_data=f"src:p:{key}")],
        ]),
    )


@owner_only
async def source_delete(update, context):
    query = update.callback_query
    key = query.data.split(":")[2]
    await torrent_search.remove_source(key)
    await query.answer("Eliminado")
    text, kb = await _sources_menu_content()
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


@owner_only
async def sources_restore(update, context):
    await torrent_search.restore_defaults()
    await update.callback_query.answer("Restaurados")
    text, kb = await _sources_menu_content()
    await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


@owner_only
async def source_new_menu(update, context):
    query = update.callback_query
    await query.answer()
    context.user_data.pop("pending_src", None)
    parsers = [k for k in torrent_search.BUILTIN_KEYS]
    kb = [[InlineKeyboardButton("🧩 Torznab (Jackett / Prowlarr…)", callback_data="src:newt")]]
    row = []
    for k in parsers:
        row.append(InlineKeyboardButton(f"♊ {torrent_search.SOURCES[k]['name']}", callback_data=f"src:newc:{k}"))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton("⬅️ Buscadores", callback_data="src:menu")])
    await query.edit_message_text(
        rich(
            r_h("Añadir buscador", 2, "➕"),
            r_p("Elige el tipo:"),
            r_ul([
                "<b>Torznab</b> — cualquier indexador Torznab (Jackett, Prowlarr…): URL + API key.",
                "<b>♊ Clon de una web incluida</b> — otro dominio de una web con el mismo diseño (por ejemplo, un clon de The Pirate Bay o de 1337x).",
            ]),
        ),
        parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb),
    )


async def _ask_new_source(update, context, kind: str, parser: str = ""):
    query = update.callback_query
    await query.answer()
    context.user_data["pending_src"] = {
        "kind": kind, "parser": parser, "chat_id": query.message.chat_id, "message_id": query.message.message_id,
    }
    if kind == "torznab":
        lines = [
            "Envía <b>nombre</b>, <b>URL</b> y <b>API key</b> en un mensaje, separados por espacios:",
            "<code>MiJackett http://jackett:9117/api/v2.0/indexers/all/results/torznab/ TUAPIKEY</code>",
        ]
    else:
        lines = [
            f"Envía <b>nombre</b> y <b>URL</b> de la web clon de {esc(torrent_search.SOURCES[parser]['name'])}:",
            "<code>MiClon https://ejemplo.org</code>",
        ]
    await query.edit_message_text(
        rich(r_h("Añadir buscador", 2, "➕"), r_p(*lines), r_footer("Lo probaré antes de guardarlo.")),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✖️ Cancelar", callback_data="src:new")]]),
    )


@owner_only
async def source_new_torznab(update, context):
    await _ask_new_source(update, context, "torznab")


@owner_only
async def source_new_clone(update, context):
    await _ask_new_source(update, context, "clone", update.callback_query.data.split(":")[2])


async def _handle_new_source_text(update, context) -> bool:
    pending = context.user_data.pop("pending_src", None)
    if not pending:
        return False
    raw = (update.effective_message.text or "").strip()
    try:
        await update.effective_message.delete()
    except Exception:
        pass
    parts = raw.split()
    kind = pending["kind"]
    need = 3 if kind == "torznab" else 2
    url = torrent_search.normalize_url(parts[1], local_ok=True) if len(parts) >= 2 else None
    if len(parts) < need or not url:
        text, kb = await _sources_menu_content()
        await context.bot.edit_message_text(
            chat_id=pending["chat_id"], message_id=pending["message_id"],
            text=rich(r_quote("⚠️ Formato no válido. Usa: nombre URL" + (" API_key" if kind == "torznab" else "")), text),
            parse_mode=ParseMode.HTML, reply_markup=kb)
        return True
    name, apikey = parts[0], (parts[2] if kind == "torznab" else "")
    await context.bot.edit_message_text(chat_id=pending["chat_id"], message_id=pending["message_id"], text="🧪 Probando el buscador…")
    key = await torrent_search.add_custom(name, kind, url, apikey, pending.get("parser", ""))
    r = await torrent_search.test_source(key, only_url=url)
    if r["ok"]:
        note = r_quote(f"✅ Añadido y funcionando: <b>{r['count']}</b> resultados en {r['ms']} ms")
    else:
        note = r_quote(f"⚠️ Añadido, pero la prueba falló: {esc(r['error'] or 'sin respuesta')}. Revisa la URL o elimínalo.")
    text, kb = await _source_content(key, note=note)
    await context.bot.edit_message_text(
        chat_id=pending["chat_id"], message_id=pending["message_id"],
        text=text, parse_mode=ParseMode.HTML, reply_markup=kb)
    return True
