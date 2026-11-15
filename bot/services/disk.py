import os
import shutil

import config
import db
from i18n import L

GB = 1024 ** 3
MODES = ("off", "warn", "reject", "pause")


def _existing(path: str) -> str | None:
    p = os.path.abspath(path)
    while p and not os.path.exists(p):
        parent = os.path.dirname(p)
        if parent == p:
            return None
        p = parent
    return p or None


def usage(path: str) -> dict | None:
    real = _existing(path)
    if not real:
        return None
    try:
        total, used, free = shutil.disk_usage(real)
        return {"total": total, "used": used, "free": free, "dev": os.stat(real).st_dev}
    except OSError:
        return None


def volumes() -> list[dict]:
    seen: dict[int, dict] = {}
    for name, path in config.FOLDERS.items():
        u = usage(path)
        if not u:
            continue
        entry = seen.setdefault(u["dev"], {**u, "folders": [], "path": path})
        entry["folders"].append(name)
    return list(seen.values())


async def settings() -> dict:
    mode = await db.get_setting("disk_guard", "warn")
    return {
        "guard": mode if mode in MODES else "warn",
        "reserve_gb": _num(await db.get_setting("disk_reserve_gb", "2"), 2),
        "alert_on": await db.get_setting("disk_alert_on", "1") == "1",
        "alert_gb": _num(await db.get_setting("disk_alert_gb", "10"), 10),
        "cooldown_h": _num(await db.get_setting("disk_cooldown_h", "12"), 12),
    }


def _num(raw, default):
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return default


async def check_fit(path: str, size: int) -> dict:
    cfg = await settings()
    u = usage(path)
    if not u or not size or size <= 0:
        return {"ok": True, "known": False, "free": u["free"] if u else 0, "needed": size or 0, "guard": cfg["guard"]}
    needed = int(size + cfg["reserve_gb"] * GB)
    return {"ok": u["free"] >= needed, "known": True, "free": u["free"], "needed": needed, "size": size, "guard": cfg["guard"]}


def human(n: float) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def bar(frac: float, width: int = 10) -> str:
    filled = max(0, min(width, round(frac * width)))
    return "█" * filled + "░" * (width - filled)


def no_space_text(name: str, res: dict) -> str:
    return L(
        f"💾 No hay espacio suficiente para «{name}»: necesita {human(res['needed'])} (incluye la reserva) y quedan {human(res['free'])} libres.",
        f"💾 Not enough space for “{name}”: it needs {human(res['needed'])} (including the reserve) and {human(res['free'])} are free.",
    )
