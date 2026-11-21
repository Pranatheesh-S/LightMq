"""Native Qt interface for active and completed browser downloads."""

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QKeyEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from browser.features.downloads.download_item import DownloadItem
from browser.features.downloads.download_manager import DownloadManager


class DownloadRow(QWidget):
    """Display one download and the actions currently available for it."""

    def __init__(self, item: DownloadItem, manager: DownloadManager, parent: QWidget | None = None):
        super().__init__(parent)
        self.item = item
        self.manager = manager
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)

        self.filename_label = QLabel(self)
        self.filename_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.filename_label)
        self.detail_label = QLabel(self)
        self.detail_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.detail_label)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        self.button_layout = QHBoxLayout()
        self.pause_button = QPushButton(self)
        self.pause_button.clicked.connect(self._toggle_pause)
        self.button_layout.addWidget(self.pause_button)
        self.cancel_button = QPushButton("Cancel", self)
        self.cancel_button.clicked.connect(item.cancel)
        self.button_layout.addWidget(self.cancel_button)
        self.open_button = QPushButton("Open", self)
        self.open_button.clicked.connect(self._open_file)
        self.button_layout.addWidget(self.open_button)
        self.folder_button = QPushButton("Show in Folder", self)
        self.folder_button.clicked.connect(self._show_folder)
        self.button_layout.addWidget(self.folder_button)
        self.remove_button = QPushButton("Remove", self)
        self.remove_button.clicked.connect(lambda: manager.remove(item))
        self.button_layout.addWidget(self.remove_button)
        self.button_layout.addStretch()
        layout.addLayout(self.button_layout)
        self.item.changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        """Refresh metrics and enable only actions supported by current state."""
        item = self.item
        source = QUrl(item.url).host() or item.url
        file_type = item.mime_type or (Path(item.filename).suffix.lstrip(".").upper() or "File")
        self.filename_label.setText(item.filename)
        self.detail_label.setText(
            f"{item.status} · {item.progress_text} · {file_type} · {source}\n{item.destination}"
            + (f" · {item.speed_text}" if item.speed_text else "")
            + (f" · {item.eta_text}" if item.eta_text else "")
        )

        progress = item.progress
        if item.is_active and progress is None:
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setFormat("Downloading…")
        else:
            self.progress_bar.setRange(0, 100)
            terminal_value = 100 if item.status == "Completed" else 0
            self.progress_bar.setValue(progress if progress is not None else terminal_value)
            self.progress_bar.setFormat(f"{progress}%" if progress is not None else item.status)

        active = item.is_active
        self.pause_button.setText("Resume" if item.is_paused else "Pause")
        self.pause_button.setEnabled(active)
        self.cancel_button.setEnabled(active)
        completed = item.status == "Completed" and Path(item.destination).is_file()
        self.open_button.setEnabled(completed)
        self.folder_button.setEnabled(Path(item.destination).parent.is_dir())
        self.remove_button.setEnabled(not active)

    def _toggle_pause(self) -> None:
        if self.item.is_paused:
            self.item.resume()
        else:
            self.item.pause()

    def _open_file(self) -> None:
        if self.item.status == "Completed" and Path(self.item.destination).is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.item.destination))

    def _show_folder(self) -> None:
        folder = Path(self.item.destination).parent
        if folder.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))


class DownloadsDialog(QDialog):
    """Session download list with progress and transfer controls."""

    def __init__(
        self,
        download_manager: DownloadManager | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Downloads")
        self.resize(820, 540)
        self._manager = download_manager or DownloadManager.get_instance()
        self._rows: dict[int, DownloadRow] = {}
        self._escape_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self._escape_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._escape_shortcut.activated.connect(self.close)
        self._init_ui()
        self._manager.downloads_changed.connect(self._sync_rows)
        self._sync_rows()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.content = QWidget(self.scroll_area)
        self.rows_layout = QVBoxLayout(self.content)
        self.rows_layout.setContentsMargins(4, 4, 4, 4)
        self.rows_layout.addStretch()
        self.scroll_area.setWidget(self.content)
        layout.addWidget(self.scroll_area)

        buttons = QHBoxLayout()
        self.clear_button = QPushButton("Clear Finished", self)
        self.clear_button.clicked.connect(self._manager.clear)
        buttons.addWidget(self.clear_button)
        buttons.addStretch()
        close_button = QPushButton("Close", self)
        close_button.clicked.connect(self.accept)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

    def _sync_rows(self) -> None:
        """Create rows for new records and remove rows no longer tracked."""
        items = self._manager.get_downloads()
        current_ids = {item.id for item in items}
        for request_id in set(self._rows) - current_ids:
            row = self._rows.pop(request_id)
            self.rows_layout.removeWidget(row)
            row.deleteLater()
        for item in items:
            if item.id not in self._rows:
                row = DownloadRow(item, self._manager, self.content)
                self._rows[item.id] = row
                self.rows_layout.insertWidget(0, row)
        self.clear_button.setEnabled(any(not item.is_active for item in items))

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Close the manager on Escape without affecting browser loading."""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            event.accept()
            return
        super().keyPressEvent(event)
