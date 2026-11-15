# API REST externa

[Read in English](../en/api.md) · [Todas las guías](README.md)

La web app habla con el bot a través de una **API REST** (JSON por HTTP). Puedes usar esa misma API para **conectar el proyecto con una app o un servicio externo**: tu propia app de móvil o de escritorio, un panel de casa, Home Assistant, n8n, un script, una extensión del navegador… o lo que se te ocurra para sacarle todavía más provecho.

## Índice

- [Activar el acceso externo](#activar-el-acceso-externo)
- [Autenticación](#autenticación)
- [Documentación interactiva](#documentación-interactiva)
- [Ejemplos](#ejemplos)
- [Endpoints principales](#endpoints-principales)
- [Seguridad](#seguridad)

## Activar el acceso externo

Por defecto solo la web app de Telegram puede usar la API. Para permitir tus propias apps:

1. Genera un token largo y aleatorio en cualquier ordenador:
   ```bash
   openssl rand -hex 32
   ```
2. Añádelo a tu `.env`:
   ```ini
   API_TOKEN=pega-aquí-los-64-caracteres
   ```
   Tiene que tener al menos 24 caracteres; si no, el acceso externo sigue desactivado (el registro muestra un aviso).
3. Comprueba que el servidor de la web app está activado (**Ajustes → Web app → Activar**) y reinicia: `docker compose up -d`.

La API escucha en el puerto `8080` del contenedor del bot. Para llegar a ella:

- **Desde otro contenedor** en la red `nas_net`: `http://nas-telegram-bot:8080`.
- **Desde tu red local**: el puerto ya lo publica `docker-compose.yml` (`WEBAPP_LAN_PORT`, 8080): usa `http://IP_DEL_NAS:8080`.
- **Desde internet**: con la misma dirección HTTPS de la web app ([Publicar la web app](web-app-hosting.md)).

## Autenticación

Cada petición a `/api/...` necesita **una** de estas dos cosas:

| Método | Cabecera | Quién lo usa |
|---|---|---|
| Token de la API | `Authorization: Bearer <API_TOKEN>` | Tus apps y servicios. Actúa como el **propietario** (acceso total). |
| Firma de Telegram | `X-Telegram-Init-Data: <initData>` | La web app de Telegram (Mini App). El propietario o los usuarios autorizados. |

Sin credenciales válidas la API responde `403`. `/api/health` es pública y solo dice si el bot está en marcha.

## Documentación interactiva

FastAPI genera la referencia completa, siempre al día, de cada endpoint con sus parámetros:

- `http://<host>:8080/docs`: Swagger UI (pulsa **Authorize** y pega tu token para probar peticiones).
- `http://<host>:8080/openapi.json`: esquema OpenAPI, para generar clientes en cualquier lenguaje.

## Ejemplos

Primero define dos variables:

```bash
BASE=http://IP_DEL_NAS:8080
TOKEN=tu-token-de-la-api
```

**Estado y cola activa**

```bash
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/api/state"
```

**Descargar un enlace directo a la carpeta «Movies»** (3 pasos: crear → método → destino)

```bash
# 1) crea la(s) tarea(s); devuelve sus ids
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"urls": ["https://example.com/archivo.iso"]}' "$BASE/api/tasks/create_links"
# → {"tasks":[{"id":42,"filename":"archivo.iso","size":"1.2 GB"}], ...}

# 2) elige cómo descargarla: aria2 (directa), rd (Real-Debrid) o tb (TorBox)
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"ids": [42], "method": "aria2"}' "$BASE/api/tasks/set_method"

# 3) elige la carpeta de destino (un nombre de GET /api/folders) y empieza
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"ids": [42], "folder": "Movies"}' "$BASE/api/tasks/set_destination"
```

**Buscar torrents**

```bash
curl -s -G -H "Authorization: Bearer $TOKEN" --data-urlencode "query=ubuntu 24.04" "$BASE/api/torrent/search"
```

**Cancelar una tarea**

```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" "$BASE/api/tasks/42/cancel"
```

**Python**

```python
import requests

BASE = "http://IP_DEL_NAS:8080"
H = {"Authorization": "Bearer tu-token-de-la-api"}

state = requests.get(f"{BASE}/api/state", headers=H, timeout=15).json()
for task in state.get("tasks", []):
    print(task.get("filename"), task.get("status"), task.get("progress"))
```

## Endpoints principales

Los campos exactos de cada uno están en `/docs`.

| Área | Endpoints |
|---|---|
| Estado | `GET /api/health`, `GET /api/state`, `GET /api/services/status`, `GET /api/disk` |
| Tareas | `POST /api/tasks/create_links`, `create_telegram`, `create_gdrive`, `set_method`, `set_destination`; `POST /api/tasks/{id}/pause`, `resume`, `start_now`, `prioritize`, `move_up`, `move_down`, `cancel`, `force_remove`; `POST /api/queue/reorder` |
| Torrents | `GET /api/torrent/search` (`provider`: `all`, `builtin`, la clave de un buscador o `prowlarr:<id del indexador>`), `GET /api/torrent/providers`, `POST /api/torrent/resolve_magnet`, `prepare`, `add`; `GET /api/pending`, `POST /api/pending/discard` |
| Webs de vídeo (yt-dlp) | `POST /api/ytdl/info`, `POST /api/ytdl/download`, `GET /api/ytdl/tasks`, `DELETE /api/ytdl/tasks/{id}` |
| Archivos | `GET /api/files`, `GET /api/files/download`, `POST /api/files/mkdir`, `rename`, `delete`, `extract`, `copy`, `upload_to_telegram` |
| Carpetas | `GET /api/folders`, `GET /api/folders/browse`, `POST /api/folders` … |
| Historial | `GET /api/history`, `POST /api/history/clear` |
| Prowlarr | `GET/POST /api/prowlarr`, `POST /api/prowlarr/test`, `POST /api/prowlarr/delete`, `POST /api/search_mode` (`builtin`, `prowlarr`, `both`) |
| Ajustes | proveedores (`/api/providers`, `/api/tb/*`, `/api/rd/*`, `/api/clients/{key}`), buscadores (`/api/sources/*`), reglas, notificaciones, disco, copias de seguridad, TMDB, usuarios, userbot, Google Drive |

## Seguridad

- El token de la API tiene **todo el poder del propietario**: puede borrar archivos, cambiar cualquier ajuste y gestionar las claves de los proveedores y los usuarios. Trátalo como una contraseña y no lo pongas nunca en código público ni en una página web.
- Mejor úsalo desde tu red local o una red privada de Docker. Si lo expones a internet, usa siempre HTTPS (un túnel o un proxy).
- Para revocarlo, vacía `API_TOKEN` (o cámbialo) y reinicia el contenedor.
- La API no envía cabeceras CORS, así que las páginas web de otros dominios no pueden llamarla desde el navegador. Llámala desde un backend, una app o un script.
