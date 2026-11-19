"""Tab bar UI component for LightMq Browser.

Hosts a closable, movable QTabBar paired with an intuitive '+' button to create new tabs.
Displays dynamic titles and favicons with text elision.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QTabBar,
    QWidget,
)


class TabBar(QWidget):
    """Custom tab bar container widget displaying tabs and a new-tab button."""

    tab_close_requested = Signal(int)
    current_changed = Signal(int)
    new_tab_requested = Signal()
    tab_moved = Signal(int, int)

    MAX_TITLE_LENGTH = 28

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        """Construct the horizontal tab bar layout and controls."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 0)
        layout.setSpacing(4)

        # Native Qt TabBar
        self._tab_bar = QTabBar(self)
        self._tab_bar.setTabsClosable(True)
        self._tab_bar.setMovable(True)
        self._tab_bar.setExpanding(False)
        self._tab_bar.setDrawBase(False)
        self._tab_bar.setElideMode(Qt.TextElideMode.ElideRight)

        # Style tab bar for clean browser look
        self._tab_bar.setStyleSheet(
            "QTabBar::tab {"
            "   background: #E8EAED;"
            "   color: #3C4043;"
            "   padding: 6px 14px;"
            "   margin-right: 2px;"
            "   border-top-left-radius: 6px;"
            "   border-top-right-radius: 6px;"
            "   max-width: 220px;"
            "   min-width: 90px;"
            "}"
            "QTabBar::tab:selected {"
            "   background: #FFFFFF;"
            "   color: #202124;"
            "   font-weight: bold;"
            "}"
            "QTabBar::tab:hover:!selected {"
            "   background: #F1F3F4;"
            "}"
        )

        # New Tab (+) Button
        self._btn_new = QPushButton("+", self)
        self._btn_new.setToolTip("New Tab (Ctrl+T)")
        self._btn_new.setFixedSize(26, 26)
        self._btn_new.setStyleSheet(
            "QPushButton {"
            "   border: none;"
            "   border-radius: 13px;"
            "   font-size: 16px;"
            "   font-weight: bold;"
            "   color: #5F6368;"
            "   background: transparent;"
            "}"
            "QPushButton:hover {"
            "   background-color: #E8EAED;"
            "   color: #202124;"
            "}"
        )

        layout.addWidget(self._tab_bar)
        layout.addWidget(self._btn_new)
        layout.addStretch()

        # Connect internal signals
        self._tab_bar.tabCloseRequested.connect(self.tab_close_requested.emit)
        self._tab_bar.currentChanged.connect(self.current_changed.emit)
        self._tab_bar.tabMoved.connect(self.tab_moved.emit)
        self._btn_new.clicked.connect(self.new_tab_requested.emit)

    def count(self) -> int:
        """Return the count of tabs currently in the tab bar."""
        return self._tab_bar.count()

    def current_index(self) -> int:
        """Return the index of the currently active tab."""
        return self._tab_bar.currentIndex()

    def set_current_index(self, index: int) -> None:
        """Set the active tab index without re-triggering recursive events.

        Args:
            index: Target tab index.
        """
        if 0 <= index < self._tab_bar.count():
            self._tab_bar.blockSignals(True)
            self._tab_bar.setCurrentIndex(index)
            self._tab_bar.blockSignals(False)

    def insert_tab(self, index: int, title: str = "New Tab", icon: QIcon | None = None) -> int:
        """Insert a tab at the given index.

        Args:
            index: Target insertion index.
            title: Tab text label.
            icon: Optional tab favicon.

        Returns:
            int: Created tab index.
        """
        truncated_title = self._format_title(title)
        if icon is not None and not icon.isNull():
            return self._tab_bar.insertTab(index, icon, truncated_title)
        return self._tab_bar.insertTab(index, truncated_title)

    def add_tab(self, title: str = "New Tab", icon: QIcon | None = None) -> int:
        """Append a new tab at the end of the tab bar.

        Args:
            title: Tab text label.
            icon: Optional tab favicon.

        Returns:
            int: Created tab index.
        """
        return self.insert_tab(self._tab_bar.count(), title, icon)

    def remove_tab(self, index: int) -> None:
        """Remove the tab at the given index.

        Args:
            index: Tab index to remove.
        """
        if 0 <= index < self._tab_bar.count():
            self._tab_bar.removeTab(index)

    def set_tab_title(self, index: int, title: str) -> None:
        """Update tab label text.

        Args:
            index: Tab index.
            title: New title string.
        """
        if 0 <= index < self._tab_bar.count():
            formatted = self._format_title(title)
            self._tab_bar.setTabText(index, formatted)

    def set_tab_icon(self, index: int, icon: QIcon) -> None:
        """Update tab favicon.

        Args:
            index: Tab index.
            icon: Favicon QIcon.
        """
        if 0 <= index < self._tab_bar.count():
            self._tab_bar.setTabIcon(index, icon)

    def set_tab_tooltip(self, index: int, tooltip: str) -> None:
        """Set the tooltip string for the tab at index.

        Args:
            index: Tab index.
            tooltip: Tooltip string (typically full URL or title).
        """
        if 0 <= index < self._tab_bar.count():
            self._tab_bar.setTabToolTip(index, tooltip)

    def _format_title(self, title: str) -> str:
        """Clean and truncate titles longer than MAX_TITLE_LENGTH."""
        cleaned = title.strip() or "New Tab"
        if len(cleaned) > self.MAX_TITLE_LENGTH:
            return cleaned[: self.MAX_TITLE_LENGTH - 1] + "…"
        return cleaned
