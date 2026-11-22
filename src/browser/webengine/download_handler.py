"""Connect Qt WebEngine profiles to browser download managers."""

import logging
import weakref
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, QSettings
from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget
from PySide6.QtWebEngineCore import (
    QWebEngineDownloadRequest,
    QWebEnginePage,
    QWebEngineProfile,
)

from browser.features.downloads.download_manager import DownloadManager
from browser.features.downloads.download_utils import (
    default_download_directory,
    preserve_file_extension,
    safe_filename,
)

logger = logging.getLogger(__name__)


class DownloadHandler(QObject):
    """Own one profile signal connection and prompt for every destination."""

    def __init__(
        self,
        manager: DownloadManager,
        parent_window: QWidget | None = None,
        parent: QObject | None = None,
        private_session: bool = False,
    ) -> None:
        super().__init__(parent)
        self._manager = manager
        self._private_session=private_session
        self._private_notice_shown=False
        self._window_ref = weakref.ref(parent_window) if parent_window is not None else lambda: None

    def handle_request(self, request: QWebEngineDownloadRequest) -> None:
        """Select the destination, configure it, then accept or cancel promptly."""
        # Schedule restoration before the modal save dialog runs its nested event loop.
        # This keeps the originating page visible behind the dialog as well as afterward.
        self._restore_page_after_download_navigation(request)
        original_name = request.suggestedFileName()
        mime_type = request.mimeType()
        source_url = request.url().toString()
        suggested = preserve_file_extension(
            safe_filename(original_name), original_name, mime_type, source_url
        )
        prefs = QSettings("LightMq", "LightMq Browser")
        configured_dir = str(prefs.value("downloads/default_directory", "")).strip()
        base_dir = Path(configured_dir).expanduser() if configured_dir else default_download_directory()
        initial = str(base_dir / suggested)
        window = self._window_ref()
        parent = window if window is not None else None

        try:
            if bool(prefs.value("downloads/ask_before_saving", True, type=bool)):
                destination, _ = QFileDialog.getSaveFileName(parent, "Save Download", initial, "All Files (*)")
            else:
                destination = initial
            while destination:
                target = Path(destination).expanduser()
                filename = preserve_file_extension(
                    safe_filename(target.name), suggested, mime_type, source_url
                )
                target = target.parent / filename
                if not target.parent.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    answer = QMessageBox.question(
                        parent,
                        "Replace existing file?",
                        f"{target.name} already exists. Replace it?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    if answer != QMessageBox.StandardButton.Yes:
                        destination, _ = QFileDialog.getSaveFileName(
                            parent, "Choose a different download name", str(target), "All Files (*)"
                        )
                        continue

                # Qt requires both values to be set before accept().
                request.setDownloadDirectory(str(target.parent.resolve()))
                request.setDownloadFileName(filename)
                self._manager.add_request(request, str(target.resolve()))
                request.accept()
                self._manager.mark_accepted(request.id())
                if self._private_session and not self._private_notice_shown:
                    self._private_notice_shown=True
                    self._manager.notify("Incognito downloads are saved on this device and remain after the private session ends.",6000)
                self._schedule_popup_tab_cleanup(request)
                # Qt may commit the download navigation after the chooser returns.
                self._restore_page_after_download_navigation(request)
                return

            request.cancel()
            self._schedule_popup_tab_cleanup(request)
            self._restore_page_after_download_navigation(request)
            self._manager.notify("Download cancelled", 2500)
        except (OSError, RuntimeError) as exc:
            try:
                request.cancel()
            except RuntimeError:
                pass
            logger.warning("Could not prepare download destination: %s", exc)
            self._manager.notify(f"Could not start download: {exc}", 6000)

    @staticmethod
    def _restore_page_after_download_navigation(request: QWebEngineDownloadRequest) -> None:
        """Restore the previous page when a top-level URL becomes a download."""
        try:
            page = request.page() if hasattr(request, "page") else None
            if page is None:
                return
            download_url = QUrl(request.url())
        except RuntimeError:
            return

        def restore(attempt: int = 0) -> None:
            try:
                current_url = page.url()
                current_text = current_url.toString()
                history = page.history()
                has_previous_page = (
                    history.canGoBack()
                    and history.backItem().url().toString() not in ("", "about:blank")
                )
                view, tab_manager, opened_for_popup, opener_view = page.download_context()
                last_navigation_url = page.last_main_frame_navigation_url()
                is_download_navigation = current_url == download_url
                is_uninitialized_popup = (
                    opened_for_popup
                    and current_text in ("", "about:blank")
                    and last_navigation_url == download_url
                )

                if opened_for_popup and not has_previous_page and (
                    is_download_navigation
                    or is_uninitialized_popup
                    or last_navigation_url == download_url
                ):
                    page._close_popup_after_download = True
                    if opener_view is not None and tab_manager is not None:
                        opener_index = tab_manager.index_of(opener_view)
                        if opener_index >= 0:
                            tab_manager.set_current_index(opener_index)
                    elif is_download_navigation:
                        page.setHtml(
                            "<html><body><p>This page started a download.</p>"
                            "<p>Open Downloads to check its progress.</p></body></html>"
                        )
                    if page._download_handled:
                        DownloadHandler._queue_popup_tab_close(view, tab_manager)
                    return

                if not is_download_navigation:
                    if attempt < 40:
                        QTimer.singleShot(50, lambda: restore(attempt + 1))
                    return

                if has_previous_page:
                    page.triggerAction(QWebEnginePage.WebAction.Back)
                else:
                    page.setHtml(
                        "<html><body><p>This page started a download.</p>"
                        "<p>Open Downloads to check its progress.</p></body></html>"
                    )
                if opened_for_popup:
                    page._close_popup_after_download = True
                    if page._download_handled:
                        DownloadHandler._queue_popup_tab_close(view, tab_manager)
            except RuntimeError:
                return

        QTimer.singleShot(0, restore)

    @staticmethod
    def _schedule_popup_tab_cleanup(request: QWebEngineDownloadRequest) -> None:
        """Close a popup tab that had no useful page before its download."""
        try:
            page = request.page() if hasattr(request, "page") else None
            if page is None:
                return
            page._download_handled = True
            if not page._close_popup_after_download:
                return
            view, tab_manager, _, _ = page.download_context()
        except RuntimeError:
            return
        if view is None or tab_manager is None:
            return
        DownloadHandler._queue_popup_tab_close(view, tab_manager)

    @staticmethod
    def _queue_popup_tab_close(view: QObject | None, tab_manager: QObject | None) -> None:
        """Queue removal of the marked popup after Qt finishes its request callback."""
        if view is None or tab_manager is None:
            return

        def close_popup_tab() -> None:
            try:
                index = tab_manager.index_of(view)
                if index >= 0:
                    tab_manager.close_tab(index)
            except RuntimeError:
                return

        QTimer.singleShot(0, close_popup_tab)

    def set_parent_window(self, parent_window: QWidget | None) -> None:
        """Use the most recently active window for future save dialogs."""
        self._window_ref = weakref.ref(parent_window) if parent_window is not None else lambda: None


def attach_download_handler(
    profile: QWebEngineProfile,
    manager: DownloadManager,
    parent_window: QWidget | None = None,
    private_session: bool = False,
) -> DownloadHandler:
    """Connect a handler once for a given profile/manager pair."""
    key = (id(profile), id(manager))
    handler = manager.handler_for(key)
    if handler is None:
        handler = DownloadHandler(manager,parent_window,parent=manager,private_session=private_session)
        profile.downloadRequested.connect(handler.handle_request)
        manager.retain_handler(key, handler)
    elif isinstance(handler, DownloadHandler):
        handler.set_parent_window(parent_window)
    return handler
