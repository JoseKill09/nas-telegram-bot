import logging
import uuid

from telegram import InlineKeyboardButton as Btn, InlineKeyboardMarkup as Markup
from telegram.constants import ParseMode

import torbox
from i18n import L
from rich_ui import esc, r_footer, r_h, r_kv_table, r_p, r_quote, r_table, rich
from utils import owner_only

logger = logging.getLogger(__name__)

PAGE = 8


async def _token() -> str | None:
    import handlers_settings as hs
    return await hs.get_tb_token() if await hs.tb_is_enabled() else None


def _status(t: dict) -> str:
    if t.get("download_finished") or t.get("download_present"):
        return L("✅ Listo", "✅ Ready")
    state = (t.get("download_state") or "").lower()
    if state in ("error", "failed", "expired", "missingfiles"):
        return "❌ " + state
    if t.get("active"):
        return f"⬇️ {float(t.get('progress') or 0) * 100:.0f}%"
    return "⏸ " + (state or L("en espera", "waiting"))


def _cut(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


async def _show(update, text, kb):
    query = update.callback_query
    if query:
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def list_content(token: str, page: int = 0, note: str | None = None) -> tuple[str, Markup]:
    items = await torbox.list_torrents(token)
    items.sort(key=lambda t: t.get("created_at") or "", reverse=True)
    total = len(items)
    pages = max(1, -(-total // PAGE))
    page = max(0, min(page, pages - 1))
    chunk = items[page * PAGE:(page + 1) * PAGE]
    rows, kb, row = [], [], []
    for n, t in enumerate(chunk, start=page * PAGE + 1):
        rows.append([
            f"<b>{n}</b>", esc(_cut(t.get("name") or "?", 52)), esc(torbox.human_size(t.get("size"))),
            _status(t), f"{t.get('seeds') or 0}/{t.get('peers') or 0}", esc(str(t.get("created_at") or "")[:10]),
        ])
        row.append(Btn(str(n), callback_data=f"tbl:o:{t['id']}"))
        if len(row) == 4:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    blocks = [r_h(L("Mi TorBox", "My TorBox"), 2, "📦")]
    if note:
        blocks.append(r_quote(note))
    if rows:
        blocks.append(r_table(rows, header=["#", L("Nombre", "Name"), L("Tamaño", "Size"), L("Estado", "Status"), "🌱/👥", L("Fecha", "Date")],
                              caption=L(f"{total} torrents · página {page + 1}/{pages}", f"{total} torrents · page {page + 1}/{pages}")))
    else:
        blocks.append(r_p(L("No tienes torrents en TorBox.", "You have no torrents in TorBox.")))
    blocks.append(r_footer(L("Toca un número para ver el detalle, enviarlo al NAS o borrarlo.", "Tap a number for details, to send it to the NAS or delete it.")))
    nav = []
    if page > 0:
        nav.append(Btn("◀", callback_data=f"tbl:p:{page - 1}"))
    nav.append(Btn("🔄", callback_data=f"tbl:p:{page}"))
    if page + 1 < pages:
        nav.append(Btn("▶", callback_data=f"tbl:p:{page + 1}"))
    kb.append(nav)
    if total:
        kb.append([Btn(L("🗑️ Borrar todo", "🗑️ Delete all"), callback_data="tbl:delall")])
    kb.append([Btn(L("⬅️ Menú", "⬅️ Menu"), callback_data="menu:main")])
    return rich(*blocks), Markup(kb)


NO_TOKEN = ("TorBox no está activado. Ve a Ajustes → Proveedores de descarga → TorBox.")


@owner_only
async def torbox_command(update, context):
    token = await _token()
    if not token:
        await update.effective_message.reply_text(L(NO_TOKEN, "TorBox is not enabled. Go to Settings → Download providers → TorBox."))
        return
    try:
        text, kb = await list_content(token)
    except torbox.TorBoxError as e:
        await update.effective_message.reply_text(f"❌ TorBox: {e}")
        return
    await _show(update, text, kb)


@owner_only
async def tbl_page(update, context):
    query = update.callback_query
    await query.answer()
    token = await _token()
    if not token:
        await query.edit_message_text(L(NO_TOKEN, "TorBox is not enabled."))
        return
    try:
        text, kb = await list_content(token, int(query.data.split(":")[2]))
    except torbox.TorBoxError as e:
        await query.edit_message_text(f"❌ TorBox: {e}")
        return
    await _show(update, text, kb)


async def _find(token: str, tid: int) -> dict | None:
    return await torbox.get_torrent(token, tid)


@owner_only
async def tbl_open(update, context):
    query = update.callback_query
    await query.answer()
    token = await _token()
    tid = int(query.data.split(":")[2])
    try:
        t = await _find(token, tid)
    except torbox.TorBoxError as e:
        await query.edit_message_text(f"❌ TorBox: {e}")
        return
    if not t:
        text, kb = await list_content(token)
        await _show(update, text, kb)
        return
    files = t.get("files") or []
    ready = bool(t.get("download_finished") or t.get("download_present"))
    pairs = [
        (L("Nombre", "Name"), esc(t.get("name") or "?")),
        (L("Estado", "Status"), _status(t)),
        (L("Tamaño", "Size"), esc(torbox.human_size(t.get("size")))),
        (L("Archivos", "Files"), str(len(files))),
        ("🌱 / 👥", f"{t.get('seeds') or 0} / {t.get('peers') or 0}"),
        (L("Velocidad", "Speed"), f"{(t.get('download_speed') or 0) / (1024 * 1024):.2f} MB/s"),
        (L("Añadido", "Added"), esc(str(t.get("created_at") or "")[:16].replace("T", " "))),
        (L("Caduca", "Expires"), esc(str(t.get("expires_at") or "—")[:16].replace("T", " "))),
        ("Hash", f"<code>{esc(t.get('hash') or '')}</code>"),
    ]
    kb = []
    if ready:
        kb.append([Btn(L("📥 Enviar al NAS", "📥 Send to NAS"), callback_data=f"tbl:send:{tid}")])
    kb.append([Btn(L("🗑️ Borrar de TorBox", "🗑️ Delete from TorBox"), callback_data=f"tbl:del:{tid}")])
    kb.append([Btn(L("⬅️ Lista", "⬅️ List"), callback_data="tbl:p:0")])
    await _show(update, rich(r_h(L("Torrent de TorBox", "TorBox torrent"), 2, "📦"), r_kv_table(pairs)), Markup(kb))


@owner_only
async def tbl_send(update, context):
    query = update.callback_query
    await query.answer()
    token = await _token()
    tid = int(query.data.split(":")[2])
    try:
        t = await _find(token, tid)
    except torbox.TorBoxError as e:
        await query.edit_message_text(f"❌ TorBox: {e}")
        return
    if not t or not t.get("files"):
        await query.edit_message_text(L("⚠️ No hay archivos disponibles en ese torrent.", "⚠️ No files available in that torrent."))
        return
    import handlers_torbox
    files = [{"id": f["id"], "path": f.get("name") or f.get("short_name") or f"file{f['id']}", "bytes": f.get("size") or 0}
             for f in t["files"]]
    torrent_id = uuid.uuid4().hex[:10]
    handlers_torbox._states()[torrent_id] = {
        "provider": "torbox", "token": token, "source": None, "hash": t.get("hash"), "cached": True,
        "files": files, "selected": {f["id"] for f in files}, "select_files": True,
        "torrent_name": t.get("name") or "Torrent", "total": t.get("size") or 0, "tb_id": tid, "keep_remote": True,
        "chat_id": query.message.chat_id, "message_id": query.message.message_id,
        "requested_by": query.from_user.id, "extract_after": False,
        "last_snapshot": {"status": "ready", "progress": 100, "speed": 0, "seeders": 0, "total": 0},
    }
    await handlers_torbox.present(query.message, torrent_id)


@owner_only
async def tbl_delete_confirm(update, context):
    query = update.callback_query
    await query.answer()
    tid = query.data.split(":")[2]
    await _show(update, rich(r_h(L("Borrar torrent", "Delete torrent"), 2, "🗑️"),
                             r_p(L("¿Borrar este torrent de tu cuenta de TorBox? Los archivos ya descargados en el NAS no se tocan.",
                                   "Delete this torrent from your TorBox account? Files already downloaded to the NAS are not touched."))),
                Markup([[Btn(L("🗑️ Sí, borrar", "🗑️ Yes, delete"), callback_data=f"tbl:delok:{tid}"),
                         Btn(L("✖️ No", "✖️ No"), callback_data=f"tbl:o:{tid}")]]))


@owner_only
async def tbl_delete(update, context):
    query = update.callback_query
    await query.answer()
    token = await _token()
    try:
        await torbox.delete_torrent(token, int(query.data.split(":")[2]))
        text, kb = await list_content(token, 0, L("✅ Borrado.", "✅ Deleted."))
    except torbox.TorBoxError as e:
        text, kb = f"❌ TorBox: {e}", None
    await _show(update, text, kb)


@owner_only
async def tbl_delete_all_confirm(update, context):
    query = update.callback_query
    await query.answer()
    await _show(update, rich(r_h(L("Borrar todo", "Delete all"), 2, "🗑️"),
                             r_p(L("¿Borrar <b>todos</b> los torrents de tu cuenta de TorBox? No se puede deshacer.",
                                   "Delete <b>all</b> torrents from your TorBox account? This cannot be undone."))),
                Markup([[Btn(L("🗑️ Sí, borrar todo", "🗑️ Yes, delete all"), callback_data="tbl:delallok"),
                         Btn(L("✖️ No", "✖️ No"), callback_data="tbl:p:0")]]))


@owner_only
async def tbl_delete_all(update, context):
    query = update.callback_query
    await query.answer()
    token = await _token()
    failed = 0
    try:
        for t in await torbox.list_torrents(token):
            try:
                await torbox.delete_torrent(token, t["id"])
            except torbox.TorBoxError:
                failed += 1
        text, kb = await list_content(token, 0, L("✅ Borrados.", "✅ Deleted.") + (f" ({failed} ✗)" if failed else ""))
    except torbox.TorBoxError as e:
        text, kb = f"❌ TorBox: {e}", None
    await _show(update, text, kb)
