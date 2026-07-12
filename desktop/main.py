#!/usr/bin/env python3
"""Launch the YouTube Watch-Completion Predictor desktop app.

Usage:
    python main.py             # GUI + local server (default)
    python main.py --headless  # local server only, no GUI (e.g. run at login)
    python main.py --selfcheck # import everything and exit; used by CI to
                                # smoke-test a frozen .exe before shipping it
"""

from __future__ import annotations

import sys


def _selfcheck() -> int:
    # A windowed (console=False) frozen exe shows a blocking "unhandled
    # exception" dialog instead of printing a traceback, which would hang a
    # CI runner forever. Catch everything ourselves, write it somewhere
    # readable, and exit cleanly instead of letting it bubble up.
    try:
        import ytpredictor.server  # noqa: F401 - exercises the sklearn/scipy import chain
    except Exception:
        import traceback

        report = traceback.format_exc()
        try:
            with open("selfcheck_error.log", "w", encoding="utf-8") as fh:
                fh.write(report)
        except OSError:
            pass
        print(report, file=sys.stderr)
        return 1

    print("selfcheck OK")
    return 0


def main() -> int:
    if "--selfcheck" in sys.argv:
        return _selfcheck()

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
