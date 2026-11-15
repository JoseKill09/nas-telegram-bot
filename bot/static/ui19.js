// NAS Downloader 19.0 — barra flotante, tema de Telegram, selección múltiple y copiar/mover.
(function () {
  "use strict";
  const tgw = window.Telegram ? window.Telegram.WebApp : null;

  // ---------- Tema (sigue al cliente de Telegram, en vivo) ----------
  function applyTheme() {
    const light = tgw ? tgw.colorScheme === "light" : !!(window.matchMedia && matchMedia("(prefers-color-scheme: light)").matches);
    document.documentElement.setAttribute("data-theme", light ? "light" : "dark");
    const p = (tgw && tgw.themeParams) || {};
    const root = document.documentElement.style;
    if (p.button_color && /^#[0-9a-f]{6}$/i.test(p.button_color)) {
      root.setProperty("--accent", p.button_color);
      root.setProperty("--accent-strong", p.button_color);
      root.setProperty("--accent-dim", p.button_color + (light ? "1a" : "2b"));
    }
    requestAnimationFrame(() => {
      const bg = getComputedStyle(document.documentElement).getPropertyValue("--bg").trim();
      try {
        if (tgw && bg) { tgw.setHeaderColor(bg); tgw.setBackgroundColor(bg); }
      } catch (e) { /* versiones antiguas */ }
    });
  }
  applyTheme();
  if (tgw) tgw.onEvent("themeChanged", applyTheme);
  if (window.matchMedia) {
    try { matchMedia("(prefers-color-scheme: light)").addEventListener("change", () => { if (!tgw) applyTheme(); }); } catch (e) {}
  }

  // ---------- Barra flotante ----------
  const NAV_ICONS = {
    queue: '<path d="M12 3v12m0 0l-4-4m4 4l4-4M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2"/>',
    search: '<path d="M11 4a7 7 0 100 14 7 7 0 000-14zm9 16l-4-4"/>',
    files: '<path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z"/>',
    history: '<path d="M12 3a9 9 0 100 18 9 9 0 000-18zm0 5v4l3 2"/>',
    settings: '<path d="M4 7h10M18 7h2M4 17h2M10 17h10M14 4v6M6 14v6"/>',
  };
  function buildNav() {
    const nav = document.querySelector("nav.tabs");
    if (!nav || nav.dataset.built) return;
    nav.dataset.built = "1";
    nav.setAttribute("role", "tablist");
    nav.querySelectorAll(".tab").forEach((b) => {
      const label = b.textContent.trim();
      b.setAttribute("aria-label", label);
      b.innerHTML =
        '<svg class="tab-ico" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
        (NAV_ICONS[b.dataset.tab] || "") + '</svg><span class="tab-lbl"><span>' + label + "</span></span>";
    });
  }
  buildNav();

  // ---------- Copiar / mover ----------
  const call = (p, o) => window.api(p, o);
  const esc = (s) => window.escapeHtml(s);
  const ic = (n, s) => window.icon(n, s);

  const cp = { items: [], srcFolder: "", policy: "skip", move: false, folder: null, path: "" };

  window.openCopyDialog = function (paths) {
    cp.items = paths.slice();
    cp.srcFolder = fm.folder;
    cp.policy = "skip";
    cp.move = false;
    cp.folder = null;
    cp.path = "";
    renderPicker();
  };

  async function renderPicker() {
    const n = cp.items.length;
    const head = '<h3>' + ic("copy", 18) + " Copiar a otra carpeta</h3>" +
      '<div class="nd-file">' + ic("copy", 20) + '<div><div class="nd-file-name">' + n + (n === 1 ? " elemento" : " elementos") +
      '</div><div class="nd-file-sub">' + esc(cp.items.length === 1 ? cp.items[0] : cp.srcFolder) + "</div></div></div>";
    let rows = "", crumb = "Raíz";
    if (cp.folder === null) {
      let folders = window.appFolders || [];
      try { folders = (await call("/api/state")).folders; } catch (e) {}
      rows = folders.map((f) => '<button type="button" class="folder-pick-row cp-row" data-folder="' + esc(f) + '" data-path=""><span class="file-icon folder-icon">' + ic("folder", 18) + "</span>" + esc(f) + "</button>").join("");
    } else {
      crumb = cp.path ? cp.folder + " / " + cp.path.split("/").join(" / ") : cp.folder;
      try {
        const d = await call("/api/files?folder=" + encodeURIComponent(cp.folder) + "&path=" + encodeURIComponent(cp.path) + "&sizes=0");
        rows = d.dirs.map((x) => {
          const np = cp.path ? cp.path + "/" + x.name : x.name;
          return '<button type="button" class="folder-pick-row cp-row" data-folder="' + esc(cp.folder) + '" data-path="' + esc(np) + '"><span class="file-icon folder-icon">' + ic("folder", 18) + "</span>" + esc(x.name) + "</button>";
        }).join("") || '<p class="empty" style="padding:12px 0;">Sin subcarpetas</p>';
      } catch (e) {
        rows = '<p class="modal-error">' + esc(e.message) + "</p>";
      }
    }
    const seg = (v, l) => '<button type="button" class="seg-btn' + (cp.policy === v ? " active" : "") + '" data-pol="' + v + '">' + l + "</button>";
    const body = head +
      '<div class="cp-crumb">' + esc(crumb) + "</div>" +
      '<div class="cp-list">' + rows + "</div>" +
      (cp.folder !== null ?
        '<div class="nd-field"><div class="nd-field-head"><span>Si ya existe un archivo con el mismo nombre</span></div>' +
        '<div class="seg">' + seg("skip", "Omitir") + seg("replace", "Reemplazar") + seg("rename", "Renombrar") + "</div></div>" +
        '<div class="option-row" style="margin-bottom:12px;"><div style="flex:1;padding-right:12px;"><div class="option-title">Mover en vez de copiar</div><div class="option-desc">Borra los originales al terminar</div></div>' +
        '<label class="toggle-switch"><input type="checkbox" id="cpMove"' + (cp.move ? " checked" : "") + '><span class="toggle-slider"></span></label></div>' : "") +
      '<div class="center-modal-footer">' +
      '<button class="btn btn-secondary" id="cpBack">' + ic("arrowLeft", 14) + (cp.folder === null ? " Cancelar" : cp.path ? " Atrás" : " Raíz") + "</button>" +
      (cp.folder !== null ? '<button class="btn btn-primary" id="cpGo">' + ic("copy", 14) + " <span id=\"cpGoText\">" + (cp.move ? "Mover aquí" : "Copiar aquí") + "</span></button>" : "") +
      "</div>";
    window.renderCenter(body);
    document.querySelectorAll(".cp-row").forEach((r) => r.addEventListener("click", () => {
      cp.folder = r.dataset.folder; cp.path = r.dataset.path; renderPicker();
    }));
    document.querySelectorAll(".seg-btn").forEach((b) => b.addEventListener("click", () => {
      cp.policy = b.dataset.pol;
      document.querySelectorAll(".seg-btn").forEach((x) => x.classList.toggle("active", x === b));
    }));
    const mv = document.getElementById("cpMove");
    if (mv) mv.addEventListener("change", () => {
      cp.move = mv.checked;
      document.getElementById("cpGoText").textContent = cp.move ? "Mover aquí" : "Copiar aquí";
    });
    document.getElementById("cpBack").addEventListener("click", () => {
      if (cp.folder === null) return window.closeCenterModal();
      if (cp.path) { const p = cp.path.split("/"); p.pop(); cp.path = p.join("/"); } else { cp.folder = null; }
      renderPicker();
    });
    const go = document.getElementById("cpGo");
    if (go) go.addEventListener("click", startCopy);
  }

  async function startCopy() {
    try {
      const r = await call("/api/files/copy", {
        method: "POST",
        body: JSON.stringify({ folder: cp.srcFolder, paths: cp.items, dest_folder: cp.folder, dest_path: cp.path, policy: cp.policy, move: cp.move }),
      });
      showProgress(r.job_id);
    } catch (e) { window.tgAlert(e.message); }
  }

  function showProgress(jobId) {
    window.renderCenter('<h3>' + ic("copy", 18) + ' <span id="cpTitle">Copiando…</span></h3>' +
      '<div class="cp-bar"><div class="cp-bar-fill" id="cpFill"></div></div>' +
      '<div class="cp-stat" id="cpStat">Preparando…</div><div class="cp-cur" id="cpCur"></div>' +
      '<div class="center-modal-footer"><button class="btn btn-secondary" id="cpStop">' + ic("x", 14) + " Cancelar</button></div>");
    let stopped = false;
    document.getElementById("cpStop").addEventListener("click", async () => {
      try { await call("/api/files/copy/" + jobId + "/cancel", { method: "POST" }); } catch (e) {}
    });
    const hs = (n) => { const u = ["B", "KB", "MB", "GB", "TB"]; let i = 0; while (n >= 1024 && i < 4) { n /= 1024; i++; } return n.toFixed(i ? 1 : 0) + " " + u[i]; };
    const tick = async () => {
      if (stopped) return;
      let j;
      try { j = await call("/api/files/copy/" + jobId); } catch (e) { return; }
      const fill = document.getElementById("cpFill");
      if (!fill) { stopped = true; return; }
      const pct = j.total ? Math.min(100, Math.round((j.done * 100) / j.total)) : 0;
      fill.style.width = pct + "%";
      const sp = j.done / Math.max(1, Date.now() / 1000 - j.started);
      document.getElementById("cpTitle").textContent = j.move ? "Moviendo…" : "Copiando…";
      document.getElementById("cpStat").textContent = pct + "% · " + hs(j.done) + " / " + hs(j.total) + " · " + hs(sp) + "/s";
      document.getElementById("cpCur").textContent = j.current || "";
      if (j.finished) {
        stopped = true;
        let msg = j.cancelled ? "Operación cancelada." : (j.copied + (j.move ? " movido(s)" : " copiado(s)") + " en " + j.dest + (j.skipped ? " · omitidos: " + j.skipped : ""));
        if (j.errors && j.errors.length) msg += "\n" + j.errors.slice(0, 3).join("; ");
        window.closeCenterModal();
        window.tgAlert(msg);
        if (fm.folder) window.loadFiles(fm.folder, fm.path);
        return;
      }
      setTimeout(tick, 1000);
    };
    tick();
  }

  // ---------- Selección múltiple en Archivos ----------
  const sel = { on: false, names: new Set(), order: [], archives: new Set() };
  let bar = null;

  function ensureBar() {
    if (bar) return bar;
    bar = document.createElement("div");
    bar.className = "sel-bar hidden";
    bar.innerHTML =
      '<div class="sel-count" id="selCount"></div><div class="sel-actions">' +
      '<button type="button" id="selCopy" class="sel-act primary">' + ic("copy", 20) + "<span>Copiar</span></button>" +
      '<button type="button" id="selExtract" class="sel-act">' + ic("archive", 20) + "<span>Descomprimir</span></button>" +
      '<button type="button" id="selDelete" class="sel-act danger">' + ic("trash", 20) + "<span>Eliminar</span></button></div>";
    document.body.appendChild(bar);
    bar.querySelector("#selCopy").addEventListener("click", () => window.openCopyDialog(paths()));
    bar.querySelector("#selExtract").addEventListener("click", () => {
      const n = [...sel.names].find((x) => sel.archives.has(x));
      if (n) { exitSel(); window.openExtractDialog(n); }
    });
    bar.querySelector("#selDelete").addEventListener("click", async () => {
      const list = paths();
      if (!list.length) return;
      if (!(await window.confirmModal("¿Eliminar " + list.length + " elemento(s)? Esta acción no se puede deshacer."))) return;
      try {
        for (const p of list) await call("/api/files/delete", { method: "POST", body: JSON.stringify({ folder: fm.folder, path: p }) });
      } catch (e) { window.tgAlert(e.message); }
      exitSel();
      window.loadFiles(fm.folder, fm.path);
    });
    return bar;
  }
  function paths() {
    return [...sel.names].map((n) => (fm.path ? fm.path + "/" + n : n));
  }
  function refreshBar() {
    const b = ensureBar();
    const n = sel.names.size;
    b.classList.toggle("hidden", !sel.on);
    document.body.classList.toggle("sel-mode", sel.on);
    b.querySelector("#selCount").textContent = n + (n === 1 ? " seleccionado" : " seleccionados");
    b.querySelector("#selCopy").disabled = n === 0;
    b.querySelector("#selDelete").disabled = n === 0;
    b.querySelector("#selExtract").classList.toggle("hidden", !(n === 1 && [...sel.names].every((x) => sel.archives.has(x))));
    const t = document.getElementById("selToggle");
    if (t) { t.textContent = sel.on ? "Cancelar" : "Seleccionar"; t.classList.toggle("cancel", sel.on); }
  }
  function exitSel() {
    sel.on = false; sel.names.clear();
    document.querySelectorAll("#fileList .file-row").forEach((r) => r.classList.remove("selected"));
    refreshBar();
    document.getElementById("fileList").classList.remove("selecting");
  }

  const origRender = window.renderFileList;
  window.renderFileList = function (data) {
    origRender(data);
    sel.names.clear(); sel.archives = new Set(data.files.filter((f) => window.isArchiveFilename(f.name)).map((f) => f.name));
    const entries = data.dirs.map((d) => d.name).concat(data.files.map((f) => f.name));
    const rows = document.querySelectorAll("#fileList .file-row");
    rows.forEach((row, i) => {
      const name = entries[i];
      if (name === undefined) return;
      row.insertAdjacentHTML("afterbegin", '<span class="sel-check" aria-hidden="true">' + ic("check", 14) + "</span>");
      // Pulsación prolongada: entra en selección con este elemento marcado
      let lpT = null, lpDone = false, lpX = 0, lpY = 0;
      const lpClear = () => { if (lpT) { clearTimeout(lpT); lpT = null; } };
      row.addEventListener("pointerdown", (ev) => {
        lpDone = false; lpX = ev.clientX; lpY = ev.clientY; lpClear();
        lpT = setTimeout(() => {
          lpT = null; lpDone = true;
          if (!sel.on) { sel.on = true; document.getElementById("fileList").classList.add("selecting"); }
          if (!sel.names.has(name)) sel.names.add(name);
          row.classList.add("selected");
          if (tgw && tgw.HapticFeedback) tgw.HapticFeedback.impactOccurred("medium");
          refreshBar();
        }, 450);
      });
      row.addEventListener("pointermove", (ev) => { if (Math.abs(ev.clientX - lpX) > 8 || Math.abs(ev.clientY - lpY) > 8) lpClear(); });
      ["pointerup", "pointercancel", "pointerleave"].forEach((e2) => row.addEventListener(e2, lpClear));
      row.addEventListener("contextmenu", (ev) => ev.preventDefault());
      row.addEventListener("click", (ev) => {
        if (lpDone) { lpDone = false; ev.stopImmediatePropagation(); ev.preventDefault(); return; }
        if (!sel.on) return;
        ev.stopImmediatePropagation(); ev.preventDefault();
        if (sel.names.has(name)) sel.names.delete(name); else sel.names.add(name);
        row.classList.toggle("selected", sel.names.has(name));
        refreshBar();
      }, true);
    });
    // Mantiene la barra de selección coherente tras recargar
    const list = document.getElementById("fileList");
    list.classList.toggle("selecting", sel.on);
    ensureToggle();
    refreshBar();
  };

  function ensureToggle() {
    let t = document.getElementById("selToggle");
    if (!t) {
      t = document.createElement("button");
      t.id = "selToggle"; t.type = "button"; t.className = "sel-toggle";
      t.addEventListener("click", () => {
        if (sel.on) return exitSel();
        sel.on = true; document.getElementById("fileList").classList.add("selecting"); refreshBar();
      });
      const bc = document.getElementById("breadcrumb");
      bc.parentNode.insertBefore(t, bc.nextSibling);
    }
    t.classList.toggle("hidden", !fm.folder);
  }
  document.addEventListener("click", (e) => {
    if (e.target.closest(".tab")) { if (sel.on) exitSel(); }
  });


  // ---------- Deslizadores con burbuja ----------
  function enhanceRanges(root) {
    (root || document).querySelectorAll('input[type="range"]:not([data-rng])').forEach((inp) => {
      inp.dataset.rng = "1";
      const wrap = document.createElement("div");
      wrap.className = "rng";
      inp.parentNode.insertBefore(wrap, inp);
      const bub = document.createElement("span");
      bub.className = "rng-bubble";
      wrap.appendChild(bub);
      wrap.appendChild(inp);
      const upd = () => {
        const min = +inp.min || 0, max = +inp.max || 100, v = +inp.value;
        const pct = max > min ? ((v - min) / (max - min)) * 100 : 0;
        wrap.style.setProperty("--p", pct + "%");
        // 14px = mitad del pulgar: la burbuja sigue al pulgar real
        bub.style.left = "calc(" + pct + "% + " + (14 - pct * 0.28) + "px)";
        bub.textContent = inp.value;
      };
      inp.addEventListener("input", () => { upd(); if (tgw && tgw.HapticFeedback) tgw.HapticFeedback.selectionChanged(); });
      inp.addEventListener("pointerdown", () => wrap.classList.add("drag"));
      ["pointerup", "pointercancel", "blur"].forEach((ev) => inp.addEventListener(ev, () => wrap.classList.remove("drag")));
      upd();
      // los valores se rellenan después de crear el control
      setTimeout(upd, 150); setTimeout(upd, 800);
    });
  }
  enhanceRanges();
  new MutationObserver(() => enhanceRanges()).observe(document.body, { childList: true, subtree: true });


  // ---------- Cabeceras grandes por sección ----------
  const TITLES = { queue: "Descargas", search: "Buscar", files: "Archivos", history: "Historial", settings: "Ajustes" };
  let sectionTitle = "";
  function setTitle(tab) {
    const h = document.getElementById("pageTitle");
    if (h) h.textContent = (tab === "settings" && sectionTitle) ? sectionTitle : (TITLES[tab] || "Descargas");
    const dc = document.getElementById("diskChip");
    if (dc) dc.style.display = tab === "queue" ? "" : "none";
    const fab = document.getElementById("fabAdd");
    if (fab) fab.classList.toggle("fab-off", tab !== "queue" && tab !== "files");
  }
  const origActivate = window.activateTab;
  window.activateTab = function (name) {
    origActivate(name);
    setTitle(name);
  };
  document.querySelectorAll(".tab").forEach((b) => b.addEventListener("click", () => setTitle(b.dataset.tab)));
  setTitle("queue");

  // ---------- Ajustes: lista con iconos de colores ----------
  const SET_STYLE = {
    language: ["#3390ec", "M12 3a9 9 0 100 18 9 9 0 000-18zM3 12h18M12 3c2.5 2.5 4 5.5 4 9s-1.5 6.5-4 9c-2.5-2.5-4-5.5-4-9s1.5-6.5 4-9z"],
    folders: ["#c26f0e", "M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z"],
    limits: ["#2f7fd6", "M4 7h10M18 7h2M4 17h2M10 17h10M14 4v6M6 14v6"],
    userbot: ["#7a5cd6", "M12 4v3M7 9h10a3 3 0 013 3v4a3 3 0 01-3 3H7a3 3 0 01-3-3v-4a3 3 0 013-3zM9 13h.01M15 13h.01"],
    providers: ["#1a8a5c", "M3 7h18v12H3zM3 11h18"],
    sources: ["#d6542f", "M11 4a7 7 0 100 14 7 7 0 000-14zm9 16l-4-4"],
    gdrive: ["#2e9d4a", "M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z"],
    tmdb: ["#0f9db0", "M5 4h14v16H5zM9 4v16M15 4v16"],
    notifications: ["#d69a1a", "M18 9a6 6 0 10-12 0c0 7-3 8-3 8h18s-3-1-3-8M10 21h4"],
    disk: ["#5b6472", "M4 14h16v5H4zM4 14l2-8h12l2 8"],
    rules: ["#b04fa6", "M4 6h16M4 12h10M4 18h6"],
    backup: ["#4a6fa5", "M12 3v12m0 0l-4-4m4 4l4-4M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2"],
    users: ["#c2578a", "M16 19v-1a4 4 0 00-4-4H8a4 4 0 00-4 4v1M10 11a3 3 0 100-6 3 3 0 000 6zM20 19v-1a4 4 0 00-3-3.9"],
  };
  function decorateSettings() {
    document.querySelectorAll(".settings-menu-item:not([data-deco])").forEach((el) => {
      el.dataset.deco = "1";
      const st = SET_STYLE[el.dataset.section] || ["#5b6472", "M5 12h14"];
      const title = el.querySelector(".card-title"), sub = el.querySelector(".card-sub");
      if (!title || !sub) return;
      const label = title.textContent.trim();
      const subTxt = sub.textContent.trim();
      el.classList.add("set-item");
      el.innerHTML = '<span class="set-tile" style="background:' + st[0] + '"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#fff" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="' + st[1] + '"/></svg></span>' +
        '<span class="set-text"><span class="set-title">' + label + '</span><span class="set-sub">' + subTxt + '</span></span>' +
        '<span class="set-chev"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg></span>';
    });
  }
  decorateSettings();

  // ---------- Ajustes: título de la sección, botón volver, buscador ----------
  const backBtn = document.getElementById("settingsBack");
  const tl = document.querySelector(".topbar-left");
  if (backBtn && tl) { backBtn.classList.add("in-top"); tl.insertBefore(backBtn, tl.firstChild); }
  function syncBack(open) {
    if (backBtn) backBtn.classList.toggle("show", !!open);
    document.body.classList.toggle("in-section", !!open);
  }
  syncBack(false);
  const origOpen = window.openSettingsSection;
  window.openSettingsSection = function (section) {
    const el = document.querySelector('.settings-menu-item[data-section="' + section + '"] .set-title');
    sectionTitle = el ? el.textContent.trim() : "";
    setTitle("settings"); syncBack(true);
    window.scrollTo(0, 0);
    return origOpen(section);
  };
  const origMenu = window.renderSettingsMenu;
  window.renderSettingsMenu = function () {
    sectionTitle = ""; setTitle("settings"); syncBack(false);
    return origMenu();
  };
  const sbox = document.getElementById("settingsSearch");
  if (sbox) sbox.addEventListener("input", () => {
    const q = sbox.value.trim().toLowerCase();
    let any = false;
    document.querySelectorAll("#settingsMenu .set-group").forEach((g) => {
      let n = 0;
      g.querySelectorAll(".settings-menu-item").forEach((it) => {
        const ok = !q || it.textContent.toLowerCase().includes(q);
        it.classList.toggle("hidden", !ok);
        if (ok) n++;
      });
      g.classList.toggle("hidden", n === 0);
      if (n) any = true;
    });
    const nm = document.getElementById("settingsNoMatch");
    if (nm) nm.classList.toggle("hidden", any);
  });

  // ---------- Campos numéricos con − / + ----------
  function enhanceSteppers() {
    document.querySelectorAll("#settingsSectionContent input[type=number]:not([data-stp])").forEach((inp) => {
      inp.dataset.stp = "1";
      const w = document.createElement("div");
      w.className = "stp";
      inp.parentNode.insertBefore(w, inp);
      const mk = (t, l) => { const b = document.createElement("button"); b.type = "button"; b.className = "stp-b"; b.setAttribute("aria-label", l); b.textContent = t; return b; };
      const m = mk("−", "Menos"), pl = mk("+", "Más");
      w.append(m, inp, pl);
      const step = (d) => {
        const st = +inp.step || 1, mn = inp.min !== "" ? +inp.min : -Infinity;
        const v = Math.max(mn, Math.round(((+inp.value || 0) + d * st) * 100) / 100);
        inp.value = v;
        inp.dispatchEvent(new Event("change", { bubbles: true }));
        if (tgw && tgw.HapticFeedback) tgw.HapticFeedback.selectionChanged();
      };
      m.addEventListener("click", () => step(-1));
      pl.addEventListener("click", () => step(1));
    });
  }
  enhanceSteppers();
  new MutationObserver(() => enhanceSteppers()).observe(document.getElementById("settingsSectionContent"), { childList: true, subtree: true });

  // ---------- Pestañas: aparición animada del texto ----------
  const mo = new MutationObserver(() => buildNav());
  mo.observe(document.body, { childList: true, subtree: true });
})();
