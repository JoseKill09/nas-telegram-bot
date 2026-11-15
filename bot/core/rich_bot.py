import html
import logging
import os
import re
import time

from telegram import InlineKeyboardMarkup, Message
from telegram.error import BadRequest, Forbidden, NetworkError, TimedOut
from telegram.ext import ExtBot

import i18n
import rich_blocks

try:
    from telegram.error import EndPointNotFound
except Exception:
    EndPointNotFound = None

try:
    from telegram._utils.defaultvalue import DefaultValue
except Exception:
    DefaultValue = None

logger = logging.getLogger(__name__)

RICH_ENABLED_BY_ENV = os.getenv("RICH_MESSAGES", "1").strip() not in ("0", "false", "no", "off")

_state = {"disabled": not RICH_ENABLED_BY_ENV, "buttons_disabled": not RICH_ENABLED_BY_ENV, "warned": set(),
          "button_fails": 0, "buttons_paused_until": 0.0}

# Embedded buttons are never switched off for good. After this many CONSECUTIVE rejections that look
# button-related they pause for BUTTON_PAUSE_SECONDS (classic keyboard meanwhile) and then retry by themselves.
# Any other rejection only affects that one message.
BUTTON_FAIL_LIMIT = 3
BUTTON_PAUSE_SECONDS = 600
_BUTTON_ERR_HINTS = ("button", "reply_markup", "keyboard", "callback", "inline", "url invalid", "data invalid", "web app")

def set_enabled(value: bool) -> None:
    _state["disabled"] = not value
    _state["buttons_disabled"] = not value
    _state["button_fails"] = 0
    _state["buttons_paused_until"] = 0.0


def _buttons_paused() -> bool:
    return time.monotonic() < _state["buttons_paused_until"]


def _describe(blocks_content: dict | None, markup) -> str:
    """Diagnostic summary of a rejected message WITHOUT its content: block types and the screen (1st callback)."""
    types = []
    for b in (blocks_content or {}).get("blocks", []):
        t = b.get("type", "?")
        if types and types[-1][0] == t:
            types[-1][1] += 1
        else:
            types.append([t, 1])
    summary = ",".join(f"{t}×{n}" if n > 1 else t for t, n in types) or "-"
    screen = "-"
    if isinstance(markup, InlineKeyboardMarkup):
        for row in markup.inline_keyboard:
            for btn in row:
                if isinstance(getattr(btn, "callback_data", None), str):
                    screen = btn.callback_data[:40]
                    break
            if screen != "-":
                break
    return f"bloques=[{summary}] pantalla≈{screen}"


def is_enabled() -> bool:
    return not _state["disabled"]


RICH_MAX_LEN = 32768

_BLOCK_TAG_RE = re.compile(
    r"<\s*(p|h[1-6]|table|ul|ol|hr|details|tg-thinking|footer)\b", re.IGNORECASE
)
_LEGACY_BLOCK_RE = re.compile(
    r"(<blockquote[^>]*>.*?</blockquote>|<pre[^>]*>.*?</pre>)", re.IGNORECASE | re.DOTALL
)


def _val(v):
    if DefaultValue is not None and isinstance(v, DefaultValue):
        return DefaultValue.get_value(v)
    return v


def is_rich_blocks(text: str) -> bool:
    return bool(_BLOCK_TAG_RE.search(text or ""))


def _paragraphs(text: str) -> list[str]:
    out = []
    for p in re.split(r"\n\s*\n", text):
        p = p.strip("\n")
        if p.strip():
            out.append("<p>" + "<br/>".join(p.split("\n")) + "</p>")
    return out


def legacy_to_rich(text: str, parse_mode) -> str:
    text = text or ""
    if not parse_mode:
        return "".join(_paragraphs(html.escape(text))) or "<p>&#8203;</p>"
    blocks = []
    for part in _LEGACY_BLOCK_RE.split(text):
        if not part:
            continue
        low = part[:12].lower()
        if low.startswith("<blockquote"):
            inner = re.sub(r"^<blockquote[^>]*>|</blockquote>$", "", part.strip(), flags=re.I)
            blocks.append("<blockquote>" + "<br/>".join(inner.strip("\n").split("\n")) + "</blockquote>")
        elif low.startswith("<pre"):
            blocks.append(part.strip())
        else:
            blocks.extend(_paragraphs(part))
    return "".join(blocks) or "<p>&#8203;</p>"


def rich_to_legacy(text: str) -> str:
    t = text or ""
    t = re.sub(r"<\s*br\s*/?\s*>", "\n", t, flags=re.I)
    t = re.sub(r"<\s*hr\s*/?\s*>", "\n──────────\n", t, flags=re.I)
    t = re.sub(r"<\s*h[1-6][^>]*>(.*?)<\s*/\s*h[1-6]\s*>", r"\n<b>\1</b>\n", t, flags=re.I | re.S)
    t = re.sub(r"<\s*summary[^>]*>(.*?)<\s*/\s*summary\s*>", r"\n<b>\1</b>\n", t, flags=re.I | re.S)
    t = re.sub(r"<\s*/?\s*details[^>]*>", "\n", t, flags=re.I)
    t = re.sub(r"<\s*caption[^>]*>(.*?)<\s*/\s*caption\s*>", r"<i>\1</i>\n", t, flags=re.I | re.S)
    t = re.sub(r"<\s*/\s*t[dh]\s*>\s*(?=<\s*t[dh])", " · ", t, flags=re.I)
    t = re.sub(r"<\s*t[dh][^>]*>", "", t, flags=re.I)
    t = re.sub(r"<\s*/\s*t[dh]\s*>", "", t, flags=re.I)
    t = re.sub(r"<\s*/\s*tr\s*>", "\n", t, flags=re.I)
    t = re.sub(r"<\s*/?\s*(table|thead|tbody|tr)[^>]*>", "", t, flags=re.I)
    t = re.sub(r"<\s*li[^>]*>", "• ", t, flags=re.I)
    t = re.sub(r"<\s*/\s*li\s*>", "\n", t, flags=re.I)
    t = re.sub(r"<\s*/?\s*(ul|ol)[^>]*>", "\n", t, flags=re.I)
    t = re.sub(r"<\s*p[^>]*>", "", t, flags=re.I)
    t = re.sub(r"<\s*/\s*p\s*>", "\n\n", t, flags=re.I)
    t = re.sub(r"<\s*/?\s*(footer|tg-thinking)[^>]*>", "", t, flags=re.I)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()[:4096]


def _to_rich_html(text: str, parse_mode) -> str | None:
    if _state["disabled"]:
        return None
    pm = (str(parse_mode).upper() if parse_mode else None)
    if pm not in (None, "HTML"):
        return None
    rich = text if (pm == "HTML" and is_rich_blocks(text)) else legacy_to_rich(text, parse_mode)
    if len(rich) > RICH_MAX_LEN:
        return None
    return rich


def _warn_once(key: str, msg: str, *args):
    if key not in _state["warned"]:
        _state["warned"].add(key)
        logger.warning(msg, *args)


def _dedupe_markup(markup):
    """Drops repeated buttons (same text and action) and repeated 📖 guide buttons within one keyboard."""
    if not isinstance(markup, InlineKeyboardMarkup):
        return markup
    seen, seen_guide, rows, changed = set(), set(), [], False
    for row in markup.inline_keyboard:
        new_row = []
        for b in row:
            cb = getattr(b, "callback_data", None)
            key = (b.text, cb, getattr(b, "url", None))
            guide_key = b.text if (isinstance(cb, str) and cb.startswith("guide:")) else None
            if key in seen or (guide_key and guide_key in seen_guide):
                changed = True
                continue
            seen.add(key)
            if guide_key:
                seen_guide.add(guide_key)
            new_row.append(b)
        if new_row:
            rows.append(new_row)
    return InlineKeyboardMarkup(rows) if changed else markup


def _markup_ok(markup) -> bool:
    return markup is None or isinstance(markup, InlineKeyboardMarkup)


class RichExtBot(ExtBot):

    __slots__ = ()

    async def _rich_call(self, endpoint: str, payload: dict):
        result = await self.do_api_request(endpoint, api_kwargs=payload)
        if isinstance(result, dict):
            return Message.de_json(result, self)
        return result

    def _handle_rich_error(self, endpoint: str, err: Exception, buttons: bool = False, info: str = "") -> bool:
        msg = str(err).lower().replace("_", " ")
        if EndPointNotFound is not None and isinstance(err, EndPointNotFound):
            _state["disabled"] = True
            _state["buttons_disabled"] = True
            logger.warning(
                "La API de Telegram no reconoce %s (%s). Rich Messages desactivados, "
                "se usa el formato clásico.", endpoint, err,
            )
            return True
        if any(s in msg for s in ("not modified", "message to edit not found",
                                  "message can't be edited", "chat not found")):
            return False
        if isinstance(err, (Forbidden, TimedOut)):
            return False
        if isinstance(err, BadRequest):
            if buttons:
                related = any(h in msg for h in _BUTTON_ERR_HINTS)
                paused = False
                if related:
                    _state["button_fails"] += 1
                    if _state["button_fails"] >= BUTTON_FAIL_LIMIT:
                        _state["buttons_paused_until"] = time.monotonic() + BUTTON_PAUSE_SECONDS
                        _state["button_fails"] = 0
                        paused = True
                logger.warning(
                    "Telegram rechazó un Rich Message con botones integrados en %s (%s; %s). "
                    "Este mensaje sale con botones normales%s.", endpoint, err, info or "-",
                    f"; botones integrados en pausa {BUTTON_PAUSE_SECONDS // 60} min tras {BUTTON_FAIL_LIMIT} fallos seguidos"
                    if paused else " (los integrados siguen activos)",
                )
            else:
                _warn_once(
                    f"{endpoint}:{msg[:60]}",
                    "Telegram rechazó un Rich Message en %s (%s). Se reenvía en formato clásico.",
                    endpoint, err,
                )
            return True
        return False

    def _blocks_payload(self, rich_html: str, reply_markup) -> dict | None:
        if _state["buttons_disabled"] or _buttons_paused() or not isinstance(reply_markup, InlineKeyboardMarkup):
            return None
        blocks = rich_blocks.html_to_blocks(rich_html)
        if not blocks:
            _warn_once("noblocks:" + _describe(None, reply_markup),
                       "No se pudo convertir un mensaje a bloques (%s); sale con botones normales.",
                       _describe(None, reply_markup))
            return None
        try:
            button_blocks = rich_blocks.keyboard_to_button_blocks(reply_markup)
        except rich_blocks.UnsupportedButton as e:
            _warn_once(f"unsupported:{e}", "El botón «%s» no se puede integrar; ese mensaje sale con botones normales.", e)
            return None
        except Exception:
            logger.warning("Error convirtiendo botones (%s); sale con botones normales.", _describe(None, reply_markup),
                           exc_info=True)
            return None
        if not button_blocks:
            return None
        return {"blocks": blocks + button_blocks}

    async def send_message(self, chat_id, text, parse_mode=None, *args, **kwargs):
        parse_mode = _val(parse_mode)
        text = i18n.tr(text)
        if kwargs.get("reply_markup") is not None:
            kwargs["reply_markup"] = _dedupe_markup(i18n.tr_markup(_val(kwargs["reply_markup"])))
        reply_markup = _val(kwargs.get("reply_markup"))
        simple_kwargs = {
            k for k, v in kwargs.items()
            if _val(v) not in (None, False) and k not in (
                "reply_markup", "disable_notification", "protect_content", "message_thread_id",
                "reply_parameters", "read_timeout", "write_timeout", "connect_timeout",
                "pool_timeout", "api_kwargs", "allow_sending_without_reply", "reply_to_message_id",
            )
        }
        rich = None if (args or simple_kwargs or not _markup_ok(reply_markup)) else _to_rich_html(text, parse_mode)

        if rich is not None:
            extra = {}
            for k in ("disable_notification", "protect_content", "message_thread_id"):
                v = _val(kwargs.get(k))
                if v not in (None, False):
                    extra[k] = v
            rp = _val(kwargs.get("reply_parameters"))
            if rp is not None:
                extra["reply_parameters"] = rp.to_dict()
            elif _val(kwargs.get("reply_to_message_id")):
                extra["reply_parameters"] = {"message_id": _val(kwargs.get("reply_to_message_id"))}

            blocks_content = self._blocks_payload(rich, reply_markup)
            if blocks_content is not None:
                try:
                    res = await self._rich_call(
                        "sendRichMessage", {"chat_id": chat_id, "rich_message": blocks_content, **extra}
                    )
                    _state["button_fails"] = 0
                    return res
                except (BadRequest, Forbidden, TimedOut, NetworkError) as e:
                    if not self._handle_rich_error("sendRichMessage", e, buttons=True,
                                                   info=_describe(blocks_content, reply_markup)):
                        raise

            payload = {"chat_id": chat_id, "rich_message": {"html": rich}, **extra}
            if reply_markup is not None:
                payload["reply_markup"] = reply_markup.to_dict()
            try:
                return await self._rich_call("sendRichMessage", payload)
            except (BadRequest, Forbidden, TimedOut, NetworkError) as e:
                if not self._handle_rich_error("sendRichMessage", e):
                    raise
            text = rich_to_legacy(rich)
            parse_mode = "HTML"
        elif parse_mode and str(parse_mode).upper() == "HTML" and is_rich_blocks(text):
            text = rich_to_legacy(text)

        return await super().send_message(chat_id, text, parse_mode, *args, **kwargs)

    async def edit_message_text(self, text, chat_id=None, message_id=None,
                                inline_message_id=None, parse_mode=None, *args, **kwargs):
        parse_mode = _val(parse_mode)
        text = i18n.tr(text)
        if kwargs.get("reply_markup") is not None:
            kwargs["reply_markup"] = _dedupe_markup(i18n.tr_markup(_val(kwargs["reply_markup"])))
        reply_markup = _val(kwargs.get("reply_markup"))
        extra_kwargs = {
            k for k, v in kwargs.items()
            if _val(v) not in (None, False) and k not in (
                "reply_markup", "read_timeout", "write_timeout", "connect_timeout",
                "pool_timeout", "api_kwargs", "disable_web_page_preview",
            )
        }
        can_rich = not (args or extra_kwargs or inline_message_id or not chat_id or not message_id
                        or not _markup_ok(reply_markup))
        rich = _to_rich_html(text, parse_mode) if can_rich else None

        if rich is not None:
            blocks_content = self._blocks_payload(rich, reply_markup)
            if blocks_content is not None:
                try:
                    res = await self._rich_call(
                        "editMessageText",
                        {"chat_id": chat_id, "message_id": message_id, "rich_message": blocks_content},
                    )
                    _state["button_fails"] = 0
                    return res
                except (BadRequest, Forbidden, TimedOut, NetworkError) as e:
                    if not self._handle_rich_error("editMessageText", e, buttons=True,
                                                   info=_describe(blocks_content, reply_markup)):
                        raise

            payload = {"chat_id": chat_id, "message_id": message_id, "rich_message": {"html": rich}}
            if reply_markup is not None:
                payload["reply_markup"] = reply_markup.to_dict()
            try:
                return await self._rich_call("editMessageText", payload)
            except (BadRequest, Forbidden, TimedOut, NetworkError) as e:
                if not self._handle_rich_error("editMessageText", e):
                    raise
            text = rich_to_legacy(rich)
            parse_mode = "HTML"
        elif parse_mode and str(parse_mode).upper() == "HTML" and is_rich_blocks(text):
            text = rich_to_legacy(text)

        return await super().edit_message_text(
            text, chat_id, message_id, inline_message_id, parse_mode, *args, **kwargs
        )


def _translated(name):
    async def method(self, *args, **kwargs):
        for key in ("text", "caption"):
            if isinstance(kwargs.get(key), str):
                kwargs[key] = i18n.tr(kwargs[key])
        if kwargs.get("reply_markup") is not None:
            kwargs["reply_markup"] = i18n.tr_markup(_val(kwargs["reply_markup"]))
        return await getattr(super(RichExtBot, self), name)(*args, **kwargs)

    method.__name__ = name
    return method


for _name in (
    "answer_callback_query", "send_photo", "send_document", "send_video", "send_audio",
    "send_animation", "edit_message_caption", "edit_message_reply_markup",
):
    setattr(RichExtBot, _name, _translated(_name))
