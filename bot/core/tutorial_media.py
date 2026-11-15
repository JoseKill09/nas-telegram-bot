"""Carousel of web app screenshots for the web app tutorial (chat only).

The screenshots live in static/tutorial/<lang>/01..06.jpg. The first time they are needed the bot
uploads them once (as one album that is deleted at once) and keeps Telegram's file_id in the database.

Cascade (the first one that Telegram accepts is remembered until the next restart):
  1. Rich Message made of blocks: slideshow + guide text + embedded buttons.
  2. Rich Message in HTML with <tg-slideshow> and the media list (classic buttons below).
  3. Classic album of photos with captions + the guide as a normal message.
"""
import logging
import os

from telegram import InputMediaPhoto
from telegram.error import BadRequest, TelegramError

import db
import i18n
import rich_blocks
import rich_bot

logger = logging.getLogger(__name__)

DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "tutorial")
COUNT = 6
CAPTIONS = {
    "en": ["Downloads: progress, speed and time left", "New download: links, magnets, Google Drive and video sites",
           "Torrent search with filters and TorBox cache ⚡", "File manager on your NAS",
           "History of finished downloads", "Every setting, also available in the chat"],
    "es": ["Descargas: progreso, velocidad y tiempo restante", "Nueva descarga: enlaces, magnets, Google Drive y webs de vídeo",
           "Búsqueda de torrents con filtros y caché de TorBox ⚡", "Gestor de archivos de tu NAS",
           "Historial de descargas terminadas", "Todos los ajustes, también disponibles en el chat"],
}
_state = {"skip": set()}  # methods Telegram rejected since the last restart


def _lang() -> str:
    return "es" if i18n.lang == "es" else "en"


def available() -> bool:
    return all(os.path.isfile(os.path.join(DIR, _lang(), f"{n:02d}.jpg")) for n in range(1, COUNT + 1))


async def _file_ids(bot, chat_id: int, lang: str) -> list[str]:
    keys = [f"tut_fid_{lang}_{n}" for n in range(1, COUNT + 1)]
    ids = [await db.get_setting(k) for k in keys]
    if all(ids):
        return ids
    files = [open(os.path.join(DIR, lang, f"{n:02d}.jpg"), "rb") for n in range(1, COUNT + 1)]
    try:
        msgs = await bot.send_media_group(chat_id, [InputMediaPhoto(f) for f in files], disable_notification=True)
    finally:
        for f in files:
            f.close()
    ids = [m.photo[-1].file_id for m in msgs]
    for k, fid in zip(keys, ids):
        await db.set_setting(k, fid)
    for m in msgs:
        try:
            await m.delete()
        except TelegramError:
            pass
    return ids


async def send(bot, chat_id: int, guide_html: str, markup) -> bool:
    """Sends the web app tutorial with the screenshot carousel. Returns False if nothing could be sent
    (the caller then shows the plain text guide)."""
    if not available():
        return False
    lang = _lang()
    caps = CAPTIONS[lang]
    try:
        ids = await _file_ids(bot, chat_id, lang)
    except TelegramError as e:
        logger.warning("Tutorial: no se pudieron subir las capturas (%s); se muestra solo el texto.", e)
        return False
    markup = i18n.tr_markup(markup) if markup is not None else None

    if rich_bot.is_enabled() and "blocks" not in _state["skip"] and markup is not None:
        try:
            text_blocks = rich_blocks.html_to_blocks(guide_html) or []
            slides = [{"type": "photo", "photo": {"type": "photo", "media": fid}, "caption": {"text": cap}}
                      for fid, cap in zip(ids, caps)]
            blocks = [{"type": "slideshow", "blocks": slides}] + text_blocks + rich_blocks.keyboard_to_button_blocks(markup)
            await bot._rich_call("sendRichMessage", {"chat_id": chat_id, "rich_message": {"blocks": blocks}})
            return True
        except (BadRequest, rich_blocks.UnsupportedButton) as e:
            _state["skip"].add("blocks")
            logger.warning("Tutorial: el carrusel en bloques no se aceptó (%s); se prueba en HTML.", e)

    if rich_bot.is_enabled() and "html" not in _state["skip"]:
        try:
            slides = "".join(f'<img src="tg://photo?id=s{n}"/>' for n in range(1, COUNT + 1))
            payload = {
                "chat_id": chat_id,
                "rich_message": {
                    "html": f"<tg-slideshow>{slides}</tg-slideshow>{guide_html}",
                    "media": [{"id": f"s{n}", "media": {"type": "photo", "media": fid}}
                              for n, fid in enumerate(ids, 1)],
                },
            }
            if markup is not None:
                payload["reply_markup"] = markup.to_dict()
            await bot._rich_call("sendRichMessage", payload)
            return True
        except BadRequest as e:
            _state["skip"].add("html")
            logger.warning("Tutorial: el carrusel en HTML no se aceptó (%s); se envía como álbum.", e)

    try:
        await bot.send_media_group(chat_id, [InputMediaPhoto(fid, caption=cap)
                                             for fid, cap in zip(ids, caps)])
    except TelegramError as e:
        logger.warning("Tutorial: no se pudo enviar el álbum (%s).", e)
        return False
    await bot.send_message(chat_id, guide_html, parse_mode="HTML", reply_markup=markup)
    return True
