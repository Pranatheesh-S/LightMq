"""Load safe local raster extension icons without executing SVG content."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QSize, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QImage, QImageReader, QPixmap
import stat
import zipfile

from browser.features.extensions.package_inspector import ExtensionPackage


_SAFE_RASTER_FORMATS = {b"png", b"jpeg", b"webp", b"bmp", b"gif"}
_MAX_ICON_BYTES = 2 * 1024 * 1024
_MAX_ICON_DIMENSION = 8192
_MAX_ICON_PIXELS = 40_000_000


def load_extension_icon(package: ExtensionPackage | None) -> QIcon:
    """Return an icon only from a bounded raster manifest resource."""
    if package is None:
        return QIcon()
    root = package.path.resolve(strict=False)
    for _size, resource in sorted(package.icons, key=lambda pair: _icon_rank(pair[0])):
        try:
            relative = PurePosixPath(resource.replace("\\", "/"))
            if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
                continue
            if root.is_dir():
                path = root.joinpath(*relative.parts).resolve(strict=True)
                if not path.is_relative_to(root) or not path.is_file():
                    continue
                if path.stat().st_size > _MAX_ICON_BYTES:
                    continue
                reader = QImageReader(str(path))
                reader.setDecideFormatFromContent(True)
                image = _read_scaled(reader)
            elif package.path.suffix.lower() == ".zip":
                with zipfile.ZipFile(package.path) as archive:
                    info = archive.getinfo(relative.as_posix())
                    file_type = stat.S_IFMT(info.external_attr >> 16)
                    if (info.is_dir() or info.file_size > _MAX_ICON_BYTES
                            or file_type not in (0, stat.S_IFREG)):
                        continue
                    buffer_data = QByteArray(archive.read(info))
                buffer = QBuffer(buffer_data)
                if not buffer.open(QIODevice.OpenModeFlag.ReadOnly):
                    continue
                reader = QImageReader(buffer)
                reader.setDecideFormatFromContent(True)
                image = _read_scaled(reader)
                buffer.close()
            else:
                continue
            if image.isNull():
                continue
            pixmap = QPixmap.fromImage(image)
            screen = QGuiApplication.primaryScreen()
            if screen is not None:
                pixmap.setDevicePixelRatio(float(screen.devicePixelRatio()))
            return QIcon(pixmap)
        except (OSError, RuntimeError, ValueError, KeyError, zipfile.BadZipFile):
            continue
    return QIcon()


def _read_scaled(reader: QImageReader) -> QImage:
    """Decode only supported raster data and bound the decoded dimensions."""
    if bytes(reader.format()).lower() not in _SAFE_RASTER_FORMATS:
        return QImage()
    dimensions = reader.size()
    if (not dimensions.isValid() or dimensions.width() > _MAX_ICON_DIMENSION or
            dimensions.height() > _MAX_ICON_DIMENSION or
            dimensions.width() * dimensions.height() > _MAX_ICON_PIXELS):
        return QImage()
    reader.setScaledSize(dimensions.scaled(
        QSize(64, 64), Qt.AspectRatioMode.KeepAspectRatio
    ))
    return reader.read()


def _icon_rank(size: str) -> tuple[int, int]:
    """Prefer icons closest to 64 px while tolerating arbitrary manifest keys."""
    try:
        number = int(size)
        return abs(number - 64), number
    except ValueError:
        return 10_000, 0
