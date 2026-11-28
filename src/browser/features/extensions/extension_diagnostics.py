"""Build truthful, metadata-only extension diagnostics for native UI."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import TYPE_CHECKING

import PySide6
from PySide6.QtCore import qVersion
from PySide6.QtWebEngineCore import QWebEngineExtensionInfo, QWebEngineProfile

from browser.features.extensions.extension_compatibility import (
    CompatibilityReport,
    analyze_extension,
)
from browser.features.extensions.package_inspector import ExtensionPackage

if TYPE_CHECKING:
    from browser.features.extensions.extension_controller import ExtensionController


@dataclass(frozen=True)
class ExtensionDiagnostics:
    """Observed extension state plus explicit non-tested runtime checks."""

    extension_id: str
    name: str
    manifest_version: int | None
    version: str
    installation: str
    loaded: str
    enabled: str
    error_messages: tuple[str, ...]
    compatibility: CompatibilityReport
    runtime_checks: tuple[tuple[str, str], ...]
    manifest_features: tuple[str, ...]


def collect_extension_diagnostics(
    extension: QWebEngineExtensionInfo, controller: ExtensionController
) -> ExtensionDiagnostics:
    """Collect data directly from Qt and local manifest metadata."""
    extension_id = str(extension.id())
    package: ExtensionPackage | None = controller.installed_package(extension)
    errors: list[str] = []
    qt_error = str(extension.error() or "").strip()
    if qt_error:
        errors.append(qt_error)
    for operation, message, success in controller.operation_history(extension_id):
        if not success:
            errors.append(f"{operation}: {message}")
    error_messages = tuple(dict.fromkeys(errors)) or ("No Qt-reported errors recorded.",)
    popup_url = extension.actionPopupUrl()
    popup_url_available = bool(popup_url.isValid() and not popup_url.isEmpty())
    popup_declared = bool((package and package.action_popup) or popup_url_available)
    blocked = bool(getattr(controller, "extension_execution_blocked", False))
    runtime_checks = (
        ("Content script execution", "Not tested" if not blocked else "Blocked; extension cannot be enabled safely"),
        (
            "Action popup",
            "Declared; not executed" if popup_declared and blocked else
            "Qt popup URL available" if popup_url_available else
            "Declared in manifest; Qt reports no popup URL" if popup_declared else "No popup declared",
        ),
        (
            "Background service worker",
            "Declared; not executed" if package and package.background_service_worker and blocked else
            "Not declared" if not package or not package.background_service_worker else "Not tested",
        ),
    )
    features: list[str] = []
    if package:
        if package.background_service_worker:
            features.append(f"Service worker: {package.background_service_worker}")
        if package.action_popup:
            features.append(f"Action popup: {package.action_popup}")
        if package.icons:
            features.append(f"Manifest icons: {len(package.icons)}")
        if package.web_accessible_resources:
            features.append(f"Web-accessible resources: {len(package.web_accessible_resources)}")
        if package.content_security_policy:
            features.append("Extension page content security policy declared")
        features.extend(f"Additional manifest key: {key}" for key in package.other_manifest_keys)
    return ExtensionDiagnostics(
        extension_id=extension_id,
        name=str(extension.name() or "Unnamed extension"),
        manifest_version=3 if package else None,
        version=package.version if package else "Unavailable",
        installation=("Profile installation successful" if extension.isInstalled() else
                      "Temporary session load" if controller.is_temporary(extension) else "Not installed"),
        loaded="Loaded" if extension.isLoaded() else "Not loaded",
        enabled="Enabled" if controller.is_enabled(extension_id) else "Disabled",
        error_messages=error_messages,
        compatibility=analyze_extension(
            package, controller.profile,
            extension_execution_blocked=blocked,
        ) if package else analyze_extension_unavailable(controller.profile),
        runtime_checks=runtime_checks,
        manifest_features=tuple(features) or ("No additional manifest features reported.",),
    )


def analyze_extension_unavailable(profile: QWebEngineProfile) -> CompatibilityReport:
    """Return an Unknown report where local manifest metadata cannot be read."""
    from browser.features.extensions.extension_compatibility import (
        CapabilityEvidence,
        CompatibilityStatus,
    )
    match = re.search(r"(?:Chrome|Chromium)/([0-9.]+)", profile.httpUserAgent())
    return CompatibilityReport(
        status=CompatibilityStatus.UNKNOWN,
        qt_version=qVersion(),
        pyside_version=PySide6.__version__,
        chromium_version=match.group(1) if match else "Unknown",
        api_namespaces=(),
        evidence=("The extension manifest could not be read, so compatibility is unknown.",),
        capabilities=(CapabilityEvidence("Manifest metadata", "Unavailable", "Qt extension path is missing or unreadable."),),
    )
