"""Cloudflare Tunnel managed from the bot (runs `cloudflared` inside the bot container).

Settings (database): cf_token (tunnel token), cf_enabled ("1"/"0").
CLOUDFLARE_TUNNEL_TOKEN in the environment is only used as the initial token if none is saved.
In the Cloudflare dashboard the public hostname must point to HTTP `bot:8080` (or `localhost:8080`).
"""
import asyncio
import logging
import os
import shutil

import db

logger = logging.getLogger(__name__)

_proc: asyncio.subprocess.Process | None = None
_watch: asyncio.Task | None = None
_state = {"connected": False, "last": ""}
_wanted = False


def binary() -> str | None:
    return shutil.which("cloudflared")


async def get_token() -> str:
    return (await db.get_setting("cf_token") or os.getenv("CLOUDFLARE_TUNNEL_TOKEN", "")).strip()


async def is_enabled() -> bool:
    return (await db.get_setting("cf_enabled", "0")) == "1"


def valid_token(token: str) -> bool:
    return len(token) >= 40 and " " not in token and "\n" not in token


def running() -> bool:
    return _proc is not None and _proc.returncode is None


def status() -> dict:
    return {"running": running(), "connected": running() and _state["connected"], "last": _state["last"],
            "installed": binary() is not None}


async def _read(proc) -> None:
    assert proc.stdout is not None
    async for raw in proc.stdout:
        line = raw.decode(errors="replace").strip()
        low = line.lower()
        if "registered tunnel connection" in low:
            _state["connected"] = True
        elif " err " in low or "error" in low or "failed" in low:
            _state["last"] = line[-200:]
            if "unauthorized" in low or "invalid" in low:
                _state["connected"] = False


async def _supervise() -> None:
    global _proc
    while _wanted:
        token = await get_token()
        if not token:
            return
        _state.update(connected=False)
        try:
            _proc = await asyncio.create_subprocess_exec(
                binary(), "tunnel", "--no-autoupdate", "run", "--token", token,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        except Exception as e:
            _state["last"] = str(e)
            return
        await _read(_proc)
        await _proc.wait()
        if not _wanted:
            return
        _state["connected"] = False
        await asyncio.sleep(10)


async def start() -> tuple[bool, str]:
    """Starts the tunnel. Returns (ok, reason) where reason is 'nobinary', 'notoken' or ''."""
    global _wanted, _watch
    if not binary():
        return False, "nobinary"
    if not await get_token():
        return False, "notoken"
    await stop()
    _wanted = True
    _watch = asyncio.create_task(_supervise())
    await db.set_setting("cf_enabled", "1")
    return True, ""


async def stop(persist: bool = False) -> None:
    global _wanted, _watch, _proc
    _wanted = False
    if _proc and _proc.returncode is None:
        try:
            _proc.terminate()
            await asyncio.wait_for(_proc.wait(), 5)
        except Exception:
            try:
                _proc.kill()
            except Exception:
                pass
    if _watch:
        _watch.cancel()
        _watch = None
    _proc = None
    _state["connected"] = False
    if persist:
        await db.set_setting("cf_enabled", "0")


async def autostart() -> None:
    """On boot: starts the tunnel if it was enabled (or a token came from the environment)."""
    enabled = await is_enabled()
    if not enabled and not await db.get_setting("cf_token") and os.getenv("CLOUDFLARE_TUNNEL_TOKEN"):
        enabled = True
    if enabled and await get_token():
        await start()
