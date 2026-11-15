from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ConversationHandler, MessageHandler, CommandHandler, CallbackQueryHandler, filters
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneNumberInvalidError

import config
import db
import keyboards
from rich_ui import esc, header, r_h, r_p, r_kv_table, r_footer, rich
from utils import owner_only

PHONE, CODE, PASSWORD = range(3)
MIN_CONNECTIONS, MAX_CONNECTIONS = 1, 40


@owner_only
async def userbot_menu(update, context):
    query = update.callback_query
    await query.answer()
    manager = context.bot_data.get("userbot_manager")
    if manager is None:
        target = update.callback_query.message if update.callback_query else update.message
        await target.reply_text("⚠️ El bot todavía se está iniciando. Espera unos segundos y vuelve a intentarlo.")
        return ConversationHandler.END if update.message else None
    connected = await manager.is_connected()
    max_conn = await manager.get_max_connections()

    if connected:
        meta = await db.get_userbot_meta() or {}
        name = meta.get("first_name") or "(sin nombre)"
        username = f" · @{esc(meta.get('username'))}" if meta.get("username") else ""
        connected_at = (meta.get("connected_at") or "")[:10]
        pairs = [
            ("Estado", "🟢 Conectado"),
            ("Cuenta", f"<b>{esc(name)}</b>{username}"),
            ("ID", f"<code>{esc(meta.get('user_id', '?'))}</code>"),
            ("Desde", esc(connected_at or "desconocido")),
            ("Transferencias", f"FastTelethon · {max_conn} conexiones"),
        ]
    else:
        pairs = [("Estado", "🔴 Desconectado"), ("Transferencias", f"FastTelethon · {max_conn} conexiones")]

    creds_ok = bool(config.API_ID and config.API_HASH)
    if not creds_ok:
        pairs.append(("API ID / HASH", "⚠️ Sin configurar"))
    if not config.CHANNEL_ID:
        pairs.append(("Canal privado", "⚠️ Sin configurar"))
    action_row = [InlineKeyboardButton("🔌 Conectar nueva cuenta", callback_data="ub:connect" if creds_ok else "ub:cfg")]
    if connected:
        action_row.append(InlineKeyboardButton("🚫 Desconectar", callback_data="ub:disconnect"))
    kb = [action_row]
    if connected and meta.get("username"):
        kb.append([InlineKeyboardButton("👤 Ver perfil de la cuenta conectada", url=f"https://t.me/{meta['username']}")])
    kb += [
        [InlineKeyboardButton("🔑 Credenciales y canal", callback_data="ub:cfg"),
         InlineKeyboardButton("📖 Tutorial", callback_data="guide:userbot:ub:menu")],
        [InlineKeyboardButton(f"🔧 Conexiones paralelas ({max_conn})", callback_data="ub:set_connections")],
        [InlineKeyboardButton("⬅️ Ajustes", callback_data="settings:menu")],
    ]

    text = rich(
        r_h("Userbot", 2, "🤖"),
        r_kv_table(pairs),
        r_footer("Se usa para descargar archivos reenviados y subir archivos grandes a Telegram."),
    )
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb))


@owner_only
async def connect_entry(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "Vamos a conectar la cuenta de Telegram (recomendado: la que tenga Premium).\n\n"
        "Envíame el número de teléfono completo con prefijo internacional, ejemplo:\n"
        "<code>+34600000000</code>\n\nEnvía /cancel para cancelar en cualquier momento.",
        parse_mode=ParseMode.HTML,
    )
    return PHONE


@owner_only
async def receive_phone(update, context):
    phone = update.message.text.strip()
    manager = context.bot_data.get("userbot_manager")
    if manager is None:
        target = update.callback_query.message if update.callback_query else update.message
        await target.reply_text("⚠️ El bot todavía se está iniciando. Espera unos segundos y vuelve a intentarlo.")
        return ConversationHandler.END if update.message else None
    try:
        await manager.start_login(phone)
    except PhoneNumberInvalidError:
        await update.message.reply_text("❌ Número no válido. Inténtalo de nuevo o /cancel.")
        return PHONE
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
        return ConversationHandler.END

    await update.message.reply_text("📩 Te he enviado un código por Telegram. Escríbelo aquí (ej: 12345):")
    return CODE


@owner_only
async def receive_code(update, context):
    code = update.message.text.strip().replace(" ", "")
    manager = context.bot_data.get("userbot_manager")
    if manager is None:
        target = update.callback_query.message if update.callback_query else update.message
        await target.reply_text("⚠️ El bot todavía se está iniciando. Espera unos segundos y vuelve a intentarlo.")
        return ConversationHandler.END if update.message else None
    try:
        await manager.submit_code(code)
    except SessionPasswordNeededError:
        await update.message.reply_text("🔒 Tu cuenta tiene verificación en dos pasos. Envía tu contraseña:")
        return PASSWORD
    except PhoneCodeInvalidError:
        await update.message.reply_text("❌ Código incorrecto. Inténtalo de nuevo o /cancel.")
        return CODE
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
        return ConversationHandler.END

    await update.message.reply_text("✅ Userbot conectado correctamente.", reply_markup=keyboards.main_menu())
    return ConversationHandler.END


@owner_only
async def receive_password(update, context):
    password = update.message.text
    manager = context.bot_data.get("userbot_manager")
    if manager is None:
        target = update.callback_query.message if update.callback_query else update.message
        await target.reply_text("⚠️ El bot todavía se está iniciando. Espera unos segundos y vuelve a intentarlo.")
        return ConversationHandler.END if update.message else None
    try:
        await manager.submit_password(password)
    except Exception as e:
        await update.message.reply_text(f"❌ Contraseña incorrecta o error: {e}. Intenta de nuevo o /cancel.")
        return PASSWORD

    await update.message.reply_text("✅ Userbot conectado correctamente.", reply_markup=keyboards.main_menu())
    return ConversationHandler.END


@owner_only
async def cancel(update, context):
    await update.message.reply_text("Operación cancelada.", reply_markup=keyboards.main_menu())
    return ConversationHandler.END


@owner_only
async def disconnect(update, context):
    query = update.callback_query
    await query.answer()
    manager = context.bot_data.get("userbot_manager")
    if manager is None:
        target = update.callback_query.message if update.callback_query else update.message
        await target.reply_text("⚠️ El bot todavía se está iniciando. Espera unos segundos y vuelve a intentarlo.")
        return ConversationHandler.END if update.message else None
    await manager.disconnect_and_forget()
    await query.edit_message_text("🚫 Userbot desconectado y sesión olvidada.", reply_markup=keyboards.main_menu())


@owner_only
async def set_connections_entry(update, context):
    query = update.callback_query
    await query.answer()
    manager = context.bot_data.get("userbot_manager")
    current = await manager.get_max_connections() if manager else config.USERBOT_MAX_CONNECTIONS
    context.user_data["pending_ub_connections"] = True
    await query.edit_message_text(
        rich(
            r_h("Conexiones paralelas (FastTelethon)", 3, "🔧"),
            r_p(
                f"Valor actual: <b>{current}</b>. Envía un número entre <b>{MIN_CONNECTIONS}</b> y "
                f"<b>{MAX_CONNECTIONS}</b>."
            ),
            r_footer(
                "Telegram limita la velocidad real por su lado, no tu ancho de banda: subir este número "
                "no siempre acelera y valores muy altos pueden provocar FloodWait. Envía /cancel para cancelar."
            ),
        ),
        parse_mode=ParseMode.HTML,
    )


async def handle_pending_text(update, context) -> bool:
    if not context.user_data.get("pending_ub_connections"):
        return False

    raw = update.effective_message.text.strip()
    try:
        value = int(raw)
    except ValueError:
        await update.effective_message.reply_text(
            f"⚠️ Eso no es un número. Envía un valor entre {MIN_CONNECTIONS} y {MAX_CONNECTIONS}, o /cancel."
        )
        return True

    if not (MIN_CONNECTIONS <= value <= MAX_CONNECTIONS):
        await update.effective_message.reply_text(
            f"⚠️ Debe estar entre {MIN_CONNECTIONS} y {MAX_CONNECTIONS}. Inténtalo de nuevo, o /cancel."
        )
        return True

    manager = context.bot_data.get("userbot_manager")
    if manager:
        value = await manager.set_max_connections(value)
    else:
        await db.set_setting("userbot_max_connections", str(value))
    context.user_data.pop("pending_ub_connections", None)

    await update.effective_message.reply_text(
        f"✅ Conexiones paralelas ajustadas a <b>{value}</b>. Se aplica a la siguiente descarga/subida.",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboards.main_menu(),
    )
    return True


def build_conversation_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(connect_entry, pattern="^ub:connect$")],
        states={
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_phone)],
            CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_code)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_password)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )


def connect_button_markup():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔌 Conectar userbot", callback_data="ub:connect")]])
