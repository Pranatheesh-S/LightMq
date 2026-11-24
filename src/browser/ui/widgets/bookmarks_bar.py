"""Hierarchical bookmarks bar with folder menus and overflow handling."""

from PySide6.QtCore import Signal
from PySide6.QtGui import QContextMenuEvent, QAction
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMenu, QPushButton, QToolButton, QWidget

from browser.features.bookmarks.bookmark_manager import BookmarkItem, BookmarkManager
from browser.ui.icons.icon_button import IconButton
from browser.ui.icons.icon_manager import IconManager
from browser.ui.theme_palette import BrowserTheme


class BookmarkButton(QPushButton):
    """Bookmark bar action retaining the stable database record ID."""

    open_requested = Signal(str)
    remove_requested = Signal(str)
    edit_requested = Signal(int)
    new_tab_requested = Signal(str)

    def __init__(self, item: BookmarkItem, parent: QWidget | None = None):
        super().__init__(item.title,parent)
        self.item=item
        self._icon_theme=getattr(parent,"_icon_theme",None)
        self.url=item.url or ""
        self.setToolTip(self.url)
        self.setMaximumWidth(170)
        self.clicked.connect(lambda:self.open_requested.emit(self.url))

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu=QMenu(self)
        actions=(
            ("Open",lambda:self.open_requested.emit(self.url),"bookmark"),
            ("Open in New Tab",lambda:self.new_tab_requested.emit(self.url),"new-window"),
            ("Edit",lambda:self.edit_requested.emit(self.item.id),"edit"),
            ("Copy URL",lambda:QApplication.clipboard().setText(self.url),"edit"),
            ("Delete",lambda:self.remove_requested.emit(self.url),"close"),
        )
        for label,callback,icon_name in actions:
            IconManager.set_action_icon(menu.addAction(label,callback),icon_name,18,self._icon_theme)
        menu.exec(event.globalPos())


class BookmarksBar(QWidget):
    """Render Bookmarks Bar root children and route context actions."""

    open_url_requested=Signal(str)
    open_new_tab_requested=Signal(str)
    edit_requested=Signal(int)
    manager_requested=Signal()

    def __init__(self,bookmark_manager:BookmarkManager|None=None,parent:QWidget|None=None,icon_theme:BrowserTheme|None=None):
        super().__init__(parent)
        self._manager=bookmark_manager or BookmarkManager.get_instance()
        self._icon_theme=icon_theme
        self._layout=QHBoxLayout(self);self._layout.setContentsMargins(8,2,8,2);self._layout.setSpacing(4)
        self.setFixedHeight(34)
        self._manager.bookmarks_changed.connect(self.refresh_bookmarks)
        self.refresh_bookmarks()

    def _clear(self):
        while self._layout.count():
            item=self._layout.takeAt(0)
            if item.widget():item.widget().deleteLater()

    def refresh_bookmarks(self):
        self._clear()
        visible=[]
        for item in self._manager.children(self._manager.BAR_ROOT_ID):
            if item.is_folder:
                button=QToolButton(self);button.setProperty("lightmqIconButton",True);button.setToolTip(f"Open {item.title} bookmark folder")
                IconManager.set_widget_icon(button,"chevron-down",14,self._icon_theme);button.setMinimumHeight(30)
                button.setText(item.title);button.setToolButtonStyle(QToolButton.ToolButtonStyle.ToolButtonTextBesideIcon)
                button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
                menu=QMenu(button);self._fill_menu(menu,item)
                menu.addSeparator()
                self._set_action_icon(menu.addAction("Open All in New Tabs",lambda _=False,folder=item:self._open_all(folder.id)),"tabs")
                self._set_action_icon(menu.addAction("New Bookmark…",lambda _=False,folder=item:self._new_bookmark(folder.id)),"bookmark")
                self._set_action_icon(menu.addAction("New Folder…",lambda _=False,folder=item:self._new_folder(folder.id)),"folder")
                self._set_action_icon(menu.addAction("Rename Folder…",lambda _=False,folder=item:self._rename_folder(folder)),"edit")
                self._set_action_icon(menu.addAction("Delete Folder",lambda _=False,folder=item:self._delete_folder(folder)),"close")
                button.setMenu(menu)
            else:
                button=BookmarkButton(item,self);button.open_requested.connect(self.open_url_requested.emit);button.new_tab_requested.connect(self.open_new_tab_requested.emit);button.edit_requested.connect(self.edit_requested.emit);button.remove_requested.connect(self._remove_url)
            visible.append(button)
        # Fit the row to the actual toolbar width and route the rest through overflow.
        capacity=max(1,(self.width()-80)//150)
        for button in visible[:capacity]:self._layout.addWidget(button)
        if len(visible)>capacity:
            overflow=IconButton("menu","More bookmarks",self,button_size=34,icon_size=18,theme=self._icon_theme);overflow.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            menu=QMenu(overflow)
            for widget in visible[capacity:]:
                item=widget.item if isinstance(widget,BookmarkButton) else None
                if item and item.url:self._set_action_icon(menu.addAction(item.title,lambda checked=False,url=item.url:self.open_url_requested.emit(url)),"bookmark")
                elif item:
                    folder_menu=menu.addMenu(item.title);IconManager.set_action_icon(folder_menu.menuAction(),"folder",18,self._icon_theme);self._fill_menu(folder_menu,item)
            overflow.setMenu(menu);self._layout.addWidget(overflow)
        self._layout.addStretch(1)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.refresh_bookmarks()

    def _fill_menu(self,menu:QMenu,folder:BookmarkItem):
        for item in self._manager.children(folder.id):
            if item.is_folder:
                sub=menu.addMenu(item.title);IconManager.set_action_icon(sub.menuAction(),"folder",18,self._icon_theme);self._fill_menu(sub,item)
                sub.addSeparator()
                self._set_action_icon(sub.addAction("Open All in New Tabs",lambda checked=False,parent=item:self._open_all(parent.id)),"tabs")
                self._set_action_icon(sub.addAction("New Bookmark…",lambda checked=False,parent=item:self._new_bookmark(parent.id)),"bookmark")
                self._set_action_icon(sub.addAction("New Folder…",lambda checked=False,parent=item:self._new_folder(parent.id)),"folder")
                self._set_action_icon(sub.addAction("Rename Folder…",lambda checked=False,parent=item:self._rename_folder(parent)),"edit")
                self._set_action_icon(sub.addAction("Delete Folder",lambda checked=False,parent=item:self._delete_folder(parent)),"close")
            elif item.url:
                action=menu.addAction(item.title,lambda checked=False,url=item.url:self.open_url_requested.emit(url))
                self._set_action_icon(action,"bookmark")
                action.setToolTip(item.url)
                action.setStatusTip(item.url)
                action.setMenuRole(QAction.MenuRole.NoRole)

    def _set_action_icon(self, action: QAction, icon_name: str) -> None:
        """Attach the common theme-aware icon to a bookmark menu action."""
        IconManager.set_action_icon(action,icon_name,18,self._icon_theme)

    def _new_folder(self,parent_id:int):
        from PySide6.QtWidgets import QInputDialog,QMessageBox
        name,ok=QInputDialog.getText(self,"New Bookmark Folder","Folder name:")
        if ok:
            try:self._manager.create_folder(name,parent_id)
            except ValueError as exc:QMessageBox.warning(self,"Folder not created",str(exc))

    def _new_bookmark(self,parent_id:int):
        from PySide6.QtWidgets import QInputDialog,QMessageBox
        url,ok=QInputDialog.getText(self,"New Bookmark","Website URL:")
        if not ok:return
        title,ok=QInputDialog.getText(self,"New Bookmark","Name:",text=url)
        if ok:
            try:self._manager.create_bookmark(title,url,parent_id)
            except ValueError as exc:QMessageBox.warning(self,"Bookmark not saved",str(exc))

    def _open_all(self,parent_id:int):
        def visit(folder_id:int):
            for item in self._manager.children(folder_id):
                if item.is_folder:visit(item.id)
                elif item.url:self.open_new_tab_requested.emit(item.url)
        visit(parent_id)

    def _rename_folder(self,item:BookmarkItem):
        from PySide6.QtWidgets import QInputDialog,QMessageBox
        name,ok=QInputDialog.getText(self,"Rename Folder","Folder name:",text=item.title)
        if ok:
            try:self._manager.update_item(item.id,name)
            except ValueError as exc:QMessageBox.warning(self,"Folder not renamed",str(exc))

    def _delete_folder(self,item:BookmarkItem):
        from PySide6.QtWidgets import QMessageBox
        if QMessageBox.question(self,"Delete Folder",f"Delete ‘{item.title}’ and all bookmarks inside it?")==QMessageBox.StandardButton.Yes:
            self._manager.delete_item(item.id)

    def _remove_url(self,url:str):self._manager.remove_bookmark(url)

    def contextMenuEvent(self,event:QContextMenuEvent):
        menu=QMenu(self);menu.addAction("Open Bookmark Manager…",self.manager_requested.emit)
        menu.addAction("New Folder…",lambda:self._new_folder(self._manager.BAR_ROOT_ID));menu.exec(event.globalPos())

from PySide6.QtWidgets import QApplication
