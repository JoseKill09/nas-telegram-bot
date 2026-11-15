# Userbot from scratch

[Leer en español](../es/userbot.md) · [All guides](README.md)

## Contents

- [What it is and why you want it](#what-it-is-and-why-you-want-it)
- [Before you start (important)](#before-you-start-important)
- [1. Get your API ID and API HASH](#1-get-your-api-id-and-api-hash)
- [2. Create the private bridge channel](#2-create-the-private-bridge-channel)
- [3. Give the credentials and the channel to the bot](#3-give-the-credentials-and-the-channel-to-the-bot)
- [4. Connect the account](#4-connect-the-account)
- [5. Use it](#5-use-it)
- [Tuning parallel connections](#tuning-parallel-connections)
- [Disconnecting and security](#disconnecting-and-security)
- [Troubleshooting](#troubleshooting)

## What it is and why you want it

Telegram limits bots: they can only **download files up to 20 MB** and **upload up to 50 MB**. The **Userbot** is a normal Telegram account (yours, ideally with **Premium**) that the bot controls through Telegram's own protocol (MTProto, with the Telethon library). With it:

- Files you forward to the bot are downloaded to the NAS **up to 2 GB** (or **4 GB** with Premium).
- Downloads are much faster thanks to **parallel connections** (FastTelethon).
- You can send **message links** (`t.me/channel/123`, `t.me/c/123456/789`, topics, `tg://privatepost…`) and the bot fetches the file, also from private groups/channels and chats that do not allow forwarding, **as long as your account can see them**. Albums bring all their files.
- Big NAS files can be **sent back to Telegram** from the file manager.

Without the Userbot everything else still works; only files over 20 MB from Telegram will not.

## Before you start (important)

- Use **your own account** and only content you are allowed to access. Automating an account is allowed by Telegram's API terms, but abuse (spam, mass scraping) can get the account limited or banned.
- The bot stores the login **session** in its database (`data/bot_config/bot.db`). Whoever has that file has access to the account: never share it, and protect backups that include it with a password.
- Have the phone with Telegram at hand: you will receive a login code.

## 1. Get your API ID and API HASH

1. Open [my.telegram.org](https://my.telegram.org) in a browser and log in with the phone number of the account you will connect. The code arrives **inside the Telegram app** (not by SMS).
2. Click **API development tools**.
3. Fill in the form: *App title* `NAS Bot`, *Short name* `nasbot` (letters only, 5–32 chars), *Platform* **Desktop**, the rest empty. **Create application**.
4. Copy **App api_id** (a number) and **App api_hash** (32 characters).

> If the form shows "ERROR", try another browser/without VPN, wait a few minutes or change the short name. It is a known issue of that page.

## 2. Create the private bridge channel

The bot and the Userbot exchange big files through a private channel that only they use.

1. In Telegram: **New channel** → name `NAS bridge` → **Private** → create it (skip adding members).
2. Channel → **Administrators → Add admin** → add **your bot** (search its @username) with permission to post messages.
3. The Userbot account must also be a member (if you created the channel with that same account, it already is the owner).

## 3. Give the credentials and the channel to the bot

1. In the bot: **Settings → Userbot → 🔑 Credentials and channel**.
2. Press **🔑 API ID / HASH** and send **both values in one message, separated by a space**, for example `1234567 0123456789abcdef0123456789abcdef`. The bot deletes your message.
3. Press **📣 Channel ID** and just **forward any message from the channel** to the bot and it detects the ID by itself. (Or send it by hand: it looks like `-1001234567890`.)

(Alternative: `API_ID`, `API_HASH` and `CHANNEL_ID` in `.env`.)

## 4. Connect the account

1. **Settings → Userbot → 🔌 Connect new account**.
2. Send the phone number with country code, for example `+441234567890`.
3. Telegram sends a login code to your Telegram app. Send it to the bot. *Tip:* if Telegram rejects a code typed as is, write it with spaces (`1 2 3 4 5`); the bot removes them.
4. If you have two-step verification, send your **2FA password**.
5. The status changes to 🟢 with the account name. You can also connect it from the web app (**Settings → Userbot**).

Telegram will show a "new login" notice on your other devices: that is the bot.

## 5. Use it

- **Forward** any file (video, document, archive…) to the bot → choose the folder → it downloads.
- **Paste a message link** (`https://t.me/…`) → same flow.
- **Send a NAS file to Telegram**: file manager → file → *Send to Telegram*.
- Everything also works from the web app.

## Tuning parallel connections

**Settings → Userbot → 🔧 Parallel connections** (default 20). More connections = faster on a good line, but very high values can trigger Telegram flood limits. 8–20 is a good range. You can also set `USERBOT_MAX_CONNECTIONS` in `.env`.

## Disconnecting and security

- **Settings → Userbot → 🚫 Disconnect** closes the session and deletes it from the database.
- You can also close it from your phone: Telegram → Settings → Devices → end the bot's session.
- If you suspect the database leaked, end the session from Devices immediately.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| "API ID / HASH not configured" | Step 3 is missing, or the values have spaces. Send them again. |
| `PHONE_NUMBER_INVALID` | Use the international format with `+` and no spaces. |
| `PHONE_CODE_INVALID` / expired | Request a new one with Connect; send it with spaces between digits. |
| "Check that CHANNEL_ID is correct and that the bot is admin" | The bot is not an admin of the bridge channel, or the ID is wrong. Forward a channel message again. |
| A message link says it cannot find the chat | Your connected account must be a member of that chat and able to see the message. |
| `FloodWait` in the logs | Telegram is throttling. Lower the parallel connections and wait the indicated seconds. |
| Files over 2 GB fail | Only Premium accounts can transfer up to 4 GB. |
