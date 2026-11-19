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

from PySide6.QtWidgets import QApplication
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

    # Handle --version flag
    if args.version:
        chromium_ver = get_bundled_chromium_version()
        print(f"{APP_NAME} v{APP_VERSION} (Chromium v{chromium_ver})")
        return 0

    # Handle --diagnostics flag
    if args.diagnostics:
        print(format_diagnostics_report())
        return 0

    window = MainWindow(initial_url=args.url)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
