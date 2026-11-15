import asyncio
import json
import os
import re
import sys
from pathlib import Path

try:
    import yt_dlp
    HAVE_YTDLP = True
except ImportError:
    yt_dlp = None
    HAVE_YTDLP = False

import filemanager

YTDLP_PLATFORMS = (
    "youtube.com", "youtu.be", "tiktok.com", "twitter.com", "x.com",
    "instagram.com", "twitch.tv", "vimeo.com", "reddit.com", "facebook.com",
    "fb.watch", "dailymotion.com", "threads.net", "bilibili.com", "vk.com",
    "pinterest.com", "pin.it", "streamable.com", "bsky.app",
)


def is_ytdlp_url(url: str) -> bool:
    if not url or not url.startswith(("http://", "https://")):
        return False
    lower = url.lower()
    return any(p in lower for p in YTDLP_PLATFORMS)


def _format_size(bytes_val: int | float | None) -> str:
    if not bytes_val or bytes_val <= 0:
        return "~?"
    return f"~{filemanager.human_size(bytes_val)}"


def extract_video_info(url: str) -> dict:
    info = None

    if HAVE_YTDLP:
        try:
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "socket_timeout": 20,
                "retries": 10,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception:
            info = None

    if not info:
        try:
            import subprocess
            cmd = [
                sys.executable, "-m", "yt_dlp",
                "--no-colors",
                "--no-warnings",
                "--skip-download",
                "--dump-single-json",
                "--socket-timeout", "20",
                "--retries", "10",
                url,
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            if res.returncode == 0 and res.stdout.strip():
                info = json.loads(res.stdout)
        except Exception as e:
            pass

    if info and "entries" in info and info["entries"]:
        info = info["entries"][0]

    if not info:
        raise RuntimeError("No se pudo extraer información del enlace. Comprueba que el vídeo sea público y accesible.")

    title = info.get("title", "video")
    duration = info.get("duration") or 0
    duration_str = f"{int(duration // 60)}:{int(duration % 60):02d}" if duration else ""
    thumbnail = info.get("thumbnail")

    formats = info.get("formats", [])
    best_audio = None
    best_audio_size = 0

    for f in formats:
        if f.get("vcodec") == "none" and f.get("acodec") != "none":
            size = f.get("filesize") or f.get("filesize_approx") or 0
            if not size and duration and f.get("abr"):
                size = int((f["abr"] * 1000 / 8) * duration)
            if size > best_audio_size or best_audio is None:
                best_audio = f
                best_audio_size = size

    target_heights = [1080, 720, 480, 360]
    height_buckets = {h: None for h in target_heights}

    for f in formats:
        h = f.get("height") or 0
        w = f.get("width") or 0
        eff_h = min(h, w) if (h > w and w > 0) else h
        if not eff_h:
            continue
        for th in target_heights:
            if eff_h >= th and (eff_h - th) <= 80:
                cur = height_buckets[th]
                f_size = f.get("filesize") or f.get("filesize_approx") or 0
                if not f_size and duration and f.get("tbr"):
                    f_size = int((f["tbr"] * 1000 / 8) * duration)

                if cur is None or (f_size and f_size > cur.get("size", 0)):
                    height_buckets[th] = {
                        "format_id": f["format_id"],
                        "height": eff_h,
                        "ext": f.get("ext", "mp4"),
                        "size": f_size,
                        "has_audio": f.get("acodec") != "none",
                    }

    available_options = []
    for th in target_heights:
        data = height_buckets[th]
        if data:
            total_size = data["size"]
            if not data["has_audio"] and best_audio:
                total_size += best_audio_size
                fmt_spec = f"{data['format_id']}+{best_audio['format_id']}/bestvideo[height<={th}]+bestaudio/best[height<={th}]/best"
            else:
                fmt_spec = f"{data['format_id']}/bestvideo[height<={th}]+bestaudio/best[height<={th}]/best"

            available_options.append({
                "label": f"🎬 {th}p ({_format_size(total_size)})",
                "quality": f"{th}p",
                "format_spec": fmt_spec,
                "size_bytes": total_size,
                "is_audio": False,
            })

    if not available_options:
        v_formats = [f for f in formats if f.get("vcodec") != "none"]
        if v_formats:
            v_formats.sort(key=lambda f: (f.get("height") or 0, f.get("filesize") or 0), reverse=True)
            best_v = v_formats[0]
            v_size = best_v.get("filesize") or best_v.get("filesize_approx") or 0
            h_lbl = f"{best_v.get('height')}p" if best_v.get('height') else "Mejor Calidad"
            available_options.append({
                "label": f"🎬 {h_lbl} ({_format_size(v_size)})",
                "quality": h_lbl,
                "format_spec": "bestvideo+bestaudio/best",
                "size_bytes": v_size,
                "is_audio": False,
            })
        else:
            available_options.append({
                "label": "🎬 Mejor Calidad Disponible",
                "quality": "best",
                "format_spec": "bestvideo+bestaudio/best",
                "size_bytes": 0,
                "is_audio": False,
            })

    audio_spec = "bestaudio/best"
    available_options.append({
        "label": f"🎵 Solo Audio MP3 ({_format_size(best_audio_size)})",
        "quality": "audio",
        "format_spec": audio_spec,
        "size_bytes": best_audio_size,
        "is_audio": True,
    })

    return {
        "title": title,
        "duration": duration,
        "duration_str": duration_str,
        "thumbnail": thumbnail,
        "options": available_options,
    }


async def download_video(
    url: str,
    format_spec: str,
    dest_dir: str,
    is_audio: bool = False,
    progress_callback = None,
) -> str:
    os.makedirs(dest_dir, exist_ok=True)
    out_template = os.path.join(dest_dir, "%(title).200B.%(ext)s")

    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--no-colors",
        "--no-warnings",
        "--newline",
        "--no-playlist",
        "--continue",
        "--socket-timeout", "20",
        "--retries", "10",
        "--fragment-retries", "10",
        "--file-access-retries", "5",
        "-o", out_template,
        "--progress-template", "PROGRESS:%(progress.downloaded_bytes)s:%(progress.total_bytes|progress.total_bytes_estimate)s:%(progress.speed)s",
        "--print", "after_move:filepath",
        "--print", "filename",
    ]

    if is_audio:
        cmd.extend(["-x", "--audio-format", "mp3", "--audio-quality", "192K"])
        if format_spec and format_spec not in ("bestaudio/best", "audio"):
            cmd.extend(["-f", format_spec])
        else:
            cmd.extend(["-f", "bestaudio/best"])
    else:
        if format_spec:
            cmd.extend(["-f", format_spec])

    cmd.append(url)

    files_before = set(os.listdir(dest_dir)) if os.path.exists(dest_dir) else set()

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    reported_paths = []
    stderr_lines = []

    async def read_stdout():
        while True:
            line_bytes = await proc.stdout.readline()
            if not line_bytes:
                break
            line = line_bytes.decode("utf-8", errors="ignore").strip()
            if line.startswith("PROGRESS:"):
                parts = line.split(":")
                if len(parts) >= 4 and progress_callback:
                    try:
                        d_bytes = int(float(parts[1])) if parts[1] != "NA" else 0
                        t_bytes = int(float(parts[2])) if parts[2] != "NA" else 0
                        speed = float(parts[3]) if parts[3] != "NA" else 0.0
                        if asyncio.iscoroutinefunction(progress_callback):
                            await progress_callback(d_bytes, t_bytes, speed)
                        else:
                            res = progress_callback(d_bytes, t_bytes, speed)
                            if asyncio.iscoroutine(res):
                                await res
                    except Exception:
                        pass
            elif os.path.isabs(line) and not line.endswith((".part", ".ytdl")):
                reported_paths.append(line)

    async def read_stderr():
        while True:
            line_bytes = await proc.stderr.readline()
            if not line_bytes:
                break
            line = line_bytes.decode("utf-8", errors="ignore").strip()
            if line:
                stderr_lines.append(line)

    await asyncio.gather(read_stdout(), read_stderr())
    rc = await proc.wait()

    if rc != 0:
        err_msg = "\n".join(stderr_lines[-5:]) if stderr_lines else f"Código de salida {rc}"
        if "ERROR:" in err_msg:
            err_msg = err_msg.split("ERROR:", 1)[1].strip()
        raise RuntimeError(f"Fallo en descarga: {err_msg}")

    for p in reversed(reported_paths):
        if os.path.exists(p):
            return p

    if is_audio:
        for p in reversed(reported_paths):
            base, _ = os.path.splitext(p)
            mp3_p = f"{base}.mp3"
            if os.path.exists(mp3_p):
                return mp3_p

    files_after = set(os.listdir(dest_dir)) if os.path.exists(dest_dir) else set()
    new_files = [
        os.path.join(dest_dir, f)
        for f in (files_after - files_before)
        if not f.endswith((".part", ".ytdl"))
    ]
    if new_files:
        new_files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return new_files[0]

    if reported_paths:
        return reported_paths[0]

    raise RuntimeError("La descarga finalizó pero no se localizó el archivo generado en el NAS.")
