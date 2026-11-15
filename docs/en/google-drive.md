# Google Drive from scratch

[Leer en español](../es/google-drive.md) · [All guides](README.md)

With this module you send the bot a Google Drive link (a file or a whole folder) and it downloads it straight to your NAS through the official Google Drive API, using **your own** Google account and **your own** Google Cloud project. Nothing goes through third-party services.

It takes about 15 minutes and is free.

## Contents

- [Before you start](#before-you-start)
- [1. Create a Google Cloud project](#1-create-a-google-cloud-project)
- [2. Enable the Google Drive API](#2-enable-the-google-drive-api)
- [3. Configure the consent screen](#3-configure-the-consent-screen)
- [4. Create the OAuth client](#4-create-the-oauth-client)
- [5. Give the keys to the bot](#5-give-the-keys-to-the-bot)
- [6. Connect your account](#6-connect-your-account)
- [7. Use it](#7-use-it)
- [Avoid reconnecting every 7 days](#avoid-reconnecting-every-7-days)
- [Privacy](#privacy)
- [Troubleshooting](#troubleshooting)

## Before you start

- The **web app must be online over HTTPS** ([Web app hosting](web-app-hosting.md)), because after you approve access Google sends you back to `https://<your-panel>/oauth2/google/callback`.
- Write down your **redirect URI**: your web app URL + `/oauth2/google/callback`. Example: `https://panel.your-domain.com/oauth2/google/callback`. The bot also shows it in **Settings → Google Drive**.
- The bot only asks for **read-only** access (`drive.readonly`): it can read and download, never change or delete anything in your Drive.

## 1. Create a Google Cloud project

1. Open [console.cloud.google.com](https://console.cloud.google.com) and sign in with the Google account you want to use.
2. Accept the terms if it is your first time.
3. At the top, open the project selector → **New project**. Name: `NAS Bot` (anything). Organisation: *No organisation*. **Create**.
4. Make sure the new project is selected in the top bar.

## 2. Enable the Google Drive API

1. Menu ☰ → **APIs & Services → Library**.
2. Search **Google Drive API**, open it and press **Enable**.

## 3. Configure the consent screen

Google calls this area **Google Auth Platform** (older dashboards: *OAuth consent screen*).

1. Menu ☰ → **APIs & Services → OAuth consent screen** (or **Google Auth Platform**) → **Get started**.
2. **App information**: app name `NAS Bot`, user support email: yours. Next.
3. **Audience**: **External**. Next.
4. **Contact information**: your email. Next, accept the policy and **Create**.
5. Go to **Audience → Test users → Add users** and add **your own Google account** (the one whose Drive you will use). Save.
6. Optional but useful: **Data access → Add or remove scopes** → tick `.../auth/drive.readonly` → Update → Save.

## 4. Create the OAuth client

1. Go to **Clients** (older: **APIs & Services → Credentials → Create credentials → OAuth client ID**).
2. **Application type: Web application**. Name: `NAS Bot web`.
3. **Authorized redirect URIs → Add URI** and paste your redirect URI **exactly**, for example
   `https://panel.your-domain.com/oauth2/google/callback`
   (https, no trailing slash, same subdomain as your web app).
4. Leave *Authorized JavaScript origins* empty. **Create**.
5. A window shows the **Client ID** (ends in `.apps.googleusercontent.com`) and the **Client secret** (starts with `GOCSPX-`). Copy both. You can download the JSON as a backup; keep it private.

## 5. Give the keys to the bot

In Telegram: **Settings → Google Drive → 🔑 Google credentials → 🔑 Client ID / secret**, and send the **Client ID** and the **Client secret** in **one message, separated by a space**, for example:

```
1234-abc.apps.googleusercontent.com GOCSPX-xxxxxxxx
```

The bot deletes your message and stores the keys in its database.

(Alternative: `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env`. If your redirect URI is not the default one, also set `GOOGLE_REDIRECT_URI`.)

## 6. Connect your account

1. **Settings → Google Drive → 🔌 Connect**. The bot sends a link.
2. Open it, choose the Google account you added as a test user.
3. Google warns **"Google hasn't verified this app"**. It is your own app, so press **Continue** (sometimes under *Advanced → Go to NAS Bot*).
4. Allow access. You land on a page that says **✅ Account connected**. Go back to Telegram and reopen **Settings → Google Drive**: the status is now 🟢 with your email.

## 7. Use it

Send the bot any Drive link: `https://drive.google.com/file/d/…`, `…/open?id=…` or a folder `https://drive.google.com/drive/folders/…`. The bot lists the files (folders are read recursively, shared drives included), you choose the destination folder and it downloads. It also works from the web app.

You can download files of your own Drive, files shared with you and public "anyone with the link" files. Google Drive links are always downloaded with the Drive API, never through debrid services.

## Avoid reconnecting every 7 days

While the app is in **Testing**, Google expires the authorisation after about 7 days and you must press Connect again. To avoid it:

1. **Google Auth Platform → Audience → Publish app** → Confirm.
2. Disconnect and connect again in the bot (Settings → Google Drive).

Google may say the app needs verification because Drive is a sensitive scope. For an app that only you use, you do not need to submit it: you will keep seeing the "unverified app" warning when connecting, and the authorisation no longer expires every week.

## Privacy

- The keys and the refresh token are stored only in `data/bot_config/bot.db` on your NAS.
- Revoke access at any time at [myaccount.google.com/permissions](https://myaccount.google.com/permissions) or with **Settings → Google Drive → Disconnect**.

## Troubleshooting

| Error | Cause / fix |
|---|---|
| `redirect_uri_mismatch` | The URI in Google is not exactly the one the bot uses. Compare character by character (https, subdomain, no `/` at the end). Changes take a few minutes. |
| `access_denied` / "app is being tested" | Your account is not in **Test users**. Add it. |
| "Google did not return a refresh_token" | You had authorised before. Remove the app at [myaccount.google.com/permissions](https://myaccount.google.com/permissions) and connect again. |
| `invalid_client` | Client ID or secret copied wrong (extra space?). Send them again. |
| "Invalid request" page | The Connect link expires and works only once. Press **Connect** again. |
| The link page does not open | The web app is not online. Check `https://<your-panel>/api/health`. |
| `404 File not found` when downloading | Your account cannot open that file. Open the link in a browser with the same account to check. |
| Must reconnect every week | The app is still in Testing. See [above](#avoid-reconnecting-every-7-days). |
