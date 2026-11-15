import os
import re
import urllib.parse
from pathlib import Path
import httpx

import config
import db

TMDB_API_BASE = "https://api.themoviedb.org/3"


def _clean_title_and_tags(filename: str) -> tuple[str, str | None, str | None, str]:
    name, ext = os.path.splitext(filename)
    t = re.sub(r"\[.*?\]|\(.*?\)", " ", name)
    t = re.sub(r"[\._\-\+]", " ", t)

    res_match = re.search(r"\b(2160p|4k|1080p|720p|480p)\b", t, re.IGNORECASE)
    resolution = res_match.group(1).lower() if res_match else None
    if resolution == "4k":
        resolution = "2160p"

    tv_match = re.search(r"\b(s\d{1,2}\s?e\d{1,2}|s\d{1,2})\b", t, re.IGNORECASE)

    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", t)
    year = year_match.group(1) if year_match else None

    split_pattern = (
        r"\b(2160p|1080p|720p|480p|4k|uhd|bluray|blu[\s\-]?ray|web[\s\-]?dl|webrip|web|hdtv|"
        r"dvdrip|x265|x264|hevc|avc|av1|xvid|dts|ac3|aac|atmos|remux|repack)\b"
    )
    parts = re.split(split_pattern, t, flags=re.I)
    candidate = parts[0].strip()

    if tv_match:
        cand_tv = t.split(tv_match.group(0))[0].strip()
        candidate = cand_tv
    elif year and year in candidate:
        candidate = candidate.split(year)[0].strip()

    clean_title = " ".join(candidate.split())
    if not clean_title:
        clean_title = " ".join(t.split()[:3])

    return clean_title, year, resolution, ext


async def get_api_key() -> str:
    return (await db.get_setting("tmdb_token", "") or "").strip()


async def is_enabled() -> bool:
    return bool(await get_api_key()) and await db.get_setting("tmdb_enabled", "0") == "1"


async def check_key(key: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{TMDB_API_BASE}/configuration", params={"api_key": key})
            return resp.status_code == 200
    except Exception:
        return False


async def search_tmdb(clean_title: str, year: str | None = None) -> dict | None:
    if not await is_enabled():
        return None
    api_key = await get_api_key()

    params = {
        "api_key": api_key,
        "language": "es-ES",
        "query": clean_title,
        "include_adult": "false",
    }
    if year:
        params["year"] = year

    url = f"{TMDB_API_BASE}/search/multi"
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                if results:
                    return results[0]
    except Exception:
        pass
    return None


async def organize_media_path(filename: str, base_folder_key: str) -> tuple[str, str]:
    clean_title, year, resolution, ext = _clean_title_and_tags(filename)
    ext_clean = ext if ext else ""

    tv_match = re.search(r"\bS(\d{1,2})\s?E(\d{1,2})\b", filename, re.IGNORECASE)

    tmdb_data = await search_tmdb(clean_title, year)

    if config.folder_media(base_folder_key) == "tv" or tv_match:
        series_name = clean_title
        if tmdb_data and tmdb_data.get("media_type") == "tv":
            series_name = tmdb_data.get("name") or tmdb_data.get("original_name") or series_name

        if tv_match:
            s_num = int(tv_match.group(1))
            e_num = int(tv_match.group(2))
            rel_dir = f"{series_name}/Temporada {s_num:02d}"
            res_tag = f" [{resolution}]" if resolution else ""
            new_filename = f"{series_name} - S{s_num:02d}E{e_num:02d}{res_tag}{ext_clean}"
        else:
            rel_dir = series_name
            res_tag = f" [{resolution}]" if resolution else ""
            new_filename = f"{series_name}{res_tag}{ext_clean}"

        return rel_dir, new_filename

    movie_title = clean_title
    movie_year = year
    if tmdb_data and tmdb_data.get("media_type") == "movie":
        movie_title = tmdb_data.get("title") or tmdb_data.get("original_title") or movie_title
        r_date = tmdb_data.get("release_date") or ""
        if r_date and len(r_date) >= 4:
            movie_year = r_date[:4]

    year_str = f" ({movie_year})" if movie_year else ""
    rel_dir = f"{movie_title}{year_str}"
    res_tag = f" [{resolution}]" if resolution else ""
    new_filename = f"{movie_title}{year_str}{res_tag}{ext_clean}"

    return rel_dir, new_filename


_folder_cache: dict[tuple, str | None] = {}
_INVALID_CHARS = re.compile(r'[\\/:*?"<>|]+')


def _sanitize(name: str) -> str:
    return " ".join(_INVALID_CHARS.sub(" ", name).split()).strip(" .")


async def folder_name_for(media: str, hint: str) -> str | None:
    if not hint or not await is_enabled():
        return None
    api_key = await get_api_key()
    clean_title, year, _res, _ext = _clean_title_and_tags(hint)
    if not clean_title:
        return None
    cache_key = (media, clean_title.lower(), year)
    if cache_key in _folder_cache:
        return _folder_cache[cache_key]

    year_param = "year" if media == "movie" else "first_air_date_year"
    result = None
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            for with_year in ([True, False] if year else [False]):
                params = {
                    "api_key": api_key, "language": "en-US",
                    "query": clean_title, "include_adult": "false",
                }
                if with_year:
                    params[year_param] = year
                resp = await client.get(f"{TMDB_API_BASE}/search/{media}", params=params)
                if resp.status_code == 200 and resp.json().get("results"):
                    result = resp.json()["results"][0]
                    break
    except Exception:
        return None
    if not result:
        _folder_cache[cache_key] = None
        return None

    if media == "movie":
        spanish = result.get("original_language") == "es"
        title = (result.get("original_title") if spanish else result.get("title")) or result.get("title")
        date = result.get("release_date") or ""
        y = date[:4] if len(date) >= 4 else year
        name = f"{title} ({y})" if y else title
    else:
        spanish = result.get("original_language") == "es"
        title = (result.get("original_name") if spanish else result.get("name")) or result.get("name")
        name = title
    name = _sanitize(name or "")
    _folder_cache[cache_key] = name or None
    return _folder_cache[cache_key]


async def adjust_relpath(folder_key: str, relpath: str, hint: str) -> str:
    media = config.folder_media(folder_key)
    if not media or relpath:
        return relpath
    name = await folder_name_for(media, hint)
    return name or relpath
