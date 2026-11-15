import base64
import hashlib
import io
import json
import os
import zipfile
from datetime import datetime

import config
import db
from i18n import L

MAGIC = b"NASBAK1\n"
FORMAT = 1

GROUP_ORDER = ["settings", "folders", "sources", "rules", "users", "history", "channel", "tokens", "userbot"]

PRESETS = {
    "light": ["settings", "folders", "sources", "rules"],
    "standard": ["settings", "folders", "sources", "rules", "users"],
    "full": list(GROUP_ORDER),
}

SECRET_EXACT = {
    "cfg_API_ID", "cfg_API_HASH", "cfg_GOOGLE_CLIENT_ID", "cfg_GOOGLE_CLIENT_SECRET",
    "google_email", "tr_user", "qb_user", "bk_key", "prowlarr_key",
}


def info() -> dict:
    return {
        "settings": ("⚙️", L("Ajustes generales", "General settings"),
                     L("Idioma, límites, notificaciones, espacio en disco, texto enriquecido, clientes y proveedores (sin tokens).",
                       "Language, limits, notifications, disk space, rich text, clients and providers (no tokens).")),
        "folders": ("📁", L("Carpetas", "Folders"), L("Las carpetas de descarga configuradas.", "The configured download folders.")),
        "sources": ("🔎", L("Buscadores", "Search sources"),
                    L("Buscadores añadidos, eliminados, activos y sus espejos.", "Added, removed and enabled search sources and mirrors.")),
        "rules": ("🧭", L("Reglas de destino", "Destination rules"), L("Todas tus reglas de destino.", "All your destination rules.")),
        "users": ("👥", L("Usuarios autorizados", "Authorized users"), L("Lista de usuarios con acceso al bot.", "Users who can use the bot.")),
        "history": ("🕘", L("Historial", "History"), L("Tareas y lotes de descargas.", "Download tasks and batches.")),
        "channel": ("📡", L("Índice del canal", "Channel index"), L("Archivos ya copiados al canal del Userbot.", "Files already copied to the Userbot channel.")),
        "tokens": ("🔑", L("Tokens y credenciales", "Tokens and credentials"),
                   L("Real-Debrid, TorBox, TMDB, Google, contraseñas de clientes, API ID/Hash. ⚠️ Sensible.",
                     "Real-Debrid, TorBox, TMDB, Google, client passwords, API ID/Hash. ⚠️ Sensitive.")),
        "userbot": ("🤖", L("Sesión del Userbot", "Userbot session"),
                    L("Permite entrar en tu cuenta de Telegram sin volver a iniciar sesión. ⚠️ Muy sensible.",
                      "Lets the bot access your Telegram account without logging in again. ⚠️ Very sensitive.")),
    }


def is_secret(key: str) -> bool:
    return key in SECRET_EXACT or key.endswith(("_token", "_pass", "_secret", "_refresh_token", "_access_token")) \
        or key.startswith("google_")


def group_of(key: str) -> str:
    if is_secret(key):
        return "tokens"
    if key == "cfg_FOLDERS":
        return "folders"
    if key.startswith("src_"):
        return "sources"
    if key.startswith("rules_"):
        return "rules"
    return "settings"


async def get_key(create: bool = True) -> str | None:
    key = await db.get_setting("bk_key")
    if not key and create:
        import secrets
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        key = "-".join("".join(secrets.choice(alphabet) for _ in range(5)) for _ in range(5))
        await db.set_setting("bk_key", key)
    return key


async def build(groups: list[str], password: str | None = None) -> tuple[bytes, str]:
    password = password or await get_key()
    groups = [g for g in GROUP_ORDER if g in groups]
    raw = await db.dump_settings()
    data = {"settings": {k: v for k, v in raw.items() if group_of(k) in groups}, "tables": {}}
    counts = {}
    for g in groups:
        counts[g] = sum(1 for k in raw if group_of(k) == g)
    table_map = {"users": "authorized_users", "history": None, "channel": "channel_files", "userbot": "userbot_session"}
    for g in groups:
        if g == "history":
            data["tables"]["tasks"] = await db.dump_table("tasks")
            data["tables"]["batches"] = await db.dump_table("batches")
            counts[g] = len(data["tables"]["tasks"])
        elif table_map.get(g):
            rows = await db.dump_table(table_map[g])
            data["tables"][table_map[g]] = rows
            counts[g] = len(rows)
    manifest = {
        "format": FORMAT, "app_version": config.VERSION, "created": datetime.now().isoformat(timespec="seconds"),
        "groups": groups, "counts": counts, "encrypted": True,
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, indent=2))
        z.writestr("data.json", json.dumps(data, ensure_ascii=False))
    payload = buf.getvalue()
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    return encrypt(payload, password), f"nas-bot-backup-{stamp}.nasbak"


def _key(password: str, salt: bytes) -> bytes:
    return base64.urlsafe_b64encode(hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 300_000, 32))


def encrypt(payload: bytes, password: str) -> bytes:
    from cryptography.fernet import Fernet
    salt = os.urandom(16)
    return MAGIC + salt + Fernet(_key(password, salt)).encrypt(payload)


class BackupError(Exception):
    pass


def is_encrypted(blob: bytes) -> bool:
    return blob.startswith(MAGIC)


def decrypt(blob: bytes, password: str) -> bytes:
    from cryptography.fernet import Fernet, InvalidToken
    salt = blob[len(MAGIC):len(MAGIC) + 16]
    try:
        return Fernet(_key(password, salt)).decrypt(blob[len(MAGIC) + 16:])
    except InvalidToken:
        raise BackupError(L("Contraseña incorrecta.", "Wrong password."))


def read(blob: bytes, password: str | None = None) -> tuple[dict, dict]:
    if is_encrypted(blob):
        if not password:
            raise BackupError(L("La copia está cifrada: falta la contraseña.", "The backup is encrypted: password required."))
        blob = decrypt(blob, password)
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            manifest = json.loads(z.read("manifest.json"))
            data = json.loads(z.read("data.json"))
    except (zipfile.BadZipFile, KeyError, ValueError):
        raise BackupError(L("El archivo no es una copia de seguridad válida.", "The file is not a valid backup."))
    if manifest.get("format") != FORMAT:
        raise BackupError(L("Formato de copia no compatible.", "Unsupported backup format."))
    return manifest, data


async def restore(manifest: dict, data: dict, groups: list[str]) -> dict:
    done = {}
    settings = data.get("settings", {})
    for g in groups:
        if g not in manifest.get("groups", []):
            continue
        if g in ("settings", "folders", "sources", "rules", "tokens"):
            keys = [k for k in settings if group_of(k) == g]
            if g in ("sources", "rules"):
                for k in [k for k in (await db.dump_settings()) if group_of(k) == g and k not in settings]:
                    await db.delete_setting(k)
            for k in keys:
                await db.set_setting(k, settings[k])
            done[g] = len(keys)
        elif g == "users":
            done[g] = await db.replace_table("authorized_users", data["tables"].get("authorized_users", []))
        elif g == "history":
            done[g] = await db.replace_table("tasks", data["tables"].get("tasks", []))
            await db.replace_table("batches", data["tables"].get("batches", []))
        elif g == "channel":
            done[g] = await db.replace_table("channel_files", data["tables"].get("channel_files", []))
        elif g == "userbot":
            done[g] = await db.replace_table("userbot_session", data["tables"].get("userbot_session", []))
    await config.load_runtime()
    # Apply web app / tunnel changes right away (no restart needed)
    try:
        import tunnel
        import webserver
        import lan_access
        if await lan_access.server_needed() and not webserver.running():
            await webserver.start()
        await tunnel.autostart()
    except Exception:
        pass
    return done
