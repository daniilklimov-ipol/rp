"""Filesystem locations for app data (DB, model file, config), Windows-friendly."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "YouTubeWatchPredictor"


def app_data_dir() -> Path:
    """Return (creating if needed) the per-user directory for app data.

    Windows: %APPDATA%\\YouTubeWatchPredictor
    macOS/Linux: ~/.local/share/YouTubeWatchPredictor (XDG-ish fallback)
    """
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")

    path = Path(base) / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return app_data_dir() / "ytpredictor.db"


def model_path() -> Path:
    return app_data_dir() / "model.joblib"


def config_path() -> Path:
    return app_data_dir() / "config.json"
