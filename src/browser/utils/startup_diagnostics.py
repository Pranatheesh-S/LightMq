"""Local, bounded, metadata-only startup diagnostics for GUI releases."""

import logging
from logging.handlers import RotatingFileHandler
import sys
from pathlib import Path

import PySide6
from PySide6.QtCore import QLibraryInfo, qVersion
from PySide6.QtWebEngineCore import qWebEngineChromiumVersion
from PySide6.QtWidgets import QMessageBox

from browser.utils.paths import app_data_directory, resource_path
from browser.version import __version__


def missing_runtime_components() -> list[str]:
    """Use Qt's deployed paths to report missing helpers and bundled resources."""
    qt_data = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.DataPath))
    qt_helpers = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.LibraryExecutablesPath))
    required = {
        'WebEngine helper': qt_helpers / 'QtWebEngineProcess.exe',
        'Chromium resources': qt_data / 'resources/qtwebengine_resources.pak',
        'Chromium ICU data': qt_data / 'resources/icudtl.dat',
        'Light theme': resource_path('ui/themes/light.qss'),
        'Dark theme': resource_path('ui/themes/dark.qss'),
        'Application icon': resource_path('resources/lightmq.ico'),
    }
    return [label for label, path in required.items() if not path.is_file()]


def configure_startup_logging() -> None:
    """Keep exception text, URLs, and document paths out of startup logs."""
    directory = app_data_directory() / "logs"
    directory.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("lightmq.startup")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        handler = RotatingFileHandler(directory / "startup.log", maxBytes=262144, backupCount=2, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        logger.addHandler(handler)
    logger.info("LightMq %s Python %s PySide6 %s Qt %s frozen=%s", __version__, sys.version.split()[0], PySide6.__version__, qVersion(), bool(getattr(sys, "frozen", False)))
    logger.info('Chromium %s', qWebEngineChromiumVersion())
    if getattr(sys, 'frozen', False):
        missing = missing_runtime_components()
        if missing:
            logger.error('Missing components: %s', ', '.join(missing))
            QMessageBox.critical(None, 'Incomplete LightMq installation',
                                 'Reinstall LightMq to restore missing components:\n' + '\n'.join(missing))
            raise SystemExit(2)

    def report_error(kind: type, value: BaseException, traceback: object) -> None:
        logger.error("Unhandled exception type=%s", kind.__name__)
        QMessageBox.critical(None, "LightMq error", "LightMq encountered an unexpected error. Local startup diagnostics record the error type; no browsing details are logged.")

    sys.excepthook = report_error
