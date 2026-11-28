"""Human-readable permission and host-access summaries for MV3 manifests."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from browser.features.extensions.package_inspector import ExtensionPackage


_PERMISSION_LABELS = {
    "activeTab": "Read the currently active tab after a user gesture",
    "alarms": "Schedule background tasks",
    "bookmarks": "Read and change browser bookmarks",
    "clipboardRead": "Read clipboard contents",
    "clipboardWrite": "Write to the clipboard",
    "cookies": "Read and change site cookies",
    "debugger": "Attach debugging tools to tabs",
    "downloads": "Manage browser downloads",
    "history": "Read and change browsing history",
    "identity": "Request identity or authentication tokens",
    "management": "Inspect and manage browser extensions",
    "nativeMessaging": "Communicate with installed native applications",
    "notifications": "Display system notifications",
    "proxy": "Read and change proxy settings",
    "scripting": "Inject scripts into web pages when permitted",
    "storage": "Store extension data in browser-managed storage",
    "tabCapture": "Capture audio or video from browser tabs",
    "webRequest": "Observe network requests",
    "webRequestBlocking": "Block or modify network requests",
    "declarativeNetRequest": "Apply declared network filtering rules",
    "desktopCapture": "Capture the desktop or application windows",
    "geolocation": "Access location APIs when separately granted",
}
_SENSITIVE = {
    "clipboardRead", "cookies", "debugger", "history", "identity", "management",
    "nativeMessaging", "proxy", "tabCapture", "desktopCapture", "webRequest",
    "webRequestBlocking", "downloads", "browsingData", "geolocation",
}
_BROAD_PATTERNS = {"<all_urls>", "*://*/*", "http://*/*", "https://*/*", "file:///*"}


@dataclass(frozen=True)
class PermissionFinding:
    """One displayed permission or host-access finding."""

    scope: str
    value: str
    explanation: str
    elevated: bool = False
    broad: bool = False
    optional: bool = False


def analyze_permissions(package: ExtensionPackage) -> tuple[PermissionFinding, ...]:
    """Explain declared permissions without implying runtime enforcement."""
    findings: list[PermissionFinding] = []
    for permission in package.permissions:
        findings.append(_permission(permission, optional=False))
    for permission in package.optional_permissions:
        findings.append(_permission(permission, optional=True))
    for host in package.host_permissions:
        findings.append(_host(host, optional=False))
    for host in package.optional_host_permissions:
        findings.append(_host(host, optional=True))
    for match in package.content_script_matches:
        findings.append(_host(match, optional=False, scope="Content script site match"))
    if not findings:
        findings.append(PermissionFinding("Permissions", "None declared", "No manifest permissions were declared."))
    return tuple(findings)


def _permission(value: str, *, optional: bool) -> PermissionFinding:
    text = _PERMISSION_LABELS.get(value, f"Requests the '{value}' extension permission")
    return PermissionFinding(
        "Optional API permission" if optional else "API permission",
        value,
        text,
        elevated=value in _SENSITIVE,
        optional=optional,
    )


def _host(value: str, *, optional: bool, scope: str = "Host access") -> PermissionFinding:
    normalized = value.casefold()
    broad = normalized in _BROAD_PATTERNS
    wildcard_subdomains = False
    if not broad:
        try:
            host = urlsplit(value.replace("*://", "https://", 1)).hostname or ""
            broad = host == "*"
            wildcard_subdomains = host.startswith("*.")
        except ValueError:
            host = ""
    if broad:
        explanation = "This pattern may grant access to most or all websites."
    elif wildcard_subdomains:
        explanation = "This wildcard covers the named domain and multiple subdomains."
    else:
        explanation = "The extension declares access for this site pattern."
    return PermissionFinding(
        "Optional host access" if optional else scope,
        value,
        explanation,
        elevated=broad or wildcard_subdomains,
        broad=broad or wildcard_subdomains,
        optional=optional,
    )
