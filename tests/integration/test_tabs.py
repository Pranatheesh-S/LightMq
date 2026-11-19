"""Integration tests for multiple tabs and Chromium DevTools lifecycle."""

import sys
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication

from browser.ui.main_window import MainWindow

app = QApplication.instance() or QApplication(sys.argv)


def test_main_window_tab_creation():
    """Verify tabs can be created through TabBar and TabManager."""
    window = MainWindow(initial_url="about:blank")
    assert window.tab_manager.count() == 1
    assert window.tab_bar.count() == 1

    # Create second tab
    window.tab_manager.create_tab("https://github.com", activate=True)
    assert window.tab_manager.count() == 2
    assert window.tab_bar.count() == 2
    assert window.tab_manager.current_index() == 1
    assert window.stacked_widget.count() == 2


def test_tab_switching_synchronizes_ui():
    """Verify switching tabs updates address bar, window title, and active viewport."""
    window = MainWindow(initial_url="https://tab1.com")
    v2 = window.tab_manager.create_tab("https://tab2.com", activate=True)

    # Active tab is tab 2
    assert window.address_bar.text() == "https://tab2.com"

    # Switch back to tab 1
    window.tab_manager.set_current_index(0)
    assert window.address_bar.text() == "https://tab1.com"
    assert window.tab_bar.current_index() == 0


def test_background_tab_does_not_overwrite_active_address_bar():
    """Verify that a background tab title/URL event never overwrites active tab state."""
    window = MainWindow(initial_url="https://active.com")
    bg_view = window.tab_manager.create_tab("https://background.com", activate=False)

    # Active tab is still index 0
    assert window.tab_manager.current_index() == 0
    assert window.address_bar.text() == "https://active.com"

    # Simulate background tab URL and title change
    window._on_tab_url_changed(bg_view, QUrl("https://background-redirected.com"))
    window._on_tab_title_changed(bg_view, "Background Title")

    # Active address bar and window title must remain unchanged!
    assert window.address_bar.text() == "https://active.com"
    assert "Background Title" not in window.windowTitle()

    # But TabBar label for background tab must update!
    assert window.tab_bar._tab_bar.tabText(1) == "Background Title"


def test_devtools_switches_across_tabs():
    """Verify DevTools reattaches to active tab when switching tabs."""
    window = MainWindow(initial_url="https://tab1.com")
    v1 = window.tab_manager.current_view()
    v2 = window.tab_manager.create_tab("https://tab2.com", activate=True)

    manager = window.devtools_manager
    manager.open()
    assert manager.is_open() is True

    # DevTools should inspect tab 2 (active)
    devtools_page = window.devtools_panel.get_page()
    assert v2.page().devToolsPage() == devtools_page
    assert v1.page().devToolsPage() is None

    # Switch back to tab 1
    window.tab_manager.set_current_index(0)

    # DevTools should now inspect tab 1
    assert v1.page().devToolsPage() == devtools_page
    assert v2.page().devToolsPage() is None


def test_closing_inspected_tab_safety():
    """Verify closing the currently inspected tab detaches DevTools without crash."""
    window = MainWindow(initial_url="https://tab1.com")
    v1 = window.tab_manager.current_view()
    v2 = window.tab_manager.create_tab("https://tab2.com", activate=True)

    manager = window.devtools_manager
    manager.open()

    # Close active tab 2 (which is being inspected)
    window.tab_manager.close_tab(1)

    # Browser must remain stable, DevTools re-attaches to tab 1
    assert window.tab_manager.count() == 1
    assert window.tab_manager.current_view() is v1
    devtools_page = window.devtools_panel.get_page()
    assert v1.page().devToolsPage() == devtools_page


def test_closing_all_tabs_recreates_fresh_tab():
    """Verify closing the final tab creates a new blank tab rather than crashing."""
    window = MainWindow(initial_url="https://last.com")
    assert window.tab_manager.count() == 1

    window.tab_manager.close_tab(0)

    assert window.tab_manager.count() == 1
    assert window.tab_manager.current_view() is not None
    assert window.tab_bar.count() == 1
