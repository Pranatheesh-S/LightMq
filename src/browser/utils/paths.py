"""Filesystem path resolvers for LightMq's user-specific application data."""

from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication


def resource_path(relative: str) -> Path:
    """Resolve bundled read-only assets in development and frozen distributions."""
    root = Path(__file__).resolve().parents[1]
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Resource must remain inside the browser package")
    return path


def app_data_directory() -> Path:
    """Return the stable per-user application-data directory."""
    app = QApplication.instance()
    if app is not None:
        if not app.applicationName():
            app.setApplicationName("LightMq Browser")
        if not app.organizationName():
            app.setOrganizationName("LightMq")
    location = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppDataLocation
    )
    if not location:
        raise RuntimeError("Qt did not provide an application data directory")
    return Path(location)


def sessions_directory() -> Path:
    """Return and create the directory used for local session metadata."""
    path = app_data_directory() / "Sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path
