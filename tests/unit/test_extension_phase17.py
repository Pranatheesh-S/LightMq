"""Evidence, permission, update, Web Store, and icon checks for Phase 17."""

from dataclasses import replace
import json
from pathlib import Path
import sys

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from browser.features.extensions.extension_assets import load_extension_icon
from browser.features.extensions.extension_compatibility import (
    CompatibilityStatus,
    analyze_extension,
)
from browser.features.extensions.extension_updates import compare_local_update
from browser.features.extensions.package_inspector import (
    ExtensionPackageError,
    inspect_extension_package,
)
from browser.features.extensions.permission_analyzer import analyze_permissions
from browser.features.extensions.webstore_integration import recognize_webstore_listing


app = QApplication.instance() or QApplication(sys.argv)
FIXTURE = Path(__file__).parents[1] / "fixtures" / "extensions" / "simple_mv3"
STORE_ID = "abcdefghijklmnopabcdefghijklmnop"


class _Manager:
    extensions = installExtension = loadExtension = setExtensionEnabled = object()
    uninstallExtension = unloadExtension = object()


class _Profile:
    def httpUserAgent(self):
        return "Mozilla/5.0 Chrome/140.0.0.0 Safari/537.36"

    def extensionManager(self):
        return _Manager()


def _write_manifest(folder: Path, manifest: dict, files: dict[str, bytes] | None = None) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    for name, data in (files or {}).items():
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return folder


def test_manifest_extraction_and_static_api_scan_are_explicitly_limited(tmp_path):
    folder = tmp_path / "scan"
    manifest = {
        "manifest_version": 3,
        "name": "Static Scan",
        "version": "1.0.0",
        "background": {"service_worker": "worker.js"},
        "action": {"default_popup": "popup.html"},
        "icons": {"16": "icon.png"},
        "web_accessible_resources": [{"resources": ["assets/*.js"], "matches": ["https://example.test/*"]}],
        "content_security_policy": {"extension_pages": "script-src 'self'; object-src 'self'"},
        "side_panel": {"default_path": "side.html"},
    }
    _write_manifest(folder, manifest, {
        "worker.js": b"chrome.tabs.query({}); browser.storage.local.get('x');",
        "popup.html": b"<!doctype html><p>popup</p>",
        "icon.png": b"not an image yet",
        "assets/injected.js": b"",
        "side.html": b"<p>side</p>",
    })
    package = inspect_extension_package(folder)
    report = analyze_extension(package, _Profile(), extension_execution_blocked=True)

    assert package.background_service_worker == "worker.js"
    assert package.action_popup == "popup.html"
    assert package.icons == (("16", "icon.png"),)
    assert package.web_accessible_resources == ("assets/*.js",)
    assert package.content_security_policy.startswith("script-src")
    assert package.other_manifest_keys == ("side_panel",)
    assert report.status is CompatibilityStatus.LIMITED
    assert report.qt_version.startswith("6.")
    assert report.chromium_version == "140.0.0.0"
    assert report.api_namespaces == ("storage", "tabs")
    assert "Dynamic construction" in report.evidence[-1]


def test_compatibility_without_runtime_evidence_is_not_verified():
    package = inspect_extension_package(FIXTURE)
    report = analyze_extension(package)
    assert report.status is CompatibilityStatus.UNKNOWN
    assert all(item.status != "Verified" for item in report.capabilities)


def test_permission_review_marks_sensitive_and_broad_requests():
    # Use the fixture copy of the package with no side effects on browser storage.
    package = inspect_extension_package(FIXTURE)
    package = replace(
        package,
        permissions=("cookies", "storage"),
        host_permissions=("https://*/*",),
        content_script_matches=("<all_urls>",),
    )
    findings = analyze_permissions(package)
    assert any(item.value == "cookies" and item.elevated for item in findings)
    assert any(item.value == "https://*/*" and item.broad for item in findings)
    assert any(item.value == "<all_urls>" and item.broad for item in findings)


def test_resource_references_must_exist_before_install(tmp_path):
    folder = tmp_path / "missing-resource"
    _write_manifest(folder, {
        "manifest_version": 3,
        "name": "Missing Resource",
        "version": "1.0",
        "background": {"service_worker": "missing.js"},
    })
    try:
        inspect_extension_package(folder)
    except ExtensionPackageError as error:
        assert "missing" in str(error).casefold()
    else:
        raise AssertionError("A missing service worker was accepted")


def test_webstore_recognizer_requires_official_https_listing_host():
    current = recognize_webstore_listing(
        f"https://chromewebstore.google.com/detail/sample/{STORE_ID}?hl=en"
    )
    legacy = recognize_webstore_listing(
        f"https://chrome.google.com/webstore/detail/sample/{STORE_ID}"
    )
    assert current is not None and current.extension_id == STORE_ID
    assert legacy is not None and legacy.extension_id == STORE_ID
    assert recognize_webstore_listing(f"http://chromewebstore.google.com/detail/x/{STORE_ID}") is None
    assert recognize_webstore_listing(f"https://chromewebstore.google.com.evil.test/detail/x/{STORE_ID}") is None
    assert recognize_webstore_listing(f"https://chromewebstore.google.com:8443/detail/x/{STORE_ID}") is None
    assert recognize_webstore_listing(f"https://chromewebstore.google.com/detail/x/{STORE_ID}/extra") is None
    invalid_id = recognize_webstore_listing(
        f"https://chromewebstore.google.com/detail/x/{STORE_ID[:-1]}z"
    )
    assert invalid_id is not None and invalid_id.extension_id is None
    assert recognize_webstore_listing(f"https://user@chromewebstore.google.com/detail/x/{STORE_ID}") is None


def test_local_update_compare_requires_same_manifest_key_and_reviews_added_scope():
    base = inspect_extension_package(FIXTURE)
    installed = replace(base, version="1.2.0", manifest_key="trusted-public-key", permissions=("storage",))
    candidate = replace(
        base,
        version="1.3.0",
        manifest_key="trusted-public-key",
        permissions=("storage", "cookies"),
        host_permissions=("https://example.test/*",),
    )
    result = compare_local_update(installed, candidate)
    assert result.update_available
    assert result.status == "Permission review required"
    assert result.added_permissions == ("cookies",)
    assert result.added_hosts == ("https://example.test/*",)
    assert "will not replace" in result.explanation
    assert compare_local_update(installed, replace(candidate, manifest_key="different-key")).status == "Different identity"
    assert compare_local_update(base, candidate).status == "Identity unverified"


def test_icon_loader_accepts_bounded_png_and_ignores_svg(tmp_path):
    folder = tmp_path / "icon-package"
    png = QImage(24, 24, QImage.Format.Format_ARGB32)
    png.fill(0xFF0088CC)
    _write_manifest(folder, {
        "manifest_version": 3,
        "name": "Icon",
        "version": "1.0",
        "icons": {"24": "icon.png", "32": "unsafe.svg"},
    }, {"unsafe.svg": b"<svg xmlns='http://www.w3.org/2000/svg'><script/></svg>"})
    assert png.save(str(folder / "icon.png"))
    package = inspect_extension_package(folder)
    icon = load_extension_icon(package)
    assert not icon.isNull()
    svg_package = replace(package, icons=(("32", "unsafe.svg"),))
    assert load_extension_icon(svg_package).isNull()
