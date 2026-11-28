"""Safety and manifest validation for local extension packages."""

import json
from pathlib import Path
import zipfile

import pytest

from browser.features.extensions.package_inspector import (
    ExtensionPackageError,
    inspect_extension_package,
)


FIXTURE = Path(__file__).parents[1] / "fixtures" / "extensions" / "simple_mv3"


def test_inspects_unpacked_manifest_v3_and_permissions():
    package = inspect_extension_package(FIXTURE)

    assert package.name == "LightMq Local Test Extension"
    assert package.version == "1.0.0"
    assert package.permissions == ("storage",)
    assert package.host_permissions == ("http://127.0.0.1/*",)
    assert package.content_script_matches == ("http://127.0.0.1/*",)
    assert any("storage" in item for item in package.requested_capabilities)


def test_inspects_valid_zip_with_top_level_manifest(tmp_path):
    archive_path = tmp_path / "simple.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in FIXTURE.iterdir():
            archive.write(source, source.name)

    package = inspect_extension_package(archive_path)
    assert package.name == "LightMq Local Test Extension"


@pytest.mark.parametrize(
    "manifest, expected",
    [
        ({"manifest_version": 2, "name": "Old", "version": "1"}, "Manifest V3"),
        ({"manifest_version": 3, "name": "Missing version"}, "version"),
        ([], "JSON object"),
    ],
)
def test_rejects_invalid_or_unsupported_manifest(tmp_path, manifest, expected):
    folder = tmp_path / "extension"
    folder.mkdir()
    content = "[]" if isinstance(manifest, list) else json.dumps(manifest)
    (folder / "manifest.json").write_text(content, encoding="utf-8")

    with pytest.raises(ExtensionPackageError, match=expected):
        inspect_extension_package(folder)


@pytest.mark.parametrize(
    "unsafe_name", ["../outside.txt", "C:/outside.txt", "/outside.txt", "a/../../b"]
)
def test_rejects_zip_path_traversal_before_install(tmp_path, unsafe_name):
    archive_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(
            "manifest.json",
            json.dumps({"manifest_version": 3, "name": "Traversal test", "version": "1.0"}),
        )
        archive.writestr(unsafe_name, "must not be extracted")

    with pytest.raises(ExtensionPackageError):
        inspect_extension_package(archive_path)


def test_rejects_missing_manifest_and_malformed_zip(tmp_path):
    missing = tmp_path / "missing.zip"
    with zipfile.ZipFile(missing, "w") as archive:
        archive.writestr("readme.txt", "no extension manifest")
    with pytest.raises(ExtensionPackageError, match="manifest.json"):
        inspect_extension_package(missing)

    malformed = tmp_path / "broken.zip"
    malformed.write_bytes(b"not a zip")
    with pytest.raises(ExtensionPackageError):
        inspect_extension_package(malformed)
