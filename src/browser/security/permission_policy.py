"""Safe capability names and origin checks for website permission requests."""

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineCore import QWebEnginePermission


class PermissionPolicy:
    """Map supported Qt permission types and allow only secure web origins."""

    _CAPABILITIES = {
        "MediaAudioCapture": "microphone",
        "MediaVideoCapture": "camera",
        "MediaAudioVideoCapture": "camera and microphone",
        "DesktopVideoCapture": "screen sharing",
        "DesktopAudioVideoCapture": "screen and audio sharing",
        "MouseLock": "mouse lock",
        "Notifications": "desktop notifications",
        "Geolocation": "location",
        "ClipboardReadWrite": "clipboard access",
        "LocalFontsAccess": "local fonts",
    }

    @classmethod
    def capability_name(cls, permission: QWebEnginePermission) -> str | None:
        """Return a user-facing name for a supported permission, if any."""
        enum_name = getattr(permission.permissionType(), "name", "")
        name = enum_name.removeprefix("PermissionType")
        return cls._CAPABILITIES.get(name)

    @staticmethod
    def origin_is_secure(origin: QUrl) -> bool:
        """Allow HTTPS origins and loopback HTTP origins only."""
        if not origin.isValid() or not origin.host():
            return False
        scheme = origin.scheme().lower()
        host = origin.host().lower().rstrip(".")
        if scheme == "https":
            return True
        return scheme == "http" and host in {"localhost", "127.0.0.1", "::1"}

    @classmethod
    def is_request_allowed_to_prompt(cls, permission: QWebEnginePermission) -> bool:
        """Check that a request is live, supported, and has a secure origin."""
        try:
            return (
                permission.isValid()
                and cls.capability_name(permission) is not None
                and cls.origin_is_secure(permission.origin())
            )
        except RuntimeError:
            return False
