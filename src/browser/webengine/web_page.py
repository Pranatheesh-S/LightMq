"""Custom WebEnginePage managing page lifecycle, security, and window requests.

Encapsulates Chromium page configuration, certificate verification, and JavaScript
interaction policies.
"""

from collections.abc import Callable
import logging
from PySide6.QtCore import QObject
from PySide6.QtWebEngineCore import QWebEngineCertificateError, QWebEnginePage

logger = logging.getLogger(__name__)


class WebPage(QWebEnginePage):
    """Customized QWebEnginePage for LightMq browser."""

    def __init__(self, profile=None, parent: QObject | None = None):
        if profile is not None:
            super().__init__(profile, parent)
        else:
            super().__init__(parent)
        self._window_factory: Callable[[], "WebPage"] | None = None

    def set_window_factory(self, factory: Callable[[], "WebPage"] | None) -> None:
        """Register a callback factory to handle new window/tab requests from web content.

        Args:
            factory: Callable that creates and returns a new WebPage instance.
        """
        self._window_factory = factory

    def certificateError(self, certificate_error: QWebEngineCertificateError) -> bool:
        """Handle SSL/TLS certificate errors.

        Strict security: Reject invalid, expired, or self-signed certificates by default.
        Never bypass SSL verification silently.

        Args:
            certificate_error: Certificate error metadata.

        Returns:
            bool: False to reject navigation and protect the user.
        """
        logger.warning(
            "SSL Certificate Error on %s: %s (error code: %s)",
            certificate_error.url().toString(),
            certificate_error.description(),
            certificate_error.type(),
        )
        return False

    def createWindow(self, window_type: QWebEnginePage.WebWindowType) -> QWebEnginePage | None:
        """Handle requests from web content to open a new window or tab.

        When a window factory is registered, creates and delegates to a new tab.

        Args:
            window_type: Type of requested window.

        Returns:
            QWebEnginePage: Target page for the navigation.
        """
        if self._window_factory is not None:
            try:
                new_page = self._window_factory()
                if new_page is not None:
                    return new_page
            except Exception as e:
                logger.error("Failed to execute window factory for new tab: %s", e)

        return self
