"""Unit tests for TabManager lifecycle, collection, and navigation."""

import sys
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication

from browser.core.tab_manager import TabManager

app = QApplication.instance() or QApplication(sys.argv)


def test_tab_manager_initial_state():
    """Verify newly instantiated TabManager has zero tabs."""
    tm = TabManager()
    assert tm.count() == 0
    assert tm.current_index() == -1
    assert tm.current_view() is None


def test_tab_creation_and_activation():
    """Verify tabs can be created and activated."""
    tm = TabManager()
    created_events = []
    tm.tab_created.connect(lambda idx, view: created_events.append((idx, view)))

    # Create first tab
    v1 = tm.create_tab("https://example.com", activate=True)
    assert tm.count() == 1
    assert tm.current_index() == 0
    assert tm.current_view() is v1
    assert len(created_events) == 1

    # Create second tab
    v2 = tm.create_tab("https://github.com", activate=True)
    assert tm.count() == 2
    assert tm.current_index() == 1
    assert tm.current_view() is v2
    assert len(created_events) == 2


def test_tab_switching_next_prev():
    """Verify tab cycling with next_tab and prev_tab (wraparound)."""
    tm = TabManager()
    tm.create_tab("https://tab1.com")
    tm.create_tab("https://tab2.com")
    tm.create_tab("https://tab3.com")

    assert tm.current_index() == 2

    # Next tab wraps from 2 to 0
    tm.next_tab()
    assert tm.current_index() == 0

    tm.next_tab()
    assert tm.current_index() == 1

    # Prev tab wraps backwards from 1 to 0, then 0 to 2
    tm.prev_tab()
    assert tm.current_index() == 0

    tm.prev_tab()
    assert tm.current_index() == 2


def test_close_inactive_tab():
    """Verify closing an inactive tab does not alter active tab content."""
    tm = TabManager()
    v0 = tm.create_tab("https://tab0.com")
    v1 = tm.create_tab("https://tab1.com")
    v2 = tm.create_tab("https://tab2.com")

    # Set active to tab 2
    tm.set_current_index(2)
    assert tm.current_view() is v2

    # Close inactive tab 1
    tm.close_tab(1)
    assert tm.count() == 2
    assert tm.current_view() is v2
    assert tm.current_index() == 1


def test_close_active_tab():
    """Verify closing active tab switches gracefully to adjacent tab."""
    tm = TabManager()
    v0 = tm.create_tab("https://tab0.com")
    v1 = tm.create_tab("https://tab1.com")
    v2 = tm.create_tab("https://tab2.com")

    # Close active tab (tab 2)
    tm.close_tab(2)
    assert tm.count() == 2
    assert tm.current_index() == 1
    assert tm.current_view() is v1


def test_close_last_tab_creates_new():
    """Verify closing the last remaining tab automatically creates a fresh blank tab."""
    tm = TabManager()
    tm.create_tab("https://only.com")
    assert tm.count() == 1

    # Close the only tab
    tm.close_tab(0)
    assert tm.count() == 1
    assert tm.current_index() == 0
    assert tm.current_view() is not None


def test_tab_reordering():
    """Verify moving tabs reorders the internal list and preserves active index."""
    tm = TabManager()
    v0 = tm.create_tab("https://tab0.com")
    v1 = tm.create_tab("https://tab1.com")
    v2 = tm.create_tab("https://tab2.com")

    tm.set_current_index(0)
    assert tm.current_view() is v0

    # Move tab 0 to position 2
    tm.move_tab(0, 2)
    assert tm.view_at(2) is v0
    assert tm.current_view() is v0
    assert tm.current_index() == 2
