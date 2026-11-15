import html
import uuid

from telegram import InlineKeyboardButton as Btn, InlineKeyboardMarkup as Markup
from telegram.constants import ParseMode

import filemanager
import tmdb_helper
import torrent_search
from i18n import L
from rich_ui import esc, r_footer, r_h, r_kv_table, r_p, r_quote, r_table, rich
from utils import authorized_only, get_command_payload, is_owner

PAGE_SIZE = 10
TMDB_IMG_BASE = "https://image.tmdb.org/t/p/w500"

_search_cache: dict[str, dict] = {}
_item_cache: dict[str, dict] = {}

RES_OPTIONS = ["any", "2160p", "1080p", "720p"]
CODEC_OPTIONS = ["any", "x265", "x264"]
SEEDS_OPTIONS = [0, 1, 5, 20, 50]
SORT_OPTIONS = ["smart", "seeds", "size", "quality"]

DEFAULT_FILTERS = {"res": "any", "codec": "any", "seeds": 0, "cached": False, "sort": "smart"}


def _sort_label(value: str) -> str:
    return {
        "smart": L("Relevancia (⚡ primero)", "Relevance (⚡ first)"),
        "seeds": "Seeds",
        "size": L("Tamaño", "Size"),
        "quality": L("Calidad", "Quality"),
    }[value]


def _filtered(data: dict) -> list[dict]:
    f = data["filters"]
    out = []
    for it in data["results"]:
        meta = it.get("meta", {})
        if f["res"] != "any" and meta.get("resolution") != f["res"]:
            continue
        if f["codec"] != "any" and meta.get("codec") != f["codec"]:
            continue
        if it.get("seeders", 0) < f["seeds"]:
            continue
        if f["cached"] and not it.get("cached"):
            continue
        out.append(it)
    if f["sort"] == "seeds":
        out.sort(key=lambda i: (bool(i.get("cached")), i.get("seeders", 0)), reverse=True)
    elif f["sort"] == "size":
        out.sort(key=lambda i: i.get("size_bytes", 0), reverse=True)
    elif f["sort"] == "quality":
        out.sort(key=lambda i: (bool(i.get("cached")), i.get("meta", {}).get("quality_score", 0)), reverse=True)
    return out


def _filters_summary(f: dict) -> str:
    parts = []
    if f["res"] != "any":
        parts.append(f["res"])
    if f["codec"] != "any":
        parts.append(f["codec"])
    if f["seeds"]:
        parts.append(f"≥{f['seeds']} seeds")
    if f["cached"]:
        parts.append(L("solo ⚡", "only ⚡"))
    parts.append(_sort_label(f["sort"]))
    return " · ".join(parts)


def _cut(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


def _render_results(qid: str, page: int = 0) -> tuple[str, Markup]:
    data = _search_cache.get(qid)
    if not data:
        return (L("⚠️ La búsqueda ha caducado. Vuelve a buscar.", "⚠️ The search has expired. Search again."),
                Markup([[Btn(L("🏠 Menú principal", "🏠 Main menu"), callback_data="menu:main")]]))
    results = _filtered(data)
    total = len(results)
    pages = max(1, -(-total // PAGE_SIZE))
    page = max(0, min(page, pages - 1))
    start = page * PAGE_SIZE
    chunk = results[start:start + PAGE_SIZE]

    rows, kb, row = [], [], []
    for n, it in enumerate(chunk, start=start + 1):
        item_id = uuid.uuid4().hex[:10]
        _item_cache[item_id] = it
        it["_id"] = item_id
        meta = it.get("meta", {})
        res = meta.get("resolution", "N/D")
        quality = " ".join(x for x in (res if res != "N/D" else "", meta.get("codec") if meta.get("codec") != "N/D" else "") if x) or "—"
        rows.append([
            f"<b>{n}</b>",
            "⚡" if it.get("cached") else "",
            esc(_cut(it.get("title", "Torrent"), 250)),  # full name (cut only for absurdly long ones)
            esc(it.get("size", "?")),
            f"{it.get('health', {}).get('icon', '')} {it.get('seeders', 0)}/{it.get('leechers', 0)}",
            esc(quality),
            esc(_cut(it.get("provider", ""), 14)),
        ])
        row.append(Btn(f"{'⚡' if it.get('cached') else ''}{n}", callback_data=f"ts:i:{qid}:{item_id}"))
        if len(row) == 5:
            kb.append(row)
            row = []
    if row:
        kb.append(row)

    n_cached = sum(1 for it in results if it.get("cached"))
    caption = L(f"{start + 1 if total else 0}–{start + len(chunk)} de {total} · página {page + 1}/{pages}",
                f"{start + 1 if total else 0}–{start + len(chunk)} of {total} · page {page + 1}/{pages}")
    if n_cached:
        caption += L(f" · ⚡ {n_cached} en TorBox", f" · ⚡ {n_cached} on TorBox")
    blocks = [r_h(L("Resultados: ", "Results: ") + data["query"], 2, "🔍")]
    if rows:
        blocks.append(r_table(rows, header=["#", "⚡", L("Título", "Title"), L("Tamaño", "Size"), "🌱/👥", L("Calidad", "Quality"), L("Fuente", "Source")],
                              caption=esc(caption)))
    else:
        blocks.append(r_p(L("Ningún resultado con estos filtros.", "No results with these filters.")))
    blocks.append(r_footer(L("Toca un número para ver la ficha y descargar. ", "Tap a number to open the card and download. ")
                           + esc(L("Filtros: ", "Filters: ") + _filters_summary(data["filters"]))))

    nav = []
    if page > 0:
        nav.append(Btn("◀", callback_data=f"ts:page:{qid}:{page - 1}"))
    nav.append(Btn(f"{page + 1}/{pages}", callback_data=f"ts:page:{qid}:{page}"))
    if page + 1 < pages:
        nav.append(Btn("▶", callback_data=f"ts:page:{qid}:{page + 1}"))
    kb.append(nav)
    kb.append([Btn(L("⚙️ Filtros", "⚙️ Filters"), callback_data=f"ts:f:{qid}"),
               Btn(L("🏠 Menú", "🏠 Menu"), callback_data="menu:main")])
    return rich(*blocks), Markup(kb)


def _filters_content(qid: str) -> tuple[str, Markup]:
    data = _search_cache[qid]
    f = data["filters"]
    text = rich(
        r_h(L("Filtros", "Filters"), 2, "⚙️"),
        r_kv_table([
            (L("Resolución", "Resolution"), L("Cualquiera", "Any") if f["res"] == "any" else f["res"]),
            (L("Códec", "Codec"), L("Cualquiera", "Any") if f["codec"] == "any" else f["codec"]),
            (L("Seeds mínimos", "Minimum seeds"), str(f["seeds"])),
            (L("Solo ⚡ en TorBox", "Only ⚡ on TorBox"), L("Sí", "Yes") if f["cached"] else "No"),
            (L("Orden", "Sort"), _sort_label(f["sort"])),
        ]),
        r_footer(L("Cada botón cambia al siguiente valor.", "Each button switches to the next value.")),
    )
    kb = Markup([
        [Btn(L("📺 Resolución", "📺 Resolution"), callback_data=f"ts:fc:{qid}:res"),
         Btn(L("🎞️ Códec", "🎞️ Codec"), callback_data=f"ts:fc:{qid}:codec")],
        [Btn("🌱 Seeds", callback_data=f"ts:fc:{qid}:seeds"),
         Btn(L("⚡ Solo caché", "⚡ Cached only"), callback_data=f"ts:fc:{qid}:cached")],
        [Btn(L("↕️ Orden", "↕️ Sort"), callback_data=f"ts:fc:{qid}:sort"),
         Btn(L("♻️ Quitar filtros", "♻️ Reset"), callback_data=f"ts:fr:{qid}")],
        [Btn(L("⬅️ Resultados", "⬅️ Results"), callback_data=f"ts:page:{qid}:0")],
    ])
    return text, kb


async def _tmdb_intro_card(query_text: str) -> tuple[str, str] | None:
    try:
        data = await tmdb_helper.search_tmdb(query_text)
    except Exception:
        data = None
    if not data or not data.get("poster_path"):
        return None
    name = data.get("title") or data.get("name") or query_text
    date = (data.get("release_date") or data.get("first_air_date") or "")[:4]
    overview = data.get("overview") or ""
    if len(overview) > 300:
        overview = overview[:297] + "..."
    kind = "🎬 " + L("Película", "Movie") if data.get("media_type") == "movie" else (
        "📺 Serie" if data.get("media_type") == "tv" else "🎞️")
    lines = [f"{kind} · {esc(date)}" if date else kind]
    if data.get("vote_average"):
        lines.append(f"⭐ {data['vote_average']:.1f}/10 (TMDB)")
    if overview:
        lines += ["", esc(overview)]
    caption = f"<b>{esc(name)}</b>\n" + "\n".join(lines)
    return f"{TMDB_IMG_BASE}{data['poster_path']}", caption[:1024]


async def no_sources_reply(update):
    """Every search source is disabled (they all come OFF by default): explain it instead of «0 results»."""
    owner = is_owner(update.effective_user.id)
    text = rich(
        r_h(L("No hay ningún buscador activo", "No search source is enabled"), 2, "🔎"),
        r_p(L("Los buscadores de torrents vienen apagados al instalar el bot: tú decides cuáles usar.",
              "Torrent search sources come switched off when the bot is installed: you choose which ones to use.")
            if owner else
            L("El administrador del bot todavía no ha activado ningún buscador. Pídeselo.",
              "The bot administrator has not enabled any search source yet. Ask them to.")),
        r_footer(L("Ajustes → 🔎 Buscadores: activa los que quieras y pulsa «Probar todos».",
                   "Settings → 🔎 Search sources: enable the ones you want and press «Test all».") if owner else ""),
    )
    markup = Markup([[Btn("🔎 " + L("Activar buscadores", "Enable search sources"), callback_data="src:menu"),
                      Btn("🧭 " + L("Conectar Prowlarr", "Connect Prowlarr"), callback_data="px:menu")]]) if owner else None
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)


@authorized_only
async def search_command(update, context):
    query = get_command_payload(update).strip()
    if not query:
        await update.effective_message.reply_text(
            rich(
                r_h(L("Buscador de torrents", "Torrent search"), 2, "🔎"),
                r_p(L("Uso: <code>/buscar &lt;lo que quieras buscar&gt;</code>", "Usage: <code>/search &lt;what you want to find&gt;</code>")),
                r_footer(L("Ejemplo: /buscar ubuntu 24.04", "Example: /search ubuntu 24.04")),
            ),
            parse_mode=ParseMode.HTML,
        )
        return

    if not await torrent_search.has_search_backend():
        await no_sources_reply(update)
        return

    status_msg = await update.effective_message.reply_text(
        L("🔍 Buscando ", "🔍 Searching ") + f"<code>{html.escape(query)}</code>...", parse_mode=ParseMode.HTML
    )
    await _run_search(update.effective_user.id, query, "all", status_msg)


_fallback_queries: dict[str, str] = {}


async def _run_search(user_id: int, query: str, provider: str, status_msg) -> None:
    results, info = await torrent_search.search_torrents_ex(query, provider=provider)
    if not results:
        text = L("❌ No se encontraron torrents para ", "❌ No torrents found for ") + f"<code>{html.escape(query)}</code>.\n"
        markup = None
        if info.get("prowlarr_error"):
            text += L("⚠️ Prowlarr no respondió: ", "⚠️ Prowlarr did not answer: ") + html.escape(info["prowlarr_error"])
            if provider != "builtin" and await torrent_search.enabled_sources():
                fid = uuid.uuid4().hex[:10]
                _fallback_queries[fid] = query
                if len(_fallback_queries) > 30:
                    _fallback_queries.pop(next(iter(_fallback_queries)))
                markup = Markup([[Btn("🔎 " + L("Buscar con los integrados", "Search with built-in sources"),
                                      callback_data=f"ts:fb:{fid}")]])
        else:
            text += L("Si pasa siempre, revisa Ajustes → Buscadores.", "If this keeps happening, check Settings → Search sources.")
        await status_msg.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
        return

    qid = uuid.uuid4().hex[:10]
    _search_cache[qid] = {
        "query": query, "results": results, "user_id": user_id,
        "filters": dict(DEFAULT_FILTERS),
    }
    if len(_search_cache) > 60:
        _search_cache.pop(next(iter(_search_cache)))

    card = await _tmdb_intro_card(query)
    if card:
        try:
            await status_msg.reply_photo(photo=card[0], caption=card[1], parse_mode=ParseMode.HTML)
        except Exception:
            pass

    text, markup = _render_results(qid, 0)
    await status_msg.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)


@authorized_only
async def search_fallback_callback(update, context):
    """«Search with built-in sources» after Prowlarr failed."""
    query = update.callback_query
    text = _fallback_queries.pop(query.data.split(":")[2], None)
    if not text:
        await query.answer(L("Esa búsqueda ha caducado, vuelve a buscar.", "That search expired, search again."), show_alert=True)
        return
    await query.answer()
    await query.edit_message_text(L("🔍 Buscando con los integrados ", "🔍 Searching built-in sources ")
                                  + f"<code>{html.escape(text)}</code>...", parse_mode=ParseMode.HTML)
    await _run_search(update.effective_user.id, text, "builtin", query.message)


async def _edit(query, text, markup):
    try:
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
    except Exception:
        pass


@authorized_only
async def search_page_callback(update, context):
    query = update.callback_query
    await query.answer()
    _, _, qid, page = query.data.split(":")
    text, markup = _render_results(qid, int(page))
    await _edit(query, text, markup)


@authorized_only
async def search_filters_callback(update, context):
    query = update.callback_query
    await query.answer()
    qid = query.data.split(":")[2]
    if qid not in _search_cache:
        text, markup = _render_results(qid)
    else:
        text, markup = _filters_content(qid)
    await _edit(query, text, markup)


def _next(options: list, current):
    return options[(options.index(current) + 1) % len(options)] if current in options else options[0]


@authorized_only
async def search_filter_change(update, context):
    query = update.callback_query
    await query.answer()
    _, _, qid, field = query.data.split(":")
    data = _search_cache.get(qid)
    if not data:
        text, markup = _render_results(qid)
        await _edit(query, text, markup)
        return
    f = data["filters"]
    if field == "res":
        f["res"] = _next(RES_OPTIONS, f["res"])
    elif field == "codec":
        f["codec"] = _next(CODEC_OPTIONS, f["codec"])
    elif field == "seeds":
        f["seeds"] = _next(SEEDS_OPTIONS, f["seeds"])
    elif field == "cached":
        f["cached"] = not f["cached"]
    elif field == "sort":
        f["sort"] = _next(SORT_OPTIONS, f["sort"])
    text, markup = _filters_content(qid)
    await _edit(query, text, markup)


@authorized_only
async def search_filter_reset(update, context):
    query = update.callback_query
    await query.answer()
    qid = query.data.split(":")[2]
    if qid in _search_cache:
        _search_cache[qid]["filters"] = dict(DEFAULT_FILTERS)
        text, markup = _filters_content(qid)
    else:
        text, markup = _render_results(qid)
    await _edit(query, text, markup)


@authorized_only
async def search_item_callback(update, context):
    query = update.callback_query
    await query.answer()
    _, _, qid, item_id = query.data.split(":")
    item = _item_cache.get(item_id)
    if not item:
        await query.answer(L("Este resultado ya no está disponible. Vuelve a buscar.", "This result is no longer available. Search again."), show_alert=True)
        return
    meta = item.get("meta", {})
    magnet = item.get("magnet") or ""
    info_hash = ""
    if magnet:
        import torbox
        info_hash = torbox.magnet_infohash(magnet) or ""
    cached = item.get("cached")
    pairs = [
        (L("Título", "Title"), esc(item.get("title", ""))),
        (L("Fuente", "Source"), esc(item.get("provider", ""))),
        (L("Tamaño", "Size"), esc(item.get("size", "?"))),
        ("🌱 Seeds / 👥 Peers", f"{item.get('seeders', 0)} / {item.get('leechers', 0)} {item.get('health', {}).get('icon', '')}"),
        (L("Resolución", "Resolution"), esc(meta.get("resolution", "N/D"))),
        (L("Fuente de vídeo", "Video source"), esc(meta.get("source", "—"))),
        (L("Códec", "Codec"), esc(meta.get("codec", "N/D")) + (f" · {esc(meta['hdr'])}" if meta.get("hdr") else "")),
        (L("Audio / idiomas", "Audio / languages"), esc(", ".join(meta.get("audio_features") or []) or "—") + (" · " + esc(" ".join(meta.get("languages") or [])) if meta.get("languages") else "")),
        (L("Puntuación", "Score"), f"⭐ {meta.get('quality_score', '?')}/10"),
        (L("Categoría", "Category"), esc(item.get("category", "—"))),
    ]
    if info_hash:
        pairs.append(("Hash", f"<code>{esc(info_hash)}</code>"))
    pairs.append(("TorBox", L("⚡ En caché (instantáneo)", "⚡ Cached (instant)") if cached else (L("No está en caché", "Not cached") if cached is False else L("Sin comprobar", "Not checked"))))
    text = rich(r_h(L("Ficha del torrent", "Torrent card"), 2, "🧲"), r_kv_table(pairs))
    kb = Markup([
        [Btn(("⚡ " if cached else "📥 ") + L("Descargar", "Download"), callback_data=f"ts:dl:{item_id}")],
        [Btn(L("⬅️ Resultados", "⬅️ Results"), callback_data=f"ts:page:{qid}:0")],
    ])
    await _edit(query, text, kb)


@authorized_only
async def search_download_callback(update, context):
    query = update.callback_query
    await query.answer()
    item_id = query.data.split(":", 2)[2]
    item = _item_cache.get(item_id)
    if not item:
        await query.answer(L("Este resultado ya no está en caché. Realiza la búsqueda de nuevo.", "This result is no longer cached. Search again."), show_alert=True)
        return
    status_msg = await query.message.reply_text(L("⏳ Obteniendo magnet / .torrent del resultado...", "⏳ Getting the magnet / .torrent of the result..."))
    source = await torrent_search.resolve_torrent_source(item)
    if not source:
        await status_msg.edit_text(L("❌ No se pudo extraer el enlace magnet ni el .torrent para este resultado.", "❌ Could not extract a magnet or .torrent for this result."))
        return
    kind, value = source
    import handlers_torbox
    await handlers_torbox.offer_source(status_msg, kind, value, update.effective_user.id)
