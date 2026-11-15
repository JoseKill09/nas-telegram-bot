import asyncio
import os
import re
import shutil
import time
from pathlib import Path

import config


class PathError(Exception):
    pass


def resolve_path(folder_key: str, relpath: str = ""):
    if folder_key not in config.FOLDERS:
        raise PathError("Carpeta no válida")
    base = Path(config.FOLDERS[folder_key]).resolve()
    target = (base / relpath).resolve()
    if target != base and base not in target.parents:
        raise PathError("Ruta no permitida")
    return base, target


HIDDEN_NAMES = {"#recycle", "@eaDir"}


def list_dir(folder_key: str, relpath: str = ""):
    base, target = resolve_path(folder_key, relpath)
    target.mkdir(parents=True, exist_ok=True)
    entries = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    entries = [e for e in entries if e.name.lower() not in {n.lower() for n in HIDDEN_NAMES}]
    dirs = [e for e in entries if e.is_dir()]
    files = [e for e in entries if e.is_file()]
    return dirs, files


def human_size(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024:
            return f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} PB"


_DIR_SIZE_CACHE: dict[str, tuple[int, float]] = {}
_DIR_SIZE_TTL = 600
_DIR_SIZE_TIMEOUT = 6.0


def _dir_size_sync(path: Path) -> int:
    total = 0
    try:
        with os.scandir(path) as it:
            for entry in it:
                try:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        total += _dir_size_sync(entry.path)
                    else:
                        total += entry.stat(follow_symlinks=False).st_size
                except OSError:
                    continue
    except OSError:
        return 0
    return total


async def get_dir_size(folder_key: str, relpath: str) -> int | None:
    _base, target = resolve_path(folder_key, relpath)
    key = str(target)
    cached = _DIR_SIZE_CACHE.get(key)
    if cached and (time.monotonic() - cached[1]) < _DIR_SIZE_TTL:
        return cached[0]
    try:
        size = await asyncio.wait_for(asyncio.to_thread(_dir_size_sync, target), timeout=_DIR_SIZE_TIMEOUT)
    except asyncio.TimeoutError:
        return None
    _DIR_SIZE_CACHE[key] = (size, time.monotonic())
    return size


def invalidate_dir_size_cache(folder_key: str, relpath: str = ""):
    try:
        _base, target = resolve_path(folder_key, relpath)
    except PathError:
        return
    invalidate_dir_size_cache_path(target)


def invalidate_dir_size_cache_path(path):
    path = Path(path)
    _DIR_SIZE_CACHE.pop(str(path), None)
    for parent in path.parents:
        if str(parent) in _DIR_SIZE_CACHE:
            _DIR_SIZE_CACHE.pop(str(parent), None)
        if any(str(parent) == str(Path(p).resolve()) for p in config.FOLDERS.values()):
            break


def get_info(folder_key: str, relpath: str):
    base, target = resolve_path(folder_key, relpath)
    stat = target.stat()
    return {
        "name": target.name,
        "is_dir": target.is_dir(),
        "size": None if target.is_dir() else human_size(stat.st_size),
    }


def rename(folder_key: str, relpath: str, new_name: str):
    base, target = resolve_path(folder_key, relpath)
    if "/" in new_name or "\\" in new_name:
        raise PathError("Nombre no válido")
    new_path = target.parent / new_name
    if new_path.exists():
        raise FileExistsError()
    target.rename(new_path)
    return new_path.relative_to(base)


def delete(folder_key: str, relpath: str):
    base, target = resolve_path(folder_key, relpath)
    if target == base:
        raise PathError("No se puede eliminar la carpeta raíz")
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()


def mkdir(folder_key: str, relpath: str, name: str):
    base, target = resolve_path(folder_key, relpath)
    if "/" in name or "\\" in name:
        raise PathError("Nombre no válido")
    new_dir = target / name
    if new_dir.exists():
        raise FileExistsError()
    new_dir.mkdir(parents=True)


def ensure_all_base_folders():
    for path in config.FOLDERS.values():
        Path(path).mkdir(parents=True, exist_ok=True)


def get_disk_space_info(folder_key: str = "Downloads", relpath: str = "") -> dict:
    try:
        _base, target = resolve_path(folder_key, relpath)
        target_path = target if target.exists() else _base
        usage = shutil.disk_usage(target_path)
        return {
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
            "total_str": human_size(usage.total),
            "used_str": human_size(usage.used),
            "free_str": human_size(usage.free),
            "free_pct": round((usage.free / usage.total) * 100, 1) if usage.total else 0,
        }
    except Exception:
        return {
            "total": 0, "used": 0, "free": 0,
            "total_str": "?", "used_str": "?", "free_str": "?", "free_pct": 0
        }


def check_disk_space(folder_key: str, required_bytes: int, safety_margin_gb: float = 2.0) -> tuple[bool, str]:
    if not required_bytes or required_bytes <= 0:
        return True, ""
    info = get_disk_space_info(folder_key)
    margin = int(safety_margin_gb * 1024 * 1024 * 1024)
    needed = required_bytes + margin
    if info["free"] > 0 and info["free"] < needed:
        return False, (
            f"⚠️ Espacio insuficiente en el disco del NAS para '{folder_key}'.\n"
            f"• Espacio libre: {info['free_str']}\n"
            f"• Necesario: {human_size(required_bytes)} (+ {safety_margin_gb:.1f}GB de margen)"
        )
    return True, ""


# ---------------------------------------------------------------------------
# Copiar / mover (19.0)
# ---------------------------------------------------------------------------
import itertools

COPY_JOBS: dict[int, dict] = {}
_JOB_IDS = itertools.count(1)


def _tree_size(path: Path) -> int:
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    return _dir_size_sync(path)


def _unique_name(dest: Path) -> Path:
    stem, suffix = dest.stem, dest.suffix
    if dest.is_dir():
        stem, suffix = dest.name, ""
    for i in itertools.count(2):
        cand = dest.with_name(f"{stem} ({i}){suffix}")
        if not cand.exists():
            return cand


def _copy_file(src: Path, dst: Path, job: dict):
    chunk = 4 * 1024 * 1024
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(src, "rb") as fin, open(dst, "wb") as fout:
        while True:
            if job.get("cancel"):
                raise InterruptedError()
            buf = fin.read(chunk)
            if not buf:
                break
            fout.write(buf)
            job["done"] += len(buf)
    try:
        shutil.copystat(src, dst)
    except OSError:
        pass


def _copy_tree(src: Path, dst: Path, job: dict):
    if src.is_file():
        _copy_file(src, dst, job)
        return
    dst.mkdir(parents=True, exist_ok=True)
    for child in sorted(src.iterdir()):
        _copy_tree(child, dst / child.name, job)


def _run_copy_sync(job: dict, items: list[Path], dest_dir: Path, policy: str, move: bool):
    for src in items:
        if job.get("cancel"):
            break
        job["current"] = src.name
        dst = dest_dir / src.name
        try:
            if src.resolve() == dst.resolve():
                job["skipped"] += 1
                continue
            if dest_dir.resolve() == src.resolve() or src.resolve() in dest_dir.resolve().parents:
                job["errors"].append(f"{src.name}: destino dentro del origen")
                continue
            if dst.exists():
                if policy == "skip":
                    job["skipped"] += 1
                    job["done"] += _tree_size(src)
                    continue
                if policy == "rename":
                    dst = _unique_name(dst)
                elif policy == "replace":
                    if dst.is_dir():
                        shutil.rmtree(dst)
                    else:
                        dst.unlink()
            if move and not dst.exists() and src.stat().st_dev == dest_dir.stat().st_dev:
                dst.parent.mkdir(parents=True, exist_ok=True)
                size = _tree_size(src)
                os.replace(src, dst)
                job["done"] += size
            else:
                _copy_tree(src, dst, job)
                if move:
                    if src.is_dir():
                        shutil.rmtree(src)
                    else:
                        src.unlink()
            job["copied"] += 1
        except InterruptedError:
            job["cancelled"] = True
            try:
                if dst.exists():
                    shutil.rmtree(dst) if dst.is_dir() else dst.unlink()
            except Exception:
                pass
            break
        except Exception as e:
            job["errors"].append(f"{src.name}: {e}")


async def start_copy(src_folder: str, src_paths: list[str], dst_folder: str, dst_path: str,
                     policy: str = "skip", move: bool = False) -> int:
    if policy not in ("skip", "replace", "rename"):
        raise PathError("Política no válida")
    items = []
    for rel in src_paths:
        base, target = resolve_path(src_folder, rel)
        if target == base or not target.exists():
            raise PathError("Origen no válido")
        items.append(target)
    _b, dest_dir = resolve_path(dst_folder, dst_path)
    dest_dir.mkdir(parents=True, exist_ok=True)
    total = sum(await asyncio.gather(*[asyncio.to_thread(_tree_size, p) for p in items]))
    ok, msg = check_disk_space(dst_folder, 0 if move else total)
    if not ok:
        raise PathError(msg)
    job_id = next(_JOB_IDS)
    job = {"id": job_id, "total": total, "done": 0, "copied": 0, "skipped": 0, "errors": [],
           "current": "", "finished": False, "cancel": False, "cancelled": False, "move": move,
           "started": time.time(), "dest": f"{dst_folder}/{dst_path}".rstrip("/")}
    COPY_JOBS[job_id] = job

    async def _runner():
        try:
            await asyncio.to_thread(_run_copy_sync, job, items, dest_dir, policy, move)
        finally:
            job["finished"] = True
            invalidate_dir_size_cache(dst_folder, dst_path)
            invalidate_dir_size_cache(src_folder, "")

    job["task"] = asyncio.create_task(_runner())
    return job_id


def job_public(job: dict) -> dict:
    return {k: v for k, v in job.items() if k != "task"}


def apply_new_name(old: str, new: str) -> str:
    # Limpia el nombre pedido y conserva la extensión original si falta.
    new = re.sub(r'[\\/:*?"<>|\x00-\x1f]', " ", (new or "")).strip().strip(".")
    new = re.sub(r"\s+", " ", new)
    if not new:
        return old
    old_ext = Path(old).suffix
    if old_ext and not new.lower().endswith(old_ext.lower()):
        new += old_ext
    return new[:200]
