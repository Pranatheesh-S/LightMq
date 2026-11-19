"""Application constants and engine metadata helpers for LightMq Browser."""

import re
import sys
from PySide6.QtCore import qVersion
from PySide6.QtWebEngineCore import QWebEngineProfile
import PySide6

APP_NAME = "LightMq Browser"
APP_VERSION = "0.1.0"
DEFAULT_START_URL = "https://example.com"


def get_bundled_chromium_version() -> str:
    """Extract the bundled Chromium version from Qt WebEngine's default User-Agent.

    Returns:
        str: Chromium version string (e.g. '140.0.0.0') or 'Unknown'.
    """
    try:
        ua = QWebEngineProfile.defaultProfile().httpUserAgent()
        match = re.search(r"Chrome/([0-9.]+)", ua)
        return match.group(1) if match else "Unknown"
    except Exception:
        return "Unknown"


def get_engine_diagnostics() -> dict[str, str]:
    """Retrieve verified environment, Qt, PySide6, and Chromium engine versions.

    Returns:
        dict: Mapping of subsystem labels to version numbers.
    """
    ua = "Unknown"
    try:
        ua = QWebEngineProfile.defaultProfile().httpUserAgent()
    except Exception:
        pass

    return {
        "application_name": APP_NAME,
        "application_version": APP_VERSION,
        "python_version": sys.version.split()[0],
        "pyside6_version": PySide6.__version__,
        "qt_version": qVersion(),
        "chromium_version": get_bundled_chromium_version(),
        "platform": f"{sys.platform} (64-bit)" if sys.maxsize > 2**32 else f"{sys.platform} (32-bit)",
        "user_agent": ua,
    }


def format_diagnostics_report() -> str:
    """Generate a clean ASCII diagnostics report for CLI output.

    Returns:
        str: Formatted diagnostics report.
    """
    info = get_engine_diagnostics()
    return (
        "==========================================================\n"
        " LightMq Browser - Engine & Environment Diagnostics\n"
        "==========================================================\n"
        f" Application:            {info['application_name']} v{info['application_version']}\n"
        f" Python Runtime:         {info['python_version']}\n"
        f" PySide6 Framework:      {info['pyside6_version']}\n"
        f" Qt Core Library:        {info['qt_version']}\n"
        f" Bundled Chromium Engine:{info['chromium_version']}\n"
        f" Host Platform:          {info['platform']}\n"
        "----------------------------------------------------------\n"
        f" Default User-Agent:\n"
        f"   {info['user_agent']}\n"
        "=========================================================="
    )
