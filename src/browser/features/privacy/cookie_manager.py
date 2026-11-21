"""Asynchronous cookie inventory and deletion for a WebEngine profile."""

import logging
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QNetworkCookie
from PySide6.QtWebEngineCore import QWebEngineProfile

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CookieInfo:
    """Safe cookie metadata for UI display, excluding the cookie value."""

    name: str
    domain: str
    path: str
    expires: str
    lifetime: str
    secure: bool
    http_only: bool
    key: tuple[bytes, str, str]


class CookieManager(QObject):
    """Expose cookie metadata and request deletions without retaining values."""

    cookies_changed = Signal()
    operation_requested = Signal(str)

    def __init__(self, profile: QWebEngineProfile, parent: QObject | None = None):
        super().__init__(parent)
        self._store = profile.cookieStore()
        self._cookies: dict[tuple[bytes, str, str], QNetworkCookie] = {}
        self._store.cookieAdded.connect(self._on_cookie_added)
        self._store.cookieRemoved.connect(self._on_cookie_removed)

    @staticmethod
    def _key(cookie: QNetworkCookie) -> tuple[bytes, str, str]:
        """Return a non-secret identity for a cookie."""
        return bytes(cookie.name()), cookie.domain(), cookie.path()

    def cookies(self) -> list[CookieInfo]:
        """Return display-safe cookie metadata without exposing cookie values."""
        records = []
        for key, cookie in self._cookies.items():
            session = cookie.isSessionCookie()
            expiry = cookie.expirationDate()
            records.append(CookieInfo(
                name=bytes(cookie.name()).decode("utf-8", "replace"),
                domain=cookie.domain(),
                path=cookie.path(),
                expires="Session" if session else expiry.toLocalTime().toString("yyyy-MM-dd HH:mm:ss"),
                lifetime="Session" if session else "Persistent",
                secure=cookie.isSecure(),
                http_only=cookie.isHttpOnly(),
                key=key,
            ))
        return records

    def load_all(self) -> None:
        """Request an asynchronous inventory of all cookies in the profile."""
        self._cookies.clear()
        self.cookies_changed.emit()
        self._store.loadAllCookies()

    def delete_cookie(self, cookie_info: CookieInfo) -> bool:
        """Request deletion of one cookie; completion arrives through cookieRemoved."""
        cookie = self._cookies.get(cookie_info.key)
        if cookie is None:
            return False
        self._store.deleteCookie(cookie)
        self.operation_requested.emit("Cookie deletion requested; waiting for WebEngine cookie events.")
        return True

    def delete_session_cookies(self) -> None:
        """Request deletion of session cookies only."""
        self._store.deleteSessionCookies()
        self.operation_requested.emit("Session-cookie deletion requested; waiting for WebEngine cookie events.")

    def delete_all_cookies(self) -> None:
        """Request deletion of all cookies in the profile."""
        self._store.deleteAllCookies()
        self.operation_requested.emit("Cookie deletion requested; waiting for WebEngine cookie events.")

    def _on_cookie_added(self, cookie: QNetworkCookie) -> None:
        """Update the in-memory metadata inventory without logging cookie values."""
        self._cookies[self._key(cookie)] = QNetworkCookie(cookie)
        self.cookies_changed.emit()

    def _on_cookie_removed(self, cookie: QNetworkCookie) -> None:
        """Remove deleted cookie metadata from the inventory."""
        self._cookies.pop(self._key(cookie), None)
        self.cookies_changed.emit()
