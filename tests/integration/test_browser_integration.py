"""Integration tests for MainWindow, WebView, and DevTools integration."""

import sys
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication

from browser.features.history.history_manager import HistoryManager
from browser.ui.dialogs.clear_data_dialog import ClearDataDialog
from browser.ui.dialogs.privacy_settings_dialog import PrivacySettingsDialog
from browser.ui.main_window import MainWindow

app = QApplication.instance() or QApplication(sys.argv)


def test_main_window_components():
    """Verify MainWindow initializes all required subcomponents."""
    window = MainWindow(initial_url="about:blank")
    assert window.web_view is not None
    assert window.devtools_panel is not None
    assert window.devtools_manager is not None
    assert window.address_bar is not None
    assert window.btn_go is not None
    assert window.btn_devtools is not None
    assert window.btn_about is not None
    assert window.splitter is not None


def test_navigation_triggers_webview():
    """Verify navigate_to normalizes URL and updates WebView."""
    window = MainWindow(initial_url="about:blank")
    window.navigate_to("example.com")
    assert window.web_view.url() == QUrl("https://example.com")


def test_devtools_toggle_and_lifecycle():
    """Verify Developer Tools can be opened, closed, and repeatedly toggled safely."""
    window = MainWindow(initial_url="about:blank")
    manager = window.devtools_manager
    panel = window.devtools_panel

    # Initial state: panel is hidden
    assert panel.isHidden() is True
    assert manager.is_open() is False

    # Open DevTools
    manager.open()
    assert panel.isHidden() is False
    assert manager.is_open() is True
    assert window.btn_devtools.isChecked() is True

    # Close DevTools
    manager.close()
    assert panel.isHidden() is True
    assert manager.is_open() is False
    assert window.btn_devtools.isChecked() is False

    # Repeatedly toggle 20 times to ensure stability and zero crashes
    for _ in range(20):
        manager.toggle()
        manager.toggle()

    assert panel.isHidden() is True
    assert manager.is_open() is False


def test_devtools_page_attachment():
    """Verify DevTools page is attached to the active web page."""
    window = MainWindow(initial_url="about:blank")
    panel = window.devtools_panel
    devtools_page = panel.get_page()

    assert devtools_page is not None
    assert window.web_view.page().devToolsPage() == devtools_page


def test_title_change_updates_window():
    """Verify webpage title updates the MainWindow title."""
    window = MainWindow(initial_url="about:blank")
    window._on_title_changed("Test Webpage")
    assert window.windowTitle() == "Test Webpage - LightMq Browser"

    window._on_title_changed("")
    assert window.windowTitle() == "LightMq Browser"


def test_successful_tab_navigation_is_written_to_history(tmp_path):
    """The main-window loadFinished handler commits the pending navigation once."""
    previous_manager = HistoryManager._instance
    manager = HistoryManager(storage_path=tmp_path / "history.sqlite3")
    HistoryManager._instance = manager
    window = MainWindow(initial_url="about:blank")
    try:
        view = window.web_view
        assert view is not None
        view.setUrl(QUrl("https://history-test.example/path"))
        view.page().main_frame_navigation_requested.emit("https://history-test.example/path", "typed")

        window._on_tab_load_finished(view, True)
        window._on_tab_load_finished(view, True)

        visits = manager.get_entries()
        assert len(visits) == 1
        assert visits[0]["url"] == "https://history-test.example/path"
        assert visits[0]["visit_type"] == "typed"
    finally:
        window.close()
        HistoryManager._instance = previous_manager


def test_privacy_settings_and_clear_data_dialogs_initialize():
    """Normal windows expose profile privacy settings and supported clear options."""
    window = MainWindow(initial_url="about:blank")
    try:
        assert window.btn_privacy is not None
        view = window.web_view
        assert view is not None
        assert id(view.page()) in window._permission_handler._attached_pages

        settings = PrivacySettingsDialog(
            window._privacy_manager, window.open_clear_data, window,
        )
        assert settings.tabs.count() == 3
        assert settings.cookie_table.columnCount() == 7
        assert settings.permission_table.columnCount() == 4

        clear_dialog = ClearDataDialog(window)
        assert clear_dialog.clear_history is True
        assert clear_dialog.clear_cookies is True
        assert clear_dialog.clear_cache is True
        assert clear_dialog.clear_permissions is False
        assert clear_dialog.history_range() == (None, None)
        settings.close()
        clear_dialog.close()
    finally:
        window.close()
