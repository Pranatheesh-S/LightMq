"""Create and inspect LightMq's shared persistent WebEngine profile."""

from __future__ import annotations

import re
from pathlib import Path

import PySide6
from PySide6.QtCore import QStandardPaths, qVersion
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineCore import QWebEngineProfile


class WebProfileManager:
    """Own the one disk-backed profile used by all regular browser windows."""

    PROFILE_NAME = "Default"
    _profile: QWebEngineProfile | None = None

    @classmethod
    def data_root(cls) -> Path:
        """Return the stable application data root for the current platform."""
        app = QApplication.instance()
        if app is not None:
            if not app.applicationName():
                app.setApplicationName("LightMq Browser")
            if not app.organizationName():
                app.setOrganizationName("LightMq")
        app_data = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppDataLocation
        )
        if not app_data:
            raise RuntimeError("Qt did not provide an application data directory")
        return Path(app_data) / "Browser" / "Profiles" / cls.PROFILE_NAME

    @classmethod
    def create_persistent_profile(
        cls,
        data_root: str | Path,
        parent: QApplication,
    ) -> QWebEngineProfile:
        """Create an isolated named persistent profile under ``data_root``.

        The caller owns the returned profile through ``parent``. This factory is
        also used by tests with temporary directories.
        """
        root = Path(data_root)
        storage_path = root / "Storage"
        cache_path = root / "Cache"
        storage_path.mkdir(parents=True, exist_ok=True)
        cache_path.mkdir(parents=True, exist_ok=True)

        profile = QWebEngineProfile(cls.PROFILE_NAME, parent)
        profile.setPersistentStoragePath(str(storage_path))
        profile.setCachePath(str(cache_path))
        profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
        )
        profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
        return profile

    @classmethod
    def default_profile(cls) -> QWebEngineProfile:
        """Return the shared regular profile, creating it once per app process."""
        if cls._profile is not None:
            return cls._profile
        app = QApplication.instance()
        if app is None:
            raise RuntimeError("QApplication must exist before creating the browser profile")
        cls._profile = cls.create_persistent_profile(cls.data_root(), app)
        return cls._profile

    @staticmethod
    def diagnostics(profile: QWebEngineProfile) -> dict[str, str]:
        """Return non-sensitive configuration and engine details for diagnostics."""
        user_agent = profile.httpUserAgent()
        match = re.search(r"Chrome/([0-9.]+)", user_agent)
        return {
            "profile_name": profile.storageName(),
            "off_the_record": str(profile.isOffTheRecord()),
            "persistent_storage_path": profile.persistentStoragePath(),
            "cache_path": profile.cachePath(),
            "cookie_policy": profile.persistentCookiesPolicy().name,
            "http_cache_type": profile.httpCacheType().name,
            "qt_webengine_version": qVersion(),
            "chromium_version": match.group(1) if match else "Unknown",
            "pyside6_version": PySide6.__version__,
        }
