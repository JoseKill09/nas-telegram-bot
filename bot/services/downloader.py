import aria2p
import config

_api = None


def reset_api():
    global _api
    _api = None


def get_api():
    global _api
    if _api is None:
        client = aria2p.Client(host=config.ARIA2_HOST, port=config.ARIA2_PORT, secret=config.ARIA2_SECRET)
        _api = aria2p.API(client)
    return _api


def add_uri(url: str, dest_dir: str, filename: str | None = None, connections: int = 16) -> str:
    connections = max(1, min(16, connections))
    options = {
        "dir": dest_dir,
        "split": str(connections),
        "max-connection-per-server": str(connections),
        "min-split-size": "1M",
    }
    if filename:
        options["out"] = filename

    try:
        api = get_api()
        download = api.add_uris([url], options=options)
        return download.gid
    except Exception:
        reset_api()
        api = get_api()
        download = api.add_uris([url], options=options)
        return download.gid


def get_download(gid: str):
    try:
        return get_api().get_download(gid)
    except Exception:
        reset_api()
        return get_api().get_download(gid)


def get_active_downloads_dict() -> dict:
    try:
        api = get_api()
        downloads = api.tell_active()
        return {d.gid: d for d in downloads}
    except Exception:
        reset_api()
        try:
            api = get_api()
            downloads = api.tell_active()
            return {d.gid: d for d in downloads}
        except Exception:
            return {}


def pause(gid: str):
    try:
        get_download(gid).pause()
    except Exception:
        reset_api()
        get_download(gid).pause()


def resume(gid: str):
    try:
        get_download(gid).resume()
    except Exception:
        reset_api()
        get_download(gid).resume()


def remove_download(gid: str, delete_files: bool = True):
    try:
        dl = get_download(gid)
        dl.remove(force=True, files=delete_files)
    except Exception:
        reset_api()
        dl = get_download(gid)
        dl.remove(force=True, files=delete_files)
