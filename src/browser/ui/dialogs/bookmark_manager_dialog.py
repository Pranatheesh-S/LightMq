"""Native searchable bookmark manager with hierarchy, CRUD, and import/export."""

from pathlib import Path
from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QMessageBox, QPushButton, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget)

from browser.features.bookmarks.bookmark_manager import BookmarkItem, BookmarkManager
from browser.features.bookmarks.bookmark_import_export import import_netscape_file, export_netscape_file


class _ImportSignals(QObject):
    finished=Signal(object)


class _ImportWorker(QRunnable):
    """Keep HTML parsing and transactional insertion off the GUI thread."""

    def __init__(self,manager:BookmarkManager,path:Path):
        super().__init__();self.manager=manager;self.path=path;self.signals=_ImportSignals()

    def run(self):
        try:self.signals.finished.emit(self.manager.import_tree(import_netscape_file(self.path),self.manager.BAR_ROOT_ID))
        except Exception as exc:self.signals.finished.emit(exc)


class _BookmarkTree(QTreeWidget):
    order_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["Name", "URL"])
        self.setColumnWidth(0, 240)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

    def dropEvent(self, event):
        target=self.itemAt(event.position().toPoint())
        if target is not None and target.data(0,Qt.ItemDataRole.UserRole+1)=="bookmark":
            event.ignore()
            return
        super().dropEvent(event)
        self.order_changed.emit()


class BookmarkManagerDialog(QDialog):
    """Browse, search, reorder, import, export, and edit saved bookmarks."""

    open_url_requested = Signal(str, bool)

    def __init__(self, manager: BookmarkManager | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.manager=manager or BookmarkManager.get_instance()
        self.setWindowTitle("LightMq Bookmark Manager")
        self.resize(900,600)
        layout=QVBoxLayout(self)
        self.search=QLineEdit(self); self.search.setPlaceholderText("Search bookmarks by name, URL, or folder…")
        self.search.textChanged.connect(self.refresh)
        layout.addWidget(self.search)
        self.tree=_BookmarkTree(self); self.tree.itemDoubleClicked.connect(self._open_selected)
        self.tree.itemActivated.connect(self._open_selected); self.tree.order_changed.connect(self._save_order)
        self.manager.bookmarks_changed.connect(self.refresh)
        layout.addWidget(self.tree,1)
        self.empty_state=QLabel("No bookmarks match your search.",self);self.empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter);layout.addWidget(self.empty_state)
        self._import_worker=None
        actions=QHBoxLayout()
        for label,slot in (("Open",lambda:self._open_selected(new_tab=False)),("Open in New Tab",lambda:self._open_selected(new_tab=True)),("New Bookmark",self._add_bookmark),("New Folder",self._add_folder),("Edit",self._edit),("Delete",self._delete),("Import…",self._import),("Export…",self._export),("Close",self.accept)):
            button=QPushButton(label,self); button.clicked.connect(slot); actions.addWidget(button)
        layout.addLayout(actions)
        self.refresh()

    def refresh(self, *_args):
        query=self.search.text().strip().casefold()
        selected=self.tree.currentItem().data(0,Qt.ItemDataRole.UserRole) if self.tree.currentItem() else None
        self.tree.clear()
        items=self.manager.all_items()
        children:dict[int|None,list[BookmarkItem]]={}
        for entry in items:
            if entry.parent_id is not None:children.setdefault(entry.parent_id,[]).append(entry)
        visible_items=0
        def build(parent_item, item: BookmarkItem):
            nonlocal visible_items
            child=QTreeWidgetItem([item.title,item.url or ""])
            child.setData(0,Qt.ItemDataRole.UserRole,item.id)
            child.setData(0,Qt.ItemDataRole.UserRole+1,item.item_type)
            if item.is_folder:
                for sub in children.get(item.id,[]): build(child,sub)
            if not query or self._has_match(child,query):
                parent_item.addChild(child)
                visible_items+=1
                if query: child.setExpanded(True)
        for root in self.manager.roots():
            top=QTreeWidgetItem([root.title,""]); top.setData(0,Qt.ItemDataRole.UserRole,root.id); top.setData(0,Qt.ItemDataRole.UserRole+1,"folder")
            top.setFlags(top.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
            for item in children.get(root.id,[]): build(top,item)
            self.tree.addTopLevelItem(top); top.setExpanded(True)
        self.empty_state.setVisible(bool(query) and visible_items==0)
        if selected:
            found=self.tree.findItems("",Qt.MatchFlag.MatchContains|Qt.MatchFlag.MatchRecursive,0)
            for item in found:
                if item.data(0,Qt.ItemDataRole.UserRole)==selected: self.tree.setCurrentItem(item); break

    @staticmethod
    def _has_match(item, query: str) -> bool:
        own=query in item.text(0).casefold() or query in item.text(1).casefold()
        return own or any(BookmarkManagerDialog._has_match(item.child(i),query) for i in range(item.childCount()))

    def _selected(self):
        item=self.tree.currentItem()
        if item is None:return None
        return self.manager.get_item(int(item.data(0,Qt.ItemDataRole.UserRole)))

    def _parent_folder(self) -> int:
        item=self.tree.currentItem()
        if item is None:return self.manager.BAR_ROOT_ID
        selected=self.manager.get_item(int(item.data(0,Qt.ItemDataRole.UserRole)))
        return selected.id if selected and selected.is_folder else (selected.parent_id or self.manager.BAR_ROOT_ID)

    def _add_bookmark(self):
        url,ok=QInputDialog.getText(self,"New Bookmark","Website URL:")
        if not ok:return
        title,ok=QInputDialog.getText(self,"New Bookmark","Name:",text=url)
        if not ok:return
        try:self.manager.create_bookmark(title,url,self._parent_folder())
        except ValueError as exc:QMessageBox.warning(self,"Bookmark not saved",str(exc))

    def _add_folder(self):
        name,ok=QInputDialog.getText(self,"New Folder","Folder name:")
        if ok:
            try:self.manager.create_folder(name,self._parent_folder())
            except ValueError as exc:QMessageBox.warning(self,"Folder not created",str(exc))

    def _edit(self):
        item=self._selected()
        if not item:return
        name,ok=QInputDialog.getText(self,"Edit Bookmark" if not item.is_folder else "Rename Folder","Name:",text=item.title)
        if not ok:return
        url=item.url
        if not item.is_folder:
            url,ok=QInputDialog.getText(self,"Edit Bookmark","URL:",text=item.url or "")
            if not ok:return
        try:self.manager.update_item(item.id,name,url)
        except ValueError as exc:QMessageBox.warning(self,"Bookmark not updated",str(exc))

    def _delete(self):
        item=self._selected()
        if not item:return
        answer=QMessageBox.question(self,"Delete Bookmark" if not item.is_folder else "Delete Folder",f"Delete ‘{item.title}’"+ (" and all items inside it?" if item.is_folder else "?"))
        if answer==QMessageBox.StandardButton.Yes:self.manager.delete_item(item.id)

    def _open_selected(self, *_args, new_tab=False):
        item=self._selected()
        if item and not item.is_folder and item.url:self.open_url_requested.emit(item.url,new_tab)

    def _save_order(self):
        self.manager.blockSignals(True)
        try:
            for idx in range(self.tree.topLevelItemCount()):
                self._save_children(self.tree.topLevelItem(idx))
        finally:
            self.manager.blockSignals(False)
            self.manager.bookmarks_changed.emit()

    def _save_children(self,parent_item):
        parent_id=int(parent_item.data(0,Qt.ItemDataRole.UserRole))
        ids=[int(parent_item.child(i).data(0,Qt.ItemDataRole.UserRole)) for i in range(parent_item.childCount())]
        try:
            for i,item_id in enumerate(ids):
                item=self.manager.get_item(item_id)
                if item and item.parent_id!=parent_id:self.manager.move_item(item_id,parent_id,i)
            actual=[x.id for x in self.manager.children(parent_id)]
            if set(actual)==set(ids):self.manager.reorder(parent_id,ids)
        except ValueError:self.refresh();return
        for i in range(parent_item.childCount()):
            child=parent_item.child(i)
            if child.data(0,Qt.ItemDataRole.UserRole+1)=="folder":self._save_children(child)

    def _import(self):
        filename,_=QFileDialog.getOpenFileName(self,"Import Bookmarks","","HTML bookmark files (*.html *.htm)")
        if not filename:return
        self._import_worker=_ImportWorker(self.manager,Path(filename))
        self._import_worker.signals.finished.connect(self._on_import_finished)
        if self.sender() is not None:
            self.sender().setEnabled(False);self.sender().setText("Importing…")
        QThreadPool.globalInstance().start(self._import_worker)

    def _on_import_finished(self,result):
        self._import_worker=None
        for button in self.findChildren(QPushButton):
            if button.text()=="Importing…":button.setText("Import…");button.setEnabled(True)
        if isinstance(result,Exception):QMessageBox.warning(self,"Import failed",str(result));return
        QMessageBox.information(self,"Import complete",f"Imported {result[0]} bookmark(s) and {result[1]} folder(s). Skipped {result[2]} invalid or duplicate item(s).")

    def _export(self):
        filename,_=QFileDialog.getSaveFileName(self,"Export Bookmarks","bookmarks.html","HTML bookmark files (*.html)")
        if not filename:return
        try:export_netscape_file(Path(filename),[node for root in self.manager.roots() for node in self.manager.export_tree(root.id)])
        except OSError as exc:QMessageBox.warning(self,"Export failed",str(exc))

from PySide6.QtWidgets import QFileDialog
