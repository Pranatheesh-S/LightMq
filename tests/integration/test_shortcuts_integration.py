"""Integration tests for LightMq browser keyboard shortcuts.

Tests command dispatching, multi-window isolation, tab operations, navigation controls,
find-in-page, zoom bounds, bookmarks bar toggling, and DevTools shortcuts.
"""

import sys
from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import QApplication

from browser.features.bookmarks.bookmark_manager import BookmarkManager
from browser.ui.main_window import MainWindow
from browser.utils.constants import DEFAULT_START_URL

app = QApplication.instance() or QApplication(sys.argv)


def test_tab_shortcuts_integration():
    """Verify Ctrl+T, Ctrl+W, Ctrl+Shift+T, Ctrl+Tab, Ctrl+Shift+Tab, Ctrl+1..9."""
    win = MainWindow()

    assert win.tab_manager.count() == 1

    # 1. New Tab (Ctrl+T)
    win.new_tab()
    assert win.tab_manager.count() == 2
    assert win.tab_manager.current_index() == 1

    # 2. Navigate tab 2 to specific URL
    win.navigate_to("https://example.com/testpage")
    t2 = win.tab_manager.current_view()
    assert t2 is not None

    # 3. Close Tab (Ctrl+W)
    win.close_tab()
    assert win.tab_manager.count() == 1
    assert win.tab_manager.closed_tabs_count() == 1

    # 4. Restore Closed Tab (Ctrl+Shift+T)
    restored = win.restore_closed_tab()
    assert restored is not None
    assert win.tab_manager.count() == 2
    assert "testpage" in restored.url().toString()

    # 5. Switch to Tab 1 (Ctrl+1)
    win.switch_to_tab(0)
    assert win.tab_manager.current_index() == 0

    # 6. Switch to Last Tab (Ctrl+9)
    win.switch_to_last_tab()
    assert win.tab_manager.current_index() == 1

    # 7. Next and Previous Tab (Ctrl+Tab, Ctrl+Shift+Tab)
    win.next_tab()
    assert win.tab_manager.current_index() == 0  # wrap-around
    win.prev_tab()
    assert win.tab_manager.current_index() == 1  # wrap-around


def test_navigation_and_focus_shortcuts():
    """Verify Ctrl+L (focus URL), Alt+Home (home), Ctrl+Shift+R (cache bypass)."""
    win = MainWindow()
    win.show()
    app.processEvents()

    # 1. Focus Address Bar (Ctrl+L)
    win.address_bar.set_url(QUrl("https://example.com"))
    win.focus_address_bar()
    app.processEvents()
    assert win.address_bar.hasFocus()
    assert win.address_bar.hasSelectedText()

    # 2. Homepage (Alt+Home)
    win.home()
    assert win.tab_manager.current_view().url().toString() == DEFAULT_START_URL

    # 3. Reload bypassing cache (Ctrl+Shift+R)
    win.reload_bypass_cache()


def test_find_in_page_and_dismiss_shortcuts():
    """Verify Ctrl+F opens find bar and Esc dismisses it."""
    win = MainWindow()
    win.show()
    app.processEvents()

    assert win.find_bar.isHidden()

    # Open Find Bar (Ctrl+F)
    win.open_find_in_page()
    app.processEvents()
    assert not win.find_bar.isHidden()
    assert win.find_bar.search_input.hasFocus()

    # Dismiss Find Bar (Esc)
    win.stop_or_dismiss()
    assert win.find_bar.isHidden()


def test_zoom_shortcuts_and_bounds():
    """Verify Ctrl+=/Ctrl++, Ctrl+-, Ctrl+0 and bounds clamping (0.25 to 5.0)."""
    win = MainWindow()
    view = win.tab_manager.current_view()
    assert view is not None

    # Reset zoom (Ctrl+0)
    win.reset_zoom()
    assert view.zoomFactor() == 1.0

    # Zoom in (Ctrl+=)
    win.zoom_in()
    assert round(view.zoomFactor(), 2) == 1.1

    # Zoom out (Ctrl+-)
    win.zoom_out()
    assert round(view.zoomFactor(), 2) == 1.0

    # Test lower bound (0.25)
    for _ in range(15):
        win.zoom_out()
    assert view.zoomFactor() >= 0.25

    # Test upper bound (5.0)
    for _ in range(60):
        win.zoom_in()
    assert view.zoomFactor() <= 5.0

    # Reset to 1.0
    win.reset_zoom()
    assert view.zoomFactor() == 1.0


def test_bookmarks_shortcuts():
    """Verify Ctrl+D (bookmark page) and Ctrl+Shift+B (toggle bookmarks bar)."""
    BookmarkManager.get_instance().clear()
    win = MainWindow()

    # 1. Toggle Bookmarks Bar (Ctrl+Shift+B)
    assert win.bookmarks_bar.isHidden()
    win.toggle_bookmarks_bar()
    assert not win.bookmarks_bar.isHidden()
    win.toggle_bookmarks_bar()
    assert win.bookmarks_bar.isHidden()

    # 2. Bookmark current page (Ctrl+D)
    view = win.tab_manager.current_view()
    assert view is not None
    view.setUrl(QUrl("https://example.com/unique-bookmark"))

    manager = BookmarkManager.get_instance()
    win.bookmark_current_page()
    assert manager.is_bookmarked("https://example.com/unique-bookmark")


def test_fullscreen_toggle_shortcut():
    """Verify F11 toggles fullscreen mode."""
    win = MainWindow()

    assert not win.isFullScreen()
    win.toggle_fullscreen()
    assert win.isFullScreen()
    win.toggle_fullscreen()
    assert not win.isFullScreen()


def test_devtools_shortcuts():
    """Verify F12, Ctrl+Shift+I, Ctrl+Shift+J, Ctrl+Shift+C, Ctrl+U."""
    win = MainWindow()

    assert not win.devtools_manager.is_open()

    # Toggle DevTools (F12 / Ctrl+Shift+I)
    win.toggle_devtools()
    assert win.devtools_manager.is_open()
    win.toggle_devtools()
    assert not win.devtools_manager.is_open()

    # Open JavaScript Console (Ctrl+Shift+J)
    win.open_js_console()
    assert win.devtools_manager.is_open()

    # Activate inspect element (Ctrl+Shift+C)
    win.activate_inspect_element()
    assert win.devtools_manager.is_open()

    # View Page Source in new tab (Ctrl+U)
    initial_tabs = win.tab_manager.count()
    win.view_page_source()
    assert win.tab_manager.count() == initial_tabs + 1
    new_view = win.tab_manager.current_view()
    assert new_view is not None
    assert new_view.url().toString().startswith("view-source:")


def test_multi_window_and_private_browsing_shortcuts():
    """Verify Ctrl+N and Ctrl+Shift+N and private window isolation."""
    win1 = MainWindow()

    # 1. New Normal Window (Ctrl+N)
    win2 = win1.new_window()
    assert win2 is not None
    assert win2.is_private is False
    assert win2 in MainWindow._all_windows

    # 2. New Private Window (Ctrl+Shift+N)
    win_priv = win1.new_private_window()
    assert win_priv is not None
    assert win_priv.is_private is True
    assert "Private Browsing" in win_priv.windowTitle()

    # 3. Isolation: tabs closed in private window never enter normal restore stack
    win_priv.navigate_to("https://secret.com/page")
    win_priv.new_tab()
    win_priv.close_tab()
    assert win_priv.tab_manager.closed_tabs_count() == 0
    assert win1.tab_manager.closed_tabs_count() == 0

    # 4. Clean window close
    win2.close()
    assert win2 not in MainWindow._all_windows
    win_priv.close()
    assert win_priv not in MainWindow._all_windows
