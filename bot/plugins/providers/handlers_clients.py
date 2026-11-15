import asyncio
import logging
import uuid
from datetime import datetime

from telegram import InlineKeyboardButton as Btn, InlineKeyboardMarkup as Markup
from telegram.constants import ParseMode

import config
import db
import filemanager
import torbox
import torrent_clients
from i18n import L
from qbittorrent import QbError
from rich_ui import esc, progress_card, r_footer, r_h, r_kv_table, r_p, r_quote, rich
from utils import owner_only

logger = logging.getLogger(__name__)


def _states() -> dict:
    import handlers_realdebrid as h_rd
    return h_rd.rd_torrent_states


async def prepare(kind: str, value, requested_by, provider: str = "qbittorrent") -> dict:
    mod = torrent_clients.module(provider)
    if kind == "torrent_file":
        info_hash, name = torbox.torrent_info(value)
    else:
        info_hash, name = torbox.magnet_infohash(value), torbox.magnet_name(value)
    if not info_hash:
        raise ValueError(L("No se pudo leer el hash del torrent.", "Could not read the torrent hash."))
    save = config.FOLDERS.get(config.default_download_folder(), "/media")
    name_label = torrent_clients.label(provider)
    async with mod.Session() as q:
        if await q.info(info_hash):
            raise ValueError(L(f"Ese torrent ya está en {name_label}.", f"That torrent is already in {name_label}."))
        if kind == "torrent_file":
            await q.add(torrent_bytes=value, savepath=save, paused=True)
        else:
            await q.add(magnet=value, savepath=save)
        files = await mod.wait_metadata(q, info_hash)
        if not files:
            await q.delete(info_hash, True)
            raise ValueError(L(f"{name_label} no obtuvo los metadatos del torrent (¿sin seeders?).",
                               f"{name_label} could not get the torrent metadata (no seeders?)."))
        await q.pause(info_hash)
        info = await q.status(info_hash) or {}
    items = [{"id": i, "path": f.get("name") or f"file{i}", "bytes": f.get("size") or 0} for i, f in enumerate(files)]
    torrent_id = uuid.uuid4().hex[:10]
    state = {
        "provider": provider,
        "token": None,
        "hash": info_hash,
        "files": items,
        "selected": {f["id"] for f in items},
        "select_files": True,
        "cached": False,
        "torrent_name": (info or {}).get("name") or name or "Torrent",
        "total": sum(f["bytes"] for f in items),
        "chat_id": requested_by,
        "message_id": None,
        "requested_by": requested_by,
        "extract_after": False,
        "last_snapshot": {"status": "waiting", "progress": 0, "speed": 0, "seeders": 0, "total": 0},
    }
    _states()[torrent_id] = state
    return state | {"torrent_id": torrent_id}


async def _edit(context, state, text, markup=None, html=False):
    chat_id, message_id = state.get("chat_id"), state.get("message_id")
    if not chat_id or not message_id:
        return
    try:
        await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup,
                                            parse_mode=ParseMode.HTML if html else None)
    except Exception:
        pass


def _fmt_eta(seconds) -> str:
    if not seconds or seconds >= 8640000:
        return "—"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m {s:02d}s"


async def run(context, torrent_id: str):
    state = _states().get(torrent_id)
    if not state:
        return
    h = state["hash"]
    provider = state["provider"]
    mod = torrent_clients.module(provider)
    pname = torrent_clients.label(provider)
    cancel_kb = Markup([[Btn(L("❌ Cancelar", "❌ Cancel"), callback_data=f"rdcancel:{torrent_id}")]])
    try:
        sched = state.get("schedule")
        if sched and sched != "now":
            import handlers_torbox
            when = handlers_torbox.schedule_fields(sched).get("scheduled_for")
            if when:
                delay = (datetime.fromisoformat(when) - datetime.now(datetime.fromisoformat(when).tzinfo)).total_seconds()
                await _edit(context, state, L(f"⏰ Programado para {when[:16].replace('T', ' ')}", f"⏰ Scheduled for {when[:16].replace('T', ' ')}"), cancel_kb)
                await asyncio.sleep(max(0, delay))

        cfg = await mod.get_config()
        async with mod.Session(cfg) as q:
            ids = [f["id"] for f in state["files"]]
            chosen = [i for i in ids if i in state["selected"]]
            import disk
            need = sum(f.get("bytes") or 0 for f in state["files"] if f["id"] in state["selected"])
            fit = await disk.check_fit(state["dest_path"], need)
            if not fit["ok"] and fit["guard"] in ("reject", "pause"):
                raise QbError(disk.no_space_text(state.get("torrent_name", ""), fit))
            await q.set_priority(h, [i for i in ids if i not in state["selected"]], 0)
            await q.set_priority(h, chosen, 1)
            await q.set_location(h, state["dest_path"])
            await q.resume(h)

            last = None
            while True:
                info = await q.status(h)
                if info is None:
                    raise QbError(L(f"El torrent desapareció de {pname}.", f"The torrent disappeared from {pname}."))
                progress = info["progress"] * 100
                speed = info["dlspeed"]
                total = info["size"] or state.get("total") or 0
                state["torrent_name"] = info["name"] or state["torrent_name"]
                state["last_snapshot"] = {
                    "status": "done" if info["done"] else "downloading", "progress": progress, "speed": speed,
                    "seeders": info["seeds"], "total": total,
                }
                if info["error"]:
                    raise QbError(L(f"{pname} informó de un error ({info['error']}).", f"{pname} reported an error ({info['error']})."))
                if progress >= 99.999 or info["done"]:
                    break
                text = progress_card(
                    L(f"Descargando con {pname}", f"Downloading with {pname}"), "⬇️", state["torrent_name"],
                    progress, total, speed, _fmt_eta(info["eta"]), [("🌱 Seeders", str(info["seeds"]))],
                )
                if text != last:
                    await _edit(context, state, text, cancel_kb, html=True)
                    last = text
                await asyncio.sleep(5)

            if not cfg["keep_seeding"]:
                await q.delete(h, False)

        filemanager.invalidate_dir_size_cache(state["dest_folder"].split("/")[0], "")
        await db.create_task(
            kind="link", filename=state["torrent_name"], dest_folder=state["dest_folder"],
            dest_path=state["dest_path"], status="done", client=provider,
            total_size=state["last_snapshot"].get("total"), requested_by=state.get("requested_by"),
            finished_at=datetime.now().isoformat(),
        )
        _states().pop(torrent_id, None)
        await _edit(context, state, L(f"✅ Descarga completada con {pname}.\n📁 {state['dest_folder']}",
                                      f"✅ Download completed with {pname}.\n📁 {state['dest_folder']}"))
    except asyncio.CancelledError:
        return
    except QbError as e:
        await _edit(context, state, f"❌ {pname}: {e}")
        _states().pop(torrent_id, None)
    except Exception as e:
        logger.exception("qBittorrent flow failed")
        await _edit(context, state, f"❌ {e}")
        _states().pop(torrent_id, None)


async def cancel(state: dict):
    task = state.get("monitor_task")
    if task:
        task.cancel()
    try:
        async with torrent_clients.module(state["provider"]).Session() as q:
            await q.delete(state["hash"], True)
    except Exception as e:
        logger.warning("Could not remove the torrent from the client: %s", e)


async def menu_content(key: str, note: str | None = None) -> tuple[str, Markup]:
    spec = torrent_clients.CLIENTS[key]
    mod, pre, name = spec["module"], spec["prefix"], spec["label"]
    cfg = await mod.get_config()
    enabled = await mod.is_enabled()
    rows = [
        (L("Estado", "Status"), L("🟢 Activado", "🟢 Enabled") if enabled else L("⚪ Desactivado", "⚪ Disabled")),
        ("URL", f"<code>{esc(cfg['url'])}</code>"),
    ]
    if mod.NEEDS_USER:
        rows.append((L("Usuario", "User"), esc(cfg["user"]) or "—"))
    rows.append((L("Contraseña", "Password"), "••••••••" if cfg["password"] else L("⚠️ Sin configurar", "⚠️ Not set")))
    rows.append((L("Seguir sembrando", "Keep seeding"), L("Sí", "Yes") if cfg["keep_seeding"] else "No"))
    blocks = [
        r_h(name, 2, spec["icon"]),
        r_p(L("Cliente BitTorrent local: descarga directo al NAS con tu conexión, sin servicios debrid.",
              "Local BitTorrent client: downloads straight to the NAS over your own connection, no debrid service.")),
        r_kv_table(rows),
    ]
    if note:
        blocks.append(r_quote(note))
    blocks.append(r_footer(L(f"{name} debe ver las mismas carpetas con las mismas rutas /media/...",
                             f"{name} must see the same folders at the same /media/... paths")))
    action_row = [Btn("🔗 URL", callback_data=f"cl:{key}:url")]
    if mod.NEEDS_USER:
        action_row.append(Btn("👤 " + L("Usuario", "User"), callback_data=f"cl:{key}:user"))
    action_row.append(Btn("🔑 " + L("Contraseña", "Password"), callback_data=f"cl:{key}:pass"))
    kb = Markup([
        [Btn(L("🔴 Desactivar", "🔴 Disable") if enabled else L("🟢 Activar", "🟢 Enable"), callback_data=f"cl:{key}:toggle"),
         Btn(L("🧪 Probar", "🧪 Test"), callback_data=f"cl:{key}:test")],
        action_row,
        [Btn(L("🌱 Seguir sembrando: ", "🌱 Keep seeding: ") + (L("sí", "yes") if cfg["keep_seeding"] else "no"), callback_data=f"cl:{key}:seed")],
        [Btn("📖 " + L("Tutorial", "Guide"), callback_data=f"guide:{spec['tutorial']}:cl:{key}:menu")],
        [Btn(L("⬅️ Proveedores", "⬅️ Providers"), callback_data="prov:menu")],
    ])
    return rich(*blocks), kb


async def _show(update, key, note=None):
    import handlers_setup as hs
    text, kb = await menu_content(key, note)
    await hs.show(update, text, kb)


@owner_only
async def client_action(update, context):
    query = update.callback_query
    _, key, action = query.data.split(":", 2)
    if key not in torrent_clients.CLIENTS:
        await query.answer()
        return
    spec = torrent_clients.CLIENTS[key]
    mod, pre = spec["module"], spec["prefix"]
    if action == "menu":
        await query.answer()
        context.user_data.pop("pending_setup", None)
        await _show(update, key)
    elif action == "toggle":
        await db.set_setting(f"{pre}_enabled", "0" if await mod.is_enabled() else "1")
        await query.answer()
        await _show(update, key)
    elif action == "seed":
        cfg = await mod.get_config()
        await db.set_setting(f"{pre}_keep_seeding", "0" if cfg["keep_seeding"] else "1")
        await query.answer()
        await _show(update, key)
    elif action == "test":
        await query.answer(L("Probando…", "Testing…"))
        try:
            version = await mod.test_connection()
            note = L(f"✅ Conectado · {spec['label']} {esc(version)}", f"✅ Connected · {spec['label']} {esc(version)}")
        except QbError as e:
            note = f"❌ {esc(e)}"
        await _show(update, key, note)
    elif action in ("url", "user", "pass"):
        await query.answer()
        import handlers_setup as hs
        context.user_data["pending_setup"] = {
            "kind": f"cl_{action}", "client": key, "chat_id": query.message.chat_id,
            "message_id": query.message.message_id, "back": f"cl:{key}:menu",
        }
        hints = {
            "url": L(f"Envía la URL de la Web UI, por ejemplo <code>{mod.DEFAULT_URL}</code>.",
                     f"Send the Web UI URL, for example <code>{mod.DEFAULT_URL}</code>."),
            "user": L("Envía el usuario de la Web UI.", "Send the Web UI username."),
            "pass": L("Envía la contraseña de la Web UI (el mensaje se borra al instante).",
                      "Send the Web UI password (the message is deleted immediately)."),
        }
        title = {"url": "URL", "user": L("Usuario", "Username"), "pass": L("Contraseña", "Password")}[action]
        text, kb = hs._prompt_content(f"{spec['label']} · {title}", [hints[action]], f"cl:{key}:menu", spec["tutorial"])
        await hs.show(update, text, kb)


async def handle_pending(update, context, pending, raw, finish, retry) -> bool:
    kind = pending["kind"]
    if kind not in ("cl_url", "cl_user", "cl_pass"):
        return False
    key = pending["client"]
    pre = torrent_clients.CLIENTS[key]["prefix"]
    if kind == "cl_url":
        if not raw.startswith(("http://", "https://")):
            await retry(L("La URL debe empezar por http:// o https://", "The URL must start with http:// or https://"))
            return True
        await db.set_setting(f"{pre}_url", raw.rstrip("/"))
    elif kind == "cl_user":
        await db.set_setting(f"{pre}_user", raw)
    else:
        await db.set_setting(f"{pre}_pass", raw)
    text, kb = await menu_content(key, L("✅ Guardado.", "✅ Saved."))
    await finish(update, context, pending, text, kb)
    return True
