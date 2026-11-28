"""Coordinate Qt WebEngine's profile-scoped extension manager safely."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote

from PySide6.QtCore import QObject, QSettings, QTimer, Signal
from PySide6.QtWebEngineCore import QWebEngineExtensionInfo, QWebEngineProfile

from browser.features.extensions.package_inspector import (
    ExtensionPackage,
    inspect_extension_package,
    read_installed_manifest,
)

if TYPE_CHECKING:
    from browser.features.extensions.extension_diagnostics import ExtensionDiagnostics


ENABLED_STATES_KEY = "extensions/enabled_states"


@dataclass
class _PendingOperation:
    """One in-flight manager request; Qt completion signals carry no token."""

    kind: str
    source_path: str = ""
    extension_id: str = ""
    enable_after: bool = False
    package: ExtensionPackage | None = None


class ExtensionController(QObject):
    """Expose real persistent-profile extension operations to native UI."""

    extensions_changed = Signal()
    operation_finished = Signal(str, str, str, bool)

    # This installed Qt 6.12 runtime terminates natively when setExtensionEnabled
    # is called. Keep this fail-closed until the exact runtime is retested.
    EXTENSION_EXECUTION_BLOCKED = True

    _shared_by_profile: dict[int, tuple[QWebEngineProfile, "ExtensionController"]] = {}

    def __init__(
        self,
        profile: QWebEngineProfile,
        settings: QSettings,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        if profile.isOffTheRecord():
            raise ValueError("Qt WebEngine does not support extensions in Incognito profiles.")
        self.profile = profile
        self.settings = settings
        self.manager = profile.extensionManager()
        self.extension_execution_blocked = self.EXTENSION_EXECUTION_BLOCKED
        self._pending: _PendingOperation | None = None
        self._temporary_ids: set[str] = set()
        self._packages_by_id: dict[str, ExtensionPackage] = {}
        self._extensions_by_id: dict[str, QWebEngineExtensionInfo] = {}
        self._enabled_by_id: dict[str, bool] = {}
        self._operation_history: dict[str, list[tuple[str, str, bool]]] = {}
        self.operation_finished.connect(self._record_operation_result)
        self._operation_timeout = QTimer(self)
        self._operation_timeout.setSingleShot(True)
        self._operation_timeout.setInterval(180_000)
        self._operation_timeout.timeout.connect(
            lambda: self._fail_pending("Qt WebEngine did not complete the extension operation.")
        )
        self.manager.installFinished.connect(self._on_install_finished)
        self.manager.loadFinished.connect(self._on_load_finished)
        self.manager.uninstallFinished.connect(self._on_uninstall_finished)

        # Profiles may have finished loading extensions before a manager window
        # opens, so inspect the current list as well as the asynchronous signal.
        for extension in self.manager.extensions():
            self._remember(extension)

        # Qt's installer keeps user packages under installPath(), but this
        # runtime does not always enumerate them on a fresh process start.
        # Retry through the same profile manager once startup initialization has
        # had a chance to complete; loadExtension keeps them disabled.
        self._startup_restore_timer = QTimer(self)
        self._startup_restore_timer.setSingleShot(True)
        self._startup_restore_timer.timeout.connect(self._load_missing_installed_extensions)
        self._startup_restore_timer.start(500)

    @classmethod
    def shared_for_profile(
        cls, profile: QWebEngineProfile, settings: QSettings
    ) -> "ExtensionController":
        """Return one controller for the application's shared regular profile."""
        key = id(profile)
        existing = cls._shared_by_profile.get(key)
        if existing is not None and existing[0] is profile:
            return existing[1]
        controller = cls(profile, settings, profile)
        cls._shared_by_profile[key] = (profile, controller)
        profile.destroyed.connect(lambda _obj=None, k=key: cls._shared_by_profile.pop(k, None))
        return controller

    @property
    def busy(self) -> bool:
        """Whether an install/load/uninstall request is awaiting Qt completion."""
        return self._pending is not None

    def extensions(self) -> list[QWebEngineExtensionInfo]:
        """Return a fresh snapshot of manager metadata for the native UI."""
        return list(self._extensions_by_id.values())

    def extension(self, extension_id: str) -> QWebEngineExtensionInfo | None:
        """Find a currently loaded extension without assuming its ID still exists."""
        if not extension_id:
            return None
        return self._extensions_by_id.get(extension_id)

    def is_enabled(self, extension_id: str) -> bool:
        """Return the state last received or applied through this controller."""
        return self._enabled_by_id.get(extension_id, False)

    def install(self, package: ExtensionPackage, enable_after: bool = False) -> bool:
        """Install a validated archive or folder into Qt's persistent profile storage."""
        duplicate = next((
            extension for extension in self.user_extensions()
            if (existing := self.installed_package(extension)) is not None
            and existing.name == package.name
            and existing.version == package.version
            and existing.manifest_sha256 == package.manifest_sha256
        ), None)
        if duplicate is not None:
            self.operation_finished.emit(
                "install", duplicate.id(),
                "An extension with the same name, version, and manifest is already installed.",
                False,
            )
            return False
        if not self._begin("install", package.path, enable_after):
            return False
        try:
            current = inspect_extension_package(package.path)
            if current.manifest_sha256 != package.manifest_sha256:
                self._fail_pending("The extension manifest changed after it was reviewed.")
                return False
            self.manager.installExtension(str(current.path))
            return True
        except (OSError, RuntimeError, ValueError) as error:
            self._fail_pending(str(error))
            return False

    def load_unpacked(self, package: ExtensionPackage, enable_after: bool = False) -> bool:
        """Temporarily load a validated unpacked folder for developer testing."""
        if not package.path.is_dir():
            self.operation_finished.emit(
                "load", "", "Developer Mode can load an unpacked folder only.", False
            )
            return False
        if not self._begin("load", package.path, enable_after, package=package):
            return False
        try:
            current = inspect_extension_package(package.path)
            if current.manifest_sha256 != package.manifest_sha256:
                self._fail_pending("The extension manifest changed after it was reviewed.")
                return False
            self.manager.loadExtension(str(current.path))
            return True
        except (OSError, RuntimeError, ValueError) as error:
            self._fail_pending(str(error))
            return False

    def set_enabled(
        self, extension_id: str, enabled: bool, *, user_approved: bool = False
    ) -> bool:
        """Fail closed: Qt's native enabled-state setter crashes in this runtime."""
        extension = self.extension(extension_id)
        if extension is None or not extension.isLoaded():
            self._forget_enabled_state(extension_id)
            self.extensions_changed.emit()
            self.operation_finished.emit(
                "enable" if enabled else "disable",
                extension_id,
                "This extension is no longer loaded. Its saved state was removed.",
                False,
            )
            return False
        if enabled and not user_approved:
            self.operation_finished.emit(
                "enable", extension_id, "User approval is required before enabling.", False
            )
            return False
        message = (
            "This LightMq Qt WebEngine build crashes natively when changing an extension's "
            "enabled state. No change was made; the extension remains in Qt's current state."
        )
        self.operation_finished.emit(
            "enable" if enabled else "disable", extension_id, message, False
        )
        return False

    def uninstall(self, extension_id: str) -> bool:
        """Uninstall only extensions located inside Qt's profile install directory."""
        extension = self.extension(extension_id)
        if extension is None or not self.is_user_installed(extension):
            self.operation_finished.emit(
                "uninstall", extension_id, "This extension is not a removable user install.", False
            )
            return False
        if not self._begin("uninstall", extension_id=extension_id):
            return False
        try:
            self.manager.uninstallExtension(extension)
            return True
        except (RuntimeError, ValueError) as error:
            self._fail_pending(str(error))
            return False

    def is_user_installed(self, extension: QWebEngineExtensionInfo) -> bool:
        """Identify Qt-installed user extensions without exposing built-in entries."""
        if not extension.isInstalled():
            return False
        root_text = self.manager.installPath()
        if not root_text:
            return False
        try:
            root = Path(root_text).resolve(strict=False)
            candidate = Path(extension.path()).resolve(strict=False)
            return candidate != root and candidate.is_relative_to(root)
        except (OSError, RuntimeError, ValueError):
            return False

    def is_temporary(self, extension: QWebEngineExtensionInfo) -> bool:
        """Return whether this session explicitly loaded an unpacked extension."""
        return extension.id() in self._temporary_ids

    def user_extensions(self) -> list[QWebEngineExtensionInfo]:
        """Exclude Qt's bundled PDF and Hangouts extensions from user management."""
        return [
            extension
            for extension in self.extensions()
            if self.is_user_installed(extension) or self.is_temporary(extension)
        ]

    def _load_missing_installed_extensions(self) -> None:
        """Reload validated packages from Qt's own persistent install directory."""
        install_root_text = self.manager.installPath()
        if not install_root_text:
            return
        try:
            install_root = Path(install_root_text).resolve(strict=True)
            if not install_root.is_dir():
                return
            loaded_paths = {
                Path(extension.path()).resolve(strict=False)
                for extension in self.extensions()
                if extension.isLoaded()
            }
            for candidate in install_root.iterdir():
                if candidate.is_symlink() or not candidate.is_dir():
                    continue
                try:
                    package = read_installed_manifest(candidate)
                    resolved = candidate.resolve(strict=True)
                    if resolved in loaded_paths:
                        continue
                    self.manager.loadExtension(str(resolved))
                except (OSError, RuntimeError, ValueError):
                    continue
        except (OSError, RuntimeError, ValueError):
            return

    def installed_package(self, extension: QWebEngineExtensionInfo) -> ExtensionPackage | None:
        """Read a best-effort local manifest summary for permission review."""
        cached = self._packages_by_id.get(extension.id())
        if cached is not None:
            return cached
        try:
            if extension.isInstalled():
                return read_installed_manifest(extension.path())
            return inspect_extension_package(extension.path())
        except (OSError, RuntimeError, ValueError):
            return None

    def open_popup_url(self, extension_id: str) -> str | None:
        """Return only a loaded/enabled extension's Qt-reported action popup URL."""
        extension = self.extension(extension_id)
        if extension is None or not self.is_enabled(extension_id):
            return None
        url = extension.actionPopupUrl()
        if (not url.isValid() or url.isEmpty() or url.scheme() != "chrome-extension"
                or url.host().casefold() != extension.id().casefold()
                or url.userInfo()):
            return None
        return url.toString()

    def operation_history(self, extension_id: str) -> tuple[tuple[str, str, bool], ...]:
        """Return bounded, in-memory manager outcomes for a single extension."""
        return tuple(self._operation_history.get(extension_id, ()))

    def diagnostics(self, extension_id: str) -> ExtensionDiagnostics | None:
        """Return a typed report assembled from Qt observations and local metadata."""
        from browser.features.extensions.extension_diagnostics import (
            collect_extension_diagnostics,
        )

        extension = self.extension(extension_id)
        if extension is None:
            return None
        return collect_extension_diagnostics(extension, self)

    def _record_operation_result(
        self, operation: str, extension_id: str, message: str, success: bool
    ) -> None:
        """Keep the latest ten native operation results in memory only."""
        if not extension_id:
            return
        items = self._operation_history.setdefault(extension_id, [])
        items.append((operation, message[:600], bool(success)))
        del items[:-10]

    def _begin(
        self,
        kind: str,
        source_path: str | Path = "",
        enable_after: bool = False,
        extension_id: str = "",
        package: ExtensionPackage | None = None,
    ) -> bool:
        if self._pending is not None:
            self.operation_finished.emit(
                kind, extension_id, "Another extension operation is still in progress.", False
            )
            return False
        self._pending = _PendingOperation(
            kind,
            str(source_path),
            extension_id,
            bool(enable_after),
            package,
        )
        self._operation_timeout.start()
        return True

    def _fail_pending(self, message: str) -> None:
        operation = self._pending
        if operation is None:
            return
        self._pending = None
        self._operation_timeout.stop()
        self.operation_finished.emit(
            operation.kind, operation.extension_id, message, False
        )

    def _on_install_finished(self, extension: QWebEngineExtensionInfo) -> None:
        self._remember(extension)
        operation = self._pending
        if operation is None or operation.kind != "install":
            self.extensions_changed.emit()
            return
        success = extension.isInstalled() and extension.isLoaded() and not extension.error()
        message = extension.error()
        if success:
            if operation.package is not None:
                self._packages_by_id[extension.id()] = replace(
                    operation.package, path=Path(extension.path())
                )
            enabled = operation.enable_after
            if enabled:
                message = (
                    "Installed disabled. This Qt WebEngine build cannot safely enable extensions."
                )
            else:
                message = "Installed disabled."
        elif not message:
            message = "Qt WebEngine could not install the extension."
        self._pending = None
        self._operation_timeout.stop()
        self.extensions_changed.emit()
        self.operation_finished.emit("install", extension.id(), message, success)

    def _on_load_finished(self, extension: QWebEngineExtensionInfo) -> None:
        self._remember(extension)
        operation = self._pending
        is_pending_load = (
            operation is not None
            and operation.kind == "load"
            and self._same_path(operation.source_path, extension.path())
        )
        if is_pending_load and operation is not None:
            success = extension.isLoaded() and not extension.error()
            message = extension.error()
            if success:
                self._temporary_ids.add(extension.id())
                if operation.package is not None:
                    self._packages_by_id[extension.id()] = operation.package
            if success and operation.enable_after:
                message = (
                    "Temporarily loaded disabled. This Qt WebEngine build cannot safely "
                    "enable extensions."
                )
            elif success:
                message = "Temporarily loaded disabled; it will not persist after restart."
            elif not message:
                message = "Qt WebEngine could not load the unpacked extension."
            self._pending = None
            self._operation_timeout.stop()
            self.operation_finished.emit("load", extension.id(), message, success)
        self.extensions_changed.emit()

    def _on_uninstall_finished(self, extension: QWebEngineExtensionInfo) -> None:
        operation = self._pending
        if operation is None or operation.kind != "uninstall":
            self.extensions_changed.emit()
            return
        # Qt 6.12 may report isInstalled=True on uninstallFinished even after
        # it has removed the extension directory, so verify the managed path.
        success = not extension.error() and not Path(extension.path()).exists()
        message = extension.error()
        if success:
            self._forget_enabled_state(extension.id())
            self._extensions_by_id.pop(extension.id(), None)
            self._enabled_by_id.pop(extension.id(), None)
            self._temporary_ids.discard(extension.id())
            self._packages_by_id.pop(extension.id(), None)
            message = "Extension uninstalled."
        elif not message:
            message = "Qt WebEngine could not uninstall the extension."
        self._pending = None
        self._operation_timeout.stop()
        self.extensions_changed.emit()
        self.operation_finished.emit("uninstall", extension.id(), message, success)

    def _remember(self, extension: QWebEngineExtensionInfo) -> None:
        """Cache Qt's value metadata so updates never re-query the manager mid-page."""
        extension_id = extension.id()
        if not extension_id:
            return
        self._extensions_by_id[extension_id] = extension
        self._enabled_by_id[extension_id] = extension.isEnabled()

    def _forget_enabled_state(self, extension_id: str) -> None:
        if not extension_id:
            return
        key = f"{ENABLED_STATES_KEY}/{quote(extension_id, safe='')}"
        if self.settings.contains(key):
            self.settings.remove(key)
            self.settings.sync()

    @staticmethod
    def _same_path(first: str, second: str) -> bool:
        if not first or not second:
            return False
        try:
            return str(Path(first).resolve(strict=False)).casefold() == str(
                Path(second).resolve(strict=False)
            ).casefold()
        except (OSError, RuntimeError, ValueError):
            return False
