"""Custom diagnostics follow active tabs without displacing Chromium DevTools."""

import sys

from PySide6.QtWidgets import QApplication

from browser.ui.main_window import MainWindow

app = QApplication.instance() or QApplication(sys.argv)


def test_custom_tools_track_active_page_and_chromium_devtools_stays_attached():
    window = MainWindow(initial_url="about:blank")
    first = window.web_view
    assert first is not None
    window.devtools_manager.open()
    chromium_page = window.devtools_panel.get_page()
    assert first.page().devToolsPage() is chromium_page
    window.devtools_panel.mode.setCurrentIndex(1)
    assert not window.devtools_panel.tools.isHidden()
    second = window.tab_manager.create_tab("about:blank", activate=True)
    assert window.devtools_panel.current_page is second.page()
    assert second.page().devToolsPage() is chromium_page
    window.tab_manager.group_manager.create_group("Inspection", "blue")
    assert window.devtools_panel.current_page is second.page()
    window.tab_manager.close_current_tab()
    assert window.devtools_panel.current_page is not None
