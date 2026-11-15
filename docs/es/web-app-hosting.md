# Publicar la web app (túnel de Cloudflare y alternativas)

[Read in English](../en/web-app-hosting.md) · [Todas las guías](README.md)

La web app es un panel visual opcional (una **Mini App** de Telegram) con la cola, el buscador, el gestor de archivos, el historial y todos los ajustes. Todo lo que hace también está en el chat, así que puedes saltarte esta guía.

## Índice

- [Cómo funciona (léelo primero)](#cómo-funciona-léelo-primero)
- [Opción A: túnel de Cloudflare integrado en el bot (recomendada)](#opción-a-túnel-de-cloudflare-integrado-en-el-bot-recomendada)
- [Opción B: tu propio contenedor cloudflared](#opción-b-tu-propio-contenedor-cloudflared)
- [Opción C: Tailscale Funnel (sin dominio)](#opción-c-tailscale-funnel-sin-dominio)
- [Opción D: proxy inverso (Caddy / Nginx Proxy Manager)](#opción-d-proxy-inverso-caddy--nginx-proxy-manager)
- [Opción E: ngrok (pruebas rápidas)](#opción-e-ngrok-pruebas-rápidas)
- [Opción F: red local o tu propia VPN (sin dominio)](#opción-f-red-local-o-tu-propia-vpn-sin-dominio)
- [Actívala en el bot](#actívala-en-el-bot)
- [Lista de seguridad](#lista-de-seguridad)
- [Problemas frecuentes](#problemas-frecuentes)

## Cómo funciona (léelo primero)

- La web app **la sirve el propio bot** (FastAPI, puerto `8080` dentro del contenedor). No es una web estática: necesita el bot funcionando en tu NAS.
- Telegram solo abre Mini Apps por **HTTPS público**. Necesitas una dirección `https://` pública que llegue al puerto `8080` del bot.
- Los alojamientos estáticos como Cloudflare Pages, Vercel, Netlify o GitHub Pages **no sirven por sí solos**, porque el panel habla con tu NAS en tiempo real. Lo que necesitas es un **túnel** o un **proxy inverso**.
- El inicio de sesión es automático: Telegram firma cada petición (`initData`) y el bot comprueba la firma con el token de tu bot. Solo el propietario y los usuarios que autorices pueden usar el panel.

| Opción | Coste | ¿Necesita dominio? | ¿Abre puertos del router? | Dificultad |
|---|---|---|---|---|
| A. Túnel de Cloudflare dentro del bot | Gratis | Sí (en Cloudflare) | No | Fácil |
| B. Contenedor cloudflared propio | Gratis | Sí (en Cloudflare) | No | Media |
| C. Tailscale Funnel | Gratis | No (`*.ts.net`) | No | Fácil |
| D. Proxy inverso + Let's Encrypt | Gratis | Sí (cualquiera) | Sí (443) | Media/alta |
| E. ngrok | Plan gratuito | No | No | Fácil (pruebas) |
| F. Red local / VPN propia | Gratis | No | No | Fácil (fuera de Telegram) |

## Opción A: túnel de Cloudflare integrado en el bot (recomendada)

La imagen del bot ya incluye `cloudflared` y puede encender y apagar el túnel por sí misma. Sin contenedores extra y sin abrir puertos.

### A.1 Pon un dominio en Cloudflare (una sola vez)

> **Necesitas un nombre de dominio propio antes de configurar la web app con Cloudflare.** Sin él no se puede publicar el panel. Si no quieres comprar uno, usa la [opción C (Tailscale Funnel)](#opción-c-tailscale-funnel-sin-dominio).

1. Crea una cuenta gratuita en [dash.cloudflare.com](https://dash.cloudflare.com).
2. **Añade un dominio** (*Add a site*). Si no tienes, cómpralo en **Domain Registration** (barato, a precio de coste) o en cualquier registrador.
3. Si el dominio es de otro registrador, Cloudflare te muestra dos **nameservers**. Cámbialos en tu registrador por esos dos y espera a que el dominio aparezca como **Active** (de minutos a unas horas).

### A.2 Crea el túnel

1. En [dash.cloudflare.com](https://dash.cloudflare.com) abre **Networking** en el menú lateral → **Tunnels** → **Create a tunnel**. *(Cloudflare cambia los menús de vez en cuando; si no lo encuentras, busca «Tunnels» en el panel.)*
2. Escribe un nombre para el túnel, por ejemplo `nas-bot`, y continúa (**Create Tunnel**).
3. Elige **Docker** como sistema operativo. En la parte de abajo verás un comando del tipo `docker run cloudflare/cloudflared ... --token eyJh...`. **Copia solo el token largo que va después de `--token`**. No ejecutes el comando.

### A.3 Dale el túnel al bot

1. En Telegram: **Ajustes → Web app → Túnel de Cloudflare → Poner token**, pégalo y pulsa **Iniciar**. El bot borra tu mensaje con el token.
2. De vuelta en Cloudflare, en unos segundos el túnel aparece como conectado. Pulsa **Continue**.

(Alternativa: ponlo en el `.env` como `CLOUDFLARE_TUNNEL_TOKEN=` antes del primer arranque. El token guardado desde el bot siempre tiene prioridad.)

### A.4 Publica el panel en tu dominio

1. En tu túnel abre la pestaña **Routes** → **Add route** → **Published application**.
2. Subdominio: por ejemplo `panel`. Dominio: el tuyo (tiene que estar en Cloudflare, mira A.1). Path: vacío.
3. **Service URL**: `http://bot:8080` (el mismo destino que muestra el bot en Ajustes → Web app → Túnel de Cloudflare).
4. Pulsa **Add route**. Tu panel será `https://panel.tu-dominio.com`.

Sigue en [Actívala en el bot](#actívala-en-el-bot).

> **No pongas Cloudflare Access (el inicio de sesión de Zero Trust) delante del panel.** La Mini App se abre dentro de Telegram y no puede mostrar esa página de acceso, así que se quedaría en blanco. El bot ya identifica cada petición a través de Telegram.

## Opción B: tu propio contenedor cloudflared

Úsala si ya tienes un contenedor `cloudflared` para otros servicios.

1. Conecta ese contenedor a la red de Docker del bot, `nas_net` (añádele `networks: [nas_net]` y declara `nas_net` como `external: true`).
2. En tu túnel: **Routes** → **Add route** → **Published application**, con **Service URL** `http://nas-telegram-bot:8080` (el nombre del contenedor).
3. Deja parado el túnel integrado en el bot.

## Opción C: Tailscale Funnel (sin dominio)

[Tailscale Funnel](https://tailscale.com/kb/1223/funnel) publica un servicio en `https://<equipo>.<tailnet>.ts.net` con un certificado válido.

1. Instala Tailscale en el NAS (muchas tiendas de apps de NAS lo tienen) e inicia sesión.
2. En la consola de administración de Tailscale activa **HTTPS certificates** y **Funnel** para ese equipo.
3. El puerto del bot ya lo publica `docker-compose.yml` (`WEBAPP_LAN_PORT`, 8080 por defecto). Ejecuta en el NAS: `tailscale funnel --bg 8080`.
   *Solo para ti, sin exponerlo a internet:* `tailscale serve --bg 8080` da una dirección HTTPS que solo pueden abrir tus dispositivos de Tailscale. Es ideal para la [opción F](#opción-f-red-local-o-tu-propia-vpn-sin-dominio) y permite instalar la web app como app.
4. Tu URL es la que muestra `tailscale funnel status`.

## Opción D: proxy inverso (Caddy / Nginx Proxy Manager)

Solo si ya tienes experiencia: expone el puerto 443 de tu router a internet.

1. Apunta un registro DNS (`panel.tu-dominio.com`) a tu IP pública (o usa DDNS).
2. Redirige el puerto **443** (y el 80 para el certificado) del router al proxy.
3. Apunta el proxy a `IP_DEL_NAS:8080` (el puerto ya está publicado) o pon el proxy en la red `nas_net` y usa `nas-telegram-bot:8080`.
4. Ejemplo con Caddy (`Caddyfile`); el certificado es automático:
   ```
   panel.tu-dominio.com {
       reverse_proxy nas-telegram-bot:8080
   }
   ```
   En Nginx Proxy Manager: nuevo Proxy Host → reenviar a `nas-telegram-bot` puerto `8080` → pestaña SSL → solicitar certificado de Let's Encrypt → activar *Websockets support*.

## Opción E: ngrok (pruebas rápidas)

1. Crea una cuenta en [ngrok.com](https://ngrok.com) y reclama tu dominio estático gratuito.
2. El puerto ya está publicado (8080). Ejecuta `ngrok http --url=<tu-dominio-estático> 8080`.
3. Sirve para probar; para el día a día es mejor la A o la C.

## Opción F: red local o tu propia VPN (sin dominio)

Usa el panel en un navegador normal de tu casa, o desde fuera a través de tu propia VPN (WireGuard, Tailscale…), sin Cloudflare y sin dominio. No es una Mini App de Telegram: entras con un enlace de un solo uso que te envía el bot.

Paso a paso: [Web app en tu red local](../../README.es.md#web-app-en-tu-red-local-sin-dominio) (también dentro del bot: 📖 Tutoriales → 🏠 Red local). En resumen: Ajustes → Web app → 🏠 Red local → pon la dirección (`http://IP_DEL_NAS:8080`) → Activar → envía `/web` y abre el enlace.

**Instalarla como app:** los navegadores solo ofrecen la opción «Instalar» de verdad por **HTTPS**. Por `http://IP_DEL_NAS:8080` tendrás un acceso directo en la pantalla de inicio (en iPhone se abre a pantalla completa). Para una app instalable del todo, abre el panel con tu dominio de Cloudflare (opción A) o con `tailscale serve` (opción C): las dos dan HTTPS.

## Actívala en el bot

1. **Ajustes → Web app → Activar** (el servidor arranca al momento, sin reiniciar).
2. **Poner URL** y envía tu dirección HTTPS, por ejemplo `https://panel.tu-dominio.com` (sin barra final).
3. Aparece un botón **🖥 Abrir panel web** en el menú principal. Ábrelo.
4. Comprueba desde un navegador que `https://panel.tu-dominio.com/api/health` responde `{"status":"ok"...}`.

Si más adelante cambias la URL, Google Drive también necesita la nueva URI de redirección ([guía de Google Drive](google-drive.md)).

## Lista de seguridad

- No publiques nunca el puerto 8080 directamente en internet sin HTTPS. Usa un túnel o un proxy.
- Restringe quién puede usar el bot en BotFather (Bot Settings → Access).
- Autoriza usuarios extra en Ajustes → Usuarios solo si confías en ellos.
- Si activas la [API externa](api.md), usa un `API_TOKEN` largo y mantenlo en secreto.

## Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| Panel en blanco o «403» | Lo abriste fuera de Telegram, o no eres el propietario ni un usuario autorizado. Ábrelo desde el botón del bot. |
| Error 1033 / 502 de Cloudflare | El túnel está parado o la URL del servicio está mal. Ajustes → Web app → Túnel de Cloudflare → Iniciar; comprueba `bot:8080`. |
| Sale una página de inicio de sesión de Cloudflare | Quita la aplicación de Cloudflare Access de ese nombre de host. |
| Se ve una versión antigua del panel | Cierra la Mini App del todo y vuelve a abrirla; Telegram la guarda en caché. |
| `/api/health` funciona pero no aparece el botón | Vuelve a poner la URL en Ajustes → Web app y envía `/start`. |
