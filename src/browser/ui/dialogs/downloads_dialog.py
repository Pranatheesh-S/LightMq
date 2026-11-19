"""File downloads dialog for LightMq Browser."""

import os
from pathlib import Path
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from browser.features.downloads.download_manager import DownloadManager


class DownloadsDialog(QDialog):
    """Dialog displaying list of active and completed file downloads."""

    def __init__(
        self,
        download_manager: DownloadManager | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Downloads")
        self.resize(720, 420)
        self._manager = download_manager or DownloadManager.get_instance()
        self._init_ui()
        self._load_downloads()
        self._manager.downloads_changed.connect(self._load_downloads)

    def _init_ui(self) -> None:
        """Construct the dialog layout."""
        layout = QVBoxLayout(self)

        self.table = QTableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Filename", "Status", "Size", "Destination Path"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        self.btn_open_folder = QPushButton("Open Containing Folder", self)
        self.btn_open_folder.clicked.connect(self._on_open_folder_clicked)
        btn_layout.addWidget(self.btn_open_folder)

        self.btn_clear = QPushButton("Clear Completed", self)
        self.btn_clear.clicked.connect(self._manager.clear)
        btn_layout.addWidget(self.btn_clear)

        btn_layout.addStretch()

        self.btn_close = QPushButton("Close", self)
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

    def _load_downloads(self) -> None:
        """Populate the table with download items."""
        downloads = self._manager.get_downloads()
        self.table.setRowCount(len(downloads))
        for row, item in enumerate(downloads):
            file_item = QTableWidgetItem(item.filename)
            status_item = QTableWidgetItem(item.state_str)

            size_str = f"{item.received_bytes // 1024} KB"
            if item.total_bytes > 0:
                size_str += f" / {item.total_bytes // 1024} KB"
            size_item = QTableWidgetItem(size_str)

            path_item = QTableWidgetItem(item.download_path)

            self.table.setItem(row, 0, file_item)
            self.table.setItem(row, 1, status_item)
            self.table.setItem(row, 2, size_item)
            self.table.setItem(row, 3, path_item)

    def _on_open_folder_clicked(self) -> None:
        """Open the folder containing the selected downloaded file."""
        selected_rows = self.table.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            downloads = self._manager.get_downloads()
            if 0 <= row < len(downloads):
                item = downloads[row]
                folder = Path(item.download_path).parent
                if folder.exists():
                    QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
                else:
                    user_downloads = Path.home() / "Downloads"
                    if user_downloads.exists():
                        QDesktopServices.openUrl(QUrl.fromLocalFile(str(user_downloads)))
