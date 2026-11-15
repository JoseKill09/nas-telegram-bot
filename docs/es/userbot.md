# Userbot desde cero

[Read in English](../en/userbot.md) · [Todas las guías](README.md)

## Índice

- [Qué es y para qué lo quieres](#qué-es-y-para-qué-lo-quieres)
- [Antes de empezar (importante)](#antes-de-empezar-importante)
- [1. Consigue tu API ID y API HASH](#1-consigue-tu-api-id-y-api-hash)
- [2. Crea el canal privado puente](#2-crea-el-canal-privado-puente)
- [3. Dale las credenciales y el canal al bot](#3-dale-las-credenciales-y-el-canal-al-bot)
- [4. Conecta la cuenta](#4-conecta-la-cuenta)
- [5. Úsalo](#5-úsalo)
- [Ajustar las conexiones paralelas](#ajustar-las-conexiones-paralelas)
- [Desconectar y seguridad](#desconectar-y-seguridad)
- [Problemas frecuentes](#problemas-frecuentes)

## Qué es y para qué lo quieres

Telegram limita a los bots: solo pueden **descargar archivos de hasta 20 MB** y **subir hasta 50 MB**. El **Userbot** es una cuenta normal de Telegram (la tuya, mejor si tiene **Premium**) que el bot controla con el protocolo propio de Telegram (MTProto, con la librería Telethon). Con él:

- Los archivos que reenvías al bot se descargan al NAS **hasta 2 GB** (o **4 GB** con Premium).
- Las descargas son mucho más rápidas gracias a las **conexiones en paralelo** (FastTelethon).
- Puedes enviar **enlaces de mensajes** (`t.me/canal/123`, `t.me/c/123456/789`, temas, `tg://privatepost…`) y el bot descarga el archivo, también de grupos y canales privados y de chats que no permiten reenviar, **siempre que tu cuenta pueda verlos**. Los álbumes traen todos sus archivos.
- Puedes **enviar a Telegram archivos grandes del NAS** desde el gestor de archivos.

Sin el Userbot todo lo demás sigue funcionando; solo fallarán los archivos de Telegram de más de 20 MB.

## Antes de empezar (importante)

- Usa **tu propia cuenta** y solo contenido al que tengas derecho a acceder. Las condiciones de la API de Telegram permiten automatizar una cuenta, pero el abuso (spam, extracción masiva) puede hacer que la limiten o la bloqueen.
- El bot guarda la **sesión** de inicio en su base de datos (`data/bot_config/bot.db`). Quien tenga ese archivo tiene acceso a la cuenta: no lo compartas nunca y protege con contraseña las copias de seguridad que la incluyan.
- Ten a mano el móvil con Telegram: recibirás un código de inicio de sesión.

## 1. Consigue tu API ID y API HASH

1. Abre [my.telegram.org](https://my.telegram.org) en un navegador e inicia sesión con el número de la cuenta que vas a conectar. El código llega **dentro de la app de Telegram** (no por SMS).
2. Pulsa **API development tools**.
3. Rellena el formulario: *App title* `NAS Bot`, *Short name* `nasbot` (solo letras, de 5 a 32 caracteres), *Platform* **Desktop**, el resto vacío. **Create application**.
4. Copia **App api_id** (un número) y **App api_hash** (32 caracteres).

> Si el formulario da «ERROR», prueba con otro navegador o sin VPN, espera unos minutos o cambia el nombre corto. Es un fallo conocido de esa página.

## 2. Crea el canal privado puente

El bot y el Userbot se pasan los archivos grandes a través de un canal privado que solo usan ellos.

1. En Telegram: **Nuevo canal** → nombre `Puente NAS` → **Privado** → créalo (sáltate lo de añadir miembros).
2. Canal → **Administradores → Añadir administrador** → añade **tu bot** (búscalo por su @usuario) con permiso para publicar mensajes.
3. La cuenta del Userbot también tiene que ser miembro (si creaste el canal con esa misma cuenta, ya es la propietaria).

## 3. Dale las credenciales y el canal al bot

1. En el bot: **Ajustes → Userbot → 🔑 Credenciales y canal**.
2. Pulsa **🔑 API ID / HASH** y envía **los dos valores en un solo mensaje, separados por un espacio**, por ejemplo `1234567 0123456789abcdef0123456789abcdef`. El bot borra tu mensaje.
3. Pulsa **📣 ID del canal** y basta con **reenviar al bot cualquier mensaje del canal** y detecta el ID por sí solo. (O envíalo a mano: tiene la forma `-1001234567890`.)

(Alternativa: `API_ID`, `API_HASH` y `CHANNEL_ID` en el `.env`.)

## 4. Conecta la cuenta

1. **Ajustes → Userbot → 🔌 Conectar nueva cuenta**.
2. Envía el número de teléfono con prefijo internacional, por ejemplo `+34600000000`.
3. Telegram envía un código a tu app de Telegram. Envíaselo al bot. *Truco:* si Telegram rechaza el código escrito tal cual, escríbelo con espacios (`1 2 3 4 5`); el bot los quita.
4. Si tienes verificación en dos pasos, envía tu **contraseña 2FA**.
5. El estado pasa a 🟢 con el nombre de la cuenta. También puedes conectarla desde la web app (**Ajustes → Userbot**).

Telegram mostrará un aviso de «nuevo inicio de sesión» en tus otros dispositivos: es el bot.

## 5. Úsalo

- **Reenvía** cualquier archivo (vídeo, documento, comprimido…) al bot → elige la carpeta → se descarga.
- **Pega un enlace de mensaje** (`https://t.me/…`) → mismo proceso.
- **Envía un archivo del NAS a Telegram**: gestor de archivos → archivo → *Enviar a Telegram*.
- Todo funciona también desde la web app.

## Ajustar las conexiones paralelas

**Ajustes → Userbot → 🔧 Conexiones paralelas** (20 por defecto). Más conexiones = más velocidad con una buena línea, pero valores muy altos pueden activar los límites anti-flood de Telegram. Entre 8 y 20 es un buen rango. También puedes poner `USERBOT_MAX_CONNECTIONS` en el `.env`.

## Desconectar y seguridad

- **Ajustes → Userbot → 🚫 Desconectar** cierra la sesión y la borra de la base de datos.
- También puedes cerrarla desde el móvil: Telegram → Ajustes → Dispositivos → terminar la sesión del bot.
- Si sospechas que se ha filtrado la base de datos, termina la sesión desde Dispositivos inmediatamente.

## Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| «API ID / HASH sin configurar» | Falta el paso 3 o los valores tienen espacios. Envíalos otra vez. |
| `PHONE_NUMBER_INVALID` | Usa el formato internacional con `+` y sin espacios. |
| `PHONE_CODE_INVALID` / caducado | Pide uno nuevo con Conectar; envíalo con espacios entre los dígitos. |
| «Comprueba que CHANNEL_ID sea correcto y que el bot sea administrador del canal» | El bot no es administrador del canal puente o el ID está mal. Vuelve a reenviar un mensaje del canal. |
| Un enlace de mensaje dice que no encuentra el chat | Tu cuenta conectada tiene que ser miembro de ese chat y poder ver el mensaje. |
| `FloodWait` en el registro | Telegram está limitando. Baja las conexiones paralelas y espera los segundos que indica. |
| Fallan los archivos de más de 2 GB | Solo las cuentas Premium pueden transferir hasta 4 GB. |
