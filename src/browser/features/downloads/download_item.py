"""Live model for one Qt WebEngine download request."""

from time import monotonic
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtWebEngineCore import QWebEngineDownloadRequest

from browser.features.downloads.download_utils import format_duration, format_size


class DownloadItem(QObject):
    """Track the independent state and metrics of one download request."""

    changed = Signal()

    def __init__(self, request: QWebEngineDownloadRequest, parent: QObject | None = None):
        super().__init__(parent)
        self.request = request
        self.id = request.id()
        self.filename = request.downloadFileName() or request.suggestedFileName() or "download"
        self.url = request.url().toString()
        self.mime_type = request.mimeType()
        self.destination = str(Path(request.downloadDirectory()) / self.filename)
        self.received_bytes = request.receivedBytes()
        self.total_bytes = request.totalBytes()
        self.speed_bytes_per_second = 0.0
        self._last_sample_time = monotonic()
        self._last_sample_bytes = self.received_bytes
        self._state = request.state()
        self._speed_initialized = False
        self.terminal_notification_sent = False

        request.receivedBytesChanged.connect(self._on_progress)
        request.totalBytesChanged.connect(self._on_total_changed)
        request.stateChanged.connect(self._on_state_changed)
        request.isPausedChanged.connect(self._on_pause_changed)
        request.interruptReasonChanged.connect(self._on_interrupt_changed)
        request.destroyed.connect(self._on_request_destroyed)

    @property
    def is_active(self) -> bool:
        """Whether Qt still considers the transfer active or paused."""
        return self._state in (
            QWebEngineDownloadRequest.DownloadState.DownloadRequested,
            QWebEngineDownloadRequest.DownloadState.DownloadInProgress,
        )

    @property
    def is_paused(self) -> bool:
        """Whether the request is currently paused."""
        try:
            return self.is_active and self.request.isPaused()
        except RuntimeError:
            return False

    @property
    def status(self) -> str:
        """Readable transfer status, including Qt's interruption reason."""
        if self._state == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            return "Completed"
        if self._state == QWebEngineDownloadRequest.DownloadState.DownloadCancelled:
            return "Cancelled"
        if self._state == QWebEngineDownloadRequest.DownloadState.DownloadInterrupted:
            try:
                reason = self.request.interruptReasonString()
            except RuntimeError:
                reason = ""
            return f"Failed: {reason}" if reason else "Failed or interrupted"
        if self.is_paused:
            return "Paused"
        if self._state == QWebEngineDownloadRequest.DownloadState.DownloadRequested:
            return "Pending"
        return "Downloading"

    @property
    def progress(self) -> int | None:
        """Transfer percentage, or None while the total size is unknown."""
        if self.total_bytes <= 0:
            return None
        return min(100, int(self.received_bytes * 100 / self.total_bytes))

    @property
    def progress_text(self) -> str:
        """Human-readable transferred and total byte counts."""
        total = format_size(self.total_bytes) if self.total_bytes > 0 else "Unknown size"
        return f"{format_size(self.received_bytes)} / {total}"

    @property
    def eta_text(self) -> str:
        """Estimated remaining time when transfer size and speed are known."""
        if not self.is_active or self.is_paused or self.total_bytes <= 0:
            return ""
        if self.speed_bytes_per_second <= 0:
            return ""
        remaining = max(0, self.total_bytes - self.received_bytes)
        return format_duration(remaining / self.speed_bytes_per_second)

    @property
    def speed_text(self) -> str:
        """Human-readable transfer rate."""
        if not self.speed_bytes_per_second:
            return ""
        return f"{format_size(int(self.speed_bytes_per_second))}/s"

    def pause(self) -> None:
        """Pause an active transfer."""
        if self.is_active and not self.is_paused:
            self.request.pause()

    def resume(self) -> None:
        """Resume a paused transfer when Qt reports it is resumable."""
        if self.is_active and self.is_paused:
            self.request.resume()

    def cancel(self) -> None:
        """Cancel an active transfer."""
        if self.is_active:
            self.request.cancel()

    def _sample_speed(self) -> None:
        now = monotonic()
        elapsed = now - self._last_sample_time
        delta = self.received_bytes - self._last_sample_bytes
        if elapsed > 0 and delta >= 0:
            instantaneous = delta / elapsed
            if not self._speed_initialized:
                self.speed_bytes_per_second = instantaneous
                self._speed_initialized = True
            else:
                self.speed_bytes_per_second = (
                    0.3 * instantaneous + 0.7 * self.speed_bytes_per_second
                )
        self._last_sample_time = now
        self._last_sample_bytes = self.received_bytes

    def _on_progress(self) -> None:
        self.received_bytes = self.request.receivedBytes()
        self._sample_speed()
        self.changed.emit()

    def _on_total_changed(self) -> None:
        self.total_bytes = self.request.totalBytes()
        self.changed.emit()

    def _on_state_changed(self, state: QWebEngineDownloadRequest.DownloadState) -> None:
        self._state = state
        self.changed.emit()

    def _on_pause_changed(self) -> None:
        self.changed.emit()

    def _on_interrupt_changed(self) -> None:
        self.changed.emit()

    def _on_request_destroyed(self) -> None:
        if self.is_active:
            self._state = QWebEngineDownloadRequest.DownloadState.DownloadInterrupted
            self.changed.emit()
