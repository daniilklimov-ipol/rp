"""Application entry point: builds the QApplication and shows the window."""

import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from . import config
from .window import BrowserWindow


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)

    # Sharing GL contexts keeps QtWebEngine happy across multiple views.
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)

    app = QApplication(argv)
    app.setApplicationName(config.APP_NAME)

    window = BrowserWindow()

    # Any URLs passed on the command line open in tabs.
    for arg in argv[1:]:
        window.add_tab(url=arg)

    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
