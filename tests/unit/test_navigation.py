"""Unit tests for URL normalization and validation."""

from PySide6.QtCore import QUrl
from browser.core.navigation import is_valid_url, normalize_url


def test_normalize_empty_url():
    """Empty or whitespace-only input should normalize to about:blank."""
    assert normalize_url("") == QUrl("about:blank")
    assert normalize_url("   ") == QUrl("about:blank")


def test_normalize_standard_domain():
    """Domain names without scheme should default to https://."""
    url = normalize_url("example.com")
    assert url == QUrl("https://example.com")
    assert url.scheme() == "https"
    assert url.host() == "example.com"


def test_normalize_full_https_url():
    """Explicit HTTPS URLs should be preserved."""
    url = normalize_url("https://example.com/path?query=1")
    assert url == QUrl("https://example.com/path?query=1")
    assert url.scheme() == "https"


def test_normalize_http_url():
    """Explicit HTTP URLs should be preserved."""
    url = normalize_url("http://insecure.example.com")
    assert url == QUrl("http://insecure.example.com")
    assert url.scheme() == "http"


def test_normalize_localhost():
    """Localhost targets should default to http://."""
    url = normalize_url("localhost:8000")
    assert url == QUrl("http://localhost:8000")
    assert url.scheme() == "http"
    assert url.port() == 8000

    url_ip = normalize_url("127.0.0.1:3000")
    assert url_ip == QUrl("http://127.0.0.1:3000")


def test_normalize_file_and_about():
    """File and about schemes should be preserved."""
    assert normalize_url("about:blank") == QUrl("about:blank")
    assert normalize_url("file:///path/to/file.html") == QUrl("file:///path/to/file.html")


def test_is_valid_url():
    """Valid and invalid QUrls should be classified accurately."""
    assert is_valid_url(QUrl("https://example.com")) is True
    assert is_valid_url(QUrl("http://localhost:8000")) is True
    assert is_valid_url(QUrl("")) is False
