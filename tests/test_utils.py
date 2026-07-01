"""Unit tests for browser.utils URL/search parsing.

These only need PyQt5's non-GUI QtCore (QUrl); no display is required.
"""

import pytest

pytest.importorskip("PyQt5.QtCore")

from browser import config, utils  # noqa: E402


@pytest.mark.parametrize(
    "text",
    [
        "http://example.com",
        "https://example.com/path",
        "example.com",
        "sub.example.co.uk/x",
        "localhost:8000",
        "file:///tmp/page.html",
        "about:blank",
    ],
)
def test_looks_like_url_true(text):
    assert utils.looks_like_url(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "",
        "hello world",
        "what is python",
        "python programming tutorial",
        ".hidden",
    ],
)
def test_looks_like_url_false(text):
    assert utils.looks_like_url(text) is False


def test_url_from_input_adds_scheme():
    url = utils.url_from_input("example.com")
    assert url.toString() == "http://example.com"


def test_url_from_input_keeps_scheme():
    url = utils.url_from_input("https://example.com/a")
    assert url.toString() == "https://example.com/a"


def test_url_from_input_search():
    url = utils.url_from_input("hello world")
    text = url.toString()
    assert text.startswith("https://duckduckgo.com/?q=")
    assert "hello" in text and "world" in text


def test_pretty_host():
    assert utils.pretty_host("https://example.com/page") == "example.com"


def test_config_roundtrip(tmp_path):
    path = tmp_path / "data.json"
    payload = [{"url": "https://a.com", "title": "A"}]
    config.save_json(str(path), payload)
    assert config.load_json(str(path), []) == payload


def test_config_load_missing_returns_default():
    assert config.load_json("/nonexistent/path/xyz.json", ["fallback"]) == ["fallback"]
