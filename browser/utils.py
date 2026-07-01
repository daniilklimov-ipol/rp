"""Small helpers shared across the browser UI."""

from urllib.parse import urlparse

from PyQt5.QtCore import QUrl

from . import config


def looks_like_url(text):
    """Heuristically decide whether ``text`` is a URL rather than a search."""
    text = text.strip()
    if not text or " " in text:
        return False
    if text.startswith(("http://", "https://", "file://", "about:")):
        return True
    # A dotted token with no spaces (example.com, localhost:8000/path) is a URL.
    if "." in text and not text.startswith("."):
        return True
    if text.startswith("localhost"):
        return True
    return False


def url_from_input(text):
    """Turn address-bar text into a :class:`QUrl` (URL or search query)."""
    text = text.strip()
    if looks_like_url(text):
        if "://" not in text:
            text = "http://" + text
        return QUrl(text)
    query = QUrl.toPercentEncoding(text).data().decode("ascii")
    return QUrl(config.SEARCH_URL.format(query=query))


def pretty_host(url):
    """Return a short, human-friendly label for a QUrl (its host or scheme)."""
    if isinstance(url, QUrl):
        url = url.toString()
    parsed = urlparse(url)
    return parsed.netloc or parsed.scheme or url
