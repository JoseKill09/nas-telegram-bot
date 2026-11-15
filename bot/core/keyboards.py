import secrets
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

import config
from i18n import L

_path_tokens: dict[str, tuple[str, str]] = {}
_token_by_path: dict[tuple[str, str], str] = {}


def token_for(folder_key: str, relpath: str) -> str:
    key = (folder_key, relpath)
    if key in _token_by_path:
        return _token_by_path[key]
    token = secrets.token_hex(4)
    _path_tokens[token] = key
    _token_by_path[key] = token
    return token


def resolve_token(token: str):
    return _path_tokens.get(token)


def main_menu(is_owner: bool = True) -> InlineKeyboardMarkup:
    kb = []

    if config.WEBAPP_ENABLED and config.WEBAPP_URL:
        kb.append([InlineKeyboardButton(L("🖥️ Abrir panel web", "🖥️ Open web panel"), web_app=WebAppInfo(url=config.WEBAPP_URL))])

    kb.append([
        InlineKeyboardButton(L("📥 Cola", "📥 Queue"), callback_data="queue:view"),
        InlineKeyboardButton(L("📂 Archivos", "📂 Files"), callback_data="fm:root"),
    ])
    kb.append([
        InlineKeyboardButton(L("🗂️ Historial", "🗂️ History"), callback_data="hist:page:0"),
        InlineKeyboardButton(L("ℹ️ Ayuda", "ℹ️ Help"), callback_data="menu:help"),
    ])

    if is_owner:
        kb.append([
            InlineKeyboardButton("🤖 Userbot", callback_data="ub:menu"),
            InlineKeyboardButton(L("⚙️ Ajustes", "⚙️ Settings"), callback_data="settings:menu"),
        ])

    return InlineKeyboardMarkup(kb)


def folders_menu(prefix: str) -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(name, callback_data=f"{prefix}:{name}") for name in config.FOLDERS]
    return InlineKeyboardMarkup([row])
