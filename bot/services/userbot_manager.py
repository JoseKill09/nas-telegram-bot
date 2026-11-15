from telethon import TelegramClient, utils
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
from telethon.tl.types import (
    InputFile,
    InputFileBig,
    DocumentAttributeFilename,
    DocumentAttributeVideo,
    DocumentAttributeAudio,
)

import asyncio
import logging
import os
import random
import shutil
from typing import Optional, Tuple

import config
import db
import fast_telethon

logger = logging.getLogger(__name__)

FAST_DOWNLOAD_MIN_SIZE = 8 * 1024 * 1024
MIN_CONNECTIONS, MAX_CONNECTIONS = 1, 40


async def get_max_connections() -> int:
    value = await db.get_setting("userbot_max_connections")
    if value is not None:
        try:
            return max(1, min(40, int(value)))
        except (TypeError, ValueError):
            pass
    return config.USERBOT_MAX_CONNECTIONS


async def _probe_media_metadata(file_path: str) -> dict:
    meta = {"duration": 0, "width": 0, "height": 0}
    ffprobe_bin = shutil.which("ffprobe")
    if not ffprobe_bin:
        return meta
    try:
        proc = await asyncio.create_subprocess_exec(
            ffprobe_bin,
            "-v", "error",
            "-show_entries", "format=duration:stream=width,height",
            "-of", "default=noprint_wrappers=1",
            file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
        for line in stdout.decode().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip()
                if k == "width":
                    try:
                        meta["width"] = int(v)
                    except ValueError:
                        pass
                elif k == "height":
                    try:
                        meta["height"] = int(v)
                    except ValueError:
                        pass
                elif k == "duration":
                    try:
                        meta["duration"] = int(float(v))
                    except ValueError:
                        pass
    except Exception as e:
        logger.debug("ffprobe metadata no disponible para %s: %s", file_path, e)
    return meta


_VIDEO_EXTS_FOR_THUMB = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".ts"}
_IMAGE_EXTS_FOR_THUMB = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".heic", ".tiff", ".tif"}


async def _generate_thumbnail(file_path: str) -> str | None:
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        return None
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in _VIDEO_EXTS_FOR_THUMB and ext not in _IMAGE_EXTS_FOR_THUMB:
        return None

    out_path = f"{file_path}.thumb.jpg"
    args = [ffmpeg_bin, "-y", "-loglevel", "error"]
    if ext in _VIDEO_EXTS_FOR_THUMB:
        args += ["-ss", "3", "-i", file_path, "-frames:v", "1"]
    else:
        args += ["-i", file_path, "-frames:v", "1"]
    args += ["-vf", "scale='min(320,iw)':'-2'", out_path]

    try:
        proc = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.communicate(), timeout=20)
        if proc.returncode == 0 and os.path.isfile(out_path) and os.path.getsize(out_path) > 0:
            return out_path
    except Exception as e:
        logger.debug("No se pudo generar miniatura para %s: %s", file_path, e)
    if ext in _VIDEO_EXTS_FOR_THUMB:
        try:
            proc = await asyncio.create_subprocess_exec(
                ffmpeg_bin, "-y", "-loglevel", "error", "-i", file_path, "-frames:v", "1",
                "-vf", "scale='min(320,iw)':'-2'", out_path,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.communicate(), timeout=20)
            if proc.returncode == 0 and os.path.isfile(out_path) and os.path.getsize(out_path) > 0:
                return out_path
        except Exception:
            pass
    return None


class UserbotManager:

    def __init__(self, api_id, api_hash, get_session_cb, set_session_cb, set_meta_cb=None, clear_meta_cb=None):
        self.api_id = api_id
        self.api_hash = api_hash
        self._get_session_cb = get_session_cb
        self._set_session_cb = set_session_cb
        self._set_meta_cb = set_meta_cb
        self._clear_meta_cb = clear_meta_cb
        self.client: TelegramClient | None = None
        self._phone = None
        self._phone_code_hash = None
        self.active_uploads = {}

    async def load_existing(self) -> bool:
        session_str = await self._get_session_cb()
        if not session_str:
            return False
        try:
            client = TelegramClient(StringSession(session_str), self.api_id, self.api_hash)
            await asyncio.wait_for(client.connect(), timeout=10.0)
            if await client.is_user_authorized():
                self.client = client
                return True
            await client.disconnect()
        except Exception:
            pass
        return False

    async def get_max_connections(self) -> int:
        return await get_max_connections()

    async def set_max_connections(self, value: int) -> int:
        value = max(MIN_CONNECTIONS, min(MAX_CONNECTIONS, int(value)))
        await db.set_setting("userbot_max_connections", str(value))
        return value

    async def is_connected(self) -> bool:
        return bool(
            self.client
            and self.client.is_connected()
            and await self.client.is_user_authorized()
        )


    async def start_login(self, phone: str):
        self.client = TelegramClient(StringSession(), self.api_id, self.api_hash)
        await asyncio.wait_for(self.client.connect(), timeout=15.0)
        sent = await self.client.send_code_request(phone)
        self._phone = phone
        self._phone_code_hash = sent.phone_code_hash

    async def submit_code(self, code: str):
        await self.client.sign_in(phone=self._phone, code=code, phone_code_hash=self._phone_code_hash)
        await self._save_session()

    async def submit_password(self, password: str):
        await self.client.sign_in(password=password)
        await self._save_session()

    async def _save_session(self):
        session_str = self.client.session.save()
        await self._set_session_cb(session_str)
        if self._set_meta_cb:
            try:
                me = await self.client.get_me()
                await self._set_meta_cb(me.id, me.username, me.first_name)
            except Exception:
                pass
        self._phone = None
        self._phone_code_hash = None

    async def disconnect_and_forget(self):
        if self.client:
            try:
                await self.client.log_out()
            except Exception:
                pass
            self.client = None
        await self._set_session_cb(None)
        if self._clear_meta_cb:
            await self._clear_meta_cb()


    async def _get_message(self, chat_id, message_id):
        """get_messages que no falla si el chat aún no está en la caché de la sesión (p. ej. enlaces t.me/c/…)."""
        try:
            return await self.client.get_messages(chat_id, ids=message_id)
        except ValueError:
            from tg_links import _entity
            return await self.client.get_messages(await _entity(self.client, chat_id), ids=message_id)

    async def download_message_media(self, chat_id, message_id, dest_path, progress_callback=None):
        msg = await self._get_message(chat_id, message_id)
        if msg is None:
            raise RuntimeError("No se encontro el mensaje en el canal privado")
        return await self.client.download_media(msg, file=dest_path, progress_callback=progress_callback)

    async def download_message_media_fast(self, chat_id, message_id, dest_path, progress_callback=None):
        msg = await self._get_message(chat_id, message_id)
        if msg is None or not msg.file:
            raise RuntimeError("No se encontro el mensaje o no tiene un archivo descargable")

        document = msg.document or msg.media
        file_size = msg.file.size
        if not file_size or file_size < FAST_DOWNLOAD_MIN_SIZE:
            raise RuntimeError("Archivo demasiado pequeño para paralelizar")

        with open(dest_path, "wb") as out:
            await fast_telethon.download_file(
                self.client, document, out,
                progress_callback=progress_callback,
                connection_count=await get_max_connections(),
            )

        return dest_path


    def register_upload(
        self,
        upload_id: str,
        filename: str = "",
        total_size: int = 0,
        chat_id: int | str | None = None,
    ) -> asyncio.Event:
        cancel_event = asyncio.Event()
        self.active_uploads[upload_id] = {
            "cancel_event": cancel_event,
            "status": "uploading",
            "filename": filename,
            "total_size": total_size,
            "current_bytes": 0,
            "speed": 0.0,
            "chat_id": chat_id,
        }
        return cancel_event

    def update_upload_progress(self, upload_id: str, current: int, total: int, speed: float = 0.0):
        item = self.active_uploads.get(upload_id)
        if item:
            item["current_bytes"] = current
            item["total_size"] = total
            item["speed"] = speed

    def get_upload_info(self, upload_id: str) -> dict | None:
        return self.active_uploads.get(upload_id)

    def cancel_upload(self, upload_id: str) -> bool:
        item = self.active_uploads.get(upload_id)
        if item:
            item["cancel_event"].set()
            item["status"] = "cancelled"
            return True
        return False

    def unregister_upload(self, upload_id: str):
        self.active_uploads.pop(upload_id, None)

    async def upload_file_fast(
        self,
        file_path: str,
        progress_callback = None,
        cancel_event: asyncio.Event | None = None,
    ) -> InputFile | InputFileBig:
        if not self.client or not await self.is_connected():
            raise RuntimeError("El Userbot no está conectado")

        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

        file_size = os.path.getsize(file_path)
        if file_size == 0:
            raise ValueError("El archivo está vacío (0 bytes)")

        def _wrapped_progress(current, total):
            if cancel_event and cancel_event.is_set():
                raise asyncio.CancelledError("Subida cancelada por el usuario")
            if progress_callback:
                return progress_callback(current, total)
            return None

        with open(file_path, "rb") as f:
            try:
                return await fast_telethon.upload_file(
                    self.client, f,
                    progress_callback=_wrapped_progress,
                    connection_count=await get_max_connections(),
                )
            except asyncio.CancelledError:
                raise

    async def send_file_to_chat(
        self,
        chat_id: int | str,
        file_path: str,
        caption: str = "",
        progress_callback = None,
        cancel_event: asyncio.Event | None = None,
        is_audio: bool = False,
        is_video: bool = False,
        force_document: bool = False,
        thumb = None,
    ):
        auto_thumb_path = None
        try:
            if not self.client or not await self.is_connected():
                raise RuntimeError("El Userbot no está conectado")

            if not os.path.isfile(file_path):
                raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

            entity = None
            try:
                me = await self.client.get_me()
                if me and (chat_id == me.id or str(chat_id) == str(me.id)):
                    entity = "me"
            except Exception:
                pass

            if not entity:
                try:
                    entity = await self.client.get_input_entity(chat_id)
                except Exception:
                    try:
                        entity = await self.client.get_entity(chat_id)
                    except Exception:
                        entity = chat_id

            is_image = False
            if not force_document and not is_audio and not is_video:
                ext = os.path.splitext(file_path)[1].lower()
                video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".ts"}
                audio_exts = {".mp3", ".flac", ".wav", ".m4a", ".ogg", ".aac", ".wma", ".opus"}
                image_exts = {".jpg", ".jpeg", ".png", ".webp"}
                if ext in video_exts:
                    is_video = True
                elif ext in audio_exts:
                    is_audio = True
                elif ext in image_exts:
                    is_image = True
                else:
                    force_document = True

            filename = os.path.basename(file_path)

            if force_document and not thumb:
                thumb = await _generate_thumbnail(file_path)
                auto_thumb_path = thumb

            uploaded_handle = None
            try:
                uploaded_handle = await self.upload_file_fast(
                    file_path=file_path,
                    progress_callback=progress_callback,
                    cancel_event=cancel_event,
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning("Fallo en upload_file_fast, recurriendo al método estándar de Telethon: %s", e)
                uploaded_handle = None

            if uploaded_handle:
                attributes = []
                try:
                    attrs_result, _mime_type = utils.get_attributes(file_path, supports_streaming=is_video)
                    attributes = list(attrs_result) if attrs_result else []
                except Exception:
                    attributes = []

                has_filename = any(isinstance(a, DocumentAttributeFilename) for a in attributes)
                if not has_filename:
                    attributes.append(DocumentAttributeFilename(file_name=filename))

                if is_video and not force_document:
                    meta = await _probe_media_metadata(file_path)
                    has_video_attr = False
                    for a in attributes:
                        if isinstance(a, DocumentAttributeVideo):
                            has_video_attr = True
                            a.supports_streaming = True
                            if meta["duration"] and not getattr(a, "duration", 0):
                                a.duration = meta["duration"]
                            if meta["width"] and not getattr(a, "w", 0):
                                a.w = meta["width"]
                            if meta["height"] and not getattr(a, "h", 0):
                                a.h = meta["height"]
                    if not has_video_attr:
                        attributes.append(
                            DocumentAttributeVideo(
                                duration=meta["duration"],
                                w=meta["width"],
                                h=meta["height"],
                                supports_streaming=True,
                            )
                        )
                elif is_audio and not force_document:
                    meta = await _probe_media_metadata(file_path)
                    has_audio_attr = any(isinstance(a, DocumentAttributeAudio) for a in attributes)
                    if not has_audio_attr:
                        attributes.append(
                            DocumentAttributeAudio(
                                duration=meta["duration"],
                                title=os.path.splitext(filename)[0],
                            )
                        )

                kwargs = {
                    "caption": caption,
                    "attributes": attributes,
                    "force_document": force_document,
                }
                if is_video:
                    kwargs["supports_streaming"] = True
                if thumb and os.path.isfile(thumb):
                    kwargs["thumb"] = thumb

                try:
                    return await self.client.send_file(entity, uploaded_handle, **kwargs)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    raise RuntimeError(f"Error al enviar archivo con Userbot: {e}")

            async def _telethon_progress(current, total):
                if cancel_event and cancel_event.is_set():
                    raise asyncio.CancelledError("Subida cancelada por el usuario")
                if progress_callback:
                    if asyncio.iscoroutinefunction(progress_callback):
                        await progress_callback(current, total)
                    else:
                        res = progress_callback(current, total)
                        if asyncio.iscoroutine(res):
                            await res

            kwargs = {
                "caption": caption,
                "progress_callback": _telethon_progress,
                "force_document": force_document,
            }
            if is_video:
                kwargs["supports_streaming"] = True
            if thumb and os.path.isfile(thumb):
                kwargs["thumb"] = thumb

            try:
                return await self.client.send_file(entity, file_path, **kwargs)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                raise RuntimeError(f"Error al subir archivo con Userbot: {e}")

        finally:
            if auto_thumb_path:
                try:
                    os.remove(auto_thumb_path)
                except OSError:
                    pass
    async def find_file_in_channel(
        self, chat_id, filename: str, file_size: Optional[int] = None
    ) -> Optional[int]:
        if not await self.is_connected():
            return None
        try:
            entity = await self.client.get_input_entity(chat_id)
        except Exception:
            try:
                entity = await self.client.get_entity(chat_id)
            except Exception as e:
                logger.warning("No se pudo resolver la entidad %s para búsqueda: %s", chat_id, e)
                return None

        clean_name = os.path.basename(filename).strip()
        try:
            async for msg in self.client.iter_messages(entity, search=clean_name, limit=20):
                if not msg.media and not msg.file:
                    continue
                doc_name = getattr(msg.file, "name", None) or getattr(msg, "file_name", None)
                doc_size = getattr(msg.file, "size", None) or getattr(msg, "file_size", None)
                if not doc_name and msg.message:
                    for line in msg.message.splitlines():
                        if clean_name.lower() in line.lower():
                            doc_name = clean_name
                            break
                if doc_name and doc_name.lower() == clean_name.lower():
                    if file_size is not None and doc_size is not None:
                        if abs(doc_size - file_size) > 1024:
                            continue
                    return msg.id
        except Exception as e:
            logger.warning("Error al buscar archivo '%s' en canal %s: %s", clean_name, chat_id, e)
        return None
