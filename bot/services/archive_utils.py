import asyncio
import bz2
import gzip
import lzma
import os
import re
import shutil
import struct
import subprocess
import tarfile
import threading
import time
import zipfile
from pathlib import Path

ARCHIVE_EXTENSIONS = (
    ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz", ".tar",
    ".zip", ".rar", ".7z", ".gz", ".bz2", ".xz",
)

# pause after every 512 KB chunk: keeps the disk and CPU free for the rest of the NAS
THROTTLE_SECONDS = 0.001

_PASSWORD_HINTS = ("wrong password", "enter password", "data error in encrypted file", "bad password")


class PasswordRequiredError(Exception):
    pass


class WrongPasswordError(Exception):
    pass


def is_archive(filename: str) -> bool:
    name = (filename or "").lower()
    return any(name.endswith(ext) for ext in ARCHIVE_EXTENSIONS)


def archive_volumes(file_path: str) -> list[str]:
    path = Path(file_path)
    name = path.name
    patterns = []
    m = re.match(r"^(.*)\.part0*1\.rar$", name, re.I)
    if m:
        patterns.append(re.compile(rf"^{re.escape(m.group(1))}\.part\d+\.rar$", re.I))
    m = re.match(r"^(.*)\.(7z|zip)\.0*1$", name, re.I)
    if m:
        patterns.append(re.compile(rf"^{re.escape(m.group(1))}\.{m.group(2)}\.\d+$", re.I))
    m = re.match(r"^(.*)\.rar$", name, re.I)
    if m:
        patterns.append(re.compile(rf"^{re.escape(m.group(1))}\.r\d\d$", re.I))
    out = [str(path)]
    if patterns and path.parent.is_dir():
        for sibling in path.parent.iterdir():
            if sibling.is_file() and sibling != path and any(p.match(sibling.name) for p in patterns):
                out.append(str(sibling))
    return out


def archive_base_name(filename: str) -> str:
    lower = (filename or "").lower()
    for ext in ARCHIVE_EXTENSIONS:
        if lower.endswith(ext):
            return filename[: -len(ext)]
    return filename


def check_password_needed(file_path: str) -> bool:
    path = Path(file_path)
    if not path.is_file():
        return False
    name = path.name.lower()

    if name.endswith(".zip"):
        try:
            with zipfile.ZipFile(path) as zf:
                return any(z.flag_bits & 0x1 for z in zf.infolist())
        except Exception:
            return False

    if name.endswith((".7z", ".rar")):
        try:
            res = subprocess.run(
                _low_prio_cmd(["7z", "l", "-slt", "-mmt1", "-p ", str(path)]),
                capture_output=True, text=True, timeout=15,
            )
            output = (res.stdout + res.stderr).lower()
            return "encrypted = +" in output or any(hint in output for hint in _PASSWORD_HINTS)
        except Exception:
            return False

    return False


def get_uncompressed_size(file_path: str, password: str | None = None) -> int:
    path = Path(file_path)
    if not path.is_file():
        return 0
    name = path.name.lower()

    try:
        if name.endswith(".zip"):
            with zipfile.ZipFile(path) as zf:
                return sum(z.file_size for z in zf.infolist())

        if name.endswith((".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz", ".tar")):
            with tarfile.open(path, "r:*") as tf:
                return sum(m.size for m in tf.getmembers() if m.isfile())

        if name.endswith(".gz"):
            with open(path, "rb") as f:
                f.seek(-4, os.SEEK_END)
                return struct.unpack("<I", f.read(4))[0]

        if name.endswith((".7z", ".rar")):
            pwd_arg = f"-p{password}" if password else "-p "
            res = subprocess.run(
                _low_prio_cmd(["7z", "l", "-mmt1", pwd_arg, str(path)]),
                capture_output=True, text=True, timeout=30,
            )
            if res.returncode == 0:
                lines = res.stdout.strip().splitlines()
                for line in reversed(lines):
                    parts = line.strip().split()
                    if len(parts) >= 3 and parts[0].isdigit():
                        return int(parts[0])
                    match = re.search(r"(\d+)\s+\d+\s+files", line, re.IGNORECASE)
                    if match:
                        return int(match.group(1))

        return max(path.stat().st_size * 2, path.stat().st_size)
    except Exception:
        return path.stat().st_size if path.exists() else 0


def _safe_clean_dest(dest_dir: str, file_path: str):
    try:
        dest_p = Path(dest_dir).resolve()
        orig_p = Path(file_path).resolve()
        if dest_p == orig_p or dest_p in orig_p.parents:
            return
        if dest_p.exists() and dest_p.is_dir():
            shutil.rmtree(dest_p, ignore_errors=True)
    except Exception:
        pass


def _lower_priority():
    # run this thread at the lowest CPU priority so the NAS stays responsive
    try:
        os.setpriority(os.PRIO_PROCESS, threading.get_native_id(), 19)
    except Exception:
        pass


_IONICE_OK = None


def _check_ionice():
    global _IONICE_OK
    try:
        _IONICE_OK = bool(shutil.which("ionice")) and subprocess.run(
            ["ionice", "-c", "3", "true"], capture_output=True, timeout=5).returncode == 0
    except Exception:
        _IONICE_OK = False


def _low_prio_cmd(cmd: list[str]) -> list[str]:
    prefix = []
    if shutil.which("nice"):
        prefix += ["nice", "-n", "19"]
    if _IONICE_OK is None:
        _check_ionice()
    if _IONICE_OK:
        prefix += ["ionice", "-c", "3"]
    return prefix + cmd


def _throttle():
    time.sleep(THROTTLE_SECONDS)


def _copy_stream(source, target, state, total_size, progress_callback):
    while True:
        chunk = source.read(512 * 1024)
        if not chunk:
            break
        target.write(chunk)
        state["bytes"] += len(chunk)
        if progress_callback:
            progress_callback(state["bytes"], total_size)
        _throttle()


def _extract_python_sync(path: Path, name: str, dest: Path, password, total_size, progress_callback):
    """zip / tar / gz / bz2 / xz in a worker thread (never blocks the bot) at the lowest priority."""
    _lower_priority()
    state = {"bytes": 0}
    if name.endswith(".zip"):
        try:
            with zipfile.ZipFile(path) as zf:
                pwd = password.encode() if password else None
                for item in zf.infolist():
                    if item.is_dir():
                        zf.extract(item, dest, pwd=pwd)
                        continue
                    target_file = dest / item.filename
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(item, pwd=pwd) as source, open(target_file, "wb") as target:
                        _copy_stream(source, target, state, total_size, progress_callback)
        except RuntimeError as e:
            msg = str(e).lower()
            if "password" in msg or "encrypted" in msg:
                raise (WrongPasswordError() if password else PasswordRequiredError()) from e
            raise
    elif name.endswith((".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz", ".tar")):
        with tarfile.open(path, "r:*") as tf:
            for member in tf:
                tf.extract(member, dest)
                if member.isfile():
                    state["bytes"] += member.size
                    if progress_callback:
                        progress_callback(state["bytes"], total_size)
                    _throttle()
    else:
        opener = gzip.open if name.endswith(".gz") else bz2.open if name.endswith(".bz2") else lzma.open
        with opener(path, "rb") as f_in, open(dest / path.stem, "wb") as f_out:
            _copy_stream(f_in, f_out, state, total_size, progress_callback)


async def extract_archive_with_progress(
    file_path: str,
    dest_dir: str,
    password: str | None = None,
    progress_callback=None,
):
    path = Path(file_path)
    name = path.name.lower()
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)

    total_size = await asyncio.to_thread(get_uncompressed_size, file_path, password)
    extracted_bytes = 0

    try:
        if name.endswith((".7z", ".rar")):
            pwd_arg = f"-p{password}" if password else "-p "
            # one thread, lowest CPU and disk priority: 7z uses every core by default
            proc = await asyncio.create_subprocess_exec(
                *_low_prio_cmd(["7z", "x", str(path), f"-o{dest}", "-y", "-bsp1", "-mmt1", pwd_arg]),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            pct_pattern = re.compile(r"(\d+)%")
            buffer = b""

            while True:
                chunk = await proc.stdout.read(256)
                if not chunk:
                    break
                buffer += chunk
                matches = pct_pattern.findall(buffer.decode("utf-8", errors="ignore"))
                if matches:
                    pct = int(matches[-1])
                    extracted_bytes = int(total_size * pct / 100) if total_size else pct
                    if progress_callback:
                        progress_callback(extracted_bytes, total_size)
                    buffer = buffer[-64:]

            await proc.wait()
            stderr_out = (await proc.stderr.read()).decode("utf-8", errors="ignore")

            if proc.returncode != 0:
                output = (stderr_out + buffer.decode("utf-8", errors="ignore")).lower()
                if any(hint in output for hint in _PASSWORD_HINTS):
                    raise (WrongPasswordError() if password else PasswordRequiredError())
                raise RuntimeError(stderr_out.strip() or "7z could not extract the file")
        elif name.endswith(ARCHIVE_EXTENSIONS):
            await asyncio.to_thread(_extract_python_sync, path, name, dest, password, total_size, progress_callback)
        else:
            raise RuntimeError("Unsupported archive format")

        if progress_callback:
            progress_callback(total_size, total_size)

    except asyncio.CancelledError:
        _safe_clean_dest(dest_dir, file_path)
        raise
    except Exception:
        _safe_clean_dest(dest_dir, file_path)
        raise


async def extract_archive(file_path: str, dest_dir: str, password: str | None = None):
    await extract_archive_with_progress(file_path, dest_dir, password=password)
