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
    window.devtools_panel.dom.start_picker()
    assert window.devtools_panel.dom.picker_active
    second = window.tab_manager.create_tab("about:blank", activate=True)
    assert window.devtools_panel.current_page is second.page()
    assert not window.devtools_panel.dom.picker_active
    assert window.devtools_panel.dom._selected_data == {}
    assert second.page().devToolsPage() is chromium_page
    window.tab_manager.group_manager.create_group("Inspection", "blue")
    assert window.devtools_panel.current_page is second.page()
    window.tab_manager.close_current_tab()
    assert window.devtools_panel.current_page is not None


def test_inspector_panel_position_and_unsupported_document_message():
    window = MainWindow(initial_url="about:blank")
    window.show()
    panel = window.devtools_panel
    panel.position.setCurrentIndex(1)
    assert window.splitter.orientation().name == "Vertical"
    assert window._settings.value("devtools/panel_position") == "bottom"
    panel.position.setCurrentIndex(0)
    assert window.splitter.orientation().name == "Horizontal"
    panel.set_target_view(None)
    assert "unavailable" in panel.dom.status.text().lower()
    window.devtools_manager.open()
    window.splitter.setSizes([640, 260])
    window.devtools_manager._save_splitter_sizes()
    saved_sizes = window.devtools_manager._load_splitter_sizes()
    assert saved_sizes == window.splitter.sizes()
    window.devtools_manager.close()
    window.devtools_manager.open()
    assert window.devtools_manager._load_splitter_sizes() == saved_sizes
    assert all(size > 0 for size in window.splitter.sizes())
