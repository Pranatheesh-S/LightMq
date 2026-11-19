"""Custom WebEngineView component for web content rendering.

Subclasses QWebEngineView and integrates with WebPage to provide page navigation,
progress reporting, and lifecycle notifications.
"""

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QWidget
from PySide6.QtWebEngineCore import QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView

from browser.webengine.web_page import WebPage


class WebView(QWebEngineView):
    """Customized WebEngineView hosting the Chromium web viewport."""

    def __init__(self, profile: QWebEngineProfile | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self._custom_page = WebPage(profile=profile, parent=self)
        self.setPage(self._custom_page)

    def navigate(self, url: QUrl) -> None:
        """Navigate to a target QUrl.

        Args:
            url: Validated destination QUrl.
        """
        if url.isValid() and not url.isEmpty():
            self.setUrl(url)
