"""Browsing history viewer dialog for LightMq Browser."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from browser.features.history.history_manager import HistoryManager


class HistoryDialog(QDialog):
    """Dialog displaying searchable browsing history with open and clear options."""

    open_url_requested = Signal(str)

    def __init__(
        self,
        history_manager: HistoryManager | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Browsing History")
        self.resize(750, 480)
        self._manager = history_manager or HistoryManager.get_instance()
        self._init_ui()
        self._load_entries()

    def _init_ui(self) -> None:
        """Construct the dialog layout."""
        layout = QVBoxLayout(self)

        # Search bar
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("Filter history by title or URL...")
        self.search_edit.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_edit)
        layout.addLayout(search_layout)

        # Table of history items
        self.table = QTableWidget(self)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Title", "URL", "Date Visited"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)
        layout.addWidget(self.table)

        # Action Buttons
        btn_layout = QHBoxLayout()
        self.btn_clear = QPushButton("Clear All History", self)
        self.btn_clear.clicked.connect(self._on_clear_clicked)
        btn_layout.addWidget(self.btn_clear)

        btn_layout.addStretch()

        self.btn_open = QPushButton("Open Selected", self)
        self.btn_open.clicked.connect(self._on_open_clicked)
        btn_layout.addWidget(self.btn_open)

        self.btn_close = QPushButton("Close", self)
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

    def _load_entries(self, query: str = "") -> None:
        """Populate the table with history records."""
        entries = self._manager.get_entries(query)
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            title_item = QTableWidgetItem(entry["title"])
            url_item = QTableWidgetItem(entry["url"])
            time_item = QTableWidgetItem(entry["timestamp"])

            self.table.setItem(row, 0, title_item)
            self.table.setItem(row, 1, url_item)
            self.table.setItem(row, 2, time_item)

    def _on_search_changed(self, text: str) -> None:
        """Re-filter entries based on search input."""
        self._load_entries(text.strip())

    def _on_row_double_clicked(self, row: int, col: int) -> None:
        """Open item on double click."""
        url_item = self.table.item(row, 1)
        if url_item is not None:
            self.open_url_requested.emit(url_item.text())
            self.accept()

    def _on_open_clicked(self) -> None:
        """Open the currently selected item."""
        selected_rows = self.table.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            url_item = self.table.item(row, 1)
            if url_item is not None:
                self.open_url_requested.emit(url_item.text())
                self.accept()

    def _on_clear_clicked(self) -> None:
        """Clear all history entries."""
        self._manager.clear()
        self._load_entries()
