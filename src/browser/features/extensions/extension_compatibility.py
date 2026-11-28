"""Evidence-based Manifest V3 compatibility reports for Qt WebEngine."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
import re
import zipfile

import PySide6
from PySide6.QtCore import qVersion
from PySide6.QtWebEngineCore import QWebEngineProfile

from browser.features.extensions.package_inspector import ExtensionPackage


class CompatibilityStatus(str, Enum):
    """User-facing classifications, kept deliberately conservative."""

    VERIFIED_WORKING = "Verified Working"
    POTENTIALLY_COMPATIBLE = "Potentially Compatible"
    LIMITED = "Limited Compatibility"
    INCOMPATIBLE = "Incompatible"
    UNKNOWN = "Unknown"


@dataclass(frozen=True)
class CapabilityEvidence:
    """One capability observation tied to the current Qt runtime."""

    capability: str
    status: str
    evidence: str


@dataclass(frozen=True)
class CompatibilityReport:
    """A static, non-executing assessment with explicit evidence limits."""

    status: CompatibilityStatus
    qt_version: str
    pyside_version: str
    chromium_version: str
    api_namespaces: tuple[str, ...]
    evidence: tuple[str, ...]
    capabilities: tuple[CapabilityEvidence, ...]
    source_scan_limited: bool = True


# Namespaces remain unknown unless LightMq has an actual controlled runtime
# test for that Qt/Chromium build. The manager API itself is not an API matrix.
_NAMESPACE_RE = re.compile(r"\b(?:chrome|browser)\.([A-Za-z_$][\w$]*)")
_MAX_SOURCE_BYTES = 2 * 1024 * 1024
_MAX_SOURCE_FILES = 256


def analyze_extension(
    package: ExtensionPackage,
    profile: QWebEngineProfile | None = None,
    *,
    extension_execution_blocked: bool | None = None,
) -> CompatibilityReport:
    """Analyze manifest and bounded source text without running extension code.

    ``extension_execution_blocked`` must reflect a verified observation from
    the active runtime. ``None`` means LightMq has no current observation.
    """
    user_agent = profile.httpUserAgent() if profile is not None else ""
    chromium_match = re.search(r"(?:Chrome|Chromium)/([0-9.]+)", user_agent)
    chromium_version = chromium_match.group(1) if chromium_match else "Unknown"
    namespaces = _scan_api_namespaces(package)
    manager_methods = (
        "extensions", "installExtension", "loadExtension", "setExtensionEnabled",
        "uninstallExtension", "unloadExtension",
    )
    manager_present = all(
        hasattr(profile.extensionManager(), method) for method in manager_methods
    ) if profile is not None else None
    capability_records = [
        CapabilityEvidence(
            "Profile extension manager", "Available" if manager_present else
            "Unavailable" if manager_present is False else "Unknown",
            "All expected manager methods were found on the active profile manager."
            if manager_present else "No active profile was supplied for runtime inspection.",
        ),
        CapabilityEvidence(
            "Extension enable/disable", "Blocked" if extension_execution_blocked is True else "Unknown",
            "LightMq's controlled local MV3 test reproduced a native access violation "
            "when calling setExtensionEnabled(); LightMq therefore does not call it."
            if extension_execution_blocked is True else
            "No safe enable/disable runtime result is recorded for this assessment.",
        ),
        CapabilityEvidence(
            "Chrome extension JavaScript APIs", "Unknown",
            "Qt exposes no per-namespace support matrix; source matches are static hints only.",
        ),
        CapabilityEvidence(
            "Action popup execution", "Unknown",
            "Popup metadata can be read from Qt, but execution requires an enabled extension.",
        ),
    ]
    if package.manifest_version != 3:
        status = CompatibilityStatus.INCOMPATIBLE
        evidence = ("Only Manifest V3 is supported by LightMq's package validator.",)
    elif manager_present is None or manager_present is False:
        status = CompatibilityStatus.UNKNOWN
        evidence = (
            "Manifest is valid, but the expected profile extension manager API could not be verified.",
        )
    elif extension_execution_blocked is True:
        status = CompatibilityStatus.LIMITED
        evidence = (
            "The package is valid and can be installed disabled.",
            "Extension execution is blocked because changing enabled state crashes this Qt runtime.",
        )
    else:
        status = CompatibilityStatus.POTENTIALLY_COMPATIBLE
        evidence = ("The Manifest V3 package passed static validation; runtime behavior is unverified.",)
    if namespaces:
        evidence += (
            "Static source scan found API namespace references: " + ", ".join(namespaces) +
            ". Dynamic construction and indirect API use cannot be detected.",
        )
        capability_records.extend(
            CapabilityEvidence(
                f"chrome.{namespace} / browser.{namespace}",
                "Unknown",
                "A static source reference was found; dynamic API calls and exact Qt support are unverified.",
            )
            for namespace in namespaces
        )
    else:
        evidence += ("No chrome.* or browser.* namespace references were found in the bounded source scan.",)
    return CompatibilityReport(
        status=status,
        qt_version=qVersion(),
        pyside_version=PySide6.__version__,
        chromium_version=chromium_version,
        api_namespaces=namespaces,
        evidence=evidence,
        capabilities=tuple(capability_records),
    )


def _scan_api_namespaces(package: ExtensionPackage) -> tuple[str, ...]:
    """Read at most 2 MiB of JavaScript as text; never execute package code."""
    remaining = _MAX_SOURCE_BYTES
    scanned = 0
    found: set[str] = set()
    try:
        if package.path.is_dir():
            files = package.path.rglob("*.js")
            for path in files:
                if scanned >= _MAX_SOURCE_FILES or remaining <= 0:
                    break
                if path.is_symlink() or not path.is_file():
                    continue
                resolved = path.resolve(strict=True)
                if not resolved.is_relative_to(package.path.resolve(strict=True)):
                    continue
                size = min(resolved.stat().st_size, remaining)
                if size <= 0:
                    continue
                with resolved.open("rb") as source:
                    text = source.read(size).decode("utf-8", "ignore")
                found.update(_NAMESPACE_RE.findall(text))
                remaining -= size
                scanned += 1
        elif package.path.suffix.lower() == ".zip":
            with zipfile.ZipFile(package.path) as archive:
                for info in archive.infolist():
                    if scanned >= _MAX_SOURCE_FILES or remaining <= 0:
                        break
                    name = info.filename.replace("\\", "/")
                    if info.is_dir() or not name.lower().endswith(".js"):
                        continue
                    pure = PurePosixPath(name)
                    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
                        continue
                    if info.file_size < 0 or info.file_size > remaining:
                        continue
                    text = archive.read(info).decode("utf-8", "ignore")
                    found.update(_NAMESPACE_RE.findall(text))
                    remaining -= info.file_size
                    scanned += 1
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile):
        return ()
    return tuple(sorted(found))
