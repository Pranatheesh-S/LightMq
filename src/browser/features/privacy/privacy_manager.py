"""Coordinate profile-owned cookie, cache, and permission data operations."""

from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Signal
from PySide6.QtWebEngineCore import QWebEnginePermission, QWebEngineProfile

from browser.features.privacy.cache_manager import CacheManager
from browser.features.privacy.cookie_manager import CookieManager
from browser.security.permission_policy import PermissionPolicy


@dataclass(frozen=True)
class PermissionInfo:
    """Display-safe permission status and an opaque Qt handle for reset."""

    origin: str
    capability: str
    decision: str
    persistence: str
    _handle: QWebEnginePermission = field(repr=False, compare=False)


class PrivacyManager(QObject):
    """Provide privacy operations for one existing WebEngine profile."""

    permissions_changed = Signal()

    def __init__(self, profile: QWebEngineProfile, parent: QObject | None = None):
        super().__init__(parent)
        self.profile = profile
        self.cookies = CookieManager(profile, self)
        self.cache = CacheManager(profile, self)

    def permissions(self) -> list[PermissionInfo]:
        """Return permission metadata exposed by Qt without UI-side WebEngine access."""
        records = []
        for permission in self.profile.listAllPermissions():
            if not permission.isValid() or permission.state().name not in ("Granted", "Denied"):
                continue
            records.append(PermissionInfo(
                origin=permission.origin().toString(),
                capability=PermissionPolicy.capability_name(permission) or permission.permissionType().name,
                decision=permission.state().name,
                persistence="Persistent" if permission.isPersistent() else "In memory",
                _handle=permission,
            ))
        return records

    def reset_permission(self, record: PermissionInfo) -> bool:
        """Reset one Qt-stored decision using its opaque display record."""
        permission = record._handle
        if not permission.isValid():
            return False
        permission.reset()
        self.permissions_changed.emit()
        return True

    def reset_permissions(self) -> int:
        """Reset every currently stored permission decision and return its count."""
        permissions = self.permissions()
        reset_count = 0
        for record in permissions:
            permission = record._handle
            if permission.isValid():
                permission.reset()
                reset_count += 1
        self.permissions_changed.emit()
        return reset_count
