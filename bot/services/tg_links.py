"""Telegram message links (t.me/…) downloaded with the connected userbot account.

Enlaces de mensajes de Telegram: se resuelven con la cuenta conectada como userbot (la tuya), así que
funcionan con chats privados, grupos y canales en los que estés, incluidos los que no permiten reenviar
(con tu cuenta puedes descargar lo que puedes ver). Cada archivo se convierte en una tarea «telegram»
normal: mismo menú de carpeta y misma descarga rápida que un archivo reenviado.

Formatos admitidos:
  https://t.me/<usuario_o_canal>/<id>          https://t.me/<usuario_o_canal>/<hilo>/<id>
  https://t.me/c/<id_interno>/<id>              https://t.me/c/<id_interno>/<hilo>/<id>
  https://telegram.me/…, ?single, ?comment=…    tg://privatepost?channel=…&post=…   tg://resolve?domain=…&post=…
"""
import mimetypes
import re
from urllib.parse import parse_qs, urlparse

_HOSTS = ("t.me", "telegram.me", "telegram.dog")
_RESERVED = {"joinchat", "addstickers", "addemoji", "share", "proxy", "socks", "setlanguage", "login", "invoice", "boost", "m"}


def parse(url: str):
    """-> (chat, message_id) donde chat es int (-100…) o str (@usuario); None si no es un enlace a un mensaje."""
    u = (url or "").strip()
    if u.startswith("tg://"):
        p = urlparse(u)
        q = parse_qs(p.query)
        if p.netloc == "privatepost" and q.get("channel") and q.get("post"):
            return int(f"-100{q['channel'][0]}"), int(q["post"][0])
        if p.netloc == "resolve" and q.get("domain") and q.get("post"):
            return q["domain"][0], int(q["post"][0])
        return None
    if not re.match(r"^https?://", u, re.I):
        u = "https://" + u
    p = urlparse(u)
    host = p.netloc.lower().removeprefix("www.")
    if host not in _HOSTS:
        return None
    parts = [x for x in p.path.split("/") if x]
    q = parse_qs(p.query)
    if q.get("comment") and q["comment"][0].isdigit():
        return None                                         # comentarios: no admitidos (necesitan el chat de discusión)
    if len(parts) >= 3 and parts[0] == "c" and parts[1].isdigit() and parts[-1].isdigit():
        return int(f"-100{parts[1]}"), int(parts[-1])
    if len(parts) >= 2 and parts[0].lower() not in _RESERVED and not parts[0].startswith("+") and parts[-1].isdigit():
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{3,31}", parts[0]):
            return parts[0], int(parts[-1])
    return None


def is_tg_link(text: str) -> bool:
    return parse(text) is not None


def find_links(text: str) -> list[str]:
    return [m.group(0) for m in re.finditer(r"(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me|telegram\.dog)/\S+|tg://\S+", text or "") if parse(m.group(0))]


def _name(msg) -> str:
    f = msg.file
    if f and f.name:
        return f.name
    ext = (f.ext if f else "") or (mimetypes.guess_extension(f.mime_type) if f and f.mime_type else "") or ""
    if ext == ".jpe":
        ext = ".jpg"
    base = re.sub(r"[\\/:*?\"<>|\n\r]+", " ", msg.message or "").strip()[:60]
    if not base:
        kind = "video" if msg.video else ("audio" if msg.audio else ("foto" if msg.photo else "archivo"))
        base = f"{kind}_{msg.date.strftime('%Y%m%d_%H%M%S') if msg.date else msg.id}"
    return base if base.lower().endswith(ext.lower()) else base + ext


async def _entity(client, chat):
    try:
        return await client.get_entity(chat)
    except ValueError:
        # chat numérico que el userbot aún no tiene en caché: se cargan sus chats una vez
        await client.get_dialogs()
        return await client.get_entity(chat)


async def resolve(manager, url: str) -> list[dict]:
    """Archivos del mensaje enlazado (si es un álbum, todos sus archivos).
    -> [{"chat_id": int, "message_id": int, "filename": str, "size": int}]"""
    ref = parse(url)
    if not ref:
        raise ValueError("Ese enlace no apunta a un mensaje de Telegram")
    if manager is None or not await manager.is_connected():
        raise RuntimeError("Para enlaces de Telegram hace falta tener conectada tu cuenta (userbot) en el bot")
    client = manager.client
    chat, mid = ref
    try:
        entity = await _entity(client, chat)
    except Exception:
        raise RuntimeError("Tu cuenta no tiene acceso a ese chat (¿estás dentro?)")
    msg = await client.get_messages(entity, ids=mid)
    if msg is None:
        raise RuntimeError("No encuentro ese mensaje (puede que se haya borrado o que no tengas acceso)")
    msgs = [msg]
    if msg.grouped_id:                                       # álbum: sus vecinos con el mismo grupo
        near = await client.get_messages(entity, ids=list(range(max(1, mid - 10), mid + 11)))
        msgs = [m for m in near if m and m.grouped_id == msg.grouped_id] or [msg]
    out = []
    for m in sorted(msgs, key=lambda x: x.id):
        if not m.file:
            continue
        out.append({"chat_id": int(m.chat_id), "message_id": int(m.id), "filename": _name(m), "size": int(m.file.size or 0)})
    if not out:
        raise RuntimeError("Ese mensaje no tiene ningún archivo descargable")
    return out
