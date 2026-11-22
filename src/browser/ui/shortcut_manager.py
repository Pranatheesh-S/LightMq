"""Keyboard shortcut coordinator subsystem for LightMq Browser.

Centralizes definition, registration, and dispatch of all browser keyboard shortcuts.
Ensures window-scoped activation, eliminates duplicate registrations, and preserves
native text-editing keys.
"""

from collections.abc import Callable
import logging
from typing import TYPE_CHECKING
from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QKeySequence, QShortcut

if TYPE_CHECKING:
    from browser.ui.main_window import MainWindow

logger = logging.getLogger(__name__)


class ShortcutManager(QObject):
    """Manages application-wide keyboard shortcuts mapped to a MainWindow instance."""

    def __init__(self, window: "MainWindow", parent: QObject | None = None):
        super().__init__(parent or window)
        self._window = window
        self._shortcuts: dict[str, QShortcut] = {}
        self._registry: list[dict[str, str]] = []
        self._callbacks: dict[str, Callable[[], None]] = {}
        self._defaults: dict[str, str] = {}

    def register_shortcut(
        self,
        key_sequence: str,
        callback: Callable[[], None],
        action_name: str,
        category: str,
        description: str,
    ) -> QShortcut | None:
        """Register a keyboard shortcut bound to the window.

        Args:
            key_sequence: Key sequence string (e.g. 'Ctrl+T', 'F12').
            callback: Function to invoke when shortcut triggers.
            action_name: Machine-readable identifier for the action.
            category: Action category (e.g. 'Tabs', 'Navigation', 'Browser', 'DevTools').
            description: Human-readable action description.

        Returns:
            QShortcut | None: The registered shortcut instance, or None if duplicate.
        """
        seq = QKeySequence(key_sequence)
        normalized = seq.toString()
        if not normalized:
            # Fallback for sequences that QKeySequence string parsing might not re-emit directly
            normalized = key_sequence.strip()

        if normalized in self._shortcuts:
            logger.warning("Shortcut %s is already registered. Skipping duplicate.", normalized)
            return None

        shortcut = QShortcut(seq, self._window, context=Qt.ShortcutContext.WindowShortcut)
        shortcut.activated.connect(callback)
        self._shortcuts[normalized] = shortcut
        self._callbacks[action_name] = callback
        self._defaults[action_name] = normalized

        meta = {
            "key": key_sequence,
            "normalized": normalized,
            "action": action_name,
            "category": category,
            "description": description,
        }
        self._registry.append(meta)
        logger.debug("Registered shortcut %s -> %s", normalized, action_name)
        return shortcut

    def register_all_default_shortcuts(self) -> None:
        """Register all default LightMq keyboard shortcuts."""
        w = self._window

        # ======================================================================
        # 1. Tabs and Windows
        # ======================================================================
        self.register_shortcut(
            "Ctrl+T", w.new_tab, "new_tab", "Tabs", "Open new tab"
        )
        self.register_shortcut(
            "Ctrl+W", w.close_tab, "close_tab", "Tabs", "Close current tab"
        )
        self.register_shortcut(
            "Ctrl+Shift+T", w.restore_closed_tab, "restore_closed_tab", "Tabs", "Restore recently closed tab"
        )
        self.register_shortcut(
            "Ctrl+N", w.new_window, "new_window", "Windows", "Open new browser window"
        )
        self.register_shortcut(
            "Ctrl+Shift+N", w.new_private_window, "new_private_window", "Windows", "Open private browsing window"
        )
        self.register_shortcut(
            "Ctrl+Tab", w.next_tab, "next_tab", "Tabs", "Switch to next tab"
        )
        self.register_shortcut(
            "Ctrl+Shift+Tab", w.prev_tab, "prev_tab", "Tabs", "Switch to previous tab"
        )

        # Tab Switching Ctrl+1 through Ctrl+8
        for i in range(1, 9):
            idx = i - 1
            self.register_shortcut(
                f"Ctrl+{i}",
                lambda target=idx: w.switch_to_tab(target),
                f"switch_to_tab_{i}",
                "Tabs",
                f"Switch to tab {i}",
            )

        # Switch to Last Tab (Ctrl+9)
        self.register_shortcut(
            "Ctrl+9", w.switch_to_last_tab, "switch_to_last_tab", "Tabs", "Switch to last tab"
        )

        # ======================================================================
        # 2. Navigation and Page Controls
        # ======================================================================
        self.register_shortcut(
            "Ctrl+L", w.focus_address_bar, "focus_address_bar", "Navigation", "Focus and select address bar URL"
        )
        self.register_shortcut(
            "Alt+Left", w.back, "back", "Navigation", "Navigate backward"
        )
        self.register_shortcut(
            "Alt+Right", w.forward, "forward", "Navigation", "Navigate forward"
        )
        self.register_shortcut(
            "Alt+Home", w.home, "home", "Navigation", "Navigate to homepage"
        )
        self.register_shortcut(
            "F5", w.reload, "reload_f5", "Navigation", "Reload active page"
        )
        self.register_shortcut(
            "Ctrl+R", w.reload, "reload_ctrl", "Navigation", "Reload active page"
        )
        self.register_shortcut(
            "Ctrl+Shift+R", w.reload_bypass_cache, "reload_bypass_cache", "Navigation", "Reload bypassing cache"
        )
        self.register_shortcut(
            "Esc", w.stop_or_dismiss, "stop_or_dismiss", "Navigation", "Stop loading / dismiss find bar"
        )
        self.register_shortcut(
            "Ctrl+F", w.open_find_in_page, "open_find_in_page", "Page", "Open find-in-page interface"
        )
        self.register_shortcut(
            "Ctrl+D", w.bookmark_current_page, "bookmark_current_page", "Page", "Bookmark current page"
        )
        self.register_shortcut(
            "Ctrl+P", w.print_current_page, "print_current_page", "Page", "Print current page"
        )
        self.register_shortcut(
            "Ctrl+S", w.save_current_page, "save_current_page", "Page", "Save current page"
        )

        # ======================================================================
        # 3. Browser Management
        # ======================================================================
        self.register_shortcut(
            "Ctrl+H", w.open_history, "open_history", "Browser", "Open browsing history"
        )
        self.register_shortcut(
            "Ctrl+J", w.open_downloads, "open_downloads", "Browser", "Open downloads"
        )
        self.register_shortcut(
            "Ctrl+Shift+Del", w.open_clear_data, "open_clear_data", "Browser", "Open clear browsing data dialog"
        )
        self.register_shortcut(
            "Ctrl+Shift+B", w.toggle_bookmarks_bar, "toggle_bookmarks_bar", "Browser", "Show/hide bookmarks bar"
        )
        self.register_shortcut(
            "Ctrl+Shift+O", w._open_bookmark_manager_shortcut, "open_bookmark_manager", "Browser", "Open bookmark manager"
        )
        self.register_shortcut(
            "F11", w.toggle_fullscreen, "toggle_fullscreen", "Browser", "Toggle fullscreen"
        )
        self.register_shortcut(
            "Ctrl+=", w.zoom_in, "zoom_in_equal", "Browser", "Zoom in"
        )
        self.register_shortcut(
            "Ctrl++", w.zoom_in, "zoom_in_plus", "Browser", "Zoom in"
        )
        self.register_shortcut(
            "Ctrl+-", w.zoom_out, "zoom_out", "Browser", "Zoom out"
        )
        self.register_shortcut(
            "Ctrl+0", w.reset_zoom, "reset_zoom", "Browser", "Reset zoom to 100%"
        )

        # ======================================================================
        # 4. Developer Tools
        # ======================================================================
        self.register_shortcut(
            "F12", w.toggle_devtools, "toggle_devtools_f12", "DevTools", "Toggle Developer Tools"
        )
        self.register_shortcut(
            "Ctrl+Shift+I", w.toggle_devtools, "toggle_devtools_ctrl", "DevTools", "Toggle Developer Tools"
        )
        self.register_shortcut(
            "Ctrl+Shift+J", w.open_js_console, "open_js_console", "DevTools", "Open JavaScript Console"
        )
        self.register_shortcut(
            "Ctrl+Shift+C", w.activate_inspect_element, "activate_inspect_element", "DevTools", "Activate inspect-element mode"
        )
        self.register_shortcut(
            "Ctrl+U", w.view_page_source, "view_page_source", "DevTools", "View page source"
        )

        for entry in self._registry:
            stored = w._browser_settings.get(f"shortcuts/{entry['action']}", None)
            if isinstance(stored, str) and stored != entry["key"]:
                self._replace_binding(entry["action"], stored)

    def apply_custom(self, bindings: dict[str, str]) -> bool:
        """Validate all custom shortcuts, then atomically replace changed bindings."""
        occupied: dict[str, str] = {}
        for action, sequence in bindings.items():
            normalized = QKeySequence(sequence).toString() if sequence else ""
            if normalized and normalized in occupied:
                return False
            if normalized:
                occupied[normalized] = action
        for action, sequence in bindings.items():
            self._replace_binding(action, sequence)
        return True

    def reset_defaults(self) -> None:
        """Restore all currently registered actions to their original bindings."""
        self.apply_custom(self._defaults)

    def _replace_binding(self, action: str, sequence: str) -> None:
        """Replace a registered action binding while preserving its callback."""
        entry = next((item for item in self._registry if item["action"] == action), None)
        if entry is None:
            return
        old_key = entry["normalized"]
        shortcut = self._shortcuts.pop(old_key, None)
        if shortcut is None:
            return
        callback = self._callbacks.get(action)
        try:
            shortcut.activated.disconnect()
        except RuntimeError:
            pass
        shortcut.setEnabled(False)
        shortcut.deleteLater()
        normalized = QKeySequence(sequence).toString() if sequence else ""
        entry["key"], entry["normalized"] = sequence, normalized
        if normalized:
            replacement = QShortcut(QKeySequence(normalized), self._window, context=Qt.ShortcutContext.WindowShortcut)
            if callback is not None:
                replacement.activated.connect(callback)
            self._shortcuts[normalized] = replacement

    def is_registered(self, key_sequence: str) -> bool:
        """Check if a key sequence is currently registered."""
        seq = QKeySequence(key_sequence)
        normalized = seq.toString() or key_sequence.strip()
        return normalized in self._shortcuts

    def get_shortcut(self, key_sequence: str) -> QShortcut | None:
        """Get the QShortcut object for a key sequence."""
        seq = QKeySequence(key_sequence)
        normalized = seq.toString() or key_sequence.strip()
        return self._shortcuts.get(normalized)

    def get_registered_shortcuts(self) -> list[dict[str, str]]:
        """Return the complete metadata list of registered shortcuts."""
        return list(self._registry)
