import os
import re

import config
import db
import rules

BASE = "/media"


class FolderError(Exception):
    pass


def valid_name(name: str) -> str:
    name = (name or "").strip()
    if not name or re.search(r"[:/\\]", name) or len(name.encode()) > 30:
        raise FolderError("Invalid name")
    return name


def inside_base(path: str) -> str:
    real = os.path.realpath(path)
    if real != BASE and not real.startswith(BASE + os.sep):
        raise FolderError("Outside the shared folder")
    return real


def list_subdirs(path: str) -> list[str]:
    real = inside_base(path)
    try:
        return sorted((d for d in os.listdir(real)
                       if not d.startswith(".") and os.path.isdir(os.path.join(real, d))), key=str.lower)
    except OSError:
        return []


def make_subdir(parent: str, name: str) -> str:
    name = valid_name(name)
    target = os.path.join(inside_base(parent), name)
    os.makedirs(target, exist_ok=True)
    return target


async def add(name: str, path: str, media: str = "") -> None:
    name = valid_name(name)
    if name in config.FOLDERS:
        raise FolderError("A folder with that name already exists")
    if not path.startswith("/"):
        raise FolderError("The path must be absolute")
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        pass
    config.FOLDERS[name] = os.path.normpath(path)
    config.FOLDER_MEDIA[name] = media if media in ("movie", "tv") else ""
    await config.save_folders()


async def set_path(name: str, path: str) -> None:
    if name not in config.FOLDERS:
        raise FolderError("Unknown folder")
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        pass
    config.FOLDERS[name] = os.path.normpath(path)
    await config.save_folders()


async def rename(old: str, new: str) -> None:
    new = valid_name(new)
    if old not in config.FOLDERS:
        raise FolderError("Unknown folder")
    if new != old and new in config.FOLDERS:
        raise FolderError("A folder with that name already exists")
    items = [(new if n == old else n, p, config.FOLDER_MEDIA.get(n, "")) for n, p in config.FOLDERS.items()]
    config.set_folders([{"name": n, "path": p, "media": m} for n, p, m in items])
    await config.save_folders()
    lst = await rules.load()
    changed = False
    for r in lst:
        if r["folder"] == old:
            r["folder"] = new
            changed = True
    if changed:
        await rules.save(lst)
    if (await rules.get_options())["fallback"] == old:
        await rules.set_option("fallback", new)
