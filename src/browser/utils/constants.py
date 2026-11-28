"""Application constants and engine metadata helpers for LightMq Browser."""

import sys
from PySide6.QtCore import qVersion
from PySide6.QtWebEngineCore import qWebEngineChromiumVersion
import PySide6
from browser.webengine.web_profile import WebProfileManager

APP_NAME = "LightMq Browser"
from browser.version import __version__

APP_VERSION = __version__
DEFAULT_START_URL = "lightmq://newtab"


def get_bundled_chromium_version() -> str:
    """Extract the bundled Chromium version from Qt WebEngine's default User-Agent.

    Returns:
        str: Chromium version string (e.g. '140.0.0.0') or 'Unknown'.
    """
    try:
        return qWebEngineChromiumVersion() or "Unknown"
    except Exception:
        return "Unknown"


def get_engine_diagnostics() -> dict[str, str]:
    """Retrieve verified environment, Qt, PySide6, and Chromium engine versions.

    Returns:
        dict: Mapping of subsystem labels to version numbers.
    """
    ua = "Unknown"
    try:
        ua = WebProfileManager.default_profile().httpUserAgent()
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
    profile = WebProfileManager.diagnostics(WebProfileManager.default_profile())
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
        f" Profile Name:           {profile['profile_name']}\n"
        f" Off the Record:         {profile['off_the_record']}\n"
        f" Persistent Storage:     {profile['persistent_storage_path']}\n"
        f" Cache Path:             {profile['cache_path']}\n"
        f" Cookie Policy:          {profile['cookie_policy']}\n"
        f" HTTP Cache Type:        {profile['http_cache_type']}\n"
        f" Qt WebEngine Version:   {profile['qt_webengine_version']}\n"
        f" PySide6 Version:        {profile['pyside6_version']}\n"
        "----------------------------------------------------------\n"
        "=========================================================="
    )
