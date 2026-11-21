"""Safe, profile-scoped handling for Qt WebEngine permission requests."""

from dataclasses import dataclass
import weakref

import shiboken6
from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEnginePermission

from browser.security.permission_policy import PermissionPolicy


@dataclass
class PendingPermission:
    """A live permission request and the page/origin context that created it."""

    key: tuple[int, str, int]
    page_ref: weakref.ReferenceType[QWebEnginePage]
    permission: QWebEnginePermission
    top_origin: str
    origin: str
    capability: str


class PermissionRequestHandler(QObject):
    """Prompt through signals and deny stale, unsupported, or insecure requests."""

    permission_requested = Signal(object)
    request_cancelled = Signal(object)
    permissions_changed = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._attached_pages: set[int] = set()
        self._pending: dict[tuple[int, str, int], PendingPermission] = {}

    @staticmethod
    def origin_key(url: QUrl) -> str:
        """Return the URL origin without path, query, or fragment data."""
        if not url.isValid() or not url.scheme() or not url.host():
            return ""
        port = url.port()
        default_port = (url.scheme().lower() == "https" and port in (-1, 443)) or (
            url.scheme().lower() == "http" and port in (-1, 80)
        )
        suffix = "" if default_port else f":{port}"
        return f"{url.scheme().lower()}://{url.host().lower()}{suffix}"

    def attach_page(self, page: QWebEnginePage) -> None:
        """Connect one page's permission lifecycle exactly once."""
        page_id = id(page)
        if page_id in self._attached_pages:
            return
        self._attached_pages.add(page_id)
        page_ref = weakref.ref(page)
        permission_signal = getattr(page, "permissionRequested", None)
        if permission_signal is None:
            return
        permission_signal.connect(lambda permission, ref=page_ref: self._on_request(ref, permission))
        page.urlChanged.connect(lambda url, ref=page_ref: self._on_url_changed(ref, url))
        page.destroyed.connect(lambda _obj=None, pid=page_id: self._on_page_destroyed(pid))

    def _on_request(
        self, page_ref: weakref.ReferenceType[QWebEnginePage], permission: QWebEnginePermission,
    ) -> None:
        """Validate a request and notify the owning window for a user decision."""
        page = page_ref()
        if page is None or not shiboken6.isValid(page):
            self._deny(permission)
            return
        if not PermissionPolicy.is_request_allowed_to_prompt(permission):
            self._deny(permission)
            return
        origin = self.origin_key(permission.origin())
        page_id = id(page)
        permission_type = int(permission.permissionType().value)
        key = (page_id, origin, permission_type)
        if key in self._pending:
            self._deny(permission)
            return
        request = PendingPermission(
            key=key,
            page_ref=page_ref,
            permission=permission,
            top_origin=self.origin_key(page.url()),
            origin=permission.origin().toString(),
            capability=PermissionPolicy.capability_name(permission) or "",
        )
        self._pending[key] = request
        self.permission_requested.emit(request)

    def resolve(self, request: PendingPermission, allow: bool) -> bool:
        """Apply a user's choice if the original page and permission are still live."""
        if self._pending.get(request.key) is not request:
            return False
        self._pending.pop(request.key, None)
        page = request.page_ref()
        try:
            live = (
                page is not None
                and shiboken6.isValid(page)
                and request.permission.isValid()
                and self.origin_key(page.url()) == request.top_origin
            )
            if not live:
                self._deny(request.permission)
                self.request_cancelled.emit(request)
                return False
            if allow:
                request.permission.grant()
            else:
                request.permission.deny()
        except RuntimeError:
            self._deny(request.permission)
            self.request_cancelled.emit(request)
            return False
        self.permissions_changed.emit()
        return True

    def cancel_for_page(self, page: QWebEnginePage) -> None:
        """Deny and dismiss outstanding requests before a page is closed."""
        self._on_page_destroyed(id(page))

    def _on_url_changed(
        self, page_ref: weakref.ReferenceType[QWebEnginePage], url: QUrl,
    ) -> None:
        """Cancel requests if the requesting page navigates to a different origin."""
        page = page_ref()
        if page is None:
            return
        current_origin = self.origin_key(url)
        for request in tuple(self._pending.values()):
            if request.key[0] == id(page) and request.top_origin != current_origin:
                self._cancel_request(request)

    def _on_page_destroyed(self, page_id: int) -> None:
        """Deny any unresolved request associated with a destroyed page."""
        self._attached_pages.discard(page_id)
        for request in tuple(self._pending.values()):
            if request.key[0] == page_id:
                self._cancel_request(request)

    def _cancel_request(self, request: PendingPermission) -> None:
        """Remove a request, deny it when possible, and close its prompt."""
        if self._pending.pop(request.key, None) is not None:
            self._deny(request.permission)
            self.request_cancelled.emit(request)

    @staticmethod
    def _deny(permission: QWebEnginePermission) -> None:
        """Deny an unresolved request while tolerating an expired Qt wrapper."""
        try:
            if permission.isValid():
                permission.deny()
        except RuntimeError:
            pass
