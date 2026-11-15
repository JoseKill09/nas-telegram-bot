/* Upgrades every <select> into a modern control:
   - up to 4 short options -> segmented pill control
   - otherwise            -> styled dropdown (opens a list; never the ugly native popup)
   The original <select> stays in the DOM (hidden) so existing code keeps working:
   we set its value and fire a normal "change" event. Add data-plain to opt out. */
(function () {
  "use strict";
  const enhanced = new Set();

  function labelOf(sel) {
    const o = sel.options[sel.selectedIndex];
    return o ? o.text : "";
  }

  function fire(sel) {
    sel.dispatchEvent(new Event("input", { bubbles: true }));
    sel.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function closeAll(except) {
    document.querySelectorAll(".ui-sel-list").forEach((l) => {
      if (l !== except) l.remove();
    });
    document.querySelectorAll(".ui-sel-btn.open").forEach((b) => {
      if (!except || b !== except._btn) b.classList.remove("open");
    });
  }

  function buildSegmented(sel, wrap) {
    const seg = document.createElement("div");
    seg.className = "ui-seg";
    seg.setAttribute("role", "radiogroup");
    [...sel.options].forEach((o, i) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "ui-seg-opt";
      b.textContent = o.text;
      b.setAttribute("role", "radio");
      b.addEventListener("click", () => {
        if (sel.selectedIndex === i) return;
        sel.selectedIndex = i;
        fire(sel);
        sync(sel);
      });
      seg.appendChild(b);
    });
    wrap.appendChild(seg);
    wrap._seg = seg;
  }

  function openList(sel, btn) {
    closeAll();
    const list = document.createElement("div");
    list.className = "ui-sel-list";
    list._btn = btn;
    [...sel.options].forEach((o, i) => {
      const it = document.createElement("button");
      it.type = "button";
      it.className = "ui-sel-item" + (i === sel.selectedIndex ? " active" : "");
      it.innerHTML = `<span></span><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>`;
      it.firstChild.textContent = o.text;
      it.addEventListener("click", (e) => {
        e.stopPropagation();
        sel.selectedIndex = i;
        fire(sel);
        sync(sel);
        closeAll();
      });
      list.appendChild(it);
    });
    document.body.appendChild(list);
    const r = btn.getBoundingClientRect();
    const width = Math.max(r.width, 180);
    list.style.minWidth = width + "px";
    const below = window.innerHeight - r.bottom - 12;
    const above = r.top - 12;
    const h = Math.min(list.scrollHeight, 320);
    if (below >= h || below >= above) {
      list.style.top = r.bottom + 6 + "px";
      list.style.maxHeight = Math.max(120, Math.min(320, below)) + "px";
    } else {
      list.style.bottom = window.innerHeight - r.top + 6 + "px";
      list.style.maxHeight = Math.max(120, Math.min(320, above)) + "px";
    }
    list.style.left = Math.max(8, Math.min(r.left, window.innerWidth - width - 8)) + "px";
    btn.classList.add("open");
    const act = list.querySelector(".active");
    if (act) act.scrollIntoView({ block: "nearest" });
  }

  function buildDropdown(sel, wrap) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "ui-sel-btn";
    btn.innerHTML = `<span class="ui-sel-label"></span><svg class="ui-sel-chev" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>`;
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      if (btn.classList.contains("open")) closeAll();
      else openList(sel, btn);
    });
    wrap.appendChild(btn);
    wrap._btn = btn;
  }

  function sync(sel) {
    const wrap = sel._wrap;
    if (!wrap) return;
    wrap.classList.toggle("hidden", sel.classList.contains("hidden"));
    wrap.classList.toggle("disabled", sel.disabled);
    if (wrap._seg) {
      [...wrap._seg.children].forEach((b, i) => {
        const on = i === sel.selectedIndex;
        if (sel.options[i] && b.textContent !== sel.options[i].text) b.textContent = sel.options[i].text;
        b.classList.toggle("active", on);
        b.setAttribute("aria-checked", on ? "true" : "false");
      });
    }
    if (wrap._btn) {
      wrap._btn.querySelector(".ui-sel-label").textContent = labelOf(sel);
      wrap._btn.disabled = sel.disabled;
    }
  }

  function enhance(sel) {
    if (sel.dataset.plain !== undefined || sel._wrap || sel.multiple || sel.size > 1) return;
    const opts = [...sel.options];
    if (!opts.length || !sel.parentNode) return;
    const wrap = document.createElement("span");
    wrap.className = "ui-sel";
    sel.parentNode.insertBefore(wrap, sel);
    wrap.appendChild(sel);
    sel.classList.add("ui-sel-native");
    sel.tabIndex = -1;
    sel._wrap = wrap;
    const short = opts.length <= 4 && opts.every((o) => o.text.length <= 20);
    if (short) buildSegmented(sel, wrap);
    else buildDropdown(sel, wrap);
    enhanced.add(sel);
    sync(sel);
  }

  function scan(root) {
    (root.querySelectorAll ? root.querySelectorAll("select") : []).forEach(enhance);
    if (root.tagName === "SELECT") enhance(root);
  }

  let queued = false;
  const obs = new MutationObserver((muts) => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      muts.forEach((m) => m.addedNodes.forEach((n) => n.nodeType === 1 && scan(n)));
    });
  });

  function init() {
    scan(document.body);
    obs.observe(document.body, { childList: true, subtree: true });
    document.addEventListener("click", () => closeAll());
    document.addEventListener("keydown", (e) => e.key === "Escape" && closeAll());
    window.addEventListener("resize", () => closeAll());
    document.addEventListener("scroll", () => closeAll(), true);
    // keeps controls in sync when code changes a select's value/visibility directly
    setInterval(() => {
      enhanced.forEach((sel) => {
        if (!sel.isConnected) enhanced.delete(sel);
        else sync(sel);
      });
    }, 500);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
