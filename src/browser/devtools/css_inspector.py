"""Computed CSS viewer with temporary inline property edits and reset."""

from __future__ import annotations

import json
import re

from PySide6.QtWidgets import (QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)


class CSSInspector(QWidget):
    """Show computed values and edit validated inline declarations on selection."""

    SAFE_PROPERTY = re.compile(r"^-?[a-zA-Z][a-zA-Z0-9-]{0,63}$")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.page = None
        self.path = "[]"
        self.properties = {}
        layout = QVBoxLayout(self)
        self.filter = QLineEdit(); self.filter.setPlaceholderText("Filter computed properties")
        self.table = QTableWidget(0, 2); self.table.setHorizontalHeaderLabels(["Property", "Computed value"]); self.table.horizontalHeader().setStretchLastSection(True)
        controls = QFormLayout()
        self.property_name = QLineEdit(); self.property_name.setPlaceholderText("e.g. background-color")
        self.property_value = QLineEdit(); self.property_value.setPlaceholderText("e.g. #2563eb")
        controls.addRow("Property", self.property_name); controls.addRow("Value", self.property_value)
        buttons = QHBoxLayout(); self.apply_button = QPushButton("Apply"); self.reset_button = QPushButton("Reset edits")
        buttons.addWidget(self.apply_button); buttons.addWidget(self.reset_button)
        self.status = QLabel("Computed styles only; stylesheet source rules are not exposed here.")
        layout.addWidget(self.filter); layout.addWidget(self.table, 1); layout.addLayout(controls); layout.addLayout(buttons); layout.addWidget(self.status)
        self.filter.textChanged.connect(self._filter_rows); self.apply_button.clicked.connect(self.apply_edit); self.reset_button.clicked.connect(self.reset_edits)

    def set_page(self, page) -> None:
        self.page = page
        self.properties = {}
        self.path = "[]"

    def set_selection(self, path: str, data: dict) -> None:
        self.path = path
        self.properties = data.get("css", {}) if isinstance(data.get("css"), dict) else {}
        self._render()

    def _render(self) -> None:
        self.table.setRowCount(0)
        for name, value in sorted(self.properties.items()):
            row = self.table.rowCount(); self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(name)))
            self.table.setItem(row, 1, QTableWidgetItem(str(value)))
        self._filter_rows(self.filter.text())

    def _filter_rows(self, query: str) -> None:
        needle = query.casefold()
        for row in range(self.table.rowCount()):
            self.table.setRowHidden(row, needle not in self.table.item(row, 0).text().casefold() and needle not in self.table.item(row, 1).text().casefold())

    def apply_edit(self) -> None:
        name, value = self.property_name.text().strip(), self.property_value.text()
        if self.page is None or not self.SAFE_PROPERTY.fullmatch(name) or not value.strip():
            self.status.setText("Enter a valid CSS property name and value.")
            return
        path, prop, val = self.path, json.dumps(name), json.dumps(value)
        script = f"(()=>{{let e=document.documentElement;for(const i of {path})e=e?.childNodes[i];if(!e||!(e instanceof Element)||!CSS.supports({prop},{val}))return false;e.__lightmqOriginalStyles??={{}};if(!({prop} in e.__lightmqOriginalStyles))e.__lightmqOriginalStyles[{prop}]={{value:e.style.getPropertyValue({prop}),priority:e.style.getPropertyPriority({prop})}};e.style.setProperty({prop},{val});return true}})()"
        self.page.runJavaScript(script, self._applied)

    def _applied(self, valid) -> None:
        self.status.setText("Temporary style applied." if valid else "The browser rejected this CSS value.")

    def reset_edits(self) -> None:
        if self.page is None: return
        path = self.path
        script = f"(()=>{{let e=document.documentElement;for(const i of {path})e=e?.childNodes[i];const m=e?.__lightmqOriginalStyles;if(!m)return false;for(const [p,v] of Object.entries(m))v.value?e.style.setProperty(p,v.value,v.priority):e.style.removeProperty(p);delete e.__lightmqOriginalStyles;return true}})()"
        self.page.runJavaScript(script, lambda ok: self.status.setText("Temporary edits reset." if ok else "No temporary edits to reset."))
