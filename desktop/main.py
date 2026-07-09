#!/usr/bin/env python3
"""Launch the YouTube Watch-Completion Predictor desktop app.

Usage:
    python main.py            # GUI + local server (default)
    python main.py --headless # local server only, no GUI (e.g. run at login)
"""

from __future__ import annotations

import sys


def main() -> int:
    if "--headless" in sys.argv:
        from ytpredictor.config import load_settings
        from ytpredictor.runtime import ServerThread

        settings = load_settings()
        server = ServerThread(settings)
        print(f"Serving on http://{settings.server_host}:{settings.server_port} (Ctrl+C to stop)")
        try:
            server.run()  # blocking
        except KeyboardInterrupt:
            server.stop()
        return 0

    from ytpredictor.gui import main as gui_main

    return gui_main()


if __name__ == "__main__":
    sys.exit(main())
