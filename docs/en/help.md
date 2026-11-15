# Help, FAQ and troubleshooting

[Leer en español](../es/help.md) · [All guides](README.md)

## Contents

- [Ask an AI assistant](#ask-an-ai-assistant)
- [Where to look first](#where-to-look-first)
- [Frequent problems](#frequent-problems)
- [FAQ](#faq)
- [Reporting a bug](#reporting-a-bug)

## Ask an AI assistant

This whole repository (code, web app and documentation) was written with **Claude**, Anthropic's AI assistant. If you have any question or get stuck at any step, you can simply ask an AI model such as [Claude](https://claude.ai) to guide you or to do it with you:

- Paste the guide you are following and the exact error (or a screenshot) and ask: *"I'm following this guide to install NAS Telegram Bot on my Synology. Step 4 fails with this error. What should I do?"*
- With an agent such as [Claude Code](https://claude.com/claude-code) running on your NAS or computer, you can ask it to read this repository and set it up with you, step by step.
- **Never paste your real tokens, keys, `.env` or `bot.db` into any chat** (yours or an AI's). Replace them with `XXXX` before sharing logs.

## Where to look first

1. **The logs:** `docker compose logs --tail 100 bot` (and `aria2`).
2. **Settings → status:** every module shows 🟢 / 🔴 / ⚪ and its own guide.
3. **Settings → Folders:** ✅ / ❌ shows whether each folder is mounted and writable.
4. **Search sources → Test all:** which torrent sites answer from your network.

## Frequent problems

| Problem | Solution |
|---|---|
| The bot does not answer `/start` | Check `BOT_TOKEN` and `OWNER_ID` in `.env` and look at the logs. Only the owner and authorised users get answers. |
| `Conflict: terminated by other getUpdates request` | The same token is running in two places. Stop the other copy. |
| Downloads fail with "permission denied" | The folder is not writable by the container or is not mounted for both `bot` and `aria2` at the same path. |
| A download "finishes" but the file is not where expected | Destination rules may have moved it. Use Settings → Destination rules → 🧪 Test a name. |
| A search site returns nothing or TLS errors | The site changed domain or your ISP blocks it. Add a working mirror or enable the WARP proxy (`--profile warp`) in Search sources → Alternative output. |
| Telegram files over 20 MB fail | You need the [Userbot](userbot.md). |
| Google Drive errors | See the [Google Drive troubleshooting table](google-drive.md#troubleshooting). |
| The web app does not open or is blank | See the [web app troubleshooting table](web-app-hosting.md#troubleshooting). |
| Port already in use when starting | Another container uses `8081`, `9091`, `8112` or `6881`. Change the left side of the `ports:` line of that optional service. |
| `container name "/aria2" is already in use` | You already have an `aria2` container. Rename `container_name` in `docker-compose.yml` (and `ARIA2_HOST`). |

## FAQ

**Do I need the web app?** No. Everything is in the chat too.

**Which torrent provider should I use?** Whichever suits you. Given Real-Debrid's recent issues, TorBox is the one we recommend right now (cached torrents ⚡ are instant), but Real-Debrid and local clients (qBittorrent, Transmission, Deluge) are fully supported.

**Can several people use it?** Yes. The owner authorises users in Settings → Users. Each user only sees their own downloads; dangerous actions stay owner-only.

**Where are my settings stored?** In `data/bot_config/bot.db`. Back it up with `/backup` (encrypted) or by copying `data/`.

**Does it work on ARM (Raspberry Pi)?** Yes, `arm64` images are used where available.

**Is it legal?** The software is a download manager. You are responsible for what you download: respect copyright and the terms of every service you connect.

## Reporting a bug

Open an issue on GitHub with: version (first line of `CHANGELOG.md`), your NAS/OS, what you did, what you expected and the relevant log lines **with tokens removed**.
