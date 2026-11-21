"""Session-only coordinator for Qt WebEngine download requests."""

import logging
from PySide6.QtCore import QObject, Signal
from PySide6.QtWebEngineCore import QWebEngineDownloadRequest

from browser.features.downloads.download_item import DownloadItem

logger = logging.getLogger(__name__)


class DownloadManager(QObject):
    """Retain and coordinate simultaneous downloads independently of browser tabs."""

    downloads_changed = Signal()
    item_added = Signal(object)
    notification = Signal(str, int)
    active_count_changed = Signal(int)

    _instance: "DownloadManager | None" = None

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._downloads: list[DownloadItem] = []
        self._handlers: dict[tuple[int, int], QObject] = {}

    @classmethod
    def get_instance(cls) -> "DownloadManager":
        """Return the shared manager used by regular browser windows."""
        if cls._instance is None:
            cls._instance = DownloadManager()
        return cls._instance

    def handler_for(self, key: tuple[int, int]) -> QObject | None:
        """Return a retained profile handler, if one was already connected."""
        return self._handlers.get(key)

    def retain_handler(self, key: tuple[int, int], handler: QObject) -> None:
        """Keep the profile signal receiver alive for its entire connection."""
        self._handlers[key] = handler

    def add_request(self, request: QWebEngineDownloadRequest, destination: str) -> DownloadItem:
        """Track a configured request before it is accepted by Qt WebEngine."""
        item = DownloadItem(request, parent=self)
        item.destination = destination
        item.changed.connect(lambda tracked=item: self._on_item_changed(tracked))
        self._downloads.insert(0, item)
        self.item_added.emit(item)
        self.downloads_changed.emit()
        return item

    def mark_accepted(self, request_id: int) -> None:
        """Announce a request after its destination is configured and accepted."""
        item = self.get_by_id(request_id)
        if item is not None:
            self.notify(f"Download started: {item.filename}", 3000)
            self._emit_state()

    def get_by_id(self, request_id: int) -> DownloadItem | None:
        """Find a retained request by Qt's request identifier."""
        return next((item for item in self._downloads if item.id == request_id), None)

    def get_downloads(self) -> list[DownloadItem]:
        """Return a snapshot of session download records, newest first."""
        return list(self._downloads)

    def remove(self, item: DownloadItem) -> None:
        """Remove a finished entry without deleting its downloaded file."""
        if item.is_active or item not in self._downloads:
            return
        self._downloads.remove(item)
        item.deleteLater()
        self._emit_state()

    def clear(self) -> None:
        """Remove all finished entries while retaining active transfers."""
        retained: list[DownloadItem] = []
        for item in self._downloads:
            if item.is_active:
                retained.append(item)
            else:
                item.deleteLater()
        self._downloads = retained
        self._emit_state()

    def notify(self, message: str, timeout_ms: int = 3000) -> None:
        """Emit a short, nonintrusive UI notification."""
        self.notification.emit(message, timeout_ms)

    def _on_item_changed(self, item: DownloadItem) -> None:
        if not item.is_active and not item.terminal_notification_sent:
            item.terminal_notification_sent = True
            if item.status == "Completed":
                self.notify(f"Download completed: {item.filename}", 4000)
            elif item.status == "Cancelled":
                self.notify(f"Download cancelled: {item.filename}", 3000)
            elif item.status.startswith("Failed"):
                self.notify(f"{item.status}: {item.filename}", 6000)
                logger.warning("Download %s ended: %s", item.filename, item.status)
        self._emit_state()

    def _emit_state(self) -> None:
        self.downloads_changed.emit()
        self.active_count_changed.emit(sum(item.is_active for item in self._downloads))
