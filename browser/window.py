"""The main browser window: tab bar, toolbar, address bar and menus."""

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QAction,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStatusBar,
    QTabWidget,
    QToolBar,
)

from . import config, utils
from .tab import BrowserTab


class BrowserWindow(QMainWindow):
    """Top-level window that manages a set of tabs and shared navigation UI."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(config.APP_NAME)
        self.resize(1200, 800)

        self.bookmarks = config.load_json(config.BOOKMARKS_FILE, [])
        self.history = config.load_json(config.HISTORY_FILE, [])

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.setCentralWidget(self.tabs)

        self.setStatusBar(QStatusBar(self))

        self._build_toolbar()
        self._build_menus()

        self.add_tab()

    # ------------------------------------------------------------------ UI
    def _build_toolbar(self):
        nav = QToolBar("Navigation")
        nav.setMovable(False)
        self.addToolBar(nav)

        self.back_action = QAction("◀", self)
        self.back_action.setToolTip("Back")
        self.back_action.triggered.connect(lambda: self._current().back())
        nav.addAction(self.back_action)

        self.forward_action = QAction("▶", self)
        self.forward_action.setToolTip("Forward")
        self.forward_action.triggered.connect(lambda: self._current().forward())
        nav.addAction(self.forward_action)

        self.reload_action = QAction("⟳", self)
        self.reload_action.setToolTip("Reload")
        self.reload_action.triggered.connect(lambda: self._current().reload())
        nav.addAction(self.reload_action)

        home_action = QAction("⌂", self)
        home_action.setToolTip("Home")
        home_action.triggered.connect(self.go_home)
        nav.addAction(home_action)

        self.address_bar = QLineEdit()
        self.address_bar.setPlaceholderText("Search or enter address")
        self.address_bar.setClearButtonEnabled(True)
        self.address_bar.returnPressed.connect(self.navigate_to_address)
        nav.addWidget(self.address_bar)

        star_action = QAction("★", self)
        star_action.setToolTip("Bookmark this page")
        star_action.triggered.connect(self.bookmark_current)
        nav.addAction(star_action)

        new_tab_action = QAction("＋", self)
        new_tab_action.setToolTip("New tab")
        new_tab_action.triggered.connect(lambda: self.add_tab())
        nav.addAction(new_tab_action)

    def _build_menus(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")
        self._add_action(file_menu, "New Tab", self.add_tab, "Ctrl+T")
        self._add_action(file_menu, "Close Tab", self.close_current_tab, "Ctrl+W")
        file_menu.addSeparator()
        self._add_action(file_menu, "Quit", self.close, "Ctrl+Q")

        nav_menu = menubar.addMenu("&Navigation")
        self._add_action(nav_menu, "Back", lambda: self._current().back(), "Alt+Left")
        self._add_action(nav_menu, "Forward", lambda: self._current().forward(), "Alt+Right")
        self._add_action(nav_menu, "Reload", lambda: self._current().reload(), "Ctrl+R")
        self._add_action(nav_menu, "Home", self.go_home, "Alt+Home")
        self._add_action(nav_menu, "Focus Address Bar", self._focus_address, "Ctrl+L")

        self.bookmarks_menu = menubar.addMenu("&Bookmarks")
        self._rebuild_bookmarks_menu()

        help_menu = menubar.addMenu("&Help")
        self._add_action(help_menu, "About", self.show_about)

    def _add_action(self, menu, text, slot, shortcut=None):
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    # --------------------------------------------------------------- tabs
    def add_tab(self, url=None, view=None):
        """Add a new tab; ``view`` lets popups reuse an existing WebView."""
        if view is None:
            view = BrowserTab(self, url)
        index = self.tabs.addTab(view, "New Tab")
        self.tabs.setCurrentIndex(index)

        view.urlChanged.connect(lambda qurl, v=view: self._on_url_changed(v, qurl))
        view.loadFinished.connect(lambda ok, v=view: self._on_load_finished(v, ok))
        view.titleChanged.connect(lambda title, v=view: self._on_title_changed(v, title))
        view.createTabRequested.connect(lambda new_view: self.add_tab(view=new_view))
        return view

    def close_tab(self, index):
        if self.tabs.count() <= 1:
            # Keep at least one tab; reset it to the home page instead.
            self._current().load(QUrl(config.HOME_URL))
            return
        widget = self.tabs.widget(index)
        self.tabs.removeTab(index)
        widget.deleteLater()

    def close_current_tab(self):
        self.close_tab(self.tabs.currentIndex())

    def _current(self):
        return self.tabs.currentWidget()

    def on_tab_changed(self, _index):
        view = self._current()
        if view is not None:
            self._sync_address(view.url())
            self._update_nav_actions(view)

    # ---------------------------------------------------------- navigation
    def navigate_to_address(self):
        url = utils.url_from_input(self.address_bar.text())
        self._current().load(url)

    def go_home(self):
        self._current().load(QUrl(config.HOME_URL))

    def _focus_address(self):
        self.address_bar.setFocus()
        self.address_bar.selectAll()

    def _sync_address(self, qurl):
        text = qurl.toString()
        if text == "about:blank":
            text = ""
        self.address_bar.setText(text)
        self.address_bar.setCursorPosition(0)

    def _update_nav_actions(self, view):
        self.back_action.setEnabled(view.history().canGoBack())
        self.forward_action.setEnabled(view.history().canGoForward())

    # ------------------------------------------------------------- signals
    def _on_url_changed(self, view, qurl):
        if view is self._current():
            self._sync_address(qurl)
            self._update_nav_actions(view)

    def _on_load_finished(self, view, ok):
        if ok:
            self._record_history(view.url(), view.title())
        if view is self._current():
            self._update_nav_actions(view)

    def _on_title_changed(self, view, title):
        index = self.tabs.indexOf(view)
        if index != -1:
            label = (title or "New Tab")
            self.tabs.setTabText(index, label[:24])
            self.tabs.setTabToolTip(index, title)
        if view is self._current():
            self.setWindowTitle(f"{title} — {config.APP_NAME}" if title else config.APP_NAME)

    # ----------------------------------------------------------- bookmarks
    def bookmark_current(self):
        view = self._current()
        url = view.url().toString()
        if not url or url == "about:blank":
            return
        title = view.title() or utils.pretty_host(url)
        if any(b["url"] == url for b in self.bookmarks):
            self.statusBar().showMessage("Already bookmarked", 2000)
            return
        self.bookmarks.append({"title": title, "url": url})
        config.save_json(config.BOOKMARKS_FILE, self.bookmarks)
        self._rebuild_bookmarks_menu()
        self.statusBar().showMessage("Bookmarked", 2000)

    def _rebuild_bookmarks_menu(self):
        menu = self.bookmarks_menu
        menu.clear()
        self._add_action(menu, "Bookmark This Page", self.bookmark_current, "Ctrl+D")
        if self.bookmarks:
            menu.addSeparator()
            for bm in self.bookmarks:
                action = QAction(bm["title"][:60] or bm["url"], self)
                action.setToolTip(bm["url"])
                action.triggered.connect(
                    lambda _checked, u=bm["url"]: self._current().load(QUrl(u))
                )
                menu.addAction(action)
            menu.addSeparator()
            self._add_action(menu, "Clear Bookmarks", self.clear_bookmarks)

    def clear_bookmarks(self):
        self.bookmarks = []
        config.save_json(config.BOOKMARKS_FILE, self.bookmarks)
        self._rebuild_bookmarks_menu()

    # ------------------------------------------------------------- history
    def _record_history(self, qurl, title):
        url = qurl.toString()
        if not url or url == "about:blank":
            return
        # Avoid consecutive duplicates.
        if self.history and self.history[-1].get("url") == url:
            return
        self.history.append({"url": url, "title": title or ""})
        if len(self.history) > config.MAX_HISTORY:
            self.history = self.history[-config.MAX_HISTORY :]
        config.save_json(config.HISTORY_FILE, self.history)

    # --------------------------------------------------------------- about
    def show_about(self):
        QMessageBox.about(
            self,
            f"About {config.APP_NAME}",
            f"<h3>{config.APP_NAME}</h3>"
            "<p>A minimal tabbed web browser built with PyQt5 and the "
            "QtWebEngine (Chromium) rendering engine.</p>",
        )
