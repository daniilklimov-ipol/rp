"""Application-wide configuration and small persistence helpers."""

import json
import os

APP_NAME = "PyBrowser"
HOME_URL = "https://duckduckgo.com"
# A search template used when the address bar text is not a URL.
SEARCH_URL = "https://duckduckgo.com/?q={query}"

# Where per-user data (bookmarks, history) lives.
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", APP_NAME.lower())
BOOKMARKS_FILE = os.path.join(CONFIG_DIR, "bookmarks.json")
HISTORY_FILE = os.path.join(CONFIG_DIR, "history.json")

# Cap the stored history so the file cannot grow without bound.
MAX_HISTORY = 1000


def _ensure_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)


def load_json(path, default):
    """Load a JSON file, returning ``default`` on any error."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def save_json(path, data):
    """Persist ``data`` as JSON, creating the config dir if needed."""
    _ensure_dir()
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
    except OSError:
        # Persistence is best-effort; never crash the browser over it.
        pass
