# Instalación desde cero

[Read in English](../en/installation.md) · [Todas las guías](README.md)

Al terminar esta guía tendrás el bot funcionando en tu NAS y respondiéndote en Telegram. Se tarda unos 15 minutos.

## Índice

- [Qué necesitas](#qué-necesitas)
- [1. Crea tu bot con BotFather](#1-crea-tu-bot-con-botfather)
- [2. Consigue tu ID de usuario de Telegram](#2-consigue-tu-id-de-usuario-de-telegram)
- [3. Descarga el proyecto en tu NAS](#3-descarga-el-proyecto-en-tu-nas)
- [4. Crea tu archivo .env](#4-crea-tu-archivo-env)
- [5. Elige las carpetas que puede usar el bot](#5-elige-las-carpetas-que-puede-usar-el-bot)
- [6. Arráncalo](#6-arráncalo)
- [7. Primeros pasos en Telegram](#7-primeros-pasos-en-telegram)
- [Actualizar](#actualizar)
- [Desinstalar](#desinstalar)

## Qué necesitas

- Un NAS o cualquier equipo Linux que pueda ejecutar **Docker** y **Docker Compose** (Synology, QNAP, Ugreen, TrueNAS, Unraid, una Raspberry Pi 4/5, un mini PC…). Funciona en `x86_64` y en `arm64`.
- Acceso a una terminal (SSH) o una interfaz de Docker que acepte un `docker-compose.yml` (Portainer, Container Manager, Dockge…).
- Una cuenta de Telegram.

## 1. Crea tu bot con BotFather

1. En Telegram abre [@BotFather](https://t.me/BotFather) y envía `/newbot`.
2. Elige un nombre visible (por ejemplo *Mi NAS*) y un nombre de usuario que termine en `bot` (por ejemplo `mi_nas_descargas_bot`).
3. BotFather te responde con un **token** del tipo `1234567890:AA…`. Ese es tu `BOT_TOKEN`. Trátalo como una contraseña: quien lo tenga controla tu bot.
4. Recomendado: en BotFather → tu bot → **Bot Settings** → **Access** → **Restrict bot usage**, permite solo tu cuenta (y la de quien quieras). Los desconocidos no podrán ni abrir el chat.

## 2. Consigue tu ID de usuario de Telegram

Abre [@userinfobot](https://t.me/userinfobot) y envíale cualquier mensaje. Te responde con tu **Id** numérico (por ejemplo `123456789`). Ese es tu `OWNER_ID`: la única persona con control total del bot.

## 3. Descarga el proyecto en tu NAS

Por SSH, ve a la carpeta donde guardas tus proyectos de Docker y ejecuta:

```bash
git clone https://github.com/JoseKill09/nas-telegram-bot.git nas-telegram-bot
cd nas-telegram-bot
```

¿No tienes `git`? Descarga el ZIP desde GitHub (**Code → Download ZIP**), descomprímelo y sube la carpeta a tu NAS.

## 4. Crea tu archivo .env

```bash
cp .env.example .env
nano .env        # o el editor que prefieras
```

Rellena como mínimo:

```ini
BOT_TOKEN=1234567890:AA...tu-token...
OWNER_ID=123456789
TZ=Europe/Madrid
ARIA2_SECRET=un-valor-largo-y-aleatorio
```

Puedes generar un secreto aleatorio con `openssl rand -hex 24`. Las demás líneas son opcionales y están explicadas dentro del archivo; casi todas se pueden configurar después desde el bot.

> No subas nunca tu `.env` a ningún sitio. Ya está incluido en `.gitignore`.

## 5. Elige las carpetas que puede usar el bot

El bot funciona dentro de Docker, así que solo ve la carpeta que le des. En el `.env`, pon en `MEDIA_ROOT` la carpeta del NAS que tiene (o tendrá) tus descargas:

```ini
MEDIA_ROOT=/volume1/media          # estilo Synology / Ugreen
# MEDIA_ROOT=/share/Multimedia     # estilo QNAP
# MEDIA_ROOT=/mnt/user/media       # estilo Unraid
```

Dentro de los contenedores aparece como `/media`. Después, desde Telegram, añades cualquier subcarpeta con el nombre que quieras (Películas, Series, Música…).

¿Tienes carpetas en sitios distintos? Añade más líneas en `volumes:` de **los dos** servicios, `bot` y `aria2`, en `docker-compose.yml`, por ejemplo `- /volume1/Musica:/media/Musica`. Es más limpio hacerlo en un `docker-compose.override.yml` (git lo ignora), así las actualizaciones nunca tocan tus rutas:

```yaml
services:
  bot:
    volumes:
      - /volume1/Musica:/media/Musica
  aria2:
    volumes:
      - /volume1/Musica:/media/Musica
```

## 6. Arráncalo

```bash
docker compose up -d --build
docker compose logs -f bot      # Ctrl+C para salir del registro
```

La primera construcción tarda unos minutos. Cuando el registro muestre que el bot ha arrancado sin errores, ve a Telegram.

Servicios extra opcionales (solo si los quieres):

```bash
docker compose --profile qbittorrent up -d     # o transmission, deluge
docker compose --profile warp up -d            # proxy Cloudflare WARP para buscadores bloqueados
```

## 7. Primeros pasos en Telegram

1. Abre tu bot y envía `/start`. Elige español o inglés.
2. Envía `/setup` (o pulsa **⚙️ Ajustes**). Cada módulo muestra 🟢 / 🔴 y abre su propia guía con botones para pegar las claves. No hace falta tocar código.
3. Añade tus carpetas: Ajustes → Carpetas → ➕ Añadir carpeta.
4. Si quieres torrents, elige al menos un proveedor (ahora mismo recomendamos TorBox; Real-Debrid y los clientes locales también funcionan).
5. Envía al bot un enlace directo, un magnet o un archivo para probarlo.

Siguientes pasos: [Publicar la web app](web-app-hosting.md) (la web app es opcional y **necesita un dominio propio** si la publicas con Cloudflare) · [Google Drive](google-drive.md) · [Userbot](userbot.md).

## Actualizar

```bash
cd nas-telegram-bot
git pull
docker compose up -d --build
```

Las actualizaciones nunca tocan tu `.env` ni `data/` (base de datos, tokens, sesiones). Mira [CHANGELOG.md](../../CHANGELOG.md) para ver qué ha cambiado.

## Desinstalar

```bash
docker compose down
```

Después borra la carpeta. Tus archivos descargados siguen en `MEDIA_ROOT`. Si crees que volverás, haz antes una copia (`/backup`).
