"""Browser settings affect real window and WebEngine behavior."""

import sys

from PySide6.QtCore import QSettings, QEventLoop, QTimer, QPoint, Qt
from PySide6.QtGui import QColor, QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from browser.storage.settings import BrowserSettings, StartupSettings
from browser.ui.main_window import MainWindow
from browser.ui.settings_window import SettingsWindow
from browser.ui.theme_manager import ThemeManager
from browser.ui.theme_palette import build_palette

app = QApplication.instance() or QApplication(sys.argv)


def test_theme_and_accent_apply_to_qt_application(tmp_path):
    settings = BrowserSettings(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))
    manager = ThemeManager(settings)
    settings.set("appearance/theme", "dark")
    manager.apply()
    assert "#202124" in app.styleSheet()
    settings.set("appearance/accent_color", "purple")
    manager.apply()
    assert "#9334e6" in app.styleSheet().lower()


def test_search_routing_zoom_defaults_and_independent_tab_zoom(tmp_path):
    window = MainWindow(initial_url="about:blank")
    prefs = BrowserSettings(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))
    window._browser_settings = prefs
    prefs.set("search/default_provider", "DuckDuckGo")
    prefs.set("web/default_zoom", 125)
    window.navigate_to("settings integration query")
    assert window.web_view.url().host() == "duckduckgo.com"
    restored=BrowserSettings(QSettings(str(tmp_path/"prefs.ini"),QSettings.Format.IniFormat))
    assert restored.search_provider()=="DuckDuckGo"
    assert restored.default_zoom()==1.25
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


def test_settings_shortcut_binding_persists_and_runs_action(tmp_path):
    window=MainWindow(initial_url="about:blank")
    prefs=BrowserSettings(QSettings(str(tmp_path/"shortcuts.ini"),QSettings.Format.IniFormat))
    startup=StartupSettings(prefs.store)
    window._browser_settings=prefs;window._startup_settings=startup
    settings=SettingsWindow(prefs,startup,window)
    settings.sidebar.setCurrentRow(7)
    settings.shortcut_edits["new_tab"][0].setKeySequence(QKeySequence("Ctrl+Shift+Y"))
    settings._save_shortcuts()
    restored=BrowserSettings(QSettings(str(tmp_path/"shortcuts.ini"),QSettings.Format.IniFormat))
    assert restored.get("shortcuts/new_tab")=="Ctrl+Shift+Y"
    before=window.tab_manager.count()
    shortcut=window.shortcut_manager.get_shortcut("Ctrl+Shift+Y")
    assert shortcut is not None
    shortcut.activated.emit()
    assert window.tab_manager.count()==before+1
    settings.close()


def test_theme_preview_cancel_and_apply_persist_without_reloading_tabs(tmp_path):
    window=MainWindow(initial_url="about:blank")
    prefs=BrowserSettings(QSettings(str(tmp_path/"appearance.ini"),QSettings.Format.IniFormat))
    startup=StartupSettings(prefs.store)
    window._browser_settings=prefs;window._startup_settings=startup;window._theme_manager=ThemeManager(prefs)
    tab_count=window.tab_manager.count()
    settings=SettingsWindow(prefs,startup,window)
    settings.sidebar.setCurrentRow(1);settings.theme.setCurrentText("Custom");settings._sync_color_inputs(QColor("#8B3A62"));settings._preview_selected_mode("Custom")
    settings._theme_preview_timer.stop();settings._apply_pending_theme_preview();settings.show();app.processEvents()
    settings.grab().save(str(tmp_path/"appearance-settings.png"))
    settings.theme.setCurrentText("Custom")
    settings._sync_color_inputs(QColor("#8B3A62"))
    settings._preview_selected_mode("Custom")
    settings._theme_preview_timer.stop();settings._apply_pending_theme_preview()
    assert "#8b3a62" in app.styleSheet().lower()
    assert prefs.theme()=="system"  # preview is not committed
    settings._cancel_theme_preview()
    assert prefs.theme()=="system"
    settings.theme.setCurrentText("Custom")
    settings._sync_color_inputs(QColor("#8B3A62"))
    settings._apply_theme()
    assert prefs.theme()=="custom"
    assert prefs.custom_theme_color()=="#8b3a62"
    restored=BrowserSettings(QSettings(str(tmp_path/"appearance.ini"),QSettings.Format.IniFormat))
    assert restored.theme()=="custom" and restored.custom_theme_color()=="#8b3a62"
    assert window.tab_manager.count()==tab_count
    assert build_palette(prefs.custom_theme_color(),True).accent_color=="#8b3a62"
    settings._reset_theme()
    assert prefs.theme()=="system"
    assert prefs.accent()=="blue"
    settings.close()


def test_hue_ring_mouse_input_updates_hex_and_rgb(tmp_path):
    window=MainWindow(initial_url="about:blank")
    prefs=BrowserSettings(QSettings(str(tmp_path/"wheel.ini"),QSettings.Format.IniFormat))
    startup=StartupSettings(prefs.store)
    window._browser_settings=prefs;window._startup_settings=startup;window._theme_manager=ThemeManager(prefs)
    settings=SettingsWindow(prefs,startup,window)
    settings.sidebar.setCurrentRow(1);settings.theme.setCurrentText("Custom");settings.show();app.processEvents()
    QTest.mouseClick(settings.hue_wheel,Qt.MouseButton.LeftButton,pos=QPoint(66,15))
    app.processEvents()
    color=QColor(settings.hex_edit.text())
    assert color.isValid() and color.red()>220 and color.green()<40 and color.blue()<40
    assert [spin.value() for spin in settings.rgb_spins]==[color.red(),color.green(),color.blue()]
    settings.close()


def test_new_tab_channel_loads_shortcuts_and_theme_updates_without_reload(tmp_path):
    window=MainWindow()
    window.resize(1180,760);window.show();app.processEvents()
    view=window.web_view
    finished=[];view.loadFinished.connect(lambda ok:finished.append(ok))
    loop=QEventLoop();timeout=QTimer();timeout.setSingleShot(True);timeout.timeout.connect(loop.quit);timeout.start(8000)
    if not finished:loop.exec()
    timeout.stop();assert finished
    result=[]
    view.page().runJavaScript("typeof bridge + '|' + document.getElementById('shortcuts').children.length",lambda value:(result.append(value),loop.quit()))
    timeout.start(3000);loop.exec();timeout.stop()
    assert result and result[0].startswith("object|")
    app.processEvents();window.grab().save(str(tmp_path/"lightmq-new-tab.png"))
    load_count=len(finished)
    palette=build_palette("#8b3a62",dark=True)
    view.update_start_page_theme(palette)
    QTimer.singleShot(100,loop.quit);loop.exec()
    assert len(finished)==load_count


def test_three_dot_menu_actions_and_responsive_browser_shell(tmp_path):
    window=MainWindow(initial_url="about:blank")
    window.resize(1180,760);window.show();app.processEvents()
    window.grab().save(str(tmp_path/"lightmq-browser.png"))
    assert window.address_bar.objectName()=="addressBar"
    assert window.btn_browser_menu.property("lightmqIconName")=="menu"
    assert not window.btn_browser_menu.icon().isNull()
    texts=[action.text() for action in window.btn_browser_menu.menu().actions()]
    assert any(text.startswith("New Tab") for text in texts)
    assert any(text.startswith("New Incognito Window") for text in texts)
    for action in window.btn_browser_menu.menu().actions():
        if action.text() and not action.isSeparator():
            assert not action.icon().isNull(),action.text()
    bookmark_menu=next(action.menu() for action in window.btn_browser_menu.menu().actions() if action.text()=="Bookmarks")
    assert all(not action.icon().isNull() for action in bookmark_menu.actions() if action.menu())
    saved_bookmark_action=next(action for action in window.saved_bookmarks_menu.actions() if action.text().startswith("Bookmark this page"))
    assert not saved_bookmark_action.icon().isNull()
    window.btn_browser_menu.showMenu();app.processEvents()
    window.btn_browser_menu.menu().grab().save(str(tmp_path/"lightmq-menu.png"))
    window.btn_browser_menu.menu().hide()
    count=window.tab_manager.count()
    next(action for action in window.btn_browser_menu.menu().actions() if action.text().startswith("New Tab")).trigger()
    assert window.tab_manager.count()==count+1
