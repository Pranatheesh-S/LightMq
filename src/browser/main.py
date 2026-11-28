"""Application entry point for LightMq Browser.

Initializes the PySide6 application, parses command-line arguments (including
engine diagnostics), and launches the main browser desktop window.
"""

import argparse
import sys
from pathlib import Path

# Ensure 'src' directory is in sys.path when executed directly as a script file
src_dir = str(Path(__file__).resolve().parent.parent)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QUrl
from PySide6.QtGui import QIcon
from browser.utils.paths import resource_path
from browser.core.session_manager import SessionManager
from browser.storage.settings import StartupMode, StartupSettings
from browser.ui.main_window import MainWindow
from browser.utils.constants import (
    APP_NAME,
    APP_VERSION,
    format_diagnostics_report,
    get_bundled_chromium_version,
)


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="LightMq - Python Desktop Web Browser")
    parser.add_argument(
        "url",
        nargs="?",
        default=None,
        help="Optional initial URL or website address to open on startup",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="store_true",
        help="Display application and Chromium engine version and exit",
    )
    parser.add_argument(
        "--diagnostics",
        "--diag",
        action="store_true",
        help="Display comprehensive engine and environment diagnostics and exit",
    )
    return parser.parse_args()


def main() -> int:
    """Main application lifecycle entry point.

    Returns:
        int: Exit status code.
    """
    args = parse_arguments()

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    app.setApplicationName(APP_NAME)
    app.setOrganizationName("LightMq")
    app.setApplicationVersion(APP_VERSION)
    app.setWindowIcon(QIcon(str(resource_path("resources/lightmq.ico"))))

    # Handle --version flag
    if args.version:
        chromium_ver = get_bundled_chromium_version()
        print(f"{APP_NAME} v{APP_VERSION} (Chromium v{chromium_ver})")
        return 0

    # Handle --diagnostics flag
    if args.diagnostics:
        print(format_diagnostics_report())
        return 0

    from browser.utils.startup_diagnostics import configure_startup_logging
    configure_startup_logging()

    local_document = None
    if args.url is not None:
        candidate = Path(args.url).expanduser()
        if candidate.is_file():
            candidate = candidate.resolve()
            if candidate.suffix.lower() == ".xlsx":
                local_document = candidate
                args.url = "lightmq://newtab"
            elif candidate.suffix.lower() in {".pdf", ".html", ".htm"}:
                args.url = QUrl.fromLocalFile(str(candidate)).toString()
            else:
                QMessageBox.warning(None, "Unsupported file", "Supported local files: PDF, XLSX, HTML, HTM.")
                return 2
        elif candidate.is_absolute() or args.url.lower().startswith("file:"):
            QMessageBox.warning(None, "File unavailable", "The requested local file does not exist or cannot be opened.")
            return 2

    session_manager = SessionManager(parent=app)
    crashed, recovery_snapshot = session_manager.begin_run()
    startup_settings = StartupSettings()
    restore_snapshot = None
    initial_url = args.url

    if initial_url is None and crashed:
        if recovery_snapshot is not None:
            prompt = QMessageBox()
            prompt.setWindowTitle("Recover Previous Tabs?")
            prompt.setIcon(QMessageBox.Icon.Warning)
            prompt.setText("LightMq did not close normally last time.")
            prompt.setInformativeText("Restore tabs from the crash recovery snapshot?")
            restore_button = prompt.addButton("Restore Tabs", QMessageBox.ButtonRole.AcceptRole)
            prompt.addButton("Start Fresh", QMessageBox.ButtonRole.DestructiveRole)
            prompt.setDefaultButton(restore_button)
            prompt.exec()
            if prompt.clickedButton() is restore_button:
                restore_snapshot = recovery_snapshot
            else:
                initial_url = _startup_url(startup_settings)
        else:
            initial_url = _startup_url(startup_settings)
    elif initial_url is None:
        if startup_settings.restore_previous_session():
            repository = session_manager.repository
            restore_snapshot = repository.load_current() or repository.load_recovery()
        else:
            initial_url = _startup_url(startup_settings)

    window = MainWindow(
        initial_url=initial_url,
        session_manager=session_manager,
        restore_snapshot=restore_snapshot,
    )
    window.show()
    if local_document is not None:
        window.open_local_document(str(local_document))

    return app.exec()


def _startup_url(settings: StartupSettings) -> str:
    """Return the initial page selected in startup preferences."""
    if settings.fallback_mode() is StartupMode.HOMEPAGE:
        return settings.homepage()
    from browser.utils.constants import DEFAULT_START_URL

    return DEFAULT_START_URL


if __name__ == "__main__":
    sys.exit(main())
