import _pathsetup

import asyncio
import logging
import signal

from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

import config
import db
import filemanager
import google_drive
import handlers_start as h_start
import handlers_userbot as h_ub
import handlers_files as h_files
import handlers_downloads as h_dl
import handlers_settings as h_settings
import handlers_realdebrid as h_rd
import handlers_torbox as h_tb
import handlers_gdrive as h_gdrive
import handlers_setup as h_setup
import handlers_clients as h_clients
import handlers_tools as h_tools
import notifier
import handlers_tbmanage as h_tbm
import handlers_search as h_search
import handlers_ytdlp as h_ytdl
import ytdlp_downloader
import i18n
import torrent_search
import webapp
import webserver
import tunnel
from userbot_manager import UserbotManager
from i18n import L
from utils import is_authorized
import rich_bot
from rich_bot import RichExtBot

import warnings
warnings.filterwarnings("ignore", message=r".*per_message=False.*")
warnings.filterwarnings("ignore", message=r".*do_api_request.*")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logging.getLogger("telethon").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def error_handler(update, context):
    logger.error("Excepción no controlada", exc_info=context.error)
    try:
        if config.OWNER_ID:
            await context.bot.send_message(
                chat_id=config.OWNER_ID,
                text=f"⚠️ Error interno: {context.error}",
            )
    except Exception:
        pass


async def route_text(update: Update, context):
    user = update.effective_user
    if user is None or not await is_authorized(user.id):
        return
    if user.id != config.OWNER_ID:
        try:
            await db.update_authorized_user_info(user.id, user.username, user.first_name)
        except Exception:
            pass

    consumed = await h_dl.handle_password_reply(update, context)
    if consumed:
        return
    consumed = await h_files.handle_pending_text(update, context)
    if consumed:
        return
    consumed = await h_dl.handle_pending_text(update, context)
    if consumed:
        return
    consumed = await h_setup.handle_pending_text(update, context)
    if consumed:
        return
    consumed = await h_settings.handle_pending_text(update, context)
    if consumed:
        return
    consumed = await h_ub.handle_pending_text(update, context)
    if consumed:
        return

    text = update.effective_message.text or ""
    text_clean = text.strip()

    import tg_links
    tg = tg_links.find_links(text_clean)
    if tg:
        await h_dl.handle_tg_links(update, context, tg)
        return

    if google_drive.is_drive_url(text_clean):
        await h_gdrive.handle_drive_link(update, context, text_clean)
        return

    if text_clean.startswith("magnet:?"):
        await h_rd.handle_magnet(update, context, text_clean)
        return

    if ytdlp_downloader.is_ytdlp_url(text_clean):
        await h_ytdl.handle_ytdlp_url(update, context, text_clean)
        return

    if text_clean.startswith(("http://", "https://")):
        await h_dl.handle_incoming_links(update, context, [text_clean])
        return

    await update.effective_message.reply_text(
        L("No he entendido el mensaje.\n\n"
          "• /buscar <texto> — busca torrents\n"
          "• /link <url> — descarga enlaces directos\n"
          "• /torrent <magnet> — descarga un torrent con el proveedor que elijas\n"
          "• /cola — cola de descargas\n"
          "• /setup — configuración del proyecto\n"
          "• O envíame un archivo directamente.",
          "I didn't understand that.\n\n"
          "• /search <text> — search torrents\n"
          "• /link <url> — download direct links\n"
          "• /torrent <magnet> — download a torrent with the provider of your choice\n"
          "• /queue — download queue\n"
          "• /setup — project setup\n"
          "• Or send me a file directly.")
    )


async def post_init(application: Application):
    notifier.set_bot(application.bot)
    db.add_task_listener(notifier.task_changed)
    try:
        filemanager.ensure_all_base_folders()
    except Exception as e:
        logger.warning("Could not create base folders: %s", e)

    try:
        manager = UserbotManager(
            config.API_ID, config.API_HASH, db.get_session_string, db.set_session_string,
            set_meta_cb=db.set_userbot_meta, clear_meta_cb=db.clear_userbot_meta,
        )
        if config.API_ID and config.API_HASH:
            await manager.load_existing()
        application.bot_data["userbot_manager"] = manager
    except Exception as e:
        logger.error("Could not initialise the userbot manager: %s", e)

    if not config.LANGUAGE and config.OWNER_ID:
        try:
            text, kb = h_setup.language_content(first_run=True)
            await application.bot.send_message(
                chat_id=config.OWNER_ID,
                text="👋 " + L("¡Hola! / Hello!", "Hello! / ¡Hola!") + "\n\n" + text,
                parse_mode="HTML",
                reply_markup=kb,
            )
        except Exception as e:
            logger.warning("Could not send the welcome message to the owner: %s", e)


def build_app() -> Application:
    application = Application.builder().bot(RichExtBot(token=config.BOT_TOKEN)).build()

    application.add_handler(CommandHandler("start", h_start.start))
    application.add_handler(CommandHandler(["setup", "settings", "ajustes"], h_setup.setup_command))
    application.add_handler(CommandHandler("version", h_start.version_command))
    application.add_handler(CommandHandler("rich", h_start.rich_command))
    application.add_handler(CommandHandler(["backup", "copia"], h_tools.backup_command))
    application.add_handler(CommandHandler(["disk", "disco"], h_tools.disk_command))
    application.add_handler(CommandHandler(["notify", "avisos"], h_tools.notif_command))
    application.add_handler(CallbackQueryHandler(h_start.rich_toggle, pattern="^rich:toggle$"))
    application.add_handler(CommandHandler(["buscar", "search"], h_search.search_command))
    application.add_handler(CommandHandler(["web", "acceso"], h_setup.web_link_command))
    application.add_handler(CommandHandler("link", h_dl.link_command))
    application.add_handler(CommandHandler("ytdl", h_ytdl.ytdl_command))
    application.add_handler(CommandHandler("torrent", h_rd.torrent_command))
    application.add_handler(CommandHandler("queue", h_dl.queue_command))
    application.add_handler(CommandHandler("cola", h_dl.queue_command))
    application.add_handler(CommandHandler("historial", h_dl.history_command))
    application.add_handler(CommandHandler("history", h_dl.history_command))
    application.add_handler(CommandHandler("cancel", h_start.cancel_pending))
    application.add_handler(CallbackQueryHandler(h_start.main_menu_callback, pattern="^menu:main$"))
    application.add_handler(CallbackQueryHandler(h_start.help_callback, pattern="^menu:help$"))

    application.add_handler(CallbackQueryHandler(h_search.search_page_callback, pattern="^ts:page:"))
    application.add_handler(CallbackQueryHandler(h_search.search_fallback_callback, pattern="^ts:fb:"))
    application.add_handler(CallbackQueryHandler(h_search.search_download_callback, pattern="^ts:dl:"))
    application.add_handler(CallbackQueryHandler(h_search.search_item_callback, pattern="^ts:i:"))
    application.add_handler(CallbackQueryHandler(h_search.search_filters_callback, pattern="^ts:f:"))
    application.add_handler(CallbackQueryHandler(h_search.search_filter_change, pattern="^ts:fc:"))
    application.add_handler(CallbackQueryHandler(h_search.search_filter_reset, pattern="^ts:fr:"))
    application.add_handler(CommandHandler("torbox", h_tbm.torbox_command))
    application.add_handler(CallbackQueryHandler(h_tbm.tbl_page, pattern="^tbl:p:"))
    application.add_handler(CallbackQueryHandler(h_tbm.tbl_open, pattern="^tbl:o:"))
    application.add_handler(CallbackQueryHandler(h_tbm.tbl_send, pattern="^tbl:send:"))
    application.add_handler(CallbackQueryHandler(h_tbm.tbl_delete_confirm, pattern="^tbl:del:"))
    application.add_handler(CallbackQueryHandler(h_tbm.tbl_delete, pattern="^tbl:delok:"))
    application.add_handler(CallbackQueryHandler(h_tbm.tbl_delete_all_confirm, pattern="^tbl:delall$"))
    application.add_handler(CallbackQueryHandler(h_tbm.tbl_delete_all, pattern="^tbl:delallok$"))

    application.add_handler(CallbackQueryHandler(h_ub.userbot_menu, pattern="^ub:menu$"))
    application.add_handler(CallbackQueryHandler(h_ub.disconnect, pattern="^ub:disconnect$"))
    application.add_handler(CallbackQueryHandler(h_ub.set_connections_entry, pattern="^ub:set_connections$"))
    application.add_handler(h_ub.build_conversation_handler())

    application.add_handler(CallbackQueryHandler(h_files.fm_root, pattern="^fm:root$"))
    application.add_handler(CallbackQueryHandler(h_files.fm_nav, pattern="^fm:nav:"))
    application.add_handler(CallbackQueryHandler(h_files.fm_file_menu, pattern="^fm:file:"))
    application.add_handler(CallbackQueryHandler(h_files.fm_info, pattern="^fm:info:"))
    application.add_handler(CallbackQueryHandler(h_files.fm_delete_confirm, pattern="^fm:delconfirm:"))
    application.add_handler(CallbackQueryHandler(h_files.fm_delete, pattern="^fm:delete:"))
    application.add_handler(CallbackQueryHandler(h_files.fm_rename_entry, pattern="^fm:rename:"))
    application.add_handler(CallbackQueryHandler(h_files.fm_mkdir_entry, pattern="^fm:mkdir:"))
    application.add_handler(CallbackQueryHandler(h_files.fm_upload_entry, pattern="^fm:upload:"))
    application.add_handler(CallbackQueryHandler(h_files.fm_upload_as, pattern="^fm:uploadas:"))
    application.add_handler(CallbackQueryHandler(h_files.fm_extract_entry, pattern="^fm:extract:"))
    application.add_handler(CallbackQueryHandler(h_files.fm_cancel_upload, pattern="^fm:cancelup:"))
    application.add_handler(CallbackQueryHandler(h_files.fm_cp_start, pattern="^fm:cp:"))
    application.add_handler(CallbackQueryHandler(h_files.fm_cp_roots, pattern="^fm:cproots$"))
    application.add_handler(CallbackQueryHandler(h_files.fm_cp_nav, pattern="^fm:cpnav:"))
    application.add_handler(CallbackQueryHandler(h_files.fm_cp_toggle, pattern="^fm:cp(pol|mv)$"))
    application.add_handler(CallbackQueryHandler(h_files.fm_cp_go, pattern="^fm:cpgo$"))
    application.add_handler(CallbackQueryHandler(h_files.fm_cp_cancel, pattern="^fm:cpcancel$"))
    application.add_handler(CallbackQueryHandler(h_files.fm_cp_stop, pattern="^fm:cpstop:"))

    application.add_handler(CallbackQueryHandler(h_setup.settings_menu, pattern="^settings:menu$"))
    application.add_handler(CallbackQueryHandler(h_setup.language_menu, pattern="^lang:menu$"))
    application.add_handler(CallbackQueryHandler(h_setup.language_set, pattern="^lang:set:"))
    application.add_handler(CallbackQueryHandler(h_setup.guide_view, pattern="^guide:"))
    application.add_handler(CallbackQueryHandler(h_setup.lan_menu, pattern="^lan:menu$"))
    application.add_handler(CallbackQueryHandler(h_setup.lan_toggle, pattern="^lan:toggle$"))
    application.add_handler(CallbackQueryHandler(h_setup.lan_url_prompt, pattern="^lan:url$"))
    application.add_handler(CallbackQueryHandler(h_setup.lan_link_cb, pattern="^lan:link$"))
    application.add_handler(CallbackQueryHandler(h_setup.lan_revoke_cb, pattern="^lan:revoke$"))
    application.add_handler(CallbackQueryHandler(h_setup.folders_menu, pattern="^fld:menu$"))
    application.add_handler(CallbackQueryHandler(h_setup.folder_open, pattern="^fld:o:"))
    application.add_handler(CallbackQueryHandler(h_setup.folder_media, pattern="^fld:m:"))
    application.add_handler(CallbackQueryHandler(h_setup.folder_delete, pattern="^fld:d:"))
    application.add_handler(CallbackQueryHandler(h_setup.folder_add_prompt, pattern="^fld:add$"))
    application.add_handler(CallbackQueryHandler(h_setup.folder_path_start, pattern="^fld:p:"))
    application.add_handler(CallbackQueryHandler(h_setup.folder_rename_prompt, pattern="^fld:r:"))
    application.add_handler(CallbackQueryHandler(h_setup.folder_browse, pattern="^fld:(b|up|pg|new|browse|typed|pick|nm):?"))
    application.add_handler(CallbackQueryHandler(h_setup.folders_reset, pattern="^fld:reset$"))
    application.add_handler(CallbackQueryHandler(h_setup.web_menu, pattern="^web:menu$"))
    application.add_handler(CallbackQueryHandler(h_setup.web_toggle, pattern="^web:toggle$"))
    application.add_handler(CallbackQueryHandler(h_setup.web_url_prompt, pattern="^web:url$"))
    application.add_handler(CallbackQueryHandler(h_setup.web_url_clear, pattern="^web:urlclear$"))
    application.add_handler(CallbackQueryHandler(h_setup.tunnel_menu, pattern="^web:tn$"))
    application.add_handler(CallbackQueryHandler(h_setup.tunnel_toggle, pattern="^web:tntog$"))
    application.add_handler(CallbackQueryHandler(h_setup.tunnel_token_prompt, pattern="^web:tntok$"))
    application.add_handler(CallbackQueryHandler(h_setup.tunnel_token_clear, pattern="^web:tnclear$"))
    application.add_handler(CallbackQueryHandler(h_setup.userbot_creds_menu, pattern="^ub:cfg$"))
    application.add_handler(CallbackQueryHandler(h_setup.cfg_api_prompt, pattern="^cfg:api$"))
    application.add_handler(CallbackQueryHandler(h_setup.cfg_channel_prompt, pattern="^cfg:channel$"))
    application.add_handler(CallbackQueryHandler(h_setup.gdrive_creds_menu, pattern="^gdrive:cfg$"))
    application.add_handler(CallbackQueryHandler(h_setup.cfg_gid_prompt, pattern="^cfg:gid$"))
    application.add_handler(CallbackQueryHandler(h_clients.client_action, pattern="^cl:"))
    application.add_handler(CallbackQueryHandler(h_tools.restore_action, pattern="^bk:(rt|rgo)"))
    application.add_handler(CallbackQueryHandler(h_tools.backup_action, pattern="^bk:"))
    application.add_handler(CallbackQueryHandler(h_tools.notif_action, pattern="^nt:"))
    application.add_handler(CallbackQueryHandler(h_tools.disk_action, pattern="^dk:"))
    application.add_handler(CallbackQueryHandler(h_tools.rules_action, pattern="^ru:"))
    application.add_handler(CallbackQueryHandler(h_settings.extract_menu, pattern="^extract:menu$"))
    application.add_handler(CallbackQueryHandler(h_settings.extract_toggle, pattern="^extract:toggle$"))
    application.add_handler(CallbackQueryHandler(h_settings.limits_menu, pattern="^limits:menu$"))
    application.add_handler(CallbackQueryHandler(h_settings.limits_group_menu, pattern="^limits:group:"))
    application.add_handler(CallbackQueryHandler(h_settings.limits_set_entry, pattern="^limits:set:"))
    application.add_handler(CallbackQueryHandler(h_settings.rd_menu, pattern="^rd:menu$"))
    application.add_handler(CallbackQueryHandler(h_settings.rd_toggle, pattern="^rd:toggle$"))
    application.add_handler(CallbackQueryHandler(h_settings.rd_remove_token, pattern="^rd:remove_token$"))
    application.add_handler(CallbackQueryHandler(h_settings.rd_purge_confirm, pattern="^rd:purge_confirm$"))
    application.add_handler(CallbackQueryHandler(h_settings.rd_purge_do, pattern="^rd:purge_do$"))
    application.add_handler(h_settings.build_rd_token_conversation())
    application.add_handler(h_settings.build_tb_token_conversation())
    application.add_handler(h_settings.build_tmdb_token_conversation())
    application.add_handler(CallbackQueryHandler(h_settings.tmdb_menu, pattern="^tmdb:menu$"))
    application.add_handler(CallbackQueryHandler(h_settings.tmdb_toggle, pattern="^tmdb:toggle$"))
    application.add_handler(CallbackQueryHandler(h_settings.tmdb_remove_token, pattern="^tmdb:remove_token$"))
    application.add_handler(CallbackQueryHandler(h_settings.proxy_menu, pattern="^src:px$"))
    application.add_handler(CallbackQueryHandler(h_settings.proxy_toggle, pattern="^src:pxtog$"))
    application.add_handler(CallbackQueryHandler(h_settings.proxy_test, pattern="^src:pxtest$"))
    application.add_handler(CallbackQueryHandler(h_settings.proxy_url_prompt, pattern="^src:pxurl$"))
    application.add_handler(CallbackQueryHandler(h_settings.proxy_reset, pattern="^src:pxrst$"))
    application.add_handler(CallbackQueryHandler(h_settings.sources_menu, pattern="^src:menu$"))
    application.add_handler(CallbackQueryHandler(h_settings.search_modes_menu, pattern="^src:modes$"))
    application.add_handler(CallbackQueryHandler(h_settings.search_mode_set, pattern="^src:mode:"))
    application.add_handler(CallbackQueryHandler(h_settings.prowlarr_menu, pattern="^px:menu$"))
    application.add_handler(CallbackQueryHandler(h_settings.prowlarr_prompt, pattern="^px:(url|key)$"))
    application.add_handler(CallbackQueryHandler(h_settings.prowlarr_test_cb, pattern="^px:test$"))
    application.add_handler(CallbackQueryHandler(h_settings.prowlarr_delete_cb, pattern="^px:del$"))
    application.add_handler(CallbackQueryHandler(h_settings.sources_test_all, pattern="^src:all$"))
    application.add_handler(CallbackQueryHandler(h_settings.source_menu, pattern="^src:p:"))
    application.add_handler(CallbackQueryHandler(h_settings.source_toggle, pattern="^src:tog:"))
    application.add_handler(CallbackQueryHandler(h_settings.source_test, pattern="^src:t:"))
    application.add_handler(CallbackQueryHandler(h_settings.source_mirror_prompt, pattern="^src:madd:"))
    application.add_handler(CallbackQueryHandler(h_settings.source_mirror_delete, pattern="^src:mdel:"))
    application.add_handler(CallbackQueryHandler(h_settings.source_mirror_reset, pattern="^src:mrst:"))
    application.add_handler(CallbackQueryHandler(h_settings.source_mirror_save_anyway, pattern="^src:msave:"))
    application.add_handler(CallbackQueryHandler(h_settings.source_delete_confirm, pattern="^src:del:"))
    application.add_handler(CallbackQueryHandler(h_settings.source_delete, pattern="^src:delok:"))
    application.add_handler(CallbackQueryHandler(h_settings.sources_restore, pattern="^src:restore$"))
    application.add_handler(CallbackQueryHandler(h_settings.source_new_menu, pattern="^src:new$"))
    application.add_handler(CallbackQueryHandler(h_settings.source_new_torznab, pattern="^src:newt$"))
    application.add_handler(CallbackQueryHandler(h_settings.source_new_clone, pattern="^src:newc:"))
    application.add_handler(CallbackQueryHandler(h_settings.providers_menu, pattern="^prov:menu$"))
    application.add_handler(CallbackQueryHandler(h_settings.tb_menu, pattern="^tb:menu$"))
    application.add_handler(CallbackQueryHandler(h_settings.tb_toggle, pattern="^tb:toggle$"))
    application.add_handler(CallbackQueryHandler(h_settings.tb_remove_token, pattern="^tb:remove_token$"))
    application.add_handler(CallbackQueryHandler(h_settings.users_menu, pattern="^users:menu$"))
    application.add_handler(CallbackQueryHandler(h_settings.users_add_entry, pattern="^users:add$"))
    application.add_handler(CallbackQueryHandler(h_settings.users_remove, pattern="^users:remove:"))
    application.add_handler(CallbackQueryHandler(h_gdrive.gdrive_menu, pattern="^gdrive:menu$"))
    application.add_handler(CallbackQueryHandler(h_gdrive.gdrive_connect, pattern="^gdrive:connect$"))
    application.add_handler(CallbackQueryHandler(h_gdrive.gdrive_disconnect, pattern="^gdrive:disconnect$"))

    application.add_handler(CallbackQueryHandler(h_rd.rd_toggle_file, pattern="^rdfile:"))
    application.add_handler(CallbackQueryHandler(h_rd.rd_select_all, pattern="^rdall:"))
    application.add_handler(CallbackQueryHandler(h_rd.rd_select_none, pattern="^rdnone:"))
    application.add_handler(CallbackQueryHandler(h_rd.rd_confirm_selection, pattern="^rdconfirm:"))
    application.add_handler(CallbackQueryHandler(h_rd.rd_cancel_selection, pattern="^rdcancelsel:"))
    application.add_handler(CallbackQueryHandler(h_rd.rd_cancel_monitor, pattern="^rdcancel:"))
    application.add_handler(CallbackQueryHandler(h_rd.rd_extract_choice, pattern="^rdext:"))
    application.add_handler(CallbackQueryHandler(h_tb.provider_selected, pattern="^provsel:"))

    application.add_handler(CallbackQueryHandler(h_dl.queue_view_callback, pattern="^queue:(view|refresh)$"))
    application.add_handler(CallbackQueryHandler(h_dl.choose_method, pattern="^method:"))
    application.add_handler(CallbackQueryHandler(h_dl.file_batch_same, pattern="^fbatch:same:"))
    application.add_handler(CallbackQueryHandler(h_dl.file_batch_diff, pattern="^fbatch:diff:"))
    application.add_handler(CallbackQueryHandler(h_dl.dl_root, pattern="^dlroot:"))
    application.add_handler(CallbackQueryHandler(h_dl.dl_rename_entry, pattern="^dlrn:"))
    application.add_handler(CallbackQueryHandler(h_dl.dl_nav, pattern="^dlnav:"))
    application.add_handler(CallbackQueryHandler(h_dl.dl_mkdir_entry, pattern="^dlmkdir:"))
    application.add_handler(CallbackQueryHandler(h_dl.dl_save, pattern="^dlsave:"))
    application.add_handler(CallbackQueryHandler(h_dl.dl_extract_choice, pattern="^dlextract:"))
    application.add_handler(CallbackQueryHandler(h_dl.dl_sched_menu, pattern="^dlsched:"))
    application.add_handler(CallbackQueryHandler(h_dl.dl_sched_apply, pattern="^dlschedset:"))
    application.add_handler(CallbackQueryHandler(h_dl.dl_sched_at, pattern="^dlschedat:"))
    application.add_handler(CallbackQueryHandler(h_dl.dl_cancel, pattern="^dlcancel:"))
    application.add_handler(CallbackQueryHandler(h_dl.dl_pause, pattern="^dlpause:"))
    application.add_handler(CallbackQueryHandler(h_dl.dl_resume, pattern="^dlresume:"))
    application.add_handler(CallbackQueryHandler(h_dl.dl_prioritize, pattern="^dlprio:"))
    application.add_handler(CallbackQueryHandler(h_dl.dl_move_up, pattern="^dlmoveup:"))
    application.add_handler(CallbackQueryHandler(h_dl.dl_move_down, pattern="^dlmovedown:"))
    application.add_handler(CallbackQueryHandler(h_dl.history_page_callback, pattern="^hist:page:"))
    application.add_handler(CallbackQueryHandler(h_dl.history_clear_confirm, pattern="^hist:clear_confirm$"))
    application.add_handler(CallbackQueryHandler(h_dl.history_clear_do, pattern="^hist:clear_do$"))

    application.add_handler(CallbackQueryHandler(h_ytdl.ytdl_dest_callback, pattern="^ytdl:dest:"))
    application.add_handler(CallbackQueryHandler(h_ytdl.ytdl_opt_callback, pattern="^ytdl:opt:"))
    application.add_handler(CallbackQueryHandler(h_ytdl.ytdl_folder_callback, pattern="^ytdl:folder:"))
    application.add_handler(CallbackQueryHandler(h_ytdl.ytdl_cancel_callback, pattern="^ytdl:cancel:"))
    application.add_handler(MessageHandler(filters.FORWARDED, h_setup.handle_pending_forward), group=-1)
    application.add_handler(MessageHandler(
        filters.Document.ALL | filters.VIDEO | filters.AUDIO | filters.PHOTO,
        h_dl.handle_incoming_file,
    ))
    application.add_handler(MessageHandler(
        filters.StatusUpdate.USERS_SHARED,
        h_settings.users_pick_received,
    ))
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        route_text,
    ))

    application.job_queue.run_repeating(h_dl.poll_aria2_downloads, interval=2, first=2)
    application.job_queue.run_repeating(h_dl.push_telegram_progress, interval=2, first=2)
    application.job_queue.run_repeating(h_dl.push_gdrive_progress, interval=2, first=2)
    application.job_queue.run_repeating(h_dl.push_extract_progress, interval=2, first=2)
    application.job_queue.run_repeating(h_dl.queue_worker, interval=15, first=15)
    application.job_queue.run_repeating(notifier.disk_job, interval=600, first=60)
    application.job_queue.run_repeating(h_tools.auto_backup_job, interval=3600, first=120)
    application.add_error_handler(error_handler)

    return application


def main():
    asyncio.run(run())


async def run():
    if not config.BOT_TOKEN or not config.OWNER_ID:
        raise SystemExit("BOT_TOKEN and OWNER_ID must be set in the .env file.")

    await db.init_db()
    # one-time (19.3.2): old requests left waiting for a folder are archived so the web app doesn't list them
    if await db.get_setting("pending_cleanup_1932", "0") != "1":
        for _t in await db.get_tasks_by_status("pending_folder"):
            await db.update_task(_t["id"], status="cancelled")
        await db.set_setting("pending_cleanup_1932", "1")
    await config.load_runtime()
    i18n.set_lang(config.LANGUAGE)
    await torrent_search.load_custom()
    rich_bot.set_enabled(await db.get_setting("rich_enabled", "1") == "1" and rich_bot.RICH_ENABLED_BY_ENV)

    application = build_app()
    webapp.set_application(application)

    await application.initialize()
    await post_init(application)
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)

    import lan_access
    if await lan_access.server_needed():   # Telegram web app and/or local network access
        await webserver.start()
    await tunnel.autostart()

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass

    try:
        await stop.wait()
    finally:
        await tunnel.stop()
        await webserver.stop()
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


if __name__ == "__main__":
    main()
