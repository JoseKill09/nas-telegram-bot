import i18n
from rich_ui import r_h, r_p, r_ul, r_quote, r_footer, rich

TOPICS = ["folders", "webapp", "cloudflare", "lan", "gdrive", "userbot", "qbit", "transmission", "deluge", "torbox", "realdebrid", "rules", "backup", "sources", "prowlarr", "tmdb"]

_G = {
    "folders": {
        "en": {
            "title": "Folders the bot can access",
            "intro": "The bot lives inside a Docker container, so it only sees what you share with it. You share <b>one</b> folder of your NAS (<code>MEDIA_ROOT</code>), which appears inside the containers as <code>/media</code>. Every folder inside it can then be added to the bot with any name you like (Music, Projects, Anime…), straight from Telegram.",
            "steps": [
                "In your <code>.env</code> file set <code>MEDIA_ROOT</code> to a real folder of your NAS that contains (or will contain) your files, for example <code>MEDIA_ROOT=/volume1/media</code>. Apply it with <code>docker compose up -d</code>.",
                "In the bot open Settings → Folders → ➕ Add folder. Browse the shared folder with the buttons, press <b>Use this</b> and type the name you want. You can also press <b>New</b> to create a subfolder on the spot.",
                "To change a folder later, open it in the list: ✏️ rename it, 📂 point it to another path, or change its TMDB type (Movies or Series, so TMDB creates title folders in it).",
                "Renaming a folder also updates your destination rules.",
                "Need something outside <code>MEDIA_ROOT</code>? Add one more line under <code>volumes:</code> in <code>docker-compose.yml</code> for <b>bot</b>, <b>aria2</b> (and your local torrent client), for example <code>- /volume1/Music:/media/Music</code>. It then appears inside the shared folder tree.",
            ],
            "footer": "By default the bot starts with three example folders (Downloads, Movies, Series); rename or remove them freely.",
        },
        "es": {
            "title": "Carpetas a las que accede el bot",
            "intro": "El bot vive dentro de un contenedor Docker, así que solo ve lo que compartes con él. Compartes <b>una</b> carpeta de tu NAS (<code>MEDIA_ROOT</code>), que dentro de los contenedores aparece como <code>/media</code>. Cada carpeta que haya dentro se puede añadir al bot con el nombre que quieras (Música, Proyectos, Anime…), directamente desde Telegram.",
            "steps": [
                "En tu archivo <code>.env</code> pon en <code>MEDIA_ROOT</code> una carpeta real de tu NAS que contenga (o vaya a contener) tus archivos, por ejemplo <code>MEDIA_ROOT=/volume1/media</code>. Aplícalo con <code>docker compose up -d</code>.",
                "En el bot abre Ajustes → Carpetas → ➕ Añadir carpeta. Recorre la carpeta compartida con los botones, pulsa <b>Usar esta</b> y escribe el nombre que quieras. También puedes pulsar <b>Nueva</b> para crear una subcarpeta en el momento.",
                "Para cambiar una carpeta después, ábrela en la lista: ✏️ cámbale el nombre, 📂 apúntala a otra ruta o cambia su tipo TMDB (Películas o Series, para que TMDB cree carpetas por título).",
                "Al renombrar una carpeta también se actualizan tus reglas de destino.",
                "¿Necesitas algo fuera de <code>MEDIA_ROOT</code>? Añade una línea más en <code>volumes:</code> de <code>docker-compose.yml</code> para <b>bot</b>, <b>aria2</b> (y tu cliente de torrents local), por ejemplo <code>- /volume1/Music:/media/Music</code>. Aparecerá dentro del árbol de la carpeta compartida.",
            ],
            "footer": "Por defecto el bot arranca con tres carpetas de ejemplo (Downloads, Movies, Series); renómbralas o quítalas con libertad.",
        },
    },
    "webapp": {
        "en": {
            "title": "Web app (Telegram Mini App)",
            "intro": "The web app is an optional visual panel inside Telegram: queue, file manager, torrent search and every setting. Everything it does is also available in the chat, so you can skip it.",
            "steps": [
                "<b>Before you start you need your own domain name</b> (for example <code>example.com</code>). Telegram only opens Mini Apps over a public <b>HTTPS</b> address, and the easiest free way to get one is a Cloudflare Tunnel on a subdomain of your domain. Buy one (Cloudflare sells them at cost) or use one you already have.",
                "Set up the tunnel first: Settings → Web app → 📖 Cloudflare guide.",
                "Enable the web app: Settings → Web app → Enable. The server starts immediately, no restart needed.",
                "Press <b>Set URL</b> and send your HTTPS address, for example <code>https://panel.example.com</code> (no slash at the end).",
                "A <b>🖥️ Open web panel</b> button appears in the main menu (send /start). The panel authenticates you through Telegram: only the owner and the users you authorised can use it.",
                "If you never want it, leave it disabled: port 8080 stays closed and nothing is exposed.",
            ],
            "footer": "Do not expose port 8080 directly to the internet; use the tunnel or a reverse proxy with HTTPS. Without a domain, see the alternatives (Tailscale Funnel…) in the online guide.",
        },
        "es": {
            "title": "Web app (Mini App de Telegram)",
            "intro": "La web app es un panel visual opcional dentro de Telegram: cola, gestor de archivos, buscador de torrents y todos los ajustes. Todo lo que hace también está en el chat, así que puedes prescindir de ella.",
            "steps": [
                "<b>Antes de empezar necesitas un nombre de dominio propio</b> (por ejemplo <code>ejemplo.com</code>). Telegram solo abre Mini Apps por una dirección <b>HTTPS</b> pública, y la forma gratuita más fácil de tenerla es un túnel de Cloudflare en un subdominio de tu dominio. Cómpralo (Cloudflare los vende a precio de coste) o usa uno que ya tengas.",
                "Configura antes el túnel: Ajustes → Web app → 📖 Tutorial Cloudflare.",
                "Activa la web app: Ajustes → Web app → Activar. El servidor arranca al momento, sin reiniciar.",
                "Pulsa <b>Poner URL</b> y envía tu dirección HTTPS, por ejemplo <code>https://panel.ejemplo.com</code> (sin barra al final).",
                "Aparece un botón <b>🖥️ Abrir panel web</b> en el menú principal (envía /start). El panel te identifica a través de Telegram: solo el propietario y los usuarios autorizados pueden usarlo.",
                "Si no la quieres, déjala desactivada: el puerto 8080 queda cerrado y no se expone nada.",
            ],
            "footer": "No expongas el puerto 8080 directamente a internet; usa el túnel o un proxy inverso con HTTPS. Si no tienes dominio, mira las alternativas (Tailscale Funnel…) en la guía en línea.",
        },
    },
    "cloudflare": {
        "en": {
            "title": "Cloudflare Tunnel for the web app",
            "intro": "A Cloudflare Tunnel gives your NAS a public HTTPS address without opening ports on your router. You need a free Cloudflare account and <b>your own domain already added to Cloudflare</b> (its status must be <i>Active</i>). Without a domain this guide cannot be completed.",
            "steps": [
                "Add your domain to Cloudflare if it is not there yet: <code>dash.cloudflare.com</code> → <b>Add a domain</b>. If you bought it elsewhere, change its nameservers at your registrar to the two that Cloudflare shows and wait until it says <i>Active</i>.",
                "In <code>dash.cloudflare.com</code> open <b>Networking</b> in the side menu → <b>Tunnels</b> → <b>Create a tunnel</b>.",
                "Type a name for the tunnel (for example <i>nas-bot</i>) and continue (<b>Create Tunnel</b>).",
                "Choose <b>Docker</b> as the operating system. At the bottom you will see a command like <code>docker run cloudflare/cloudflared … --token eyJh…</code>: copy <b>only the long token after</b> <code>--token</code>. Do not run the command.",
                "In the bot: Settings → Web app → Cloudflare Tunnel → <b>Set token</b>, paste it and press <b>Start</b>. The bot runs the tunnel itself (no extra container). The bot deletes your message with the token.",
                "Back in Cloudflare, wait until the tunnel shows as connected and press <b>Continue</b>.",
                "In the <b>Routes</b> tab press <b>Add route</b> → <b>Published application</b>. Subdomain: for example <code>panel</code>; Domain: yours. In <b>Service URL</b> write <code>http://bot:8080</code> and save (<b>Add route</b>).",
                "Back in the bot: Settings → Web app → <b>Enable</b> and <b>Set URL</b> to <code>https://panel.example.com</code> (your subdomain and domain).",
            ],
            "footer": "Do not put Cloudflare Access in front of the panel: Telegram cannot show its login page. The tunnel only forwards the web panel; the Telegram bot itself never needs inbound ports.",
        },
        "es": {
            "title": "Túnel de Cloudflare para la web app",
            "intro": "Un túnel de Cloudflare da a tu NAS una dirección HTTPS pública sin abrir puertos en el router. Necesitas una cuenta gratuita de Cloudflare y <b>un dominio propio ya añadido a Cloudflare</b> (con estado <i>Active</i>). Sin dominio no se puede completar esta guía.",
            "steps": [
                "Añade tu dominio a Cloudflare si aún no está: <code>dash.cloudflare.com</code> → <b>Add a domain</b>. Si lo compraste en otro sitio, cambia en tu registrador los nameservers por los dos que te indica Cloudflare y espera a que aparezca como <i>Active</i>.",
                "En <code>dash.cloudflare.com</code> abre <b>Networking</b> en el menú lateral → <b>Tunnels</b> → <b>Create a tunnel</b>.",
                "Escribe un nombre para el túnel (por ejemplo <i>nas-bot</i>) y continúa (<b>Create Tunnel</b>).",
                "Elige <b>Docker</b> como sistema operativo. En la parte de abajo verás un comando del tipo <code>docker run cloudflare/cloudflared … --token eyJh…</code>: copia <b>solo el token largo que va después de</b> <code>--token</code>. No ejecutes el comando.",
                "En el bot: Ajustes → Web app → Túnel de Cloudflare → <b>Poner token</b>, pégalo y pulsa <b>Iniciar</b>. El propio bot ejecuta el túnel (sin contenedor extra) y borra tu mensaje con el token.",
                "De vuelta en Cloudflare, espera a que el túnel aparezca como conectado y pulsa <b>Continue</b>.",
                "En la pestaña <b>Routes</b> pulsa <b>Add route</b> → <b>Published application</b>. Subdominio: por ejemplo <code>panel</code>; Dominio: el tuyo. En <b>Service URL</b> escribe <code>http://bot:8080</code> y guarda (<b>Add route</b>).",
                "De vuelta en el bot: Ajustes → Web app → <b>Activar</b> y <b>Poner URL</b> con <code>https://panel.ejemplo.com</code> (tu subdominio y dominio).",
            ],
            "footer": "No pongas Cloudflare Access delante del panel: Telegram no puede mostrar su página de acceso. El túnel solo reenvía el panel web; el bot de Telegram no necesita puertos de entrada.",
        },
    },
    "lan": {
        "en": {
            "title": "Web app on your local network (no domain)",
            "intro": "Open the web panel in any browser at home without Cloudflare or a domain. From outside home, connect to your own VPN (WireGuard, Tailscale…) and use the same address. Sign-in is a single-use link sent by the bot; no passwords.",
            "steps": [
                "The web app port is published on your network by <code>docker-compose.yml</code>: <code>8080</code> by default, change it with <code>WEBAPP_LAN_PORT</code> in <code>.env</code> if it is taken.",
                "In the bot: Settings → Web app → 🏠 Local network → ✏️ Local address, and send the address of your NAS with that port, for example <code>http://192.168.1.50:8080</code>. Give your NAS a fixed IP in your router so it does not change.",
                "Press 🟢 <b>Enable</b>. The web server starts even if the Telegram web app is disabled.",
                "Press 🔗 <b>Send me an access link</b> (or send <code>/web</code>). Open it within 5 minutes in the browser of a device on your network: you are signed in for 30 days. Every authorised user can ask for their own link with <code>/web</code>.",
                "Close sessions from Settings → Web app → 🏠 Local network → 🚪 Close every session. Disabling the access also closes them all.",
                "Install it as an app: browsers only allow it over <b>HTTPS</b>. Over <code>http://</code> on your network you get a home-screen shortcut (on iPhone it opens full screen). For a real installable app, open the panel through your Cloudflare domain or through Tailscale (<code>tailscale serve</code>), which gives HTTPS inside your own private network.",
            ],
            "footer": "Anyone on your Wi-Fi can see the sign-in page, but without a link from the bot they cannot get in. Never forward a port of your router to 8080.",
        },
        "es": {
            "title": "Web app en tu red local (sin dominio)",
            "intro": "Abre el panel web en cualquier navegador de tu casa sin Cloudflare ni dominio. Desde fuera de casa, conéctate a tu propia VPN (WireGuard, Tailscale…) y usa la misma dirección. Se entra con un enlace de un solo uso que envía el bot; sin contraseñas.",
            "steps": [
                "El puerto de la web app se publica en tu red desde <code>docker-compose.yml</code>: <code>8080</code> por defecto; cámbialo con <code>WEBAPP_LAN_PORT</code> en el <code>.env</code> si está ocupado.",
                "En el bot: Ajustes → Web app → 🏠 Red local → ✏️ Dirección local, y envía la dirección de tu NAS con ese puerto, por ejemplo <code>http://192.168.1.50:8080</code>. Dale al NAS una IP fija en tu router para que no cambie.",
                "Pulsa 🟢 <b>Activar</b>. El servidor web arranca aunque la web app de Telegram esté desactivada.",
                "Pulsa 🔗 <b>Enviarme un enlace de acceso</b> (o envía <code>/web</code>). Ábrelo antes de 5 minutos en el navegador de un dispositivo de tu red: quedas dentro durante 30 días. Cada usuario autorizado puede pedir su propio enlace con <code>/web</code>.",
                "Cierra sesiones en Ajustes → Web app → 🏠 Red local → 🚪 Cerrar todas las sesiones. Al desactivar el acceso también se cierran todas.",
                "Instalarla como app: los navegadores solo lo permiten por <b>HTTPS</b>. Por <code>http://</code> en tu red tendrás un acceso directo en la pantalla de inicio (en iPhone se abre a pantalla completa). Para una app instalable de verdad, abre el panel con tu dominio de Cloudflare o con Tailscale (<code>tailscale serve</code>), que da HTTPS dentro de tu propia red privada.",
            ],
            "footer": "Cualquiera en tu wifi puede ver la página de acceso, pero sin un enlace del bot no puede entrar. No redirijas nunca un puerto del router al 8080.",
        },
    },
    "gdrive": {
        "en": {
            "title": "Google Drive: set it up from scratch",
            "intro": "This lets the bot download Google Drive links straight to your NAS using your own Google account and your own Google Cloud project. It needs the web app online with its public HTTPS URL (and therefore a domain), because Google sends you back to it after you approve access.",
            "steps": [
                "Make sure the web app is enabled and its HTTPS URL is set (Settings → Web app). Settings → Google Drive shows your <b>redirect URI</b>: your web app URL + <code>/oauth2/google/callback</code>.",
                "Open <code>console.cloud.google.com</code>, create a new project (for example <i>NAS Bot</i>) and select it.",
                "APIs &amp; Services → Library → search <b>Google Drive API</b> → Enable.",
                "Open <b>Google Auth Platform</b> (APIs &amp; Services → OAuth consent screen) → Get started: app name and your email, Audience <b>External</b>, contact email, accept and Create.",
                "Google Auth Platform → <b>Audience</b> → Test users → Add users: add your own Google account.",
                "Google Auth Platform → <b>Clients</b> → Create client → Application type <b>Web application</b>. Under <b>Authorized redirect URIs</b> add exactly your redirect URI. Create.",
                "In the bot: Settings → Google Drive → 🔑 Google credentials → 🔑 Client ID / secret, and send the <b>Client ID</b> and the <b>Client secret</b> in <b>one message, separated by a space</b>.",
                "Press <b>🔌 Connect</b>, open the link, choose your account, accept the \"unverified app\" warning (it is your own app) and allow access.",
            ],
            "footer": "While the app is in Testing, Google asks you to reconnect about every 7 days. To avoid it: Google Auth Platform → Audience → Publish app, then disconnect and connect again.",
        },
        "es": {
            "title": "Google Drive: configurarlo desde cero",
            "intro": "Permite que el bot descargue enlaces de Google Drive directamente al NAS con tu propia cuenta de Google y tu propio proyecto de Google Cloud. Necesita la web app en línea con su URL HTTPS pública (y por tanto un dominio), porque Google te devuelve a ella cuando apruebas el acceso.",
            "steps": [
                "Comprueba que la web app está activada y tiene su URL HTTPS (Ajustes → Web app). Ajustes → Google Drive muestra tu <b>URI de redirección</b>: la URL de tu web app + <code>/oauth2/google/callback</code>.",
                "Abre <code>console.cloud.google.com</code>, crea un proyecto nuevo (por ejemplo <i>NAS Bot</i>) y selecciónalo.",
                "APIs y servicios → Biblioteca → busca <b>Google Drive API</b> → Habilitar.",
                "Abre <b>Google Auth Platform</b> (APIs y servicios → Pantalla de consentimiento de OAuth) → Comenzar: nombre de la app y tu correo, Público <b>Externo</b>, correo de contacto, acepta y Crear.",
                "Google Auth Platform → <b>Público</b> → Usuarios de prueba → Añadir usuarios: añade tu propia cuenta de Google.",
                "Google Auth Platform → <b>Clientes</b> → Crear cliente → Tipo de aplicación <b>Aplicación web</b>. En <b>URIs de redirección autorizados</b> añade exactamente tu URI de redirección. Crear.",
                "En el bot: Ajustes → Google Drive → 🔑 Credenciales de Google → 🔑 Client ID / secret, y envía el <b>ID de cliente</b> y el <b>Secreto del cliente</b> en <b>un solo mensaje, separados por un espacio</b>.",
                "Pulsa <b>🔌 Conectar</b>, abre el enlace, elige tu cuenta, acepta el aviso de «app no verificada» (es tu propia app) y permite el acceso.",
            ],
            "footer": "Mientras la app está en Prueba, Google pide reconectar cada 7 días aproximadamente. Para evitarlo: Google Auth Platform → Público → Publicar aplicación, y después desconecta y vuelve a conectar.",
        },
    },
    "userbot": {
        "en": {
            "title": "Userbot: what it is and how to set it up",
            "intro": "Bots are limited by Telegram to downloading files up to 20 MB and uploading up to 50 MB. The Userbot is a normal Telegram account (ideally Premium) controlled by the bot through MTProto, which removes those limits (up to 2 GB, or 4 GB with Premium), allows message links (t.me/…) and is much faster thanks to parallel connections (FastTelethon).",
            "steps": [
                "Get your <b>API ID</b> and <b>API HASH</b>: log in at <code>my.telegram.org</code> with the account you will connect (the code arrives in the Telegram app) → API development tools → create an application (platform Desktop).",
                "In the bot: Settings → Userbot → 🔑 Credentials and channel → 🔑 API ID / HASH, and send <b>both values in one message, separated by a space</b>.",
                "Create a <b>private channel</b>. Add your <b>bot as administrator</b> (with permission to post) and make sure your userbot account is a member. It is the bridge between them.",
                "Settings → Userbot → 🔑 Credentials and channel → 📣 Channel ID, then <b>forward any message from the channel to the bot</b>. It detects the channel by itself (you can also send the ID by hand, like <code>-1001234567890</code>).",
                "Press <b>🔌 Connect new account</b>, send the phone number with country code (for example <code>+441234567890</code>), then the login code Telegram sends you (if it is rejected, type it with spaces: <code>1 2 3 4 5</code>) and your 2FA password if you have one.",
                "How it works: when you forward a big file to the bot, the bot copies it to the private channel, the Userbot downloads it from there at full speed and saves it to the NAS. To send a NAS file to Telegram, the Userbot uploads it to the channel and the bot forwards it to you.",
            ],
            "footer": "The login session is stored only in your own database file; never share <code>/config/bot.db</code>. Use only your own account and content you are allowed to access.",
        },
        "es": {
            "title": "Userbot: qué es y cómo configurarlo",
            "intro": "Telegram limita a los bots a descargar archivos de hasta 20 MB y subir hasta 50 MB. El Userbot es una cuenta normal de Telegram (idealmente Premium) manejada por el bot mediante MTProto, lo que quita esos límites (hasta 2 GB, o 4 GB con Premium), permite enlaces de mensajes (t.me/…) y es mucho más rápido gracias a las conexiones paralelas (FastTelethon).",
            "steps": [
                "Consigue tu <b>API ID</b> y <b>API HASH</b>: entra en <code>my.telegram.org</code> con la cuenta que vas a conectar (el código llega a la app de Telegram) → API development tools → crea una aplicación (plataforma Desktop).",
                "En el bot: Ajustes → Userbot → 🔑 Credenciales y canal → 🔑 API ID / HASH, y envía <b>los dos valores en un solo mensaje, separados por un espacio</b>.",
                "Crea un <b>canal privado</b>. Añade a tu <b>bot como administrador</b> (con permiso para publicar) y comprueba que tu cuenta del userbot es miembro. Es el puente entre ambos.",
                "Ajustes → Userbot → 🔑 Credenciales y canal → 📣 ID del canal y <b>reenvía al bot cualquier mensaje del canal</b>. Lo detecta solo (también puedes enviar el ID a mano, tipo <code>-1001234567890</code>).",
                "Pulsa <b>🔌 Conectar nueva cuenta</b>, envía el teléfono con prefijo internacional (por ejemplo <code>+34600000000</code>), luego el código que te manda Telegram (si lo rechaza, escríbelo con espacios: <code>1 2 3 4 5</code>) y tu contraseña 2FA si la tienes.",
                "Cómo funciona: al reenviar un archivo grande al bot, este lo copia al canal privado, el Userbot lo descarga desde ahí a máxima velocidad y lo guarda en el NAS. Para enviarte un archivo del NAS, el Userbot lo sube al canal y el bot te lo reenvía.",
            ],
            "footer": "La sesión se guarda solo en tu propia base de datos; nunca compartas <code>/config/bot.db</code>. Usa solo tu propia cuenta y contenido al que tengas derecho a acceder.",
        },
    },
    "qbit": {
        "en": {
            "title": "qBittorrent (local BitTorrent client)",
            "intro": "With qBittorrent the torrent downloads straight to your NAS using your own connection, with no debrid service. The bot talks to qBittorrent through its Web UI API.",
            "steps": [
                "Start the bundled container: <code>docker compose --profile qbittorrent up -d</code>. It mounts the same folders as the bot, so paths match.",
                "Open <code>http://NAS_IP:8081</code>. The first login is <code>admin</code> and a temporary password printed in the container logs (<code>docker compose logs qbittorrent</code>). Change it in Tools → Options → Web UI.",
                "In the bot open Settings → Download providers → qBittorrent. Set the URL (default <code>http://qbittorrent:8081</code>), the username and the password, then press <b>Test</b>.",
                "Enable the provider. When you send a magnet you will choose it from the provider list, pick the files and the destination folder.",
                "Using an existing qBittorrent instead? Just enter its URL and credentials, and make sure it can see the same folders at the same paths (the <code>/media/...</code> paths).",
            ],
            "footer": "Option 'keep seeding' decides whether finished torrents stay in qBittorrent or are removed (files are always kept).",
        },
        "es": {
            "title": "qBittorrent (cliente BitTorrent local)",
            "intro": "Con qBittorrent el torrent se descarga directamente en tu NAS con tu propia conexión, sin servicios debrid. El bot habla con qBittorrent a través de su API Web UI.",
            "steps": [
                "Arranca el contenedor incluido: <code>docker compose --profile qbittorrent up -d</code>. Monta las mismas carpetas que el bot, así las rutas coinciden.",
                "Abre <code>http://IP_DEL_NAS:8081</code>. El primer acceso es <code>admin</code> y una contraseña temporal que sale en los logs (<code>docker compose logs qbittorrent</code>). Cámbiala en Herramientas → Opciones → Web UI.",
                "En el bot abre Ajustes → Proveedores de descarga → qBittorrent. Pon la URL (por defecto <code>http://qbittorrent:8081</code>), el usuario y la contraseña, y pulsa <b>Probar</b>.",
                "Activa el proveedor. Al enviar un magnet lo elegirás en la lista de proveedores, marcarás los archivos y la carpeta destino.",
                "¿Ya tienes un qBittorrent propio? Solo introduce su URL y credenciales, y asegúrate de que ve las mismas carpetas con las mismas rutas (las rutas <code>/media/...</code>).",
            ],
            "footer": "La opción «seguir sembrando» decide si los torrents terminados se quedan en qBittorrent o se quitan (los archivos siempre se conservan).",
        },
    },
    "transmission": {
        "en": {
            "title": "Transmission (local BitTorrent client)",
            "intro": "Transmission downloads the torrent straight to your NAS with your own connection. The bot controls it remotely, picks the files and moves them to the folder you choose.",
            "steps": [
                "Start the bundled container: <code>docker compose --profile transmission up -d</code>. It mounts the same folders as the bot, so paths match.",
                "Open <code>http://NAS_IP:9091</code>. In the bundled container the RPC has no login by default; to protect it set <code>USER</code> and <code>PASS</code> in the compose service.",
                "In the bot open Settings → Download providers → Transmission. Set the URL (default <code>http://transmission:9091</code>), the username and the password (leave them empty if there is no login) then press <b>Test</b>.",
                "Enable the provider. When you send a magnet you will choose it from the provider list, pick the files and the destination folder.",
                "Using an existing Transmission? Enter its URL and make sure it sees the same folders at the same paths (the <code>/media/...</code> paths).",
            ],
            "footer": "Option 'keep seeding' decides whether finished torrents stay in Transmission or are removed (files are always kept).",
        },
        "es": {
            "title": "Transmission (cliente BitTorrent local)",
            "intro": "Transmission descarga el torrent directamente en tu NAS con tu propia conexión. El bot lo controla en remoto, elige los archivos y los deja en la carpeta que elijas.",
            "steps": [
                "Arranca el contenedor incluido: <code>docker compose --profile transmission up -d</code>. Monta las mismas carpetas que el bot, así las rutas coinciden.",
                "Abre <code>http://IP_DEL_NAS:9091</code>. En el contenedor incluido el RPC no tiene login por defecto; para protegerlo define <code>USER</code> y <code>PASS</code> en el servicio del compose.",
                "En el bot abre Ajustes → Proveedores de descarga → Transmission. Pon la URL (por defecto <code>http://transmission:9091</code>), el usuario y la contraseña (déjalos vacíos si no hay login) y pulsa <b>Probar</b>.",
                "Activa el proveedor. Al enviar un magnet lo elegirás en la lista de proveedores, marcarás los archivos y la carpeta destino.",
                "¿Ya tienes un Transmission propio? Introduce su URL y asegúrate de que ve las mismas carpetas con las mismas rutas (las rutas <code>/media/...</code>).",
            ],
            "footer": "La opción «seguir sembrando» decide si los torrents terminados se quedan en Transmission o se quitan (los archivos siempre se conservan).",
        },
    },
    "deluge": {
        "en": {
            "title": "Deluge (local BitTorrent client)",
            "intro": "Deluge downloads the torrent straight to your NAS with your own connection. The bot controls it remotely, picks the files and moves them to the folder you choose.",
            "steps": [
                "Start the bundled container: <code>docker compose --profile deluge up -d</code>. It mounts the same folders as the bot, so paths match.",
                "Open <code>http://NAS_IP:8112</code>. The Web UI default password is <code>deluge</code>; change it in Preferences → Interface. Make sure the Web UI is connected to the daemon (Connection Manager).",
                "In the bot open Settings → Download providers → Deluge. Set the URL (default <code>http://deluge:8112</code>) and the Web UI password (Deluge has no username) then press <b>Test</b>.",
                "Enable the provider. When you send a magnet you will choose it from the provider list, pick the files and the destination folder.",
                "Using an existing Deluge? Enter its URL and make sure it sees the same folders at the same paths (the <code>/media/...</code> paths).",
            ],
            "footer": "Option 'keep seeding' decides whether finished torrents stay in Deluge or are removed (files are always kept).",
        },
        "es": {
            "title": "Deluge (cliente BitTorrent local)",
            "intro": "Deluge descarga el torrent directamente en tu NAS con tu propia conexión. El bot lo controla en remoto, elige los archivos y los deja en la carpeta que elijas.",
            "steps": [
                "Arranca el contenedor incluido: <code>docker compose --profile deluge up -d</code>. Monta las mismas carpetas que el bot, así las rutas coinciden.",
                "Abre <code>http://IP_DEL_NAS:8112</code>. La contraseña por defecto de la Web UI es <code>deluge</code>; cámbiala en Preferencias → Interfaz. Comprueba que la Web UI está conectada al daemon (Gestor de conexiones).",
                "En el bot abre Ajustes → Proveedores de descarga → Deluge. Pon la URL (por defecto <code>http://deluge:8112</code>) y la contraseña de la Web UI (Deluge no usa usuario) y pulsa <b>Probar</b>.",
                "Activa el proveedor. Al enviar un magnet lo elegirás en la lista de proveedores, marcarás los archivos y la carpeta destino.",
                "¿Ya tienes un Deluge propio? Introduce su URL y asegúrate de que ve las mismas carpetas con las mismas rutas (las rutas <code>/media/...</code>).",
            ],
            "footer": "La opción «seguir sembrando» decide si los torrents terminados se quedan en Deluge o se quitan (los archivos siempre se conservan).",
        },
    },
    "rules": {
        "en": {
            "title": "Destination rules",
            "intro": "Rules choose the destination folder of a download by its file name, type, size, origin or requester, so you do not have to pick the folder every time.",
            "steps": [
                "Fastest way: Settings → Destination rules → ✨ Quick rule. Type a word or phrase (for example <i>Ubuntu</i>) and pick a folder: from then on, any file whose name contains it goes there. Then turn on <b>Automatic</b> mode so it is applied without asking. The web app has the same Quick rule card.",
                "For finer control: ➕ New rule and give it a name.",
                "Set the conditions: words the name contains, words to exclude, extensions, file types (video, audio…), size range, origin (Telegram, link, torrent…), series episode yes/no, a regex or specific Telegram user IDs. Empty conditions are ignored; all filled ones must match.",
                "Pick the destination folder and, optionally, a subfolder with templates such as <code>{year}</code>, <code>{month}</code>, <code>{day}</code>, <code>{ext}</code>, <code>{user}</code>, <code>{name}</code> or <code>{first}</code> (for example <code>Photos/{year}/{month}</code>).",
                "Choose what happens with archives: ask, extract or leave as is.",
                "Rules are checked in order; use ⬆️ ⬇️ to reorder. 'Stop on match' decides whether later rules can also match.",
                "Mode: <b>Suggest</b> adds a ⭐ button with the folder; <b>Automatic</b> applies it without asking; <b>Off</b> ignores the rules. You can also set a default folder and what to do when several rules match.",
                "Use 🧪 Test a name to check which rule would catch a file.",
            ],
            "footer": "Rules are included in backups.",
        },
        "es": {
            "title": "Reglas de destino",
            "intro": "Las reglas eligen la carpeta destino de una descarga según el nombre, tipo, tamaño, origen o quién la pide, para no tener que elegir la carpeta cada vez.",
            "steps": [
                "Lo más rápido: Ajustes → Reglas de destino → ✨ Regla rápida. Escribe una palabra o frase (por ejemplo <i>Ubuntu</i>) y elige una carpeta: desde entonces, cualquier archivo cuyo nombre la contenga irá ahí. Luego activa el modo <b>Automático</b> para que se aplique sin preguntar. La web app tiene la misma tarjeta de Regla rápida.",
                "Para algo más fino: ➕ Nueva regla y ponle un nombre.",
                "Define las condiciones: palabras que contiene el nombre, palabras a excluir, extensiones, tipos de archivo (vídeo, audio…), rango de tamaño, origen (Telegram, enlace, torrent…), episodio de serie sí/no, una regex o IDs concretos de usuarios de Telegram. Las condiciones vacías se ignoran; todas las rellenas deben cumplirse.",
                "Elige la carpeta destino y, si quieres, una subcarpeta con plantillas como <code>{year}</code>, <code>{month}</code>, <code>{day}</code>, <code>{ext}</code>, <code>{user}</code>, <code>{name}</code> o <code>{first}</code> (por ejemplo <code>Fotos/{year}/{month}</code>).",
                "Elige qué hacer con los comprimidos: preguntar, descomprimir o dejarlos.",
                "Las reglas se revisan en orden; usa ⬆️ ⬇️ para reordenarlas. «Parar al coincidir» decide si las siguientes también pueden coincidir.",
                "Modo: <b>Sugerir</b> añade un botón ⭐ con la carpeta; <b>Automático</b> la aplica sin preguntar; <b>Desactivado</b> ignora las reglas. También puedes fijar una carpeta por defecto y qué hacer si coinciden varias.",
                "Con 🧪 Probar nombre compruebas qué regla atraparía un archivo.",
            ],
            "footer": "Las reglas se incluyen en las copias de seguridad.",
        },
    },
    "backup": {
        "en": {
            "title": "Backup and restore",
            "intro": "Save your configuration to an encrypted file and restore it on this or another installation.",
            "steps": [
                "Open Settings → Backup (or send <code>/backup</code>) and choose what to include: general settings, folders, search sources, rules, users, history, channel index, tokens and Userbot session.",
                "Presets: <b>Minimal</b>, <b>Standard</b> or <b>All</b> (includes tokens and the Userbot session, so a new installation works immediately).",
                "Every backup is <b>encrypted</b>. By default with an <b>automatic key</b>: press 🔑 Show key and keep it in a password manager, because you need it to restore on another installation. If you prefer, switch to 🔒 <b>Custom password</b>.",
                "Press 📤 Create backup now: the file arrives in the chat. With ⏰ Automatic you can also get a daily or weekly backup.",
                "To restore, press 📥 Restore, send the file (and the key or password if asked), tick the groups to restore and confirm. A safety copy of the current data is saved in <code>/config/backups</code> first.",
                "After restoring tokens, the Userbot session or users, restart the container.",
            ],
            "footer": "Files up to 20 MB can be restored from Telegram; the web app has no such limit.",
        },
        "es": {
            "title": "Copia de seguridad y restauración",
            "intro": "Guarda tu configuración en un archivo cifrado y restáurala en esta u otra instalación.",
            "steps": [
                "Abre Ajustes → Copia de seguridad (o envía <code>/backup</code>) y elige qué incluir: ajustes generales, carpetas, buscadores, reglas, usuarios, historial, índice del canal, tokens y sesión del Userbot.",
                "Preajustes: <b>Mínima</b>, <b>Estándar</b> o <b>Todo</b> (incluye tokens y la sesión del Userbot, así una instalación nueva funciona al instante).",
                "Todas las copias van <b>cifradas</b>. Por defecto con una <b>clave automática</b>: pulsa 🔑 Ver clave y guárdala en un gestor de contraseñas, porque la necesitas para restaurar en otra instalación. Si lo prefieres, cambia a 🔒 <b>Contraseña propia</b>.",
                "Pulsa 📤 Crear copia ahora: el archivo llega al chat. Con ⏰ Automática también puedes recibir una copia diaria o semanal.",
                "Para restaurar, pulsa 📥 Restaurar, envía el archivo (y la clave o contraseña si te la pide), marca los grupos y confirma. Antes se guarda una copia de seguridad de lo actual en <code>/config/backups</code>.",
                "Tras restaurar tokens, la sesión del Userbot o los usuarios, reinicia el contenedor.",
            ],
            "footer": "Desde Telegram se pueden restaurar archivos de hasta 20 MB; la web app no tiene ese límite.",
        },
    },
    "torbox": {
        "en": {
            "title": "TorBox",
            "intro": "TorBox downloads torrents in its cloud and the bot then pulls the files to your NAS. Torrents already in TorBox's cache are marked with ⚡ and are instant.",
            "steps": [
                "Create an account at <code>torbox.app</code> and subscribe to a plan.",
                "Open Settings → API in TorBox and copy your <b>API key</b>.",
                "In the bot: Settings → Download providers → TorBox → 🔑 Set token, and send the key.",
                "Enable the provider. The search results will now be checked against TorBox's cache.",
            ],
            "footer": "Your key is stored in the bot's own database and is never sent anywhere except TorBox.",
        },
        "es": {
            "title": "TorBox",
            "intro": "TorBox descarga los torrents en su nube y luego el bot trae los archivos a tu NAS. Los torrents que ya están en la caché de TorBox se marcan con ⚡ y son instantáneos.",
            "steps": [
                "Crea una cuenta en <code>torbox.app</code> y contrata un plan.",
                "Abre Settings → API en TorBox y copia tu <b>API key</b>.",
                "En el bot: Ajustes → Proveedores de descarga → TorBox → 🔑 Configurar token, y envía la clave.",
                "Activa el proveedor. Los resultados de búsqueda se comprobarán contra la caché de TorBox.",
            ],
            "footer": "Tu clave se guarda en la base de datos del bot y solo se envía a TorBox.",
        },
    },
    "realdebrid": {
        "en": {
            "title": "Real-Debrid",
            "intro": "Real-Debrid downloads torrents and hosters in its cloud; the bot then pulls the files to your NAS.",
            "steps": [
                "Create an account at <code>real-debrid.com</code> with a premium plan.",
                "Go to <code>real-debrid.com/apitoken</code> and copy your <b>API token</b>.",
                "In the bot: Settings → Download providers → Real-Debrid → 🔑 Set token, and send it.",
                "Enable the provider.",
            ],
            "footer": "Real-Debrid has no instant-cache check for arbitrary torrents, so ⚡ only appears for TorBox.",
        },
        "es": {
            "title": "Real-Debrid",
            "intro": "Real-Debrid descarga torrents y enlaces de hosters en su nube; el bot trae después los archivos a tu NAS.",
            "steps": [
                "Crea una cuenta en <code>real-debrid.com</code> con un plan premium.",
                "Entra en <code>real-debrid.com/apitoken</code> y copia tu <b>API token</b>.",
                "En el bot: Ajustes → Proveedores de descarga → Real-Debrid → 🔑 Configurar token, y envíalo.",
                "Activa el proveedor.",
            ],
            "footer": "Real-Debrid no permite comprobar la caché de torrents arbitrarios, por eso el ⚡ solo aparece con TorBox.",
        },
    },
    "sources": {
        "en": {
            "title": "Torrent search sources",
            "intro": "The bot searches several torrent sites at once. <b>All built-in sources come switched off</b>: you decide which ones to use. Each source has a main URL plus backup mirrors; if the main one fails the bot tries the mirrors and remembers the one that worked.",
            "steps": [
                "Open Settings → 🔎 Search sources and enable the ones you want. Tap a source to enable or disable it, test it, or add your own mirrors (one URL per line).",
                "Remove a default source with <b>Remove source</b>; you can bring all removed ones back with <b>Restore defaults</b>.",
                "Add a new source with <b>Add source</b>. Supported types: <b>Torznab</b> (Jackett, Prowlarr or any Torznab indexer: URL + API key) and <b>Mirror of a built-in site</b>.",
                "Press <b>Test all</b> to check which ones work from your network; turn off the failing ones.",
                "If a site is blocked by your ISP, use Settings → Search sources → Alternative output to route requests through a proxy.",
            ],
            "footer": "Built-in mirrors are written from memory and may be down or outdated: add the ones that work for you.",
        },
        "es": {
            "title": "Buscadores de torrents",
            "intro": "El bot busca en varias webs de torrents a la vez. <b>Todos los buscadores incluidos vienen apagados</b>: tú decides cuáles usar. Cada buscador tiene una URL principal y espejos de respaldo; si la principal falla, prueba los espejos y recuerda el que funcionó.",
            "steps": [
                "Abre Ajustes → 🔎 Buscadores y activa los que quieras. Toca uno para activarlo o desactivarlo, probarlo o añadir tus propios espejos (una URL por línea).",
                "Elimina un buscador de fábrica con <b>Eliminar buscador</b>; puedes recuperar los eliminados con <b>Restaurar de fábrica</b>.",
                "Añade uno nuevo con <b>Añadir buscador</b>. Tipos admitidos: <b>Torznab</b> (Jackett, Prowlarr o cualquier indexador Torznab: URL + API key) y <b>Espejo de una web incluida</b>.",
                "Pulsa <b>Probar todos</b> para ver cuáles funcionan desde tu red; desactiva los que fallen.",
                "Si tu operador bloquea una web, usa Ajustes → Buscadores → Salida alternativa para pasar las peticiones por un proxy.",
            ],
            "footer": "Los espejos de fábrica están escritos de memoria y pueden estar caídos u obsoletos: añade los que te funcionen.",
        },
    },
    "prowlarr": {
        "en": {
            "title": "Prowlarr and FlareSolverr (optional)",
            "intro": "Prowlarr manages torrent indexers in one place. Connect it and the bot searches all its indexers with a single query, alone or together with the built-in sources. FlareSolverr lets Prowlarr open indexers protected by Cloudflare.",
            "steps": [
                "Start the bundled containers: <code>docker compose --profile prowlarr --profile flaresolverr up -d</code>. Already have a Prowlarr? Skip this step and use its URL.",
                "Open <code>http://NAS_IP:9696</code>. The first time, Prowlarr asks you to create a username and password (authentication method <b>Forms</b>).",
                "Optional, for sites behind Cloudflare: Prowlarr → Settings → Indexers → <b>Indexer Proxies</b> → ➕ <b>FlareSolverr</b>. Host <code>http://flaresolverr:8191</code> and a tag such as <code>flaresolverr</code>. Then add that tag to the indexers that need it.",
                "Prowlarr → Indexers → <b>Add Indexer</b>: add the indexers you want and press Test on each one.",
                "Copy the <b>API Key</b>: Prowlarr → Settings → General → Security.",
                "In the bot: Settings → 🔎 Search sources → 🧭 Prowlarr → 🔗 URL (<code>http://prowlarr:9696</code>) and 🔑 API key. The bot tests the connection by itself and shows how many indexers it sees.",
                "Choose 🔀 <b>Search mode</b>: <b>Prowlarr</b> (only Prowlarr) or <b>Both</b> (Prowlarr + the built-in sources you enabled).",
            ],
            "footer": "In the web app each Prowlarr indexer appears as a filter chip. If Prowlarr does not answer, the bot tells you and offers to search with the built-in sources. The API key never leaves your server.",
        },
        "es": {
            "title": "Prowlarr y FlareSolverr (opcional)",
            "intro": "Prowlarr gestiona indexadores de torrents en un solo sitio. Conéctalo y el bot buscará en todos sus indexadores con una sola consulta, solo o junto con los buscadores integrados. FlareSolverr permite a Prowlarr abrir indexadores protegidos por Cloudflare.",
            "steps": [
                "Arranca los contenedores incluidos: <code>docker compose --profile prowlarr --profile flaresolverr up -d</code>. ¿Ya tienes un Prowlarr? Sáltate este paso y usa su URL.",
                "Abre <code>http://IP_DEL_NAS:9696</code>. La primera vez Prowlarr te pide crear un usuario y una contraseña (método de autenticación <b>Forms</b>).",
                "Opcional, para webs detrás de Cloudflare: Prowlarr → Settings → Indexers → <b>Indexer Proxies</b> → ➕ <b>FlareSolverr</b>. Host <code>http://flaresolverr:8191</code> y una etiqueta (tag) como <code>flaresolverr</code>. Después pon esa etiqueta a los indexadores que la necesiten.",
                "Prowlarr → Indexers → <b>Add Indexer</b>: añade los indexadores que quieras y pulsa Test en cada uno.",
                "Copia la <b>API Key</b>: Prowlarr → Settings → General → Security.",
                "En el bot: Ajustes → 🔎 Buscadores → 🧭 Prowlarr → 🔗 URL (<code>http://prowlarr:9696</code>) y 🔑 API key. El bot prueba la conexión solo y te dice cuántos indexadores ve.",
                "Elige el 🔀 <b>Modo de búsqueda</b>: <b>Prowlarr</b> (solo Prowlarr) o <b>Ambos</b> (Prowlarr + los buscadores integrados que hayas activado).",
            ],
            "footer": "En la web app cada indexador de Prowlarr aparece como un filtro. Si Prowlarr no responde, el bot te avisa y te ofrece buscar con los integrados. La API key nunca sale de tu servidor.",
        },
    },
    "tmdb": {
        "en": {
            "title": "TMDB (optional)",
            "intro": "When enabled, downloads sent to the root of a folder marked as Movies or Series are placed in a folder named after the title.",
            "steps": [
                "Create a free account at <code>themoviedb.org</code>.",
                "Go to your account Settings → <b>API</b> and request an API key (type Developer, fill in the short form).",
                "Copy the <b>API Key</b> (the short one, 32 characters). Not the long \"API Read Access Token\": the bot does not use it.",
                "In the bot: Settings → TMDB → 🔑 Set token, send the key and enable it.",
                "Mark your folders as Movies or Series in Settings → Folders.",
            ],
            "footer": "TMDB is only used to name folders; files are never renamed.",
        },
        "es": {
            "title": "TMDB (opcional)",
            "intro": "Si lo activas, las descargas enviadas a la raíz de una carpeta marcada como Películas o Series se guardan en una carpeta con el nombre del título.",
            "steps": [
                "Crea una cuenta gratuita en <code>themoviedb.org</code>.",
                "Ve a los ajustes de tu cuenta → <b>API</b> y solicita una clave de API (tipo Developer, rellena el formulario corto).",
                "Copia la <b>API Key</b> (la corta, de 32 caracteres). No el «API Read Access Token» largo: el bot no lo usa.",
                "En el bot: Ajustes → TMDB → 🔑 Configurar token, envía la clave y actívalo.",
                "Marca tus carpetas como Películas o Series en Ajustes → Carpetas.",
            ],
            "footer": "TMDB solo se usa para nombrar carpetas; los archivos nunca se renombran.",
        },
    },

}


def guide_text(topic: str) -> str:
    data = _G[topic][i18n.lang if i18n.lang in ("en", "es") else "en"]
    return rich(
        r_h(data["title"], 2, "📖"),
        r_p(data["intro"]),
        r_ul(data["steps"], ordered=True),
        r_footer(data["footer"]),
    )


def guide_title(topic: str) -> str:
    return _G[topic][i18n.lang if i18n.lang in ("en", "es") else "en"]["title"]
