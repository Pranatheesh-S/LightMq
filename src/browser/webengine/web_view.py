"""Custom WebEngineView component for web content rendering.

Subclasses QWebEngineView and integrates with WebPage to provide page navigation,
progress reporting, and lifecycle notifications.
"""

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QWidget
from PySide6.QtWebEngineCore import QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView

from browser.utils.constants import DEFAULT_START_URL
from browser.webengine.web_page import WebPage
from browser.webengine.new_tab_content import PRIVATE_START_URL, new_tab_html, private_start_html


class WebView(QWebEngineView):
    """Customized WebEngineView hosting the Chromium web viewport."""

    def __init__(self, profile: QWebEngineProfile | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self._showing_new_tab = False
        self._internal_url = DEFAULT_START_URL
        self._custom_page = WebPage(profile=profile, parent=self)
        self.setPage(self._custom_page)
        self._custom_page.main_frame_navigation_requested.connect(self._on_main_frame_navigation)

    def url(self) -> QUrl:
        """Return the internal new-tab address while its HTML is being installed."""
        if self._showing_new_tab:
            return QUrl(self._internal_url)
        return super().url()

    def _on_main_frame_navigation(self, target: str, _visit_type: str) -> None:
        """Leave new-tab mode as soon as the user navigates to another page."""
        if target not in (DEFAULT_START_URL,PRIVATE_START_URL):
            self._showing_new_tab = False

    def setUrl(self, url: QUrl) -> None:
        """Load either the built-in start page or the requested external URL."""
        if url.toString() in (DEFAULT_START_URL,PRIVATE_START_URL):
            self._showing_new_tab = True
            self._internal_url=url.toString()
            html=private_start_html() if self._internal_url==PRIVATE_START_URL else new_tab_html()
            super().setHtml(html,QUrl(self._internal_url))
            return
        self._showing_new_tab = False
        super().setUrl(url)

    def navigate(self, url: QUrl) -> None:
        """Navigate to a target QUrl.

        Args:
            url: Validated destination QUrl.
        """
        if url.isValid() and not url.isEmpty():
            self.setUrl(url)
