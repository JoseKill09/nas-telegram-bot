import asyncio
import logging

import uvicorn

import config

logger = logging.getLogger(__name__)

_server: uvicorn.Server | None = None
_task: asyncio.Task | None = None


def running() -> bool:
    return _task is not None and not _task.done()


async def start() -> bool:
    global _server, _task
    if running():
        return True
    import webapp

    cfg = uvicorn.Config(webapp.app, host="0.0.0.0", port=config.WEBAPP_PORT, log_level="warning")
    _server = uvicorn.Server(cfg)
    _server.install_signal_handlers = lambda: None
    _task = asyncio.create_task(_server.serve())
    await asyncio.sleep(0.5)
    if _task.done():
        logger.error("The web server could not start: %s", _task.exception())
        return False
    return True


async def stop() -> None:
    global _server, _task
    if _server is not None:
        _server.should_exit = True
    if _task is not None:
        try:
            await asyncio.wait_for(_task, timeout=10)
        except Exception:
            _task.cancel()
    _server = None
    _task = None
