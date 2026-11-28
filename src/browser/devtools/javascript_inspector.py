"""Honest, bounded JavaScript information for the currently selected element."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget


class JavaScriptInspector(QWidget):
    """Show only inline handlers exposed by DOM APIs and direct users to DevTools."""

    open_chromium_devtools = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._data: dict[str, Any] = {}
        layout = QVBoxLayout(self)
        self.summary = QLabel("Select a webpage element to inspect observable JavaScript information.")
        self.summary.setWordWrap(True); layout.addWidget(self.summary)
        self.handlers = QPlainTextEdit(); self.handlers.setReadOnly(True); layout.addWidget(self.handlers, 1)
        self.limitation = QLabel(
            "Standard DOM APIs cannot enumerate listeners registered with addEventListener(), "
            "framework delegation, or reliably map a selected element to a source file. "
            "No event listeners or source locations are inferred."
        )
        self.limitation.setWordWrap(True); layout.addWidget(self.limitation)
        self.open_button = QPushButton("Open Chromium DevTools")
        self.open_button.clicked.connect(self.open_chromium_devtools.emit); layout.addWidget(self.open_button)

    def set_selection(self, _path: str, data: dict[str, Any]) -> None:
        self._data = data if isinstance(data, dict) else {}
        tag = str(self._data.get("tag", "element"))
        attrs = self._data.get("inline", {})
        if isinstance(attrs, dict) and attrs:
            self.handlers.setPlainText("\n".join(f"{name}={value}" for name, value in list(attrs.items())[:30]))
            self.summary.setText(f"Observed inline event-handler attributes on <{tag.lower()}>. These are markup attributes, not a complete listener list.")
        else:
            self.handlers.setPlainText("No inline event-handler attributes were found on the selected element.")
            self.summary.setText(f"No inline handler attributes were observed on <{tag.lower()}>.")

    def clear_selection(self) -> None:
        self._data = {}; self.handlers.clear()
        self.summary.setText("Select a webpage element to inspect observable JavaScript information.")
