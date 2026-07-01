# PyBrowser

A minimal but genuinely functional tabbed web browser written in Python on top
of **PyQt5** and the **QtWebEngine** (Chromium) rendering engine.

## Features

- Full Chromium rendering via QtWebEngine — real, modern web pages.
- Multiple **tabs**: open, close, reorder, and middle-click / popup links open
  in new tabs automatically.
- **Address bar** that is smart about input: type a URL to navigate, or type
  anything else to run a DuckDuckGo search.
- Navigation toolbar: back, forward, reload, home.
- **Bookmarks** with a Bookmarks menu, persisted to disk.
- **History** recording (capped), persisted to disk.
- Keyboard shortcuts: `Ctrl+T` new tab, `Ctrl+W` close tab, `Ctrl+L` focus
  address bar, `Ctrl+R` reload, `Alt+Left/Right` back/forward, `Ctrl+D`
  bookmark, `Ctrl+Q` quit.

## Installation

```bash
pip install -r requirements.txt
```

> QtWebEngine requires a graphical environment (an X server / Wayland). On a
> headless machine, run under a virtual display, e.g. `xvfb-run python main.py`.

## Usage

```bash
python main.py                 # open the home page
python main.py https://python.org example.com   # open URLs in tabs
```

## Project layout

```
main.py               # thin launcher
browser/
  app.py              # QApplication setup + entry point
  window.py           # main window: tabs, toolbar, menus, bookmarks/history
  tab.py              # WebView / tab widget (handles popups → new tabs)
  utils.py            # URL-vs-search parsing helpers
  config.py           # constants + JSON persistence helpers
tests/
  test_utils.py       # unit tests for the URL parsing logic
```

## Configuration

User data is stored under `~/.config/pybrowser/`:

- `bookmarks.json`
- `history.json`

Edit `browser/config.py` to change the home page or default search engine.

## Running the tests

```bash
pip install -r requirements.txt pytest
pytest
```
