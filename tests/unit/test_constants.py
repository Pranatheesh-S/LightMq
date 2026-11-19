"""Unit tests for browser constants, engine version detection, and diagnostics."""

import sys
from PySide6.QtWidgets import QApplication

from browser.utils.constants import (
    APP_NAME,
    APP_VERSION,
    format_diagnostics_report,
    get_bundled_chromium_version,
    get_engine_diagnostics,
)

app = QApplication.instance() or QApplication(sys.argv)


def test_bundled_chromium_version_detection():
    """Verify that bundled Chromium version is extracted from the default WebEngine profile."""
    version = get_bundled_chromium_version()
    assert version != "Unknown"
    # Chromium version format: major.minor.build.patch
    parts = version.split(".")
    assert len(parts) >= 2
    assert int(parts[0]) >= 100  # Modern Chromium is v100+


def test_get_engine_diagnostics():
    """Verify that engine diagnostics dictionary contains all expected keys."""
    diag = get_engine_diagnostics()
    assert diag["application_name"] == APP_NAME
    assert diag["application_version"] == APP_VERSION
    assert diag["pyside6_version"] != ""
    assert diag["qt_version"] != ""
    assert diag["chromium_version"] != "Unknown"
    assert "Chrome/" in diag["user_agent"]


def test_format_diagnostics_report():
    """Verify that ASCII diagnostics report formats cleanly with engine specifications."""
    report = format_diagnostics_report()
    assert "LightMq Browser - Engine & Environment Diagnostics" in report
    assert "Bundled Chromium Engine:" in report
    assert "PySide6 Framework:" in report
    assert "Qt Core Library:" in report
