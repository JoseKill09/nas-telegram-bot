import logging
from datetime import datetime

import config
import db
from i18n import L

logger = logging.getLogger(__name__)

_bot = None
_alerted: dict[str, float] = {}

DEFAULTS = {
    "enabled": "1", "done": "1", "failed": "1", "min_mb": "0", "to": "requester",
    "quiet_on": "0", "quiet_from": "23", "quiet_to": "8", "disk": "1",
}
TARGETS = ("requester", "owner", "both")


def set_bot(bot) -> None:
    global _bot
    _bot = bot


async def get() -> dict:
    out = {}
    for k, d in DEFAULTS.items():
        out[k] = await db.get_setting(f"notif_{k}", d)
    return {
        "enabled": out["enabled"] == "1", "done": out["done"] == "1", "failed": out["failed"] == "1",
        "min_mb": _int(out["min_mb"], 0), "to": out["to"] if out["to"] in TARGETS else "requester",
        "quiet_on": out["quiet_on"] == "1", "quiet_from": _int(out["quiet_from"], 23) % 24,
        "quiet_to": _int(out["quiet_to"], 8) % 24, "disk": out["disk"] == "1",
    }


def _int(raw, default):
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return default


async def set_value(key: str, value) -> None:
    await db.set_setting(f"notif_{key}", "1" if value is True else "0" if value is False else str(value))


def in_quiet(cfg: dict, hour: int | None = None) -> bool:
    if not cfg["quiet_on"]:
        return False
    h = datetime.now().hour if hour is None else hour
    a, b = cfg["quiet_from"], cfg["quiet_to"]
    if a == b:
        return False
    return a <= h < b if a < b else (h >= a or h < b)


def _recipients(cfg: dict, task: dict) -> list[int]:
    req = task.get("requested_by")
    out = []
    if cfg["to"] in ("requester", "both") and req:
        out.append(int(req))
    if cfg["to"] in ("owner", "both") or not out:
        out.append(config.OWNER_ID)
    return list(dict.fromkeys(out))


def _duration(task: dict) -> str:
    try:
        a = datetime.fromisoformat(str(task.get("started_at")).replace(" ", "T"))
        secs = int((datetime.now(a.tzinfo) - a).total_seconds())
    except (TypeError, ValueError):
        return ""
    if secs < 1:
        return ""
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m}m" if h else f"{m}m {s}s" if m else f"{s}s"


def _size(n) -> str:
    from disk import human
    return human(n) if n else ""


def build_text(task: dict) -> str:
    from rich_ui import esc
    name = esc(task.get("filename") or "?")
    folder = esc(task.get("dest_folder") or "")
    if task.get("status") == "done":
        bits = [b for b in (_size(task.get("total_size")), _duration(task)) if b]
        text = L("✅ <b>Descarga terminada</b>", "✅ <b>Download finished</b>") + f"\n<code>{name}</code>"
        if folder:
            text += f"\n📁 {folder}"
        if bits:
            text += "\n" + " · ".join(bits)
        return text
    err = esc(str(task.get("error") or "")[:300])
    text = L("❌ <b>Descarga fallida</b>", "❌ <b>Download failed</b>") + f"\n<code>{name}</code>"
    if err:
        text += f"\n{err}"
    return text


async def task_changed(task: dict) -> None:
    if _bot is None or not task:
        return
    try:
        cfg = await get()
        if not cfg["enabled"]:
            return
        status = task.get("status")
        if status == "done":
            if not cfg["done"] or task.get("kind") in ("extract", "upload"):
                return
            if cfg["min_mb"] and (task.get("total_size") or 0) < cfg["min_mb"] * 1024 * 1024:
                return
        elif status == "error":
            if not cfg["failed"] or (task.get("error") or "") in ("cancelled", "auto_paused"):
                return
        else:
            return
        text = build_text(task)
        silent = in_quiet(cfg)
        for chat in _recipients(cfg, task):
            try:
                await _bot.send_message(chat_id=chat, text=text, parse_mode="HTML", disable_notification=silent)
            except Exception as e:
                logger.warning("notify %s failed: %s", chat, e)
    except Exception:
        logger.exception("notifier")


async def send_owner(text: str, force_sound: bool = False) -> None:
    if _bot is None:
        return
    cfg = await get()
    silent = in_quiet(cfg) and not force_sound
    try:
        await _bot.send_message(chat_id=config.OWNER_ID, text=text, parse_mode="HTML", disable_notification=silent)
    except Exception as e:
        logger.warning("notify owner failed: %s", e)


async def disk_job(context) -> None:
    import disk
    cfg = await get()
    dcfg = await disk.settings()
    if not (cfg["enabled"] and cfg["disk"] and dcfg["alert_on"]):
        return
    import time
    now = time.time()
    for v in disk.volumes():
        key = str(v["dev"])
        low = v["free"] < dcfg["alert_gb"] * disk.GB
        if not low:
            _alerted.pop(key, None)
            continue
        last = _alerted.get(key, 0)
        if now - last < dcfg["cooldown_h"] * 3600:
            continue
        _alerted[key] = now
        names = ", ".join(v["folders"])
        await send_owner(L(
            f"⚠️ <b>Poco espacio en disco</b>\n{names}: quedan {disk.human(v['free'])} de {disk.human(v['total'])}.",
            f"⚠️ <b>Low disk space</b>\n{names}: {disk.human(v['free'])} left of {disk.human(v['total'])}.",
        ))
