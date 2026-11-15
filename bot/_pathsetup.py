import sys
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent
_TOP_LEVEL_DIRS = ("core", "services", "plugins")

_done = False


def setup() -> None:
    global _done
    if _done:
        return
    _done = True

    for sub in _TOP_LEVEL_DIRS:
        top_dir = _BASE_DIR / sub
        if not top_dir.is_dir():
            continue
        _add(top_dir)
        if sub == "plugins":
            for plugin_dir in sorted(top_dir.iterdir()):
                if plugin_dir.is_dir() and not plugin_dir.name.startswith("_"):
                    _add(plugin_dir)


def _add(path: Path) -> None:
    p = str(path)
    if p not in sys.path:
        sys.path.insert(0, p)


setup()
