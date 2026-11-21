"""Unit checks for safe permission policy and profile privacy coordinators."""

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import QNetworkCookie
from PySide6.QtWebEngineCore import QWebEnginePermission
from browser.features.privacy.cache_manager import CacheManager
from browser.features.privacy.cookie_manager import CookieManager
from browser.security.permission_policy import PermissionPolicy
from browser.webengine.permissions import PermissionRequestHandler


class _CookieStore(QObject):
    """Small signal-compatible cookie-store test double."""

    cookieAdded = Signal(object)
    cookieRemoved = Signal(object)

    def __init__(self):
        super().__init__()
        self.deleted: list[tuple[QNetworkCookie, QUrl]] = []
        self.deleted_all = 0
        self.deleted_session = 0

    def loadAllCookies(self):
        """No-op: tests inject cookie events explicitly."""

    def deleteCookie(self, cookie, origin=QUrl()):
        """Record an individual deletion request."""
        self.deleted.append((cookie, origin))

    def deleteAllCookies(self):
        """Record a full deletion request."""
        self.deleted_all += 1

    def deleteSessionCookies(self):
        """Record a session-cookie deletion request."""
        self.deleted_session += 1


class _Profile(QObject):
    """Expose the cookieStore method needed by CookieManager."""

    def __init__(self):
        super().__init__()
        self.store = _CookieStore()

    def cookieStore(self):
        """Return the test cookie store."""
        return self.store


class _CacheProfile(QObject):
    """Signal-compatible profile test double for cache completion."""

    clearHttpCacheCompleted = Signal()

    def __init__(self):
        super().__init__()
        self.clear_requests = 0

    def clearHttpCache(self):
        """Record a cache clear without completing it automatically."""
        self.clear_requests += 1


class _PermissionPage(QObject):
    """Signal-compatible page test double with a controllable top-level URL."""

    permissionRequested = Signal(object)
    urlChanged = Signal(QUrl)

    def __init__(self, url: str):
        super().__init__()
        self.current_url = QUrl(url)

    def url(self):
        """Return the current top-level page URL."""
        return self.current_url

    def navigate(self, url: str):
        """Change the top-level origin and emit Qt's navigation notification."""
        self.current_url = QUrl(url)
        self.urlChanged.emit(self.current_url)


class _Permission:
    """Minimal live permission request double."""

    def __init__(self, origin: str):
        self._origin = QUrl(origin)
        self._type = QWebEnginePermission.PermissionType.MediaAudioCapture
        self.valid = True
        self.decision = ""

    def isValid(self):
        """Return whether the test request remains live."""
        return self.valid

    def permissionType(self):
        """Return the requested Qt permission category."""
        return self._type

    def origin(self):
        """Return the actual requesting origin."""
        return self._origin

    def grant(self):
        """Record an allow decision."""
        self.decision = "granted"
        self.valid = False

    def deny(self):
        """Record a deny decision."""
        self.decision = "denied"
        self.valid = False


def test_permission_policy_only_prompts_for_supported_secure_origins():
    """Permission requests are limited to secure web origins and known Qt types."""
    assert PermissionPolicy.origin_is_secure(QUrl("https://media.example/path"))
    assert PermissionPolicy.origin_is_secure(QUrl("http://localhost:8000"))
    assert not PermissionPolicy.origin_is_secure(QUrl("http://media.example"))
    assert not PermissionPolicy.origin_is_secure(QUrl("file:///tmp/page.html"))
    assert PermissionPolicy._CAPABILITIES["MediaAudioCapture"] == "microphone"
    assert PermissionPolicy._CAPABILITIES["Notifications"] == "desktop notifications"


def test_cookie_manager_tracks_metadata_and_requests_supported_deletions():
    """Cookie values remain internal while deletion uses Qt's asynchronous APIs."""
    profile = _Profile()
    manager = CookieManager(profile)
    cookie = QNetworkCookie(b"session_id", b"private-value")
    cookie.setDomain("example.test")
    cookie.setPath("/")
    profile.store.cookieAdded.emit(cookie)

    listed = manager.cookies()
    assert len(listed) == 1
    assert listed[0].name == "session_id"
    assert listed[0].domain == "example.test"
    assert not hasattr(listed[0], "value")

    manager.delete_cookie(listed[0])
    manager.delete_session_cookies()
    manager.delete_all_cookies()
    assert len(profile.store.deleted) == 1
    assert profile.store.deleted[0][0].domain() == "example.test"
    assert profile.store.deleted[0][1].isEmpty()
    assert profile.store.deleted_session == 1
    assert profile.store.deleted_all == 1

    profile.store.cookieRemoved.emit(cookie)
    assert manager.cookies() == []


def test_cache_manager_reports_completion_only_after_profile_signal():
    """HTTP cache clearing remains pending until Qt emits its completion signal."""
    profile = _CacheProfile()
    manager = CacheManager(profile)
    events: list[str] = []
    manager.clear_started.connect(lambda: events.append("started"))
    manager.clear_completed.connect(lambda: events.append("completed"))

    assert manager.clear() is True
    assert manager.clear() is False
    assert events == ["started"]
    profile.clearHttpCacheCompleted.emit()
    assert events == ["started", "completed"]
    assert manager.clear() is True


def test_permission_handler_grants_by_actual_origin_and_cancels_stale_requests():
    """Permission decisions use request origin and deny after top-level navigation."""
    page = _PermissionPage("https://top.example/start")
    handler = PermissionRequestHandler()
    handler.attach_page(page)
    requests = []
    cancelled = []
    handler.permission_requested.connect(requests.append)
    handler.request_cancelled.connect(cancelled.append)

    allowed = _Permission("https://embedded.example")
    page.permissionRequested.emit(allowed)
    assert len(requests) == 1
    assert requests[0].permission.origin().host() == "embedded.example"
    assert handler.resolve(requests[0], True) is True
    assert allowed.decision == "granted"

    stale = _Permission("https://embedded.example")
    page.permissionRequested.emit(stale)
    page.navigate("https://different.example/page")
    assert stale.decision == "denied"
    assert len(cancelled) == 1


def test_permission_handler_denies_insecure_origins_and_suppresses_duplicate_prompts():
    """Insecure requests are blocked and duplicate requests do not create prompts."""
    page = _PermissionPage("https://top.example/")
    handler = PermissionRequestHandler()
    handler.attach_page(page)
    requests = []
    handler.permission_requested.connect(requests.append)

    insecure = _Permission("http://untrusted.example")
    page.permissionRequested.emit(insecure)
    assert insecure.decision == "denied"
    assert requests == []

    first = _Permission("https://top.example")
    duplicate = _Permission("https://top.example")
    page.permissionRequested.emit(first)
    page.permissionRequested.emit(duplicate)
    assert len(requests) == 1
    assert duplicate.decision == "denied"
    assert handler.resolve(requests[0], False) is True
    assert first.decision == "denied"
