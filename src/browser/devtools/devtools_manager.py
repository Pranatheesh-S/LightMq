"""Developer Tools lifecycle and coordinator subsystem.

Manages attaching Chromium Developer Tools to the active tab, dynamically
re-attaching across tab switches, and detaching on tab closure.
"""

import logging
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QSplitter
from PySide6.QtWebEngineCore import QWebEnginePage

from browser.devtools.devtools_panel import DevToolsPanel
from browser.webengine.web_view import WebView

logger = logging.getLogger(__name__)


class DevToolsManager(QObject):
    """Coordinates Developer Tools panel visibility and page attachment across multiple tabs."""

    visibility_changed = Signal(bool)

    def __init__(
        self,
        devtools_panel: DevToolsPanel,
        splitter: QSplitter,
        target_view: WebView | None = None,
        parent: QObject | None = None,
        settings=None,
    ):
        super().__init__(parent)
        self._panel = devtools_panel
        self._splitter = splitter
        self._target_view: WebView | None = None
        self._is_attached = False
        self._settings = settings
        self._splitter.splitterMoved.connect(self._save_splitter_sizes)

        # Connect panel close button
        self._panel.close_requested.connect(self.close)

        if target_view is not None:
            self.set_target_view(target_view)

    def set_target_view(self, view: WebView | None) -> None:
        """Update active target view being inspected.

        Automatically detaches from previous tab and re-attaches to the new active tab.

        Args:
            view: Newly active WebView or None.
        """
        if self._target_view is view:
            return

        # Detach from previously inspected view
        self.detach()

        self._target_view = view

        self._panel.set_target_view(view, view.page().profile() if view is not None else None)

        if self._target_view is not None:
            # Connect Inspect Element context menu action
            try:
                inspect_action = self._target_view.page().action(QWebEnginePage.WebAction.InspectElement)
                if inspect_action is not None:
                    inspect_action.triggered.connect(self._on_inspect_triggered)
            except Exception:
                pass

            # Always ensure the active tab has the devtools page attached
            self.attach()

    def attach(self) -> None:
        """Attach DevTools page to the current target web page."""
        if self._target_view is None or self._is_attached:
            return

        try:
            target_page = self._target_view.page()
            devtools_page = self._panel.get_page()
            target_page.setDevToolsPage(devtools_page)
            self._is_attached = True
            logger.info("DevTools page attached to active tab.")
        except Exception as e:
            logger.error("Failed to attach DevTools page: %s", e)

    def detach(self) -> None:
        """Safely detach DevTools page from the current target web page."""
        if self._target_view is not None and self._is_attached:
            try:
                self._target_view.page().setDevToolsPage(None)
            except (RuntimeError, Exception):
                pass
            self._is_attached = False
            logger.info("DevTools page detached from tab.")

    def on_view_closing(self, view: WebView) -> None:
        """Safely detach DevTools when the inspected tab is about to be closed.

        Args:
            view: The WebView being closed.
        """
        if self._target_view is view:
            self.detach()
            self._target_view = None
            self._panel.set_target_view(None)

    def _on_inspect_triggered(self) -> None:
        """Handle Inspect Element action triggered from the web view context menu."""
        if not self.is_open():
            self.open()

    def is_open(self) -> bool:
        """Return True if the Developer Tools panel is currently visible."""
        return not self._panel.isHidden()

    def toggle(self) -> None:
        """Toggle Developer Tools visibility."""
        if self.is_open():
            self.close()
        else:
            self.open()

    def open(self) -> None:
        """Open and display the Developer Tools panel in the splitter."""
        self.attach()
        self._panel.show()

        saved_sizes = self._load_splitter_sizes()
        if saved_sizes:
            self._splitter.setSizes(saved_sizes)
        else:
            # Use the active splitter axis so bottom docking gets a vertical ratio.
            extent = self._splitter.height() if self._splitter.orientation().name == "Vertical" else self._splitter.width()
            if extent > 200:
                tools_extent = max(280, int(extent * 0.4))
                self._splitter.setSizes([extent - tools_extent, tools_extent])
            else:
                self._splitter.setSizes([700, 450])

        self.visibility_changed.emit(True)

    def close(self) -> None:
        """Hide the Developer Tools panel."""
        self._save_splitter_sizes()
        self._panel.cancel_transient_tools()
        self._panel.hide()
        self.visibility_changed.emit(False)

    def _load_splitter_sizes(self) -> list[int] | None:
        if self._settings is None:
            return None
        raw = self._settings.value("devtools/splitter_sizes", None)
        if not isinstance(raw, (list, tuple)) or len(raw) != 2:
            return None
        try:
            sizes = [int(value) for value in raw]
        except (TypeError, ValueError):
            return None
        return sizes if all(value > 0 for value in sizes) else None

    def _save_splitter_sizes(self, *_args) -> None:
        if self._settings is None or self._panel.isHidden():
            return
        sizes = self._splitter.sizes()
        if len(sizes) == 2 and all(size > 0 for size in sizes):
            self._settings.setValue("devtools/splitter_sizes", sizes)
