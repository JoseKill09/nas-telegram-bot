# Google Drive desde cero

[Read in English](../en/google-drive.md) · [Todas las guías](README.md)

Con este módulo envías al bot un enlace de Google Drive (un archivo o una carpeta entera) y lo descarga directamente a tu NAS mediante la API oficial de Google Drive, con **tu propia** cuenta de Google y **tu propio** proyecto de Google Cloud. Nada pasa por servicios de terceros.

Se tarda unos 15 minutos y es gratis.

## Índice

- [Antes de empezar](#antes-de-empezar)
- [1. Crea un proyecto de Google Cloud](#1-crea-un-proyecto-de-google-cloud)
- [2. Activa la API de Google Drive](#2-activa-la-api-de-google-drive)
- [3. Configura la pantalla de consentimiento](#3-configura-la-pantalla-de-consentimiento)
- [4. Crea el cliente OAuth](#4-crea-el-cliente-oauth)
- [5. Dale las claves al bot](#5-dale-las-claves-al-bot)
- [6. Conecta tu cuenta](#6-conecta-tu-cuenta)
- [7. Úsalo](#7-úsalo)
- [Evita reconectar cada 7 días](#evita-reconectar-cada-7-días)
- [Privacidad](#privacidad)
- [Problemas frecuentes](#problemas-frecuentes)

## Antes de empezar

- **La web app tiene que estar en línea por HTTPS** ([Publicar la web app](web-app-hosting.md)), porque cuando apruebas el acceso Google te devuelve a `https://<tu-panel>/oauth2/google/callback`.
- Apunta tu **URI de redirección**: la URL de tu web app + `/oauth2/google/callback`. Ejemplo: `https://panel.tu-dominio.com/oauth2/google/callback`. El bot también la muestra en **Ajustes → Google Drive**.
- El bot solo pide acceso de **solo lectura** (`drive.readonly`): puede leer y descargar, nunca cambiar ni borrar nada de tu Drive.

## 1. Crea un proyecto de Google Cloud

1. Abre [console.cloud.google.com](https://console.cloud.google.com) e inicia sesión con la cuenta de Google que vayas a usar.
2. Acepta las condiciones si es la primera vez.
3. Arriba, abre el selector de proyectos → **Proyecto nuevo**. Nombre: `NAS Bot` (el que quieras). Organización: *Sin organización*. **Crear**.
4. Comprueba que el proyecto nuevo está seleccionado en la barra superior.

## 2. Activa la API de Google Drive

1. Menú ☰ → **APIs y servicios → Biblioteca**.
2. Busca **Google Drive API**, ábrela y pulsa **Habilitar**.

## 3. Configura la pantalla de consentimiento

Google llama a esta zona **Google Auth Platform** (en paneles antiguos, *Pantalla de consentimiento de OAuth*).

1. Menú ☰ → **APIs y servicios → Pantalla de consentimiento de OAuth** (o **Google Auth Platform**) → **Comenzar**.
2. **Información de la aplicación**: nombre `NAS Bot`, correo de asistencia: el tuyo. Siguiente.
3. **Público**: **Externo**. Siguiente.
4. **Información de contacto**: tu correo. Siguiente, acepta la política y **Crear**.
5. Ve a **Público → Usuarios de prueba → Añadir usuarios** y añade **tu propia cuenta de Google** (la del Drive que vas a usar). Guarda.
6. Opcional, pero útil: **Acceso a los datos → Añadir o quitar permisos** → marca `.../auth/drive.readonly` → Actualizar → Guardar.

## 4. Crea el cliente OAuth

1. Ve a **Clientes** (en paneles antiguos: **APIs y servicios → Credenciales → Crear credenciales → ID de cliente de OAuth**).
2. **Tipo de aplicación: Aplicación web**. Nombre: `NAS Bot web`.
3. **URIs de redirección autorizados → Añadir URI** y pega tu URI de redirección **exactamente**, por ejemplo
   `https://panel.tu-dominio.com/oauth2/google/callback`
   (con https, sin barra final y con el mismo subdominio que tu web app).
4. Deja vacío *Orígenes de JavaScript autorizados*. **Crear**.
5. Una ventana muestra el **ID de cliente** (termina en `.apps.googleusercontent.com`) y el **Secreto del cliente** (empieza por `GOCSPX-`). Copia los dos. Puedes descargar el JSON como copia; guárdalo en privado.

## 5. Dale las claves al bot

En Telegram: **Ajustes → Google Drive → 🔑 Credenciales de Google → 🔑 Client ID / secret**, y envía el **ID de cliente** y el **Secreto del cliente** en **un solo mensaje, separados por un espacio**, por ejemplo:

```
1234-abc.apps.googleusercontent.com GOCSPX-xxxxxxxx
```

El bot borra tu mensaje y guarda las claves en su base de datos.

(Alternativa: `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET` en el `.env`. Si tu URI de redirección no es la de por defecto, pon también `GOOGLE_REDIRECT_URI`.)

## 6. Conecta tu cuenta

1. **Ajustes → Google Drive → 🔌 Conectar**. El bot te envía un enlace.
2. Ábrelo y elige la cuenta de Google que añadiste como usuario de prueba.
3. Google avisa: **«Google no ha verificado esta aplicación»**. Es tu propia app, así que pulsa **Continuar** (a veces está en *Configuración avanzada → Ir a NAS Bot*).
4. Permite el acceso. Llegarás a una página que dice **✅ Cuenta conectada**. Vuelve a Telegram y abre otra vez **Ajustes → Google Drive**: el estado ya es 🟢 con tu correo.

## 7. Úsalo

Envía al bot cualquier enlace de Drive: `https://drive.google.com/file/d/…`, `…/open?id=…` o una carpeta `https://drive.google.com/drive/folders/…`. El bot lista los archivos (las carpetas se leen enteras, incluidas las unidades compartidas), eliges la carpeta de destino y lo descarga. También funciona desde la web app.

Puedes descargar archivos de tu propio Drive, archivos compartidos contigo y archivos públicos de «cualquier persona con el enlace». Los enlaces de Google Drive se descargan siempre con la API de Drive, nunca a través de servicios debrid.

## Evita reconectar cada 7 días

Mientras la app está en **Prueba**, Google caduca la autorización a los 7 días aproximadamente y tienes que volver a pulsar Conectar. Para evitarlo:

1. **Google Auth Platform → Público → Publicar aplicación** → Confirmar.
2. Desconecta y vuelve a conectar en el bot (Ajustes → Google Drive).

Puede que Google diga que la app necesita verificación porque Drive es un permiso sensible. Si la app solo la usas tú, no hace falta enviarla a verificar: seguirás viendo el aviso de «app no verificada» al conectar, y la autorización ya no caducará cada semana.

## Privacidad

- Las claves y el token de actualización se guardan solo en `data/bot_config/bot.db`, en tu NAS.
- Puedes retirar el acceso cuando quieras en [myaccount.google.com/permissions](https://myaccount.google.com/permissions) o con **Ajustes → Google Drive → Desconectar**.

## Problemas frecuentes

| Error | Causa y solución |
|---|---|
| `redirect_uri_mismatch` | La URI de Google no es exactamente la que usa el bot. Compárala carácter a carácter (https, subdominio, sin `/` al final). Los cambios tardan unos minutos en aplicarse. |
| `access_denied` / «la app está en prueba» | Tu cuenta no está en **Usuarios de prueba**. Añádela. |
| «Google no devolvió un refresh_token» | Ya habías autorizado antes. Quita la app en [myaccount.google.com/permissions](https://myaccount.google.com/permissions) y vuelve a conectar. |
| `invalid_client` | El ID de cliente o el secreto se copiaron mal (¿algún espacio?). Envíalos otra vez. |
| Página «Solicitud inválida» | El enlace de Conectar caduca y solo sirve una vez. Pulsa **Conectar** de nuevo. |
| El enlace no abre ninguna página | La web app no está en línea. Comprueba `https://<tu-panel>/api/health`. |
| `404 File not found` al descargar | Tu cuenta no puede abrir ese archivo. Abre el enlace en el navegador con la misma cuenta para comprobarlo. |
| Hay que reconectar cada semana | La app sigue en Prueba. Mira [más arriba](#evita-reconectar-cada-7-días). |
