"""A single browser tab wrapping a QWebEngineView."""

from PyQt5.QtCore import QUrl, pyqtSignal
from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineView

from . import config


class WebView(QWebEngineView):
    """A web view that opens ``target=_blank`` / popup links in a new tab."""

    # Emitted when the page requests a brand new view (e.g. window.open).
    createTabRequested = pyqtSignal(QWebEngineView)

    def createWindow(self, _window_type):
        view = WebView(self.parent())
        self.createTabRequested.emit(view)
        return view


class BrowserTab(WebView):
    """A WebView pre-configured with the app's default home page."""

    def __init__(self, parent=None, url=None):
        super().__init__(parent)
        self.load(QUrl(url or config.HOME_URL))

    def current_title(self):
        return self.title() or "New Tab"


__all__ = ["BrowserTab", "WebView", "QWebEnginePage"]
