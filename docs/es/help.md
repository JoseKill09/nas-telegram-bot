# Ayuda, preguntas frecuentes y problemas

[Read in English](../en/help.md) · [Todas las guías](README.md)

## Índice

- [Pregúntale a un asistente de IA](#pregúntale-a-un-asistente-de-ia)
- [Dónde mirar primero](#dónde-mirar-primero)
- [Problemas frecuentes](#problemas-frecuentes)
- [Preguntas frecuentes](#preguntas-frecuentes)
- [Informar de un fallo](#informar-de-un-fallo)

## Pregúntale a un asistente de IA

Todo este repositorio (código, web app y documentación) se escribió con **Claude**, el asistente de IA de Anthropic. Si tienes cualquier duda o te atascas en algún paso, puedes simplemente pedirle a un modelo de IA como [Claude](https://claude.ai) que te guíe o que lo haga contigo:

- Pega la guía que estás siguiendo y el error exacto (o una captura) y pregunta: *«Estoy siguiendo esta guía para instalar NAS Telegram Bot en mi Synology. El paso 4 me da este error. ¿Qué hago?»*
- Con un agente como [Claude Code](https://claude.com/claude-code) funcionando en tu NAS o tu ordenador, puedes pedirle que lea este repositorio y lo configure contigo paso a paso.
- **No pegues nunca tus tokens, claves, `.env` ni `bot.db` reales en ningún chat** (ni con personas ni con una IA). Sustitúyelos por `XXXX` antes de compartir un registro.

## Dónde mirar primero

1. **El registro:** `docker compose logs --tail 100 bot` (y `aria2`).
2. **Ajustes → estado:** cada módulo muestra 🟢 / 🔴 / ⚪ y su propia guía.
3. **Ajustes → Carpetas:** ✅ / ❌ indica si cada carpeta está montada y se puede escribir en ella.
4. **Buscadores → Probar todos:** qué webs de torrents responden desde tu red.

## Problemas frecuentes

| Problema | Solución |
|---|---|
| El bot no responde a `/start` | Revisa `BOT_TOKEN` y `OWNER_ID` en el `.env` y mira el registro. Solo responde al propietario y a los usuarios autorizados. |
| `Conflict: terminated by other getUpdates request` | El mismo token está funcionando en dos sitios. Para la otra copia. |
| Las descargas fallan con «permission denied» | El contenedor no puede escribir en la carpeta, o no está montada en `bot` y `aria2` con la misma ruta. |
| Una descarga «termina» pero el archivo no está donde esperabas | Puede que una regla de destino lo haya movido. Usa Ajustes → Reglas de destino → 🧪 Probar un nombre. |
| Un buscador no devuelve nada o da errores TLS | La web cambió de dominio o tu operador la bloquea. Añade un espejo que funcione o activa el proxy WARP (`--profile warp`) en Buscadores → Salida alternativa. |
| Fallan los archivos de Telegram de más de 20 MB | Necesitas el [Userbot](userbot.md). |
| Errores de Google Drive | Mira la [tabla de problemas de Google Drive](google-drive.md#problemas-frecuentes). |
| La web app no abre o sale en blanco | Mira la [tabla de problemas de la web app](web-app-hosting.md#problemas-frecuentes). |
| Puerto ocupado al arrancar | Otro contenedor usa `8081`, `9091`, `8112` o `6881`. Cambia la parte izquierda de la línea `ports:` de ese servicio opcional. |
| `container name "/aria2" is already in use` | Ya tienes un contenedor `aria2`. Cambia `container_name` en `docker-compose.yml` (y `ARIA2_HOST`). |

## Preguntas frecuentes

**¿Necesito la web app?** No. Todo está también en el chat.

**¿Qué proveedor de torrents uso?** El que mejor te venga. Por los problemas recientes de Real-Debrid, ahora mismo recomendamos TorBox (los torrents en caché ⚡ son instantáneos), pero Real-Debrid y los clientes locales (qBittorrent, Transmission, Deluge) funcionan igual de bien.

**¿Pueden usarlo varias personas?** Sí. El propietario autoriza usuarios en Ajustes → Usuarios. Cada usuario solo ve sus propias descargas; las acciones peligrosas son solo para el propietario.

**¿Dónde se guarda mi configuración?** En `data/bot_config/bot.db`. Haz copia con `/backup` (cifrada) o copiando `data/`.

**¿Funciona en ARM (Raspberry Pi)?** Sí, se usan imágenes `arm64` cuando existen.

**¿Es legal?** El programa es un gestor de descargas. Tú eres responsable de lo que descargas: respeta los derechos de autor y las condiciones de cada servicio que conectes.

## Informar de un fallo

Abre una *issue* en GitHub con: la versión (primera línea de `CHANGELOG.md`), tu NAS o sistema, qué hiciste, qué esperabas y las líneas del registro que importan, **sin tokens**.
