"""Developer Tools UI container component.

Hosts a dedicated QWebEngineView configured with a devtools page, complete with a
compact header bar and close button.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebEngineWidgets import QWebEngineView


class DevToolsPanel(QWidget):
    """Container widget hosting the Chromium Developer Tools interface."""

    close_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        """Initialize the panel layout, header bar, and devtools view."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar
        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 4, 8, 4)
        header_layout.setSpacing(6)

        title = QLabel("Chromium Developer Tools", header)
        title.setStyleSheet("font-weight: bold; color: #555;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.btn_close = QPushButton("✕", header)
        self.btn_close.setToolTip("Close Developer Tools (F12)")
        self.btn_close.setFixedSize(22, 22)
        self.btn_close.setStyleSheet(
            "QPushButton { border: none; font-size: 13px; font-weight: bold; color: #666; }"
            "QPushButton:hover { background-color: #E81123; color: white; border-radius: 2px; }"
        )
        self.btn_close.clicked.connect(self.close_requested.emit)
        header_layout.addWidget(self.btn_close)

        layout.addWidget(header)

        # Developer Tools QWebEngineView
        self._view = QWebEngineView(self)
        self._page = QWebEnginePage(self._view)
        self._view.setPage(self._page)
        layout.addWidget(self._view)

    def get_page(self) -> QWebEnginePage:
        """Return the QWebEnginePage dedicated to rendering Developer Tools."""
        return self._page

    def get_view(self) -> QWebEngineView:
        """Return the QWebEngineView hosting Developer Tools."""
        return self._view
