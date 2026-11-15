from html.parser import HTMLParser

from telegram import InlineKeyboardMarkup

_INLINE_TAGS = {"b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "code", "mark", "sub", "sup"}
_INLINE_TYPE = {
    "b": "bold", "strong": "bold",
    "i": "italic", "em": "italic",
    "u": "underline", "ins": "underline",
    "s": "strikethrough", "strike": "strikethrough", "del": "strikethrough",
    "code": "code", "mark": "marked", "sub": "subscript", "sup": "superscript",
}

_BLOCK_TAGS = {
    "p", "h1", "h2", "h3", "h4", "h5", "h6", "footer", "hr",
    "ul", "ol", "li", "table", "tr", "th", "td", "caption",
    "details", "summary", "blockquote", "br",
}


def _simplify_richtext(nodes: list) -> object:
    merged = []
    for n in nodes:
        if n == "" or n is None:
            continue
        if merged and isinstance(merged[-1], str) and isinstance(n, str):
            merged[-1] += n
        else:
            merged.append(n)
    if not merged:
        return ""
    if len(merged) == 1:
        return merged[0]
    return merged


class _RichBlockParser(HTMLParser):

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = {"blocks": []}
        self.stack = [self.root]
        self.inline_stack = []
        self.table_stack = []
        self.list_stack = []

    def _cur_container(self):
        return self.stack[-1]

    def _push_inline(self, tag=None):
        self.inline_stack.append({"parts": [], "tag": tag})

    def _pop_inline(self):
        frame = self.inline_stack.pop()
        text = _simplify_richtext(frame["parts"])
        if frame["tag"]:
            node = {"type": _INLINE_TYPE[frame["tag"]], "text": text} if text != "" else ""
        else:
            node = text
        if self.inline_stack:
            if node != "":
                self.inline_stack[-1]["parts"].append(node)
        return node

    def _add_block(self, block):
        self._cur_container()["blocks"].append(block)

    def handle_data(self, data):
        if self.inline_stack:
            self.inline_stack[-1]["parts"].append(data)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in _INLINE_TAGS:
            self._push_inline(tag)
            return
        if tag == "br":
            if self.inline_stack:
                self.inline_stack[-1]["parts"].append("\n")
            return
        if tag == "hr":
            self._add_block({"type": "divider"})
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._push_inline(None)
            self.inline_stack[-1]["size"] = int(tag[1])
            return
        if tag in ("p", "footer", "summary", "caption"):
            self._push_inline(None)
            return
        if tag == "blockquote":
            frame = {"blocks": []}
            self.stack.append(frame)
            return
        if tag == "details":
            self.stack.append({"blocks": [], "is_details": True, "is_open": "open" in attrs})
            self._push_inline(None)
            return
        if tag in ("ul", "ol"):
            self.list_stack.append({"items": [], "ordered": tag == "ol"})
            return
        if tag == "li":
            self._push_inline(None)
            return
        if tag == "table":
            self.table_stack.append({
                "rows": [], "cur_row": None, "caption": "",
                "is_bordered": "bordered" in attrs, "is_striped": "striped" in attrs,
            })
            return
        if tag == "tr":
            if self.table_stack:
                self.table_stack[-1]["cur_row"] = []
            return
        if tag in ("td", "th"):
            self._push_inline(None)
            self.inline_stack[-1]["is_header"] = (tag == "th")
            return

    def handle_endtag(self, tag):
        if tag in _INLINE_TAGS:
            if self.inline_stack:
                self._pop_inline()
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            frame = self.inline_stack.pop()
            text = _simplify_richtext(frame["parts"])
            self._add_block({"type": "heading", "text": text, "size": frame.get("size", 3)})
            return
        if tag in ("p", "footer"):
            frame = self.inline_stack.pop()
            text = _simplify_richtext(frame["parts"])
            if text != "":
                self._add_block({"type": "footer" if tag == "footer" else "paragraph", "text": text})
            return
        if tag == "caption":
            frame = self.inline_stack.pop()
            text = _simplify_richtext(frame["parts"])
            if self.table_stack:
                self.table_stack[-1]["caption"] = text
            return
        if tag == "summary":
            frame = self.inline_stack.pop()
            text = _simplify_richtext(frame["parts"])
            if self.stack and self.stack[-1].get("is_details"):
                self.stack[-1]["summary"] = text
            return
        if tag == "blockquote":
            frame = self.stack.pop()
            self._add_block({"type": "blockquote", "blocks": frame["blocks"]})
            return
        if tag == "details":
            frame = self.stack.pop()
            self._add_block({
                "type": "details",
                "summary": frame.get("summary", ""),
                "blocks": frame["blocks"],
                **({"is_open": True} if frame.get("is_open") else {}),
            })
            return
        if tag == "li":
            frame = self.inline_stack.pop()
            text = _simplify_richtext(frame["parts"])
            if self.list_stack:
                self.list_stack[-1]["items"].append({
                    "label": "", "blocks": [{"type": "paragraph", "text": text}] if text != "" else [],
                })
            return
        if tag in ("ul", "ol"):
            frame = self.list_stack.pop()
            self._add_block({"type": "list", "items": frame["items"]})
            return
        if tag in ("td", "th"):
            frame = self.inline_stack.pop()
            text = _simplify_richtext(frame["parts"])
            cell = {"text": text} if text != "" else {}
            if frame.get("is_header"):
                cell["is_header"] = True
            if self.table_stack and self.table_stack[-1]["cur_row"] is not None:
                self.table_stack[-1]["cur_row"].append(cell)
            return
        if tag == "tr":
            if self.table_stack and self.table_stack[-1]["cur_row"] is not None:
                self.table_stack[-1]["rows"].append(self.table_stack[-1]["cur_row"])
                self.table_stack[-1]["cur_row"] = None
            return
        if tag == "table":
            t = self.table_stack.pop()
            block = {"type": "table", "cells": t["rows"], "is_bordered": True, "is_striped": True}
            if t["caption"]:
                block["caption"] = t["caption"]
            self._add_block(block)
            return


def html_to_blocks(html_text: str) -> list[dict] | None:
    parser = _RichBlockParser()
    try:
        parser.feed(html_text or "")
        parser.close()
    except Exception:
        return None
    blocks = parser.root["blocks"]
    return blocks or None


# Button types that a RichMessageButton accepts (Bot API 10.3+). Exactly one of them per button.
_RICH_BUTTON_TYPES = (
    "callback_data", "url", "web_app", "login_url", "switch_inline_query",
    "switch_inline_query_current_chat", "switch_inline_query_chosen_chat", "copy_text",
)


class UnsupportedButton(ValueError):
    """An inline button whose type cannot be embedded (pay, callback_game…)."""


def keyboard_to_button_blocks(markup: InlineKeyboardMarkup) -> list[dict]:
    """Inline keyboard → button blocks (one block per row, at most 8 buttons per block).

    Raises UnsupportedButton instead of silently dropping a button: the caller then keeps the
    classic keyboard and every button is kept."""
    blocks = []
    for row in markup.inline_keyboard:
        for i in range(0, len(row), 8):
            buttons = []
            for btn in row[i:i + 8]:
                data = btn.to_dict()
                kind = next((k for k in _RICH_BUTTON_TYPES if data.get(k) is not None), None)
                if kind is None:
                    raise UnsupportedButton(btn.text)
                buttons.append({"text": btn.text, kind: data[kind]})
            if buttons:
                blocks.append({"type": "buttons", "buttons": buttons, "align": "left"})
    return blocks
