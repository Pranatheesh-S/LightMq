"""Unit tests for TabManager tab restoration, index switching, and private mode."""

import sys
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication

from browser.core.tab_manager import TabManager

app = QApplication.instance() or QApplication(sys.argv)


def test_closed_tab_recording_and_restoration():
    """Verify that closed tabs are pushed to restore stack and popped on restoration."""
    mgr = TabManager(default_url="https://example.com")

    # Create two tabs with explicit URLs
    t1 = mgr.create_tab("https://example.com/one")
    t2 = mgr.create_tab("https://example.com/two")
    assert mgr.count() == 2

    # Close the active tab (t2)
    mgr.close_tab(1)
    assert mgr.count() == 1
    assert mgr.closed_tabs_count() == 1

    # Restore closed tab
    restored = mgr.restore_closed_tab()
    assert restored is not None
    assert mgr.count() == 2
    assert "example.com/two" in restored.url().toString()
    assert mgr.closed_tabs_count() == 0


def test_empty_restore_stack_returns_none():
    """Restoring when no tabs have been closed returns None safely."""
    mgr = TabManager(default_url="https://example.com")
    mgr.create_tab()
    assert mgr.closed_tabs_count() == 0
    assert mgr.restore_closed_tab() is None


def test_private_tab_manager_never_records_closed_tabs():
    """Private browsing tab managers must never save closed tabs to restore stack."""
    mgr = TabManager(default_url="https://example.com", is_private=True)
    assert mgr.is_private is True

    t1 = mgr.create_tab("https://secret.com/login")
    mgr.create_tab("https://secret.com/dashboard")
    assert mgr.count() == 2

    mgr.close_tab(1)
    assert mgr.count() == 1
    assert mgr.closed_tabs_count() == 0
    assert mgr.restore_closed_tab() is None


def test_bounded_closed_tab_stack():
    """Verify that closed tab history is bounded (max 25 entries)."""
    mgr = TabManager(default_url="https://example.com")

    # Create and close 30 tabs
    for i in range(30):
        mgr.create_tab(f"https://example.com/page{i}")
        mgr.close_tab(mgr.count() - 1)

    assert mgr.closed_tabs_count() <= 25


def test_switch_to_tab_by_index_and_last():
    """Verify switch_to_tab (Ctrl+1..8) and switch_to_last_tab (Ctrl+9)."""
    mgr = TabManager(default_url="https://example.com")
    for i in range(5):
        mgr.create_tab(f"https://example.com/{i}")

    assert mgr.count() == 5

    # Switch to tab index 2
    mgr.switch_to_tab(2)
    assert mgr.current_index() == 2

    # Switch to out-of-bounds tab index (e.g. 10) - safe no-op
    mgr.switch_to_tab(10)
    assert mgr.current_index() == 2

    # Switch to last tab
    mgr.switch_to_last_tab()
    assert mgr.current_index() == 4
