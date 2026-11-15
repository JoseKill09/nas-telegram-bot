import json
import os
import re

LANGS = {"en": "English", "es": "Español"}
DEFAULT_LANG = "en"

lang = DEFAULT_LANG

_LOCALE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "locales")
_catalog: dict[str, str] = {}
_exact: dict[str, str] = {}
_phrase_re: re.Pattern | None = None
_phrases: dict[str, str] = {}
_TAG_RE = re.compile(r"(<[^>]*>)")
_LETTER_RE = re.compile(r"[^\W\d_]", re.UNICODE)


def _load_catalog() -> None:
    global _catalog, _exact, _phrases, _phrase_re
    path = os.path.join(_LOCALE_DIR, "en.json")
    try:
        with open(path, encoding="utf-8") as fh:
            _catalog = json.load(fh)
    except (OSError, ValueError):
        _catalog = {}
    _exact = {k.strip(): v.strip() for k, v in _catalog.items()}
    _phrases = {k.strip(): v.strip() for k, v in _catalog.items() if len(k.strip()) >= 4}
    if _phrases:
        keys = sorted(_phrases, key=len, reverse=True)
        pattern = "|".join(
            (r"(?<![^\W_])" if k[0].isalnum() else "") + re.escape(k) + (r"(?![^\W_])" if k[-1].isalnum() else "")
            for k in keys
        )
        _phrase_re = re.compile(pattern)
    else:
        _phrase_re = None


def set_lang(code: str) -> None:
    global lang
    lang = code if code in LANGS else DEFAULT_LANG


def L(es: str, en: str) -> str:
    return en if lang == "en" else es


def _tr_segment(seg: str) -> str:
    if not seg or not _LETTER_RE.search(seg):
        return seg
    core = seg.strip()
    lead = seg[: len(seg) - len(seg.lstrip())]
    trail = seg[len(seg.rstrip()):]
    hit = _exact.get(core)
    if hit is not None:
        return lead + hit + trail
    if _phrase_re is None:
        return seg
    return _phrase_re.sub(lambda m: _phrases[m.group(0)], seg)


def tr(text):
    if lang != "en" or not isinstance(text, str) or not text:
        return text
    return "".join(p if p.startswith("<") and p.endswith(">") else _tr_segment(p) for p in _TAG_RE.split(text))


def tr_markup(markup):
    if lang != "en" or markup is None:
        return markup
    try:
        data = markup.to_dict()
    except Exception:
        return markup
    changed = False
    for key in ("inline_keyboard", "keyboard"):
        for row in data.get(key, []) or []:
            for btn in row:
                if isinstance(btn, dict) and isinstance(btn.get("text"), str):
                    new = tr(btn["text"])
                    if new != btn["text"]:
                        btn["text"] = new
                        changed = True
                elif isinstance(btn, str):
                    pass
    if not changed:
        return markup
    try:
        return type(markup).de_json(data, None)
    except Exception:
        return markup


def catalog_json() -> dict:
    return _catalog


_load_catalog()
