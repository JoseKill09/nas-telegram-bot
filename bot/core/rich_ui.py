import html
import logging

from telegram import InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import BadRequest

logger = logging.getLogger(__name__)

HTML = ParseMode.HTML


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def header(icon: str, title: str) -> str:
    return f"{icon} <b>{esc(title)}</b>"


def kv(label: str, value, icon: str | None = None) -> str:
    prefix = f"{icon} " if icon else ""
    return f"{prefix}<b>{esc(label)}:</b> {esc(value)}"


def bar(pct: float, width: int = 14) -> str:
    filled = max(0, min(width, int(width * pct / 100)))
    return "█" * filled + "░" * (width - filled)


def build_text(icon: str, title: str, lines: list[str], footer: str | None = None) -> str:
    parts = [header(icon, title)]
    if lines:
        parts.append("")
        parts.extend(lines)
    if footer:
        parts.append("")
        parts.append(f"<i>{esc(footer)}</i>")
    return "\n".join(parts)


async def send_or_update(
    update_or_query,
    context,
    *,
    text: str,
    buttons: InlineKeyboardMarkup | None = None,
    image_url: str | None = None,
    force_new: bool = False,
):
    query = getattr(update_or_query, "callback_query", None) or (
        update_or_query if hasattr(update_or_query, "data") else None
    )
    message = query.message if query else getattr(update_or_query, "effective_message", update_or_query)
    chat_id = message.chat_id

    caption_mode_ok = image_url and len(text) <= 1024

    async def _send_fresh():
        if image_url and caption_mode_ok:
            try:
                return await context.bot.send_photo(
                    chat_id=chat_id, photo=image_url, caption=text, parse_mode=HTML, reply_markup=buttons
                )
            except BadRequest as e:
                logger.info("No se pudo enviar la imagen (%s), se envía como texto.", e)
        return await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=HTML, reply_markup=buttons)

    if force_new or not query:
        return await _send_fresh()

    is_photo_msg = bool(message.photo)
    try:
        if image_url and caption_mode_ok:
            if is_photo_msg:
                return await query.edit_message_caption(caption=text, parse_mode=HTML, reply_markup=buttons)
            sent = await _send_fresh()
            try:
                await message.delete()
            except Exception:
                pass
            return sent
        else:
            if is_photo_msg:
                sent = await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=HTML, reply_markup=buttons)
                try:
                    await message.delete()
                except Exception:
                    pass
                return sent
            return await query.edit_message_text(text=text, parse_mode=HTML, reply_markup=buttons)
    except BadRequest as e:
        if "message is not modified" in str(e).lower():
            return message
        logger.warning("send_or_update: fallo al editar, se reenvía: %s", e)
        return await _send_fresh()


def r_h(text: str, level: int = 3, icon: str | None = None) -> str:
    label = f"{icon} {esc(text)}" if icon else esc(text)
    return f"<h{level}>{label}</h{level}>"


def r_p(*lines: str) -> str:
    return "<p>" + "<br/>".join(l for l in lines if l is not None) + "</p>"


def r_hr() -> str:
    return "<hr/>"


def r_ul(items: list[str], ordered: bool = False) -> str:
    tag = "ol" if ordered else "ul"
    return f"<{tag}>" + "".join(f"<li>{i}</li>" for i in items) + f"</{tag}>"


def r_table(rows: list[list[str]], header: list[str] | None = None, caption: str | None = None) -> str:
    parts = ["<table bordered striped>"]
    if caption:
        parts.append(f"<caption>{caption}</caption>")
    if header:
        parts.append("<tr>" + "".join(f"<th>{c}</th>" for c in header) + "</tr>")
    for row in rows:
        parts.append("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>")
    parts.append("</table>")
    return "".join(parts)


def r_kv_table(pairs: list[tuple[str, str]]) -> str:
    return r_table([[f"<b>{esc(k)}</b>", v] for k, v in pairs])


def r_quote(text: str) -> str:
    return f"<blockquote>{text}</blockquote>"


def r_details(summary: str, body: str) -> str:
    return f"<details><summary>{summary}</summary>{body}</details>"


def r_footer(text: str) -> str:
    return f"<footer>{text}</footer>"


def rich(*blocks: str) -> str:
    return "".join(b for b in blocks if b)


def _human(n) -> str:
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def progress_card(title: str, icon: str, name: str, pct: float, total: float, speed: float,
                  eta: str | None = None, extra: list[tuple[str, str]] | None = None) -> str:
    from i18n import L
    pairs = [
        (L("Nombre", "Name"), esc(name)),
        (L("Progreso", "Progress"), f"<code>{bar(pct, 20)}</code> {pct:.1f}%"),
        (L("Tamaño", "Size"), f"{_human(total * pct / 100)} / {_human(total)}"),
        (L("Velocidad", "Speed"), f"{(speed or 0) / (1024 * 1024):.2f} MB/s"),
        ("ETA", esc(eta or "—")),
    ] + (extra or [])
    return rich(r_h(title, 3, icon), r_kv_table(pairs))
