"""Lazy, bounded DOM inspector backed by the active page's JavaScript context."""

from __future__ import annotations

import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QLineEdit, QPushButton, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget)


class DOMInspector(QWidget):
    """Fetch document children only when a user expands a tree node."""

    element_selected = Signal(str, dict)
    MAX_CHILDREN = 120

    def __init__(self, parent=None):
        super().__init__(parent)
        self.page = None
        self._document_token = 0
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.selector = QLineEdit(); self.selector.setPlaceholderText("Find elements: CSS selector")
        self.find_button = QPushButton("Find")
        self.refresh_button = QPushButton("Refresh")
        self.pick_button = QPushButton("Select Element")
        controls.addWidget(self.selector, 1); controls.addWidget(self.find_button); controls.addWidget(self.refresh_button); controls.addWidget(self.pick_button)
        layout.addLayout(controls)
        self.tree = QTreeWidget(); self.tree.setHeaderLabels(["DOM", "Attributes"]); self.tree.setColumnWidth(0, 230)
        layout.addWidget(self.tree, 1)
        self.status = QLabel("Select a page to inspect")
        layout.addWidget(self.status)
        self.tree.itemExpanded.connect(self._expand)
        self.tree.itemClicked.connect(self._select)
        self.refresh_button.clicked.connect(self.refresh)
        self.find_button.clicked.connect(self.find_elements)
        self.pick_button.clicked.connect(self.start_picker)

    def set_page(self, page) -> None:
        if self.page is not None:
            try:
                self.page.loadStarted.disconnect(self._invalidate)
                self.page.loadFinished.disconnect(self._loaded)
            except (RuntimeError, TypeError):
                pass
        self.page = page
        self._document_token += 1
        if page is not None:
            page.loadStarted.connect(self._invalidate)
            page.loadFinished.connect(self._loaded)
        self.refresh()

    def _invalidate(self) -> None:
        self._document_token += 1
        self.tree.clear()

    def _loaded(self, _ok: bool) -> None:
        self.refresh()

    def refresh(self) -> None:
        self.tree.clear()
        if self.page is None:
            return
        token = self._document_token
        self.page.runJavaScript("({tag:document.documentElement?.tagName||'document', path:[], attrs:{}, children:(document.documentElement?.children.length||0)>0})", lambda data: self._add_root(data, token))

    def _add_root(self, data, token: int) -> None:
        if token != self._document_token or not isinstance(data, dict):
            return
        item = self._make_item(data)
        self.tree.addTopLevelItem(item)
        item.setExpanded(True)
        self.status.setText("DOM metadata is read from the active document; child nodes load on expansion.")

    def _make_item(self, data: dict) -> QTreeWidgetItem:
        tag = str(data.get("tag", "node"))
        attrs = data.get("attrs", {}) if isinstance(data.get("attrs"), dict) else {}
        suffix = ("#" + str(attrs.get("id"))) if attrs.get("id") else ""
        if attrs.get("class"):
            suffix += "." + ".".join(str(attrs["class"]).split()[:4])
        label = ("#text " + str(data.get("text", ""))[:100]) if tag == "#text" else tag.lower() + suffix
        item = QTreeWidgetItem([label, " ".join(f'{k}="{v}"' for k, v in attrs.items())[:500]])
        item.setData(0, Qt.ItemDataRole.UserRole, json.dumps(data.get("path", [])))
        if data.get("children"):
            item.addChild(QTreeWidgetItem(["…", "Expand to load children"]))
        return item

    def _expand(self, item: QTreeWidgetItem) -> None:
        if item.childCount() != 1 or item.child(0).text(0) != "…" or self.page is None:
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        token = self._document_token
        script = f"""(()=>{{let n=document.documentElement;for(const i of {path})n=n?.childNodes[i];if(!n)return[];return Array.from(n.childNodes).slice(0,{self.MAX_CHILDREN}).map((c,i)=>{{const p={path}.concat(i);if(c.nodeType===3)return {{tag:'#text',text:(c.textContent||'').trim().slice(0,100),path:p}};if(c.nodeType!==1)return null;const a={{}};for(const x of Array.from(c.attributes).slice(0,20))a[x.name]=x.value.slice(0,160);return {{tag:c.tagName,path:p,attrs:a,children:c.childNodes.length>0}}}}).filter(Boolean)}})()"""
        self.page.runJavaScript(script, lambda rows: self._populate(item, rows, token))

    def _populate(self, item: QTreeWidgetItem, rows, token: int) -> None:
        if token != self._document_token or not isinstance(rows, list):
            return
        item.takeChildren()
        for row in rows:
            if isinstance(row, dict): item.addChild(self._make_item(row))

    def _select(self, item: QTreeWidgetItem, _column: int) -> None:
        if self.page is None: return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        script = f"""(()=>{{let e=document.documentElement;for(const i of {path})e=e?.childNodes[i];if(!e)return null;const s=getComputedStyle(e),a={{}};if(e.attributes)for(const x of Array.from(e.attributes).slice(0,30))a[x.name]=x.value;return {{tag:e.nodeName,attrs:a,text:(e.textContent||'').trim().slice(0,180),css:{{color:s.color,backgroundColor:s.backgroundColor,fontSize:s.fontSize,fontFamily:s.fontFamily,fontWeight:s.fontWeight,display:s.display,position:s.position,width:s.width,height:s.height,margin:s.margin,padding:s.padding,border:s.border,opacity:s.opacity,overflow:s.overflow,flex:s.flex,gridTemplateColumns:s.gridTemplateColumns}}}}}})()"""
        self.page.runJavaScript(script, lambda result: self.element_selected.emit(path, result or {}) if isinstance(result, dict) else None)

    def find_elements(self) -> None:
        if self.page is None: return
        selector = json.dumps(self.selector.text().strip())
        self.page.runJavaScript(f"(()=>{{try{{return Array.from(document.querySelectorAll({selector})).slice(0,{self.MAX_CHILDREN}).map(e=>({{tag:e.tagName,attrs:Object.fromEntries(Array.from(e.attributes).slice(0,20).map(a=>[a.name,a.value.slice(0,160)])),path:(()=>{{const p=[];while(e&&e!==document.documentElement){{const par=e.parentElement;if(!par)break;p.unshift(Array.prototype.indexOf.call(par.children,e));e=par}}return p}})(),children:e.children.length>0}}))}}catch(e){{return {{error:e.message}}}}}})()", self._found)

    def _found(self, rows) -> None:
        self.tree.clear()
        if isinstance(rows, list):
            for row in rows: self.tree.addTopLevelItem(self._make_item(row))
        elif isinstance(rows, dict): self.status.setText(str(rows.get("error", "No matches")))

    def start_picker(self) -> None:
        if self.page is None: return
        token = self._document_token
        self.status.setText("Inspect mode active — hover and click an element; press Esc to cancel.")
        script = """(()=>{window.__lightmqPickCleanup?.();window.__lightmqPicked=null;let last,oldOutline,oldOffset;function over(e){const t=e.target;if(!(t instanceof Element))return;if(last){last.style.outline=oldOutline;last.style.outlineOffset=oldOffset}last=t;oldOutline=t.style.outline;oldOffset=t.style.outlineOffset;t.style.outline='2px solid #ff9800';t.style.outlineOffset='2px'}function click(e){e.preventDefault();e.stopImmediatePropagation();const t=e.target;const p=[];let n=t;while(n&&n!==document.documentElement){const q=n.parentNode;if(!q)break;p.unshift(Array.prototype.indexOf.call(q.childNodes,n));n=q}cleanup();window.__lightmqPicked={tag:t.tagName,attrs:Object.fromEntries(Array.from(t.attributes).map(a=>[a.name,a.value])),path:p}}function key(e){if(e.key==='Escape')cleanup()}function cleanup(){document.removeEventListener('mouseover',over,true);document.removeEventListener('click',click,true);document.removeEventListener('keydown',key,true);if(last){last.style.outline=oldOutline;last.style.outlineOffset=oldOffset}window.__lightmqPickCleanup=null}window.__lightmqPickCleanup=cleanup;document.addEventListener('mouseover',over,true);document.addEventListener('click',click,true);document.addEventListener('keydown',key,true);return true})()"""
        self.page.runJavaScript(script)
        self._poll_pick(token, 0)

    def _poll_pick(self, token: int, elapsed: int) -> None:
        if token != self._document_token or self.page is None or elapsed >= 120000:
            return
        self.page.runJavaScript("window.__lightmqPicked||null", lambda result: self._poll_result(result, token, elapsed))

    def _poll_result(self, result, token: int, elapsed: int) -> None:
        if isinstance(result, dict):
            self._picked(result, token)
        else:
            QTimer.singleShot(200, lambda: self._poll_pick(token, elapsed + 200))

    def _picked(self, result, token: int) -> None:
        if token == self._document_token and isinstance(result, dict):
            self.element_selected.emit(json.dumps(result.get("path", [])), result)
            self.status.setText(f"Selected {result.get('tag', 'element')}")

    def cancel_picker(self) -> None:
        self._document_token += 1
        if self.page is not None:
            self.page.runJavaScript("window.__lightmqPickCleanup?.()")
