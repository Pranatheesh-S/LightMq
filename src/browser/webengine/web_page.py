"""Custom WebEnginePage managing page lifecycle, security, and window requests.

Encapsulates Chromium page configuration, certificate verification, and JavaScript
interaction policies.
"""

from collections.abc import Callable
from email.message import Message
import logging
import weakref
from pathlib import Path
from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtWebEngineCore import (
    QWebEngineCertificateError,
    QWebEngineLoadingInfo,
    QWebEnginePage,
)

logger = logging.getLogger(__name__)


class WebPage(QWebEnginePage):
    """Customized QWebEnginePage for LightMq browser."""

    main_frame_navigation_requested = Signal(str, str)
    console_message = Signal(str, str, int, str)
    pdf_document_changed = Signal(bool)

    def __init__(self, profile=None, parent: QObject | None = None):
        if profile is not None:
            super().__init__(profile, parent)
        else:
            super().__init__(parent)
        self._window_factory: Callable[[], "WebPage"] | None = None
        self._download_view_ref: weakref.ReferenceType[QObject] | None = None
        self._download_manager_ref: weakref.ReferenceType[QObject] | None = None
        self._download_opener_ref: weakref.ReferenceType[QObject] | None = None
        self._opened_for_popup = False
        self._close_popup_after_download = False
        self._download_handled = False
        self._last_main_frame_navigation_url = QUrl()
        self._is_pdf_document = False
        self._pdf_display_title = ""
        self.loadingChanged.connect(self._on_loading_changed)

    def is_pdf_document(self) -> bool:
        """Return whether the current main-frame document is a PDF viewer page."""
        return self._is_pdf_document

    def pdf_display_title(self) -> str:
        """Return a safe PDF filename for the browser tab, when known."""
        return self._pdf_display_title

    def _set_pdf_document(self, is_pdf: bool) -> None:
        if self._is_pdf_document == is_pdf:
            return
        self._is_pdf_document = is_pdf
        self.pdf_document_changed.emit(is_pdf)

    def _on_loading_changed(self, info: QWebEngineLoadingInfo) -> None:
        """Identify PDF responses by MIME type, including URLs without extensions."""
        status = getattr(info.status(), "name", "")
        if status == "LoadStartedStatus":
            self._pdf_display_title = ""
            self._set_pdf_document(False)
            return
        if status != "LoadSucceededStatus" or (hasattr(info, "isDownload") and info.isDownload()):
            self._set_pdf_document(False)
            return

        headers: dict[str, str] = {}
        try:
            for key, values in info.responseHeaders().items():
                if values:
                    headers[key.toStdString().lower()] = values[0].toStdString()
        except (AttributeError, RuntimeError, TypeError):
            headers = {}

        url = info.url()
        is_local_pdf = url.isLocalFile() and url.path().lower().endswith(".pdf")
        content_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
        is_pdf = content_type == "application/pdf" or is_local_pdf
        self._pdf_display_title = ""
        if is_pdf:
            disposition = Message()
            raw_disposition = headers.get("content-disposition", "")
            if raw_disposition:
                disposition["Content-Disposition"] = raw_disposition
            raw_name = disposition.get_filename() or url.fileName()
            if raw_name:
                self._pdf_display_title = Path(raw_name.replace("\\", "/")).name[:200]
        self._set_pdf_document(is_pdf)

    def acceptNavigationRequest(
        self,
        url: QUrl,
        navigation_type: QWebEnginePage.NavigationType,
        is_main_frame: bool,
    ) -> bool:
        """Remember top-level navigation targets before downloads replace the page."""
        if is_main_frame:
            accepted = super().acceptNavigationRequest(url, navigation_type, is_main_frame)
            if accepted:
                self._last_main_frame_navigation_url = QUrl(url)
                visit_type = getattr(navigation_type, "name", "unknown")
                visit_type = visit_type.removeprefix("NavigationType").lower()
                self.main_frame_navigation_requested.emit(url.toString(), visit_type)
            return accepted
        return super().acceptNavigationRequest(url, navigation_type, is_main_frame)

    def last_main_frame_navigation_url(self) -> QUrl:
        """Return the most recent accepted main-frame URL, if any."""
        return QUrl(self._last_main_frame_navigation_url)

    def set_download_context(
        self,
        view: QObject,
        tab_manager: QObject,
        opened_for_popup: bool,
        opener_view: QObject | None = None,
    ) -> None:
        """Keep weak references needed to clean up popup tabs that only download."""
        self._download_view_ref = weakref.ref(view)
        self._download_manager_ref = weakref.ref(tab_manager)
        self._download_opener_ref = weakref.ref(opener_view) if opener_view is not None else None
        self._opened_for_popup = opened_for_popup

    def download_context(
        self,
    ) -> tuple[QObject | None, QObject | None, bool, QObject | None]:
        """Return the originating tab and manager without extending their lifetime."""
        view = self._download_view_ref() if self._download_view_ref is not None else None
        manager = (
            self._download_manager_ref() if self._download_manager_ref is not None else None
        )
        opener = self._download_opener_ref() if self._download_opener_ref is not None else None
        return view, manager, self._opened_for_popup, opener

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
        # Certificate diagnostics must not write Incognito destinations to the
        # application's persistent logs.
        if not self.profile().isOffTheRecord():
            logger.warning(
                "SSL Certificate Error on %s: %s (error code: %s)",
                certificate_error.url().host(),
                certificate_error.description(),
                certificate_error.type(),
            )
        return False

    def javaScriptConsoleMessage(self, level, message: str, line_number: int, source_id: str) -> None:
        """Forward bounded console metadata to attached developer tools UI."""
        severity = getattr(level, "name", str(level)).replace("JavaScriptConsoleMessageLevel", "").lower()
        self.console_message.emit(severity, message[:4000], int(line_number), source_id[:1000])
        super().javaScriptConsoleMessage(level, message, line_number, source_id)

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
