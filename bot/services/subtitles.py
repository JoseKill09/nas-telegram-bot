import asyncio
import io
import os
import re
import shutil
import urllib.parse
import zipfile
from pathlib import Path
import httpx

import config

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html, */*",
}

SUPPORTED_SUB_LANGUAGES = {
    "es": {"name": "Español", "code": "es", "flag": "🇪🇸", "alias": ["spanish", "spa", "es", "castellano", "latino", "es-es", "es-la"]},
    "en": {"name": "Inglés", "code": "en", "flag": "🇬🇧", "alias": ["english", "eng", "en"]},
    "it": {"name": "Italiano", "code": "it", "flag": "🇮🇹", "alias": ["italian", "ita", "it"]},
    "de": {"name": "Alemán", "code": "de", "flag": "🇩🇪", "alias": ["german", "ger", "de", "deutsch"]},
}

VIDEO_EXTENSIONS = (".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".ts")
TEMP_SUBS_DIR = Path(config.CONFIG_DIR) / "temp_subs"


def extract_clean_title_and_year(raw_name: str) -> tuple[str, str | None]:
    t = re.sub(r"\.(mp4|mkv|avi|mov|wmv|flv|webm|m4v|ts)$", "", raw_name, flags=re.I)
    t = re.sub(r"\[.*?\]|\(.*?\)", " ", t)
    t = re.sub(r"[\._\-\+]", " ", t)

    tv_match = re.search(r"\b(s\d{1,2}\s?e\d{1,2}|s\d{1,2})\b", t, re.IGNORECASE)
    tv_tag = tv_match.group(1).upper().replace(" ", "") if tv_match else None

    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", t)
    year = year_match.group(1) if year_match else None

    split_pattern = (
        r"\b(2160p|1080p|720p|480p|4k|uhd|bluray|blu[\s\-]?ray|web[\s\-]?dl|webrip|web|hdtv|"
        r"dvdrip|x265|x264|hevc|avc|av1|xvid|dts|ac3|aac|atmos|truehd|remux|repack|proper|"
        r"amzn|nf|dsnp|atvp|hmax|yts|yify|rarbg|eztv|galaxyrg|tgx|vxt|ettv|sparks)\b"
    )
    parts = re.split(split_pattern, t, flags=re.I)
    candidate = parts[0].strip()

    if tv_tag:
        candidate_tv = t.split(tv_match.group(0))[0].strip()
        candidate = f"{candidate_tv} {tv_tag}"
    elif year and not candidate:
        candidate = t.split(year)[0].strip()

    clean_title = " ".join(candidate.split())
    if not clean_title:
        clean_title = " ".join(t.split()[:4])

    return clean_title, year


def format_sub_search_query(raw_name: str) -> str:
    title, year = extract_clean_title_and_year(raw_name)
    if year and year not in title:
        return f"{title} {year}".strip()
    return title.strip()


async def search_subtitles_subdl(query_clean: str, lang_code: str = "all") -> list[dict]:
    results = []
    lang_param = f"&languages={lang_code}" if lang_code and lang_code != "all" else ""
    url = f"https://api.subdl.com/api/v1/subtitles?film_name={urllib.parse.quote(query_clean)}{lang_param}"

    try:
        async with httpx.AsyncClient(timeout=8, headers=HEADERS, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") and data.get("subtitles"):
                    for item in data.get("subtitles", [])[:35]:
                        dl_link = item.get("url") or item.get("download_url")
                        if not dl_link:
                            continue
                        if not dl_link.startswith("http"):
                            dl_link = f"https://dl.subdl.com{dl_link}"
                        item_lang = (item.get("lang") or item.get("language") or lang_code or "es").lower()[:2]
                        if item_lang not in SUPPORTED_SUB_LANGUAGES and lang_code != "all":
                            continue
                        results.append({
                            "title": item.get("release_name") or item.get("name") or query_clean,
                            "lang": item_lang if item_lang in SUPPORTED_SUB_LANGUAGES else "es",
                            "download_url": dl_link,
                            "rating": float(item.get("rating") or item.get("downloads", 0) or 5.0),
                            "provider": "SubDL",
                            "ext": "srt",
                        })
    except Exception:
        pass
    return results


async def search_subtitles_opensubtitles(query_clean: str, lang_code: str = "all") -> list[dict]:
    results = []
    lang_filter = {"es": "spa,es", "en": "eng,en", "it": "ita,it", "de": "ger,de"}.get(lang_code, "all")
    lang_url = f"/sublanguageid-{lang_filter}" if lang_filter != "all" else ""
    url = f"https://rest.opensubtitles.org/search/query-{urllib.parse.quote(query_clean)}{lang_url}"
    headers = {**HEADERS, "X-User-Agent": "VLSub 0.10.2"}

    try:
        async with httpx.AsyncClient(timeout=8, headers=headers, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    for item in data[:30]:
                        dl_url = item.get("SubDownloadLink") or item.get("ZipDownloadLink")
                        if not dl_url:
                            continue
                        iso = (item.get("ISO639") or item.get("SubLanguageID") or "es").lower()[:2]
                        code = "es" if iso in ("sp", "es") else (iso if iso in SUPPORTED_SUB_LANGUAGES else "es")
                        results.append({
                            "title": item.get("MovieReleaseName") or item.get("SubFileName") or query_clean,
                            "lang": code,
                            "download_url": dl_url,
                            "rating": float(item.get("SubRating") or 5.0),
                            "provider": "OpenSubtitles",
                            "ext": "srt",
                        })
    except Exception:
        pass
    return results


async def search_subtitles_yify(query_clean: str, lang_code: str = "all") -> list[dict]:
    results = []
    lang_full = {"es": "spanish", "en": "english", "it": "italian", "de": "german"}.get(lang_code, "")
    url = f"https://yts-subs.com/ajax/search?q={urllib.parse.quote(query_clean)}"

    try:
        async with httpx.AsyncClient(timeout=8, headers=HEADERS, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "html.parser")
                links = soup.select("a[href*='/movie-imdb/']")
                if links:
                    movie_href = links[0].get("href")
                    sub_page_url = f"https://yts-subs.com{movie_href}"
                    resp_sub = await client.get(sub_page_url)
                    if resp_sub.status_code == 200:
                        sub_soup = BeautifulSoup(resp_sub.text, "html.parser")
                        rows = sub_soup.select("table.table tbody tr")
                        for r in rows:
                            l_elem = r.select_one(".sub-lang")
                            row_lang_text = l_elem.get_text().lower() if l_elem else ""
                            if lang_full and lang_full not in row_lang_text:
                                continue

                            code_detected = "es"
                            if "spanish" in row_lang_text:
                                code_detected = "es"
                            elif "english" in row_lang_text:
                                code_detected = "en"
                            elif "italian" in row_lang_text:
                                code_detected = "it"
                            elif "german" in row_lang_text:
                                code_detected = "de"
                            else:
                                if lang_code != "all":
                                    continue

                            dl_a = r.select_one("a[href*='/subtitles/']")
                            rating_el = r.select_one(".rating-cell")
                            rating_val = 5.0
                            if rating_el:
                                m = re.search(r"(\d+)", rating_el.get_text())
                                if m:
                                    rating_val = float(m.group(1))

                            if dl_a:
                                dl_page = f"https://yts-subs.com{dl_a.get('href')}"
                                results.append({
                                    "title": dl_a.get_text(strip=True),
                                    "lang": code_detected,
                                    "download_url": dl_page,
                                    "rating": rating_val,
                                    "provider": "YIFY Subs",
                                    "ext": "srt",
                                })
    except Exception:
        pass
    return results


async def search_subtitles_subsource(query_clean: str, lang_code: str = "all") -> list[dict]:
    results = []
    lang_param = {"es": "spanish", "en": "english", "it": "italian", "de": "german"}.get(lang_code, "")
    url = f"https://api.subsource.net/api/searchMovie?movieName={urllib.parse.quote(query_clean)}"

    try:
        async with httpx.AsyncClient(timeout=8, headers=HEADERS, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                found = data.get("found", [])
                if found:
                    movie_id = found[0].get("id")
                    if movie_id:
                        sub_url = f"https://api.subsource.net/api/getSub/{movie_id}"
                        resp_subs = await client.get(sub_url)
                        if resp_subs.status_code == 200:
                            subs_data = resp_subs.json()
                            for s in subs_data.get("subs", [])[:25]:
                                s_lang = (s.get("lang") or "").lower()
                                if lang_param and lang_param not in s_lang:
                                    continue
                                code = "es" if "spanish" in s_lang else ("en" if "english" in s_lang else "es")
                                results.append({
                                    "title": s.get("releaseName") or query_clean,
                                    "lang": code,
                                    "download_url": f"https://api.subsource.net/api/downloadSub/{s.get('id')}",
                                    "rating": float(s.get("rating") or 5.0),
                                    "provider": "Subsource",
                                    "ext": "srt",
                                })
    except Exception:
        pass
    return results


async def search_all_subtitles(raw_query: str, lang_code: str = "all") -> list[dict]:
    clean_q = format_sub_search_query(raw_query)
    if not clean_q:
        return []

    res_subdl, res_os, res_yts, res_subsrc = await asyncio.gather(
        search_subtitles_subdl(clean_q, lang_code),
        search_subtitles_opensubtitles(clean_q, lang_code),
        search_subtitles_yify(clean_q, lang_code),
        search_subtitles_subsource(clean_q, lang_code),
        return_exceptions=True,
    )

    all_subs = []
    for r in (res_subdl, res_os, res_yts, res_subsrc):
        if isinstance(r, list):
            all_subs.extend(r)

    seen = set()
    deduped = []
    for s in all_subs:
        dlink = s.get("download_url")
        if dlink and dlink not in seen:
            seen.add(dlink)
            deduped.append(s)

    deduped.sort(key=lambda s: s.get("rating", 0), reverse=True)
    return deduped


async def get_best_subtitle(raw_title: str, lang_code: str) -> dict | None:
    subs = await search_all_subtitles(raw_title, lang_code)
    return subs[0] if subs else None


async def save_subtitle_from_url(download_url: str, target_file_path: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=15, headers=HEADERS, follow_redirects=True) as client:
            resp = await client.get(download_url)
            if resp.status_code != 200:
                return False

            content = resp.content

            if b"<!DOCTYPE html" in content or b"<html" in content:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "html.parser")
                zip_a = soup.select_one("a[href$='.zip'], a[href*='download']")
                if zip_a and zip_a.get("href"):
                    zip_url = zip_a.get("href")
                    if not zip_url.startswith("http"):
                        zip_url = f"https://yts-subs.com{zip_url}"
                    resp_zip = await client.get(zip_url)
                    if resp_zip.status_code == 200:
                        content = resp_zip.content

            target_path = Path(target_file_path)
            target_path.parent.mkdir(parents=True, exist_ok=True)

            if content[:4] == b"PK\x03\x04":
                with zipfile.ZipFile(io.BytesIO(content)) as zf:
                    srt_names = [n for n in zf.namelist() if n.lower().endswith((".srt", ".vtt"))]
                    if srt_names:
                        srt_data = zf.read(srt_names[0])
                        target_path.write_bytes(srt_data)
                        return True

            target_path.write_bytes(content)
            return True
    except Exception:
        return False


def get_task_temp_sub_dir(task_id: int) -> Path:
    d = TEMP_SUBS_DIR / str(task_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


async def download_subtitles_to_temp(
    task_id: int,
    base_title: str,
    lang_codes: list[str] | None = None,
    specific_subs: list[dict] | None = None,
) -> list[str]:
    try:
        temp_dir = get_task_temp_sub_dir(task_id)
        downloaded_files = []

        if specific_subs:
            for idx, sub in enumerate(specific_subs):
                url = sub.get("download_url")
                lang = (sub.get("lang") or "es").lower()
                if not url:
                    continue
                temp_file = temp_dir / f"sub_{idx}.{lang}.srt"
                ok = await save_subtitle_from_url(url, str(temp_file))
                if ok:
                    downloaded_files.append(str(temp_file.name))
            return downloaded_files

        if lang_codes:
            for code in lang_codes:
                code_clean = code.lower().strip()
                if code_clean not in SUPPORTED_SUB_LANGUAGES:
                    continue
                best = await get_best_subtitle(base_title, code_clean)
                if not best or not best.get("download_url"):
                    continue
                temp_file = temp_dir / f"auto.{code_clean}.srt"
                ok = await save_subtitle_from_url(best["download_url"], str(temp_file))
                if ok:
                    downloaded_files.append(str(temp_file.name))

        return downloaded_files
    except Exception:
        return []


async def finalize_subtitles(task_id: int, final_media_path: str):
    temp_dir = TEMP_SUBS_DIR / str(task_id)
    if not temp_dir.exists() or not temp_dir.is_dir():
        return

    try:
        media_p = Path(final_media_path)
        if media_p.is_dir():
            target_dir = media_p
            videos = [p for p in media_p.iterdir() if p.is_file() and p.name.lower().endswith(VIDEO_EXTENSIONS)]
            if videos:
                videos.sort(key=lambda x: x.stat().st_size, reverse=True)
                base_name = videos[0].stem
            else:
                base_name = media_p.name
        else:
            target_dir = media_p.parent
            base_name = media_p.stem

        sub_files = list(temp_dir.glob("*.srt")) + list(temp_dir.glob("*.vtt"))
        for sfile in sub_files:
            m = re.search(r"\.([a-z]{2})\.(srt|vtt)$", sfile.name, re.I)
            lang = m.group(1).lower() if m else "es"
            ext = m.group(2).lower() if m else "srt"

            target_sub_path = target_dir / f"{base_name}.{lang}.{ext}"
            if target_sub_path.exists():
                target_sub_path = target_dir / f"{base_name}.{lang}_{sfile.stem}.{ext}"

            shutil.copy2(str(sfile), str(target_sub_path))
    except Exception:
        pass
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
