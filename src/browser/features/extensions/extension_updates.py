"""Safe local update comparison without modifying Qt's managed install tree."""

from __future__ import annotations

from dataclasses import dataclass
import re

from browser.features.extensions.package_inspector import ExtensionPackage


@dataclass(frozen=True)
class LocalUpdateAssessment:
    """Comparison result for a user-selected local package."""

    status: str
    explanation: str
    added_permissions: tuple[str, ...] = ()
    added_hosts: tuple[str, ...] = ()
    update_available: bool = False
    added_optional_permissions: tuple[str, ...] = ()
    added_optional_hosts: tuple[str, ...] = ()


def compare_local_update(
    installed: ExtensionPackage, candidate: ExtensionPackage
) -> LocalUpdateAssessment:
    """Compare package declarations when manifest keys match.

    A matching key is a package claim, not signature verification; the local
    package source remains untrusted until independently verified.
    """
    if not installed.manifest_key or not candidate.manifest_key:
        return LocalUpdateAssessment(
            "Identity unverified",
            "Both packages must declare the same manifest public key. Display name and version "
            "are not sufficient to establish that a package updates the installed extension.",
        )
    if installed.manifest_key != candidate.manifest_key:
        return LocalUpdateAssessment(
            "Different identity", "The package's declared key differs from the installed extension."
        )
    old_version = _version_tuple(installed.version)
    new_version = _version_tuple(candidate.version)
    if old_version is None or new_version is None:
        return LocalUpdateAssessment(
            "Invalid version", "A version could not be safely compared using Chrome's numeric version format."
        )
    if new_version <= old_version:
        return LocalUpdateAssessment(
            "No update", "The selected package version is not newer than the installed version."
        )
    added_permissions = tuple(sorted(set(candidate.permissions) - set(installed.permissions)))
    added_hosts = tuple(sorted(set(candidate.host_permissions) - set(installed.host_permissions)))
    added_optional_permissions = tuple(sorted(
        set(candidate.optional_permissions) - set(installed.optional_permissions)
    ))
    added_optional_hosts = tuple(sorted(
        set(candidate.optional_host_permissions) - set(installed.optional_host_permissions)
    ))
    delta = bool(added_permissions or added_hosts or added_optional_permissions or added_optional_hosts)
    return LocalUpdateAssessment(
        "Permission review required" if delta else "Newer version identified",
        "The declared package key matches and the numeric version is newer; this does not "
        "verify package authenticity. Qt does not provide a "
        "documented atomic in-place update/rollback workflow, so LightMq will not replace "
        "the Qt-managed installation automatically. This is a comparison only.",
        added_permissions,
        added_hosts,
        True,
        added_optional_permissions,
        added_optional_hosts,
    )


def _version_tuple(value: str) -> tuple[int, ...] | None:
    """Parse Chrome extension versions (one to four dot-separated integers)."""
    if not re.fullmatch(r"\d+(?:\.\d+){0,3}", value):
        return None
    try:
        return tuple(int(part) for part in value.split("."))
    except ValueError:
        return None
