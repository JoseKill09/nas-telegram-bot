import deluge
import qbittorrent
import transmission

CLIENTS = {
    "qbittorrent": {"module": qbittorrent, "label": "qBittorrent", "icon": "⬇️", "prefix": "qb", "tutorial": "qbit"},
    "transmission": {"module": transmission, "label": "Transmission", "icon": "📡", "prefix": "tr", "tutorial": "transmission"},
    "deluge": {"module": deluge, "label": "Deluge", "icon": "🌊", "prefix": "dg", "tutorial": "deluge"},
}


def is_client(provider: str | None) -> bool:
    return provider in CLIENTS


def module(provider: str):
    return CLIENTS[provider]["module"]


def label(provider: str) -> str:
    return CLIENTS[provider]["label"]


async def enabled_keys() -> list[str]:
    return [k for k, c in CLIENTS.items() if await c["module"].is_enabled()]
