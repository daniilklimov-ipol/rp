"""Small JSON-backed settings store: YouTube API key, server port, etc."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass

from .paths import config_path

_lock = threading.Lock()


@dataclass
class Settings:
    youtube_api_key: str = ""
    server_host: str = "127.0.0.1"
    server_port: int = 8765
    interesting_threshold: float = 60.0  # % completion considered "interesting"
    min_training_samples: int = 15


def load_settings() -> Settings:
    path = config_path()
    if not path.exists():
        return Settings()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return Settings()
    defaults = asdict(Settings())
    defaults.update({k: v for k, v in data.items() if k in defaults})
    return Settings(**defaults)


def save_settings(settings: Settings) -> None:
    path = config_path()
    with _lock:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(asdict(settings), fh, indent=2)
