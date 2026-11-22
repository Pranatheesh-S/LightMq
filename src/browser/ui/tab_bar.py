"""Chrome-inspired tab strip with pinned tabs and group headers."""

from PySide6.QtCore import Qt, Signal, QPoint, QEvent, QObject, QMimeData
from PySide6.QtGui import QIcon, QDrag, QDragEnterEvent, QDragMoveEvent, QDropEvent, QMouseEvent
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QTabBar, QToolButton, QVBoxLayout, QWidget, QMenu, QApplication

from browser.core.tab_group_manager import TabGroup


class _GroupHeaderRow(QWidget):
    reorder_requested = Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        group_id = event.mimeData().text()
        buttons = [child for child in self.findChildren(QPushButton) if child.property("group_id")]
        target = len(buttons)
        for index, button in enumerate(buttons):
            if event.position().x() < button.geometry().center().x():
                target = index
                break
        self.reorder_requested.emit(group_id, target)
        event.acceptProposedAction()


class TabBar(QWidget):
    tab_close_requested = Signal(int)
    current_changed = Signal(int)
    new_tab_requested = Signal()
    tab_moved = Signal(int, int)
    tab_context_requested = Signal(int, QPoint)
    group_context_requested = Signal(str, QPoint)
    group_toggle_requested = Signal(str)
    group_reorder_requested = Signal(str, int)

    MAX_TITLE_LENGTH = 28

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._tab_ids: dict[int, str] = {}
        self._pinned: dict[str, bool] = {}
        self._titles: dict[str, str] = {}
        self._groups = ()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 2, 6, 0)
        outer.setSpacing(0)
        self._groups_row = _GroupHeaderRow(self)
        self._groups_row.reorder_requested.connect(self.group_reorder_requested)
        self._groups_layout = QHBoxLayout(self._groups_row)
        self._groups_layout.setContentsMargins(0, 0, 0, 0)
        self._groups_layout.setSpacing(3)
        outer.addWidget(self._groups_row)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        self._tab_bar = QTabBar(self)
        self._tab_bar.setTabsClosable(False)
        self._tab_bar.setMovable(True)
        self._tab_bar.setExpanding(False)
        self._tab_bar.setDrawBase(False)
        self._tab_bar.setElideMode(Qt.TextElideMode.ElideRight)
        self._tab_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tab_bar.customContextMenuRequested.connect(self._show_tab_context)
        self._btn_new = QPushButton("+", self)
        self._btn_new.setToolTip("New Tab (Ctrl+T)")
        self._btn_new.setFixedSize(26, 26)
        row.addWidget(self._tab_bar)
        row.addWidget(self._btn_new)
        row.addStretch()
        outer.addLayout(row)
        self._tab_bar.tabCloseRequested.connect(self.tab_close_requested.emit)
        self._tab_bar.currentChanged.connect(self.current_changed.emit)
        self._tab_bar.tabMoved.connect(self.tab_moved.emit)
        self._btn_new.clicked.connect(self.new_tab_requested.emit)

    def count(self) -> int:
        return self._tab_bar.count()

    def current_index(self) -> int:
        return self._tab_bar.currentIndex()

    def set_current_index(self, index: int) -> None:
        if 0 <= index < self.count():
            self._tab_bar.blockSignals(True)
            self._tab_bar.setCurrentIndex(index)
            self._tab_bar.blockSignals(False)

    def insert_tab(self, index: int, title: str = "New Tab", icon: QIcon | None = None) -> int:
        text = self._format_title(title)
        actual = self._tab_bar.insertTab(index, icon, text) if icon and not icon.isNull() else self._tab_bar.insertTab(index, text)
        self._titles[str(self._tab_bar.tabData(actual) or "")] = title.strip() or "New Tab"
        self._install_close_button(actual)
        return actual

    def add_tab(self, title: str = "New Tab", icon: QIcon | None = None) -> int:
        return self.insert_tab(self.count(), title, icon)

    def remove_tab(self, index: int) -> None:
        if not 0 <= index < self.count():
            return
        self._tab_bar.removeTab(index)
        self._tab_ids = {i: self._tab_bar.tabData(i) for i in range(self.count())}

    def set_tab_id(self, index: int, tab_id: str) -> None:
        if 0 <= index < self.count():
            existing_title = self._tab_bar.tabText(index)
            self._tab_bar.setTabData(index, tab_id)
            self._tab_ids[index] = tab_id
            self._titles[tab_id] = existing_title or self._titles.get("", "New Tab")

    def tab_id(self, index: int) -> str | None:
        return self._tab_bar.tabData(index) if 0 <= index < self.count() else None

    def set_tab_title(self, index: int, title: str) -> None:
        if 0 <= index < self.count():
            tab_id = self.tab_id(index) or ""
            self._titles[tab_id] = title.strip() or "New Tab"
            pinned = self._pinned.get(self.tab_id(index) or "", False)
            self._tab_bar.setTabText(index, "" if pinned else self._format_title(title))
            self._tab_bar.setTabToolTip(index, title or "New Tab")

    def set_tab_icon(self, index: int, icon: QIcon) -> None:
        if 0 <= index < self.count():
            self._tab_bar.setTabIcon(index, icon)

    def set_tab_tooltip(self, index: int, tooltip: str) -> None:
        if 0 <= index < self.count():
            self._tab_bar.setTabToolTip(index, tooltip)

    def set_pinned(self, index: int, pinned: bool) -> None:
        if not 0 <= index < self.count():
            return
        tab_id = self.tab_id(index)
        if not tab_id:
            return
        if self._pinned.get(tab_id, False) == pinned:
            return
        self._pinned[tab_id] = pinned
        if pinned:
            self._tab_bar.setTabText(index, "")
            self._tab_bar.setTabButton(index, QTabBar.ButtonPosition.RightSide, None)
            self._tab_bar.setTabButton(index, QTabBar.ButtonPosition.LeftSide, None)
            self._tab_bar.setTabToolTip(index, "Pinned tab")
        else:
            self._tab_bar.setTabText(index, self._format_title(self._titles.get(tab_id, "New Tab")))
            self._install_close_button(index)

    def sync_order(self, tab_ids: list[str]) -> None:
        """Reorder the Qt tabs to match the tab model, without recreating pages."""
        for target, tab_id in enumerate(tab_ids):
            current = next((i for i in range(self.count()) if self.tab_id(i) == tab_id), -1)
            if current >= 0 and current != target:
                self._tab_bar.moveTab(current, target)
        self._tab_ids = {i: self._tab_bar.tabData(i) for i in range(self.count())}

    def set_tab_visible(self, index: int, visible: bool) -> None:
        if hasattr(self._tab_bar, "setTabVisible") and 0 <= index < self.count():
            self._tab_bar.setTabVisible(index, visible)

    def set_groups(self, groups: tuple[TabGroup, ...], collapsed_by_id: dict[str, bool] | None = None) -> None:
        self._groups = tuple(groups)
        while self._groups_layout.count():
            item = self._groups_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for position, group in enumerate(self._groups):
            collapsed = (collapsed_by_id or {}).get(group.id, group.collapsed)
            button = QPushButton(("▸ " if collapsed else "▾ ") + group.name[:18], self._groups_row)
            button.setToolTip(f"{group.name} tab group")
            button.setStyleSheet(f"QPushButton{{border:1px solid {group.color};border-radius:8px;padding:2px 8px;color:{group.color};font-weight:600;}}")
            button.clicked.connect(lambda _checked=False, group_id=group.id: self.group_toggle_requested.emit(group_id))
            button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            button.customContextMenuRequested.connect(lambda pos, group_id=group.id, b=button: self.group_context_requested.emit(group_id, b.mapToGlobal(pos)))
            button.installEventFilter(self)
            button.setProperty("group_id", group.id)
            button.setProperty("group_position", position)
            button.setProperty("drag_start", None)
            self._groups_layout.addWidget(button)
        self._groups_layout.addStretch()
        self._groups_row.setVisible(bool(self._groups))

    def _show_tab_context(self, pos: QPoint) -> None:
        index = self._tab_bar.tabAt(pos)
        if index >= 0:
            self.tab_context_requested.emit(index, self._tab_bar.mapToGlobal(pos))

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        group_id = watched.property("group_id") if isinstance(watched, QPushButton) else None
        if group_id and event.type() == QEvent.Type.MouseButtonPress and isinstance(event, QMouseEvent):
            watched.setProperty("drag_start", event.position().toPoint())
        elif group_id and event.type() == QEvent.Type.MouseMove and isinstance(event, QMouseEvent):
            start = watched.property("drag_start")
            if start is not None and (event.position().toPoint() - start).manhattanLength() >= QApplication.startDragDistance():
                drag = QDrag(watched)
                mime = QMimeData()
                mime.setText(group_id)
                drag.setMimeData(mime)
                drag.exec(Qt.DropAction.MoveAction)
                watched.setProperty("drag_start", None)
        return super().eventFilter(watched, event)

    def _install_close_button(self, index: int) -> None:
        if self._tab_bar.tabButton(index, QTabBar.ButtonPosition.RightSide) is not None:
            return
        button = QToolButton(self._tab_bar)
        button.setText("×")
        button.setAutoRaise(True)
        button.setFixedSize(18, 18)
        button.clicked.connect(lambda _checked=False, b=button: self._close_button_clicked(b))
        self._tab_bar.setTabButton(index, QTabBar.ButtonPosition.RightSide, button)

    def _close_button_clicked(self, button: QToolButton) -> None:
        for index in range(self.count()):
            if self._tab_bar.tabButton(index, QTabBar.ButtonPosition.RightSide) is button:
                self.tab_close_requested.emit(index)
                return

    def _format_title(self, title: str) -> str:
        cleaned = title.strip() or "New Tab"
        return cleaned if len(cleaned) <= self.MAX_TITLE_LENGTH else cleaned[: self.MAX_TITLE_LENGTH - 1] + "…"
