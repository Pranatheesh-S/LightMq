"""Unified panel for built-in Chromium DevTools and custom LightMq diagnostics."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QVBoxLayout, QWidget)
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebEngineWidgets import QWebEngineView

from browser.devtools.console_panel import ConsolePanel
from browser.devtools.css_inspector import CSSInspector
from browser.devtools.dom_tree import DOMInspector
from browser.devtools.network_monitor import NetworkMonitor
from browser.devtools.performance_panel import PerformancePanel


class DevToolsPanel(QWidget):
    """Keep one Chromium DevTools view and host optional custom tool widgets."""

    close_requested = Signal()

    def __init__(self, parent: QWidget | None = None, profile=None):
        super().__init__(parent)
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)
        header = QHBoxLayout(); header.addWidget(QLabel("Developer Tools")); header.addStretch()
        self.mode = QComboBox(); self.mode.addItems(["Chromium DevTools", "LightMq Tools"]); header.addWidget(self.mode)
        self.btn_close = QPushButton("✕"); self.btn_close.setToolTip("Close Developer Tools (F12)"); self.btn_close.clicked.connect(self.close_requested.emit); header.addWidget(self.btn_close)
        outer.addLayout(header)
        self._view = QWebEngineView(self)
        self._page = QWebEnginePage(profile,self._view) if profile is not None else QWebEnginePage(self._view)
        self._view.setPage(self._page); outer.addWidget(self._view, 1)
        self.tools = QTabWidget(self)
        self.dom = DOMInspector(self.tools); self.css = CSSInspector(self.tools); self.console = ConsolePanel(self.tools); self.network = NetworkMonitor(self.tools); self.performance = PerformancePanel(self.tools)
        for widget, name in ((self.dom,"DOM"),(self.css,"CSS"),(self.console,"Console"),(self.network,"Network"),(self.performance,"Performance")):
            self.tools.addTab(widget, name)
        outer.addWidget(self.tools, 1); self.tools.hide()
        self.mode.currentIndexChanged.connect(self._select_mode)
        self.dom.element_selected.connect(self.css.set_selection)
        self.current_page = None

    def _select_mode(self, index: int) -> None:
        chromium = index == 0
        self._view.setVisible(chromium); self.tools.setVisible(not chromium)

    def set_target_view(self, view, profile=None) -> None:
        if self.current_page is not None and self.current_page is not (view.page() if view is not None else None):
            self.current_page.runJavaScript("window.__lightmqPickCleanup?.()")
        self.current_page = view.page() if view is not None else None
        page = self.current_page
        for panel in (self.dom, self.css, self.console, self.performance): panel.set_page(page)
        if profile is not None: self.network.set_profile(profile)

    def cancel_transient_tools(self) -> None:
        if self.current_page is not None:
            self.current_page.runJavaScript("window.__lightmqPickCleanup?.()")
        self.dom.cancel_picker()

    def get_page(self) -> QWebEnginePage: return self._page
    def get_view(self) -> QWebEngineView: return self._view
