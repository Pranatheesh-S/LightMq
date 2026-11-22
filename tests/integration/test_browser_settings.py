"""Browser settings affect real window and WebEngine behavior."""

import sys

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from browser.storage.settings import BrowserSettings
from browser.ui.main_window import MainWindow
from browser.ui.theme_manager import ThemeManager

app = QApplication.instance() or QApplication(sys.argv)


def test_theme_and_accent_apply_to_qt_application(tmp_path):
    settings = BrowserSettings(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))
    manager = ThemeManager(settings)
    settings.set("appearance/theme", "dark")
    manager.apply()
    assert "#202124" in app.styleSheet()
    settings.set("appearance/accent_color", "purple")
    manager.apply()
    assert "#9334E6" in app.styleSheet()


def test_search_routing_zoom_defaults_and_independent_tab_zoom(tmp_path):
    window = MainWindow(initial_url="about:blank")
    prefs = BrowserSettings(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))
    window._browser_settings = prefs
    prefs.set("search/default_provider", "DuckDuckGo")
    window.navigate_to("settings integration query")
    assert window.web_view.url().host() == "duckduckgo.com"
    prefs.set("web/default_zoom", 125)
    first = window.new_tab()
    second = window.new_tab()
    assert first.zoomFactor() == 1.25
    assert second.zoomFactor() == 1.25
    first.setZoomFactor(1.5)
    assert second.zoomFactor() == 1.25


def test_custom_shortcut_changes_live_binding_and_action():
    window = MainWindow(initial_url="about:blank")
    before = window.tab_manager.count()
    assert window.shortcut_manager.apply_custom({"new_tab": "Ctrl+Shift+Y"})
    custom = window.shortcut_manager.get_shortcut("Ctrl+Shift+Y")
    assert custom is not None
    custom.activated.emit()
    assert window.tab_manager.count() == before + 1
