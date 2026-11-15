# External REST API

[Leer en español](../es/api.md) · [All guides](README.md)

The web app talks to the bot through a **REST API** (JSON over HTTP). You can use that same API to **connect the project to an external app or service**: your own mobile or desktop app, a home dashboard, Home Assistant, n8n, a script, a browser extension… or anything else you can think of to get even more out of it.

## Contents

- [Enable external access](#enable-external-access)
- [Authentication](#authentication)
- [Interactive documentation](#interactive-documentation)
- [Examples](#examples)
- [Main endpoints](#main-endpoints)
- [Security](#security)

## Enable external access

By default only the Telegram web app can call the API. To allow your own apps:

1. Generate a long random token on any computer:
   ```bash
   openssl rand -hex 32
   ```
2. Add it to your `.env`:
   ```ini
   API_TOKEN=paste-the-64-characters-here
   ```
   It must have at least 24 characters, otherwise external access stays disabled (the log shows a warning).
3. Make sure the web app server is enabled (**Settings → Web app → Enable**) and restart: `docker compose up -d`.

The API listens on port `8080` of the bot container. Reach it:

- **From another container** on the `nas_net` network: `http://nas-telegram-bot:8080`.
- **From your LAN**: the port is already published by `docker-compose.yml` (`WEBAPP_LAN_PORT`, 8080): use `http://NAS_IP:8080`.
- **From the internet**: through the same HTTPS address as the web app ([Web app hosting](web-app-hosting.md)).

## Authentication

Every `/api/...` request needs **one** of these:

| Method | Header | Who uses it |
|---|---|---|
| API token | `Authorization: Bearer <API_TOKEN>` | Your apps and services. Acts as the **owner** (full access). |
| Telegram signature | `X-Telegram-Init-Data: <initData>` | The Telegram web app (Mini App). Owner or authorised users. |

Without valid credentials the API answers `403`. `/api/health` is public and only says whether the bot is up.

## Interactive documentation

FastAPI generates the full, always up-to-date reference of every endpoint with its parameters:

- `http://<host>:8080/docs` — Swagger UI (press **Authorize** and paste your token to try requests).
- `http://<host>:8080/openapi.json` — OpenAPI schema, to generate clients in any language.

## Examples

Set two variables first:

```bash
BASE=http://NAS_IP:8080
TOKEN=your-api-token
```

**Status and active queue**

```bash
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/api/state"
```

**Download a direct link to the folder "Movies"** (3 steps: create → method → destination)

```bash
# 1) create the task(s); returns their ids
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"urls": ["https://example.com/file.iso"]}' "$BASE/api/tasks/create_links"
# → {"tasks":[{"id":42,"filename":"file.iso","size":"1.2 GB"}], ...}

# 2) choose how to download it: aria2 (direct), rd (Real-Debrid) or tb (TorBox)
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"ids": [42], "method": "aria2"}' "$BASE/api/tasks/set_method"

# 3) choose the destination folder (a name from GET /api/folders) and start
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"ids": [42], "folder": "Movies"}' "$BASE/api/tasks/set_destination"
```

**Search torrents**

```bash
curl -s -G -H "Authorization: Bearer $TOKEN" --data-urlencode "query=ubuntu 24.04" "$BASE/api/torrent/search"
```

**Cancel a task**

```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" "$BASE/api/tasks/42/cancel"
```

**Python**

```python
import requests

BASE = "http://NAS_IP:8080"
H = {"Authorization": "Bearer your-api-token"}

state = requests.get(f"{BASE}/api/state", headers=H, timeout=15).json()
for task in state.get("tasks", []):
    print(task.get("filename"), task.get("status"), task.get("progress"))
```

## Main endpoints

The exact fields of each one are in `/docs`.

| Area | Endpoints |
|---|---|
| Status | `GET /api/health`, `GET /api/state`, `GET /api/services/status`, `GET /api/disk` |
| Tasks | `POST /api/tasks/create_links`, `create_telegram`, `create_gdrive`, `set_method`, `set_destination`; `POST /api/tasks/{id}/pause`, `resume`, `start_now`, `prioritize`, `move_up`, `move_down`, `cancel`, `force_remove`; `POST /api/queue/reorder` |
| Torrents | `GET /api/torrent/search` (`provider`: `all`, `builtin`, a source key or `prowlarr:<indexer id>`), `GET /api/torrent/providers`, `POST /api/torrent/resolve_magnet`, `prepare`, `add`; `GET /api/pending`, `POST /api/pending/discard` |
| Video sites (yt-dlp) | `POST /api/ytdl/info`, `POST /api/ytdl/download`, `GET /api/ytdl/tasks`, `DELETE /api/ytdl/tasks/{id}` |
| Files | `GET /api/files`, `GET /api/files/download`, `POST /api/files/mkdir`, `rename`, `delete`, `extract`, `copy`, `upload_to_telegram` |
| Folders | `GET /api/folders`, `GET /api/folders/browse`, `POST /api/folders` … |
| History | `GET /api/history`, `POST /api/history/clear` |
| Prowlarr | `GET/POST /api/prowlarr`, `POST /api/prowlarr/test`, `POST /api/prowlarr/delete`, `POST /api/search_mode` (`builtin`, `prowlarr`, `both`) |
| Settings | providers (`/api/providers`, `/api/tb/*`, `/api/rd/*`, `/api/clients/{key}`), search sources (`/api/sources/*`), rules, notifications, disk, backups, TMDB, users, userbot, Google Drive |

## Security

- The API token has **full owner power**: it can delete files, change any setting and manage provider keys and users. Treat it like a password and never put it in public code or in a web page.
- Prefer calling it from your LAN or a private Docker network. If you expose it to the internet, always use HTTPS (a tunnel or proxy).
- To revoke it, empty `API_TOKEN` (or change it) and restart the container.
- The API does not send CORS headers, so web pages on other domains cannot call it from the browser. Call it from a backend, an app or a script.
