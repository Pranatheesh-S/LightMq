"""Download manager subsystem for LightMq Browser.

Tracks file download requests, transfer progress, and completion states.
"""

import logging
from pathlib import Path
from PySide6.QtCore import QObject, Signal
from PySide6.QtWebEngineCore import QWebEngineDownloadRequest

logger = logging.getLogger(__name__)


class DownloadItem:
    """Represents a single tracked download."""

    def __init__(self, request: QWebEngineDownloadRequest):
        self.id = request.id()
        self.filename = request.suggestedFileName()
        self.url = request.url().toString()
        self.download_path = str(Path(request.downloadDirectory()) / (request.downloadFileName() or request.suggestedFileName()))
        self.received_bytes = request.receivedBytes()
        self.total_bytes = request.totalBytes()
        self.state_str = "Downloading"
        self._request = request

    def update_from_request(self) -> None:
        """Refresh dynamic properties from the underlying request."""
        self.received_bytes = self._request.receivedBytes()
        self.total_bytes = self._request.totalBytes()
        state = self._request.state()
        if state == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            self.state_str = "Completed"
        elif state == QWebEngineDownloadRequest.DownloadState.DownloadCancelled:
            self.state_str = "Cancelled"
        elif state == QWebEngineDownloadRequest.DownloadState.DownloadInterrupted:
            self.state_str = f"Interrupted: {self._request.interruptReasonString()}"
        else:
            self.state_str = "Downloading"


class DownloadManager(QObject):
    """Manages tracking, notification, and history of browser file downloads."""

    downloads_changed = Signal()
    download_started = Signal(str)
    download_finished = Signal(str, bool)

    _instance: "DownloadManager | None" = None

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._downloads: list[DownloadItem] = []

    @classmethod
    def get_instance(cls) -> "DownloadManager":
        """Return shared singleton instance of DownloadManager."""
        if cls._instance is None:
            cls._instance = DownloadManager()
        return cls._instance

    def handle_download(self, request: QWebEngineDownloadRequest) -> None:
        """Register and monitor a new incoming download request."""
        # Set default download directory to user Downloads if not configured
        if not request.downloadDirectory():
            default_dir = str(Path.home() / "Downloads")
            request.setDownloadDirectory(default_dir)

        item = DownloadItem(request)
        self._downloads.insert(0, item)
        self.download_started.emit(item.filename)
        self.downloads_changed.emit()

        request.receivedBytesChanged.connect(lambda: self._on_progress(item))
        request.stateChanged.connect(lambda state: self._on_state_changed(item, state))

        # Accept download
        request.accept()
        logger.info("Accepted download for: %s -> %s", item.filename, item.download_path)

    def _on_progress(self, item: DownloadItem) -> None:
        """Handle byte transfer updates."""
        item.update_from_request()
        self.downloads_changed.emit()

    def _on_state_changed(
        self,
        item: DownloadItem,
        state: QWebEngineDownloadRequest.DownloadState,
    ) -> None:
        """Handle download completion, interruption, or cancellation."""
        item.update_from_request()
        is_success = (state == QWebEngineDownloadRequest.DownloadState.DownloadCompleted)
        self.download_finished.emit(item.filename, is_success)
        self.downloads_changed.emit()
        logger.info("Download state changed for %s: %s", item.filename, item.state_str)

    def get_downloads(self) -> list[DownloadItem]:
        """Return all tracked downloads."""
        return list(self._downloads)

    def clear(self) -> None:
        """Clear completed downloads from list."""
        self._downloads = [d for d in self._downloads if d.state_str == "Downloading"]
        self.downloads_changed.emit()
