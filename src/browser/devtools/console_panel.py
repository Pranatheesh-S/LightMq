"""Bounded JavaScript console output and explicit active-page command execution."""

from collections import deque
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLineEdit, QListWidget,
    QPushButton, QVBoxLayout, QWidget)


class ConsolePanel(QWidget):
    """Display active page console messages without writing them to disk."""

    LIMIT = 500

    def __init__(self, parent=None):
        super().__init__(parent)
        self.page = None
        self.messages = deque(maxlen=self.LIMIT)
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.severity = QComboBox(); self.severity.addItems(["All", "Log", "Warning", "Error"])
        self.search = QLineEdit(); self.search.setPlaceholderText("Filter console messages")
        self.clear_button = QPushButton("Clear")
        controls.addWidget(self.severity); controls.addWidget(self.search, 1); controls.addWidget(self.clear_button)
        layout.addLayout(controls)
        self.output = QListWidget(); layout.addWidget(self.output, 1)
        command = QHBoxLayout(); self.command = QLineEdit(); self.command.setPlaceholderText("JavaScript (runs only when submitted)")
        self.run_button = QPushButton("Run")
        command.addWidget(self.command, 1); command.addWidget(self.run_button); layout.addLayout(command)
        self.severity.currentTextChanged.connect(self._render); self.search.textChanged.connect(self._render)
        self.clear_button.clicked.connect(self.clear); self.run_button.clicked.connect(self.execute)
        self.command.returnPressed.connect(self.execute)

    def set_page(self, page) -> None:
        if self.page is not None:
            try:
                self.page.console_message.disconnect(self.add_message)
                self.page.loadStarted.disconnect(self.clear)
            except (RuntimeError, TypeError): pass
        self.page = page
        self.clear()
        if page is not None:
            page.console_message.connect(self.add_message)
            page.loadStarted.connect(self.clear)

    def add_message(self, severity: str, message: str, line: int, source: str) -> None:
        lowered = severity.lower()
        if "warn" in lowered: lowered = "warning"
        elif "error" in lowered: lowered = "error"
        else: lowered = "log"
        self.messages.append((lowered, message, line, source, datetime.now().strftime("%H:%M:%S")))
        self._render()

    def _render(self, *_args) -> None:
        selected = self.severity.currentText().lower()
        needle = self.search.text().casefold()
        self.output.clear()
        for severity, message, line, source, timestamp in self.messages:
            if selected != "all" and selected not in severity: continue
            rendered = f"{timestamp}  {severity.upper()}  {message}  {source}:{line}"
            if needle not in rendered.casefold(): continue
            self.output.addItem(rendered)

    def clear(self) -> None:
        self.messages.clear(); self.output.clear()

    def execute(self) -> None:
        expression = self.command.text().strip()
        if self.page is None or not expression: return
        self.command.clear()
        self.page.runJavaScript(f"(()=>{{try{{const v=eval({expression!r});return {{ok:true,value:typeof v==='undefined'?'undefined':JSON.stringify(v)}}}}catch(e){{return {{ok:false,value:String(e)}}}}}})()", self._result)

    def _result(self, result) -> None:
        if isinstance(result, dict):
            self.add_message("log" if result.get("ok") else "error", str(result.get("value", "undefined")), 0, "LightMq Console")
