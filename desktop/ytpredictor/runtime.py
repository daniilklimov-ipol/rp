"""Run the FastAPI server in a background thread, controllable from the GUI."""

from __future__ import annotations

import threading

import uvicorn

from .config import Settings
from .server import create_app


class ServerThread(threading.Thread):
    def __init__(self, settings: Settings, log_callback=None):
        super().__init__(daemon=True)
        self.settings = settings
        self.log_callback = log_callback
        app = create_app(settings)
        config = uvicorn.Config(
            app,
            host=settings.server_host,
            port=settings.server_port,
            log_level="info",
            access_log=False,
        )
        self.server = uvicorn.Server(config)

    def run(self) -> None:
        self.server.run()

    def stop(self) -> None:
        self.server.should_exit = True
