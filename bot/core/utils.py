from functools import wraps

import config
import db


def get_command_payload(update) -> str:
    text = update.effective_message.text or ""
    parts = text.split(maxsplit=1)
    return parts[1] if len(parts) > 1 else ""


async def is_authorized(user_id: int) -> bool:
    if user_id == config.OWNER_ID:
        return True
    return await db.is_authorized_user(user_id)


def is_owner(user_id: int) -> bool:
    return user_id == config.OWNER_ID


def owner_only(func):
    @wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        user = update.effective_user
        if not user or user.id != config.OWNER_ID:
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


def authorized_only(func):
    @wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        user = update.effective_user
        if not user:
            return
        if user.id != config.OWNER_ID:
            if not await db.is_authorized_user(user.id):
                return
            try:
                await db.update_authorized_user_info(user.id, user.username, user.first_name)
            except Exception:
                pass
        return await func(update, context, *args, **kwargs)
    return wrapper


CLIENT_LABELS = {
    "aria2": ("⚡", "Aria2"),
    "realdebrid": ("💳", "Real-Debrid → Aria2"),
    "torbox": ("📦", "TorBox → Aria2"),
    "telegram": ("🤖", "Telegram (userbot)"),
    "gdrive": ("📁", "Google Drive"),
    "ytdlp": ("🎞️", "yt-dlp"),
    "extract": ("📦", "Descompresión"),
    "upload": ("📤", "Subida (Userbot)"),
}

_KIND_TO_CLIENT = {
    "link": "aria2", "rd_link": "realdebrid", "telegram": "telegram",
    "gdrive": "gdrive", "ytdl": "ytdlp", "extract": "extract", "upload": "upload",
}


def task_client(task: dict) -> str:
    return (task.get("client") or _KIND_TO_CLIENT.get(task.get("kind"), "aria2"))


def client_label(task: dict, with_emoji: bool = True) -> str:
    emoji, label = CLIENT_LABELS.get(task_client(task), ("", task_client(task)))
    return f"{emoji} {label}" if with_emoji and emoji else label
