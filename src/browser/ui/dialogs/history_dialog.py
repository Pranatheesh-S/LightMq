"""Searchable, paginated browser history dialog."""

from datetime import datetime, time, timedelta, timezone

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QHBoxLayout, QHeaderView, QLabel, QInputDialog,
    QDateEdit, QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from browser.features.history.history_manager import HistoryManager


class HistoryDialog(QDialog):
    """Show visit records with search, date filters, deletion, and open actions."""

    open_url_requested = Signal(str)
    open_in_new_tab_requested = Signal(str)
    PAGE_SIZE = 100

    def __init__(self, history_manager: HistoryManager | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Browsing History")
        self.resize(900, 560)
        self._manager = history_manager or HistoryManager.get_instance()
        self._page = 0
        self._init_ui()
        self._manager.history_changed.connect(self._load_entries)
        self._load_entries()

    def _init_ui(self) -> None:
        """Build history controls and visit table."""
        layout = QVBoxLayout(self)
        filters = QHBoxLayout()
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("Search titles and URLs")
        self.search_edit.textChanged.connect(self._on_filter_changed)
        self.period = QComboBox(self)
        for label, value in (("All time", "all"), ("Today", "today"), ("Yesterday", "yesterday"),
                             ("Last 7 days", "7"), ("Last 30 days", "30"), ("Custom dates", "custom")):
            self.period.addItem(label, value)
        self.period.currentIndexChanged.connect(self._on_filter_changed)
        filters.addWidget(self.search_edit, 1)
        filters.addWidget(self.period)
        self.start_date = QDateEdit(QDate.currentDate(), self)
        self.start_date.setCalendarPopup(True)
        self.end_date = QDateEdit(QDate.currentDate(), self)
        self.end_date.setCalendarPopup(True)
        self.start_date.dateChanged.connect(self._on_filter_changed)
        self.end_date.dateChanged.connect(self._on_filter_changed)
        filters.addWidget(self.start_date)
        filters.addWidget(self.end_date)
        layout.addLayout(filters)

        self.table = QTableWidget(self)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Title", "URL", "Date visited"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.cellDoubleClicked.connect(lambda _row, _col: self._open_selected())
        layout.addWidget(self.table)
        self.empty_label = QLabel("No browsing history matches this search.", self)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty_label)

        footer = QHBoxLayout()
        self.delete_button = QPushButton("Delete visit", self)
        self.delete_button.clicked.connect(self._delete_selected)
        footer.addWidget(self.delete_button)
        self.delete_site_button = QPushButton("Delete site history", self)
        self.delete_site_button.clicked.connect(self._delete_site)
        footer.addWidget(self.delete_site_button)
        self.clear_button = QPushButton("Clear all history…", self)
        self.clear_button.clicked.connect(self._clear_all)
        footer.addWidget(self.clear_button)
        self.clear_range_button = QPushButton("Clear time range…", self)
        self.clear_range_button.clicked.connect(self._clear_range)
        footer.addWidget(self.clear_range_button)
        self.copy_button = QPushButton("Copy URL", self)
        self.copy_button.clicked.connect(self._copy_url)
        footer.addWidget(self.copy_button)
        footer.addStretch()
        self.previous_button = QPushButton("Previous", self)
        self.previous_button.clicked.connect(self._previous_page)
        footer.addWidget(self.previous_button)
        self.page_label = QLabel(self)
        footer.addWidget(self.page_label)
        self.next_button = QPushButton("Next", self)
        self.next_button.clicked.connect(self._next_page)
        footer.addWidget(self.next_button)
        self.open_button = QPushButton("Open", self)
        self.open_button.clicked.connect(self._open_selected)
        footer.addWidget(self.open_button)
        self.new_tab_button = QPushButton("Open in new tab", self)
        self.new_tab_button.clicked.connect(lambda: self._open_selected(new_tab=True))
        footer.addWidget(self.new_tab_button)
        close_button = QPushButton("Close", self)
        close_button.clicked.connect(self.accept)
        footer.addWidget(close_button)
        layout.addLayout(footer)

    def _bounds(self) -> tuple[datetime | None, datetime | None]:
        """Convert the selected local-calendar period into UTC query bounds."""
        now = datetime.now().astimezone()
        today = datetime.combine(now.date(), time.min)
        value = self.period.currentData()
        if value == "today":
            start, end = today, today + timedelta(days=1)
        elif value == "yesterday":
            start, end = today - timedelta(days=1), today
        elif value == "7":
            start, end = now - timedelta(days=7), None
        elif value == "30":
            start, end = now - timedelta(days=30), None
        elif value == "custom":
            start = datetime.combine(self.start_date.date().toPython(), time.min)
            end = datetime.combine(self.end_date.date().toPython() + timedelta(days=1), time.min)
        else:
            return None, None
        return start.astimezone().astimezone(timezone.utc), end.astimezone().astimezone(timezone.utc) if end else None

    def _load_entries(self, *_args: object) -> None:
        """Refresh the current page and pagination status."""
        start, end = self._bounds()
        query = self.search_edit.text() if hasattr(self, "search_edit") else ""
        count = self._manager.count_entries(query, start, end)
        pages = max(1, (count + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        self._page = min(self._page, pages - 1)
        entries = self._manager.get_entries(query, self.PAGE_SIZE, self._page * self.PAGE_SIZE, start, end)
        self.table.setRowCount(len(entries))
        self.empty_label.setVisible(not entries)
        self.table.setVisible(bool(entries))
        for row, entry in enumerate(entries):
            title_item = QTableWidgetItem(str(entry["title"]))
            url_item = QTableWidgetItem(str(entry["url"]))
            url_item.setData(Qt.ItemDataRole.UserRole, int(entry["id"]))
            try:
                local_time = datetime.fromisoformat(str(entry["timestamp"])).astimezone().strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                local_time = str(entry["timestamp"])
            self.table.setItem(row, 0, title_item)
            self.table.setItem(row, 1, url_item)
            self.table.setItem(row, 2, QTableWidgetItem(local_time))
        self.page_label.setText(f"{self._page + 1} / {pages} ({count} visits)")
        self.previous_button.setEnabled(self._page > 0)
        self.next_button.setEnabled(self._page + 1 < pages)

    def _on_filter_changed(self, *_args: object) -> None:
        self._page = 0
        self._load_entries()

    def _selected_items(self) -> tuple[int, str] | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        row = rows[0].row()
        url_item = self.table.item(row, 1)
        if url_item is None:
            return None
        return int(url_item.data(Qt.ItemDataRole.UserRole)), url_item.text()

    def _open_selected(self, new_tab: bool = False) -> None:
        selected = self._selected_items()
        if not selected:
            return
        (self.open_in_new_tab_requested if new_tab else self.open_url_requested).emit(selected[1])
        self.accept()

    def _delete_selected(self) -> None:
        selected = self._selected_items()
        if selected:
            self._manager.delete_entry(selected[0])

    def _delete_site(self) -> None:
        """Remove all visits for the selected URL after confirmation."""
        selected = self._selected_items()
        if not selected:
            return
        answer = QMessageBox.question(
            self, "Delete website history", f"Delete all visits to {selected[1]}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._manager.delete_url(selected[1])

    def _copy_url(self) -> None:
        selected = self._selected_items()
        if selected:
            QApplication.clipboard().setText(selected[1])

    def _clear_all(self) -> None:
        answer = QMessageBox.question(
            self, "Clear browsing history", "Delete all saved browsing history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._manager.clear()

    def _clear_range(self) -> None:
        """Clear one standard time range with a confirmation prompt."""
        choices = ("Last hour", "Last 24 hours", "Last 7 days", "Last 30 days", "All time")
        selected, accepted = QInputDialog.getItem(self, "Clear browsing history", "Time range:", list(choices), 0, False)
        if not accepted:
            return
        answer = QMessageBox.question(
            self, "Confirm deletion", f"Delete browsing history for {selected.lower()}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        now = datetime.now().astimezone()
        durations = {"Last hour": timedelta(hours=1), "Last 24 hours": timedelta(hours=24),
                     "Last 7 days": timedelta(days=7), "Last 30 days": timedelta(days=30)}
        if selected == "All time":
            self._manager.clear()
        else:
            self._manager.clear(start=(now - durations[selected]).astimezone(timezone.utc))

    def _previous_page(self) -> None:
        self._page = max(0, self._page - 1)
        self._load_entries()

    def _next_page(self) -> None:
        self._page += 1
        self._load_entries()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Support browser-history Enter/Delete shortcuts while the table is focused."""
        if self.table.hasFocus() and event.key() == Qt.Key.Key_Delete:
            self._delete_selected()
            return
        if self.table.hasFocus() and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._open_selected()
            return
        super().keyPressEvent(event)
