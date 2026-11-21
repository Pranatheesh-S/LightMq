"""Formatting and path helpers for browser downloads."""

import math
import mimetypes
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

from PySide6.QtCore import QMimeDatabase, QStandardPaths

_MIME_DATABASE = QMimeDatabase()
_MIME_EXTENSION_OVERRIDES = {
    "application/acrobat": ".pdf",
    "application/x-pdf": ".pdf",
    "application/x-7z-compressed": ".7z",
    "application/x-bzip2": ".bz2",
    "application/x-font-ttf": ".ttf",
    "application/x-gzip": ".gz",
    "application/x-msdos-program": ".exe",
    "application/x-msdownload": ".exe",
    "application/x-rar-compressed": ".rar",
    "application/x-sqlite3": ".sqlite3",
    "application/x-tar": ".tar",
    "application/x-zip-compressed": ".zip",
    "application/vnd.rar": ".rar",
    "font/otf": ".otf",
    "font/ttf": ".ttf",
    "font/woff": ".woff",
    "font/woff2": ".woff2",
    "text/markdown": ".md",
    "text/yaml": ".yaml",
}


def safe_filename(name: str, fallback: str = "download") -> str:
    """Return a single safe filename component supplied by an untrusted server."""
    cleaned = name.replace("\x00", "").replace("\\", "/").split("/")[-1]
    cleaned = re.sub(r'[<>:"|?*]', "_", cleaned).strip(" .")
    if cleaned in {"", ".", ".."}:
        return fallback
    if re.match(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", cleaned, re.IGNORECASE):
        cleaned = f"_{cleaned}"
    return cleaned[:240]


def preserve_file_extension(
    filename: str,
    suggested_filename: str = "",
    mime_type: str = "",
    source_url: str = "",
) -> str:
    """Append the original format's extension when a chosen name has none."""
    clean_name = safe_filename(filename)
    if Path(clean_name).suffix:
        return clean_name

    suggested_suffix = Path(safe_filename(suggested_filename)).suffix
    mime = mime_type.split(";", maxsplit=1)[0].strip().lower()
    mime_suffix = _extension_for_mime(mime)
    url_path = safe_filename(unquote(urlsplit(source_url).path))
    url_suffix = Path(url_path).suffix
    extension = suggested_suffix or mime_suffix or url_suffix
    return f"{clean_name}{extension}" if extension else clean_name


def _extension_for_mime(mime_type: str) -> str | None:
    """Resolve known MIME aliases and structured suffix types to file extensions."""
    if mime_type in {"", "application/octet-stream", "binary/octet-stream"}:
        return None
    if mime_type in _MIME_EXTENSION_OVERRIDES:
        return _MIME_EXTENSION_OVERRIDES[mime_type]

    qt_mime_type = _MIME_DATABASE.mimeTypeForName(mime_type)
    if qt_mime_type.isValid() and qt_mime_type.preferredSuffix():
        return f".{qt_mime_type.preferredSuffix()}"

    extension = mimetypes.guess_extension(mime_type, strict=False)
    if extension:
        return extension

    structured_suffixes = {
        "+json": ".json",
        "+xml": ".xml",
        "+zip": ".zip",
        "+gzip": ".gz",
        "+cbor": ".cbor",
    }
    return next(
        (
            extension
            for suffix, extension in structured_suffixes.items()
            if mime_type.endswith(suffix)
        ),
        None,
    )


def default_download_directory() -> Path:
    """Return the operating system Downloads directory with a home fallback."""
    location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
    return Path(location) if location else Path.home() / "Downloads"


def format_size(byte_count: int) -> str:
    """Format a byte count for compact display."""
    if byte_count < 0:
        return "Unknown size"
    units = ("B", "KB", "MB", "GB", "TB")
    size = float(byte_count)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return "Unknown size"


def format_duration(seconds: float) -> str:
    """Format a nonnegative duration in seconds."""
    if not math.isfinite(seconds) or seconds < 0:
        return ""
    remaining = int(seconds)
    if remaining < 60:
        return f"{remaining} sec remaining"
    minutes, seconds_left = divmod(remaining, 60)
    if minutes < 60:
        return f"{minutes} min {seconds_left} sec remaining"
    hours, minutes_left = divmod(minutes, 60)
    return f"{hours} hr {minutes_left} min remaining"
