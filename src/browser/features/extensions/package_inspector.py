"""Validate local Manifest V3 extension packages before handing them to Qt."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import fnmatch
import json
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Any
from urllib.parse import urlsplit
import zipfile


MAX_MANIFEST_BYTES = 1024 * 1024
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_PACKAGE_BYTES = 512 * 1024 * 1024
MAX_PACKAGE_FILES = 10000
MAX_ENTRY_BYTES = 128 * 1024 * 1024
_WINDOWS_RESERVED = {
    "con", "prn", "aux", "nul",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}


class ExtensionPackageError(ValueError):
    """Raised when an extension folder or archive is unsafe or invalid."""


@dataclass(frozen=True)
class ExtensionPackage:
    """Manifest details shown to the user before installation."""

    path: Path
    name: str
    version: str
    description: str
    permissions: tuple[str, ...]
    optional_permissions: tuple[str, ...]
    host_permissions: tuple[str, ...]
    optional_host_permissions: tuple[str, ...]
    content_script_matches: tuple[str, ...]
    manifest_sha256: str
    manifest_version: int = 3
    background_service_worker: str = ""
    action_popup: str = ""
    icons: tuple[tuple[str, str], ...] = ()
    web_accessible_resources: tuple[str, ...] = ()
    content_security_policy: str = ""
    other_manifest_keys: tuple[str, ...] = ()
    manifest_key: str = ""

    @property
    def requested_capabilities(self) -> tuple[str, ...]:
        """Return explicitly requested APIs and hosts, preserving manifest order."""
        entries = [f"API permission: {value}" for value in self.permissions]
        entries.extend(f"Host access: {value}" for value in self.host_permissions)
        entries.extend(
            f"Content script match: {value}" for value in self.content_script_matches
        )
        entries.extend(
            f"Optional API permission (not granted by default): {value}"
            for value in self.optional_permissions
        )
        entries.extend(
            f"Optional host access (not granted by default): {value}"
            for value in self.optional_host_permissions
        )
        return tuple(entries) or ("No permissions or host patterns declared.",)


def inspect_extension_package(path: str | Path) -> ExtensionPackage:
    """Validate a top-level MV3 manifest and return its review information.

    The function never extracts archives. Qt's profile extension manager performs
    the actual installation after validation and user approval.
    """
    selected = Path(path).expanduser()
    if selected.is_symlink():
        raise ExtensionPackageError("Select the actual extension folder or archive, not a symbolic link.")
    try:
        resolved = selected.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ExtensionPackageError("The selected extension path does not exist.") from error

    if resolved.is_dir():
        manifest_bytes = _read_folder_manifest(resolved)
    elif resolved.is_file() and resolved.suffix.lower() == ".zip":
        manifest_bytes = _read_zip_manifest(resolved)
    else:
        raise ExtensionPackageError("Choose an extension folder or a .zip archive.")

    manifest = _parse_manifest(manifest_bytes)
    _validate_manifest_resources(resolved, manifest)
    return _package_from_manifest(resolved, manifest, manifest_bytes)


def read_installed_manifest(path: str | Path) -> ExtensionPackage:
    """Read permission metadata from an already Qt-installed extension directory."""
    root = Path(path).resolve(strict=True)
    manifest_path = root / "manifest.json"
    try:
        if not root.is_dir() or manifest_path.is_symlink() or not manifest_path.is_file():
            raise ExtensionPackageError("Installed extension metadata is unavailable.")
        if manifest_path.stat().st_size > MAX_MANIFEST_BYTES:
            raise ExtensionPackageError("Installed manifest exceeds the 1 MiB safety limit.")
        manifest_bytes = manifest_path.read_bytes()
    except ExtensionPackageError:
        raise
    except OSError as error:
        raise ExtensionPackageError(f"Could not read installed extension metadata: {error}") from error
    manifest = _parse_manifest(manifest_bytes)
    return _package_from_manifest(root, manifest, manifest_bytes)


def _read_folder_manifest(root: Path) -> bytes:
    """Check an unpacked package tree for traversal-prone names and symlinks."""
    if root.is_symlink() or not root.is_dir():
        raise ExtensionPackageError("The extension folder must be a regular directory.")

    manifest_path = root / "manifest.json"
    try:
        if manifest_path.is_symlink() or not manifest_path.is_file():
            raise ExtensionPackageError("The selected folder has no top-level manifest.json.")
        manifest_size = manifest_path.stat().st_size
        if manifest_size > MAX_MANIFEST_BYTES:
            raise ExtensionPackageError("manifest.json is larger than the 1 MiB safety limit.")
        count = 0
        total_size = 0
        for entry in root.rglob("*"):
            relative = entry.relative_to(root).as_posix()
            _validate_relative_name(relative)
            if entry.is_symlink():
                raise ExtensionPackageError("Extension folders cannot contain symbolic links.")
            count += 1
            if count > MAX_PACKAGE_FILES:
                raise ExtensionPackageError("The extension contains too many files.")
            if entry.is_file():
                size = entry.stat().st_size
                if size > MAX_ENTRY_BYTES:
                    raise ExtensionPackageError(
                        f"An extension file exceeds the {MAX_ENTRY_BYTES // (1024 * 1024)} MiB safety limit."
                    )
                total_size += size
                if total_size > MAX_PACKAGE_BYTES:
                    raise ExtensionPackageError("The unpacked extension exceeds the 512 MiB safety limit.")
        return manifest_path.read_bytes()
    except ExtensionPackageError:
        raise
    except OSError as error:
        raise ExtensionPackageError(f"Could not read the extension folder: {error}") from error


def _read_zip_manifest(archive_path: Path) -> bytes:
    """Validate ZIP entry names and size bounds without writing extracted files."""
    try:
        archive_size = archive_path.stat().st_size
        if archive_size > MAX_ARCHIVE_BYTES:
            raise ExtensionPackageError("The ZIP archive exceeds the 128 MiB safety limit.")
        with zipfile.ZipFile(archive_path) as archive:
            members = archive.infolist()
            if not members:
                raise ExtensionPackageError("The ZIP archive is empty.")
            if len(members) > MAX_PACKAGE_FILES:
                raise ExtensionPackageError("The ZIP contains too many entries.")

            seen: set[str] = set()
            total_size = 0
            manifest_members: list[zipfile.ZipInfo] = []
            for member in members:
                name = member.filename
                _validate_relative_name(name)
                normalized = name.replace("\\", "/").rstrip("/").casefold()
                if normalized == "manifest.json" and name != "manifest.json":
                    raise ExtensionPackageError("The top-level manifest must be named manifest.json exactly.")
                if normalized in seen:
                    raise ExtensionPackageError("The ZIP contains duplicate or case-conflicting paths.")
                seen.add(normalized)
                if member.flag_bits & 0x1:
                    raise ExtensionPackageError("Encrypted ZIP entries are not supported.")
                mode = member.external_attr >> 16
                file_type = stat.S_IFMT(mode)
                allowed_type = (0, stat.S_IFREG, stat.S_IFDIR)
                if file_type not in allowed_type:
                    raise ExtensionPackageError("The ZIP contains a symbolic link or special file.")
                if member.file_size < 0 or member.file_size > MAX_ENTRY_BYTES:
                    raise ExtensionPackageError("A ZIP entry exceeds the 128 MiB safety limit.")
                if member.compress_size < 0:
                    raise ExtensionPackageError("The ZIP contains an invalid compressed-size record.")
                if member.file_size and member.compress_size == 0:
                    raise ExtensionPackageError("The ZIP contains an invalid compression record.")
                if member.compress_size and member.file_size / member.compress_size > 250:
                    raise ExtensionPackageError("The ZIP contains an unsafe compression ratio.")
                total_size += member.file_size
                if total_size > MAX_PACKAGE_BYTES:
                    raise ExtensionPackageError("The expanded extension exceeds the 512 MiB safety limit.")
                if normalized == "manifest.json":
                    manifest_members.append(member)

            if len(manifest_members) != 1 or manifest_members[0].is_dir():
                raise ExtensionPackageError("The ZIP must contain one top-level manifest.json.")
            manifest = manifest_members[0]
            if manifest.file_size > MAX_MANIFEST_BYTES:
                raise ExtensionPackageError("manifest.json is larger than the 1 MiB safety limit.")
            with archive.open(manifest, "r") as source:
                data = source.read(MAX_MANIFEST_BYTES + 1)
            if len(data) > MAX_MANIFEST_BYTES:
                raise ExtensionPackageError("manifest.json is larger than the 1 MiB safety limit.")
            return data
    except ExtensionPackageError:
        raise
    except (OSError, zipfile.BadZipFile, RuntimeError, NotImplementedError) as error:
        raise ExtensionPackageError(f"The ZIP archive could not be read: {error}") from error


def _validate_relative_name(raw_name: str) -> None:
    """Reject archive/folder names that could escape or alias the target tree."""
    if not raw_name or "\0" in raw_name:
        raise ExtensionPackageError("The package contains an empty or invalid path.")
    normalized = raw_name.replace("\\", "/")
    if normalized.startswith("/") or re.match(r"^[a-zA-Z]:", normalized):
        raise ExtensionPackageError("The package contains an absolute path.")
    is_directory = normalized.endswith("/")
    trimmed = normalized[:-1] if is_directory else normalized
    components = trimmed.split("/")
    if not trimmed or any(part in {"", ".", ".."} for part in components):
        raise ExtensionPackageError("The package contains a traversal or ambiguous path.")
    if len(normalized) > 220 or any(len(part) > 180 for part in components):
        raise ExtensionPackageError("The package contains an excessively long path.")
    for component in components:
        if ":" in component or component.endswith((".", " ")):
            raise ExtensionPackageError("The package contains a platform-unsafe path.")
        base = component.split(".", 1)[0].casefold()
        if base in _WINDOWS_RESERVED:
            raise ExtensionPackageError("The package contains a reserved device filename.")


def _parse_manifest(data: bytes) -> dict[str, Any]:
    """Parse and minimally validate the extension manifest structure."""
    try:
        manifest = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ExtensionPackageError(f"manifest.json is not valid UTF-8 JSON: {error}") from error
    if not isinstance(manifest, dict):
        raise ExtensionPackageError("manifest.json must contain a JSON object.")
    version = manifest.get("manifest_version")
    if type(version) is not int or version != 3:
        raise ExtensionPackageError("Only Manifest V3 extensions are supported by this manager.")
    for key in ("name", "version"):
        value = manifest.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ExtensionPackageError(f"manifest.json requires a non-empty string {key!r}.")
        if len(value) > 256:
            raise ExtensionPackageError(f"The manifest {key} field is too long.")
    if "description" in manifest and not isinstance(manifest["description"], str):
        raise ExtensionPackageError("The manifest description must be a string.")
    for key in (
        "permissions", "optional_permissions", "host_permissions", "optional_host_permissions"
    ):
        values = manifest.get(key, [])
        if not isinstance(values, list) or any(
            not isinstance(value, str) or not value.strip() for value in values
        ):
            raise ExtensionPackageError(f"The manifest {key} field must be an array of strings.")
    scripts = manifest.get("content_scripts", [])
    if not isinstance(scripts, list):
        raise ExtensionPackageError("The manifest content_scripts field must be an array.")
    for item in scripts:
        if not isinstance(item, dict):
            raise ExtensionPackageError("A content_scripts entry must be an object.")
        matches = item.get("matches", [])
        if not isinstance(matches, list) or any(not isinstance(value, str) for value in matches):
            raise ExtensionPackageError("Content script matches must be arrays of strings.")
        for resource_key in ("js", "css"):
            resources = item.get(resource_key, [])
            if not isinstance(resources, list) or any(
                not isinstance(value, str) or not value.strip() for value in resources
            ):
                raise ExtensionPackageError(
                    f"Content script {resource_key} must be an array of paths."
                )
    background = manifest.get("background", {})
    if not isinstance(background, dict):
        raise ExtensionPackageError("The manifest background field must be an object.")
    if "service_worker" in background and not isinstance(background["service_worker"], str):
        raise ExtensionPackageError("The background service_worker must be a path string.")
    action = manifest.get("action", {})
    if not isinstance(action, dict):
        raise ExtensionPackageError("The manifest action field must be an object.")
    if "default_popup" in action and not isinstance(action["default_popup"], str):
        raise ExtensionPackageError("The action default_popup must be a path string.")
    action_icons = action.get("default_icon", {})
    if not isinstance(action_icons, (str, dict)) or (
        isinstance(action_icons, dict)
        and any(not isinstance(size, str) or not isinstance(path, str)
                for size, path in action_icons.items())
    ):
        raise ExtensionPackageError("The action default_icon must be a path or size-to-path map.")
    icons = manifest.get("icons", {})
    if not isinstance(icons, dict) or any(
        not isinstance(size, str) or not isinstance(path, str)
        for size, path in icons.items()
    ):
        raise ExtensionPackageError("Manifest icons must map size labels to resource paths.")
    web_resources = manifest.get("web_accessible_resources", [])
    if not isinstance(web_resources, list) or any(
        not isinstance(entry, dict)
        or not isinstance(entry.get("resources", []), list)
        or any(not isinstance(value, str) for value in entry.get("resources", []))
        for entry in web_resources
    ):
        raise ExtensionPackageError("web_accessible_resources must contain resource arrays.")
    csp = manifest.get("content_security_policy", {})
    if not isinstance(csp, (str, dict)):
        raise ExtensionPackageError("content_security_policy must be a string or object.")
    if "key" in manifest and not isinstance(manifest["key"], str):
        raise ExtensionPackageError("The manifest key must be a string when provided.")
    return manifest


def _validate_manifest_resources(root: Path, manifest: dict[str, Any]) -> None:
    """Ensure executable and declared web-accessible resource paths exist."""
    references: list[str] = []
    background = manifest.get("background", {})
    if background.get("service_worker"):
        references.append(background["service_worker"])
    action = manifest.get("action", {})
    if action.get("default_popup"):
        references.append(action["default_popup"])
    for script in manifest.get("content_scripts", []):
        references.extend(script.get("js", []))
        references.extend(script.get("css", []))
    references.extend(
        resource
        for entry in manifest.get("web_accessible_resources", [])
        for resource in entry.get("resources", [])
    )
    if not references:
        return
    if root.is_dir():
        for reference in references:
            resource = _resource_path(reference)
            if any(character in resource for character in "*?["):
                if not any(root.glob(resource)):
                    raise ExtensionPackageError(
                        f"Manifest resource pattern does not match any package file: {reference}"
                    )
                continue
            candidate = root.joinpath(*PurePosixPath(resource).parts)
            try:
                resolved = candidate.resolve(strict=True)
                if not resolved.is_relative_to(root) or not resolved.is_file():
                    raise FileNotFoundError(reference)
            except (OSError, RuntimeError) as error:
                raise ExtensionPackageError(
                    f"Manifest resource is missing or unsafe: {reference}"
                ) from error
        return
    try:
        with zipfile.ZipFile(root) as archive:
            names = {info.filename.rstrip("/") for info in archive.infolist() if not info.is_dir()}
            for reference in references:
                resource = _resource_path(reference)
                matches = (
                    any(fnmatch.fnmatchcase(name, resource) for name in names)
                    if any(character in resource for character in "*?[")
                    else resource in names
                )
                if not matches:
                    raise ExtensionPackageError(
                        f"Manifest resource is missing from the ZIP: {reference}"
                    )
    except (OSError, zipfile.BadZipFile) as error:
        raise ExtensionPackageError(f"Could not verify manifest resources: {error}") from error


def _resource_path(reference: str) -> str:
    """Normalize a manifest-local resource while rejecting traversal and URLs."""
    parsed = urlsplit(reference)
    if parsed.scheme or parsed.netloc:
        raise ExtensionPackageError(f"Manifest resource must be local: {reference}")
    raw = parsed.path.lstrip("/")
    _validate_relative_name(raw)
    return raw


def _string_tuple(manifest: dict[str, Any], key: str) -> tuple[str, ...]:
    values = manifest.get(key, [])
    return tuple(dict.fromkeys(value.strip() for value in values if value.strip()))


def _package_from_manifest(
    path: Path, manifest: dict[str, Any], manifest_bytes: bytes
) -> ExtensionPackage:
    """Create a safe immutable summary for UI review and consent prompts."""
    content_matches: list[str] = []
    for script in manifest.get("content_scripts", []):
        content_matches.extend(script.get("matches", []))
    background = manifest.get("background", {})
    action = manifest.get("action", {})
    icons = {str(size): str(icon_path) for size, icon_path in manifest.get("icons", {}).items()}
    action_icons = action.get("default_icon", {})
    if isinstance(action_icons, str) and action_icons:
        icons["action"] = action_icons
    elif isinstance(action_icons, dict):
        icons.update({f"action-{size}": str(icon_path) for size, icon_path in action_icons.items()})
    csp = manifest.get("content_security_policy", {})
    web_accessible = [
        resource
        for entry in manifest.get("web_accessible_resources", [])
        for resource in entry.get("resources", [])
    ]
    known_keys = {
        "manifest_version", "name", "version", "description", "permissions",
        "optional_permissions", "host_permissions", "optional_host_permissions",
        "content_scripts", "background", "action", "icons", "web_accessible_resources",
        "content_security_policy", "key", "default_locale", "minimum_chrome_version",
    }
    return ExtensionPackage(
        path=path,
        name=manifest["name"].strip(),
        version=manifest["version"].strip(),
        description=manifest.get("description", "").strip(),
        permissions=_string_tuple(manifest, "permissions"),
        optional_permissions=_string_tuple(manifest, "optional_permissions"),
        host_permissions=_string_tuple(manifest, "host_permissions"),
        optional_host_permissions=_string_tuple(manifest, "optional_host_permissions"),
        content_script_matches=tuple(dict.fromkeys(content_matches)),
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        manifest_version=int(manifest["manifest_version"]),
        background_service_worker=str(background.get("service_worker", "")),
        action_popup=str(action.get("default_popup", "")),
        icons=tuple(sorted(icons.items())),
        web_accessible_resources=tuple(dict.fromkeys(web_accessible)),
        content_security_policy=(
            str(csp.get("extension_pages", "")) if isinstance(csp, dict) else csp
        ),
        other_manifest_keys=tuple(sorted(str(key) for key in manifest if key not in known_keys)),
        manifest_key=str(manifest.get("key", "")),
    )
