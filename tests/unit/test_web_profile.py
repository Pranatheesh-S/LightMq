"""Tests for persistent profile configuration and tab sharing."""

from pathlib import Path

from PySide6.QtWebEngineCore import QWebEngineProfile
from PySide6.QtWidgets import QApplication

from browser.ui.main_window import MainWindow
from browser.webengine.web_profile import WebProfileManager


def test_named_profile_uses_separate_stable_storage_and_disk_cache(tmp_path):
    """The profile factory configures a named, persistent, disk-backed profile."""
    app = QApplication.instance()
    assert app is not None

    root = tmp_path / "Browser" / "Profiles" / "Default"
    profile = WebProfileManager.create_persistent_profile(root, app)
    try:
        assert profile.storageName() == "Default"
        assert profile.isOffTheRecord() is False
        assert Path(profile.persistentStoragePath()) == root / "Storage"
        assert Path(profile.cachePath()) == root / "Cache"
        assert profile.persistentCookiesPolicy() == (
            QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
        )
        assert profile.httpCacheType() == QWebEngineProfile.HttpCacheType.DiskHttpCache
        assert Path(profile.persistentStoragePath()).is_dir()
        assert Path(profile.cachePath()).is_dir()
    finally:
        profile.deleteLater()
        app.processEvents()


def test_normal_tabs_and_windows_share_the_persistent_profile():
    """Normal pages share one profile object; closing a tab leaves it alive."""
    first = MainWindow(initial_url="about:blank")
    profile = WebProfileManager.default_profile()
    second_view = first.tab_manager.create_tab("about:blank")
    second = MainWindow(initial_url="about:blank")

    assert first.web_view.page().profile() is profile
    assert second_view.page().profile() is profile
    assert second.web_view.page().profile() is profile

    first.tab_manager.close_tab(1)
    assert WebProfileManager.default_profile() is profile
    assert first.web_view.page().profile() is profile


def test_profile_diagnostics_exclude_cookie_data(tmp_path):
    """Diagnostics report profile policy and engine versions without secrets."""
    app = QApplication.instance()
    profile = WebProfileManager.create_persistent_profile(tmp_path / "diagnostics", app)
    try:
        diagnostics = WebProfileManager.diagnostics(profile)
        assert diagnostics["profile_name"] == "Default"
        assert diagnostics["off_the_record"] == "False"
        assert diagnostics["cookie_policy"] == "ForcePersistentCookies"
        assert diagnostics["http_cache_type"] == "DiskHttpCache"
        assert diagnostics["qt_webengine_version"]
        assert diagnostics["chromium_version"]
        assert "cookie_values" not in diagnostics
    finally:
        profile.deleteLater()
        app.processEvents()
