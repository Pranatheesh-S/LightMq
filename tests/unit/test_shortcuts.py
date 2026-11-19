"""Unit tests for ShortcutManager subsystem.

Verifies registration, duplicate prevention, window-context isolation,
and preservation of standard text-editing shortcuts.
"""

import sys
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication

from browser.ui.main_window import MainWindow
from browser.ui.shortcut_manager import ShortcutManager

app = QApplication.instance() or QApplication(sys.argv)


def test_shortcut_manager_registration():
    """Verify that default shortcuts are registered with WindowShortcut context."""
    window = MainWindow()
    mgr = window.shortcut_manager

    shortcuts = mgr.get_registered_shortcuts()
    assert len(shortcuts) >= 30

    # Verify key shortcuts exist
    expected_keys = [
        "Ctrl+T", "Ctrl+W", "Ctrl+Shift+T", "Ctrl+N", "Ctrl+Shift+N",
        "Ctrl+Tab", "Ctrl+Shift+Tab", "Ctrl+1", "Ctrl+9",
        "Ctrl+L", "Alt+Left", "Alt+Right", "Alt+Home", "F5", "Ctrl+R", "Ctrl+Shift+R",
        "Esc", "Ctrl+F", "Ctrl+D", "Ctrl+P", "Ctrl+S",
        "Ctrl+H", "Ctrl+J", "Ctrl+Shift+Del", "Ctrl+Shift+B",
        "F11", "Ctrl+=", "Ctrl+-", "Ctrl+0",
        "F12", "Ctrl+Shift+I", "Ctrl+Shift+J", "Ctrl+Shift+C", "Ctrl+U",
    ]

    registered_normalized = [s["normalized"] for s in shortcuts]

    for key in expected_keys:
        norm = QKeySequence(key).toString()
        assert norm in registered_normalized, f"Expected shortcut {key} (norm: {norm}) not found"

    # Verify WindowShortcut context
    for s_meta in shortcuts:
        shortcut_obj = mgr.get_shortcut(s_meta["normalized"])
        assert shortcut_obj is not None
        assert shortcut_obj.context() == Qt.ShortcutContext.WindowShortcut


def test_shortcut_duplicate_prevention():
    """Verify that attempting to register an existing key sequence is rejected."""
    window = MainWindow()
    mgr = window.shortcut_manager

    # Attempt to re-register Ctrl+T
    res = mgr.register_shortcut(
        "Ctrl+T",
        lambda: None,
        "duplicate_tab",
        "Test",
        "Duplicate",
    )
    assert res is None


def test_standard_text_editing_shortcuts_not_hijacked():
    """Ensure standard text-editing keys (Ctrl+C, Ctrl+V, Ctrl+A, Ctrl+Z, etc.) are free."""
    window = MainWindow()
    mgr = window.shortcut_manager

    forbidden_text_keys = ["Ctrl+C", "Ctrl+V", "Ctrl+X", "Ctrl+A", "Ctrl+Z", "Ctrl+Y"]
    for key in forbidden_text_keys:
        assert not mgr.is_registered(key), f"Standard key {key} must not be hijacked as a window shortcut"
