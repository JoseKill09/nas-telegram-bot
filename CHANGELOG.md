# Changelog

## 21.1 — 2026-11-15

**EN**
- Internal cleanup: removed code that was no longer used.

**ES**
- Limpieza interna: eliminado código que ya no se usaba.

## 21.0 — 2026-11-15

**EN — First public release.**
- Self-hosted Telegram bot + optional web app (Telegram Mini App) to download to your NAS: direct links (aria2), torrents (TorBox, Real-Debrid, qBittorrent, Transmission, Deluge), Google Drive, yt-dlp sites and Telegram files (also big ones and message links, through the optional Userbot).
- Torrent search across several sites with mirrors, filters and TorBox instant-cache ⚡. 1337x results come from Knaben's copy when 1337x is behind Cloudflare's challenge.
- File manager, archive extraction, queue with per-engine limits, history, destination rules, notifications, disk-space control and encrypted backups.
- English and Spanish everywhere (chat, web app and documentation).
- **Prowlarr (optional)**: connect your Prowlarr from Settings → Search sources and the bot searches all its indexers with a single query. Search mode: built-in sources, Prowlarr or both (duplicates removed). Each indexer is a filter in the web app; if Prowlarr does not answer, the bot explains it and offers to search with the built-in sources. Optional Docker profiles `prowlarr` and `flaresolverr`. The Prowlarr API key never leaves the server.
- **Built-in search sources come switched off**: each user chooses which ones to enable. If none is enabled, the chat and the web app explain it with a button. Torlock removed. Source tests no longer use any title.
- **Web app on your local network (no domain)**: Settings → Web app → 🏠 Local network. Sign in in any browser with a single-use link sent by the bot (`/web`); 30-day sessions that can be closed from the bot. Works from outside through your own VPN. The port is published by default (`WEBAPP_LAN_PORT`, 8080).
- **Installable web app (PWA)**: manifest, icons and service worker; it installs as an app when opened over HTTPS (Cloudflare or Tailscale).
- **Screenshot carousel** in the web app tutorial inside the chat (Rich Messages slideshow, with album fallback).
- **Optional external REST API**: set `API_TOKEN` in `.env` to call the API with `Authorization: Bearer …` from your own apps, scripts or services. Disabled by default. See `docs/en/api.md`.
- Web app fixes for English: the «downloaded of total» size, the link field hint and 20 messages of Telegram links and 1337x that were still in Spanish. The Google Drive connection page is bilingual.
- Web app layout: the search button no longer sticks out of its card on narrow phones, and long file names end in «…» instead of overlapping the size.
- Search examples use neutral terms (Ubuntu, Debian…).
- Tutorials reviewed against the code and the current Cloudflare and Google dashboards: Cloudflare Tunnel (Networking → Tunnels, Docker token, Routes → Published application, `http://bot:8080`, own domain required), Google Drive (Google Auth Platform; Client ID and secret in one message), Userbot (API ID and HASH in one message), TMDB (short API Key v3), backups (always encrypted, automatic key), folders (they can be added from the bot), qBittorrent logs, `{day}` template and real button names. The README tutorials are now generated from the in-bot guides.
- Screenshots of the web app in `docs/screenshots/`.
- **Rich Messages: buttons no longer fall back to the old style for good.** After 3 consecutive button errors the embedded buttons now pause for 10 minutes and come back by themselves (before, they stayed off until the container was restarted). Web app, login and inline-chat buttons are embedded too instead of being silently dropped, and every rejection is logged with the screen and the block types to find its cause.
- Step-by-step guides in `docs/`: installation, web app hosting (Cloudflare Tunnel and alternatives), Google Drive, Userbot and API.

**ES — Primera versión pública.**
- Bot de Telegram autoalojado + web app opcional (Mini App de Telegram) para descargar en tu NAS: enlaces directos (aria2), torrents (TorBox, Real-Debrid, qBittorrent, Transmission, Deluge), Google Drive, webs compatibles con yt-dlp y archivos de Telegram (también grandes y enlaces de mensajes, con el Userbot opcional).
- Búsqueda de torrents en varias webs con espejos, filtros y caché instantánea ⚡ de TorBox. Los resultados de 1337x salen de la copia de Knaben cuando 1337x está detrás del desafío de Cloudflare.
- Gestor de archivos, extracción de comprimidos, cola con límites por motor, historial, reglas de destino, notificaciones, control de espacio y copias de seguridad cifradas.
- Inglés y español en todo (chat, web app y documentación).
- **Prowlarr (opcional)**: conecta tu Prowlarr desde Ajustes → Buscadores y el bot busca en todos sus indexadores con una sola consulta. Modo de búsqueda: buscadores integrados, Prowlarr o ambos (sin duplicados). Cada indexador es un filtro en la web app; si Prowlarr no responde, el bot lo explica y ofrece buscar con los integrados. Perfiles opcionales de Docker `prowlarr` y `flaresolverr`. La API key de Prowlarr nunca sale del servidor.
- **Los buscadores integrados vienen apagados**: cada usuario elige cuáles activar. Si no hay ninguno, el chat y la web app lo explican con un botón. Torlock eliminado. Las pruebas de buscadores ya no usan ningún título.
- **Web app en tu red local (sin dominio)**: Ajustes → Web app → 🏠 Red local. Se entra desde cualquier navegador con un enlace de un solo uso que envía el bot (`/web`); sesiones de 30 días que se cierran desde el bot. Funciona desde fuera con tu propia VPN. El puerto se publica por defecto (`WEBAPP_LAN_PORT`, 8080).
- **Web app instalable (PWA)**: manifiesto, iconos y service worker; se instala como app al abrirla por HTTPS (Cloudflare o Tailscale).
- **Carrusel de capturas** en el tutorial de la web app dentro del chat (carrusel de mensajes enriquecidos, con álbum de respaldo).
- **API REST externa opcional**: pon `API_TOKEN` en el `.env` para usar la API con `Authorization: Bearer …` desde tus propias apps, scripts o servicios. Desactivada por defecto. Mira `docs/es/api.md`.
- Arreglos de la web app en inglés: el tamaño «descargado de total», la ayuda del campo de enlaces y 20 mensajes de enlaces de Telegram y 1337x que seguían en español. La página de conexión de Google Drive es bilingüe.
- Diseño de la web app: el botón de buscar ya no se sale de su tarjeta en móviles estrechos, y los nombres de archivo largos terminan en «…» en vez de pisar el tamaño.
- Los ejemplos de búsqueda usan términos neutros (Ubuntu, Debian…).
- Tutoriales revisados contra el código y los paneles actuales de Cloudflare y Google: túnel de Cloudflare (Networking → Tunnels, token de Docker, Routes → Published application, `http://bot:8080`, dominio propio obligatorio), Google Drive (Google Auth Platform; Client ID y secret en un solo mensaje), Userbot (API ID y HASH en un solo mensaje), TMDB (API Key corta v3), copias (siempre cifradas, clave automática), carpetas (se pueden añadir desde el bot), registro de qBittorrent, plantilla `{day}` y nombres reales de los botones. Los tutoriales del README ahora se generan a partir de las guías del bot.
- Capturas de la web app en `docs/screenshots/`.
- **Mensajes enriquecidos: los botones ya no se quedan para siempre en el formato antiguo.** Tras 3 errores seguidos de botones, los integrados se pausan 10 minutos y vuelven solos (antes seguían apagados hasta reiniciar el contenedor). Los botones de web app, inicio de sesión y elección de chat también se integran en vez de descartarse en silencio, y cada rechazo queda en el registro con la pantalla y los tipos de bloque para encontrar su causa.
- Guías paso a paso en `docs/`: instalación, publicar la web app (túnel de Cloudflare y alternativas), Google Drive, Userbot y API.
