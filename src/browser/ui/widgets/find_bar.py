"""Find in page toolbar widget for LightMq Browser.

Integrates with QWebEngineView.findText() to provide inline text searching,
next/previous match navigation, and case-sensitivity controls.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)
from PySide6.QtWebEngineCore import QWebEngineFindTextResult, QWebEnginePage

from browser.webengine.web_view import WebView


class FindBar(QWidget):
    """Find in page floating toolbar widget."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._active_view: WebView | None = None
        self._init_ui()
        self.hide()

    def _init_ui(self) -> None:
        """Construct the find bar layout and controls."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        # Search query input
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Find in page...")
        self.search_input.setMinimumWidth(200)
        self.search_input.setMaximumWidth(300)
        self.search_input.textChanged.connect(self._on_text_changed)
        self.search_input.returnPressed.connect(self.find_next)
        layout.addWidget(self.search_input)

        # Matches counter
        self.label_matches = QLabel("", self)
        self.label_matches.setMinimumWidth(70)
        layout.addWidget(self.label_matches)

        # Previous Match Button
        self.btn_prev = QPushButton("▲", self)
        self.btn_prev.setToolTip("Previous match (Shift+Enter)")
        self.btn_prev.setFixedWidth(28)
        self.btn_prev.clicked.connect(self.find_prev)
        layout.addWidget(self.btn_prev)

        # Next Match Button
        self.btn_next = QPushButton("▼", self)
        self.btn_next.setToolTip("Next match (Enter)")
        self.btn_next.setFixedWidth(28)
        self.btn_next.clicked.connect(self.find_next)
        layout.addWidget(self.btn_next)

        # Match Case Checkbox
        self.check_case = QCheckBox("Match Case", self)
        self.check_case.toggled.connect(lambda: self.find_next())
        layout.addWidget(self.check_case)

        layout.addStretch()

        # Close Button
        self.btn_close = QPushButton("✕", self)
        self.btn_close.setToolTip("Close (Esc)")
        self.btn_close.setFixedWidth(28)
        self.btn_close.clicked.connect(self.close_and_clear)
        layout.addWidget(self.btn_close)

    def set_active_view(self, view: WebView | None) -> None:
        """Synchronize find bar with the active tab's WebView.

        Clears find highlights from the previous tab and re-applies to the new tab.
        """
        if self._active_view is not None:
            try:
                self._active_view.findText("")
            except Exception:
                pass

        self._active_view = view

        # If find bar is currently visible, search on the new active tab
        if self.isVisible() and self.search_input.text():
            self._do_find(backward=False)

    def show_and_focus(self) -> None:
        """Display the find bar, focus the input field, and select all text."""
        self.show()
        self.search_input.setFocus()
        self.search_input.selectAll()
        if self.search_input.text():
            self._do_find(backward=False)

    def close_and_clear(self) -> None:
        """Hide find bar, clear active highlights, and return focus to the web view."""
        self.hide()
        self.label_matches.setText("")
        if self._active_view is not None:
            try:
                self._active_view.findText("")
                self._active_view.setFocus()
            except Exception:
                pass

    def find_next(self) -> None:
        """Find the next occurrence."""
        self._do_find(backward=False)

    def find_prev(self) -> None:
        """Find the previous occurrence."""
        self._do_find(backward=True)

    def _on_text_changed(self, text: str) -> None:
        """Handle query text changes in real-time."""
        if not text:
            self.label_matches.setText("")
            if self._active_view is not None:
                self._active_view.findText("")
        else:
            self._do_find(backward=False)

    def _do_find(self, backward: bool = False) -> None:
        """Perform search on active WebView."""
        query = self.search_input.text()
        if not query or self._active_view is None:
            return

        flags = QWebEnginePage.FindFlag(0)
        if backward:
            flags |= QWebEnginePage.FindFlag.FindBackward
        if self.check_case.isChecked():
            flags |= QWebEnginePage.FindFlag.FindCaseSensitively

        try:
            self._active_view.findText(query, flags, self._on_find_result)
        except Exception:
            pass

    def _on_find_result(self, result: QWebEngineFindTextResult) -> None:
        """Update match counter label with match statistics."""
        total = result.numberOfMatches()
        current = result.activeMatch()
        if total > 0:
            self.label_matches.setText(f"{current} of {total}")
        elif self.search_input.text():
            self.label_matches.setText("No matches")
        else:
            self.label_matches.setText("")

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle Esc and Shift+Enter key presses within the find bar."""
        if event.key() == Qt.Key.Key_Escape:
            self.close_and_clear()
            event.accept()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.find_prev()
            else:
                self.find_next()
            event.accept()
        else:
            super().keyPressEvent(event)
