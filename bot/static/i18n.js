(function () {
  const state = { exact: new Map(), phrases: new Map(), re: null, on: false };
  const LETTER = /\p{L}/u;
  const SKIP = new Set(["SCRIPT", "STYLE", "TEXTAREA", "CODE"]);
  const ATTRS = ["placeholder", "title", "aria-label"];

  function esc(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function build(catalog) {
    for (const [k, v] of Object.entries(catalog)) {
      const key = k.trim();
      const val = String(v).trim();
      if (!key) continue;
      state.exact.set(key, val);
      if (key.length >= 4) state.phrases.set(key, val);
    }
    const keys = [...state.phrases.keys()].sort((a, b) => b.length - a.length);
    if (!keys.length) return;
    const parts = keys.map((k) => {
      const first = /[\p{L}\p{N}]/u.test(k[0]) ? "(?<![\\p{L}\\p{N}])" : "";
      const last = /[\p{L}\p{N}]/u.test(k[k.length - 1]) ? "(?![\\p{L}\\p{N}])" : "";
      return first + esc(k) + last;
    });
    state.re = new RegExp(parts.join("|"), "gu");
  }

  function tr(text) {
    if (!state.on || typeof text !== "string" || !text || !LETTER.test(text)) return text;
    const core = text.trim();
    const lead = text.slice(0, text.length - text.trimStart().length);
    const trail = text.slice(text.trimEnd().length);
    const hit = state.exact.get(core);
    if (hit !== undefined) return lead + hit + trail;
    if (!state.re) return text;
    return text.replace(state.re, (m) => state.phrases.get(m));
  }

  function walk(node) {
    if (node.nodeType === Node.TEXT_NODE) {
      const out = tr(node.nodeValue);
      if (out !== node.nodeValue) node.nodeValue = out;
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE || SKIP.has(node.tagName)) return;
    for (const a of ATTRS) {
      if (node.hasAttribute(a)) {
        const v = node.getAttribute(a);
        const out = tr(v);
        if (out !== v) node.setAttribute(a, out);
      }
    }
    node.childNodes.forEach(walk);
  }

  window.__tr = tr;

  fetch("/api/i18n")
    .then((r) => r.json())
    .then((info) => {
      document.documentElement.lang = info.lang;
      if (info.lang !== "en") return;
      build(info.catalog || {});
      state.on = true;
      document.title = tr(document.title);
      walk(document.body);
      new MutationObserver((muts) => {
        for (const m of muts) {
          if (m.type === "characterData") walk(m.target);
          else if (m.type === "attributes") walk(m.target);
          else m.addedNodes.forEach(walk);
        }
      }).observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS });
    })
    .catch(() => {});
})();
