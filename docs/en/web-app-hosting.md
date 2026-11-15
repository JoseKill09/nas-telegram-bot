# Web app hosting (Cloudflare Tunnel and alternatives)

[Leer en español](../es/web-app-hosting.md) · [All guides](README.md)

The web app is an optional visual panel (a Telegram **Mini App**) with the queue, search, file manager, history and every setting. Everything it does is also available in the chat, so you can skip this guide.

## Contents

- [How it works (read this first)](#how-it-works-read-this-first)
- [Option A — Cloudflare Tunnel built into the bot (recommended)](#option-a--cloudflare-tunnel-built-into-the-bot-recommended)
- [Option B — Your own cloudflared container](#option-b--your-own-cloudflared-container)
- [Option C — Tailscale Funnel (no domain needed)](#option-c--tailscale-funnel-no-domain-needed)
- [Option D — Reverse proxy (Caddy / Nginx Proxy Manager)](#option-d--reverse-proxy-caddy--nginx-proxy-manager)
- [Option E — ngrok (quick tests)](#option-e--ngrok-quick-tests)
- [Option F — Local network or your own VPN (no domain)](#option-f--local-network-or-your-own-vpn-no-domain)
- [Turn it on in the bot](#turn-it-on-in-the-bot)
- [Security checklist](#security-checklist)
- [Troubleshooting](#troubleshooting)

## How it works (read this first)

- The web app is **served by the bot itself** (FastAPI, port `8080` inside the container). It is not a static site: it needs the bot running on your NAS.
- Telegram only opens Mini Apps over **public HTTPS**. So you need a public `https://` address that reaches port `8080` of the bot.
- Static hosts such as Cloudflare Pages, Vercel, Netlify or GitHub Pages **cannot host it alone**, because the panel talks to your NAS in real time. What you need is a **tunnel** or a **reverse proxy**.
- Login is automatic: Telegram signs every request (`initData`) and the bot checks the signature with your bot token. Only the owner and the users you authorise can use the panel.

| Option | Cost | Needs a domain | Opens router ports | Difficulty |
|---|---|---|---|---|
| A. Cloudflare Tunnel inside the bot | Free | Yes (on Cloudflare) | No | Easy |
| B. Own cloudflared container | Free | Yes (on Cloudflare) | No | Medium |
| C. Tailscale Funnel | Free | No (`*.ts.net`) | No | Easy |
| D. Reverse proxy + Let's Encrypt | Free | Yes (any) | Yes (443) | Medium/hard |
| E. ngrok | Free tier | No | No | Easy (tests) |
| F. Local network / own VPN | Free | No | No | Easy (not inside Telegram) |

## Option A — Cloudflare Tunnel built into the bot (recommended)

The bot image already contains `cloudflared` and can start/stop the tunnel by itself. No extra container, no open ports.

### A.1 Put a domain on Cloudflare (once)

> **You need your own domain name before you can set up the web app with Cloudflare.** Without it you cannot publish the panel. If you do not want to buy one, use [Option C (Tailscale Funnel)](#option-c--tailscale-funnel-no-domain-needed).

1. Create a free account at [dash.cloudflare.com](https://dash.cloudflare.com).
2. **Add a domain** (*Add a site*). If you do not have one, buy it in **Domain Registration** (cheap, at cost) or with any registrar.
3. If the domain was bought elsewhere, Cloudflare shows two **nameservers**. Change the nameservers at your registrar to those two and wait until the domain shows **Active** (minutes to a few hours).

### A.2 Create the tunnel

1. In [dash.cloudflare.com](https://dash.cloudflare.com) open **Networking** in the side menu → **Tunnels** → **Create a tunnel**. *(Cloudflare renames menus from time to time; if you do not find it, search "Tunnels" in the dashboard.)*
2. Type a name for the tunnel, for example `nas-bot`, and continue (**Create Tunnel**).
3. Choose **Docker** as the operating system. At the bottom you will see a command like `docker run cloudflare/cloudflared ... --token eyJh...`. **Copy only the long token after `--token`**. Do not run the command.

### A.3 Give the tunnel to the bot

1. In Telegram: **Settings → Web app → Cloudflare Tunnel → Set token**, paste the token and tap **Start**. The bot deletes your message with the token.
2. Back in Cloudflare, after a few seconds the tunnel shows as connected. Press **Continue**.

(Alternative: put it in `.env` as `CLOUDFLARE_TUNNEL_TOKEN=` before the first start. The token saved from the bot always wins.)

### A.4 Publish the panel on your domain

1. In your tunnel open the **Routes** tab → **Add route** → **Published application**.
2. Subdomain: for example `panel`. Domain: yours (it must be on Cloudflare, see A.1). Path: empty.
3. **Service URL**: `http://bot:8080` (the same target the bot shows in Settings → Web app → Cloudflare Tunnel).
4. Press **Add route**. Your panel will be `https://panel.your-domain.com`.

Go to [Turn it on in the bot](#turn-it-on-in-the-bot).

> **Do not put Cloudflare Access (Zero Trust login) in front of the panel.** The Mini App opens inside Telegram and cannot show that login page, so it would stay blank. The bot already authenticates every request through Telegram.

## Option B — Your own cloudflared container

Use this if you already run a `cloudflared` container for other services.

1. Connect that container to the bot's Docker network `nas_net` (add `networks: [nas_net]` to it and declare `nas_net` as `external: true`).
2. In your tunnel: **Routes** → **Add route** → **Published application**, with **Service URL** `http://nas-telegram-bot:8080` (the container name).
3. Leave the tunnel inside the bot stopped.

## Option C — Tailscale Funnel (no domain needed)

[Tailscale Funnel](https://tailscale.com/kb/1223/funnel) publishes a service at `https://<machine>.<tailnet>.ts.net` with a valid certificate.

1. Install Tailscale on the NAS (many NAS app stores have it) and log in.
2. In the Tailscale admin console enable **HTTPS certificates** and **Funnel** for that machine.
3. The bot's port is already published by `docker-compose.yml` (`WEBAPP_LAN_PORT`, 8080 by default). Run on the NAS: `tailscale funnel --bg 8080`.
   *Only for yourself, without exposing it to the internet:* `tailscale serve --bg 8080` gives an HTTPS address that only your Tailscale devices can open. It is ideal for [Option F](#option-f--local-network-or-your-own-vpn-no-domain) and lets you install the web app as an app.
4. Your URL is the one `tailscale funnel status` shows.

## Option D — Reverse proxy (Caddy / Nginx Proxy Manager)

Only if you are used to it: it exposes your router's port 443 to the internet.

1. Point a DNS record (`panel.your-domain.com`) to your public IP (or use DDNS).
2. Forward port **443** (and 80 for the certificate) from your router to the proxy.
3. Point the proxy to `NAS_IP:8080` (the port is already published) or put the proxy on the `nas_net` network and use `nas-telegram-bot:8080`.
4. Caddy example (`Caddyfile`), certificate is automatic:
   ```
   panel.your-domain.com {
       reverse_proxy nas-telegram-bot:8080
   }
   ```
   In Nginx Proxy Manager: new Proxy Host → forward to `nas-telegram-bot` port `8080` → SSL tab → request a Let's Encrypt certificate → enable *Websockets support*.

## Option E — ngrok (quick tests)

1. Create an account at [ngrok.com](https://ngrok.com) and claim your free static domain.
2. The port is already published (8080). Run `ngrok http --url=<your-static-domain> 8080`.
3. Good for trying it out; for everyday use prefer A or C.

## Option F — Local network or your own VPN (no domain)

Use the panel in a normal browser at home, or from outside through your own VPN (WireGuard, Tailscale…), without Cloudflare and without a domain. It is not a Telegram Mini App: you sign in with a single-use link that the bot sends you.

Step by step: [Web app on your local network](../../README.md#web-app-on-your-local-network-no-domain) (also inside the bot: 📖 Guides → 🏠 Local network). In short: Settings → Web app → 🏠 Local network → set the address (`http://NAS_IP:8080`) → Enable → send `/web` and open the link.

**Install it as an app:** browsers only offer the real "Install" option over **HTTPS**. Over `http://NAS_IP:8080` you get a home-screen shortcut (on iPhone it opens full screen). For a fully installable app, open the panel through your Cloudflare domain (Option A) or through `tailscale serve` (Option C): both give HTTPS.

## Turn it on in the bot

1. **Settings → Web app → Enable** (the server starts at once, no restart).
2. **Set URL** and send your HTTPS address, for example `https://panel.your-domain.com` (no trailing slash).
3. A **🖥 Open web panel** button appears in the main menu. Open it.
4. Check from a browser that `https://panel.your-domain.com/api/health` answers `{"status":"ok"...}`.

If you change the URL later, Google Drive needs the new redirect URI too ([Google Drive guide](google-drive.md)).

## Security checklist

- Never publish port 8080 directly to the internet without HTTPS. Use a tunnel or a proxy.
- Restrict who can use the bot in BotFather (Bot Settings → Access).
- Authorise extra users from Settings → Users only if you trust them.
- If you enable the [external API](api.md), keep `API_TOKEN` long and secret.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Blank panel or "403" | Opened outside Telegram, or you are not the owner/an authorised user. Open it from the bot button. |
| Cloudflare error 1033 / 502 | Tunnel stopped or wrong service URL. Settings → Web app → Cloudflare Tunnel → Start; check `bot:8080`. |
| Cloudflare login page appears | Remove the Cloudflare Access application from that hostname. |
| Old version of the panel | Close the Mini App completely and reopen it; Telegram caches it. |
| `/api/health` works but the button does not appear | Set the URL again in Settings → Web app and send `/start`. |
