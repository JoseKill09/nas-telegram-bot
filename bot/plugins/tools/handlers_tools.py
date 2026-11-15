import io
import logging
import os
import re
from datetime import datetime

from telegram import InlineKeyboardButton as Btn, InlineKeyboardMarkup as Markup
from telegram.error import BadRequest

import backup
import config
import db
import disk
import notifier
import rules
from i18n import L
from rich_ui import esc, r_footer, r_h, r_kv_table, r_p, r_quote, r_table, r_ul, rich
from utils import authorized_only, owner_only

logger = logging.getLogger(__name__)


def _on(flag) -> str:
    return L("🟢 Sí", "🟢 Yes") if flag else L("⚪ No", "⚪ No")


def _back(cb="settings:menu", label=None):
    return [Btn(label or L("⬅️ Ajustes", "⬅️ Settings"), callback_data=cb)]


async def _show(update, text, kb):
    import handlers_setup as hs
    await hs.show(update, text, kb)


async def _prompt(update, context, kind, title, lines, back_cb, extra=None):
    import handlers_setup as hs
    query = update.callback_query
    await query.answer()
    context.user_data["pending_setup"] = {
        "kind": kind, "chat_id": query.message.chat_id, "message_id": query.message.message_id,
        "back": back_cb, **(extra or {}),
    }
    text, kb = hs._prompt_content(title, lines, back_cb)
    await hs.show(update, text, kb)


def _num(raw, minimum=0.0):
    try:
        return max(minimum, float(raw.replace(",", ".")))
    except ValueError:
        return None


# ───────────────────────── Backup ─────────────────────────

def _sel(context) -> list:
    return context.user_data.setdefault("bk_sel", list(backup.PRESETS["standard"]))


def _short_names() -> dict:
    return {
        "settings": L("Ajustes", "Settings"), "folders": L("Carpetas", "Folders"), "sources": L("Buscadores", "Sources"),
        "rules": L("Reglas", "Rules"), "users": L("Usuarios", "Users"), "history": L("Historial", "History"),
        "channel": L("Canal", "Channel"), "tokens": L("Tokens", "Tokens"), "userbot": "Userbot",
    }


def _bar(n: int, total: int) -> str:
    return "▰" * n + "▱" * (total - n)


async def backup_content(context, note: str = ""):
    meta = backup.info()
    short = _short_names()
    sel = _sel(context)
    pw = bool(context.user_data.get("bk_pw"))
    auto = await db.get_setting("bk_auto", "off")
    total = len(backup.GROUP_ORDER)
    preset = next((k for k, v in backup.PRESETS.items() if set(v) == set(sel)), None)
    preset_name = {"light": L("Mínima", "Minimal"), "standard": L("Estándar", "Standard"), "full": L("Completa", "Full")}.get(preset, L("Personalizada", "Custom"))
    sensitive = [g for g in ("tokens", "userbot") if g in sel]

    parts = [
        r_h(L("Copia de seguridad", "Backup"), 2, "💾"),
        r_p(L("Un archivo cifrado con lo que elijas, para guardarlo o llevarlo a otro bot. Te llega por este chat.",
              "An encrypted file with whatever you choose, to keep or move to another bot. It arrives in this chat.")),
    ]
    if note:
        parts.append(r_quote(note))
    parts.append(r_p(f"<b>{preset_name}</b> · {len(sel)}/{total} {L('grupos', 'groups')}  <code>{_bar(len(sel), total)}</code>"))
    parts.append(r_table(
        [[f"{'✅' if g in sel else '⬜'} {meta[g][0]} <b>{esc(meta[g][1])}</b>", esc(meta[g][2])] for g in backup.GROUP_ORDER],
        [L("Qué incluir", "What to include"), L("Contenido", "Contents")]))
    parts.append(r_kv_table([
        ("🔒 " + L("Cifrado", "Encryption"),
         L("Contraseña propia", "Custom password") if pw else L("Clave automática", "Automatic key")),
        ("⏰ " + L("Automática", "Automatic"), {"off": L("Desactivada", "Off"), "daily": L("Cada día", "Daily"),
                                              "weekly": L("Cada semana", "Weekly")}[auto]),
    ]))
    if sensitive:
        parts.append(r_quote(L("⚠️ Esta copia incluye datos muy sensibles (tokens o sesión). Guárdala y su clave por separado.",
                               "⚠️ This backup includes highly sensitive data (tokens or session). Keep it and its key apart.")))
    else:
        parts.append(r_footer(L("Para restaurarla en otra instalación necesitarás la clave: guárdala con 🔑.",
                                "To restore it on another installation you will need the key: save it with 🔑.")))

    def mark(k: str, label: str) -> str:
        return ("● " if preset == k else "") + label

    kb = [[Btn(mark("light", L("Mínima", "Minimal")), callback_data="bk:preset:light"),
           Btn(mark("standard", L("Estándar", "Standard")), callback_data="bk:preset:standard"),
           Btn(mark("full", L("Todo", "All")), callback_data="bk:preset:full")]]
    row = []
    for g in backup.GROUP_ORDER:
        row.append(Btn(f"{'✅' if g in sel else '⬜'} {meta[g][0]} {short[g]}", callback_data=f"bk:tg:{g}"))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([Btn("📤 " + L("Crear copia ahora", "Create backup now"), callback_data="bk:make")])
    kb.append([Btn("📥 " + L("Restaurar", "Restore"), callback_data="bk:restore"),
               Btn("🔑 " + L("Ver clave", "Show key"), callback_data="bk:key")])
    kb.append([Btn("🔒 " + (L("Clave automática", "Automatic key") if pw else L("Contraseña propia", "Custom password")), callback_data="bk:pw"),
               Btn("⏰ " + L("Automática", "Automatic"), callback_data="bk:auto")])
    kb.append([Btn(L("📖 Tutorial", "📖 Guide"), callback_data="guide:backup:bk:menu"), *_back()])
    return rich(*parts), Markup(kb)


@owner_only
async def backup_command(update, context):
    text, kb = await backup_content(context)
    await update.effective_message.reply_text(text, parse_mode="HTML", reply_markup=kb)


@owner_only
async def backup_action(update, context):
    query = update.callback_query
    parts = query.data.split(":")
    action = parts[1]
    sel = _sel(context)
    if action == "menu":
        await query.answer()
        context.user_data.pop("pending_setup", None)
        context.user_data.pop("pending_restore", None)
    elif action == "preset":
        await query.answer()
        context.user_data["bk_sel"] = list(backup.PRESETS[parts[2]])
    elif action == "tg":
        await query.answer()
        g = parts[2]
        if g in sel:
            sel.remove(g)
        else:
            sel.append(g)
    elif action == "pw":
        if context.user_data.get("bk_pw"):
            context.user_data.pop("bk_pw")
            await query.answer(L("Contraseña quitada", "Password removed"))
        else:
            await _prompt(update, context, "bk_pw", L("Contraseña de la copia", "Backup password"),
                          [L("Envía la contraseña (el mensaje se borra). Sin ella no se podrá restaurar: no hay forma de recuperarla.",
                             "Send the password (the message is deleted). Without it the backup cannot be restored: it cannot be recovered.")],
                          "bk:menu")
            return
    elif action == "key":
        key = await backup.get_key()
        await query.answer()
        await context.bot.send_message(
            chat_id=query.message.chat_id, parse_mode="HTML",
            text=L(f"🔑 <b>Clave de cifrado de tus copias</b>\n<code>{esc(key)}</code>\n\nGuárdala en un gestor de contraseñas y borra este mensaje. "
                   "Sin ella (o sin tu contraseña propia) no se puede restaurar una copia en otra instalación.",
                   f"🔑 <b>Your backups' encryption key</b>\n<code>{esc(key)}</code>\n\nStore it in a password manager and delete this message. "
                   "Without it (or your custom password) a backup cannot be restored on another installation."))
        return
    elif action == "auto":
        await query.answer()
        cur = await db.get_setting("bk_auto", "off")
        nxt = {"off": "daily", "daily": "weekly", "weekly": "off"}[cur]
        await db.set_setting("bk_auto", nxt)
        await db.set_setting("bk_auto_groups", ",".join(sel))
    elif action == "make":
        if not sel:
            await query.answer(L("Selecciona al menos un grupo", "Select at least one group"), show_alert=True)
            return
        await query.answer(L("Creando…", "Creating…"))
        pw = context.user_data.get("bk_pw")
        first_key = None if pw or await db.get_setting("bk_key") else True
        blob, name = await backup.build(sel, pw)
        await context.bot.send_document(chat_id=query.message.chat_id, document=io.BytesIO(blob), filename=name,
                                        caption=L("💾 Copia cifrada lista. Reenvíala a tus mensajes guardados para conservarla.",
                                                  "💾 Encrypted backup ready. Forward it to your saved messages to keep it."))
        if first_key:
            key = await backup.get_key()
            await context.bot.send_message(
                chat_id=query.message.chat_id, parse_mode="HTML",
                text=L(f"🔑 <b>Clave de cifrado generada</b>\n<code>{esc(key)}</code>\n\nGuárdala ahora en un gestor de contraseñas: la necesitarás para restaurar en otra instalación. Puedes verla de nuevo con 🔑.",
                       f"🔑 <b>Encryption key generated</b>\n<code>{esc(key)}</code>\n\nSave it now in a password manager: you will need it to restore on another installation. You can show it again with 🔑."))
        text, kb = await backup_content(context, L(f"✅ Copia creada: {esc(name)}", f"✅ Backup created: {esc(name)}"))
        await _show(update, text, kb)
        return
    elif action == "restore":
        await query.answer()
        context.user_data["pending_restore"] = {"chat_id": query.message.chat_id, "message_id": query.message.message_id}
        text = rich(r_h(L("Restaurar copia", "Restore backup"), 2, "📥"),
                    r_p(L("Envía aquí el archivo de copia (.nasbak). Antes de restaurar se guarda una copia de seguridad automática de lo actual.",
                          "Send the backup file here (.nasbak). A safety backup of the current data is saved before restoring.")))
        await _show(update, text, Markup([_back("bk:menu", L("✖️ Cancelar", "✖️ Cancel"))]))
        return
    text, kb = await backup_content(context)
    await _show(update, text, kb)


async def handle_restore_document(update, context) -> bool:
    pending = context.user_data.get("pending_restore")
    if not pending or update.effective_user.id != config.OWNER_ID:
        return False
    doc = update.effective_message.document
    if not doc:
        return False
    context.user_data.pop("pending_restore", None)
    if (doc.file_size or 0) > 20 * 1024 * 1024:
        await update.effective_message.reply_text(L("⚠️ El archivo supera 20 MB (límite de descarga de bots).", "⚠️ The file is over 20 MB (bot download limit)."))
        return True
    tg_file = await doc.get_file()
    blob = bytes(await tg_file.download_as_bytearray())
    try:
        await update.effective_message.delete()
    except Exception:
        pass
    context.user_data["bk_blob"] = blob
    if backup.is_encrypted(blob):
        stored = await backup.get_key(create=False)
        if stored:
            try:
                backup.read(blob, stored)
                return await _open_restore(context, pending, stored)
            except backup.BackupError:
                pass
        context.user_data["pending_setup"] = {"kind": "bk_restore_pw", **pending, "back": "bk:menu"}
        await context.bot.send_message(chat_id=pending["chat_id"],
                                       text=L("🔒 La copia está cifrada. Envía la contraseña.", "🔒 The backup is encrypted. Send the password."))
        return True
    return await _open_restore(context, pending, None)


async def _open_restore(context, pending, password) -> bool:
    try:
        manifest, data = backup.read(context.user_data["bk_blob"], password)
    except backup.BackupError as e:
        await context.bot.send_message(chat_id=pending["chat_id"], text=f"⚠️ {e}")
        return True
    context.user_data["bk_data"] = (manifest, data)
    context.user_data["bk_rsel"] = [g for g in manifest["groups"] if g not in ("tokens", "userbot")] or list(manifest["groups"])
    text, kb = restore_content(context)
    await context.bot.send_message(chat_id=pending["chat_id"], text=text, parse_mode="HTML", reply_markup=kb)
    return True


def restore_content(context):
    manifest, _data = context.user_data["bk_data"]
    meta = backup.info()
    sel = context.user_data["bk_rsel"]
    rows = [[("✅" if g in sel else "⬜") + f" {meta[g][0]} {meta[g][1]}", str(manifest["counts"].get(g, 0))]
            for g in backup.GROUP_ORDER if g in manifest["groups"]]
    text = rich(
        r_h(L("Restaurar copia", "Restore backup"), 2, "📥"),
        r_kv_table([(L("Creada", "Created"), esc(manifest.get("created", "?"))), (L("Versión", "Version"), esc(manifest.get("app_version", "?")))]),
        r_table(rows, [L("Grupo", "Group"), L("Elementos", "Items")]),
        r_footer(L("Restaurar reemplaza lo actual de cada grupo marcado. Tokens, sesión del Userbot y usuarios requieren reiniciar el contenedor.",
                   "Restoring replaces the current content of each selected group. Tokens, the Userbot session and users need a container restart.")),
    )
    kb, row = [], []
    for g in backup.GROUP_ORDER:
        if g in manifest["groups"]:
            row.append(Btn(f"{'✅' if g in sel else '⬜'} {meta[g][0]} {meta[g][1]}", callback_data=f"bk:rt:{g}"))
            if len(row) == 2:
                kb.append(row)
                row = []
    if row:
        kb.append(row)
    kb.append([Btn(L("✅ Restaurar lo marcado", "✅ Restore selected"), callback_data="bk:rgo")])
    kb.append(_back("bk:menu", L("✖️ Cancelar", "✖️ Cancel")))
    return text, Markup(kb)


@owner_only
async def restore_action(update, context):
    query = update.callback_query
    if "bk_data" not in context.user_data:
        await query.answer(L("Sesión expirada. Vuelve a enviar el archivo.", "Session expired. Send the file again."), show_alert=True)
        return
    parts = query.data.split(":")
    sel = context.user_data["bk_rsel"]
    if parts[1] == "rt":
        await query.answer()
        g = parts[2]
        sel.remove(g) if g in sel else sel.append(g)
        text, kb = restore_content(context)
        await _show(update, text, kb)
        return
    if not sel:
        await query.answer(L("Marca al menos un grupo", "Select at least one group"), show_alert=True)
        return
    await query.answer(L("Restaurando…", "Restoring…"))
    manifest, data = context.user_data.pop("bk_data")
    context.user_data.pop("bk_blob", None)
    safety, name = await backup.build(list(backup.GROUP_ORDER))
    folder = os.path.join(config.CONFIG_DIR, "backups")
    os.makedirs(folder, exist_ok=True)
    safe_path = os.path.join(folder, name.replace("nas-bot-backup", "before-restore"))
    with open(safe_path, "wb") as f:
        f.write(safety)
    done = await backup.restore(manifest, data, sel)
    import rich_bot
    rich_bot.set_enabled(await db.get_setting("rich_enabled", "1") != "0")
    meta = backup.info()
    text = rich(
        r_h(L("Restauración completada", "Restore completed"), 2, "✅"),
        r_ul([f"{meta[g][0]} {meta[g][1]}: {n}" for g, n in done.items()]),
        r_footer(L(f"Copia previa guardada en {safe_path}. Reinicia el contenedor para aplicar todo (docker compose restart bot).",
                   f"Previous data saved at {safe_path}. Restart the container to apply everything (docker compose restart bot).")),
    )
    await _show(update, text, Markup([_back("bk:menu", L("⬅️ Copia de seguridad", "⬅️ Backup"))]))


async def auto_backup_job(context):
    mode = await db.get_setting("bk_auto", "off")
    if mode == "off":
        return
    last = await db.get_setting("bk_last")
    gap = 86400 if mode == "daily" else 7 * 86400
    if last:
        try:
            if (datetime.now() - datetime.fromisoformat(last)).total_seconds() < gap:
                return
        except ValueError:
            pass
    groups = [g for g in (await db.get_setting("bk_auto_groups", "")).split(",") if g in backup.GROUP_ORDER] \
        or list(backup.PRESETS["standard"])
    is_new_key = not await db.get_setting("bk_key")
    blob, name = await backup.build(groups)
    await db.set_setting("bk_last", datetime.now().isoformat(timespec="seconds"))
    try:
        await context.bot.send_document(chat_id=config.OWNER_ID, document=io.BytesIO(blob), filename=name,
                                        caption=L("💾 Copia automática (cifrada)", "💾 Automatic backup (encrypted)"), disable_notification=True)
        if is_new_key:
            key = await backup.get_key()
            await context.bot.send_message(
                chat_id=config.OWNER_ID, parse_mode="HTML",
                text=L(f"🔑 <b>Clave de cifrado de tus copias</b>\n<code>{esc(key)}</code>\nGuárdala en un gestor de contraseñas.",
                       f"🔑 <b>Your backups' encryption key</b>\n<code>{esc(key)}</code>\nStore it in a password manager."))
    except Exception:
        logger.exception("auto backup")


# ───────────────────────── Notifications ─────────────────────────

async def notif_content(note: str = ""):
    c = await notifier.get()
    to_label = {"requester": L("Quien lo pidió", "Who requested it"), "owner": L("Solo el propietario", "Owner only"),
                "both": L("Ambos", "Both")}[c["to"]]
    quiet = f"{c['quiet_from']:02d}:00 → {c['quiet_to']:02d}:00" if c["quiet_on"] else L("⚪ Desactivado", "⚪ Off")
    parts = [r_h(L("Notificaciones", "Notifications"), 2, "🔔"),
             r_p(L("Avisos con un mensaje nuevo (suena en el móvil) cuando termina o falla una descarga.",
                   "Alerts as a new message (your phone rings) when a download finishes or fails."))]
    if note:
        parts.append(r_p(note))
    parts.append(r_kv_table([
        (L("🔔 Notificaciones", "🔔 Notifications"), _on(c["enabled"])),
        (L("✅ Descarga terminada", "✅ Download finished"), _on(c["done"])),
        (L("❌ Descarga fallida", "❌ Download failed"), _on(c["failed"])),
        (L("💾 Aviso de poco espacio", "💾 Low-space alert"), _on(c["disk"])),
        (L("📏 Tamaño mínimo para avisar", "📏 Minimum size to notify"), f"{c['min_mb']} MB" if c["min_mb"] else L("Sin mínimo", "No minimum")),
        (L("👤 Avisar a", "👤 Notify"), to_label),
        (L("🌙 Horas silenciosas (sin sonido)", "🌙 Quiet hours (no sound)"), quiet),
    ]))
    kb = [
        [Btn(L("🔔 General", "🔔 Master"), callback_data="nt:tg:enabled"),
         Btn(L("✅ Terminadas", "✅ Finished"), callback_data="nt:tg:done"),
         Btn(L("❌ Fallidas", "❌ Failed"), callback_data="nt:tg:failed")],
        [Btn(L("💾 Poco espacio", "💾 Low space"), callback_data="nt:tg:disk"),
         Btn(L("👤 Destinatario", "👤 Recipient"), callback_data="nt:to")],
        [Btn(L("📏 Tamaño mínimo", "📏 Min size"), callback_data="nt:min"),
         Btn(L("🌙 Silencio", "🌙 Quiet hours"), callback_data="nt:quiet")],
        _back(),
    ]
    return rich(*parts), Markup(kb)


@owner_only
async def notif_action(update, context):
    query = update.callback_query
    parts = query.data.split(":")
    act = parts[1]
    if act == "menu":
        await query.answer()
        context.user_data.pop("pending_setup", None)
    elif act == "tg":
        c = await notifier.get()
        await notifier.set_value(parts[2], not c[parts[2]])
        await query.answer(L("Guardado", "Saved"))
    elif act == "to":
        c = await notifier.get()
        nxt = notifier.TARGETS[(notifier.TARGETS.index(c["to"]) + 1) % 3]
        await notifier.set_value("to", nxt)
        await query.answer(L("Guardado", "Saved"))
    elif act == "min":
        await _prompt(update, context, "nt_min", L("Tamaño mínimo", "Minimum size"),
                      [L("Envía el tamaño mínimo en MB para avisar (0 = avisar siempre).", "Send the minimum size in MB to notify (0 = always).")],
                      "nt:menu")
        return
    elif act == "quiet":
        c = await notifier.get()
        if c["quiet_on"]:
            await notifier.set_value("quiet_on", False)
            await query.answer(L("Guardado", "Saved"))
        else:
            await _prompt(update, context, "nt_quiet", L("Horas silenciosas", "Quiet hours"),
                          [L("Envía el rango en horas, por ejemplo <code>23-8</code>. En ese tramo los avisos llegan sin sonido.",
                             "Send the range in hours, for example <code>23-8</code>. During it, alerts arrive without sound.")],
                          "nt:menu")
            return
    text, kb = await notif_content()
    await _show(update, text, kb)


@owner_only
async def notif_command(update, context):
    text, kb = await notif_content()
    await update.effective_message.reply_text(text, parse_mode="HTML", reply_markup=kb)


# ───────────────────────── Disk ─────────────────────────

GUARD_LABEL = lambda: {
    "off": L("⚪ Desactivado", "⚪ Off"),
    "warn": L("⚠️ Avisar y continuar", "⚠️ Warn and continue"),
    "reject": L("⛔ Rechazar si no cabe", "⛔ Reject if it does not fit"),
    "pause": L("⏸️ Dejar en cola hasta que haya espacio", "⏸️ Keep queued until there is space"),
}


async def disk_content(owner: bool = True, note: str = ""):
    cfg = await disk.settings()
    rows = []
    for v in disk.volumes():
        frac = v["used"] / v["total"] if v["total"] else 0
        rows.append([esc(", ".join(v["folders"])), f"<code>{disk.bar(frac)}</code> {frac * 100:.0f}%",
                     disk.human(v["free"]), disk.human(v["total"])])
    parts = [r_h(L("Espacio en disco", "Disk space"), 2, "💾")]
    if note:
        parts.append(r_p(note))
    parts.append(r_table(rows, [L("Carpetas", "Folders"), L("Uso", "Usage"), L("Libre", "Free"), L("Total", "Total")]) if rows
                 else r_p(L("No se pudo leer el espacio.", "Could not read disk space.")))
    kb = []
    if owner:
        parts.append(r_kv_table([
            (L("🛡️ Si no cabe una descarga", "🛡️ If a download does not fit"), GUARD_LABEL()[cfg["guard"]]),
            (L("📦 Reserva libre", "📦 Free reserve"), f"{cfg['reserve_gb']:g} GB"),
            (L("🔔 Alerta de poco espacio", "🔔 Low-space alert"), _on(cfg["alert_on"])),
            (L("📉 Avisar por debajo de", "📉 Alert below"), f"{cfg['alert_gb']:g} GB"),
        ]))
        kb = [
            [Btn(L("🛡️ Modo", "🛡️ Mode"), callback_data="dk:guard"), Btn(L("📦 Reserva", "📦 Reserve"), callback_data="dk:reserve")],
            [Btn(L("🔔 Alerta", "🔔 Alert"), callback_data="dk:alert"), Btn(L("📉 Umbral", "📉 Threshold"), callback_data="dk:thr")],
            [Btn("🔄", callback_data="dk:menu"), *_back()],
        ]
    return rich(*parts), Markup(kb)


@authorized_only
async def disk_command(update, context):
    text, kb = await disk_content(update.effective_user.id == config.OWNER_ID)
    await update.effective_message.reply_text(text, parse_mode="HTML", reply_markup=kb if kb.inline_keyboard else None)


@owner_only
async def disk_action(update, context):
    query = update.callback_query
    act = query.data.split(":")[1]
    cfg = await disk.settings()
    if act == "menu":
        await query.answer()
        context.user_data.pop("pending_setup", None)
    elif act == "guard":
        nxt = disk.MODES[(disk.MODES.index(cfg["guard"]) + 1) % len(disk.MODES)]
        await db.set_setting("disk_guard", nxt)
        await query.answer(L("Guardado", "Saved"))
    elif act == "alert":
        await db.set_setting("disk_alert_on", "0" if cfg["alert_on"] else "1")
        await query.answer(L("Guardado", "Saved"))
    elif act == "reserve":
        await _prompt(update, context, "dk_reserve", L("Reserva libre", "Free reserve"),
                      [L("Envía los GB que deben quedar libres después de cada descarga (0 = ninguna).",
                         "Send the GB that must stay free after each download (0 = none).")], "dk:menu")
        return
    elif act == "thr":
        await _prompt(update, context, "dk_thr", L("Umbral de alerta", "Alert threshold"),
                      [L("Envía los GB libres por debajo de los cuales quieres recibir un aviso.",
                         "Send the free GB below which you want to be alerted.")], "dk:menu")
        return
    text, kb = await disk_content()
    await _show(update, text, kb)


# ───────────────────────── Rules ─────────────────────────

FIELDS = ["name", "keywords", "exclude", "exts", "types", "size", "source", "episode", "regex", "users", "folder", "subpath", "extract", "stop"]


def _mode_label():
    return {"off": L("⚪ Desactivadas", "⚪ Off"), "suggest": L("⭐ Sugerir", "⭐ Suggest"), "auto": L("⚡ Automático", "⚡ Automatic")}


async def rules_content(note: str = ""):
    mode = await rules.get_mode()
    opts = await rules.get_options()
    lst = await rules.load()
    parts = [r_h(L("Reglas de destino", "Destination rules"), 2, "🧭"),
             r_p(L("Eligen la carpeta de una descarga según su nombre, tipo, tamaño u origen. Se evalúan en orden.",
                   "Pick a download's folder by name, type, size or origin. They are evaluated in order."))]
    if note:
        parts.append(r_p(note))
    parts.append(r_kv_table([
        (L("Modo", "Mode"), _mode_label()[mode]),
        (L("Si coinciden varias", "If several match"), L("Usar la primera", "Use the first") if opts["conflict"] == "first" else L("Preguntarme", "Ask me")),
        (L("Carpeta si ninguna coincide", "Folder if none matches"), opts["fallback"] or L("Preguntarme", "Ask me")),
    ]))
    if lst:
        parts.append(r_table(
            [[f"{i + 1}", ("🟢 " if r["enabled"] else "⚪ ") + esc(r["name"]), esc(rules.describe(r)), f"<code>{esc(rules.dest_label(r))}</code>"]
             for i, r in enumerate(lst)],
            ["#", L("Regla", "Rule"), L("Condición", "Condition"), L("Destino", "Destination")]))
    else:
        parts.append(r_p(L("Aún no hay reglas. Crea la primera con ➕.", "No rules yet. Create the first one with ➕.")))
    parts.append(r_footer(L("Suggest: te propone la carpeta con un botón ⭐. Automatic: la aplica sin preguntar (si hay archivo comprimido y la regla dice «preguntar», te pregunta).",
                            "Suggest: offers the folder as a ⭐ button. Automatic: applies it without asking (for archives, if the rule says “ask”, you are asked).")))
    kb = [[Btn(f"{i + 1}. {r['name']}"[:30], callback_data=f"ru:v:{r['id']}") for i, r in enumerate(lst[j:j + 2], j)]
          for j in range(0, len(lst), 2)]
    kb += [
        [Btn(L("✨ Regla rápida: palabra → carpeta", "✨ Quick rule: word → folder"), callback_data="ru:q")],
        [Btn(L("➕ Nueva regla", "➕ New rule"), callback_data="ru:new"), Btn(L("🧪 Probar nombre", "🧪 Test a name"), callback_data="ru:test")],
        [Btn(L("🎚️ Modo", "🎚️ Mode"), callback_data="ru:mode"), Btn(L("⚖️ Conflictos", "⚖️ Conflicts"), callback_data="ru:conflict"),
         Btn(L("📂 Por defecto", "📂 Default"), callback_data="ru:fb")],
        [Btn(L("📖 Tutorial", "📖 Guide"), callback_data="guide:rules:ru:menu"), *_back()],
    ]
    return rich(*parts), Markup(kb)


def _find(lst, rid):
    return next((r for r in lst if r["id"] == rid), None)


def rule_view(r: dict, note: str = ""):
    sizes = " ".join(x for x in (f"≥{r['min_mb']:g} MB" if r["min_mb"] else "", f"≤{r['max_mb']:g} MB" if r["max_mb"] else "") if x) or "—"
    parts = [r_h(r["name"], 2, "🧭")]
    if note:
        parts.append(r_p(note))
    parts.append(r_kv_table([
        (L("Activa", "Enabled"), _on(r["enabled"])),
        (L("Contiene (alguna)", "Contains (any)"), esc(", ".join(r["keywords"])) or "—"),
        (L("Excluir", "Exclude"), esc(", ".join(r["exclude"])) or "—"),
        (L("Extensiones", "Extensions"), esc(", ".join(r["exts"])) or "—"),
        (L("Tipos", "Types"), esc(", ".join(r["types"])) or "—"),
        (L("Tamaño", "Size"), sizes),
        (L("Origen", "Source"), r["source"]),
        (L("Episodio de serie", "Series episode"), {"any": L("Da igual", "Any"), "yes": L("Sí", "Yes"), "no": L("No", "No")}[r["episode"]]),
        ("Regex", f"<code>{esc(r['regex'])}</code>" if r["regex"] else "—"),
        (L("Usuarios", "Users"), ", ".join(str(u) for u in r["users"]) or "—"),
        (L("Carpeta", "Folder"), esc(r["folder"]) or L("⚠️ sin elegir", "⚠️ not set")),
        (L("Subcarpeta", "Subfolder"), f"<code>{esc(r['subpath'])}</code>" if r["subpath"] else "—"),
        (L("Descomprimir", "Extract"), {"ask": L("Preguntar", "Ask"), "yes": L("Sí", "Yes"), "no": L("No", "No")}[r["extract"]]),
        (L("Parar al coincidir", "Stop on match"), _on(r["stop"])),
    ]))
    parts.append(r_footer(L("Subcarpeta admite {year} {month} {day} {ext} {user} {name} {first}. Ej.: <code>Fotos/{year}/{month}</code>",
                            "Subfolder accepts {year} {month} {day} {ext} {user} {name} {first}. E.g. <code>Photos/{year}/{month}</code>")))
    i = r["id"]
    kb = [
        [Btn(L("✏️ Nombre", "✏️ Name"), callback_data=f"ru:ed:{i}:name"), Btn(L("🔤 Contiene", "🔤 Contains"), callback_data=f"ru:ed:{i}:keywords"),
         Btn(L("🚫 Excluir", "🚫 Exclude"), callback_data=f"ru:ed:{i}:exclude")],
        [Btn(L("📄 Extensiones", "📄 Extensions"), callback_data=f"ru:ed:{i}:exts"), Btn(L("🎬 Tipos", "🎬 Types"), callback_data=f"ru:ty:{i}"),
         Btn(L("📏 Tamaño", "📏 Size"), callback_data=f"ru:ed:{i}:size")],
        [Btn(L("🌐 Origen", "🌐 Source"), callback_data=f"ru:cy:{i}:source"), Btn(L("📺 Episodio", "📺 Episode"), callback_data=f"ru:cy:{i}:episode"),
         Btn("Regex", callback_data=f"ru:ed:{i}:regex")],
        [Btn(L("👥 Usuarios", "👥 Users"), callback_data=f"ru:ed:{i}:users"), Btn(L("📁 Carpeta", "📁 Folder"), callback_data=f"ru:fo:{i}"),
         Btn(L("📂 Subcarpeta", "📂 Subfolder"), callback_data=f"ru:ed:{i}:subpath")],
        [Btn(L("📦 Descomprimir", "📦 Extract"), callback_data=f"ru:cy:{i}:extract"), Btn(L("⏹️ Parar", "⏹️ Stop"), callback_data=f"ru:cy:{i}:stop"),
         Btn(L("⏯️ Activar/desactivar", "⏯️ Enable/disable"), callback_data=f"ru:cy:{i}:enabled")],
        [Btn("⬆️", callback_data=f"ru:up:{i}"), Btn("⬇️", callback_data=f"ru:dn:{i}"), Btn("🗑️", callback_data=f"ru:del:{i}")],
        _back("ru:menu", L("⬅️ Reglas", "⬅️ Rules")),
    ]
    return rich(*parts), Markup(kb)


CYCLES = {"source": rules.SOURCES, "episode": ("any", "yes", "no"), "extract": rules.EXTRACT}


@owner_only
async def rules_action(update, context):
    query = update.callback_query
    parts = query.data.split(":")
    act = parts[1]
    lst = await rules.load()
    if act == "menu":
        await query.answer()
        context.user_data.pop("pending_setup", None)
        text, kb = await rules_content()
        await _show(update, text, kb)
    elif act == "mode":
        mode = await rules.get_mode()
        await rules.set_mode(rules.MODES[(rules.MODES.index(mode) + 1) % 3])
        await query.answer(L("Guardado", "Saved"))
        text, kb = await rules_content()
        await _show(update, text, kb)
    elif act == "conflict":
        opts = await rules.get_options()
        await rules.set_option("conflict", "ask" if opts["conflict"] == "first" else "first")
        await query.answer(L("Guardado", "Saved"))
        text, kb = await rules_content()
        await _show(update, text, kb)
    elif act == "fb":
        await query.answer()
        names = list(config.FOLDERS)
        kb = [[Btn(n, callback_data=f"ru:fbs:{i}") for i, n in enumerate(names)],
              [Btn(L("Preguntarme siempre", "Always ask me"), callback_data="ru:fbs:x")], _back("ru:menu", L("⬅️ Reglas", "⬅️ Rules"))]
        text = rich(r_h(L("Carpeta por defecto", "Default folder"), 2, "📂"),
                    r_p(L("Se usa cuando ninguna regla coincide (si hay modo sugerir/automático).", "Used when no rule matches (in suggest/automatic mode).")))
        await _show(update, text, Markup(kb))
    elif act == "fbs":
        names = list(config.FOLDERS)
        await rules.set_option("fallback", names[int(parts[2])] if parts[2] != "x" else "")
        await query.answer(L("Guardado", "Saved"))
        text, kb = await rules_content()
        await _show(update, text, kb)
    elif act == "q":
        await _prompt(update, context, "ru_quick", L("Regla rápida", "Quick rule"),
                      [L("Envía la palabra o frase que debe contener el nombre del archivo. "
                         "Puedes poner varias separadas por comas (basta con que aparezca una).",
                         "Send the word or phrase the file name must contain. "
                         "You can send several separated by commas (any one is enough)."),
                       L("Ejemplo: <code>Ubuntu, linux iso</code>", "Example: <code>Ubuntu, linux iso</code>")], "ru:menu")
    elif act == "qf":
        kw = (context.user_data.get("ru_quick") or {}).get("kw")
        names = list(config.FOLDERS)
        if not kw or int(parts[2]) >= len(names):
            await query.answer(L("Caducó, empieza de nuevo", "Expired, start again"), show_alert=True)
            return
        folder = names[int(parts[2])]
        r = rules.normalize({"name": (L("Contiene ", "Contains ") + kw[0])[:40], "keywords": kw, "folder": folder})
        lst.append(r)
        await rules.save(lst)
        context.user_data.pop("ru_quick", None)
        await query.answer(L("Regla creada", "Rule created"))
        mode = await rules.get_mode()
        note = L(f"✅ Los archivos cuyo nombre contenga «{esc(', '.join(kw))}» irán a <b>{esc(folder)}</b>.",
                 f"✅ Files whose name contains “{esc(', '.join(kw))}” will go to <b>{esc(folder)}</b>.")
        kb_extra = []
        if mode != "auto":
            note += "<br/>" + L("Ahora mismo las reglas solo <b>sugieren</b> la carpeta (o están apagadas). Activa el modo automático para que se aplique sola.",
                                "Rules currently only <b>suggest</b> the folder (or are off). Turn on automatic mode to apply it by itself.")
            kb_extra = [[Btn(L("⚡ Aplicar automáticamente", "⚡ Apply automatically"), callback_data="ru:qauto")]]
        text, kb = rule_view(r, note)
        kb = Markup([*kb_extra, *kb.inline_keyboard]) if kb_extra else kb
        await _show(update, text, kb)
    elif act == "qauto":
        await rules.set_mode("auto")
        await query.answer(L("Modo automático activado", "Automatic mode on"))
        text, kb = await rules_content(L("⚡ Modo automático activado.", "⚡ Automatic mode on."))
        await _show(update, text, kb)
    elif act == "new":
        await _prompt(update, context, "ru_new", L("Nueva regla", "New rule"),
                      [L("Envía un nombre para la regla.", "Send a name for the rule.")], "ru:menu")
    elif act == "test":
        await _prompt(update, context, "ru_test", L("Probar reglas", "Test rules"),
                      [L("Envía un nombre de archivo, por ejemplo <code>Serie.S01E02.1080p.mkv</code>.",
                         "Send a file name, for example <code>Show.S01E02.1080p.mkv</code>.")], "ru:menu")
    else:
        r = _find(lst, parts[2])
        if not r:
            await query.answer(L("Regla no encontrada", "Rule not found"), show_alert=True)
            return
        await _rule_action(update, context, query, act, parts, r, lst)


async def _rule_action(update, context, query, act, parts, r, lst):
    if act == "v":
        await query.answer()
        context.user_data.pop("pending_setup", None)
    elif act == "ed":
        field = parts[3]
        hints = {
            "name": L("Envía el nombre.", "Send the name."),
            "keywords": L("Palabras separadas por comas; basta con que el nombre contenga una. <code>-</code> para vaciar.",
                          "Comma-separated words; the name needs to contain any. <code>-</code> to clear."),
            "exclude": L("Palabras separadas por comas que NO deben aparecer. <code>-</code> para vaciar.", "Comma-separated words that must NOT appear. <code>-</code> to clear."),
            "exts": L("Extensiones separadas por comas, p. ej. <code>mkv, mp4</code>. <code>-</code> para vaciar.", "Comma-separated extensions, e.g. <code>mkv, mp4</code>. <code>-</code> to clear."),
            "size": L("Rango en MB: <code>500-</code> (mínimo), <code>-2000</code> (máximo) o <code>500-2000</code>. <code>-</code> para vaciar.",
                      "Range in MB: <code>500-</code> (min), <code>-2000</code> (max) or <code>500-2000</code>. Send <code>none</code> to clear."),
            "regex": L("Expresión regular sobre el nombre. <code>-</code> para vaciar.", "Regular expression on the name. <code>-</code> to clear."),
            "users": L("IDs de usuario de Telegram separados por comas (la regla solo vale para ellos). <code>-</code> para vaciar.",
                       "Comma-separated Telegram user IDs (the rule only applies to them). <code>-</code> to clear."),
            "subpath": L("Subcarpeta dentro de la carpeta, con plantillas {year} {month} {ext} {user} {name} {first}. <code>-</code> para vaciar.",
                         "Subfolder inside the folder, with templates {year} {month} {ext} {user} {name} {first}. <code>-</code> to clear."),
        }
        await _prompt(update, context, "ru_field", L("Editar regla", "Edit rule"), [hints[field]], f"ru:v:{r['id']}",
                      {"rule": r["id"], "field": field})
        return
    elif act == "ty":
        await query.answer()
        kb = [[Btn(("✅ " if t in r["types"] else "⬜ ") + t, callback_data=f"ru:tt:{r['id']}:{t}")] for t in rules.EXT_GROUPS]
        kb.append(_back(f"ru:v:{r['id']}", L("⬅️ Regla", "⬅️ Rule")))
        text = rich(r_h(L("Tipos de archivo", "File types"), 2, "🎬"),
                    r_p(L("La regla vale si la extensión es de alguno de los tipos marcados.", "The rule matches if the extension is of any selected type.")))
        await _show(update, text, Markup(kb))
        return
    elif act == "tt":
        t = parts[3]
        r["types"] = [x for x in r["types"] if x != t] if t in r["types"] else r["types"] + [t]
        await rules.save(lst)
        await query.answer()
        kb = [[Btn(("✅ " if x in r["types"] else "⬜ ") + x, callback_data=f"ru:tt:{r['id']}:{x}")] for x in rules.EXT_GROUPS]
        kb.append(_back(f"ru:v:{r['id']}", L("⬅️ Regla", "⬅️ Rule")))
        text = rich(r_h(L("Tipos de archivo", "File types"), 2, "🎬"))
        await _show(update, text, Markup(kb))
        return
    elif act == "cy":
        field = parts[3]
        if field in ("stop", "enabled"):
            r[field] = not r[field]
        else:
            opts = CYCLES[field]
            r[field] = opts[(opts.index(r[field]) + 1) % len(opts)]
        await rules.save(lst)
        await query.answer(L("Guardado", "Saved"))
    elif act == "fo":
        await query.answer()
        names = list(config.FOLDERS)
        kb = [[Btn(("✅ " if n == r["folder"] else "") + n, callback_data=f"ru:fs:{r['id']}:{i}") for i, n in enumerate(names)],
              _back(f"ru:v:{r['id']}", L("⬅️ Regla", "⬅️ Rule"))]
        text = rich(r_h(L("Carpeta destino", "Destination folder"), 2, "📁"))
        await _show(update, text, Markup(kb))
        return
    elif act == "fs":
        r["folder"] = list(config.FOLDERS)[int(parts[3])]
        await rules.save(lst)
        await query.answer(L("Guardado", "Saved"))
    elif act in ("up", "dn"):
        i = lst.index(r)
        j = i - 1 if act == "up" else i + 1
        if 0 <= j < len(lst):
            lst[i], lst[j] = lst[j], lst[i]
            await rules.save(lst)
        await query.answer()
        text, kb = await rules_content()
        await _show(update, text, kb)
        return
    elif act == "del":
        if len(parts) > 3:
            lst.remove(r)
            await rules.save(lst)
            await query.answer(L("Eliminada", "Deleted"))
            text, kb = await rules_content()
            await _show(update, text, kb)
            return
        await query.answer()
        text = rich(r_h(L("¿Eliminar la regla?", "Delete the rule?"), 2, "🗑️"), r_p(esc(r["name"])))
        kb = Markup([[Btn(L("🗑️ Sí, eliminar", "🗑️ Yes, delete"), callback_data=f"ru:del:{r['id']}:y"),
                      Btn(L("✖️ No", "✖️ No"), callback_data=f"ru:v:{r['id']}")]])
        await _show(update, text, kb)
        return
    text, kb = rule_view(r)
    await _show(update, text, kb)


def _split(raw):
    return [] if raw.strip() in ("-", "") else [x.strip() for x in raw.split(",") if x.strip()]


async def handle_pending(update, context, pending, raw, finish, retry) -> bool:
    kind = pending["kind"]
    if kind == "bk_pw":
        if len(raw) < 4:
            await retry(L("Mínimo 4 caracteres.", "At least 4 characters."))
            return True
        context.user_data["bk_pw"] = raw
        text, kb = await backup_content(context, L("🔒 Contraseña establecida.", "🔒 Password set."))
        await finish(update, context, pending, text, kb)
        return True
    if kind == "bk_restore_pw":
        context.user_data.pop("pending_setup", None)
        return await _open_restore(context, pending, raw)
    if kind == "nt_min":
        n = _num(raw)
        if n is None:
            await retry(L("Envía un número.", "Send a number."))
            return True
        await notifier.set_value("min_mb", int(n))
        text, kb = await notif_content()
        await finish(update, context, pending, text, kb)
        return True
    if kind == "nt_quiet":
        m = re.match(r"^\s*(\d{1,2})\s*[-–:]\s*(\d{1,2})\s*$", raw)
        if not m or int(m.group(1)) > 23 or int(m.group(2)) > 23:
            await retry(L("Formato: <code>23-8</code>.", "Format: <code>23-8</code>."))
            return True
        await notifier.set_value("quiet_from", int(m.group(1)))
        await notifier.set_value("quiet_to", int(m.group(2)))
        await notifier.set_value("quiet_on", True)
        text, kb = await notif_content()
        await finish(update, context, pending, text, kb)
        return True
    if kind in ("dk_reserve", "dk_thr"):
        n = _num(raw)
        if n is None:
            await retry(L("Envía un número.", "Send a number."))
            return True
        await db.set_setting("disk_reserve_gb" if kind == "dk_reserve" else "disk_alert_gb", f"{n:g}")
        text, kb = await disk_content()
        await finish(update, context, pending, text, kb)
        return True
    if kind == "ru_new":
        lst = await rules.load()
        r = rules.normalize({"name": raw, "folder": next(iter(config.FOLDERS), "")})
        lst.append(r)
        await rules.save(lst)
        text, kb = rule_view(r, L("✅ Regla creada. Ajusta sus condiciones y su destino.", "✅ Rule created. Adjust its conditions and destination."))
        await finish(update, context, pending, text, kb)
        return True
    if kind == "ru_quick":
        kw = [x.strip().lower() for x in re.split(r"[,\n]", raw) if x.strip()]
        if not kw:
            await retry(L("Envía al menos una palabra o frase.", "Send at least one word or phrase."))
            return True
        context.user_data["ru_quick"] = {"kw": kw}
        context.user_data.pop("pending_setup", None)
        names = list(config.FOLDERS)
        text = rich(r_h(L("¿A qué carpeta?", "Which folder?"), 2, "📁"),
                    r_p(L(f"Si el nombre contiene «{esc(', '.join(kw))}», se descargará en:",
                          f"If the name contains “{esc(', '.join(kw))}”, it will be downloaded to:")))
        kb = [[Btn(n, callback_data=f"ru:qf:{i}")] for i, n in enumerate(names)]
        kb.append(_back("ru:menu", L("✖️ Cancelar", "✖️ Cancel")))
        await finish(update, context, pending, text, Markup(kb))
        return True
    if kind == "ru_test":
        found = await rules.find(raw, 0, "any", None)
        mode = await rules.get_mode()
        if found:
            lines = [f"{esc(r['name'])} → <code>{esc(rules.dest_label(r))}</code>" for r in found]
            note = L("✅ Coincide:", "✅ Matches:") + "<br/>" + "<br/>".join(lines)
        else:
            note = L("⚪ Ninguna regla coincide (el tamaño y el origen no se evalúan en esta prueba).",
                     "⚪ No rule matches (size and source are not evaluated in this test).")
        if mode == "off":
            note += "<br/>" + L("Las reglas están desactivadas.", "Rules are turned off.")
        text, kb = await rules_content(note)
        await finish(update, context, pending, text, kb)
        return True
    if kind == "ru_field":
        lst = await rules.load()
        r = _find(lst, pending["rule"])
        field = pending["field"]
        if not r:
            return True
        if field == "name":
            r["name"] = raw[:40]
        elif field in ("keywords", "exclude", "exts"):
            r[field] = [x.lower().lstrip(".") if field == "exts" else x.lower() for x in _split(raw)]
        elif field == "size":
            lo, _, hi = raw.partition("-")
            if raw.strip().lower() in ("none", "-", ""):
                r["min_mb"] = r["max_mb"] = 0
            else:
                a, b = (_num(lo) if lo.strip() else 0), (_num(hi) if hi.strip() else 0)
                if a is None or b is None:
                    await retry(L("Formato: <code>500-2000</code>.", "Format: <code>500-2000</code>."))
                    return True
                r["min_mb"], r["max_mb"] = a, b
        elif field == "regex":
            val = "" if raw.strip() == "-" else raw
            try:
                re.compile(val)
            except re.error as e:
                await retry(L(f"Regex no válida: {e}", f"Invalid regex: {e}"))
                return True
            r["regex"] = val
        elif field == "users":
            vals = _split(raw)
            if any(not v.lstrip("-").isdigit() for v in vals):
                await retry(L("Solo IDs numéricos.", "Numeric IDs only."))
                return True
            r["users"] = [int(v) for v in vals]
        elif field == "subpath":
            r["subpath"] = "" if raw.strip() == "-" else raw.strip().strip("/")
        await rules.save([rules.normalize(x) for x in lst])
        text, kb = rule_view(rules.normalize(r), L("✅ Guardado.", "✅ Saved."))
        await finish(update, context, pending, text, kb)
        return True
    return False
