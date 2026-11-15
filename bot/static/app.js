const tg = window.Telegram ? window.Telegram.WebApp : null;
const initData = tg ? tg.initData : "";

const fm = { folder: null, path: "" };

const ICONS = {
  folder: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z"/></svg>',
  video: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="6" width="14" height="12" rx="2"/><path d="m22 8-6 4 6 4V8Z"/></svg>',
  image: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/></svg>',
  document: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6"/></svg>',
  archive: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="4" rx="1"/><path d="M5 8v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8"/><path d="M10 12h4"/></svg>',
  audio: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>',
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>',
  x: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg>',
  trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>',
  star: '<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="m12 2 3.09 6.26L22 9.27l-5 4.87L18.18 21 12 17.77 5.82 21 7 14.14l-5-4.87 6.91-1.01L12 2Z"/></svg>',
  up: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M5 12l7-7 7 7"/></svg>',
  down: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M19 12l-7 7-7-7"/></svg>',
  pause: '<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></svg>',
  play: '<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M8 5v14l11-7L8 5Z"/></svg>',
  download: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12M6 11l6 6 6-6"/><path d="M5 21h14"/></svg>',
  bolt: '<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M13 2 3 14h7l-1 8 11-14h-7l1-6Z"/></svg>',
  box: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 8 12 3 3 8l9 5 9-5Z"/><path d="M3 8v8l9 5 9-5V8"/><path d="M12 13v8"/></svg>',
  lock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>',
  plug: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22v-5"/><path d="M9 8V2M15 8V2"/><path d="M18 8a2 2 0 0 1 2 2v2a8 8 0 0 1-8 8 8 8 0 0 1-8-8v-2a2 2 0 0 1 2-2h12Z"/></svg>',
  settings: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z"/></svg>',
  users: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
  card: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/></svg>',
  key: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="7.5" cy="15.5" r="5.5"/><path d="m21 2-9.6 9.6"/><path d="m15.5 7.5 3 3L22 7l-3-3"/></svg>',
  bot: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="9" width="18" height="11" rx="2"/><circle cx="8.5" cy="14.5" r="1.3" fill="currentColor" stroke="none"/><circle cx="15.5" cy="14.5" r="1.3" fill="currentColor" stroke="none"/><path d="M12 9V5M9 4h6"/></svg>',
  plus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14"/></svg>',
  info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>',
  broom: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m19 5-7 7"/><path d="M11 5 5 11l8 8 6-6"/><path d="M5 19l-2 2"/></svg>',
  crown: '<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M2 18h20l-2-9-5 4-3-7-3 7-5-4-2 9Z"/></svg>',
  person: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 21v-1a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v1"/></svg>',
  home: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/><path d="M9 22V12h6v10"/></svg>',
  pencil: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.85 2.85 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>',
  mail: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="m2 7 10 6 10-6"/></svg>',
  sprout: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 20h10M12 20v-8"/><path d="M12 12C7 12 5 9 5 5c4 0 7 2 7 7Z"/><path d="M12 12c0-4 3-6 7-6 0 4-2 7-7 7Z"/></svg>',
  gem: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h12l4 6-10 12L2 9Z"/><path d="M2 9h20M6 3l6 6 6-6M12 9v12"/></svg>',
  clock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg>',
  arrowLeft: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>',
  copy: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>',
  search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>',
  upload: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 21V9M6 13l6-6 6 6"/><path d="M5 3h14"/></svg>',
};

// «de» / «of» entre tamaño descargado y total (el catálogo no traduce palabras de menos de 4 letras)
function ofWord() {
  return document.documentElement.lang === "en" ? "of" : "de";
}

function icon(name, size) {
  const raw = ICONS[name] || "";
  return raw.replace("<svg ", `<svg width="${size || 18}" height="${size || 18}" `);
}

function hydrateStaticIcons() {
  document.querySelectorAll("[data-icon]").forEach((el) => {
    el.innerHTML = icon(el.dataset.icon, Number(el.dataset.iconSize) || 18);
  });
}

hydrateStaticIcons();

if (tg) {
  tg.ready();
  tg.expand();
}

if (!initData) {
  startBrowserMode();
} else {
  document.getElementById("app").classList.remove("hidden");
  initApp();
}

// Opened outside Telegram: allowed only with a local-network session (link sent by the bot with /web).
async function startBrowserMode() {
  try {
    const r = await fetch("/api/session", { credentials: "same-origin" });
    if (r.ok) {
      window.browserMode = true;
      document.documentElement.classList.add("browser-mode");
      document.getElementById("app").classList.remove("hidden");
      initApp();
      return;
    }
  } catch (e) { /* offline or server stopped */ }
  document.getElementById("blocked").classList.remove("hidden");
}

function initApp() {
  setupTheme();
  setupTabs();
  setupSwipeNavigation();
  setupYtdlTab();
  setupTorrentSearchTab();
  setupSettings();
  setupHistory();
  setupFileManager();
  setupAddTask();
  setupBackButton();
  document.getElementById("fabAdd").classList.remove("hidden");
  refreshQueue();
  setInterval(refreshQueue, 2000);
}

function setupBackButton() {
  if (!tg || !tg.BackButton) return;
  tg.BackButton.onClick(handleBackButtonClick);

  const observer = new MutationObserver(updateBackButton);
  const modalRoot = document.getElementById("modalRoot");
  const centerModalRoot = document.getElementById("centerModalRoot");
  if (modalRoot) observer.observe(modalRoot, { childList: true });
  if (centerModalRoot) observer.observe(centerModalRoot, { childList: true });

  updateBackButton();
}

function isAtRoot() {
  const modalOpen = document.getElementById("modalRoot").innerHTML.trim() !== "";
  const centerOpen = document.getElementById("centerModalRoot").innerHTML.trim() !== "";
  const inSubfolder = fm.folder !== null;
  const settingsSection = document.getElementById("settingsSection");
  const inSettingsSection = settingsSection && !settingsSection.classList.contains("hidden");
  const activeTab = document.querySelector(".tab.active");
  const onQueueTab = activeTab && activeTab.dataset.tab === "queue";
  return !modalOpen && !centerOpen && !inSubfolder && !inSettingsSection && onQueueTab;
}

function updateBackButton() {
  if (!tg || !tg.BackButton) return;
  if (isAtRoot()) {
    tg.BackButton.hide();
  } else {
    tg.BackButton.show();
  }
}

function handleBackButtonClick() {
  const modalRoot = document.getElementById("modalRoot");
  if (modalRoot.innerHTML.trim() !== "") {
    modalRoot.innerHTML = "";
    updateBackButton();
    return;
  }

  const centerModalRoot = document.getElementById("centerModalRoot");
  if (centerModalRoot.innerHTML.trim() !== "") {
    if (addTask.step === "options") {
      closeAddTask();
    } else if (addTask.step === "folder") {
      addTaskFolderBack();
    } else {
      closeAddTask();
    }
    updateBackButton();
    return;
  }

  const settingsSection = document.getElementById("settingsSection");
  if (settingsSection && !settingsSection.classList.contains("hidden")) {
    renderSettingsMenu();
    updateBackButton();
    return;
  }

  if (fm.folder !== null) {
    if (fm.path) {
      const parts = fm.path.split("/");
      parts.pop();
      loadFiles(fm.folder, parts.join("/"));
    } else {
      renderBreadcrumbRoots();
    }
    updateBackButton();
    return;
  }

  const activeTab = document.querySelector(".tab.active");
  if (activeTab && activeTab.dataset.tab !== "queue") {
    document.querySelector('.tab[data-tab="queue"]').click();
    updateBackButton();
  }
}

function isYtdlUrl(url) {
  const ytdlDomains = [
    "youtube.com", "youtu.be", "tiktok.com", "twitter.com", "x.com",
    "instagram.com", "twitch.tv", "vimeo.com", "reddit.com", "facebook.com",
    "fb.watch", "dailymotion.com", "threads.net", "bilibili.com", "vk.com",
    "pinterest.com", "pin.it", "streamable.com", "bsky.app"
  ];
  try {
    const hostname = new URL(url).hostname.replace("www.", "");
    return ytdlDomains.some(d => hostname.includes(d));
  } catch {
    return false;
  }
}

function setupTheme() {
  const apply = () => {
    const scheme = window.browserMode
      ? (window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark")
      : (tg && tg.colorScheme === "light" ? "light" : "dark");
    document.documentElement.setAttribute("data-theme", scheme);
  };
  apply();
  if (tg) {
    tg.onEvent("themeChanged", apply);
  }
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": initData,
      ...(options.headers || {}),
    },
  });
  if (res.status === 403) {
    document.getElementById("app").classList.add("hidden");
    document.getElementById("blocked").classList.remove("hidden");
    throw new Error("No autorizado");
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Error ${res.status}`);
  }
  return res.status === 204 ? null : res.json();
}

function setStatusDot(online) {
  document.getElementById("statusDot").classList.toggle("offline", !online);
}

const TAB_ORDER = ["queue", "search", "files", "history", "settings"];

function activateTab(tabName) {
  const btn = document.querySelector(`.tab[data-tab="${tabName}"]`);
  if (!btn || btn.classList.contains("hidden")) return;
  document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
  document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
  btn.classList.add("active");
  document.getElementById(`tab-${tabName}`).classList.add("active");

  if (tabName === "ytdl") refreshYtdlTasks();
  if (tabName === "history") loadHistory();
  if (tabName === "settings") renderSettingsMenu();
  updateBackButton();
}

function setupTabs() {
  document.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => activateTab(btn.dataset.tab));
  });
}

function setupSwipeNavigation() {
  const main = document.getElementById("mainContent");
  if (!main) return;

  let startX = 0;
  let startY = 0;
  let tracking = false;

  main.addEventListener("touchstart", (e) => {
    if (document.getElementById("modalRoot").innerHTML.trim() !== "") return;
    if (document.getElementById("centerModalRoot").innerHTML.trim() !== "") return;
    if (e.touches.length !== 1) return;

    if (e.target.closest(".provider-chips-container, .provider-chips-track, .chip-item, .filters-panel, .filter-chips, input[type='range'], textarea, input, select")) {
      tracking = false;
      return;
    }

    startX = e.touches[0].clientX;
    startY = e.touches[0].clientY;
    tracking = true;
  }, { passive: true });

  main.addEventListener("touchend", (e) => {
    if (!tracking) return;
    tracking = false;
    const endX = e.changedTouches[0].clientX;
    const endY = e.changedTouches[0].clientY;
    const dx = endX - startX;
    const dy = endY - startY;

    if (Math.abs(dx) < 65 || Math.abs(dx) < Math.abs(dy) * 1.6) return;

    const activeTab = document.querySelector(".tab.active");
    if (!activeTab) return;
    const visibleTabs = TAB_ORDER.filter((name) => {
      const btn = document.querySelector(`.tab[data-tab="${name}"]`);
      return btn && !btn.classList.contains("hidden");
    });
    const currentIndex = visibleTabs.indexOf(activeTab.dataset.tab);
    if (currentIndex === -1) return;

    if (dx < 0 && currentIndex < visibleTabs.length - 1) {
      activateTab(visibleTabs[currentIndex + 1]);
      if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred("light");
    } else if (dx > 0 && currentIndex > 0) {
      activateTab(visibleTabs[currentIndex - 1]);
      if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred("light");
    }
  }, { passive: true });
}

function defaultFolder() {
  const f = window.appFolders || [];
  return f.includes("Downloads") ? "Downloads" : f[0] || "Downloads";
}

const ytdlState = {
  currentUrl: "",
  info: null,
  selectedOption: null,
  selectedFolder: "",
  tasks: [],
};

let _ytdlFoldersPopulated = false;
function updateYtdlFolders(folders) {
  if (!folders || !folders.length) return;
  const container = document.getElementById("ytdlFolderChips");
  if (!container) return;
  if (_ytdlFoldersPopulated && container.children.length > 0) return;
  _ytdlFoldersPopulated = true;
  const current = ytdlState.selectedFolder || defaultFolder();
  container.innerHTML = "";
  folders.forEach((folder) => {
    const chip = document.createElement("button");
    chip.className = `f-chip ${folder === current ? "active" : ""}`;
    chip.dataset.folder = folder;
    chip.textContent = `📁 ${folder}`;
    chip.addEventListener("click", () => {
      container.querySelectorAll(".f-chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      ytdlState.selectedFolder = folder;
      if (tg && tg.HapticFeedback) tg.HapticFeedback.selectionChanged();
    });
    container.appendChild(chip);
  });
}

function setupYtdlTab() {
  const urlInput = document.getElementById("ytdlUrlInput");
  const analyzeBtn = document.getElementById("btnYtdlAnalyze");
  const downloadBtn = document.getElementById("btnYtdlStartDownload");
  const folderChips = document.getElementById("ytdlFolderChips");

  if (!urlInput || !analyzeBtn) return;

  analyzeBtn.addEventListener("click", () => handleYtdlAnalyze());
  urlInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") handleYtdlAnalyze();
  });

  if (folderChips) {
    folderChips.querySelectorAll(".f-chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        folderChips.querySelectorAll(".f-chip").forEach((c) => c.classList.remove("active"));
        chip.classList.add("active");
        ytdlState.selectedFolder = chip.dataset.folder || defaultFolder();
        if (tg && tg.HapticFeedback) tg.HapticFeedback.selectionChanged();
      });
    });
  }

  if (downloadBtn) {
    downloadBtn.addEventListener("click", () => handleYtdlDownload());
  }

  refreshYtdlTasks();
}

async function handleYtdlAnalyze() {
  const urlInput = document.getElementById("ytdlUrlInput");
  const analyzeBtn = document.getElementById("btnYtdlAnalyze");
  const previewCard = document.getElementById("ytdlPreviewCard");

  const url = (urlInput.value || "").trim();
  if (!url) {
    tgAlert("Pega un enlace de vídeo primero.");
    return;
  }

  analyzeBtn.disabled = true;
  analyzeBtn.innerHTML = `<span>⏳ Analizando...</span>`;

  try {
    const data = await api("/api/ytdl/info", {
      method: "POST",
      body: JSON.stringify({ url }),
    });

    if (!data.ok) throw new Error(data.detail || "Error al analizar el enlace");

    ytdlState.currentUrl = url;
    ytdlState.info = data;
    ytdlState.selectedOption = (data.options && data.options.length > 0) ? data.options[0] : null;

    document.getElementById("ytdlTitle").textContent = data.title || "Vídeo";
    const thumbImg = document.getElementById("ytdlThumb");
    if (data.thumbnail) {
      thumbImg.src = data.thumbnail;
      thumbImg.style.display = "block";
    } else {
      thumbImg.style.display = "none";
    }

    const durationBadge = document.getElementById("ytdlDurationBadge");
    if (data.duration_str) {
      durationBadge.textContent = data.duration_str;
      durationBadge.style.display = "block";
    } else {
      durationBadge.style.display = "none";
    }

    const platformEl = document.getElementById("ytdlPlatform");
    let domain = "";
    try {
      domain = new URL(url).hostname.replace("www.", "");
    } catch (e) {
      domain = "Web";
    }
    platformEl.textContent = `${domain} ${data.duration_str ? "· " + data.duration_str : ""}`;

    const optionsContainer = document.getElementById("ytdlOptionsList");
    optionsContainer.innerHTML = "";

    if (data.options && data.options.length > 0) {
      data.options.forEach((opt, idx) => {
        const chip = document.createElement("button");
        chip.className = `f-chip ${idx === 0 ? "active" : ""}`;
        chip.innerHTML = opt.is_audio ? `🎵 ${escapeHtml(opt.label)}` : `🎬 ${escapeHtml(opt.label)}`;
        chip.addEventListener("click", () => {
          optionsContainer.querySelectorAll(".f-chip").forEach((c) => c.classList.remove("active"));
          chip.classList.add("active");
          ytdlState.selectedOption = opt;
          if (tg && tg.HapticFeedback) tg.HapticFeedback.selectionChanged();
        });
        optionsContainer.appendChild(chip);
      });
    } else {
      optionsContainer.innerHTML = '<span class="hint-small">Formato estándar automático</span>';
      ytdlState.selectedOption = { format_spec: "bestvideo+bestaudio/best", is_audio: false };
    }

    previewCard.classList.remove("hidden");
    if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
  } catch (e) {
    tgAlert(e.message || "No se pudo analizar el enlace");
  } finally {
    analyzeBtn.disabled = false;
    analyzeBtn.innerHTML = `${icon("search", 16)} <span>Analizar</span>`;
  }
}

async function handleYtdlDownload() {
  const downloadBtn = document.getElementById("btnYtdlStartDownload");
  if (!ytdlState.currentUrl) return;

  const opt = ytdlState.selectedOption || { format_spec: "bestvideo+bestaudio/best", is_audio: false };

  downloadBtn.disabled = true;
  downloadBtn.innerHTML = `<span>⏳ Iniciando...</span>`;

  try {
    const res = await api("/api/ytdl/download", {
      method: "POST",
      body: JSON.stringify({
        url: ytdlState.currentUrl,
        format_spec: opt.format_spec,
        folder: ytdlState.selectedFolder || defaultFolder(),
        is_audio: !!opt.is_audio,
        title: (ytdlState.info && ytdlState.info.title) || "",
      }),
    });

    if (res && res.ok) {
      document.getElementById("ytdlPreviewCard").classList.add("hidden");
      document.getElementById("ytdlUrlInput").value = "";
      ytdlState.currentUrl = "";
      ytdlState.info = null;
      ytdlState.selectedOption = null;

      if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
      await refreshYtdlTasks();
    }
  } catch (e) {
    tgAlert(e.message || "Error al iniciar la descarga");
  } finally {
    downloadBtn.disabled = false;
    downloadBtn.innerHTML = `${icon("down", 16)} <span>Descargar al NAS</span>`;
  }
}

async function refreshYtdlTasks() {
  const listEl = document.getElementById("ytdlTasksList");
  const emptyEl = document.getElementById("ytdlEmptyTasks");
  if (!listEl) return;

  try {
    const data = await api("/api/ytdl/tasks");
    const tasks = data.tasks || [];
    ytdlState.tasks = tasks;

    if (emptyEl) {
      emptyEl.classList.toggle("hidden", tasks.length > 0);
    }

    listEl.innerHTML = "";
    for (const t of tasks) {
      const card = document.createElement("div");
      card.className = "card";

      const pct = t.pct != null ? t.pct : 0;
      let statusClass = "downloading";
      let statusText = "Descargando";
      if (t.status === "completed") {
        statusClass = "done";
        statusText = "Completado";
      } else if (t.status === "error") {
        statusClass = "error";
        statusText = "Error";
      }

      const mediaIcon = t.is_audio ? "🎵 Audio" : "🎬 Vídeo";
      const sizeInfo = t.total_mb > 0
        ? `${t.downloaded_mb || 0} MB / ${t.total_mb} MB`
        : (t.downloaded_mb > 0 ? `${t.downloaded_mb} MB` : "");

      const speedInfo = t.speed_mb > 0 ? ` · ${icon("bolt", 13)} ${t.speed_mb} MB/s` : "";

      card.innerHTML = `
        <div class="card-title">${escapeHtml(t.title || t.filename || "Vídeo")}</div>
        <div class="card-sub">
          <span class="badge ${statusClass}">${statusText}</span>
          &nbsp;${mediaIcon} · 📁 ${escapeHtml(t.folder || defaultFolder())}
          ${sizeInfo ? ` · ${sizeInfo}` : ""}
          ${speedInfo}
        </div>
        ${t.status === "downloading" ? `
          <div class="progress-track"><div class="progress-fill" style="width:${pct}%"></div></div>
        ` : ""}
        ${t.status === "error" && t.error ? `
          <div class="modal-error" style="margin-top:6px;font-size:12px;">${escapeHtml(t.error)}</div>
        ` : ""}
        <div class="card-actions">
          <button class="btn btn-secondary btn-del-ytdl">${icon("trash", 13)} Eliminar</button>
        </div>
      `;

      card.querySelector(".btn-del-ytdl").addEventListener("click", async () => {
        try {
          await api(`/api/ytdl/tasks/${t.id}`, { method: "DELETE" });
          refreshYtdlTasks();
        } catch (e) {
          tgAlert(e.message);
        }
      });

      listEl.appendChild(card);
    }
  } catch (e) {
  }
}

const searchState = {
  rawResults: [],
  filteredResults: [],
  page: 0,
  pageSize: 30,
  query: "",
  provider: "all",
  filters: {
    resolution: "all",
    codec: "all",
    language: "all",
    source: "all",
    hdr: false,
    atmos: false,
    is10bit: false,
    minScore: 1,
  },
};

function setupTorrentSearchTab() {
  const input = document.getElementById("torrentSearchInput");
  const searchBtn = document.getElementById("btnTorrentSearch");
  const loadMoreBtn = document.getElementById("btnSearchLoadMore");
  const chipContainer = document.querySelector(".provider-chips-container");
  const chipTrack = document.getElementById("providerChipsTrack");
  const toggleFiltersBtn = document.getElementById("btnToggleFilters");
  const filtersPanel = document.getElementById("searchFiltersPanel");
  const resetFiltersBtn = document.getElementById("btnResetFilters");
  const minScoreSlider = document.getElementById("filterMinScoreSlider");
  const minScoreLabel = document.getElementById("filterMinScoreLabel");

  if (chipContainer) {
    ["touchstart", "touchmove", "touchend"].forEach((evtName) => {
      chipContainer.addEventListener(evtName, (e) => {
        e.stopPropagation();
      }, { passive: true });
    });
  }

  searchBtn.addEventListener("click", () => triggerTorrentSearch());
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") triggerTorrentSearch();
  });

  const buildChips = (providers) => {
    const keep = searchState.provider;
    chipTrack.innerHTML = Object.entries(providers)
      .map(([k, label]) => `<button class="chip-item${k === keep ? " active" : ""}" data-provider="${escapeHtml(k)}">${escapeHtml(label)}</button>`)
      .join("");
    if (!chipTrack.querySelector(".chip-item.active")) {
      searchState.provider = "all";
      const first = chipTrack.querySelector(".chip-item");
      if (first) first.classList.add("active");
    }
  };
  setTimeout(() => {
    searchState.refreshProviders = () => api("/api/torrent/providers").then((d) => d && d.providers && buildChips(d.providers)).catch(() => {});
    searchState.refreshProviders();
  }, 0);

  chipTrack.addEventListener("click", (e) => {
    const chip = e.target.closest(".chip-item");
    if (!chip) return;
    e.stopPropagation();
    chipTrack.querySelectorAll(".chip-item").forEach((c) => c.classList.remove("active"));
    chip.classList.add("active");
    searchState.provider = chip.dataset.provider || "all";
    if (tg && tg.HapticFeedback) tg.HapticFeedback.selectionChanged();
    if (input.value.trim()) {
      triggerTorrentSearch();
    }
  });

  toggleFiltersBtn.addEventListener("click", () => {
    filtersPanel.classList.toggle("hidden");
    toggleFiltersBtn.classList.toggle("active", !filtersPanel.classList.contains("hidden"));
    if (tg && tg.HapticFeedback) tg.HapticFeedback.selectionChanged();
  });

  document.querySelectorAll(".f-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const type = chip.dataset.type;
      const val = chip.dataset.val;

      if (type === "extra") {
        chip.classList.toggle("active");
        if (val === "hdr") searchState.filters.hdr = chip.classList.contains("active");
        if (val === "atmos") searchState.filters.atmos = chip.classList.contains("active");
        if (val === "10bit") searchState.filters.is10bit = chip.classList.contains("active");
      } else {
        const parent = chip.parentElement;
        parent.querySelectorAll(".f-chip").forEach((c) => c.classList.remove("active"));
        chip.classList.add("active");

        if (type === "res") searchState.filters.resolution = val;
        if (type === "codec") searchState.filters.codec = val;
        if (type === "lang") searchState.filters.language = val;
        if (type === "source") searchState.filters.source = val;
      }

      updateActiveFiltersBadge();
      applyClientFilters();
      if (tg && tg.HapticFeedback) tg.HapticFeedback.selectionChanged();
    });
  });

  minScoreSlider.addEventListener("input", () => {
    const val = parseInt(minScoreSlider.value, 10);
    searchState.filters.minScore = val;
    minScoreLabel.textContent = val === 1 ? "Cualquiera" : `≥ ${val}.0 / 10 ⭐`;
    updateActiveFiltersBadge();
    applyClientFilters();
  });

  resetFiltersBtn.addEventListener("click", () => {
    resetAllFilters();
  });

  loadMoreBtn.addEventListener("click", () => {
    searchState.page += 1;
    renderSearchResultsPage();
  });
}

function updateActiveFiltersBadge() {
  const badge = document.getElementById("activeFiltersBadge");
  let count = 0;
  if (searchState.filters.resolution !== "all") count++;
  if (searchState.filters.codec !== "all") count++;
  if (searchState.filters.language !== "all") count++;
  if (searchState.filters.source !== "all") count++;
  if (searchState.filters.hdr) count++;
  if (searchState.filters.atmos) count++;
  if (searchState.filters.is10bit) count++;
  if (searchState.filters.minScore > 1) count++;

  if (count > 0) {
    badge.textContent = count;
    badge.classList.remove("hidden");
  } else {
    badge.classList.add("hidden");
  }
}

function resetAllFilters() {
  searchState.filters = {
    resolution: "all",
    codec: "all",
    language: "all",
    source: "all",
    hdr: false,
    atmos: false,
    is10bit: false,
    minScore: 1,
  };

  document.querySelectorAll(".f-chip").forEach((chip) => {
    const val = chip.dataset.val;
    if (val === "all") chip.classList.add("active");
    else chip.classList.remove("active");
  });

  const minScoreSlider = document.getElementById("filterMinScoreSlider");
  minScoreSlider.value = "1";
  document.getElementById("filterMinScoreLabel").textContent = "Cualquiera";

  updateActiveFiltersBadge();
  applyClientFilters();
  if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
}

function applyClientFilters() {
  if (!searchState.rawResults || searchState.rawResults.length === 0) return;

  const f = searchState.filters;

  searchState.filteredResults = searchState.rawResults.filter((item) => {
    const meta = item.meta || {};

    if (f.resolution !== "all" && meta.resolution !== f.resolution) return false;

    if (f.codec !== "all" && meta.codec !== f.codec) return false;

    if (f.language !== "all") {
      const langs = meta.languages || [];
      if (!langs.includes(f.language)) return false;
    }

    if (f.source === "no-cam") {
      if (meta.source === "CAM/TS") return false;
    } else if (f.source !== "all") {
      if (meta.source !== f.source) return false;
    }

    if (f.hdr && !meta.hdr) return false;
    if (f.atmos && !meta.is_atmos) return false;
    if (f.is10bit && !meta.is_10bit) return false;

    if (meta.quality_score < f.minScore) return false;

    return true;
  });

  searchState.page = 0;
  const meta = document.getElementById("searchMetaInfo");
  const count = searchState.filteredResults.length;
  const totalRaw = searchState.rawResults.length;

  if (count === 0) {
    meta.innerHTML = `⚠️ <b>0</b> resultados coinciden con los filtros aplicados (de ${totalRaw} encontrados).`;
  } else {
    const nCached = searchState.filteredResults.filter((i) => i.cached).length;
    meta.innerHTML = `✅ Mostrando <b>${count}</b> de <b>${totalRaw}</b> torrents tras aplicar filtros.` +
      (nCached ? ` · ⚡ <b>${nCached}</b> ya en TorBox (primeros)` : "");
  }

  document.getElementById("searchResultsList").innerHTML = "";
  renderSearchResultsPage();
}

async function triggerTorrentSearch() {
  const input = document.getElementById("torrentSearchInput");
  const query = input.value.trim();
  if (!query) return;

  const btn = document.getElementById("btnTorrentSearch");
  btn.disabled = true;

  const list = document.getElementById("searchResultsList");
  const empty = document.getElementById("searchEmptyState");
  const meta = document.getElementById("searchMetaInfo");
  const loadMoreBtn = document.getElementById("btnSearchLoadMore");

  list.innerHTML = "";
  empty.classList.add("hidden");
  meta.classList.remove("hidden");
  meta.innerHTML = `🔍 Buscando <b>${escapeHtml(query)}</b>...`;

  searchState.query = query;
  searchState.page = 0;
  searchState.rawResults = [];
  searchState.filteredResults = [];

  try {
    const data = await api(`/api/torrent/search?query=${encodeURIComponent(query)}&provider=${encodeURIComponent(searchState.provider)}`);
    searchState.rawResults = data.results || [];

    if (data.no_sources) {
      meta.innerHTML = window.isOwner
        ? `🔎 <b>No hay ningún buscador activo.</b> Los buscadores vienen apagados al instalar el bot: tú decides cuáles usar.<br><button type="button" class="btn btn-primary" id="btnEnableSources" style="margin-top:10px">Activar buscadores</button>`
        : `🔎 <b>No hay ningún buscador activo.</b> El administrador del bot todavía no ha activado ninguno.`;
      const go = document.getElementById("btnEnableSources");
      if (go) go.addEventListener("click", () => {
        document.querySelector('.tab[data-tab="settings"]').click();
        openSettingsSection("sources");
      });
      loadMoreBtn.classList.add("hidden");
    } else if (searchState.rawResults.length === 0) {
      meta.innerHTML = `❌ No se encontraron torrents para <b>${escapeHtml(query)}</b>.` + (data.prowlarr_error
        ? `<br>⚠️ Prowlarr no respondió: ${escapeHtml(data.prowlarr_error)}<br><button type="button" class="btn btn-secondary" id="btnSearchBuiltin" style="margin-top:10px">Buscar con los integrados</button>`
        : "");
      const fb = document.getElementById("btnSearchBuiltin");
      if (fb) fb.addEventListener("click", () => {
        const prev = searchState.provider;
        searchState.provider = "builtin";
        triggerTorrentSearch().finally(() => { searchState.provider = prev; });
      });
      loadMoreBtn.classList.add("hidden");
    } else {
      applyClientFilters();
      if (data.prowlarr_error) meta.innerHTML += `<br><span style="color:var(--yellow)">⚠️ Prowlarr no respondió (${escapeHtml(data.prowlarr_error)}); se muestran solo los buscadores integrados.</span>`;
    }
  } catch (e) {
    meta.innerHTML = `<span style="color:var(--red)">${escapeHtml(e.message)}</span>`;
    loadMoreBtn.classList.add("hidden");
  } finally {
    btn.disabled = false;
  }
}

function renderSearchResultsPage() {
  const list = document.getElementById("searchResultsList");
  const loadMoreBtn = document.getElementById("btnSearchLoadMore");

  const start = searchState.page * searchState.pageSize;
  const end = Math.min(start + searchState.pageSize, searchState.filteredResults.length);
  const slice = searchState.filteredResults.slice(start, end);

  for (const item of slice) {
    const card = document.createElement("div");
    card.className = "card torrent-card" + (item.cached ? " cached" : "");

    const health = item.health || {};
    const meta = item.meta || {};
    const qScore = meta.quality_score || 5.0;
    const qColor = meta.quality_color || "green";

    const tags = [];
    const isCached = !!item.cached;
    if (isCached) tags.push(`<span class="tag-badge tag-cached">⚡ En TorBox</span>`);
    if (meta.resolution && meta.resolution !== "N/D") tags.push(`<span class="tag-badge tag-res">${escapeHtml(meta.resolution)}</span>`);
    if (meta.source && meta.source !== "Unknown") tags.push(`<span class="tag-badge tag-src ${meta.source === 'CAM/TS' ? 'tag-warn' : ''}">${escapeHtml(meta.source)}</span>`);
    if (meta.codec && meta.codec !== "N/D") tags.push(`<span class="tag-badge tag-codec">${escapeHtml(meta.codec)}</span>`);
    if (meta.hdr) tags.push(`<span class="tag-badge tag-hdr">${escapeHtml(meta.hdr)}</span>`);
    if (meta.is_atmos) tags.push(`<span class="tag-badge tag-atmos">Atmos</span>`);
    if (meta.languages && meta.languages.length) {
      meta.languages.forEach((l) => tags.push(`<span class="tag-badge tag-lang">${escapeHtml(l)}</span>`));
    }

    const tagsHtml = tags.length ? `<div class="torrent-tags-row">${tags.join("")}</div>` : "";

    const healthBadge = `<span class="badge ${health.color === 'green' ? 'done' : (health.color === 'yellow' ? 'paused' : 'error')}">${health.icon || '🟢'} ${escapeHtml(health.label || 'Salud')}</span>`;
    const scoreBadge = `<span class="quality-score-badge ${qColor}">⭐ ${qScore}/10</span>`;

    const provIcon = "🏷️";
    const subDetails = `<b>${escapeHtml(item.size || "?")}</b> · ${provIcon} ${escapeHtml(item.provider || "Torrent")}<br>${icon("sprout", 13)} <b>${item.seeders || 0}</b> semillas · 👥 <b>${item.leechers || 0}</b> peers`;

    card.innerHTML = `
      <div class="card-title">${escapeHtml(item.title)}</div>
      ${tagsHtml}
      <div class="card-sub">
        ${scoreBadge} &nbsp;${healthBadge} &nbsp;${subDetails}
      </div>
      <div class="torrent-detail-panel hidden">
        <div class="torrent-detail-content">
          <div class="torrent-detail-label">Nombre del archivo:</div>
          <div class="torrent-detail-fulltitle">${escapeHtml(item.title)}</div>
          <div class="torrent-detail-grid">
            <div><b>Resolución:</b> ${escapeHtml(meta.resolution || 'N/D')}</div>
            <div><b>Fuente:</b> ${escapeHtml(meta.source || 'N/D')}</div>
            <div><b>Códec Vídeo:</b> ${escapeHtml(meta.codec || 'N/D')}</div>
            <div><b>Características:</b> ${escapeHtml(meta.hdr || (meta.is_10bit ? '10-bit' : 'SDR'))}</div>
            <div><b>Audio:</b> ${escapeHtml(meta.audio_features && meta.audio_features.length ? meta.audio_features.join(', ') : 'Estándar')}</div>
            <div><b>Idiomas:</b> ${escapeHtml(meta.languages && meta.languages.length ? meta.languages.join(', ') : 'Desconocido')}</div>
            <div><b>Puntuación Calidad:</b> <span style="font-weight:700;color:var(--${qColor})">${qScore} / 10</span></div>
            <div><b>Tamaño:</b> ${escapeHtml(item.size || "?")}</div>
            <div><b>Semillas / Pares:</b> 🌱 ${item.seeders || 0} / 👥 ${item.leechers || 0}</div>
            <div><b>Buscador:</b> ${escapeHtml(item.provider || "Torrent")}</div>
            <div><b>TorBox:</b> ${isCached ? "⚡ Ya en caché (descarga instantánea)" : "No está en caché"}</div>
          </div>
        </div>
      </div>
      <div class="card-actions">
        <button class="btn btn-primary btn-dl-torrent">${icon(isCached ? "bolt" : "download", 14)} Descargar al NAS</button>
        <button class="btn btn-secondary btn-toggle-details">${icon("info", 14)} Info</button>
      </div>
    `;

    const detailPanel = card.querySelector(".torrent-detail-panel");
    const toggleBtn = card.querySelector(".btn-toggle-details");

    const toggleDetails = () => {
      const isExpanded = !detailPanel.classList.contains("hidden");
      detailPanel.classList.toggle("hidden", isExpanded);
      card.classList.toggle("expanded", !isExpanded);
      toggleBtn.innerHTML = isExpanded ? `${icon("info", 14)} Info` : `${icon("x", 14)} Ocultar`;
      if (tg && tg.HapticFeedback) tg.HapticFeedback.selectionChanged();
    };

    card.addEventListener("click", (e) => {
      if (e.target.closest("button") || e.target.closest("input") || e.target.closest("a")) {
        return;
      }
      toggleDetails();
    });

    toggleBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleDetails();
    });

    card.querySelector(".btn-dl-torrent").addEventListener("click", (e) => {
      e.stopPropagation();
      startTorrentDownloadFromSearch(item);
    });

    list.appendChild(card);
  }

  if (end < searchState.filteredResults.length) {
    loadMoreBtn.classList.remove("hidden");
    loadMoreBtn.innerHTML = `${icon("down", 14)} Cargar más (${searchState.filteredResults.length - end} restantes)`;
  } else {
    loadMoreBtn.classList.add("hidden");
  }
}

async function startTorrentDownloadFromSearch(item) {
  renderCenter(`
    <h3>${icon("bolt", 18)} Obteniendo Enlace</h3>
    <p class="hint-small">Resolviendo enlace y preparando descarga...</p>
    <div id="torrentResolveProgress" style="text-align:center;padding:16px;">⏳ Conectando...</div>
  `);
  try {
    await prepareTorrent({
      magnet: item.magnet,
      details_url: item.details_url,
      torrent_file_url: item.torrent_file_url,
    });
  } catch (e) {
    showTorrentError(e.message);
  }
}

function showTorrentError(message) {
  renderCenter(`
    <h3>${icon("x", 18)} Error</h3>
    <p class="modal-error">${escapeHtml(message)}</p>
    <div class="center-modal-footer">
      <button class="btn btn-secondary" id="atErrClose">Cerrar</button>
    </div>
  `);
  document.getElementById("atErrClose").addEventListener("click", closeAddTask);
}

async function prepareTorrent(body) {
  const prep = await api("/api/torrent/prepare", { method: "POST", body: JSON.stringify(body) });
  await chooseTorrentProvider(prep);
}

async function chooseTorrentProvider(prep) {
  if (prep.providers.length === 1) {
    await addTorrentWithProvider(prep.key, prep.providers[0].id);
    return;
  }
  renderCenter(`
    <h3>${icon("download", 18)} ¿Con qué proveedor?</h3>
    <p class="hint-small" style="text-align:left;word-break:break-word;"><b>${escapeHtml(prep.name || "Torrent")}</b></p>
    <div style="display:flex;flex-direction:column;gap:8px;margin:12px 0;">
      ${prep.providers.map((p) => `<button class="btn btn-primary" data-prov="${escapeHtml(p.id)}">${escapeHtml(p.label)}</button>`).join("")}
    </div>
    <div class="center-modal-footer"><button class="btn btn-secondary" id="atProvCancel">Cancelar</button></div>
  `);
  document.getElementById("atProvCancel").addEventListener("click", closeAddTask);
  document.querySelectorAll("button[data-prov]").forEach((b) => {
    b.addEventListener("click", async () => {
      renderCenter(`
        <h3>${icon("bolt", 18)} Añadiendo...</h3>
        <div style="text-align:center;padding:16px;">⏳ Contactando con el proveedor...</div>
      `);
      try {
        await addTorrentWithProvider(prep.key, b.dataset.prov);
      } catch (e) {
        showTorrentError(e.message);
      }
    });
  });
}

async function addTorrentWithProvider(key, provider) {
  const data = await api("/api/torrent/add", { method: "POST", body: JSON.stringify({ key, provider }) });
  addTask.kind = "magnet";
  addTask.provider = data.provider;
  addTask.selectFiles = !!data.select_files;
  addTask.torrentId = data.torrent_id;
  addTask.torrentName = data.torrent_name;
  addTask.files = data.files;
  addTask.selected = new Set(data.selected);
  if (addTask.selectFiles) {
    renderFilesStep();
  } else {
    goOneScreen();
  }
}

const STATUS_LABEL = {
  downloading: "Procesando",
  paused: "Pausada",
  queued: "En cola",
  scheduled: "Programada",
  error: "Error",
  done: "Completada",
  cancelled: "Cancelada",
};

// ---- Solicitudes empezadas en el chat que esperan carpeta ----
let pendingSig = "";
async function refreshPending() {
  const box = document.getElementById("pendingBox");
  if (!box) return;
  let p;
  try { p = await api("/api/pending"); } catch (e) { return; }
  const busy = addTask.step ? new Set((addTask.taskIds || []).map(String)) : null;
  const tasks = (p.tasks || []).filter((t) => !busy || !busy.has(String(t.id)));
  const items = [];
  tasks.forEach((t) => items.push({ k: "t", id: t.id, name: t.filename, sub: t.size || (t.kind === "telegram" ? "Archivo de Telegram" : t.kind === "gdrive" ? "Google Drive" : "Enlace") }));
  (p.torrents || []).forEach((t) => items.push({ k: "r", id: t.torrent_id, name: t.name, sub: "Torrent" }));
  (p.sources || []).forEach((t) => items.push({ k: "s", id: t.key, name: t.name, sub: "Torrent" }));
  const sig = JSON.stringify(items) + (addTask.step ? "1" : "0");
  if (sig === pendingSig) return;
  pendingSig = sig;
  if (!items.length || addTask.step) { box.innerHTML = ""; return; }
  box.innerHTML = `<div class="pend">
    <div class="pend-head"><span class="pend-tile">${icon("download", 18)}</span><div><div class="pend-t">Pendiente de carpeta</div><div class="pend-s">Empezaste ${items.length === 1 ? "esta descarga" : "estas descargas"} en el chat</div></div></div>
    ${items.map((it, i) => `<div class="pend-row"><div class="pend-n"><div class="pend-name">${escapeHtml(it.name)}</div><div class="pend-sub">${escapeHtml(it.sub)}</div></div>
      <button type="button" class="btn btn-primary btn-sm" data-pi="${i}" data-pa="go">Elegir carpeta</button>
      <button type="button" class="pend-x" data-pi="${i}" data-pa="drop" aria-label="Descartar">${icon("x", 16)}</button></div>`).join("")}
  </div>`;
  box.querySelectorAll("[data-pa]").forEach((b) => b.addEventListener("click", () => {
    const it = items[+b.dataset.pi];
    if (b.dataset.pa === "go") resumePending(it, tasks);
    else dropPending(it);
  }));
}

async function dropPending(it) {
  try {
    await api("/api/pending/discard", { method: "POST", body: JSON.stringify(it.k === "t" ? { ids: [it.id] } : it.k === "s" ? { key: it.id } : { torrent_id: it.id }) });
  } catch (e) { tgAlert(e.message); }
  pendingSig = "";
  refreshPending();
}

async function resumePending(it, tasks) {
  try {
    if (it.k === "t") {
      closeAddTask();
      addTask.kind = "links";
      addTask.taskIds = [it.id];
      addTask.normalTaskIds = [it.id];
      addTask.taskInfos = [{ id: it.id, filename: it.name, size: it.sub && /\d/.test(it.sub) ? it.sub : null }];
      addTask.step = "options";
      goOneScreen();
    } else if (it.k === "r") {
      const data = await api("/api/pending/torrent/" + encodeURIComponent(it.id));
      closeAddTask();
      addTask.kind = "magnet";
      addTask.provider = data.provider;
      addTask.selectFiles = !!data.select_files;
      addTask.torrentId = data.torrent_id;
      addTask.torrentName = data.torrent_name;
      addTask.files = data.files;
      addTask.selected = new Set(data.selected);
      addTask.step = "options";
      if (addTask.selectFiles) renderFilesStep(); else goOneScreen();
    } else if (it.k === "s") {
      const prep = await api("/api/pending/source/" + encodeURIComponent(it.id));
      closeAddTask();
      addTask.step = "options";
      chooseTorrentProvider(prep);
    }
    pendingSig = "";
  } catch (e) {
    tgAlert(e.message);
  }
}

async function refreshQueue() {
  try {
    const state = await api("/api/state");
    setStatusDot(true);
    window.isOwner = !!state.is_owner;
    window.appFolders = state.folders || [];
    window.appFolderMedia = state.folder_media || {};
    document.getElementById("tabSettingsBtn").classList.toggle("hidden", !state.is_owner);
    window._lastRd = state.rd_torrents || [];
    renderTasks(state.tasks, window._lastRd);
    renderRdTorrents(state.rd_torrents);
    refreshPending();
    const dc = document.getElementById("diskChip");
    if (dc && state.disk_free) { dc.textContent = `${state.disk_free} libres`; dc.classList.remove("hidden"); }
    syncSliderValue("maxParallelTelegram", "maxParallelTelegramValue", state.max_parallel_telegram);
    syncSliderValue("maxParallelAria2", "maxParallelAria2Value", state.max_parallel_aria2);
    syncSliderValue("aria2Workers", "aria2WorkersValue", state.aria2_workers);
    syncSliderValue("maxParallelGdrive", "maxParallelGdriveValue", state.max_parallel_gdrive);
    document.getElementById("emptyState").classList.toggle(
      "hidden",
      state.tasks.length > 0 || state.rd_torrents.length > 0
    );

    if (state.folders && state.folders.length) {
      updateYtdlFolders(state.folders);
    }
    const activeTab = document.querySelector(".tab.active");
    if (activeTab && activeTab.dataset.tab === "ytdl") {
      refreshYtdlTasks();
    }
  } catch (e) {
    setStatusDot(false);
  }
}

const QUEUE_GROUPS = [
  { key: "extract", label: "Descompresión" },
  { key: "upload", label: "Subidas a Telegram" },
  { key: "gdrive", label: "Google Drive" },
  { key: "telegram", label: "Telegram" },
  { key: "link", label: "Aria2" },
  { key: "rd_link", label: "Real-Debrid (Torrents)" },
];

function queueGroupKey(kind) {
  if (kind === "extract") return "extract";
  if (kind === "upload") return "upload";
  if (kind === "gdrive" || kind === "telegram" || kind === "rd_link") return kind;
  return "link";
}

const CLIENT_FALLBACK = {
  link: "Aria2", rd_link: "Real-Debrid → Aria2", telegram: "Telegram (userbot)",
  gdrive: "Google Drive", ytdl: "yt-dlp", extract: "Descompresión", upload: "Subida (Userbot)",
};

function clientBadge(t) {
  const label = t.client_label || CLIENT_FALLBACK[t.kind] || "Aria2";
  const cls = `client-badge client-${escapeHtml(t.client || t.kind || "aria2")}`;
  return `<span class="${cls}">${escapeHtml(label)}</span>`;
}

let queueFilter = "all";
const queueSpeedHistory = [];

function parseSpeedMB(str) {
  if (!str) return 0;
  const m = /([\d.,]+)\s*([KMGT]?)i?B/i.exec(String(str));
  if (!m) return 0;
  const v = parseFloat(m[1].replace(",", "."));
  const mult = { "": 1 / 1048576, K: 1 / 1024, M: 1, G: 1024, T: 1048576 }[m[2].toUpperCase()] || 1;
  return v * mult;
}

function ringHtml(pct, color, inner) {
  const C = 2 * Math.PI * 27;
  const dash = `${((C * Math.max(0, Math.min(100, pct))) / 100).toFixed(1)} ${C.toFixed(1)}`;
  return `<div class="ring"><svg width="64" height="64" viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="27" fill="none" stroke="var(--track, #2a2d35)" stroke-width="6"/><circle class="ring-fill" cx="32" cy="32" r="27" fill="none" stroke="${color}" stroke-width="6" stroke-linecap="round" stroke-dasharray="${dash}" transform="rotate(-90 32 32)"/></svg><div class="ring-txt">${inner}</div></div>`;
}

function sparkPath(samples) {
  if (samples.length < 2) return "";
  const max = Math.max(...samples, 1);
  return samples.map((v, i) => `${i ? "L" : "M"}${((i / (samples.length - 1)) * 320).toFixed(1)} ${(32 - (v / max) * 28).toFixed(1)}`).join(" ");
}

function taskStateChip(t) {
  if (t.status === "scheduled") {
    let when = "Programada";
    if (t.scheduled_for) {
      const d = new Date(t.scheduled_for);
      if (!isNaN(d.getTime())) when = `Programada ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
    }
    return { text: when, cls: "chip-warn" };
  }
  if (t.kind === "extract" && t.status === "downloading") return { text: "Descomprimiendo", cls: "chip-warn" };
  if (t.status === "downloading") return { text: t.eta ? `Quedan ${t.eta}` : "Procesando", cls: "chip-ok" };
  if (t.status === "paused") return { text: "Pausada", cls: "chip-warn" };
  if (t.status === "queued") return { text: "En cola", cls: "chip-dim" };
  if (t.status === "error") return { text: "Error", cls: "chip-err" };
  return { text: STATUS_LABEL[t.status] || t.status, cls: "chip-dim" };
}

function taskActionsFor(t) {
  const acts = [];
  const isAria2 = t.kind !== "telegram" && t.kind !== "gdrive" && t.kind !== "extract";
  if (t.status === "scheduled") acts.push({ label: `${icon("play", 15)} Iniciar ya`, run: () => taskAction(t.id, "start_now") });
  if (isAria2 && t.status === "downloading") acts.push({ label: `${icon("pause", 15)} Pausar`, run: () => taskAction(t.id, "pause") });
  if (isAria2 && t.status === "paused") acts.push({ label: `${icon("play", 15)} Reanudar`, run: () => taskAction(t.id, "resume") });
  if (isAria2 && (t.status === "queued" || t.status === "paused")) acts.push({ label: `${icon("star", 15)} Priorizar`, run: () => taskAction(t.id, "prioritize") });
  if (!isAria2 && t.kind !== "extract" && t.status === "queued") {
    acts.push({ label: `${icon("up", 15)} Subir en la cola`, run: () => taskAction(t.id, "move_up") });
    acts.push({ label: `${icon("down", 15)} Bajar en la cola`, run: () => taskAction(t.id, "move_down") });
  }
  acts.push({ label: `${icon("x", 15)} Cancelar`, danger: true, run: () => taskAction(t.id, "cancel") });
  acts.push({ label: `${icon("trash", 15)} Forzar eliminación`, danger: true, run: () => forceRemoveTask(t.id) });
  return acts;
}

// Actualiza una lista sin reconstruirla: conserva los nodos que no cambian y
// parchea por dentro los que sí, para que el refresco no se note.
function reconcileList(list, nodes) {
  const old = new Map();
  [...list.children].forEach((c) => old.set(c.dataset.key, c));
  let ref = null;
  for (const n of nodes) {
    let use = old.get(n.dataset.key);
    if (use) {
      old.delete(n.dataset.key);
      if (use.dataset.sig !== n.dataset.sig && n.dataset.swap) {
        use.replaceWith(n);
        n.classList.add("no-anim");
        use = n;
      } else if (use.dataset.sig !== n.dataset.sig) {
        use.innerHTML = n.innerHTML;
        use.dataset.sig = n.dataset.sig;
        use._t = n._t;
        if (n.className !== use.className) use.className = n.className + " no-anim";
        const nb = n.querySelector(".ring-fill"), ob = use.querySelector(".ring-fill");
        if (nb && ob && nb.getAttribute("stroke-dasharray")) ob.setAttribute("stroke-dasharray", nb.getAttribute("stroke-dasharray"));
      }
    } else {
      use = n;
      if (list.dataset.ready) use.classList.add("is-new");
      else use.classList.add("no-anim");
    }
    const anchor = ref ? ref.nextSibling : list.firstChild;
    if (anchor !== use) list.insertBefore(use, anchor);
    ref = use;
  }
  old.forEach((c) => c.remove());
  list.dataset.ready = "1";
}

function renderTasks(tasks, rdTorrents) {
  const list = document.getElementById("taskList");
  const nodes = [];
  const visible = tasks.filter((t) => t.status !== "done" && t.status !== "cancelled");
  rdTorrents = rdTorrents || window._lastRd || [];
  window._lastTasks = tasks;

  const active = visible.filter((t) => t.status === "downloading");
  const waiting = visible.filter((t) => t.status === "queued" || t.status === "scheduled");
  const totalMB = active.reduce((s, t) => s + parseSpeedMB(t.speed), 0) + rdTorrents.reduce((s, r) => s + (r.speed || 0) / 1048576, 0);
  queueSpeedHistory.push(totalMB);
  if (queueSpeedHistory.length > 40) queueSpeedHistory.shift();

  const summary = document.createElement("div");
  summary.className = "dl-summary";
  summary.dataset.key = "sum";
  summary.innerHTML = `
    <div class="dl-summary-top">
      <div><div class="dl-summary-label">Velocidad total</div><div class="dl-summary-speed">${totalMB >= 10 ? totalMB.toFixed(0) : totalMB.toFixed(1)} MB/s</div></div>
      <div class="dl-summary-meta">${active.length + rdTorrents.length} activas · ${waiting.length} en cola</div>
    </div>
    <svg viewBox="0 0 320 36" preserveAspectRatio="none" class="dl-spark" role="img" aria-label="Velocidad reciente"><path d="${sparkPath(queueSpeedHistory)}" fill="none" stroke="var(--green)" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg>`;
  summary.dataset.sig = summary.innerHTML;
  nodes.push(summary);

  const filters = document.createElement("div");
  filters.className = "dl-filters";
  filters.dataset.key = "filters";
  filters.dataset.sig = queueFilter;
  filters.dataset.swap = "1";
  for (const [key, label] of [["all", "Todas"], ["active", "Activas"], ["queued", "En cola"]]) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "dl-filter" + (queueFilter === key ? " active" : "");
    b.textContent = label;
    b.addEventListener("click", () => { queueFilter = key; renderTasks(window._lastTasks || [], window._lastRd); });
    filters.appendChild(b);
  }
  nodes.push(filters);

  const shown = visible.filter((t) =>
    queueFilter === "all" ? true : queueFilter === "active" ? (t.status === "downloading" || t.status === "paused") : (t.status === "queued" || t.status === "scheduled"));

  for (const t of shown) {
    const card = document.createElement("div");
    card.className = "dl-card";
    card.dataset.key = "t" + t.id;
    card.dataset.sig = JSON.stringify(t);
    card._t = t;
    const pct = t.progress != null ? t.progress : 0;
    const color = t.status === "paused" ? "var(--yellow)" : t.status === "error" ? "var(--red)" : t.kind === "extract" ? "var(--yellow)" : "var(--accent)";
    const st = taskStateChip(t);
    const inner = t.status === "scheduled" ? icon("clock", 20) : t.status === "queued" ? icon("pause", 18) : `${Math.round(pct)}%`;
    const sizeChip = t.downloaded && t.size ? `${t.downloaded} ${ofWord()} ${t.size}` : (t.size || "");
    const label = t.client_label || CLIENT_FALLBACK[t.kind] || "Aria2";
    card.innerHTML = `
      ${ringHtml(t.status === "queued" || t.status === "scheduled" ? 0 : pct, color, inner)}
      <div class="dl-body">
        <div class="dl-name">${escapeHtml(t.filename)}</div>
        <div class="dl-dest">${escapeHtml(t.dest_folder || "")}</div>
        <div class="dl-chips">
          <span class="chip chip-prov">${escapeHtml(label)}</span>
          ${sizeChip ? `<span class="chip">${escapeHtml(sizeChip)}</span>` : ""}
          ${t.speed ? `<span class="chip">${escapeHtml(t.speed)}</span>` : ""}
          <span class="chip ${st.cls}">${escapeHtml(st.text)}</span>
          ${t.extract_after && t.kind !== "extract" ? `<span class="chip">${icon("archive", 11)} descomprimir</span>` : ""}
        </div>
      </div>
      <button type="button" class="dl-more" aria-label="Más acciones"><svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><circle cx="12" cy="5" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="12" cy="19" r="1.8"/></svg></button>`;
    card.addEventListener("click", (e) => {
      if (e.target.closest(".dl-more")) showActionSheet(card._t.filename, taskActionsFor(card._t));
    });
    nodes.push(card);
  }
  reconcileList(list, nodes);
}

function renderRdTorrents(torrents) {
  const list = document.getElementById("rdList");
  const title = document.getElementById("rdSectionTitle");
  const changed = JSON.stringify(window._lastRd || []) !== JSON.stringify(torrents);
  window._lastRd = torrents;
  if (changed && window._lastTasks) renderTasks(window._lastTasks, torrents);
  if (torrents.length === 0) {
    title.classList.add("hidden");
    reconcileList(list, []);
    return;
  }
  title.classList.remove("hidden");
  const rdNodes = [];
  for (const rt of torrents) {
    const card = document.createElement("div");
    card.className = "dl-card";
    card.dataset.key = "rd" + (rt.id || rt.name);
    card.dataset.sig = JSON.stringify(rt);
    const speedMb = rt.speed ? (rt.speed / (1024 * 1024)).toFixed(1) : "";
    const sizeLabel = rt.downloaded && rt.size ? `${rt.downloaded} ${ofWord()} ${rt.size}` : rt.size ? rt.size : "";
    card.innerHTML = `
      ${ringHtml(rt.progress || 0, "var(--accent)", `${Math.round(rt.progress || 0)}%`)}
      <div class="dl-body">
        <div class="dl-name">${escapeHtml(rt.name)}</div>
        <div class="dl-dest">${escapeHtml(rt.dest_folder || "")}</div>
        <div class="dl-chips">
          <span class="chip chip-prov">${rt.provider === "torbox" ? "TorBox" : "Real-Debrid"}</span>
          ${sizeLabel ? `<span class="chip">${escapeHtml(sizeLabel)}</span>` : ""}
          ${speedMb ? `<span class="chip">${speedMb} MB/s</span>` : ""}
          <span class="chip chip-ok">${escapeHtml(rt.eta ? "Quedan " + rt.eta : rt.status)}</span>
          ${rt.seeders ? `<span class="chip">${icon("sprout", 11)} ${rt.seeders}</span>` : ""}
        </div>
      </div>`;
    rdNodes.push(card);
  }
  reconcileList(list, rdNodes);
}

async function taskAction(id, action) {
  try {
    await api(`/api/tasks/${id}/${action}`, { method: "POST" });
    refreshQueue();
  } catch (e) {
    tgAlert(e.message);
  }
}

async function forceRemoveTask(id) {
  const confirmed = await confirmModal("¿Forzar la eliminación de esta tarea? Se quitará de la lista pase lo que pase.");
  if (!confirmed) return;
  try {
    await api(`/api/tasks/${id}/force_remove`, { method: "POST" });
    refreshQueue();
  } catch (e) {
    tgAlert(e.message);
  }
}

function makeBtn(label, cls, onClick) {
  const b = document.createElement("button");
  b.className = `btn ${cls}`;
  b.innerHTML = label;
  b.addEventListener("click", onClick);
  return b;
}

function setupSettings() {
  document.querySelectorAll(".settings-menu-item").forEach((el) => {
    el.addEventListener("click", () => openSettingsSection(el.dataset.section));
  });
  document.getElementById("settingsBack").addEventListener("click", () => renderSettingsMenu());
}

function renderSettingsMenu() {
  document.getElementById("settingsMenu").classList.remove("hidden");
  document.getElementById("settingsSection").classList.add("hidden");
  updateBackButton();
}

async function openSettingsSection(section) {
  document.getElementById("settingsMenu").classList.add("hidden");
  document.getElementById("settingsSection").classList.remove("hidden");
  updateBackButton();
  const content = document.getElementById("settingsSectionContent");

  if (section === "limits") {
    content.innerHTML = `
      <h2 class="section-title">Aria2 / Real-Debrid</h2>
      <div class="slider-card">
        <div class="slider-header">
          <label for="maxParallelAria2">Descargas simultáneas</label>
          <span class="slider-value" id="maxParallelAria2Value">1</span>
        </div>
        <input type="range" id="maxParallelAria2" min="1" max="4" step="1" value="1">
        <p class="hint">Cuántos enlaces (directos o resueltos por Real-Debrid) pueden descargarse a la vez.</p>
      </div>
      <div class="slider-card">
        <div class="slider-header">
          <label for="aria2Workers">Conexiones por descarga</label>
          <span class="slider-value" id="aria2WorkersValue">16</span>
        </div>
        <input type="range" id="aria2Workers" min="1" max="16" step="1" value="16">
        <p class="hint">Conexiones simultáneas que abre aria2 contra el mismo servidor. 16 es el máximo real de aria2.</p>
      </div>
      <h2 class="section-title">Telegram (userbot)</h2>
      <div class="slider-card">
        <div class="slider-header">
          <label for="maxParallelTelegram">Descargas simultáneas</label>
          <span class="slider-value" id="maxParallelTelegramValue">1</span>
        </div>
        <input type="range" id="maxParallelTelegram" min="1" max="4" step="1" value="1">
        <p class="hint">Cuántos archivos de Telegram pueden descargarse a la vez.</p>
      </div>
      <h2 class="section-title">Descompresión automática</h2>
      <div class="slider-card">
        <div class="slider-header">
          <label for="extractDelete">Eliminar el archivo original tras descomprimir</label>
          <span class="toggle-switch"><input type="checkbox" id="extractDelete"><span class="toggle-slider"></span></span>
        </div>
        <p class="hint">Solo afecta a las descargas que se descomprimen automáticamente al terminar. Descomprimir a mano desde Archivos nunca borra el original.</p>
      </div>
      <h2 class="section-title">Google Drive</h2>
      <div class="slider-card">
        <div class="slider-header">
          <label for="maxParallelGdrive">Descargas simultáneas</label>
          <span class="slider-value" id="maxParallelGdriveValue">1</span>
        </div>
        <input type="range" id="maxParallelGdrive" min="1" max="4" step="1" value="1">
        <p class="hint">Cuántos enlaces de Drive pueden descargarse a la vez (directo al NAS, sin Real-Debrid ni aria2).</p>
      </div>
    `;
    setupSlider("maxParallelAria2", "maxParallelAria2Value", "/api/settings/max_parallel_aria2");
    setupSlider("aria2Workers", "aria2WorkersValue", "/api/settings/aria2_workers");
    setupSlider("maxParallelTelegram", "maxParallelTelegramValue", "/api/settings/max_parallel_telegram");
    setupSlider("maxParallelGdrive", "maxParallelGdriveValue", "/api/settings/max_parallel_gdrive");
    try {
      const state = await api("/api/state");
      syncSliderValue("maxParallelAria2", "maxParallelAria2Value", state.max_parallel_aria2);
      syncSliderValue("aria2Workers", "aria2WorkersValue", state.aria2_workers);
      syncSliderValue("maxParallelTelegram", "maxParallelTelegramValue", state.max_parallel_telegram);
      syncSliderValue("maxParallelGdrive", "maxParallelGdriveValue", state.max_parallel_gdrive);
      const ex = document.getElementById("extractDelete");
      ex.checked = !!state.extract_delete_original;
      ex.addEventListener("change", async () => {
        try { await api("/api/settings/extract_delete_original", { method: "POST", body: JSON.stringify({ enabled: ex.checked }) }); }
        catch (e) { tgAlert(e.message); ex.checked = !ex.checked; }
      });
    } catch (e) {
    }
  } else if (section === "userbot") {
    content.innerHTML = `<div id="userbotCard" class="card-list"></div>`;
    loadUserbotInfo();
  } else if (section === "providers") {
    content.innerHTML = `<div id="providersCard" class="card-list"></div>`;
    loadProviders();
  } else if (section === "sources") {
    content.innerHTML = `<div id="sourcesCard" class="card-list"></div>`;
    loadSources();
  } else if (section === "tmdb") {
    content.innerHTML = `<div id="tmdbCard" class="card-list"></div>`;
    loadTmdbSettings();
  } else if (section === "users") {
    content.innerHTML = `<div id="usersCard" class="card-list"></div>`;
    loadUsers();
  } else if (section === "gdrive") {
    content.innerHTML = `<div id="gdriveCard" class="card-list"></div>`;
    loadGdriveStatus();
  } else if (section === "lan") {
    content.innerHTML = `<div id="lanCard" class="card-list"></div>`;
    loadLan().catch((e) => tgAlert(e.message));
  } else if (section === "language") {
    content.innerHTML = `<div id="languageCard" class="card-list"></div>`;
    loadLanguageSettings().catch((e) => tgAlert(e.message));
  } else if (section === "folders") {
    content.innerHTML = `<div id="foldersCard" class="card-list"></div>`;
    loadFolders().catch((e) => tgAlert(e.message));
  } else if (section === "notifications") {
    content.innerHTML = `<div id="notifCard" class="card-list"></div>`;
    loadNotifications().catch((e) => tgAlert(e.message));
  } else if (section === "disk") {
    content.innerHTML = `<div id="diskCard" class="card-list"></div>`;
    loadDisk().catch((e) => tgAlert(e.message));
  } else if (section === "rules") {
    content.innerHTML = `<div id="rulesCard" class="card-list"></div>`;
    loadRules().catch((e) => tgAlert(e.message));
  } else if (section === "backup") {
    content.innerHTML = `<div id="backupCard" class="card-list"></div>`;
    loadBackup().catch((e) => tgAlert(e.message));
  }
}

function setupSlider(inputId, valueId, endpoint) {
  const input = document.getElementById(inputId);
  const valueEl = document.getElementById(valueId);
  if (!input || !valueEl) return;

  const paint = () => {
    const min = Number(input.min), max = Number(input.max), val = Number(input.value);
    const pct = ((val - min) / (max - min)) * 100;
    valueEl.textContent = val;
  };

  input.addEventListener("input", paint);
  input.addEventListener("change", async () => {
    try {
      await api(endpoint, {
        method: "POST",
        body: JSON.stringify({ value: parseInt(input.value, 10) }),
      });
      if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred("light");
    } catch (e) {
      tgAlert(e.message);
    }
  });

  paint();
}

function syncSliderValue(inputId, valueId, value) {
  const input = document.getElementById(inputId);
  const valueEl = document.getElementById(valueId);
  if (!input || !valueEl) return;
  if (document.activeElement === input) return;
  input.value = value;
  const min = Number(input.min), max = Number(input.max);
  valueEl.textContent = value;
  input.dispatchEvent(new Event("input"));
}

const HISTORY_STATUS_LABEL = {
  done: `${icon("check", 13)} Completada`,
  cancelled: `${icon("x", 13)} Cancelada`,
  error: `${icon("x", 13)} Error`
};

let currentHistoryFilterUser = null;

let historyFilter = "all";

async function loadHistory(userId = currentHistoryFilterUser) {
  currentHistoryFilterUser = userId;
  const list = document.getElementById("historyList");
  const filterContainer = document.getElementById("historyUserFilterContainer");
  const chipsContainer = document.getElementById("historyUserChips");

  try {
    const url = userId !== null ? `/api/history?user_id=${encodeURIComponent(userId)}` : "/api/history";
    const data = await api(url);

    if (filterContainer && chipsContainer) {
      if (data.users && data.users.length > 0) {
        filterContainer.classList.remove("hidden");
        chipsContainer.innerHTML = "";

        const allChip = document.createElement("button");
        allChip.className = `dl-filter ${currentHistoryFilterUser === null ? "active" : ""}`;
        allChip.textContent = "Todos los usuarios";
        allChip.addEventListener("click", () => {
          loadHistory(null);
        });
        chipsContainer.appendChild(allChip);

        for (const u of data.users) {
          const chip = document.createElement("button");
          chip.className = `dl-filter ${currentHistoryFilterUser === u.id ? "active" : ""}`;
          chip.textContent = u.name;
          chip.addEventListener("click", () => {
            loadHistory(u.id);
          });
          chipsContainer.appendChild(chip);
        }
      } else {
        filterContainer.classList.add("hidden");
      }
    }

    list.innerHTML = "";
    if (data.history.length === 0) {
      list.innerHTML = `<p class="empty">Aún no hay nada en el historial${currentHistoryFilterUser !== null ? " para este usuario" : ""}.</p>`;
      return;
    }
    const hf = document.createElement("div");
    hf.className = "dl-filters";
    for (const [key, label] of [["all", "Todas"], ["done", "Completadas"], ["error", "Con error"]]) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "dl-filter" + (historyFilter === key ? " active" : "");
      b.textContent = label;
      b.addEventListener("click", () => { historyFilter = key; loadHistory(); });
      hf.appendChild(b);
    }
    list.appendChild(hf);
    for (const h of data.history.filter((x) => historyFilter === "all" || (historyFilter === "done" ? x.status === "done" : x.status !== "done"))) {
      const card = document.createElement("div");
      card.className = "hist-card";
      const ok = h.status === "done";
      const tileCls = ok ? "hist-ok" : h.status === "error" ? "hist-err" : "hist-dim";
      const tileIcon = ok ? icon("check", 20) : h.status === "error" ? icon("x", 20) : icon("clock", 20);
      const dateText = (h.created_at || "").replace("T", " ").slice(0, 16);
      const chips = [
        clientBadge(h).replace("client-badge", "chip chip-prov client-badge"),
        h.size ? `<span class="chip">${icon("box", 11)} ${escapeHtml(h.size)}</span>` : "",
        h.duration ? `<span class="chip">${icon("clock", 11)} ${escapeHtml(h.duration)}</span>` : "",
        h.avg_speed ? `<span class="chip">${icon("bolt", 11)} ${escapeHtml(h.avg_speed)}</span>` : "",
        `<span class="chip ${ok ? "chip-ok" : h.status === "error" ? "chip-err" : "chip-dim"}">${HISTORY_STATUS_LABEL[h.status] || escapeHtml(h.status)}</span>`,
      ].join("");
      const userText = h.user_name ? `<span class="chip">${icon("person", 11)} ${escapeHtml(h.user_name)}</span>` : "";
      const errorText = h.status === "error" && h.error ? `<div class="hist-error">${escapeHtml(h.error)}</div>` : "";
      card.innerHTML = `
        <div class="hist-tile ${tileCls}">${tileIcon}</div>
        <div class="dl-body">
          <div class="dl-name">${escapeHtml(h.filename)}</div>
          <div class="dl-dest">${escapeHtml(h.dest_folder || "")} · ${dateText}</div>
          <div class="dl-chips">${chips}${userText}</div>
          ${errorText}
        </div>
        <button type="button" class="dl-more" aria-label="Más acciones"><svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><circle cx="12" cy="5" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="12" cy="19" r="1.8"/></svg></button>`;
      card.querySelector(".dl-more").addEventListener("click", () => {
        const acts = [];
        if (h.url && !h.url.startsWith("/")) {
          acts.push({ label: `${icon("copy", 15)} Copiar enlace`, run: async () => {
            try { await navigator.clipboard.writeText(h.url); tgAlert("Enlace copiado al portapapeles."); }
            catch (err) { promptModal("Enlace", "Copia el enlace manualmente:", h.url); }
          } });
        }
        acts.push({ label: `${icon("trash", 15)} Borrar`, danger: true, run: () => deleteHistoryEntry(h.id) });
        showActionSheet(h.filename, acts);
      });
      list.appendChild(card);
    }
  } catch (e) {
    list.innerHTML = `<p class="empty">${escapeHtml(e.message)}</p>`;
  }
}

async function deleteHistoryEntry(id) {
  try {
    await api(`/api/tasks/${id}/force_remove`, { method: "POST" });
    loadHistory();
  } catch (e) {
    tgAlert(e.message);
  }
}

function setupHistory() {
  document.getElementById("btnClearHistory").addEventListener("click", async () => {
    const filterMsg = currentHistoryFilterUser !== null ? " seleccionado" : "";
    const confirmed = await confirmModal(`¿Borrar el historial${filterMsg}? Esta acción no se puede deshacer.`);
    if (!confirmed) return;
    try {
      const url = currentHistoryFilterUser !== null ? `/api/history/clear?user_id=${encodeURIComponent(currentHistoryFilterUser)}` : "/api/history/clear";
      await api(url, { method: "POST" });
      loadHistory();
    } catch (e) {
      tgAlert(e.message);
    }
  });
}

const PROVIDER_META = {
  realdebrid: { name: "Real-Debrid", tokenUrl: "real-debrid.com/apitoken", tokenApi: "/api/rd/token", deleteApi: "/api/rd/token/delete" },
  torbox: { name: "TorBox", tokenUrl: "torbox.app/settings (sección API)", tokenApi: "/api/tb/token", deleteApi: "/api/tb/token/delete" },
};

async function loadProviders() {
  const root = document.getElementById("providersCard");
  root.innerHTML = `<p class="empty">Consultando...</p>`;
  let data;
  try {
    data = await api("/api/providers");
  } catch (e) {
    root.innerHTML = `<p class="modal-error">${escapeHtml(e.message)}</p>`;
    return;
  }

  const rdAcc = data.realdebrid.account;
  const tbAcc = data.torbox.account;
  const detail = {
    realdebrid: rdAcc
      ? (rdAcc.type === "premium"
          ? `${icon("gem", 13)} ${escapeHtml(rdAcc.username || "")} · Premium — ${rdAcc.premium_days_left} día(s) (vence ${escapeHtml(rdAcc.expiration)})`
          : `${escapeHtml(rdAcc.username || "")} · Cuenta gratuita`)
      : "",
    torbox: tbAcc
      ? `${escapeHtml(tbAcc.email || "")} · Plan ${escapeHtml(tbAcc.plan)}${tbAcc.expiration ? ` (vence ${escapeHtml(tbAcc.expiration)})` : ""}`
      : "",
  };

  const PV_TILE = { realdebrid: "#7a5cd6", torbox: "#2f7fd6" };
  const stChip = (cfg, en) => !cfg ? `<span class="chip chip-dim">Sin token</span>` : en ? `<span class="chip chip-ok">Activado</span>` : `<span class="chip chip-err">Desactivado</span>`;
  const card = (id) => {
    const p = data[id];
    const meta = PROVIDER_META[id];
    return `
      <div class="pv">
        <div class="pv-head">
          <span class="pv-tile" style="background:${PV_TILE[id] || "#5b6472"}">${icon("card", 20)}</span>
          <div class="pv-t"><div class="pv-name">${escapeHtml(meta.name)}</div><div class="pv-sub">${detail[id] || (p.configured ? "Cuenta conectada" : "Aún no has añadido el token")}</div></div>
          ${stChip(p.configured, p.enabled)}
        </div>
        <div class="pv-actions">
          <button class="btn ${p.configured ? "btn-secondary" : "btn-primary"}" data-act="token" data-p="${id}">${icon("key", 14)} ${p.configured ? "Cambiar token" : "Configurar token"}</button>
          ${p.configured ? `<button class="btn btn-secondary" data-act="toggle" data-p="${id}">${p.enabled ? "Desactivar" : "Activar"}</button>
          <button class="btn btn-danger" data-act="delete" data-p="${id}">${icon("trash", 14)} Eliminar token</button>` : ""}
          ${id === "realdebrid" && p.configured ? `<button class="btn btn-danger" data-act="purge" data-p="realdebrid">${icon("broom", 14)} Vaciar cuenta RD</button>` : ""}
        </div>
      </div>`;
  };

  const clientKeys = Object.keys(data).filter((k) => data[k].client);
  const clientCard = (k) => {
    const c = data[k];
    return `
      <div class="pv">
        <div class="pv-head">
          <span class="pv-tile" style="background:#1a8a5c">${icon("download", 20)}</span>
          <div class="pv-t"><div class="pv-name">${escapeHtml(c.label)} (local)</div><div class="pv-sub"><code>${escapeHtml(c.url)}</code></div></div>
          ${c.enabled ? `<span class="chip chip-ok">Activado</span>` : `<span class="chip chip-err">Desactivado</span>`}
        </div>
        <label class="switch-row pv-row"><span>Seguir sembrando al terminar</span><span class="toggle-switch"><input type="checkbox" data-clact="seed" data-c="${k}" ${c.keep_seeding ? "checked" : ""}><span class="toggle-slider"></span></span></label>
        <div class="pv-actions">
          <button class="btn ${c.enabled ? "btn-secondary" : "btn-primary"}" data-clact="toggle" data-c="${k}">${c.enabled ? "Desactivar" : "Activar"}</button>
          <button class="btn btn-secondary" data-clact="conf" data-c="${k}">${icon("key", 14)} Conexión</button>
          <button class="btn btn-secondary" data-clact="test" data-c="${k}">Probar</button>
        </div>
        <div class="pv-note" id="clNote-${k}"></div>
      </div>`;
  };

  root.innerHTML = `
    <p class="hint-small">Al descargar un torrent, la app te preguntará qué proveedor usar (si tienes más de uno activado).</p>
    <h2 class="section-title">Servicios en la nube</h2>
    ${card("realdebrid")}
    ${card("torbox")}
    <div id="gdriveCard"></div>
    ${clientKeys.length ? `<h2 class="section-title">Clientes locales</h2>` : ""}
    ${clientKeys.map(clientCard).join("")}
  `;
  loadGdriveStatus();

  root.querySelectorAll("[data-clact]").forEach((btn) => {
    btn.addEventListener(btn.type === "checkbox" ? "change" : "click", async () => {
      const act = btn.dataset.clact;
      const k = btn.dataset.c;
      const c = data[k];
      const post = (b) => api(`/api/clients/${k}`, { method: "POST", body: JSON.stringify(b) });
      try {
        if (act === "toggle") {
          await api(`/api/providers/${k}/toggle`, { method: "POST", body: JSON.stringify({ enabled: !c.enabled }) });
          loadProviders();
        } else if (act === "seed") {
          await post({ keep_seeding: !c.keep_seeding });
          loadProviders();
        } else if (act === "test") {
          btn.disabled = true;
          const r = await api(`/api/clients/${k}/test`, { method: "POST" });
          document.getElementById(`clNote-${k}`).innerHTML = r.ok ? `<span class="chip chip-ok">${icon("check", 11)} ${escapeHtml(c.label)} ${escapeHtml(r.version)}</span>` : `<span class="chip chip-err">${icon("x", 11)} ${escapeHtml(r.error)}</span>`;
          btn.disabled = false;
        } else if (act === "conf") {
          const info = await api(`/api/clients/${k}`);
          const url = await promptModal(c.label, "Web UI URL", info.url);
          if (url === null) return;
          let user = "";
          if (info.needs_user) {
            user = await promptModal(c.label, "Usuario", info.user);
            if (user === null) return;
          }
          const pass = await promptModal(c.label, info.has_password ? "Contraseña (vacío = no cambiar)" : "Contraseña", "");
          if (pass === null) return;
          await post(info.needs_user ? { url, user, password: pass || "" } : { url, password: pass || "" });
          loadProviders();
        }
      } catch (e) {
        tgAlert(e.message);
        btn.disabled = false;
      }
    });
  });

  root.querySelectorAll("button[data-act]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.p;
      const act = btn.dataset.act;
      const meta = PROVIDER_META[id];
      try {
        if (act === "token") {
          openProviderTokenModal(id);
        } else if (act === "toggle") {
          await api(`/api/providers/${id}/toggle`, { method: "POST", body: JSON.stringify({ enabled: !data[id].enabled }) });
          loadProviders();
        } else if (act === "delete") {
          if (!(await confirmModal(`¿Eliminar el token de ${meta.name}? Se desactivará el proveedor.`))) return;
          await api(meta.deleteApi, { method: "POST" });
          loadProviders();
        } else if (act === "purge") {
          if (!(await confirmModal("¿Borrar TODOS los torrents y todo el historial de descargas de tu cuenta de Real-Debrid? Esta acción no se puede deshacer."))) return;
          btn.disabled = true;
          btn.textContent = "Vaciando...";
          const result = await api("/api/rd/purge", { method: "POST" });
          tgAlert(`Cuenta vaciada: ${result.torrents} torrent(s) y ${result.downloads} descarga(s) eliminados.`);
          loadProviders();
        }
      } catch (e) {
        tgAlert(e.message);
        btn.disabled = false;
      }
    });
  });
}

function sourceHost(u) {
  try { return new URL(u).host; } catch (e) { return u; }
}

function sourceTestLine(r) {
  if (!r) return "";
  return r.ok
    ? `<span style="color:var(--green)">✅ ${r.count} resultados en ${r.ms} ms · ${escapeHtml(sourceHost(r.base))}</span>`
    : `<span style="color:var(--red)">❌ ${escapeHtml(r.error || "sin respuesta")}</span>`;
}

async function loadLan(note = "") {
  const root = document.getElementById("lanCard");
  if (!root) return;
  const d = await api("/api/lan");
  const when = (t) => (t ? new Date(t * 1000).toLocaleString() : "—");
  root.innerHTML = `
    <div class="card">
      <div class="card-title">🏠 Acceso desde la red local</div>
      <div class="card-sub">Abre el panel en el navegador de tu casa (o desde fuera con tu propia VPN) sin Cloudflare ni dominio. Se entra con un enlace de un solo uso que caduca en 5 minutos; la sesión dura 30 días. Solo se instala como app si entras por HTTPS.<br>
        Estado: ${d.enabled ? "🟢 Activado" : "🔴 Desactivado"}${note ? `<br>${note}` : ""}</div>
      <div class="source-add"><input type="text" id="lanUrl" value="${escapeHtml(d.url || "")}" placeholder="http://192.168.1.50:8080"></div>
      <div class="card-actions" style="flex-wrap:wrap;">
        <button class="btn btn-secondary" data-act="lanurl">Guardar dirección</button>
        <button class="btn ${d.enabled ? "btn-secondary" : "btn-primary"}" data-act="lantoggle">${d.enabled ? "Desactivar" : "Activar"}</button>
        ${d.enabled && d.url ? `<button class="btn btn-primary" data-act="lanlink">🔗 Generar enlace de acceso</button>` : ""}
      </div>
    </div>
    <div class="card">
      <div class="card-title">Sesiones abiertas (${d.sessions.length})</div>
      ${d.sessions.length ? d.sessions.map((x) => `
        <div class="source-url"><span><b>${escapeHtml(x.name)}</b> · ${escapeHtml((x.agent || "—").slice(0, 40))} · ${when(x.last)}</span>
          <button class="btn btn-danger btn-sm" data-act="lanrev" data-id="${x.id}" title="Cerrar">${icon("trash", 12)}</button></div>`).join("")
        : `<div class="card-sub">Ninguna.</div>`}
      <div class="card-actions" style="flex-wrap:wrap;">
        ${d.sessions.length ? `<button class="btn btn-danger" data-act="lanrevall">Cerrar todas</button>` : ""}
        ${window.browserMode ? `<button class="btn btn-secondary" data-act="lanlogout">Cerrar sesión en este navegador</button>` : ""}
      </div>
    </div>`;
  root.querySelectorAll("button[data-act]").forEach((btn) => btn.addEventListener("click", async () => {
    const act = btn.dataset.act;
    try {
      if (act === "lanurl") {
        await api("/api/lan", { method: "POST", body: JSON.stringify({ url: document.getElementById("lanUrl").value.trim() }) });
        loadLan("💾 Dirección guardada");
      } else if (act === "lantoggle") {
        if (d.enabled && !(await confirmModal("¿Desactivar el acceso por red local? Se cerrarán todas las sesiones del navegador."))) return;
        await api("/api/lan", { method: "POST", body: JSON.stringify({ enabled: !d.enabled }) });
        loadLan();
      } else if (act === "lanlink") {
        const r = await api("/api/lan/link", { method: "POST" });
        loadLan(`🔗 Ábrelo en un navegador de tu red antes de 5 minutos (un solo uso):<br><code style="word-break:break-all">${escapeHtml(r.url)}</code>`);
      } else if (act === "lanrev") {
        await api("/api/lan/sessions/revoke", { method: "POST", body: JSON.stringify({ id: btn.dataset.id }) });
        loadLan();
      } else if (act === "lanrevall") {
        if (!(await confirmModal("¿Cerrar todas las sesiones del navegador?"))) return;
        await api("/api/lan/sessions/revoke", { method: "POST", body: JSON.stringify({ all: true }) });
        loadLan();
      } else if (act === "lanlogout") {
        await fetch("/api/session/logout", { method: "POST", credentials: "same-origin" });
        location.reload();
      }
    } catch (e) {
      tgAlert(e.message);
    }
  }));
}

async function loadSources(notes = {}) {
  const root = document.getElementById("sourcesCard");
  if (!root) return;
  if (!root.dataset.loaded) root.innerHTML = `<p class="empty">Consultando...</p>`;
  let data, px, pl;
  try {
    [data, px, pl] = await Promise.all([api("/api/sources"), api("/api/sources/proxy"), api("/api/prowlarr")]);
  } catch (e) {
    root.innerHTML = `<p class="modal-error">${escapeHtml(e.message)}</p>`;
    return;
  }
  root.dataset.loaded = "1";
  const proxyCard = `
    <div class="card">
      <div class="card-title">🌐 Salida alternativa</div>
      <div class="card-sub">Si una web no se abre directamente desde tu red (bloqueos por nombre o IP), el bot reintenta por este proxy. Solo lo usan los buscadores. Por defecto: el contenedor WARP de Cloudflare.<br>
        Estado: ${px.enabled ? "🟢 Activada" : "🔴 Desactivada"} ${notes.__proxy ? `<br>${notes.__proxy}` : ""}</div>
      <div class="source-add"><input type="text" id="proxyUrl" value="${escapeHtml(px.url)}" placeholder="${escapeHtml(px.default_url)}"></div>
      <div class="card-actions" style="flex-wrap:wrap;">
        <button class="btn btn-secondary" data-act="pxtest">🧪 Probar</button>
        <button class="btn btn-secondary" data-act="pxsave">Guardar dirección</button>
        <button class="btn ${px.enabled ? "btn-secondary" : "btn-primary"}" data-act="pxtoggle">${px.enabled ? "Desactivar" : "Activar"}</button>
      </div>
    </div>`;
  const MODE_NAMES = { builtin: "🔎 Buscadores integrados", prowlarr: "🧭 Prowlarr", both: "🔀 Ambos" };
  const modeCard = `
    <div class="card">
      <div class="card-title">🔀 Modo de búsqueda</div>
      <div class="card-sub">Integrados: las webs que actives abajo. Prowlarr: solo tu Prowlarr, que busca en todos sus indexadores. Ambos: junta los dos y quita duplicados.${pl.configured ? "" : "<br>Para usar Prowlarr o Ambos, primero conecta Prowlarr."}</div>
      <div class="card-actions" style="flex-wrap:wrap;">
        ${pl.modes.map((m) => `<button class="btn ${m === pl.mode ? "btn-primary" : "btn-secondary"}" data-act="smode" data-mode="${m}" ${m !== "builtin" && !pl.configured ? "disabled" : ""}>${MODE_NAMES[m]}</button>`).join("")}
      </div>
    </div>`;
  const prowlarrCard = `
    <div class="card">
      <div class="card-title">🧭 Prowlarr</div>
      <div class="card-sub">Opcional. Conecta tu Prowlarr y el bot buscará en todos sus indexadores con una sola consulta. Si va en el mismo Docker que el bot (perfil prowlarr), la URL es http://prowlarr:9696.<br>
        Estado: ${pl.configured ? "🟢 Conectado" : "⚪ Sin conectar"} ${notes.__prowlarr ? `<br>${notes.__prowlarr}` : ""}</div>
      <div class="source-add"><input type="text" id="prowlarrUrl" value="${escapeHtml(pl.url || "")}" placeholder="http://prowlarr:9696"></div>
      <div class="source-add"><input type="password" id="prowlarrKey" value="" placeholder="${pl.has_key ? "API key guardada (escribe otra para cambiarla)" : "API key (Settings → General → Security)"}" autocomplete="off"></div>
      <div class="card-actions" style="flex-wrap:wrap;">
        <button class="btn btn-primary" data-act="plsave">Guardar y probar</button>
        ${pl.configured ? `<button class="btn btn-secondary" data-act="pltest">🧪 Probar</button><button class="btn btn-danger" data-act="pldel">${icon("trash", 14)} Desconectar</button>` : ""}
      </div>
    </div>`;
  const plLine = (r) => r.ok
    ? `<span style="color:var(--green)">✅ Prowlarr ${escapeHtml(r.version || "")} · ${r.indexers} indexadores de torrents activos · ${r.ms} ms</span>`
    : `<span style="color:var(--red)">❌ ${escapeHtml(r.error || "sin respuesta")}</span>`;
  const card = (s) => {
    const state = !s.enabled ? "🔴 Desactivado" : (s.paused ? "⏸️ En pausa (2 min)" : "🟢 Activo");
    const mine = s.admin_urls.map((u) => `
      <div class="source-url"><code>${escapeHtml(u)}</code>
        <button class="btn btn-danger btn-sm" data-act="mdel" data-k="${s.key}" data-u="${escapeHtml(u)}" title="Quitar">${icon("trash", 12)}</button>
      </div>`).join("");
    return `
      <div class="card">
        <div class="card-title">${escapeHtml(s.label)}</div>
        <div class="card-sub">${state} · ${escapeHtml(s.about)}<br>Último host que funcionó: <b>${s.last ? escapeHtml(sourceHost(s.last)) : "—"}</b>
          ${notes[s.key] ? `<br>${notes[s.key]}` : ""}</div>
        <details class="source-details">
          <summary>Espejos</summary>
          ${s.admin_urls.length ? `<div class="hint-small">Añadidos por ti (se prueban primero):</div>${mine}` : ""}
          <div class="hint-small">De fábrica (escritos de memoria, pueden estar caídos):</div>
          ${s.factory_urls.map((u) => `<div class="source-url"><code>${escapeHtml(u)}</code></div>`).join("")}
          <div class="source-add">
            <textarea rows="3" placeholder="Un espejo por línea&#10;https://espejo1.ejemplo&#10;https://espejo2.ejemplo" id="mir-${s.key}"></textarea>
            <button class="btn btn-primary btn-sm" data-act="madd" data-k="${s.key}">${icon("plus", 12)} Añadir y probar</button>
          </div>
          ${s.admin_urls.length ? `<button class="btn btn-secondary btn-sm" data-act="mrst" data-k="${s.key}">Quitar todos los míos</button>` : ""}
        </details>
        <div class="card-actions" style="flex-wrap:wrap;">
          <button class="btn btn-secondary" data-act="test" data-k="${s.key}">🧪 Probar</button>
          <button class="btn ${s.enabled ? "btn-secondary" : "btn-primary"}" data-act="toggle" data-k="${s.key}" data-on="${s.enabled ? 1 : 0}">${s.enabled ? "Desactivar" : "Activar"}</button>
          <button class="btn btn-danger" data-act="srcdel" data-k="${s.key}">${icon("trash", 14)} Quitar</button>
        </div>
      </div>`;
  };
  root.innerHTML = `
    <p class="hint-small">Webs donde busca el bot. Vienen todas apagadas: activa las que quieras. Cada una tiene una URL principal y espejos de respaldo: si la principal falla prueba los espejos y recuerda el que funcionó.</p>
    ${modeCard}
    ${prowlarrCard}
    <div class="card-actions" style="margin-bottom:8px;flex-wrap:wrap;">
      <button class="btn btn-primary" data-act="testall">🩺 Probar todos</button>
      <button class="btn btn-secondary" data-act="srcadd">${icon("plus", 14)} Añadir buscador</button>
      <button class="btn btn-secondary" data-act="srcrestore">Restaurar los de fábrica</button>
    </div>
    ${proxyCard}
    ${data.sources.map(card).join("")}`;

  (loadSources._open || []).forEach((k) => {
    const el = root.querySelector(`#mir-${k}`);
    if (el) el.closest("details").open = true;
  });

  root.querySelectorAll("button[data-act]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const act = btn.dataset.act, k = btn.dataset.k;
      loadSources._open = [...root.querySelectorAll("details[open] input[id^=mir-]")].map((i) => i.id.slice(4));
      try {
        if (act === "smode") {
          await api("/api/search_mode", { method: "POST", body: JSON.stringify({ mode: btn.dataset.mode }) });
          if (searchState.refreshProviders) searchState.refreshProviders();
          loadSources();
        } else if (act === "plsave") {
          btn.disabled = true; btn.textContent = "Probando...";
          const body = { url: document.getElementById("prowlarrUrl").value.trim() };
          const key = document.getElementById("prowlarrKey").value.trim();
          if (key) body.apikey = key;
          const r = await api("/api/prowlarr", { method: "POST", body: JSON.stringify(body) });
          if (searchState.refreshProviders) searchState.refreshProviders();
          loadSources({ __prowlarr: r.ok ? plLine(r) + " · 💾 Guardado" : plLine(r) + " · no se ha guardado" });
        } else if (act === "pltest") {
          btn.disabled = true; btn.textContent = "Probando...";
          loadSources({ __prowlarr: plLine(await api("/api/prowlarr/test", { method: "POST" })) });
        } else if (act === "pldel") {
          if (!(await confirmModal("¿Desconectar Prowlarr? El modo de búsqueda volverá a «Buscadores integrados»."))) return;
          await api("/api/prowlarr/delete", { method: "POST" });
          if (searchState.refreshProviders) searchState.refreshProviders();
          loadSources();
        } else if (act === "pxtoggle") {
          await api("/api/sources/proxy", { method: "POST", body: JSON.stringify({ enabled: !px.enabled }) });
          loadSources();
        } else if (act === "pxsave") {
          await api("/api/sources/proxy", { method: "POST", body: JSON.stringify({ url: document.getElementById("proxyUrl").value, enabled: true }) });
          loadSources({ __proxy: "💾 Guardado y activado" });
        } else if (act === "pxtest") {
          btn.disabled = true; btn.textContent = "Probando...";
          const r = await api("/api/sources/proxy/test", { method: "POST" });
          loadSources({ __proxy: `${r.ok ? "✅" : "❌"} ${escapeHtml(r.detail || "sin respuesta")}${r.nyaa ? "<br>" + escapeHtml(r.nyaa) : ""}` });
        } else if (act === "toggle") {
          await api(`/api/sources/${k}/toggle`, { method: "POST", body: JSON.stringify({ enabled: btn.dataset.on !== "1" }) });
          if (searchState.refreshProviders) searchState.refreshProviders();
          loadSources();
        } else if (act === "test") {
          btn.disabled = true; btn.textContent = "Probando...";
          const r = await api(`/api/sources/${k}/test`, { method: "POST" });
          loadSources({ [k]: sourceTestLine(r) });
        } else if (act === "testall") {
          btn.disabled = true; btn.textContent = "Probando...";
          const r = await api("/api/sources/test_all", { method: "POST" });
          const n = {};
          Object.entries(r.results).forEach(([key, v]) => { n[key] = sourceTestLine(v); });
          loadSources(n);
        } else if (act === "madd") {
          const inp = document.getElementById(`mir-${k}`);
          const url = inp.value.trim();
          if (!url) return;
          btn.disabled = true; btn.textContent = "Probando...";
          let r = await api(`/api/sources/${k}/mirrors`, { method: "POST", body: JSON.stringify({ url }) });
          const failed = r.results.filter((x) => !x.saved);
          if (failed.length) {
            const ok = await confirmModal(`${failed.length} espejo(s) no pasaron la prueba (${failed.map((x) => sourceHost(x.url)).join(", ")}). ¿Guardarlos igualmente?`);
            if (ok) r = await api(`/api/sources/${k}/mirrors`, { method: "POST", body: JSON.stringify({ url: failed.map((x) => x.url).join("\n"), force: true }) });
          }
          const lines = r.results.map((x) => `${x.saved ? "💾" : ""} ${escapeHtml(sourceHost(x.url))}: ${sourceTestLine(x.test)}`).join("<br>");
          loadSources({ [k]: lines });
        } else if (act === "srcdel") {
          if (!(await confirmModal("¿Quitar este buscador?"))) return;
          await api(`/api/sources/${k}/delete`, { method: "POST" });
          if (searchState.refreshProviders) searchState.refreshProviders();
          loadSources();
        } else if (act === "srcrestore") {
          await api("/api/sources/restore", { method: "POST" });
          if (searchState.refreshProviders) searchState.refreshProviders();
          loadSources();
        } else if (act === "srcadd") {
          openAddSourceModal(data.sources);
        } else if (act === "mdel") {
          await api(`/api/sources/${k}/mirrors/delete`, { method: "POST", body: JSON.stringify({ url: btn.dataset.u }) });
          loadSources();
        } else if (act === "mrst") {
          if (!(await confirmModal("¿Quitar todos los espejos que añadiste a este buscador?"))) return;
          await api(`/api/sources/${k}/mirrors/delete`, { method: "POST", body: JSON.stringify({}) });
          loadSources();
        }
      } catch (e) {
        tgAlert(e.message);
        btn.disabled = false;
      }
    });
  });
}

const BUILTIN_PARSERS = ["apibay", "1337x", "limetorrents", "eztv", "yts", "nyaa", "knaben", "torrentscsv"];

function openAddSourceModal(sources) {
  const parsers = BUILTIN_PARSERS;
  renderCenter(`
    <h3>${icon("plus", 18)} Añadir buscador</h3>
    <select id="newSrcKind">
      <option value="torznab">Torznab (Jackett / Prowlarr)</option>
      <option value="clone">Copia de uno integrado (otro dominio)</option>
    </select>
    <input type="text" id="newSrcName" placeholder="Nombre">
    <input type="text" id="newSrcUrl" placeholder="https://...">
    <input type="text" id="newSrcKey" placeholder="API key">
    <select id="newSrcParser" class="hidden">${parsers.map((p) => `<option value="${escapeHtml(p)}">${escapeHtml(p)}</option>`).join("")}</select>
    <div id="newSrcError"></div>
    <div class="center-modal-footer">
      <button class="btn btn-secondary" id="newSrcCancel">Cancelar</button>
      <button class="btn btn-primary" id="newSrcSave">Guardar</button>
    </div>`);
  const kind = document.getElementById("newSrcKind");
  const sync = () => {
    document.getElementById("newSrcKey").classList.toggle("hidden", kind.value !== "torznab");
    document.getElementById("newSrcParser").classList.toggle("hidden", kind.value !== "clone");
  };
  kind.addEventListener("change", sync);
  sync();
  document.getElementById("newSrcCancel").addEventListener("click", closeCenterModal);
  document.getElementById("newSrcSave").addEventListener("click", async () => {
    const btn = document.getElementById("newSrcSave");
    btn.disabled = true;
    try {
      const r = await api("/api/sources/custom", {
        method: "POST",
        body: JSON.stringify({
          kind: kind.value,
          name: document.getElementById("newSrcName").value,
          url: document.getElementById("newSrcUrl").value,
          apikey: document.getElementById("newSrcKey").value,
          parser: document.getElementById("newSrcParser").value,
        }),
      });
      closeCenterModal();
      if (searchState.refreshProviders) searchState.refreshProviders();
      loadSources({ [r.key]: sourceTestLine(r.test) });
    } catch (e) {
      document.getElementById("newSrcError").innerHTML = `<p class="modal-error">${escapeHtml(e.message)}</p>`;
      btn.disabled = false;
    }
  });
}

function browseFolder(start) {
  return new Promise((resolve) => {
    const root = document.getElementById("modalRoot");
    const close = (val) => { root.innerHTML = ""; resolve(val); };
    const load = async (path) => {
      let d;
      try {
        d = await api("/api/folders/browse?path=" + encodeURIComponent(path));
      } catch (e) {
        tgAlert(e.message);
        return;
      }
      const atBase = d.path === d.parent;
      root.innerHTML = `
        <div class="modal-backdrop">
          <div class="modal-box fb-box">
            <h3>Elegir carpeta</h3>
            <div class="fb-path"><code>${escapeHtml(d.path)}</code></div>
            <div class="fb-list">
              ${atBase ? "" : `<button class="fb-row fb-up" data-go="${escapeHtml(d.parent)}"><span>⬆️</span><span>Subir</span></button>`}
              ${d.dirs.length ? d.dirs.map((x) => `<button class="fb-row" data-go="${escapeHtml(d.path.replace(/\/$/, "") + "/" + x)}"><span>📁</span><span>${escapeHtml(x)}</span></button>`).join("") : `<div class="fb-empty">No hay subcarpetas aquí</div>`}
            </div>
            <div class="fb-new">
              <input type="text" id="fbNew" placeholder="Nueva subcarpeta aquí…" maxlength="30">
              <button class="btn btn-secondary" id="fbMk">${icon("plus", 14)} Crear</button>
            </div>
            <div class="modal-actions">
              <button class="btn btn-secondary" id="fbCancel">Cancelar</button>
              <button class="btn btn-primary" id="fbUse">Usar esta carpeta</button>
            </div>
          </div>
        </div>`;
      root.querySelectorAll("[data-go]").forEach((b) => b.addEventListener("click", () => load(b.dataset.go)));
      root.querySelector("#fbCancel").addEventListener("click", () => close(null));
      root.querySelector("#fbUse").addEventListener("click", () => close(d.path));
      root.querySelector("#fbMk").addEventListener("click", async () => {
        const name = root.querySelector("#fbNew").value.trim();
        if (!name) return;
        try {
          const r = await api("/api/folders/mkdir", { method: "POST", body: JSON.stringify({ path: d.path, new_name: name }) });
          load(r.path);
        } catch (e) {
          tgAlert(e.message);
        }
      });
    };
    load(start);
  });
}

async function loadFolders() {
  const root = document.getElementById("foldersCard");
  const data = await api("/api/folders");
  const mediaLabel = { "": "Sin tipo", movie: "Películas", tv: "Series" };
  root.innerHTML = `
    <p class="hint-small">Carpetas del contenedor a las que tiene acceso el bot. Deben estar montadas como volúmenes en docker-compose.</p>
    ${data.folders.map((f) => `
      <div class="pv">
        <div class="pv-head">
          <span class="pv-tile" style="background:#c26f0e">${icon("folder", 20)}</span>
          <div class="pv-t"><div class="pv-name">${escapeHtml(f.name)}</div><div class="pv-sub"><code>${escapeHtml(f.path)}</code></div></div>
        </div>
        <div class="dl-chips" style="margin-top:0">
          ${f.exists ? (f.writable ? `<span class="chip chip-ok">${icon("check", 11)} Disponible</span>` : `<span class="chip chip-warn">Solo lectura</span>`) : `<span class="chip chip-err">${icon("x", 11)} No existe</span>`}
          <span class="chip chip-prov">TMDB: ${mediaLabel[f.media] || "Sin tipo"}</span>
        </div>
        <div class="pv-actions">
          <button class="btn btn-secondary" data-act="frename" data-n="${escapeHtml(f.name)}">${icon("pencil", 14)} Nombre</button>
          <button class="btn btn-secondary" data-act="fpath" data-n="${escapeHtml(f.name)}">Ruta</button>
          <button class="btn btn-secondary" data-act="fmedia" data-n="${escapeHtml(f.name)}" data-m="${f.media}">Tipo TMDB</button>
          <button class="btn btn-danger" data-act="fdel" data-n="${escapeHtml(f.name)}">${icon("trash", 14)} Quitar</button>
        </div>
      </div>`).join("")}
    <div class="pv-actions"><button class="btn btn-secondary" data-act="freset">Restaurar ejemplos</button></div>`;
  root.querySelectorAll("button[data-act]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const act = btn.dataset.act, n = btn.dataset.n;
      try {
        if (act === "frename") {
          const nn = await promptModal("Cambiar nombre", "Nombre de la carpeta", n);
          if (!nn) return;
          await api("/api/folders/rename", { method: "POST", body: JSON.stringify({ name: n, new_name: nn }) });
        } else if (act === "fpath") {
          const path = await browseFolder("/media");
          if (!path) return;
          await api("/api/folders/path", { method: "POST", body: JSON.stringify({ name: n, path }) });
        } else if (act === "fdel") {
          if (!(await confirmModal(`¿Quitar la carpeta ${n}? No se borra nada del disco.`))) return;
          await api("/api/folders/delete", { method: "POST", body: JSON.stringify({ name: n }) });
        } else if (act === "freset") {
          await api("/api/folders/reset", { method: "POST" });
        } else if (act === "fmedia") {
          const order = ["", "movie", "tv"];
          const next = order[(order.indexOf(btn.dataset.m) + 1) % order.length];
          await api("/api/folders/media", { method: "POST", body: JSON.stringify({ name: n, media: next }) });
        }
        loadFolders();
      } catch (e) {
        tgAlert(e.message);
      }
    });
  });
}

async function loadLanguageSettings() {
  const root = document.getElementById("languageCard");
  const info = await api("/api/i18n");
  root.innerHTML = `
    <div class="card">
      <div class="card-title">🌐 Idioma</div>
      <div class="card-sub">Idioma del chat y de la web app.</div>
      <div class="card-actions" style="flex-wrap:wrap;">
        ${Object.entries(info.languages).map(([code, name]) => `<button class="btn ${code === info.lang ? "btn-primary" : "btn-secondary"}" data-lang="${code}">${escapeHtml(name)}</button>`).join("")}
      </div>
    </div>`;
  root.querySelectorAll("button[data-lang]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await api("/api/settings/language", { method: "POST", body: JSON.stringify({ lang: btn.dataset.lang }) });
        location.reload();
      } catch (e) {
        tgAlert(e.message);
      }
    });
  });
}

async function loadTmdbSettings() {
  const root = document.getElementById("tmdbCard");
  root.innerHTML = `<p class="empty">Consultando...</p>`;
  let st;
  try {
    st = await api("/api/tmdb");
  } catch (e) {
    root.innerHTML = `<p class="modal-error">${escapeHtml(e.message)}</p>`;
    return;
  }
  root.innerHTML = `
    <div class="card">
      <div class="card-title">TMDB</div>
      <div class="card-sub">Opcional. Al descargar en la raíz de una carpeta marcada como <b>Películas</b> o <b>Series</b>, crea la carpeta con el nombre del título según TMDB (en español si el original es español, si no en inglés). No renombra archivos ni actúa dentro de subcarpetas.</div>
      <div class="card-sub" style="margin-top:8px;">API Token: ${st.configured ? "🔑 configurado" : "⚪ sin configurar"}<br>Estado: ${st.enabled ? "🟢 Activado" : "🔴 Desactivado"}</div>
      <div class="card-actions" style="flex-wrap:wrap;">
        ${st.configured ? `<button class="btn ${st.enabled ? "btn-secondary" : "btn-primary"}" id="tmdbToggle">${st.enabled ? "Desactivar" : "Activar"}</button>` : ""}
        <button class="btn ${st.configured ? "btn-secondary" : "btn-primary"}" id="tmdbToken">${icon("key", 14)} ${st.configured ? "Cambiar token" : "Configurar token"}</button>
        ${st.configured ? `<button class="btn btn-danger" id="tmdbDelete">${icon("trash", 14)} Eliminar token</button>` : ""}
      </div>
    </div>`;
  const tgl = document.getElementById("tmdbToggle");
  if (tgl) tgl.addEventListener("click", async () => {
    try { await api("/api/tmdb/toggle", { method: "POST", body: JSON.stringify({ enabled: !st.enabled }) }); loadTmdbSettings(); }
    catch (e) { tgAlert(e.message); }
  });
  const del = document.getElementById("tmdbDelete");
  if (del) del.addEventListener("click", async () => {
    if (!(await confirmModal("¿Eliminar el API Token de TMDB? Se desactivará."))) return;
    try { await api("/api/tmdb/token/delete", { method: "POST" }); loadTmdbSettings(); }
    catch (e) { tgAlert(e.message); }
  });
  document.getElementById("tmdbToken").addEventListener("click", () => {
    renderCenter(`
      <h3>${icon("key", 18)} API Key de TMDB</h3>
      <input type="text" id="tmdbTokenInput" placeholder="Pega tu clave de API (v3)">
      <p class="hint-small">Gratis en themoviedb.org/settings/api</p>
      <div id="tmdbTokenError"></div>
      <div class="center-modal-footer">
        <button class="btn btn-secondary" id="tmdbTokenCancel">Cancelar</button>
        <button class="btn btn-primary" id="tmdbTokenSave">Guardar</button>
      </div>`);
    document.getElementById("tmdbTokenInput").focus();
    document.getElementById("tmdbTokenCancel").addEventListener("click", closeCenterModal);
    document.getElementById("tmdbTokenSave").addEventListener("click", async () => {
      const token = document.getElementById("tmdbTokenInput").value.trim();
      if (!token) return;
      const btn = document.getElementById("tmdbTokenSave");
      btn.disabled = true; btn.textContent = "Comprobando...";
      try {
        await api("/api/tmdb/token", { method: "POST", body: JSON.stringify({ token }) });
        closeCenterModal(); loadTmdbSettings();
      } catch (e) {
        document.getElementById("tmdbTokenError").innerHTML = `<p class="modal-error">${escapeHtml(e.message)}</p>`;
        btn.disabled = false; btn.textContent = "Guardar";
      }
    });
  });
}

function openProviderTokenModal(id) {
  const meta = PROVIDER_META[id];
  renderCenter(`
    <h3>${icon("key", 18)} Token de ${escapeHtml(meta.name)}</h3>
    <input type="text" id="provTokenInput" placeholder="Pega tu API token aquí">
    <p class="hint-small">Puedes generarlo en ${escapeHtml(meta.tokenUrl)}</p>
    <div id="provTokenError"></div>
    <div class="center-modal-footer">
      <button class="btn btn-secondary" id="provTokenCancel">Cancelar</button>
      <button class="btn btn-primary" id="provTokenSave">Guardar</button>
    </div>
  `);
  document.getElementById("provTokenInput").focus();
  document.getElementById("provTokenCancel").addEventListener("click", closeCenterModal);
  document.getElementById("provTokenSave").addEventListener("click", async () => {
    const token = document.getElementById("provTokenInput").value.trim();
    if (!token) return;
    const btn = document.getElementById("provTokenSave");
    btn.disabled = true;
    btn.textContent = "Comprobando...";
    try {
      await api(meta.tokenApi, { method: "POST", body: JSON.stringify({ token }) });
      closeCenterModal();
      loadProviders();
    } catch (e) {
      document.getElementById("provTokenError").innerHTML = `<p class="modal-error">${escapeHtml(e.message)}</p>`;
      btn.disabled = false;
      btn.textContent = "Guardar";
    }
  });
}

async function loadUsers() {
  const card = document.getElementById("usersCard");
  card.innerHTML = `<p class="empty">Consultando...</p>`;
  try {
    const data = await api("/api/users");
    const rows = data.users
      .map((u) => {
        const name = u.first_name || "(sin nombre)";
        const alias = u.username ? ` · @${escapeHtml(u.username)}` : "";
        const added = (u.added_at || "").slice(0, 10);
        return `
          <div class="card">
            <div class="card-title">${escapeHtml(name)}${alias}</div>
            <div class="card-sub">ID: ${u.user_id} · desde ${added || "?"}</div>
            <div class="card-actions">
              <button class="btn btn-danger" data-uid="${u.user_id}">${icon("trash", 14)} Quitar</button>
            </div>
          </div>
        `;
      })
      .join("");

    card.innerHTML = `
      <div class="card">
        <div class="card-title">${icon("crown", 16)} Propietario</div>
        <div class="card-sub">ID: ${data.owner_id} · acceso total</div>
      </div>
      ${rows || '<p class="empty">No hay usuarios adicionales todavía.</p>'}
      <div class="card-actions" style="margin-top:4px;">
        <button class="btn btn-primary" id="btnAddUser">${icon("plus", 14)} Añadir usuario</button>
      </div>
    `;

    card.querySelectorAll("[data-uid]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const uid = parseInt(btn.dataset.uid, 10);
        const confirmed = await confirmModal(`¿Quitar el acceso al usuario ${uid}?`);
        if (!confirmed) return;
        try {
          await api("/api/users/remove", { method: "POST", body: JSON.stringify({ user_id: uid }) });
          loadUsers();
        } catch (e) {
          tgAlert(e.message);
        }
      });
    });
    document.getElementById("btnAddUser").addEventListener("click", openAddUserModal);
  } catch (e) {
    card.innerHTML = `<p class="empty">${escapeHtml(e.message)}</p>`;
  }
}

function openAddUserModal() {
  renderCenter(`
    <h3>${icon("plus", 18)} Añadir usuario</h3>
    <input type="text" id="addUserInput" placeholder="ID numérico de Telegram" inputmode="numeric">
    <p class="hint-small">Puede obtenerlo escribiéndole a <a href="https://t.me/userinfobot" id="userinfobotLink">@userinfobot</a> con su cuenta.</p>
    <div id="addUserError"></div>
    <div class="center-modal-footer">
      <button class="btn btn-secondary" id="addUserCancel">Cancelar</button>
      <button class="btn btn-primary" id="addUserSave">Añadir</button>
    </div>
  `);
  document.getElementById("addUserInput").focus();
  document.getElementById("userinfobotLink").addEventListener("click", (e) => {
    e.preventDefault();
    if (tg && tg.openTelegramLink) {
      tg.openTelegramLink("https://t.me/userinfobot");
    } else {
      window.open("https://t.me/userinfobot", "_blank");
    }
  });
  document.getElementById("addUserCancel").addEventListener("click", closeCenterModal);
  document.getElementById("addUserSave").addEventListener("click", async () => {
    const raw = document.getElementById("addUserInput").value.trim();
    const userId = parseInt(raw, 10);
    if (!raw || Number.isNaN(userId)) {
      document.getElementById("addUserError").innerHTML = `<p class="modal-error">Introduce un ID numérico válido.</p>`;
      return;
    }
    const btn = document.getElementById("addUserSave");
    btn.disabled = true;
    btn.textContent = "Añadiendo...";
    try {
      await api("/api/users/add", { method: "POST", body: JSON.stringify({ user_id: userId }) });
      closeCenterModal();
      loadUsers();
    } catch (e) {
      document.getElementById("addUserError").innerHTML = `<p class="modal-error">${escapeHtml(e.message)}</p>`;
      btn.disabled = false;
      btn.textContent = "Añadir";
    }
  });
}

async function loadGdriveStatus() {
  const card = document.getElementById("gdriveCard");
  if (!card) return;
  const head = (chip, sub) => `
    <div class="pv-head">
      <span class="pv-tile" style="background:#2e9d4a">${icon("folder", 20)}</span>
      <div class="pv-t"><div class="pv-name">Google Drive</div><div class="pv-sub">${sub}</div></div>
      ${chip}
    </div>`;
  try {
    const info = await api("/api/gdrive/status");
    if (!info.configured) {
      card.innerHTML = `<div class="pv">${head(`<span class="chip chip-dim">Sin configurar</span>`, "Faltan GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REDIRECT_URI en el .env del servidor.")}</div>`;
      return;
    }
    if (info.connected) {
      card.innerHTML = `<div class="pv">${head(`<span class="chip chip-ok">Conectado</span>`, escapeHtml(info.email || "Cuenta conectada"))}
        <div class="pv-note">Los enlaces de Drive se descargan directo al NAS con esta cuenta (sin Real-Debrid ni aria2).</div>
        <div class="pv-actions">
          <button class="btn btn-secondary" id="gdriveChange">${icon("plug", 14)} Cambiar cuenta</button>
          <button class="btn btn-danger" id="gdriveDisconnect">${icon("trash", 14)} Desconectar</button>
        </div></div>`;
      document.getElementById("gdriveChange").addEventListener("click", startGdriveConnect);
      document.getElementById("gdriveDisconnect").addEventListener("click", async () => {
        if (!(await confirmModal("¿Desconectar la cuenta de Google Drive?"))) return;
        try {
          await api("/api/gdrive/disconnect", { method: "POST" });
          loadGdriveStatus();
        } catch (e) {
          tgAlert(e.message);
        }
      });
    } else {
      card.innerHTML = `<div class="pv">${head(`<span class="chip chip-err">Desconectado</span>`, "Descarga enlaces de Drive directo al NAS")}
        <div class="pv-actions"><button class="btn btn-primary" id="gdriveConnect">${icon("plug", 14)} Conectar</button></div></div>`;
      document.getElementById("gdriveConnect").addEventListener("click", startGdriveConnect);
    }
  } catch (e) {
    card.innerHTML = `<p class="empty">${escapeHtml(e.message)}</p>`;
  }
}

async function startGdriveConnect() {
  try {
    const data = await api("/api/gdrive/connect/start", { method: "POST" });
    if (tg && tg.openLink) {
      tg.openLink(data.url);
    } else {
      window.open(data.url, "_blank");
    }
    tgAlert("Se abrió tu navegador para iniciar sesión con Google. Cuando termines, vuelve aquí y pulsa esta sección de nuevo para ver el estado.");
  } catch (e) {
    tgAlert(e.message);
  }
}

function formatElapsedSec(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0));
  const m = Math.floor(s / 60);
  const remS = s % 60;
  if (m < 60) return `${m}:${remS < 10 ? "0" : ""}${remS}`;
  const h = Math.floor(m / 60);
  const remM = m % 60;
  return `${h}:${remM < 10 ? "0" : ""}${remM}:${remS < 10 ? "0" : ""}${remS}`;
}

function setupFileManager() {
  document.getElementById("btnNewFolder").addEventListener("click", async () => {
    if (!fm.folder) return;
    const name = await promptModal("Nueva carpeta", "Nombre de la carpeta");
    if (!name) return;
    try {
      await api("/api/files/mkdir", {
        method: "POST",
        body: JSON.stringify({ folder: fm.folder, path: fm.path, name }),
      });
      loadFiles(fm.folder, fm.path);
    } catch (e) {
      tgAlert(e.message);
    }
  });

  loadFolderRoots();
}

async function loadFolderRoots() {
  try {
    const state = await api("/api/state");
    fm.folders = state.folders;
    fm.folder = null;
    fm.path = "";
    renderBreadcrumbRoots();
  } catch (e) {
  }
}

function renderBreadcrumbRoots() {
  fm.folder = null;
  fm.path = "";
  const bc = document.getElementById("breadcrumb");
  bc.innerHTML = "";
  document.getElementById("fileList").innerHTML = "";
  document.getElementById("btnNewFolder").classList.add("hidden");
  updateBackButton();

  const list = document.getElementById("fileList");
  for (const folder of fm.folders || []) {
    const row = document.createElement("div");
    row.className = "card file-row";
    row.innerHTML = `<div class="name"><span class="file-icon folder-icon">${icon("folder", 20)}</span><span class="fname">${escapeHtml(folder)}</span></div>`;
    row.addEventListener("click", () => loadFiles(folder, ""));
    list.appendChild(row);
  }
}

async function loadFiles(folder, path) {
  fm.folder = folder;
  fm.path = path;
  document.getElementById("btnNewFolder").classList.remove("hidden");
  updateBackButton();

  try {
    const data = await api(`/api/files?folder=${encodeURIComponent(folder)}&path=${encodeURIComponent(path)}`);
    renderBreadcrumb();
    renderFileList(data);
  } catch (e) {
    tgAlert(e.message);
  }
}

function renderBreadcrumb() {
  const bc = document.getElementById("breadcrumb");
  const parts = [fm.folder, ...(fm.path ? fm.path.split("/") : [])];
  bc.innerHTML =
    `<span data-idx="-1">${icon("home", 14)}</span> / ` +
    parts.map((p, i) => `<span data-idx="${i}">${escapeHtml(p)}</span>`).join(" / ");

  bc.querySelectorAll("span").forEach((span) => {
    span.addEventListener("click", () => {
      const idx = parseInt(span.dataset.idx, 10);
      if (idx === -1) {
        renderBreadcrumbRoots();
        return;
      }
      const newParts = parts.slice(1, idx + 1);
      loadFiles(fm.folder, newParts.join("/"));
    });
  });
}

const VIDEO_EXTENSIONS = [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg", ".ts"];
const IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic", ".svg"];
const AUDIO_EXTENSIONS = [".mp3", ".flac", ".wav", ".m4a", ".ogg", ".aac", ".wma"];

function fileTypeIcon(name) {
  const lower = (name || "").toLowerCase();
  if (isArchiveFilename(lower)) return icon("archive", 20);
  if (VIDEO_EXTENSIONS.some((ext) => lower.endsWith(ext))) return icon("video", 20);
  if (IMAGE_EXTENSIONS.some((ext) => lower.endsWith(ext))) return icon("image", 20);
  if (AUDIO_EXTENSIONS.some((ext) => lower.endsWith(ext))) return icon("audio", 20);
  return icon("document", 20);
}

function renderFileList(data) {
  const list = document.getElementById("fileList");
  list.innerHTML = "";

  for (const d of data.dirs) {
    const row = document.createElement("div");
    row.className = "card file-row";
    row.innerHTML = `<div class="name"><span class="file-icon folder-icon">${icon("folder", 20)}</span><span class="fname">${escapeHtml(d.name)}</span></div><div class="meta">${d.size ?? "…"}</div>`;
    row.addEventListener("click", () => {
      const newPath = fm.path ? `${fm.path}/${d.name}` : d.name;
      loadFiles(fm.folder, newPath);
    });
    row.addEventListener("contextmenu", (ev) => {
      ev.preventDefault();
      openFileMenu(d.name, true);
    });
    let pressTimer;
    row.addEventListener("touchstart", () => { pressTimer = setTimeout(() => openFileMenu(d.name, true), 500); });
    row.addEventListener("touchend", () => clearTimeout(pressTimer));
    list.appendChild(row);
  }

  for (const f of data.files) {
    const row = document.createElement("div");
    row.className = "card file-row";
    row.innerHTML = `<div class="name"><span class="file-icon">${fileTypeIcon(f.name)}</span><span class="fname">${escapeHtml(f.name)}</span></div><div class="meta">${f.size}</div>`;
    row.addEventListener("click", () => openFileMenu(f.name, false));
    list.appendChild(row);
  }

  if (data.dirs.length === 0 && data.files.length === 0) {
    list.innerHTML = `<p class="empty">Carpeta vacía.</p>`;
  }
}

function openFileMenu(name, isDir) {
  const itemPath = fm.path ? `${fm.path}/${name}` : name;
  const actions = [];

  if (!isDir) {
    actions.push({
      label: `${icon("download", 15)} Descargar`,
      run: () => {
        window.open(
          `/api/files/download?folder=${encodeURIComponent(fm.folder)}&path=${encodeURIComponent(itemPath)}&init_data=${encodeURIComponent(initData)}`,
          "_blank"
        );
      },
    });

    actions.push({
      label: `${icon("upload", 15)} Subir a Telegram`,
      run: () => uploadToTelegramDialog(name),
    });

    if (isArchiveFilename(name)) {
      actions.push({
        label: `${icon("archive", 15)} Descomprimir`,
        run: () => openExtractDialog(name),
      });
    }
  }

  actions.push({
    label: `${icon("copy", 15)} Copiar / mover`,
    run: () => openCopyDialog([itemPath]),
  });

  actions.push({
    label: `${icon("pencil", 15)} Renombrar`,
    run: async () => {
      const newName = await promptModal("Renombrar", "Nuevo nombre", name);
      if (!newName) return;
      try {
        await api("/api/files/rename", {
          method: "POST",
          body: JSON.stringify({ folder: fm.folder, path: itemPath, new_name: newName }),
        });
        loadFiles(fm.folder, fm.path);
      } catch (e) {
        tgAlert(e.message);
      }
    },
  });

  actions.push({
    label: `${icon("trash", 15)} Eliminar`,
    danger: true,
    run: async () => {
      const confirmed = await confirmModal(`¿Eliminar "${name}"? Esta acción no se puede deshacer.`);
      if (!confirmed) return;
      try {
        await api("/api/files/delete", {
          method: "POST",
          body: JSON.stringify({ folder: fm.folder, path: itemPath }),
        });
        loadFiles(fm.folder, fm.path);
      } catch (e) {
        tgAlert(e.message);
      }
    },
  });

  showActionSheet(name, actions);
}

function uploadToTelegramDialog(name) {
  const itemPath = fm.path ? `${fm.path}/${name}` : name;
  const targetFolder = fm.folder;

  renderCenter(`
    <h3>${icon("upload", 18)} Subir a Telegram</h3>
    <p class="hint-small" style="text-align:left;margin-bottom:16px;">
      ¿Deseas enviar el archivo <b>${escapeHtml(name)}</b> directamente a tu chat de Telegram vía Userbot?
    </p>
    <div class="center-modal-footer">
      <button class="btn btn-secondary" id="uploadCancelBtn">${icon("x", 14)} Cancelar</button>
      <button class="btn btn-primary" id="uploadConfirmBtn">${icon("upload", 14)} Enviar a Telegram</button>
    </div>
  `);

  document.getElementById("uploadCancelBtn").addEventListener("click", closeCenterModal);
  document.getElementById("uploadConfirmBtn").addEventListener("click", async () => {
    closeCenterModal();
    try {
      await api("/api/files/upload_to_telegram", {
        method: "POST",
        body: JSON.stringify({ folder: targetFolder, path: itemPath }),
      });
      tgAlert(`Iniciando subida de "${name}" a Telegram... Puedes seguir el progreso en la cola de tareas.`);
    } catch (e) {
      tgAlert(e.message || "Error al iniciar subida a Telegram");
    }
  });
}

function openExtractDialog(name) {
  const itemPath = fm.path ? `${fm.path}/${name}` : name;
  const srcFolder = fm.folder;
  const currentPath = fm.path;

  renderCenter(`
    <h3>${icon("archive", 18)} Descomprimir archivo</h3>
    <p class="hint-small" style="text-align:left;margin-bottom:16px;">
      ¿Dónde deseas descomprimir <b>${escapeHtml(name)}</b>?
    </p>
    <div style="display:flex;flex-direction:column;gap:8px;margin-bottom:14px;">
      <button class="btn btn-primary" id="extSameDir" style="padding:13px 10px;text-align:left;display:flex;align-items:center;gap:8px;">
        <span class="file-icon folder-icon">${icon("folder", 18)}</span>
        <span>En este mismo directorio</span>
      </button>
      <button class="btn btn-secondary" id="extDiffDir" style="padding:13px 10px;text-align:left;display:flex;align-items:center;gap:8px;">
        <span class="file-icon folder-icon">${icon("folder", 18)}</span>
        <span>Elegir un directorio diferente</span>
      </button>
    </div>
    <div class="center-modal-footer">
      <button class="btn btn-secondary" id="extCancel">${icon("x", 14)} Cancelar</button>
    </div>
  `);

  document.getElementById("extCancel").addEventListener("click", closeCenterModal);
  document.getElementById("extSameDir").addEventListener("click", () => {
    executeExtract(srcFolder, itemPath, srcFolder, currentPath);
  });
  document.getElementById("extDiffDir").addEventListener("click", () => {
    openExtractFolderPicker(name, srcFolder, itemPath, null, "");
  });
}

async function openExtractFolderPicker(srcName, srcFolder, srcPath, currentFolder, currentPath) {
  if (currentFolder === null) {
    let folders = window.appFolders || [];
    try {
      const state = await api("/api/state");
      folders = state.folders;
    } catch (e) {}

    const rows = folders
      .map(
        (f) =>
          `<div class="folder-pick-row" data-folder="${escapeHtml(f)}"><span class="file-icon folder-icon">${icon("folder", 18)}</span>${escapeHtml(f)}</div>`
      )
      .join("");

    renderCenter(`
      <h3>${icon("folder", 18)} Elige la carpeta de destino</h3>
      <div style="margin-bottom:14px;">${rows}</div>
      <div class="center-modal-footer">
        <button class="btn btn-secondary" id="extPickerBack">${icon("arrowLeft", 14)} Volver</button>
        <button class="btn btn-secondary" id="extPickerCancel">${icon("x", 14)} Cancelar</button>
      </div>
    `);

    document.querySelectorAll(".folder-pick-row").forEach((row) => {
      row.addEventListener("click", () => {
        openExtractFolderPicker(srcName, srcFolder, srcPath, row.dataset.folder, "");
      });
    });
    document.getElementById("extPickerBack").addEventListener("click", () => openExtractDialog(srcName));
    document.getElementById("extPickerCancel").addEventListener("click", closeCenterModal);
    return;
  }

  let data;
  try {
    data = await api(`/api/files?folder=${encodeURIComponent(currentFolder)}&path=${encodeURIComponent(currentPath)}&sizes=0`);
  } catch (e) {
    renderCenter(`
      <h3>${icon("folder", 18)} ${escapeHtml(currentFolder)}</h3>
      <p class="modal-error">${escapeHtml(e.message)}</p>
      <div class="center-modal-footer">
        <button class="btn btn-secondary" id="extPickerCancel">${icon("x", 14)} Cancelar</button>
      </div>
    `);
    document.getElementById("extPickerCancel").addEventListener("click", closeCenterModal);
    return;
  }

  const dirRows = data.dirs
    .map((d) => {
      const nextPath = currentPath ? `${currentPath}/${d.name}` : d.name;
      return `<div class="folder-pick-row" data-folder="${escapeHtml(currentFolder)}" data-path="${escapeHtml(nextPath)}"><span class="file-icon folder-icon">${icon("folder", 18)}</span>${escapeHtml(d.name)}</div>`;
    })
    .join("");

  const label = currentPath ? `${currentFolder}/${currentPath}` : currentFolder;

  renderCenter(`
    <h3>${icon("folder", 18)} ${escapeHtml(label)}</h3>
    <div style="max-height:220px;overflow-y:auto;margin-bottom:14px;">
      ${dirRows || '<p class="empty" style="padding:12px 0;">Sin subcarpetas</p>'}
    </div>
    <div class="center-modal-footer">
      <button class="btn btn-secondary" id="extPickerNewFolder">${icon("plus", 14)} Carpeta</button>
      <button class="btn btn-primary" id="extPickerExtractHere">${icon("archive", 14)} Descomprimir aquí</button>
    </div>
    <div class="center-modal-footer">
      <button class="btn btn-secondary" id="extPickerBack">${icon("arrowLeft", 14)} ${currentPath ? "Atrás" : "Cambiar raíz"}</button>
      <button class="btn btn-secondary" id="extPickerCancel">${icon("x", 14)} Cancelar</button>
    </div>
  `);

  document.querySelectorAll(".folder-pick-row").forEach((row) => {
    row.addEventListener("click", () => {
      openExtractFolderPicker(srcName, srcFolder, srcPath, row.dataset.folder, row.dataset.path);
    });
  });

  document.getElementById("extPickerCancel").addEventListener("click", closeCenterModal);
  document.getElementById("extPickerBack").addEventListener("click", () => {
    if (!currentPath) {
      openExtractFolderPicker(srcName, srcFolder, srcPath, null, "");
    } else {
      const parts = currentPath.split("/");
      parts.pop();
      openExtractFolderPicker(srcName, srcFolder, srcPath, currentFolder, parts.join("/"));
    }
  });

  document.getElementById("extPickerNewFolder").addEventListener("click", async () => {
    const name = await promptModal("Nueva carpeta", "Nombre de la carpeta");
    if (!name) return;
    try {
      await api("/api/files/mkdir", {
        method: "POST",
        body: JSON.stringify({ folder: currentFolder, path: currentPath, name }),
      });
      openExtractFolderPicker(srcName, srcFolder, srcPath, currentFolder, currentPath);
    } catch (e) {
      tgAlert(e.message);
    }
  });

  document.getElementById("extPickerExtractHere").addEventListener("click", () => {
    executeExtract(srcFolder, srcPath, currentFolder, currentPath);
  });
}

async function executeExtract(folder, path, destFolder, destPath, password = null) {
  try {
    const res = await api("/api/files/extract", {
      method: "POST",
      body: JSON.stringify({
        folder,
        path,
        dest_folder: destFolder,
        dest_path: destPath,
        password,
      }),
    });

    if (res && res.needs_password) {
      promptExtractPassword(folder, path, destFolder, destPath);
      return;
    }

    closeCenterModal();
    if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
    tgAlert("Tarea de descompresión añadida a la cola.");
    document.querySelector('.tab[data-tab="queue"]').click();
    refreshQueue();
  } catch (e) {
    if (e.message && e.message.toLowerCase().includes("contraseña")) {
      promptExtractPassword(folder, path, destFolder, destPath, e.message);
    } else {
      closeCenterModal();
      tgAlert(e.message);
    }
  }
}

function promptExtractPassword(folder, path, destFolder, destPath, errorMsg = "") {
  renderCenter(`
    <h3>${icon("lock", 18)} Archivo protegido</h3>
    <p class="hint-small">Introduce la contraseña para descomprimir el archivo:</p>
    <input type="password" id="extractPasswordInput" placeholder="Contraseña">
    <div id="extractPasswordError">${errorMsg ? `<p class="modal-error">${escapeHtml(errorMsg)}</p>` : ""}</div>
    <div class="center-modal-footer">
      <button class="btn btn-secondary" id="extractPasswordCancel">Cancelar</button>
      <button class="btn btn-primary" id="extractPasswordSubmit">Aceptar</button>
    </div>
  `);

  document.getElementById("extractPasswordInput").focus();
  document.getElementById("extractPasswordCancel").addEventListener("click", closeCenterModal);
  document.getElementById("extractPasswordSubmit").addEventListener("click", () => {
    const pwd = document.getElementById("extractPasswordInput").value;
    if (!pwd) return;
    executeExtract(folder, path, destFolder, destPath, pwd);
  });
}

function showActionSheet(title, actions) {
  const root = document.getElementById("modalRoot");
  root.innerHTML = `
    <div class="modal-backdrop">
      <div class="modal-box">
        <h3>${escapeHtml(title)}</h3>
        <div class="modal-actions" style="flex-direction:column;align-items:stretch;">
          ${actions
            .map(
              (a, i) =>
                `<button class="btn ${a.danger ? "btn-danger" : "btn-secondary"}" style="margin-bottom:8px;" data-idx="${i}">${a.label}</button>`
            )
            .join("")}
          <button class="btn btn-secondary" id="modalClose">Cancelar</button>
        </div>
      </div>
    </div>
  `;
  root.querySelectorAll("[data-idx]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const idx = parseInt(btn.dataset.idx, 10);
      root.innerHTML = "";
      actions[idx].run();
    });
  });
  document.getElementById("modalClose").addEventListener("click", () => (root.innerHTML = ""));
}

function promptModal(title, label, defaultValue = "") {
  return new Promise((resolve) => {
    const root = document.getElementById("modalRoot");
    root.innerHTML = `
      <div class="modal-backdrop">
        <div class="modal-box">
          <h3>${escapeHtml(title)}</h3>
          <input type="text" id="modalInput" placeholder="${escapeHtml(label)}" value="${escapeHtml(defaultValue)}">
          <div class="modal-actions">
            <button class="btn btn-secondary" id="modalCancel">Cancelar</button>
            <button class="btn btn-primary" id="modalOk">Aceptar</button>
          </div>
        </div>
      </div>
    `;
    const input = document.getElementById("modalInput");
    input.focus();
    document.getElementById("modalCancel").addEventListener("click", () => {
      root.innerHTML = "";
      resolve(null);
    });
    document.getElementById("modalOk").addEventListener("click", () => {
      const value = input.value.trim();
      root.innerHTML = "";
      resolve(value || null);
    });
  });
}

function confirmModal(message) {
  return new Promise((resolve) => {
    const root = document.getElementById("modalRoot");
    root.innerHTML = `
      <div class="modal-backdrop">
        <div class="modal-box">
          <h3>${escapeHtml(message)}</h3>
          <div class="modal-actions">
            <button class="btn btn-secondary" id="modalCancel">Cancelar</button>
            <button class="btn btn-danger" id="modalOk">Eliminar</button>
          </div>
        </div>
      </div>
    `;
    document.getElementById("modalCancel").addEventListener("click", () => {
      root.innerHTML = "";
      resolve(false);
    });
    document.getElementById("modalOk").addEventListener("click", () => {
      root.innerHTML = "";
      resolve(true);
    });
  });
}

function tgAlert(message) {
  if (window.__tr) message = window.__tr(message);
  if (tg && tg.showAlert) {
    tg.showAlert(message);
  } else {
    showActionSheet(message, []);
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

const addTask = {
  step: null,
  kind: null,
  taskIds: [],
  normalTaskIds: [],
  taskInfos: [],
  extract: false,
  torrentId: null,
  torrentName: "",
  files: [],
  selected: new Set(),
  folder: null,
  path: "",
};

function isDriveUrl(url) {
  return /drive\.google\.com/i.test(url || "");
}

const ARCHIVE_EXTENSIONS = [
  ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz", ".tar",
  ".zip", ".rar", ".7z", ".gz", ".bz2", ".xz",
];

function isArchiveFilename(name) {
  const lower = (name || "").toLowerCase();
  return ARCHIVE_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

function setupAddTask() {
  document.getElementById("fabAdd").addEventListener("click", openAddTask);
}

function closeCenterModal() {
  document.getElementById("centerModalRoot").innerHTML = "";
}

function closeAddTask() {
  closeCenterModal();
  addTask.step = null;
  addTask.kind = null;
  addTask.provider = null;
  addTask.selectFiles = true;
  addTask.taskIds = [];
  addTask.normalTaskIds = [];
  addTask.taskInfos = [];
  addTask.extract = false;
  addTask.torrentId = null;
  addTask.files = [];
  addTask.selected = new Set();
  addTask.folder = null;
  addTask.path = "";
  addTask.schedule = "now";
  addTask.renameBase = null;
  addTask.extractOn = null;
}

function renderCenter(html, opts) {
  opts = opts || {};
  const fs = !!addTask.step;
  const closeSvg = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>';
  const backSvg = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 6l-6 6 6 6"/></svg>';
  const btn = fs ? `<button type="button" class="fs-close" id="fsClose" aria-label="${opts.back ? "Atrás" : "Cerrar"}">${opts.back ? backSvg : closeSvg}</button>` : "";
  const root = document.getElementById("centerModalRoot");
  const ex = root.querySelector(".center-modal-backdrop.fs");
  if (fs && ex) {
    // Mismo fondo: solo cambia el contenido, sin parpadeo ni nueva animación
    const box = ex.querySelector(".center-modal-box");
    box.innerHTML = `${btn}<div class="fs-body">${html}</div>`;
    box.scrollTop = 0;
  } else {
    root.innerHTML = `
    <div class="center-modal-backdrop${fs ? " fs" : ""}" id="centerBackdrop">
      <div class="center-modal-box${fs ? " fs-box" : ""}">${btn}${fs ? `<div class="fs-body">${html}</div>` : html}</div>
    </div>
  `;
  }
  const x = document.getElementById("fsClose");
  if (x) x.addEventListener("click", opts.back ? addTaskFolderBack : closeAddTask);
}

function openAddTask() {
  addTask.step = "input";
  renderCenter(`
    <h3 class="fs-title">Nueva descarga</h3>
    <div class="nd1-hero">
      <div class="nd1-tile">${icon("plus", 22)}</div>
      <div><div class="nd1-h">¿Qué quieres descargar?</div><div class="nd1-s">Pega un enlace, varios enlaces o un magnet.</div></div>
    </div>
    <div class="nd1-field">
      <textarea id="taskInput" placeholder="${escapeHtml((window.__tr || ((x) => x))("https://… o magnet:?xt=…"))}" rows="5"></textarea>
      <button type="button" class="nd1-paste" id="atPaste">${icon("copy", 15)} Pegar</button>
    </div>
    <div class="nd1-kinds">
      <span class="nd1-kind">${icon("download", 13)} Enlace directo</span>
      <span class="nd1-kind">${icon("bolt", 13)} Magnet</span>
      <span class="nd1-kind">${icon("folder", 13)} Google Drive</span>
      <span class="nd1-kind">${icon("video", 13)} Vídeo</span>
    </div>
    <p class="hint-small">Puedes pegar varios enlaces directos o de Google Drive, uno por línea. Para un torrent, pega el enlace magnet.</p>
    <div id="addTaskError"></div>
    <div class="center-modal-footer">
      <button class="btn btn-primary fs-main" id="atContinue">Continuar</button>
    </div>
  `);
  document.getElementById("taskInput").focus();
  document.getElementById("atContinue").addEventListener("click", handleInputContinue);
  document.getElementById("atPaste").addEventListener("click", async () => {
    try {
      const t = await navigator.clipboard.readText();
      if (t) document.getElementById("taskInput").value = t;
    } catch (e) {
      document.getElementById("taskInput").focus();
    }
  });
}

function showAddTaskError(message) {
  document.getElementById("addTaskError").innerHTML = `<p class="modal-error">${escapeHtml(message)}</p>`;
}

async function handleInputContinue() {
  const raw = document.getElementById("taskInput").value.trim();
  if (!raw) return;

  const lines = raw.split("\n").map((l) => l.trim()).filter(Boolean);
  const magnets = lines.filter((l) => l.startsWith("magnet:?"));
  const urls = lines.filter((l) => l.startsWith("http://") || l.startsWith("https://"));

  const btn = document.getElementById("atContinue");
  btn.textContent = "Procesando...";
  btn.disabled = true;

  try {
    if (magnets.length > 0) {
      if (magnets.length > 1) {
        showAddTaskError("Solo se puede procesar un magnet a la vez. Se usará el primero.");
      }
      await startMagnetFlow(magnets[0]);
    } else if (urls.length > 0) {
      const ytdlUrls = urls.filter(isYtdlUrl);
      if (ytdlUrls.length > 0) {
        await startYtdlFlow(ytdlUrls[0]);
        if (ytdlUrls.length > 1) {
          tgAlert(`Se detectaron ${ytdlUrls.length} enlaces de vídeo. Se procesará el primero.`);
        }
      } else {
        await startLinksFlow(urls);
      }
    } else {
      showAddTaskError("No se detectó ningún enlace ni magnet válido.");
      btn.textContent = "Continuar";
      btn.disabled = false;
    }
  } catch (e) {
    showAddTaskError(e.message);
    btn.textContent = "Continuar";
    btn.disabled = false;
  }
}

async function startYtdlFlow(url) {
  addTask.kind = "ytdl";
  addTask.ytdlUrl = url;

  try {
    const data = await api("/api/ytdl/info", {
      method: "POST",
      body: JSON.stringify({ url }),
    });

    if (!data.ok) throw new Error(data.detail || "Error al analizar el enlace");

    addTask.ytdlInfo = data;
    addTask.ytdlSelectedOption = (data.options && data.options.length > 0) ? data.options[0] : null;

    renderYtdlOptionsStep();
  } catch (e) {
    tgAlert(e.message || "No se pudo analizar el enlace de vídeo");
    closeAddTask();
  }
}

function ytdlHost(u) {
  try { return new URL(u).hostname.replace("www.", ""); } catch (e) { return ""; }
}

function renderYtdlOptionsStep() {
  addTask.step = "ytdl_options";
  const info = addTask.ytdlInfo;
  const opt = addTask.ytdlSelectedOption;

  let folders = window.appFolders || [];
  const statePromise = api("/api/state").catch(() => ({ folders }));

  renderCenter(`
    <h3>${icon("video", 18)} ${escapeHtml(info.title || "Vídeo")}</h3>
    <div class="ytdl-preview-mini" style="display:flex;gap:10px;align-items:flex-start;margin-bottom:12px;">
      <div class="ytdl-thumb-mini">
        ${info.thumbnail ? `<img src="${escapeHtml(info.thumbnail)}" alt="" style="width:120px;height:68px;object-fit:cover;border-radius:8px;">` : ""}
        ${info.duration_str ? `<div class="ytdl-duration-badge-mini" style="position:absolute;bottom:4px;right:4px;background:rgba(0,0,0,0.8);color:#fff;padding:2px 6px;border-radius:4px;font-size:11px;">${escapeHtml(info.duration_str)}</div>` : ""}
      </div>
      <div style="flex:1;min-width:0;">
        <div class="card-sub" style="margin-bottom:4px;">${escapeHtml(info.title || "Vídeo")}</div>
        <div class="card-sub">${info.duration_str ? "⏱ " + escapeHtml(info.duration_str) + " · " : ""}${escapeHtml(ytdlHost(info.url || addTask.ytdlUrl))}</div>
      </div>
    </div>

    <div class="filter-group-label" style="margin-bottom:8px;">Calidad y Formato:</div>
    <div id="atYtdlOptionsChips" class="filter-chips" style="gap:8px;margin-bottom:16px;max-height:120px;overflow-y:auto;"></div>

    <div class="filter-group-label" style="margin-bottom:8px;">Carpeta destino en el NAS:</div>
    <div class="filter-chips" id="atYtdlFolderChips" style="gap:8px;margin-bottom:16px;">
      ${folders.map((f, i) => `<button class="f-chip" data-folder="${escapeHtml(f)}" type="button">📁 ${escapeHtml(f)}</button>`).join("")}
    </div>

    <div class="filter-group-label" style="margin-top:10px;margin-bottom:6px;">⏰ Programar inicio:</div>
    <div class="filter-chips schedule-chips" id="atYtdlScheduleChips" style="margin-bottom:16px;">
      <button type="button" class="f-chip active" data-sched="now">⚡ Ahora</button>
      <button type="button" class="f-chip" data-sched="1h">⏱️ En 1h</button>
      <button type="button" class="f-chip" data-sched="2h">⏱️ En 2h</button>
      <button type="button" class="f-chip" data-sched="4h">⏱️ En 4h</button>
      <button type="button" class="f-chip" data-sched="night">🌙 De madrugada</button>
    </div>

    <div class="center-modal-footer">
      <button class="btn btn-secondary" id="atYtdlBack">${icon("arrowLeft", 14)} Volver</button>
      <button class="btn btn-primary" id="atYtdlConfirm">${icon("down", 14)} <span id="atYtdlConfirmText">Descargar al NAS</span></button>
    </div>
  `);

  const optsContainer = document.getElementById("atYtdlOptionsChips");
  if (info.options && info.options.length > 0) {
    info.options.forEach((o, idx) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = `f-chip ${idx === 0 ? "active" : ""}`;
      chip.innerHTML = o.is_audio ? `🎵 ${escapeHtml(o.label)}` : `🎬 ${escapeHtml(o.label)}`;
      chip.addEventListener("click", () => {
        optsContainer.querySelectorAll(".f-chip").forEach((c) => c.classList.remove("active"));
        chip.classList.add("active");
        addTask.ytdlSelectedOption = o;
        if (tg && tg.HapticFeedback) tg.HapticFeedback.selectionChanged();
      });
      optsContainer.appendChild(chip);
    });
  } else {
    optsContainer.innerHTML = '<span class="hint-small">Formato estándar automático</span>';
    addTask.ytdlSelectedOption = { format_spec: "bestvideo+bestaudio/best", is_audio: false };
  }

  const folderChips = document.getElementById("atYtdlFolderChips");
  folderChips.querySelectorAll(".f-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      folderChips.querySelectorAll(".f-chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      addTask.ytdlSelectedFolder = chip.dataset.folder || defaultFolder();
      if (tg && tg.HapticFeedback) tg.HapticFeedback.selectionChanged();
    });
  });
  addTask.ytdlSelectedFolder = null;

  const schedChips = document.getElementById("atYtdlScheduleChips");
  let selectedSchedule = "now";
  schedChips.querySelectorAll(".f-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      schedChips.querySelectorAll(".f-chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      selectedSchedule = chip.dataset.sched || "now";
      const confirmText = document.getElementById("atYtdlConfirmText");
      if (confirmText) confirmText.textContent = selectedSchedule === "now" ? "Descargar al NAS" : "Programar descarga";
      if (tg && tg.HapticFeedback) tg.HapticFeedback.selectionChanged();
    });
  });

  document.getElementById("atYtdlBack").addEventListener("click", () => {
    closeAddTask();
  });

  document.getElementById("atYtdlConfirm").addEventListener("click", async () => {
    const btn = document.getElementById("atYtdlConfirm");
    btn.disabled = true;
    btn.innerHTML = `<span>⏳ Iniciando...</span>`;

    const opt = addTask.ytdlSelectedOption || { format_spec: "bestvideo+bestaudio/best", is_audio: false };
    const folder = addTask.ytdlSelectedFolder;
    if (!folder) {
      tgAlert("Elige una carpeta de destino.");
      btn.disabled = false;
      btn.innerHTML = `${icon("down", 14)} <span id="atYtdlConfirmText">Descargar al NAS</span>`;
      return;
    }

    try {
      const res = await api("/api/ytdl/download", {
        method: "POST",
        body: JSON.stringify({
          url: addTask.ytdlUrl,
          format_spec: opt.format_spec,
          folder,
          is_audio: !!opt.is_audio,
          title: info.title || "",
          schedule: selectedSchedule,
        }),
      });

      if (res && res.ok) {
        closeAddTask();
        document.querySelector('.tab[data-tab="queue"]').click();
        refreshQueue();
        if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
      }
    } catch (e) {
      tgAlert(e.message || "Error al iniciar la descarga");
      btn.disabled = false;
      btn.innerHTML = `${icon("down", 14)} <span>Reintentar</span>`;
    }
  });
}

async function startLinksFlow(urls) {
  const driveUrls = urls.filter(isDriveUrl);
  const normalUrls = urls.filter((u) => !isDriveUrl(u));

  addTask.kind = "links";
  addTask.taskIds = [];
  addTask.normalTaskIds = [];
  addTask.taskInfos = [];

  if (driveUrls.length) {
    try {
      const gdriveData = await api("/api/tasks/create_gdrive", {
        method: "POST",
        body: JSON.stringify({ urls: driveUrls }),
      });
      addTask.taskIds.push(...gdriveData.tasks.map((t) => t.id));
      addTask.taskInfos.push(...gdriveData.tasks);
      if (gdriveData.errors && gdriveData.errors.length) {
        tgAlert(gdriveData.errors.join("\n"));
      }
    } catch (e) {
      tgAlert(e.message);
    }
  }

  let rdAvailable = false;
  let tbAvailable = false;
  if (normalUrls.length) {
    const data = await api("/api/tasks/create_links", {
      method: "POST",
      body: JSON.stringify({ urls: normalUrls }),
    });
    addTask.normalTaskIds = data.tasks.map((t) => t.id);
    addTask.taskIds.push(...addTask.normalTaskIds);
    addTask.taskInfos.push(...data.tasks);
    rdAvailable = data.rd_available;
    tbAvailable = data.tb_available;
  }

  if (!addTask.taskIds.length) {
    closeAddTask();
    return;
  }

  if (addTask.normalTaskIds.length && (rdAvailable || tbAvailable)) {
    renderMethodStep(rdAvailable, tbAvailable);
  } else {
    goOneScreen();
  }
}

function renderMethodStep(rd = true, tb = false) {
  addTask.step = "method";
  renderCenter(`
    <h3>¿Cómo quieres descargarlo?</h3>
    <div class="method-choice">
      <button class="btn btn-secondary" id="methodAria2">${icon("bolt", 22)}<br>Aria2<br><span style="font-weight:400;font-size:11px;">directo</span></button>
      ${rd ? `<button class="btn btn-secondary" id="methodRd">${icon("card", 22)}<br>Real-Debrid</button>` : ""}
      ${tb ? `<button class="btn btn-secondary" id="methodTb">${icon("card", 22)}<br>TorBox</button>` : ""}
    </div>
    <div class="center-modal-footer">
      <button class="btn btn-secondary" id="atCancel">Cancelar</button>
    </div>
  `);
  document.getElementById("atCancel").addEventListener("click", closeAddTask);
  document.getElementById("methodAria2").addEventListener("click", () => chooseMethod("aria2"));
  const mrd = document.getElementById("methodRd");
  if (mrd) mrd.addEventListener("click", () => chooseMethod("rd"));
  const mtb = document.getElementById("methodTb");
  if (mtb) mtb.addEventListener("click", () => chooseMethod("tb"));
}

async function chooseMethod(method) {
  try {
    await api("/api/tasks/set_method", {
      method: "POST",
      body: JSON.stringify({ ids: addTask.normalTaskIds, method }),
    });
    goOneScreen();
  } catch (e) {
    tgAlert(e.message);
  }
}

async function startMagnetFlow(magnet) {
  await prepareTorrent({ magnet });
}

function renderFilesStep() {
  addTask.step = "files";
  const rows = addTask.files
    .map(
      (f) => `
      <label class="file-pick-row">
        <input type="checkbox" data-fid="${f.id}" ${addTask.selected.has(f.id) ? "checked" : ""}>
        <div class="fname-wrapper">
          <div class="fname">${escapeHtml(f.name)}</div>
          <div class="fsize">${escapeHtml(f.size)}</div>
        </div>
      </label>`
    )
    .join("");

  renderCenter(`
    <h3>${icon("archive", 18)} Archivos del Torrent</h3>
    <p class="hint-small" style="text-align:left;word-break:break-word;"><b>${escapeHtml(addTask.torrentName)}</b></p>
    <div class="file-select-all-bar">
      <button class="btn btn-secondary" id="atSelAll">${icon("check", 13)} Seleccionar todo</button>
      <button class="btn btn-secondary" id="atSelNone">${icon("x", 13)} Deseleccionar todo</button>
    </div>
    <div style="max-height:260px;overflow-y:auto;margin-bottom:14px;border:1px solid var(--border);border-radius:var(--radius-sm);padding:4px 8px;">${rows}</div>
    <div class="center-modal-footer">
      <button class="btn btn-secondary" id="atCancel">Cancelar</button>
      <button class="btn btn-primary" id="atContinue">Continuar</button>
    </div>
  `);

  document.querySelectorAll('.file-pick-row input[type=checkbox]').forEach((cb) => {
    cb.addEventListener("change", () => {
      const fid = parseInt(cb.dataset.fid, 10);
      if (cb.checked) addTask.selected.add(fid);
      else addTask.selected.delete(fid);
    });
  });

  document.getElementById("atSelAll").addEventListener("click", () => {
    addTask.files.forEach(f => addTask.selected.add(f.id));
    document.querySelectorAll('.file-pick-row input[type=checkbox]').forEach(cb => cb.checked = true);
  });

  document.getElementById("atSelNone").addEventListener("click", () => {
    addTask.selected.clear();
    document.querySelectorAll('.file-pick-row input[type=checkbox]').forEach(cb => cb.checked = false);
  });

  document.getElementById("atCancel").addEventListener("click", closeAddTask);
  document.getElementById("atContinue").addEventListener("click", async () => {
    if (addTask.selected.size === 0) {
      tgAlert("Selecciona al menos un archivo.");
      return;
    }
    try {
      await api("/api/rd/magnet/select", {
        method: "POST",
        body: JSON.stringify({ torrent_id: addTask.torrentId, selected: [...addTask.selected] }),
      });
      goOneScreen();
    } catch (e) {
      tgAlert(e.message);
    }
  });
}

function addTaskFolderBack() {
  if (addTask.folder === null) {
    if (addTask.chosen && addTask.chosen.folder) renderOptionsStep(addTask.chosen.folder, addTask.chosen.path);
    else closeAddTask();
    return;
  }
  if (!addTask.path) {
    renderFolderStep(null, "");
    return;
  }
  const parts = addTask.path.split("/");
  parts.pop();
  renderFolderStep(addTask.folder, parts.join("/"));
}

async function renderFolderStep(folder, path) {
  addTask.step = "folder";
  addTask.folder = folder;
  addTask.path = path || "";
  const rowHtml = (name, meta, attrs) => `<button type="button" class="fp-row" ${attrs}>
      <span class="fp-tile">${icon("folder", 18)}</span>
      <span class="fp-name">${escapeHtml(name)}</span>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg></button>`;

  if (folder === null) {
    let folders = window.appFolders || [];
    try {
      const state = await api("/api/state");
      folders = state.folders;
    } catch (e) {
    }
    renderCenter(`
      <h3 class="fs-title">Carpeta de destino</h3>
      <p class="fp-sub">Elige dónde se guardará la descarga.</p>
      <div class="fp-list">${folders.map((f) => rowHtml(f, "", `data-folder="${escapeHtml(f)}"`)).join("")}</div>
    `, { back: true });
    document.querySelectorAll(".fp-row").forEach((row) => {
      row.addEventListener("click", () => renderFolderStep(row.dataset.folder, ""));
    });
    return;
  }

  let data;
  try {
    data = await api(`/api/files?folder=${encodeURIComponent(folder)}&path=${encodeURIComponent(path)}&sizes=0`);
  } catch (e) {
    showFolderStepError(folder, path, e.message);
    return;
  }

  const dirRows = data.dirs
    .map((d) => rowHtml(d.name, "", `data-folder="${escapeHtml(folder)}" data-path="${escapeHtml(path ? `${path}/${d.name}` : d.name)}"`))
    .join("");
  const crumbs = [folder].concat(path ? path.split("/") : []);
  const label = path ? `${folder}/${path}` : folder;

  renderCenter(`
    <h3 class="fs-title">Carpeta de destino</h3>
    <div class="fp-crumb">${crumbs.map((c, i) => `<span${i === crumbs.length - 1 ? ' class="cur"' : ""}>${escapeHtml(c)}</span>`).join('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>')}</div>
    <div class="fp-list">${dirRows || '<p class="empty">Sin subcarpetas</p>'}</div>
    <div class="center-modal-footer fs-footer">
      <button class="btn btn-primary fs-main" id="atSaveHere">${icon("check", 18)} <span>Guardar en</span> <span class="nm">${escapeHtml(path ? path.split("/").pop() : folder)}</span></button>
    </div>
  `, { back: true });

  document.querySelectorAll(".fp-row").forEach((row) => {
    row.addEventListener("click", () => renderFolderStep(row.dataset.folder, row.dataset.path));
  });
  document.getElementById("atSaveHere").addEventListener("click", () => renderOptionsStep(folder, path));
}

function showFolderStepError(folder, path, message) {
  renderCenter(`
    <h3 class="fs-title">${escapeHtml(folder)}</h3>
    <p class="modal-error">${escapeHtml(message)}</p>
  `, { back: true });
}

function goOneScreen() {
  renderOptionsStep(addTask.folder || null, addTask.path || "");
}

function renderOptionsStep(folder, path) {
  addTask.step = "options";
  addTask.folder = folder;
  addTask.path = path || "";
  addTask.chosen = folder ? { folder, path: path || "" } : null;

  let hasArchive = false;
  let archiveCount = 0;

  if (addTask.kind === "links") {
    for (const t of addTask.taskInfos || []) {
      if (isArchiveFilename(t.filename)) {
        hasArchive = true;
        archiveCount++;
      }
    }
  } else if (addTask.kind === "magnet" && addTask.provider === "torbox") {
    hasArchive = false;
  } else if (addTask.kind === "magnet") {
    if (addTask.selected.size > 1) {
      hasArchive = true;
      archiveCount = addTask.selected.size;
    } else {
      for (const f of addTask.files || []) {
        if (addTask.selected.has(f.id) && isArchiveFilename(f.name)) {
          hasArchive = true;
          archiveCount++;
        }
      }
    }
  }

  const single = addTask.kind === "links" && (addTask.taskInfos || []).length === 1 ? addTask.taskInfos[0] : null;
  const origName = single ? single.filename || "" : "";
  const dot = origName.lastIndexOf(".");
  const origBase = dot > 0 ? origName.slice(0, dot) : origName;
  const origExt = dot > 0 ? origName.slice(dot) : "";
  const destLabel = !folder ? "" : path ? `${folder}/${path}` : folder;
  let selectedSchedule = addTask.schedule || "now";
  const sizeTxt = single && single.size ? ` · ${single.size}` : "";
  const infos = addTask.kind === "links" ? addTask.taskInfos || [] : [];
  const bigLabel = single && single.size ? `Descargar ${single.size}` : infos.length > 1 ? `Descargar ${infos.length} archivos` : "Descargar";

  renderCenter(`
    <h3 class="fs-title">Nueva descarga</h3>
    ${single ? `<div class="nd-file">${isArchiveFilename(origName) ? icon("archive", 20) : icon("document", 20)}<div><div class="nd-file-name">${escapeHtml(origName)}</div><div class="nd-file-sub">${escapeHtml(sizeTxt.replace(/^ · /, ""))}</div></div></div>` : ""}

    <button type="button" class="nd-row" id="atChangeDest">
      <span class="file-icon folder-icon">${icon("folder", 18)}</span>
      <span class="nd-row-main"><span class="nd-row-label">Carpeta</span><span class="nd-row-value${destLabel ? "" : " nd-empty"}">${destLabel ? escapeHtml(destLabel) : "Elige una carpeta"}</span></span>
      <span class="nd-chevron">${icon("arrowLeft", 16)}</span>
    </button>

    ${single ? `
    <div class="nd-field">
      <div class="nd-field-head"><label for="atRenameInput">Nombre del archivo <span class="nd-optional">(opcional)</span></label><button type="button" class="btn-link-small" id="atRenameReset">Restablecer</button></div>
      <div class="nd-input-row">
        <input type="text" id="atRenameInput" value="${escapeHtml(addTask.renameBase != null ? addTask.renameBase : origBase)}" autocomplete="off">
        ${origExt ? `<span class="nd-ext">${escapeHtml(origExt)}</span>` : ""}
      </div>
      <div class="hint-small" style="text-align:left;margin-top:6px;">Se guarda con este nombre. La extensión se mantiene.</div>
    </div>` : ""}

    ${addTask.kind === "magnet" && addTask.provider === "torbox" && !addTask.selectFiles ? `
    <div class="option-row" style="margin-bottom:12px;">
      <div class="option-desc">📦 <b>TorBox (sin caché):</b> primero lo descarga TorBox y luego se baja al NAS como ZIP, que se descomprimirá automáticamente en esta carpeta.</div>
    </div>` : ""}

    ${hasArchive ? `
    <div class="option-row" style="margin-bottom:12px;">
      <div style="flex:1;padding-right:12px;">
        <div class="option-title">📦 Descomprimir al terminar</div>
        <div class="option-desc"><span style="color:var(--yellow);font-weight:600;">Archivos comprimidos detectados (${archiveCount})</span></div>
      </div>
      <label class="toggle-switch">
        <input type="checkbox" id="atExtractToggle" ${addTask.extractOn === false ? "" : "checked"}>
        <span class="toggle-slider"></span>
      </label>
    </div>` : ""}

    <div class="nd-field">
      <div class="nd-field-head"><span>Cuándo descargar</span></div>
      <div class="filter-chips schedule-chips" id="atScheduleChips">
        <button type="button" class="f-chip" data-sched="now">⚡ Ahora</button>
        <button type="button" class="f-chip" data-sched="1h">⏱️ En 1h</button>
        <button type="button" class="f-chip" data-sched="2h">⏱️ En 2h</button>
        <button type="button" class="f-chip" data-sched="4h">⏱️ En 4h</button>
        <button type="button" class="f-chip" data-sched="night">🌙 De madrugada</button>
        <button type="button" class="f-chip" data-sched="at">🗓️ Elegir hora</button>
      </div>
      <input type="datetime-local" id="atScheduleAt" class="nd-datetime hidden">
    </div>

    <div class="center-modal-footer fs-footer">
      <button class="btn btn-primary fs-main" id="atConfirmFinal">${icon("download", 18)} <span id="atConfirmFinalText">${folder ? bigLabel : "Elegir carpeta"}</span></button>
    </div>
  `);

  const schedChips = document.getElementById("atScheduleChips");
  const confirmBtnText = document.getElementById("atConfirmFinalText");
  const atInput = document.getElementById("atScheduleAt");

  const applySched = (value) => {
    selectedSchedule = value;
    addTask.schedule = value;
    schedChips.querySelectorAll(".f-chip").forEach((c) => c.classList.toggle("active", c.dataset.sched === value));
    atInput.classList.toggle("hidden", value !== "at");
    if (confirmBtnText) confirmBtnText.textContent = !folder ? "Elegir carpeta" : value === "now" ? bigLabel : "Programar descarga";
  };
  schedChips.querySelectorAll(".f-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      applySched(chip.dataset.sched || "now");
      if (chip.dataset.sched === "at" && !atInput.value) {
        const d = new Date(Date.now() + 3600 * 1000);
        d.setMinutes(0, 0, 0);
        const pad = (n) => String(n).padStart(2, "0");
        atInput.value = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:00`;
      }
      if (tg && tg.HapticFeedback) tg.HapticFeedback.selectionChanged();
    });
  });
  applySched(selectedSchedule);

  document.getElementById("atChangeDest").addEventListener("click", () => renderFolderStep(folder || null, path));

  const extractEl = document.getElementById("atExtractToggle");
  if (extractEl) extractEl.addEventListener("change", () => { addTask.extractOn = extractEl.checked; });
  const renameInput = document.getElementById("atRenameInput");
  if (renameInput) {
    renameInput.addEventListener("input", () => { addTask.renameBase = renameInput.value; });
    document.getElementById("atRenameReset").addEventListener("click", () => {
      renameInput.value = origBase;
      addTask.renameBase = null;
    });
  }

  document.getElementById("atConfirmFinal").addEventListener("click", () => {
    if (!folder) { renderFolderStep(null, ""); return; }
    const extractToggle = document.getElementById("atExtractToggle");
    const extract = extractToggle ? extractToggle.checked : false;
    let newName = null;
    if (renameInput) {
      const typed = renameInput.value.trim();
      if (typed && typed !== origBase) newName = typed + origExt;
    }
    if (selectedSchedule === "at" && !atInput.value) {
      tgAlert("Elige la fecha y la hora de inicio.");
      return;
    }
    finalizeAddTask(folder, path, {
      extract,
      schedule: selectedSchedule,
      scheduleAt: selectedSchedule === "at" ? atInput.value : null,
      newName,
    });
  });
}

async function finalizeAddTask(folder, path, options = {}) {
  const btn = document.getElementById("atConfirmFinal");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span>⏳ Procesando...</span>`;
  }
  try {
    if (addTask.kind === "links") {
      await api("/api/tasks/set_destination", {
        method: "POST",
        body: JSON.stringify({
          ids: addTask.taskIds,
          folder,
          path,
          extract: !!options.extract,
          schedule: options.schedule || "now",
          schedule_at: options.scheduleAt || null,
          new_name: options.newName || null,
        }),
      });
    } else if (addTask.kind === "magnet") {
      await api("/api/rd/magnet/confirm", {
        method: "POST",
        body: JSON.stringify({
          torrent_id: addTask.torrentId,
          folder,
          path,
          extract: !!options.extract,
          schedule: options.schedule || "now",
          schedule_at: options.scheduleAt || null,
        }),
      });
    }
    closeAddTask();
    document.querySelector('.tab[data-tab="queue"]').click();
    refreshQueue();
    if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
  } catch (e) {
    tgAlert(e.message || "Error al procesar la descarga");
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `${icon("check", 14)} <span>Reintentar</span>`;
    }
  }
}

async function loadUserbotInfo() {
  const card = document.getElementById("userbotCard");
  card.innerHTML = `<p class="empty">Consultando...</p>`;
  try {
    const info = await api("/api/userbot");
    if (info.connected) {
      const dateText = (info.connected_at || "").replace("T", " ").slice(0, 16);
      card.innerHTML = `
        <div class="card">
          <div class="card-title"><span class="dot-inline green"></span> ${escapeHtml(info.first_name || "Conectado")}</div>
          <div class="card-sub">
            ID: ${info.user_id ?? "?"}${info.username ? " · @" + escapeHtml(info.username) : ""}
            <br>Conectado desde: ${dateText || "desconocido"}
          </div>
          <div class="card-actions">
            <button class="btn btn-secondary" id="ubChange">${icon("plug", 14)} Cambiar cuenta</button>
            <button class="btn btn-danger" id="ubDisconnect">${icon("x", 14)} Desconectar</button>
          </div>
        </div>
      `;
      document.getElementById("ubChange").addEventListener("click", openUserbotConnect);
      document.getElementById("ubDisconnect").addEventListener("click", async () => {
        const confirmed = await confirmModal(
          "¿Desconectar el userbot? Las descargas de Telegram dejarán de funcionar hasta que conectes otra cuenta."
        );
        if (!confirmed) return;
        try {
          await api("/api/userbot/disconnect", { method: "POST" });
          loadUserbotInfo();
        } catch (e) {
          tgAlert(e.message);
        }
      });
    } else {
      card.innerHTML = `
        <div class="card">
          <div class="card-title"><span class="dot-inline red"></span> Desconectado</div>
          <div class="card-actions">
            <button class="btn btn-primary" id="ubConnect">${icon("plug", 14)} Conectar</button>
          </div>
        </div>
      `;
      document.getElementById("ubConnect").addEventListener("click", openUserbotConnect);
    }
  } catch (e) {
    card.innerHTML = `<p class="empty">${escapeHtml(e.message)}</p>`;
  }
}

function openUserbotConnect() {
  renderCenter(`
    <h3>${icon("plug", 18)} Conectar cuenta de Telegram</h3>
    <input type="text" id="ubInput" placeholder="+34600000000">
    <p class="hint-small">Número completo con prefijo internacional.</p>
    <div id="ubError"></div>
    <div class="center-modal-footer">
      <button class="btn btn-secondary" id="ubCancel">Cancelar</button>
      <button class="btn btn-primary" id="ubNext">Continuar</button>
    </div>
  `);
  document.getElementById("ubInput").focus();
  document.getElementById("ubCancel").addEventListener("click", closeCenterModal);
  document.getElementById("ubNext").addEventListener("click", async () => {
    const phone = document.getElementById("ubInput").value.trim();
    if (!phone) return;
    await _userbotStep("/api/userbot/connect/start", { phone }, "ubNext", "Enviando...", () => {
      openUserbotCodeStep();
    });
  });
}

function openUserbotCodeStep() {
  renderCenter(`
    <h3>${icon("mail", 18)} Código de verificación</h3>
    <input type="text" id="ubInput" placeholder="12345" inputmode="numeric">
    <p class="hint-small">Revisa los mensajes de Telegram en esa cuenta.</p>
    <div id="ubError"></div>
    <div class="center-modal-footer">
      <button class="btn btn-secondary" id="ubCancel">Cancelar</button>
      <button class="btn btn-primary" id="ubNext">Continuar</button>
    </div>
  `);
  document.getElementById("ubInput").focus();
  document.getElementById("ubCancel").addEventListener("click", closeCenterModal);
  document.getElementById("ubNext").addEventListener("click", async () => {
    const code = document.getElementById("ubInput").value.trim();
    if (!code) return;
    await _userbotStep("/api/userbot/connect/code", { code }, "ubNext", "Verificando...", (res) => {
      if (res.needs_password) {
        openUserbotPasswordStep();
      } else {
        closeCenterModal();
        loadUserbotInfo();
        tgAlert("Userbot conectado correctamente.");
      }
    });
  });
}

function openUserbotPasswordStep() {
  renderCenter(`
    <h3>${icon("lock", 18)} Verificación en dos pasos</h3>
    <input type="password" id="ubInput" placeholder="Contraseña">
    <div id="ubError"></div>
    <div class="center-modal-footer">
      <button class="btn btn-secondary" id="ubCancel">Cancelar</button>
      <button class="btn btn-primary" id="ubNext">Conectar</button>
    </div>
  `);
  document.getElementById("ubInput").focus();
  document.getElementById("ubCancel").addEventListener("click", closeCenterModal);
  document.getElementById("ubNext").addEventListener("click", async () => {
    const password = document.getElementById("ubInput").value;
    if (!password) return;
    await _userbotStep("/api/userbot/connect/password", { password }, "ubNext", "Conectando...", () => {
      closeCenterModal();
      loadUserbotInfo();
      tgAlert("Userbot conectado correctamente.");
    });
  });
}

async function _userbotStep(endpoint, body, btnId, loadingText, onSuccess) {
  const btn = document.getElementById(btnId);
  const originalText = btn.textContent;
  btn.disabled = true;
  btn.textContent = loadingText;
  try {
    const res = await api(endpoint, { method: "POST", body: JSON.stringify(body) });
    onSuccess(res);
  } catch (e) {
    document.getElementById("ubError").innerHTML = `<p class="modal-error">${escapeHtml(e.message)}</p>`;
    btn.disabled = false;
    btn.textContent = originalText;
  }
}


const post = (path, body) => api(path, { method: "POST", body: JSON.stringify(body || {}) });

function humanBytes(n) {
  const u = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  n = Number(n) || 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(i ? 1 : 0)} ${u[i]}`;
}

function switchRow(id, label, checked) {
  return `<label class="switch-row"><span>${label}</span><span class="toggle-switch"><input type="checkbox" id="${id}" ${checked ? "checked" : ""}><span class="toggle-slider"></span></span></label>`;
}

async function loadNotifications() {
  const root = document.getElementById("notifCard");
  const c = await api("/api/notifications");
  root.innerHTML = `
    <p class="hint-small">Avisos con un mensaje nuevo en Telegram cuando una descarga termina o falla.</p>
    <div class="grp">
      <div class="grp-row">${switchRow("nEnabled", "Notificaciones activadas", c.enabled)}</div>
      <div class="grp-row">${switchRow("nDone", "Descarga terminada", c.done)}</div>
      <div class="grp-row">${switchRow("nFailed", "Descarga fallida", c.failed)}</div>
      <div class="grp-row">${switchRow("nDisk", "Aviso de poco espacio", c.disk)}</div>
    </div>
    <h2 class="section-title">Horas silenciosas</h2>
    <div class="grp">
      <div class="grp-row">${switchRow("nQuiet", "Sin sonido en este horario", c.quiet_on)}</div>
      <div class="grp-row"><div class="grp-t"><b>Desde</b></div><div class="stp-unit"><input type="number" id="nFrom" min="0" max="23" value="${c.quiet_from}"><span>h</span></div></div>
      <div class="grp-row"><div class="grp-t"><b>Hasta</b></div><div class="stp-unit"><input type="number" id="nTo" min="0" max="23" value="${c.quiet_to}"><span>h</span></div></div>
    </div>
    <h2 class="section-title">Filtros</h2>
    <div class="grp">
      <div class="grp-row"><div class="grp-t"><b>Tamaño mínimo para avisar</b><small>0 = avisar siempre</small></div><div class="stp-unit"><input type="number" id="nMin" min="0" step="50" value="${c.min_mb}"><span>MB</span></div></div>
      <div class="grp-row stack"><div class="grp-t"><b>Avisar a</b></div>
        <select id="nTo2">
          <option value="requester" ${c.to === "requester" ? "selected" : ""}>Quien lo pidió</option>
          <option value="owner" ${c.to === "owner" ? "selected" : ""}>Solo el propietario</option>
          <option value="both" ${c.to === "both" ? "selected" : ""}>Ambos</option>
        </select></div>
    </div>`;
  const save = async () => {
    try {
      await post("/api/notifications", {
        enabled: root.querySelector("#nEnabled").checked, done: root.querySelector("#nDone").checked,
        failed: root.querySelector("#nFailed").checked, disk: root.querySelector("#nDisk").checked,
        quiet_on: root.querySelector("#nQuiet").checked, quiet_from: Number(root.querySelector("#nFrom").value || 0),
        quiet_to: Number(root.querySelector("#nTo").value || 0), min_mb: Number(root.querySelector("#nMin").value || 0),
        to: root.querySelector("#nTo2").value,
      });
    } catch (e) { tgAlert(e.message); }
  };
  root.querySelectorAll("input,select").forEach((el) => el.addEventListener("change", save));
}

async function loadDisk() {
  const root = document.getElementById("diskCard");
  const d = await api("/api/disk");
  const s = d.settings;
  const modes = [
    ["off", "Desactivado", "No comprobar el espacio antes de descargar", "M6 6l12 12M18 6L6 18", "#5b6472"],
    ["warn", "Avisar y continuar", "Te avisa, pero la descarga empieza igual", "M12 4l9 16H3zM12 10v4M12 17h.01", "#d69a1a"],
    ["reject", "Rechazar si no cabe", "No empieza la descarga si falta espacio", "M12 3a9 9 0 100 18 9 9 0 000-18zM5.6 5.6l12.8 12.8", "#d6542f"],
    ["pause", "Dejar en cola", "Espera en cola hasta que haya espacio", "M12 3a9 9 0 100 18 9 9 0 000-18zm0 5v4l3 2", "#2f7fd6"],
  ];
  const svg = (p) => `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#fff" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${p}"/></svg>`;
  root.innerHTML = `
    <h2 class="section-title">Almacenamiento</h2>
    ${d.volumes.map((v) => {
      const pct = v.total ? Math.round((v.used / v.total) * 100) : 0;
      const cls = pct >= 90 ? "bad" : pct >= 75 ? "warn" : "";
      return `<div class="dk-vol"><div class="dk-top"><span class="pv-tile" style="background:#5b6472">${icon("box", 20)}</span>
        <div class="pv-t"><div class="pv-name">${escapeHtml(v.folders.join(", "))}</div><div class="pv-sub">${humanBytes(v.free)} libres de ${humanBytes(v.total)}</div></div>
        <span class="dk-pct ${cls}">${pct}%</span></div>
        <div class="dk-bar"><div class="dk-fill ${cls}" style="width:${pct}%"></div></div></div>`;
    }).join("")}
    <h2 class="section-title">Si una descarga no cabe</h2>
    <select id="dGuard" class="hidden">${modes.map(([k, t]) => `<option value="${k}" ${s.guard === k ? "selected" : ""}>${t}</option>`).join("")}</select>
    <div class="dk-radios" role="radiogroup">
      ${modes.map(([k, t, sub, ic, col]) => `<button type="button" role="radio" class="dk-radio${s.guard === k ? " on" : ""}" aria-checked="${s.guard === k}" data-mode="${k}">
        <span class="pv-tile sm" style="background:${col}">${svg(ic)}</span>
        <span class="pv-t"><span class="pv-name">${t}</span><span class="pv-sub">${sub}</span></span>
        <span class="dk-dot"><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="#fff" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7"/></svg></span></button>`).join("")}
    </div>
    <h2 class="section-title">Reserva y alertas</h2>
    <div class="grp">
      <div class="grp-row"><div class="grp-t"><b>Reserva libre tras cada descarga</b><small>Espacio que siempre debe quedar libre</small></div>
        <div class="stp-unit"><input type="number" id="dRes" min="0" step="0.5" value="${s.reserve_gb}"><span>GB</span></div></div>
      <div class="grp-row">${switchRow("dAlert", "Alerta de poco espacio", s.alert_on)}</div>
      <div class="grp-row"><div class="grp-t"><b>Avisar por debajo de</b><small>Recibirás un aviso en Telegram</small></div>
        <div class="stp-unit"><input type="number" id="dThr" min="0" step="1" value="${s.alert_gb}"><span>GB</span></div></div>
    </div>`;
  const save = async () => {
    try {
      await post("/api/disk", {
        guard: root.querySelector("#dGuard").value, reserve_gb: Number(root.querySelector("#dRes").value || 0),
        alert_on: root.querySelector("#dAlert").checked, alert_gb: Number(root.querySelector("#dThr").value || 0),
      });
    } catch (e) { tgAlert(e.message); }
  };
  root.querySelectorAll(".dk-radio").forEach((b) => b.addEventListener("click", () => {
    root.querySelector("#dGuard").value = b.dataset.mode;
    root.querySelectorAll(".dk-radio").forEach((x) => { const on = x === b; x.classList.toggle("on", on); x.setAttribute("aria-checked", on); });
    save();
  }));
  root.querySelectorAll("input[type=number],#dAlert").forEach((el) => el.addEventListener("change", save));
}

function openRuleModal(rule, meta) {
  return new Promise((resolve) => {
    const root = document.getElementById("modalRoot");
    const csv = (a) => escapeHtml((a || []).join(", "));
    root.innerHTML = `
      <div class="modal-backdrop"><div class="modal-box" style="max-height:88vh;overflow:auto;">
        <h3>Regla</h3>
        <label>Nombre</label><input type="text" id="rName" value="${escapeHtml(rule.name)}">
        <label>El nombre contiene (alguna, separadas por comas)</label><input type="text" id="rKw" value="${csv(rule.keywords)}">
        <label>El nombre NO contiene</label><input type="text" id="rEx" value="${csv(rule.exclude)}">
        <label>Extensiones</label><input type="text" id="rExt" value="${csv(rule.exts)}" placeholder="mkv, mp4">
        <label>Tipos</label><div>${meta.types.map((t) => `<label style="margin-right:10px"><input type="checkbox" class="rType" value="${t}" ${rule.types.includes(t) ? "checked" : ""}> ${t}</label>`).join("")}</div>
        <label>Tamaño mínimo / máximo (MB)</label><div><input type="number" id="rMin" min="0" value="${rule.min_mb || 0}" style="width:100px"> – <input type="number" id="rMax" min="0" value="${rule.max_mb || 0}" style="width:100px"></div>
        <label>Origen</label><select id="rSrc">${meta.sources.map((x) => `<option ${rule.source === x ? "selected" : ""}>${x}</option>`).join("")}</select>
        <label>Episodio de serie</label><select id="rEp">${[["any", "Da igual"], ["yes", "Sí"], ["no", "No"]].map(([k, t]) => `<option value="${k}" ${rule.episode === k ? "selected" : ""}>${t}</option>`).join("")}</select>
        <label>Regex sobre el nombre</label><input type="text" id="rRe" value="${escapeHtml(rule.regex)}">
        <label>IDs de usuario de Telegram</label><input type="text" id="rUsers" value="${csv(rule.users)}">
        <label>Carpeta destino</label><select id="rFolder">${meta.folders.map((f) => `<option ${rule.folder === f ? "selected" : ""}>${escapeHtml(f)}</option>`).join("")}</select>
        <label>Subcarpeta (plantillas {year} {month} {day} {ext} {user} {name} {first})</label><input type="text" id="rSub" value="${escapeHtml(rule.subpath)}">
        <label>Archivos comprimidos</label><select id="rExtract">${[["ask", "Preguntar"], ["yes", "Descomprimir"], ["no", "Dejar tal cual"]].map(([k, t]) => `<option value="${k}" ${rule.extract === k ? "selected" : ""}>${t}</option>`).join("")}</select>
        ${switchRow("rStop", "Parar al coincidir", rule.stop)}
        ${switchRow("rEnabled", "Regla activa", rule.enabled)}
        <div class="modal-actions"><button class="btn btn-secondary" id="modalCancel">Cancelar</button><button class="btn btn-primary" id="modalOk">Guardar</button></div>
      </div></div>`;
    const list = (id) => root.querySelector(id).value.split(",").map((x) => x.trim()).filter(Boolean);
    root.querySelector("#modalCancel").onclick = () => { root.innerHTML = ""; resolve(null); };
    root.querySelector("#modalOk").onclick = () => {
      const out = {
        ...rule, name: root.querySelector("#rName").value.trim() || "Regla", keywords: list("#rKw"), exclude: list("#rEx"),
        exts: list("#rExt"), types: [...root.querySelectorAll(".rType:checked")].map((x) => x.value),
        min_mb: Number(root.querySelector("#rMin").value || 0), max_mb: Number(root.querySelector("#rMax").value || 0),
        source: root.querySelector("#rSrc").value, episode: root.querySelector("#rEp").value, regex: root.querySelector("#rRe").value,
        users: list("#rUsers").filter((x) => /^-?\d+$/.test(x)).map(Number), folder: root.querySelector("#rFolder").value,
        subpath: root.querySelector("#rSub").value.trim(), extract: root.querySelector("#rExtract").value,
        stop: root.querySelector("#rStop").checked, enabled: root.querySelector("#rEnabled").checked,
      };
      root.innerHTML = "";
      resolve(out);
    };
  });
}

async function loadRules() {
  const root = document.getElementById("rulesCard");
  const d = await api("/api/rules");
  const modes = { off: "Desactivadas", suggest: "Sugerir (botón ⭐)", auto: "Automático" };
  const saveRules = async (rules) => { await post("/api/rules", { rules }); loadRules(); };
  root.innerHTML = `
    <p class="hint-small">Las reglas eligen la carpeta destino según el nombre, tipo, tamaño u origen. Se evalúan en orden.</p>
    <div class="card quick-rule">
      <div class="card-title">✨ Regla rápida</div>
      <div class="card-sub">Si el nombre del archivo contiene…</div>
      <input type="text" id="qrWords" placeholder="Palabra o frase (varias separadas por comas)">
      <div class="card-sub">…descárgalo en</div>
      <select id="qrFolder">${d.folders.map((f) => `<option>${escapeHtml(f)}</option>`).join("")}</select>
      <div class="card-actions"><button class="btn btn-primary" id="qrMake">${icon("plus", 14)} Crear regla</button></div>
      ${d.mode !== "auto" ? `<div class="notice-soft">Ahora mismo las reglas ${d.mode === "off" ? "están desactivadas" : "solo <b>sugieren</b> la carpeta"}. <button class="btn btn-secondary" id="qrAuto">⚡ Aplicar automáticamente</button></div>` : ""}
    </div>
    <div class="card">
      <div class="card-sub">Modo <select id="ruMode">${Object.entries(modes).map(([k, t]) => `<option value="${k}" ${d.mode === k ? "selected" : ""}>${t}</option>`).join("")}</select></div>
      <div class="card-sub">Si coinciden varias <select id="ruConf"><option value="first" ${d.options.conflict === "first" ? "selected" : ""}>Usar la primera</option><option value="ask" ${d.options.conflict === "ask" ? "selected" : ""}>Preguntarme</option></select></div>
      <div class="card-sub">Carpeta si ninguna coincide <select id="ruFb"><option value="">Preguntarme</option>${d.folders.map((f) => `<option ${d.options.fallback === f ? "selected" : ""}>${escapeHtml(f)}</option>`).join("")}</select></div>
    </div>
    ${d.rules.map((r, i) => `
      <div class="card">
        <div class="card-title">${r.enabled ? "🟢" : "⚪"} ${i + 1}. ${escapeHtml(r.name)}</div>
        <div class="card-sub">→ <code>${escapeHtml(r.folder + (r.subpath ? "/" + r.subpath : ""))}</code></div>
        <div class="card-actions" style="flex-wrap:wrap;">
          <button class="btn btn-secondary" data-a="edit" data-i="${i}">Editar</button>
          <button class="btn btn-secondary" data-a="up" data-i="${i}">⬆️</button>
          <button class="btn btn-secondary" data-a="down" data-i="${i}">⬇️</button>
          <button class="btn btn-danger" data-a="del" data-i="${i}">${icon("trash", 14)}</button>
        </div>
      </div>`).join("") || `<p class="hint-small">Aún no hay reglas.</p>`}
    <div class="card-actions" style="flex-wrap:wrap;">
      <button class="btn btn-primary" data-a="new">${icon("plus", 14)} Nueva regla</button>
      <button class="btn btn-secondary" data-a="test">🧪 Probar un nombre</button>
    </div>
    <div id="ruTest" class="card-sub"></div>`;
  const opt = async () => {
    try { await post("/api/rules", { mode: root.querySelector("#ruMode").value, conflict: root.querySelector("#ruConf").value, fallback: root.querySelector("#ruFb").value }); }
    catch (e) { tgAlert(e.message); }
  };
  root.querySelectorAll("select:not(#qrFolder)").forEach((el) => el.addEventListener("change", opt));
  root.querySelector("#qrMake").addEventListener("click", async () => {
    const words = root.querySelector("#qrWords").value.split(/[,\n]/).map((x) => x.trim().toLowerCase()).filter(Boolean);
    if (!words.length) { tgAlert("Escribe al menos una palabra o frase"); return; }
    const folder = root.querySelector("#qrFolder").value;
    const rule = { id: "", name: ("Contiene " + words[0]).slice(0, 40), enabled: true, keywords: words, exclude: [], regex: "", exts: [], types: [],
      min_mb: 0, max_mb: 0, source: "any", episode: "any", users: [], folder, subpath: "", extract: "ask", stop: true };
    try { await saveRules([...d.rules, rule]); } catch (e) { tgAlert(e.message); }
  });
  const qa = root.querySelector("#qrAuto");
  if (qa) qa.addEventListener("click", async () => {
    try { await post("/api/rules", { mode: "auto", conflict: d.options.conflict, fallback: d.options.fallback }); loadRules(); } catch (e) { tgAlert(e.message); }
  });
  root.querySelectorAll("button[data-a]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const a = btn.dataset.a, i = Number(btn.dataset.i);
      const rules = d.rules;
      try {
        if (a === "new") {
          const blank = { id: "", name: "Nueva regla", enabled: true, keywords: [], exclude: [], regex: "", exts: [], types: [], min_mb: 0, max_mb: 0,
            source: "any", episode: "any", users: [], folder: d.folders[0] || "", subpath: "", extract: "ask", stop: true };
          const r = await openRuleModal(blank, d);
          if (r) await saveRules([...rules, r]);
        } else if (a === "edit") {
          const r = await openRuleModal(rules[i], d);
          if (r) { rules[i] = r; await saveRules(rules); }
        } else if (a === "up" && i > 0) {
          [rules[i - 1], rules[i]] = [rules[i], rules[i - 1]]; await saveRules(rules);
        } else if (a === "down" && i < rules.length - 1) {
          [rules[i + 1], rules[i]] = [rules[i], rules[i + 1]]; await saveRules(rules);
        } else if (a === "del") {
          if (!(await confirmModal(`¿Eliminar la regla ${rules[i].name}?`))) return;
          rules.splice(i, 1); await saveRules(rules);
        } else if (a === "test") {
          const name = await promptModal("Probar reglas", "Nombre de archivo", "Serie.S01E02.1080p.mkv");
          if (!name) return;
          const r = await post("/api/rules/test", { name });
          root.querySelector("#ruTest").innerHTML = r.matches.length
            ? r.matches.map((m) => `✅ ${escapeHtml(m.name)} → <code>${escapeHtml(m.destination)}</code>`).join("<br>")
            : "⚪ Ninguna regla coincide";
        }
      } catch (e) { tgAlert(e.message); }
    });
  });
}

function bytesToB64(buf) {
  let s = "";
  const a = new Uint8Array(buf);
  for (let i = 0; i < a.length; i += 0x8000) s += String.fromCharCode.apply(null, a.subarray(i, i + 0x8000));
  return btoa(s);
}

async function loadBackup() {
  const root = document.getElementById("backupCard");
  const d = await api("/api/backup/groups");
  const sel = new Set(d.presets.standard);
  const SENSITIVE = ["tokens", "userbot"];
  const presetOf = () => ["light", "standard", "full"].find((k) => d.presets[k].length === sel.size && d.presets[k].every((g) => sel.has(g)));
  const paint = () => {
    const pr = presetOf();
    const hot = SENSITIVE.some((g) => sel.has(g));
    root.innerHTML = `
      <div class="bk-hero">
        <div class="bk-hero-icon">🛡️</div>
        <div>
          <div class="bk-hero-title">Copia de seguridad cifrada</div>
          <div class="bk-hero-sub">Un archivo con lo que elijas para guardarlo o llevarlo a otro bot. Siempre va cifrado.</div>
        </div>
      </div>

      <div class="bk-section">
        <div class="bk-label">Qué incluir <span class="bk-count">${sel.size}/${d.groups.length}</span></div>
        <div class="bk-presets">
          <button class="bk-chip ${pr === "light" ? "active" : ""}" data-p="light">Mínima</button>
          <button class="bk-chip ${pr === "standard" ? "active" : ""}" data-p="standard">Estándar</button>
          <button class="bk-chip ${pr === "full" ? "active" : ""}" data-p="full">Todo</button>
        </div>
        <div class="bk-grid">
          ${d.groups.map((g) => `
            <label class="bk-tile ${sel.has(g.key) ? "on" : ""} ${SENSITIVE.includes(g.key) ? "warn" : ""}">
              <input type="checkbox" class="bkg" value="${g.key}" ${sel.has(g.key) ? "checked" : ""}>
              <span class="bk-tile-icon">${g.icon}</span>
              <span class="bk-tile-text"><b>${escapeHtml(g.name)}</b><small>${escapeHtml(g.desc)}</small></span>
              <span class="bk-tick"></span>
            </label>`).join("")}
        </div>
        ${hot ? `<div class="bk-warn">⚠️ Incluye tokens o la sesión del Userbot. Guarda el archivo y su clave por separado.</div>` : ""}
      </div>

      <div class="bk-section">
        <div class="bk-label">Cifrado</div>
        <input type="password" id="bkPw" autocomplete="new-password" placeholder="Contraseña propia (opcional; si no, clave automática)">
      </div>

      <div class="bk-actions">
        <button class="btn btn-primary bk-main" id="bkMake">📤 Crear y descargar</button>
        <div class="bk-actions-row">
          <button class="btn btn-secondary" id="bkRestore">📥 Restaurar</button>
          <button class="btn btn-secondary" id="bkKey">🔑 Ver clave</button>
        </div>
      </div>

      <div class="bk-section">
        <div class="bk-label">Copia automática <small>(se envía por Telegram)</small></div>
        <select id="bkAuto">${[["off", "Desactivada"], ["daily", "Diaria"], ["weekly", "Semanal"]].map(([k, t]) => `<option value="${k}" ${d.auto === k ? "selected" : ""}>${t}</option>`).join("")}</select>
      </div>
      <input type="file" id="bkFile" class="hidden" accept=".nasbak">
      <div id="bkResult" class="bk-result"></div>`;
    root.querySelectorAll("button[data-p]").forEach((b) => b.addEventListener("click", () => { sel.clear(); d.presets[b.dataset.p].forEach((g) => sel.add(g)); paint(); }));
    root.querySelectorAll(".bkg").forEach((c) => c.addEventListener("change", () => { c.checked ? sel.add(c.value) : sel.delete(c.value); paint(); }));
    root.querySelector("#bkAuto").addEventListener("change", async (e) => {
      try { await post("/api/backup/auto", { mode: e.target.value, groups: [...sel] }); } catch (err) { tgAlert(err.message); }
    });
    root.querySelector("#bkKey").addEventListener("click", async () => {
      try { const k = await api("/api/backup/key"); tgAlert(`Clave de cifrado: ${k.key}`); } catch (e) { tgAlert(e.message); }
    });
    root.querySelector("#bkMake").addEventListener("click", async () => {
      if (!sel.size) { tgAlert("Marca al menos un grupo"); return; }
      try {
        const r = await post("/api/backup/create", { groups: [...sel], password: root.querySelector("#bkPw").value || null });
        const bin = Uint8Array.from(atob(r.data), (c) => c.charCodeAt(0));
        const a = document.createElement("a");
        a.href = URL.createObjectURL(new Blob([bin], { type: "application/octet-stream" }));
        a.download = r.name;
        a.click();
        root.querySelector("#bkResult").innerHTML = r.new_key
          ? `<div class="bk-ok">✅ Copia creada. Clave generada (guárdala): <code>${escapeHtml(r.new_key)}</code></div>`
          : `<div class="bk-ok">✅ Copia creada.</div>`;
      } catch (e) { tgAlert(e.message); }
    });
    const file = root.querySelector("#bkFile");
    root.querySelector("#bkRestore").addEventListener("click", () => file.click());
    file.addEventListener("change", async () => {
      if (!file.files[0]) return;
      try {
        const data = bytesToB64(await file.files[0].arrayBuffer());
        let info;
        try { info = await post("/api/backup/inspect", { data }); }
        catch (e) {
          const pw = await promptModal("Contraseña de la copia", "Contraseña");
          if (!pw) return;
          info = await post("/api/backup/inspect", { data, password: pw });
        }
        showRestoreChoice(root, info);
      } catch (e) { tgAlert(e.message); }
    });
  };
  paint();
}

function showRestoreChoice(root, info) {
  const result = root.querySelector("#bkResult");
  result.innerHTML = `
    <div class="bk-restore">
      <div class="bk-label">Restaurar copia <small>del ${escapeHtml(info.created || "?")} · v${escapeHtml(info.version || "?")}</small></div>
      <div class="bk-grid">
        ${info.groups.map((g) => `
          <label class="bk-tile ${["tokens", "userbot"].includes(g.key) ? "" : "on"}">
            <input type="checkbox" class="rg" value="${g.key}" ${["tokens", "userbot"].includes(g.key) ? "" : "checked"}>
            <span class="bk-tile-icon">${g.icon}</span>
            <span class="bk-tile-text"><b>${escapeHtml(g.name)}</b><small>${g.count} elementos</small></span>
            <span class="bk-tick"></span>
          </label>`).join("")}
      </div>
      <button class="btn btn-primary bk-main" id="bkGo">✅ Restaurar lo marcado</button>
      <small class="hint-small">Antes se guarda una copia de lo actual. Tras restaurar tokens, usuarios o la sesión del Userbot, reinicia el contenedor.</small>
    </div>`;
  result.querySelectorAll(".rg").forEach((c) => c.addEventListener("change", () => c.closest(".bk-tile").classList.toggle("on", c.checked)));
  result.querySelector("#bkGo").addEventListener("click", async () => {
    try {
      const groups = [...result.querySelectorAll(".rg:checked")].map((x) => x.value);
      if (!groups.length) return;
      const r = await post("/api/backup/restore", { token: info.token, groups });
      result.innerHTML = `<div class="bk-ok">✅ Restaurado: ${Object.entries(r.restored).map(([k, v]) => `${k} (${v})`).join(", ")}</div>`;
    } catch (e) { tgAlert(e.message); }
  });
}
