"""Computed CSS, box model, matched rules, and reversible page-local edits."""

from __future__ import annotations

import json
import re
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics, QPainter, QPalette
from PySide6.QtWidgets import (
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTabWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QPlainTextEdit,
)

from browser.devtools.inspector_bridge import (
    RESOLVE_HELPER, SAFE_CSS_HELPER, path_literal, run_inspector_data, run_inspector_js,
)


class BoxModelDiagram(QWidget):
    """Draw a schematic box model labeled with measured CSS pixel values."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(170)
        self.setMinimumWidth(280)
        self.setObjectName("boxModelDiagram")
        self.setToolTip("Diagram bands are schematic; all displayed spacing and bounds are measured CSS pixel values.")
        self._box: dict[str, Any] = {}

    def set_box(self, box: Any) -> None:
        self._box = box if isinstance(box, dict) else {}
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        bounds = self.rect().adjusted(6, 6, -6, -6)
        margin = bounds.adjusted(20, 22, -20, -18)
        border = margin.adjusted(20, 22, -20, -18)
        padding = border.adjusted(22, 22, -22, -18)
        content = padding.adjusted(20, 22, -20, -18)
        rects = (bounds, margin, border, padding, content)
        colors = (
            palette.color(QPalette.ColorRole.AlternateBase),
            palette.color(QPalette.ColorRole.Midlight),
            palette.color(QPalette.ColorRole.Mid),
            palette.color(QPalette.ColorRole.Highlight),
            palette.color(QPalette.ColorRole.Base),
        )
        names = ("Margin", "Border", "Padding", "Rendered box", "")
        sides = []
        for name in ("margin", "border", "padding"):
            values = self._box.get(name, {})
            if not isinstance(values, dict):
                values = {}
            sides.append("T {top:g} · R {right:g} · B {bottom:g} · L {left:g} px".format(
                **{key: float(values.get(key, 0) or 0) for key in ("top", "right", "bottom", "left")}
            ))
        sizes = "{width:.0f} × {height:.0f} CSS px".format(
            width=float(self._box.get("width", 0) or 0),
            height=float(self._box.get("height", 0) or 0),
        )
        labels = (sides[0], sides[1], sides[2], sizes, "")
        for index, rect in enumerate(rects):
            painter.setPen(palette.color(QPalette.ColorRole.Mid))
            painter.setBrush(colors[index])
            painter.drawRoundedRect(rect, 4, 4)
        metrics = QFontMetrics(painter.font())
        for index, rect in enumerate(rects[:4]):
            painter.setPen(palette.color(QPalette.ColorRole.HighlightedText) if index == 3 else palette.color(QPalette.ColorRole.Text))
            label = metrics.elidedText(f"{names[index]} · {labels[index]}", Qt.TextElideMode.ElideRight, max(20, rect.width() - 12))
            painter.drawText(rect.adjusted(6, 2, -6, 0), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter, label)
        painter.end()


class CSSInspector(QWidget):
    """Present actual browser-computed styles with temporary CSS overrides."""

    SAFE_PROPERTY = re.compile(r"^-?[a-zA-Z][a-zA-Z0-9-]{0,63}$")
    MAX_PROPERTIES = 400

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.page = None; self.path = "[]"; self.properties: dict[str, str] = {}; self._token = 0
        layout = QVBoxLayout(self)
        self.filter = QLineEdit(); self.filter.setPlaceholderText("Filter computed properties")
        layout.addWidget(self.filter)
        self.tabs = QTabWidget(self)
        computed = QWidget(self.tabs); computed_layout = QVBoxLayout(computed)
        self.box_diagram = BoxModelDiagram(computed)
        computed_layout.addWidget(self.box_diagram)
        self.table = QTableWidget(0, 2); self.table.setHorizontalHeaderLabels(["Property", "Computed value"]); self.table.horizontalHeader().setStretchLastSection(True)
        computed_layout.addWidget(self.table, 1)
        self.box_model = QLabel("Box model is available after selecting an element.")
        self.box_model.setWordWrap(True); self.box_model.setStyleSheet("QLabel { padding: 12px; border: 1px solid palette(mid); }")
        computed_layout.addWidget(self.box_model)
        self.tabs.addTab(computed, "Computed")
        self.rules = QPlainTextEdit(); self.rules.setReadOnly(True); self.rules.setPlaceholderText("Select an element to inspect accessible matching rules.")
        self.tabs.addTab(self.rules, "Matching Rules")
        layout.addWidget(self.tabs, 1)
        controls = QFormLayout(); self.property_name = QLineEdit(); self.property_name.setPlaceholderText("e.g. background-color")
        self.property_value = QLineEdit(); self.property_value.setPlaceholderText("e.g. #c00")
        controls.addRow("Property", self.property_name); controls.addRow("Value", self.property_value); layout.addLayout(controls)
        buttons = QHBoxLayout(); self.apply_button = QPushButton("Apply Temporary Style"); self.undo_button = QPushButton("Undo")
        self.redo_button = QPushButton("Redo"); self.reset_button = QPushButton("Reset CSS edits")
        for button in (self.apply_button, self.undo_button, self.redo_button, self.reset_button): buttons.addWidget(button)
        layout.addLayout(buttons)
        self.status = QLabel("Computed values come from the active browser document. Edits are temporary.")
        layout.addWidget(self.status)
        self.filter.textChanged.connect(self._filter_rows); self.apply_button.clicked.connect(self.apply_edit)
        self.undo_button.clicked.connect(self.undo_edit); self.redo_button.clicked.connect(self.redo_edit)
        self.reset_button.clicked.connect(self.reset_edits); self.table.cellClicked.connect(self._use_property)
        self._set_enabled(False)

    def set_page(self, page) -> None:
        if self.page is not None:
            try:
                run_inspector_js(self.page, "window.__lightmqCssResetAll?.()")
                self.page.loadStarted.disconnect(self._clear_for_navigation)
                self.page.renderProcessTerminated.disconnect(self._render_process_terminated)
            except (RuntimeError, TypeError): pass
        self.page = page; self.properties = {}; self.path = "[]"; self._token += 1
        self._render(); self.rules.clear(); self._set_enabled(page is not None)
        if page is not None:
            try:
                page.loadStarted.connect(self._clear_for_navigation)
                page.renderProcessTerminated.connect(self._render_process_terminated)
            except (RuntimeError, AttributeError): pass
        self._set_enabled(False)
        if page is None: self.status.setText("CSS inspection unavailable for this tab type.")

    def _clear_for_navigation(self) -> None:
        self._token += 1; self.properties = {}; self.path = "[]"; self._render(); self.rules.clear()
        self.box_diagram.set_box({}); self._set_enabled(False)
        self.box_model.setText("Navigation cleared the previous selection and temporary CSS edits.")

    def _render_process_terminated(self, *_args: Any) -> None:
        self._token += 1; self.properties = {}; self.path = "[]"; self._render(); self.rules.clear()
        self.box_diagram.set_box({}); self._set_enabled(False)
        self.status.setText("The page renderer stopped. Reload the page before inspecting its CSS.")

    def set_selection(self, path: str, data: dict[str, Any]) -> None:
        self.path = path; self.properties = data.get("css", {}) if isinstance(data.get("css"), dict) else {}
        self._render(); self._set_box(data.get("box", {})); self._set_enabled(self.page is not None and bool(data))
        if self.page is None or not data:
            self.rules.setPlainText("Select a webpage element to inspect matching CSS rules."); return
        token = self._token; literal = path_literal(path)
        script = f"""(()=>{{{SAFE_CSS_HELPER}{RESOLVE_HELPER}const e=resolvePath({literal});if(!e)return {{detached:true,blocked:0,rules:[]}};const out=[];let blocked=0;const walk=(rules,sheet)=>{{for(const r of Array.from(rules||[]).slice(0,300)){{if(r.type===1&&r.selectorText){{try{{if(e.matches(r.selectorText)){{const declarations={{}};for(let i=0;i<r.style.length&&i<80;i++)declarations[r.style[i]]=lightmqSafeCss(r.style.getPropertyValue(r.style[i])).slice(0,300);out.push({{selector:r.selectorText.slice(0,500),source:sheet,declarations}})}}}}catch{{}}}}else if(r.cssRules)walk(r.cssRules,sheet)}}}};for(const s of Array.from(document.styleSheets).slice(0,100)){{const source=s.href?lightmqSafeUrl(s.href):'[inline stylesheet]';try{{walk(s.cssRules,source)}}catch{{blocked++}}if(out.length>=80)break}}const inline={{}};for(let i=0;i<e.style.length&&i<100;i++){{const k=e.style[i];inline[k]=lightmqSafeCss(e.style.getPropertyValue(k)).slice(0,300)}}return {{rules:out.slice(0,80),blocked,inline}}}})()"""
        run_inspector_data(self.page, script, lambda result: self._show_rules(result, token))

    def _render(self) -> None:
        self.table.setRowCount(0)
        important = ("display", "position", "width", "height", "margin", "padding", "color", "background-color", "font-family", "font-size", "font-weight", "border", "border-radius", "opacity", "overflow", "z-index")
        keys = sorted(self.properties, key=lambda name: (name not in important, important.index(name) if name in important else name))
        for name in keys[:self.MAX_PROPERTIES]:
            row = self.table.rowCount(); self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(name)))
            self.table.setItem(row, 1, QTableWidgetItem(str(self.properties[name])[:500]))
        self._filter_rows(self.filter.text())

    def _filter_rows(self, query: str) -> None:
        needle = query.casefold()
        for row in range(self.table.rowCount()):
            first, second = self.table.item(row, 0), self.table.item(row, 1)
            self.table.setRowHidden(row, needle not in first.text().casefold() and needle not in second.text().casefold())

    def _set_box(self, box: Any) -> None:
        if not isinstance(box, dict): return
        self.box_diagram.set_box(box)
        def sides(name: str) -> str:
            value = box.get(name, {})
            if not isinstance(value, dict): return "—"
            return "top {top:.0f} · right {right:.0f} · bottom {bottom:.0f} · left {left:.0f} px".format(**{k: float(value.get(k, 0)) for k in ("top", "right", "bottom", "left")})
        self.box_model.setText(
            f"Margin: {sides('margin')}\nBorder: {sides('border')}\nPadding: {sides('padding')}\nRendered bounds: {float(box.get('width', 0)):.0f} × {float(box.get('height', 0)):.0f} CSS px"
        )

    def _show_rules(self, data: Any, token: int) -> None:
        if token != self._token or not isinstance(data, dict): return
        chunks = []
        for item in data.get("rules", [])[:80]:
            if not isinstance(item, dict): continue
            declarations = item.get("declarations", {})
            rendered = "\n".join(f"  {k}: {v};" for k, v in list(declarations.items())[:80])
            chunks.append(f"{item.get('selector', '')}\nSource: {item.get('source', 'Unavailable')}\n{rendered}")
        inline = data.get("inline", {})
        if inline: chunks.insert(0, "Inline style attribute\n" + "\n".join(f"  {k}: {v};" for k, v in inline.items()))
        self.rules.setPlainText("\n\n".join(chunks) if chunks else "No accessible matching stylesheet rules were found.")
        blocked = int(data.get("blocked", 0) or 0)
        self.status.setText(f"Showing {len(data.get('rules', []))} matching accessible rules. {blocked} stylesheet(s) were unavailable (often cross-origin). Full cascade provenance is not exposed by this API.")

    def _use_property(self, row: int, _column: int) -> None:
        if self.table.item(row, 0) and self.table.item(row, 1):
            self.property_name.setText(self.table.item(row, 0).text())
            self.property_value.setText(self.table.item(row, 1).text())

    def _set_enabled(self, enabled: bool) -> None:
        if hasattr(self, "apply_button"):
            self.apply_button.setEnabled(enabled); self.undo_button.setEnabled(enabled)
            self.redo_button.setEnabled(enabled); self.reset_button.setEnabled(enabled)

    def apply_edit(self) -> None:
        name, value = self.property_name.text().strip(), self.property_value.text()
        if self.page is None or not self.SAFE_PROPERTY.fullmatch(name) or not value.strip() or re.search(r"url\s*\(|expression\s*\(|@import", value, re.I):
            self.status.setText("Enter a CSS property and value accepted by the browser; URL and expression values are blocked."); return
        path, prop, val = path_literal(self.path), json.dumps(name), json.dumps(value[:1000])
        script = f"""(()=>{{{RESOLVE_HELPER}window.__lightmqCssEdits??=[];window.__lightmqCssRedo??=[];window.__lightmqCssBaseline??=new Map();window.__lightmqCssResetAll??=()=>{{for(const [e,props] of window.__lightmqCssBaseline||[])if(e?.isConnected)for(const [p,x] of props){{if(x.before)e.style.setProperty(p,x.before,x.priority);else e.style.removeProperty(p)}}window.__lightmqCssBaseline?.clear();window.__lightmqCssEdits=[];window.__lightmqCssRedo=[]}};const e=resolvePath({path}),p={prop},v={val};if(!e||!CSS.supports(p,v))return {{ok:false}};const before=e.style.getPropertyValue(p),priority=e.style.getPropertyPriority(p),baseline=window.__lightmqCssBaseline;let props=baseline.get(e),tracked=0;for(const values of baseline.values())tracked+=values.size;if((!props||!props.has(p))&&tracked>=200)return {{ok:false,limited:true}};if(!props){{props=new Map();baseline.set(e,props)}}if(!props.has(p))props.set(p,{{before,priority}});e.style.setProperty(p,v);const history=window.__lightmqCssEdits;history.push({{e,p,before,priority,after:v}});if(history.length>100)history.shift();window.__lightmqCssRedo.length=0;return {{ok:true,before,priority}}}})()"""
        token = self._token; run_inspector_data(self.page, script, lambda result: self._applied(result, token))

    def _applied(self, result: Any, token: int) -> None:
        if token != self._token: return
        if isinstance(result, dict) and result.get("ok"):
            self.status.setText("Temporary style applied. It affects only this loaded page and is not saved.")
            self._refresh_selected()
        elif isinstance(result, dict) and result.get("limited"):
            self.status.setText("Reset current CSS edits before making more than 200 unique temporary changes.")
        else: self.status.setText("The browser rejected this CSS value or the selected element is gone.")

    def _refresh_selected(self) -> None:
        if self.page is None: return
        path = path_literal(self.path); token = self._token
        script = f"(()=>{{{SAFE_CSS_HELPER}{RESOLVE_HELPER}const e=resolvePath({path});if(!e)return null;const s=getComputedStyle(e),css={{}};for(let i=0;i<s.length&&i<400;i++)css[s[i]]=lightmqSafeCss(s.getPropertyValue(s[i])).slice(0,240);for(const k of ['margin','padding','border','border-radius'])css[k]=lightmqSafeCss(s.getPropertyValue(k)).slice(0,240);const r=e.getBoundingClientRect();return {{css,box:{{width:r.width,height:r.height}}}}}})()"
        run_inspector_data(self.page, script, lambda result: self._refresh_complete(result, token))

    def _refresh_complete(self, result: Any, token: int) -> None:
        if token != self._token or not isinstance(result, dict): return
        self.properties = result.get("css", {}); self._render(); self._set_box(result.get("box", {}))

    def undo_edit(self) -> None:
        self._edit_history("undo")

    def redo_edit(self) -> None:
        self._edit_history("redo")

    def _edit_history(self, action: str) -> None:
        if self.page is None: return
        if action == "undo":
            script = "(()=>{const a=window.__lightmqCssEdits||[],x=a.pop();if(!x)return false;if(x.before)x.e.style.setProperty(x.p,x.before,x.priority);else x.e.style.removeProperty(x.p);(window.__lightmqCssRedo??=[]).push(x);return true})()"
        else:
            script = "(()=>{const a=window.__lightmqCssRedo||[],x=a.pop();if(!x||!x.e.isConnected)return false;x.e.style.setProperty(x.p,x.after);(window.__lightmqCssEdits??=[]).push(x);return true})()"
        token = self._token
        run_inspector_js(self.page, script, lambda ok: self._history_result(ok, token, action))

    def _history_result(self, ok: Any, token: int, action: str) -> None:
        if token != self._token: return
        self.status.setText(f"Temporary CSS {action} applied." if ok else f"No temporary CSS edit to {action}.")
        if ok: self._refresh_selected()

    def reset_edits(self) -> None:
        if self.page is None: return
        script = "(()=>{const a=window.__lightmqCssBaseline||new Map();let count=0;for(const [e,props] of a)if(e?.isConnected)for(const [p,x] of props){if(x.before)e.style.setProperty(p,x.before,x.priority);else e.style.removeProperty(p);count++}a.clear();window.__lightmqCssEdits=[];window.__lightmqCssRedo=[];return count})()"
        token = self._token
        run_inspector_js(self.page, script, lambda count: self._reset_complete(count, token))

    def _reset_complete(self, count: Any, token: int) -> None:
        if token != self._token: return
        self.status.setText(f"Reset {count} temporary CSS edit(s)." if count else "No temporary CSS edits to reset.")
        if count: self._refresh_selected()
