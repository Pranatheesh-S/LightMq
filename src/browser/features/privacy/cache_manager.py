"""HTTP cache clearing through the supported WebEngine profile API."""

import logging

from PySide6.QtCore import QObject, Signal
from PySide6.QtWebEngineCore import QWebEngineProfile

logger = logging.getLogger(__name__)


class CacheManager(QObject):
    """Request profile cache clearing and report Qt's completion signal."""

    clear_started = Signal()
    clear_completed = Signal()
    clear_failed = Signal(str)

    def __init__(self, profile: QWebEngineProfile, parent: QObject | None = None):
        super().__init__(parent)
        self._profile = profile
        self._clearing = False
        signal = getattr(profile, "clearHttpCacheCompleted", None)
        if signal is not None:
            signal.connect(self._on_clear_completed)

    @property
    def supports_completion_signal(self) -> bool:
        """Return whether this Qt binding exposes the HTTP-cache completion signal."""
        return getattr(self._profile, "clearHttpCacheCompleted", None) is not None

    def clear(self) -> bool:
        """Request clearing the HTTP cache; return False if a request is already active."""
        if self._clearing:
            return False
        self._clearing = True
        self.clear_started.emit()
        try:
            self._profile.clearHttpCache()
        except RuntimeError:
            self._clearing = False
            logger.exception("WebEngine rejected an HTTP cache clear request")
            self.clear_failed.emit("WebEngine could not start HTTP cache clearing.")
            return False
        if not self.supports_completion_signal:
            self._clearing = False
            self.clear_failed.emit("This Qt version does not report when cache clearing finishes.")
        return True

    def _on_clear_completed(self) -> None:
        """Forward successful cache-clear completion for our own outstanding request."""
        if self._clearing:
            self._clearing = False
            self.clear_completed.emit()
