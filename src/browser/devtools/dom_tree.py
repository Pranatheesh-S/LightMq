"""Lazy DOM tree and privacy-filtered HTML inspector for active web pages."""

from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
    QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from browser.devtools.inspector_bridge import (
    DETAILS_SCRIPT, MAX_INSPECTED_HTML, MAX_INSPECTED_TEXT, PICKER_START_SCRIPT,
    SELECTED_HIGHLIGHT_SCRIPT,
    RESOLVE_HELPER, path_literal, run_inspector_data, run_inspector_js,
)


class DOMInspector(QWidget):
    """Inspect selected elements without retaining page data past the active tab."""

    element_selected = Signal(str, dict)
    MAX_CHILDREN = 120
    PICK_INTERVAL_MS = 120
    PICK_TIMEOUT_MS = 120_000

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.page = None
        self._document_token = 0
        self._picker_active = False
        self._pick_elapsed = 0
        self._selected_path = "[]"
        self._selected_data: dict[str, Any] = {}
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.selector = QLineEdit(); self.selector.setPlaceholderText("Find elements: CSS selector")
        self.find_button = QPushButton("Find")
        self.refresh_button = QPushButton("Refresh")
        self.pick_button = QPushButton("Select Element")
        controls.addWidget(self.selector, 1); controls.addWidget(self.find_button)
        controls.addWidget(self.refresh_button); controls.addWidget(self.pick_button)
        layout.addLayout(controls)
        self.tabs = QTabWidget(self)
        tree_page = QWidget(self.tabs); tree_layout = QVBoxLayout(tree_page)
        self.tree = QTreeWidget(); self.tree.setHeaderLabels(["DOM", "Attributes"]); self.tree.setColumnWidth(0, 230)
        tree_layout.addWidget(self.tree)
        self.tabs.addTab(tree_page, "DOM Tree")
        detail_page = QWidget(self.tabs); detail_layout = QVBoxLayout(detail_page)
        self.selected_label = QLabel("No element selected")
        detail_layout.addWidget(self.selected_label)
        self.details = QPlainTextEdit(); self.details.setReadOnly(True); self.details.setPlaceholderText("Select an element to inspect its HTML, attributes and dimensions.")
        detail_layout.addWidget(self.details, 1)
        copy_row = QHBoxLayout()
        for label, key in (("Outer HTML", "outer"), ("Inner HTML", "inner"), ("Text", "text"), ("Selector", "selector"), ("XPath", "xpath")):
            button = QPushButton("Copy " + label); button.clicked.connect(lambda _=False, k=key: self.copy_detail(k)); copy_row.addWidget(button)
        detail_layout.addLayout(copy_row)
        nav_row = QHBoxLayout()
        self.parent_button = QPushButton("Select Parent")
        self.child_button = QPushButton("Select First Child")
        self.parent_button.clicked.connect(self.select_parent); self.child_button.clicked.connect(self.select_first_child)
        nav_row.addWidget(self.parent_button); nav_row.addWidget(self.child_button); detail_layout.addLayout(nav_row)
        self.tabs.addTab(detail_page, "Element")
        edit_row = QHBoxLayout()
        self.text_edit = QLineEdit(); self.text_edit.setPlaceholderText("Leaf element text (temporary)")
        self.text_apply = QPushButton("Set Text")
        self.attr_name = QLineEdit(); self.attr_name.setPlaceholderText("title / aria-label / data-…")
        self.attr_value = QLineEdit(); self.attr_value.setPlaceholderText("Attribute value")
        self.attr_apply = QPushButton("Set Attribute"); self.attr_remove = QPushButton("Remove")
        edit_row.addWidget(self.text_edit, 2); edit_row.addWidget(self.text_apply)
        edit_row.addWidget(self.attr_name); edit_row.addWidget(self.attr_value, 2)
        edit_row.addWidget(self.attr_apply); edit_row.addWidget(self.attr_remove)
        detail_layout.addLayout(edit_row)
        self.reset_html_button = QPushButton("Reset temporary HTML edits")
        self.reset_html_button.clicked.connect(self.reset_html_edits)
        detail_layout.addWidget(self.reset_html_button)
        self.status = QLabel("Select a page to inspect")
        layout.addWidget(self.tabs, 1); layout.addWidget(self.status)
        self.tree.itemExpanded.connect(self._expand); self.tree.itemClicked.connect(self._select)
        self.refresh_button.clicked.connect(self.refresh); self.find_button.clicked.connect(self.find_elements)
        self.pick_button.clicked.connect(self.toggle_picker)
        self.text_apply.clicked.connect(self.apply_text_edit); self.attr_apply.clicked.connect(self.apply_attribute_edit)
        self.attr_remove.clicked.connect(lambda: self.apply_attribute_edit(remove=True))
        self._escape = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self._escape.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._escape.activated.connect(self.cancel_picker)
        self._set_editing_enabled(False)

    @property
    def picker_active(self) -> bool:
        return self._picker_active

    def set_page(self, page) -> None:
        """Switch inspected page and invalidate every old element reference."""
        previous = self.page
        if previous is not None:
            try:
                run_inspector_js(previous, "window.__lightmqInspectorStop?.(true);window.__lightmqInspectorClear?.()")
                previous.loadStarted.disconnect(self._invalidate)
                previous.loadFinished.disconnect(self._loaded)
                previous.renderProcessTerminated.disconnect(self._render_process_terminated)
            except (RuntimeError, TypeError):
                pass
        self.page = page
        self._document_token += 1
        self._picker_active = False
        self._clear_selection()
        self.tree.clear()
        self.status.setText("Select a page to inspect" if page is not None else "Inspector unavailable for this tab type.")
        if page is not None:
            try:
                page.loadStarted.connect(self._invalidate)
                page.loadFinished.connect(self._loaded)
                page.renderProcessTerminated.connect(self._render_process_terminated)
            except (RuntimeError, AttributeError):
                self.page = None
                self.status.setText("Inspector unavailable for this document.")
                return
            self.refresh()

    def _invalidate(self) -> None:
        self._document_token += 1
        self._picker_active = False
        if self.page is not None:
            run_inspector_js(self.page, "window.__lightmqInspectorStop?.(true);window.__lightmqInspectorClear?.()")
        self.tree.clear(); self._clear_selection()
        self.status.setText("Page navigated; previous selection cleared.")

    def _loaded(self, _ok: bool) -> None:
        self.refresh()

    def _render_process_terminated(self, *_args: Any) -> None:
        """Forget selections and picker state if Chromium destroys the renderer."""
        self._document_token += 1
        self._picker_active = False
        self.pick_button.setText("Select Element")
        self.tree.clear()
        self._clear_selection()
        self.status.setText("The page renderer stopped. Reload the page before inspecting it again.")

    def refresh(self) -> None:
        self.tree.clear()
        if self.page is None:
            return
        token = self._document_token
        run_inspector_data(self.page, "({tag:document.documentElement?.tagName||'document',path:[],attrs:{},children:(document.documentElement?.childNodes.length||0)>0})", lambda data: self._add_root(data, token))

    def _add_root(self, data: Any, token: int) -> None:
        if token != self._document_token or not isinstance(data, dict): return
        item = self._make_item(data); self.tree.addTopLevelItem(item); item.setExpanded(True)
        self.status.setText("DOM tree loads children on expansion. Cross-origin iframe contents are isolated by Chromium.")

    @staticmethod
    def _safe_attrs(attrs: Any) -> dict[str, str]:
        if not isinstance(attrs, dict): return {}
        sensitive = ("password", "secret", "token", "auth", "cookie", "session", "credit", "cvv", "code=")
        return {str(k)[:80]: str(v)[:240] for k, v in list(attrs.items())[:40]
                if str(k).lower() != "value" and not any(s in str(k).lower() or s in str(v).lower() for s in sensitive)}

    def _make_item(self, data: dict[str, Any]) -> QTreeWidgetItem:
        tag = str(data.get("tag", "node"))[:80]
        attrs = self._safe_attrs(data.get("attrs"))
        suffix = ("#" + str(attrs.get("id"))) if attrs.get("id") else ""
        if attrs.get("class"): suffix += "." + ".".join(str(attrs["class"]).split()[:4])
        label = ("#text " + str(data.get("text", ""))[:100]) if tag == "#text" else tag.lower() + suffix
        item = QTreeWidgetItem([label, " ".join(f'{k}="{v}"' for k, v in attrs.items())[:600]])
        item.setData(0, Qt.ItemDataRole.UserRole, json.dumps(data.get("path", [])))
        if data.get("children"): item.addChild(QTreeWidgetItem(["…", "Expand to load children"]))
        return item

    def _expand(self, item: QTreeWidgetItem) -> None:
        if item.childCount() != 1 or item.child(0).text(0) != "…" or self.page is None: return
        path = path_literal(item.data(0, Qt.ItemDataRole.UserRole)); token = self._document_token
        script = f"""(()=>{{{RESOLVE_HELPER}const n=resolvePath({path});if(!n)return[];let nodes=Array.from(n.childNodes).slice(0,{self.MAX_CHILDREN});const shadow=n.shadowRoot;if(shadow)nodes=nodes.concat(Array.from(shadow.childNodes).slice(0,{self.MAX_CHILDREN}-nodes.length).map((node,index)=>({{node,shadowIndex:index}})));return nodes.map((entry,i)=>{{const c=entry.node||entry,p={path}.concat(entry.shadowIndex!==undefined?[{{shadow:true,index:entry.shadowIndex}}]:[i]);if(c.nodeType===3)return {{tag:'#text',text:(c.textContent||'').trim().slice(0,100),path:p}};if(c.nodeType!==1)return null;const a={{}};for(const x of Array.from(c.attributes).slice(0,40))if(x.name!=='value'&&!/(pass(word)?|secret|token|auth|cookie|session|credit.?card|cvv|security.?code|(^|[_-])code([_-]|$))/i.test(x.name+' '+x.value))a[x.name]=x.value.slice(0,240);return {{tag:c.tagName,path:p,attrs:a,children:c.childNodes.length>0||!!c.shadowRoot}}}}).filter(Boolean)}})()"""
        run_inspector_data(self.page, script, lambda rows: self._populate(item, rows, token))

    def _populate(self, item: QTreeWidgetItem, rows: Any, token: int) -> None:
        if token != self._document_token or not isinstance(rows, list): return
        item.takeChildren()
        for row in rows[:self.MAX_CHILDREN]:
            if isinstance(row, dict): item.addChild(self._make_item(row))

    def _select(self, item: QTreeWidgetItem, _column: int) -> None:
        self.select_path(item.data(0, Qt.ItemDataRole.UserRole))

    def select_path(self, raw_path: str | list[Any]) -> None:
        if self.page is None: return
        path = path_literal(raw_path); token = self._document_token
        script = DETAILS_SCRIPT.replace("__RESOLVE__", RESOLVE_HELPER).replace("__PATH__", path)
        run_inspector_data(self.page, script, lambda result: self._show_selection(path, result, token))

    def _show_selection(self, path: str, result: Any, token: int) -> None:
        if token != self._document_token: return
        if not isinstance(result, dict):
            self.status.setText("Could not inspect this element; the page may have navigated or blocked access."); self._clear_selection(); return
        if result.get("detached"):
            self.status.setText("Selected element is no longer in the page. Select it again."); self._clear_selection(); return
        self._selected_path, self._selected_data = path, result
        tag, element_id = str(result.get("tag", "element")).lower(), str(result.get("id", ""))
        classes = " ".join(str(result.get("class", "")).split()[:4])
        label = tag + ("#" + element_id if element_id else "") + ("." + classes.replace(" ", ".") if classes else "")
        self.selected_label.setText("Selected: " + label + (" (selector may be non-unique)" if not result.get("selectorUnique") else ""))
        outer = str(result.get("outer", ""))[:MAX_INSPECTED_HTML]
        details = {
            "HTML (sensitive form values redacted)": outer,
            "Text": str(result.get("text", ""))[:MAX_INSPECTED_TEXT],
            "Attributes": json.dumps(self._safe_attrs(result.get("attrs")), ensure_ascii=False, indent=2),
            "CSS selector": str(result.get("selector", "")),
            "XPath": str(result.get("xpath", "")),
            "Dimensions": json.dumps(result.get("box", {}), ensure_ascii=False, indent=2),
            "Parent": json.dumps(result.get("parent"), ensure_ascii=False),
            "Children (first 40)": json.dumps(result.get("children", []), ensure_ascii=False, indent=2),
            "Frame": ("Selected iframe element. This inspector does not cross into its document; cross-origin frame access remains blocked by Chromium." if tag == "iframe" else ("Element is inside an accessible open shadow root." if result.get("shadow") else "Top-level document")),
            "Shadow DOM": ("Element is inside an accessible open shadow root." if result.get("shadow") else ("No open shadow root is exposed on this element. A closed shadow root, if present, cannot be inspected through standard DOM APIs." if not result.get("openShadow") else "This element exposes an open shadow root.")),
            "Inline event attributes": json.dumps(result.get("inline", {}), ensure_ascii=False, indent=2) or "{}",
            "Event listener details": "Not available through standard DOM inspection. Open Chromium DevTools for advanced event/source debugging.",
        }
        self.details.setPlainText("\n\n".join(f"{key}\n{value}" for key, value in details.items()))
        box = result.get("box", {})
        self.status.setText(f"Selected {tag}; {float(box.get('width', 0)):.0f} × {float(box.get('height', 0)):.0f} CSS px. Live edits are temporary and are not saved to the site.")
        self.text_edit.setText(str(result.get("text", ""))[:MAX_INSPECTED_TEXT])
        self._set_editing_enabled(True)
        highlight = SELECTED_HIGHLIGHT_SCRIPT.replace("__RESOLVE__", RESOLVE_HELPER).replace("__PATH__", path)
        run_inspector_js(self.page, highlight)
        self.element_selected.emit(path, result)

    def _clear_selection(self) -> None:
        self._selected_path = "[]"; self._selected_data = {}
        if hasattr(self, "selected_label"):
            self.selected_label.setText("No element selected"); self.details.clear(); self._set_editing_enabled(False)
        self.element_selected.emit("[]", {})

    def _set_editing_enabled(self, enabled: bool) -> None:
        if not hasattr(self, "text_apply"): return
        safe_text = enabled and not str(self._selected_data.get("tag", "")).lower() in {"input", "textarea", "select", "option"} and not bool(self._selected_data.get("children"))
        self.text_edit.setEnabled(safe_text); self.text_apply.setEnabled(safe_text)
        self.attr_name.setEnabled(enabled); self.attr_value.setEnabled(enabled)
        self.attr_apply.setEnabled(enabled); self.attr_remove.setEnabled(enabled); self.reset_html_button.setEnabled(enabled)

    def copy_detail(self, key: str) -> None:
        value = self._selected_data.get(key)
        if value is None: return
        QApplication.clipboard().setText(str(value)[:MAX_INSPECTED_HTML])
        self.status.setText(f"Copied {key} to clipboard.")

    def select_parent(self) -> None:
        try: path = json.loads(self._selected_path)
        except json.JSONDecodeError: return
        if path: self.select_path(path[:-1])
        else: self.status.setText("The document root has no selectable parent.")

    def select_first_child(self) -> None:
        path = self._selected_data.get("firstChildPath")
        if isinstance(path, list): self.select_path(path)
        else: self.status.setText("No child element is available in this selection.")

    @staticmethod
    def _safe_edit_attribute(name: str) -> bool:
        lowered = name.lower()
        return (lowered in {"title", "alt", "role", "class", "aria-label", "aria-description"}
                or lowered.startswith("aria-") or lowered.startswith("data-")) and not lowered.startswith("on")

    def apply_text_edit(self) -> None:
        if self.page is None or not self._selected_data: return
        path = path_literal(self._selected_path); value = json.dumps(self.text_edit.text()[:MAX_INSPECTED_TEXT])
        script = f"(()=>{{{RESOLVE_HELPER}const e=resolvePath({path});if(!e||e.children.length||/^(INPUT|TEXTAREA|SELECT|OPTION)$/.test(e.tagName))return false;window.__lightmqHtmlEdits??=new Map();window.__lightmqHtmlResetAll??=()=>{{for(const [n,m] of window.__lightmqHtmlEdits){{if(m.text!==undefined)n.textContent=m.text;for(const [k,v] of m.attrs||[])v===null?n.removeAttribute(k):n.setAttribute(k,v)}}window.__lightmqHtmlEdits.clear()}};let m=window.__lightmqHtmlEdits.get(e);if(!m){{if(window.__lightmqHtmlEdits.size>=100)return {{limited:true}};m={{text:e.textContent,attrs:new Map()}};window.__lightmqHtmlEdits.set(e,m)}}e.textContent={value};return true}})()"
        token = self._document_token
        run_inspector_js(self.page, script, lambda ok: self._edit_complete(ok, token, "Temporary text change applied."))

    def apply_attribute_edit(self, remove: bool = False) -> None:
        if self.page is None or not self._selected_data: return
        name = self.attr_name.text().strip()
        if not self._safe_edit_attribute(name):
            self.status.setText("Only title, alt, role, class, aria-* and data-* attributes may be changed."); return
        path = path_literal(self._selected_path); key = json.dumps(name); value = json.dumps(self.attr_value.text()[:1000])
        action = f"e.removeAttribute({key})" if remove else f"e.setAttribute({key},{value})"
        script = f"(()=>{{{RESOLVE_HELPER}const e=resolvePath({path});if(!e)return false;window.__lightmqHtmlEdits??=new Map();window.__lightmqHtmlResetAll??=()=>{{for(const [n,m] of window.__lightmqHtmlEdits){{if(m.text!==undefined)n.textContent=m.text;for(const [k,v] of m.attrs||[])v===null?n.removeAttribute(k):n.setAttribute(k,v)}}window.__lightmqHtmlEdits.clear()}};let m=window.__lightmqHtmlEdits.get(e);if(!m){{if(window.__lightmqHtmlEdits.size>=100)return {{limited:true}};m={{attrs:new Map()}};window.__lightmqHtmlEdits.set(e,m)}}if(!m.attrs.has({key}))m.attrs.set({key},e.hasAttribute({key})?e.getAttribute({key}):null);{action};return true}})()"
        token = self._document_token
        run_inspector_js(self.page, script, lambda ok: self._edit_complete(ok, token, "Temporary attribute change applied."))

    def _edit_complete(self, ok: Any, token: int, message: str) -> None:
        if token != self._document_token: return
        if isinstance(ok, dict) and ok.get("limited"):
            self.status.setText("Reset temporary HTML edits before editing more than 100 elements.")
            return
        if ok:
            self.status.setText(message + " Website files are not changed."); self.select_path(self._selected_path)
        else: self.status.setText("The selected element changed or is no longer available.")

    def reset_html_edits(self) -> None:
        if self.page is None or not self._selected_data: return
        path = path_literal(self._selected_path)
        script = f"(()=>{{{RESOLVE_HELPER}const e=resolvePath({path}),m=e&&window.__lightmqHtmlEdits?.get(e);if(!m)return false;if(m.text!==undefined)e.textContent=m.text;for(const [k,v] of m.attrs||[])v===null?e.removeAttribute(k):e.setAttribute(k,v);window.__lightmqHtmlEdits.delete(e);return true}})()"
        token = self._document_token
        run_inspector_js(self.page, script, lambda ok: self._edit_complete(ok, token, "Temporary HTML edits restored."))

    def clear_inspector_state(self) -> None:
        """Stop page listeners and restore temporary HTML edits before closing tools."""
        self.cancel_picker()
        if self.page is not None:
            run_inspector_js(self.page, "window.__lightmqHtmlResetAll?.()")
        self.tree.clear(); self._clear_selection()
        self.status.setText("Inspector data cleared.")

    def find_elements(self) -> None:
        if self.page is None: return
        selector = json.dumps(self.selector.text().strip())
        script = f"""(()=>{{try{{const pathOf=e=>{{const p=[];while(e&&e!==document.documentElement){{const par=e.parentNode;if(par instanceof ShadowRoot){{p.unshift({{shadow:true,index:Array.prototype.indexOf.call(par.childNodes,e)}});e=par.host}}else{{if(!par)break;p.unshift(Array.prototype.indexOf.call(par.childNodes,e));e=par}}}}return p}};return Array.from(document.querySelectorAll({selector})).slice(0,{self.MAX_CHILDREN}).map(e=>{{const a={{}};for(const x of Array.from(e.attributes).slice(0,40))if(x.name!=='value'&&!/(pass(word)?|secret|token|auth|cookie|session|credit.?card|cvv|security.?code|(^|[_-])code([_-]|$))/i.test(x.name+' '+x.value))a[x.name]=x.value.slice(0,240);return {{tag:e.tagName,attrs:a,path:pathOf(e),children:e.childNodes.length>0||!!e.shadowRoot}}}})}}catch(e){{return {{error:'Invalid or inaccessible selector'}}}}}})()"""
        token = self._document_token
        run_inspector_data(self.page, script, lambda rows: self._found(rows, token))

    def _found(self, rows: Any, token: int) -> None:
        if token != self._document_token: return
        self.tree.clear()
        if isinstance(rows, list):
            for row in rows[:self.MAX_CHILDREN]: self.tree.addTopLevelItem(self._make_item(row))
            self.status.setText(f"Showing up to {self.MAX_CHILDREN} matching elements.")
        elif isinstance(rows, dict): self.status.setText(str(rows.get("error", "No matches")))

    def toggle_picker(self) -> None:
        if self._picker_active: self.cancel_picker()
        else: self.start_picker()

    def start_picker(self) -> None:
        if self.page is None: self.status.setText("Select a webpage tab before starting the element picker."); return
        self._picker_active = True; self._pick_elapsed = 0; token = self._document_token
        self.pick_button.setText("Stop Selecting")
        self.status.setText("Picker active — hover to highlight, click to select, or press Esc to cancel.")
        run_inspector_js(self.page, PICKER_START_SCRIPT)
        QTimer.singleShot(self.PICK_INTERVAL_MS, lambda: self._poll_pick(token))

    def _poll_pick(self, token: int) -> None:
        if token != self._document_token or not self._picker_active or self.page is None: return
        self._pick_elapsed += self.PICK_INTERVAL_MS
        if self._pick_elapsed >= self.PICK_TIMEOUT_MS:
            self.cancel_picker(); self.status.setText("Element picker timed out and was stopped."); return
        run_inspector_data(self.page, "window.__lightmqPickedPath||null", lambda result: self._picked(result, token))

    def _picked(self, result: Any, token: int) -> None:
        if token != self._document_token or not self._picker_active: return
        if isinstance(result, dict) and result.get("cancelled"):
            self.cancel_picker(); self.status.setText("Element selection cancelled."); return
        if isinstance(result, list):
            self._picker_active = False; self.pick_button.setText("Select Element")
            self.select_path(result); self.tabs.setCurrentIndex(1); return
        QTimer.singleShot(self.PICK_INTERVAL_MS, lambda: self._poll_pick(token))

    def cancel_picker(self) -> None:
        was_active = self._picker_active
        self._picker_active = False; self.pick_button.setText("Select Element")
        if self.page is not None:
            run_inspector_js(self.page, "window.__lightmqInspectorStop?.(true);window.__lightmqPickedPath=null")
        if was_active: self.status.setText("Element picker stopped.")
