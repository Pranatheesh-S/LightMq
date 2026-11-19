"""Bookmarks bar widget for LightMq Browser.

Displays quick-access bookmark buttons below the toolbar with click-to-navigate
and context menu management.
"""

from collections.abc import Callable
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QContextMenuEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMenu,
    QPushButton,
    QWidget,
)

from browser.features.bookmarks.bookmark_manager import BookmarkManager


class BookmarkButton(QPushButton):
    """Clickable bookmark button with context menu."""

    open_requested = Signal(str)
    remove_requested = Signal(str)

    def __init__(self, title: str, url: str, parent: QWidget | None = None):
        super().__init__(title, parent)
        self.url = url
        self.setToolTip(url)
        self.setMaximumWidth(160)
        self.clicked.connect(lambda: self.open_requested.emit(self.url))

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """Show context menu to remove bookmark."""
        menu = QMenu(self)
        action_open = menu.addAction("Open")
        action_open.triggered.connect(lambda: self.open_requested.emit(self.url))
        action_remove = menu.addAction("Delete Bookmark")
        action_remove.triggered.connect(lambda: self.remove_requested.emit(self.url))
        menu.exec(event.globalPos())


class BookmarksBar(QWidget):
    """Bar displaying pinned user bookmarks below the navigation toolbar."""

    open_url_requested = Signal(str)

    def __init__(
        self,
        bookmark_manager: BookmarkManager | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._manager = bookmark_manager or BookmarkManager.get_instance()
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(8, 2, 8, 2)
        self._layout.setSpacing(4)
        self.setFixedHeight(32)

        self._manager.bookmarks_changed.connect(self.refresh_bookmarks)
        self.refresh_bookmarks()

    def refresh_bookmarks(self) -> None:
        """Re-render bookmark buttons from manager data."""
        # Clear existing buttons
        while self._layout.count() > 0:
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        bookmarks = self._manager.get_bookmarks()
        for bm in bookmarks:
            btn = BookmarkButton(bm["title"], bm["url"], self)
            btn.open_requested.connect(self.open_url_requested.emit)
            btn.remove_requested.connect(self._manager.remove_bookmark)
            self._layout.addWidget(btn)

        self._layout.addStretch()
