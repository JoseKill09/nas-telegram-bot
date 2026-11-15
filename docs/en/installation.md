# Installation from scratch

[Leer en español](../es/installation.md) · [All guides](README.md)

At the end of this guide the bot is running on your NAS and answers you in Telegram. It takes about 15 minutes.

## Contents

- [What you need](#what-you-need)
- [1. Create your bot with BotFather](#1-create-your-bot-with-botfather)
- [2. Get your Telegram user ID](#2-get-your-telegram-user-id)
- [3. Download the project to your NAS](#3-download-the-project-to-your-nas)
- [4. Create your .env file](#4-create-your-env-file)
- [5. Choose the folders the bot can use](#5-choose-the-folders-the-bot-can-use)
- [6. Start it](#6-start-it)
- [7. First steps inside Telegram](#7-first-steps-inside-telegram)
- [Updating](#updating)
- [Uninstalling](#uninstalling)

## What you need

- A NAS or any Linux machine that can run **Docker** and **Docker Compose** (Synology, QNAP, Ugreen, TrueNAS, Unraid, a Raspberry Pi 4/5, a mini PC…). `x86_64` and `arm64` both work.
- Access to a terminal on it (SSH) or a Docker GUI that accepts a `docker-compose.yml` (Portainer, Container Manager, Dockge…).
- A Telegram account.

## 1. Create your bot with BotFather

1. In Telegram open [@BotFather](https://t.me/BotFather) and send `/newbot`.
2. Choose a display name (for example *My NAS*) and a username ending in `bot` (for example `my_nas_downloads_bot`).
3. BotFather replies with a **token** like `1234567890:AA…`. That is your `BOT_TOKEN`. Treat it like a password: anyone with it controls your bot.
4. Recommended: in BotFather → your bot → **Bot Settings** → **Access** → **Restrict bot usage**, allow only yourself (and the people you trust). Strangers will not even be able to open the chat.

## 2. Get your Telegram user ID

Open [@userinfobot](https://t.me/userinfobot) and send any message. It answers with your numeric **Id** (for example `123456789`). That is your `OWNER_ID`: the only person with full control of the bot.

## 3. Download the project to your NAS

Over SSH, go to the folder where you keep your Docker projects and run:

```bash
git clone https://github.com/JoseKill09/nas-telegram-bot.git nas-telegram-bot
cd nas-telegram-bot
```

No `git`? Download the ZIP from GitHub (**Code → Download ZIP**), unzip it and upload the folder to your NAS.

## 4. Create your .env file

```bash
cp .env.example .env
nano .env        # or any editor
```

Fill in at least:

```ini
BOT_TOKEN=1234567890:AA...your-token...
OWNER_ID=123456789
TZ=Europe/Madrid
ARIA2_SECRET=a-long-random-value
```

Generate a random secret with `openssl rand -hex 24`. Every other line is optional and is explained inside the file; most of them can be set later from the bot.

> Never upload your `.env` anywhere. It is already in `.gitignore`.

## 5. Choose the folders the bot can use

The bot runs inside Docker, so it can only see the folder you give it. Set `MEDIA_ROOT` in `.env` to the NAS folder that holds (or will hold) your downloads:

```ini
MEDIA_ROOT=/volume1/media          # Synology / Ugreen style
# MEDIA_ROOT=/share/Multimedia     # QNAP style
# MEDIA_ROOT=/mnt/user/media       # Unraid style
```

Inside the containers it appears as `/media`. Later, from Telegram, you add any subfolder with the name you like (Movies, Series, Music…).

Need folders that live in different places? Add extra lines under `volumes:` of **both** the `bot` and `aria2` services in `docker-compose.yml`, for example `- /volume1/Music:/media/Music`. A cleaner way is a `docker-compose.override.yml` (ignored by git), so updates never touch your paths:

```yaml
services:
  bot:
    volumes:
      - /volume1/Music:/media/Music
  aria2:
    volumes:
      - /volume1/Music:/media/Music
```

## 6. Start it

```bash
docker compose up -d --build
docker compose logs -f bot      # Ctrl+C to leave the logs
```

The first build takes a few minutes. When the log shows the bot started without errors, go to Telegram.

Optional extra services (only if you want them):

```bash
docker compose --profile qbittorrent up -d     # or transmission, deluge
docker compose --profile warp up -d            # Cloudflare WARP proxy for blocked search sites
```

## 7. First steps inside Telegram

1. Open your bot and send `/start`. Choose English or Spanish.
2. Send `/setup` (or tap **⚙️ Settings**). Every module shows 🟢 / 🔴 and opens its own guide with buttons to paste keys. Nothing requires editing code.
3. Add your folders: Settings → Folders → ➕ Add folder.
4. Pick at least one torrent provider if you want torrents (TorBox is the recommended one right now; Real-Debrid and local clients work too).
5. Send the bot a direct link, a magnet or a file to test it.

Next steps: [Web app hosting](web-app-hosting.md) (the web app is optional and **needs your own domain name** if you publish it with Cloudflare) · [Google Drive](google-drive.md) · [Userbot](userbot.md).

## Updating

```bash
cd nas-telegram-bot
git pull
docker compose up -d --build
```

Your `.env` and `data/` (database, tokens, sessions) are never touched by updates. Read [CHANGELOG.md](../../CHANGELOG.md) to see what changed.

## Uninstalling

```bash
docker compose down
```

Then delete the folder. Your downloaded files stay in `MEDIA_ROOT`. Make a backup first (`/backup`) if you might come back.
