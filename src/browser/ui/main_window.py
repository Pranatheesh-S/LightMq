"""Main application window for LightMq Browser.

Coordinates multiple tab management, navigation toolbar, address bar,
stacked WebEngine viewports, status bar, genuine Chromium Developer Tools,
find-in-page, bookmarks bar, and comprehensive keyboard shortcut handling.
"""

import logging
from PySide6.QtCore import Qt, QUrl, QSettings
from PySide6.QtGui import QAction, QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile

from browser.core.navigation import normalize_url
from browser.core.session_manager import SessionManager
from browser.core.tab_manager import TabManager
from browser.devtools.devtools_manager import DevToolsManager
from browser.devtools.devtools_panel import DevToolsPanel
from browser.features.bookmarks.bookmark_manager import BookmarkManager
from browser.features.downloads.download_manager import DownloadManager
from browser.features.history.history_manager import HistoryManager
from browser.features.privacy.privacy_manager import PrivacyManager
from browser.ui.address_bar import AddressBar
from browser.ui.dialogs.bookmark_dialog import BookmarkDialog
from browser.ui.dialogs.clear_data_dialog import ClearDataDialog
from browser.ui.dialogs.downloads_dialog import DownloadsDialog
from browser.ui.dialogs.history_dialog import HistoryDialog
from browser.ui.dialogs.privacy_settings_dialog import PrivacySettingsDialog
from browser.ui.dialogs.startup_settings_dialog import StartupSettingsDialog
from browser.ui.shortcut_manager import ShortcutManager
from browser.ui.tab_bar import TabBar
from browser.ui.widgets.bookmarks_bar import BookmarksBar
from browser.ui.widgets.find_bar import FindBar
from browser.ui.widgets.notification_toast import NotificationToast
from browser.utils.constants import APP_NAME, DEFAULT_START_URL, get_engine_diagnostics
from browser.storage.session_model import SessionSnapshot
from browser.storage.settings import StartupSettings
from browser.webengine.download_handler import attach_download_handler
from browser.webengine.permissions import PendingPermission, PermissionRequestHandler
from browser.webengine.web_profile import WebProfileManager
from browser.webengine.web_view import WebView

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main browser desktop window supporting multiple tabs, DevTools, and shortcuts."""

    _all_windows: list["MainWindow"] = []

    def __init__(
        self,
        initial_url: str | None = None,
        is_private: bool = False,
        session_manager: SessionManager | None = None,
        restore_snapshot: SessionSnapshot | None = None,
    ):
        super().__init__()
        MainWindow._all_windows.append(self)

        self._is_private = is_private
        self._was_maximized = False
        self._loading_states: dict[WebView, int] = {}
        self._history_navigation_pending: dict[WebView, str] = {}
        self._history_urls_by_view: dict[WebView, str] = {}
        self._permission_dialogs: dict[tuple[int, str, int], QMessageBox] = {}
        self._settings = QSettings("LightMq", "LightMq Browser")
        self._startup_settings = StartupSettings(self._settings)
        self._session_manager = None if is_private else session_manager
        self._startup_settings_dialog: StartupSettingsDialog | None = None

        # Profile initialization
        if self._is_private:
            self._profile: QWebEngineProfile | None = QWebEngineProfile(self)
            self._privacy_manager: PrivacyManager | None = None
            self._permission_handler: PermissionRequestHandler | None = None
            self.download_manager = DownloadManager(parent=self)
            self._base_title = f"{APP_NAME} (Private Browsing)"
        else:
            self._profile = WebProfileManager.default_profile()
            self._privacy_manager = PrivacyManager(self._profile, self)
            self._permission_handler = PermissionRequestHandler(self)
            self._permission_handler.permission_requested.connect(self._show_permission_request)
            self._permission_handler.request_cancelled.connect(self._dismiss_permission_request)
            self._permission_handler.permissions_changed.connect(self._privacy_manager.permissions_changed)
            self._privacy_manager.cache.clear_completed.connect(
                lambda: self.status_bar.showMessage("HTTP cache clearing completed.", 5000)
                if hasattr(self, "status_bar") else None
            )
            self._privacy_manager.cache.clear_failed.connect(
                lambda message: self.status_bar.showMessage(message, 5000)
                if hasattr(self, "status_bar") else None
            )
            self._privacy_manager.cookies.operation_requested.connect(
                lambda message: self.status_bar.showMessage(message, 5000)
                if hasattr(self, "status_bar") else None
            )
            self.download_manager = DownloadManager.get_instance()
            self._base_title = APP_NAME

        self.setWindowTitle(self._base_title)
        self.resize(1280, 850)

        self._init_ui()
        self._notification_toast = NotificationToast(self)
        self._init_shortcuts()
        self._connect_downloads()

        if self._session_manager is not None:
            self._session_manager.bind(self.tab_manager)
            self._session_manager.save_failed.connect(self._on_session_save_failed)

        # Restore before creating a fallback tab so no transient blank tab is saved.
        restored_count = (
            self._session_manager.restore(restore_snapshot)
            if self._session_manager is not None and restore_snapshot is not None
            else 0
        )
        if restored_count == 0:
            self.tab_manager.create_tab(url=initial_url or DEFAULT_START_URL, activate=True)

    @property
    def web_view(self) -> WebView | None:
        """Return the currently active tab's WebView for backward compatibility."""
        return self.tab_manager.current_view()

    @property
    def is_private(self) -> bool:
        """Return True if this window is in private browsing mode."""
        return self._is_private

    def closeEvent(self, event: QCloseEvent) -> None:
        """Save the final normal session before Qt destroys tabs and child pages."""
        if self._session_manager is not None:
            self._session_manager.finish()
        if self._permission_handler is not None:
            for index in range(self.tab_manager.count()):
                view = self.tab_manager.view_at(index)
                if view is not None:
                    self._permission_handler.cancel_for_page(view.page())
        for dialog in tuple(self._permission_dialogs.values()):
            dialog.close()
        self._permission_dialogs.clear()
        try:
            self.download_manager.notification.disconnect(self._show_download_notification)
            self.download_manager.active_count_changed.disconnect(self._update_download_button)
        except (RuntimeError, TypeError):
            pass
        if self in MainWindow._all_windows:
            MainWindow._all_windows.remove(self)
        if not self._is_private and hasattr(self, "_download_handler"):
            remaining_window = next(
                (
                    window
                    for window in MainWindow._all_windows
                    if window.download_manager is self.download_manager and not window.is_private
                ),
                None,
            )
            self._download_handler.set_parent_window(remaining_window)
        super().closeEvent(event)

    def _connect_downloads(self) -> None:
        """Connect download requests to DownloadManager."""
        self._download_handler = attach_download_handler(
            self._profile, self.download_manager, self
        )
        self.download_manager.notification.connect(self._show_download_notification)
        self.download_manager.active_count_changed.connect(self._update_download_button)
        self._update_download_button(
            sum(item.is_active for item in self.download_manager.get_downloads())
        )

    def _init_ui(self) -> None:
        """Construct the tab bar, toolbar, central splitter, and status bar."""
        central_widget = QWidget(self)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Tab Bar (Above Navigation Toolbar)
        self.tab_bar = TabBar(central_widget)
        main_layout.addWidget(self.tab_bar)

        # 2. Tab Manager
        self.tab_manager = TabManager(
            default_url=DEFAULT_START_URL,
            profile=self._profile,
            is_private=self._is_private,
            parent=self,
        )

        # 3. Central Horizontal Splitter (Web Views & DevTools)
        self.splitter = QSplitter(Qt.Orientation.Horizontal, central_widget)

        # 3a. Stacked Widget hosting all tab WebViews
        self.stacked_widget = QStackedWidget(self.splitter)
        self.splitter.addWidget(self.stacked_widget)

        # 3b. Reusable DevTools Panel
        self.devtools_panel = DevToolsPanel(self.splitter)
        self.devtools_panel.hide()
        self.splitter.addWidget(self.devtools_panel)

        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)

        # 4. Developer Tools Manager
        self.devtools_manager = DevToolsManager(
            devtools_panel=self.devtools_panel,
            splitter=self.splitter,
            parent=self,
        )

        # 5. Navigation Toolbar
        self._build_toolbar()
        main_layout.addWidget(self.toolbar)

        # 6. Bookmarks Bar (Toggled with Ctrl+Shift+B, hidden by default)
        self.bookmarks_bar = BookmarksBar(parent=central_widget)
        self.bookmarks_bar.open_url_requested.connect(self.navigate_to)
        self.bookmarks_bar.setVisible(
            not self._is_private and self._settings.value("bookmarks_bar_visible", False, type=bool)
        )
        main_layout.addWidget(self.bookmarks_bar)

        # 7. Find in Page Bar (Toggled with Ctrl+F, hidden by default)
        self.find_bar = FindBar(parent=central_widget)
        main_layout.addWidget(self.find_bar)

        # 8. Add Splitter to Central Layout
        main_layout.addWidget(self.splitter)
        self.setCentralWidget(central_widget)

        # 9. Status Bar & Loading Progress
        self._build_statusbar()

        # 10. Connect TabManager and TabBar
        self._connect_tab_signals()

    def _build_toolbar(self) -> None:
        """Create the navigation toolbar."""
        self.toolbar = QToolBar("Navigation", self)
        self.toolbar.setMovable(False)

        # Back Action
        self.action_back = QAction("←", self)
        self.action_back.setToolTip("Back (Alt+Left)")
        self.action_back.setEnabled(False)
        self.action_back.triggered.connect(self.back)
        self.toolbar.addAction(self.action_back)

        # Forward Action
        self.action_forward = QAction("→", self)
        self.action_forward.setToolTip("Forward (Alt+Right)")
        self.action_forward.setEnabled(False)
        self.action_forward.triggered.connect(self.forward)
        self.toolbar.addAction(self.action_forward)

        # Reload Action
        self.action_reload = QAction("↻", self)
        self.action_reload.setToolTip("Reload (Ctrl+R / F5)")
        self.action_reload.triggered.connect(self.reload)
        self.toolbar.addAction(self.action_reload)

        # Stop Action
        self.action_stop = QAction("✕", self)
        self.action_stop.setToolTip("Stop (Esc)")
        self.action_stop.triggered.connect(self.stop)
        self.toolbar.addAction(self.action_stop)

        # Address Bar
        self.address_bar = AddressBar(self)
        self.address_bar.navigate_requested.connect(self.navigate_to)
        self.toolbar.addWidget(self.address_bar)

        # Go Button
        self.btn_go = QPushButton("Go", self)
        self.btn_go.setToolTip("Navigate to URL")
        self.btn_go.clicked.connect(self._on_go_clicked)
        self.toolbar.addWidget(self.btn_go)

        # DevTools Toggle Button
        self.btn_devtools = QPushButton("DevTools", self)
        self.btn_devtools.setToolTip("Toggle Chromium Developer Tools (F12)")
        self.btn_devtools.setCheckable(True)
        self.btn_devtools.clicked.connect(self.devtools_manager.toggle)
        self.toolbar.addWidget(self.btn_devtools)

        # Synchronize DevTools button state
        self.devtools_manager.visibility_changed.connect(self.btn_devtools.setChecked)

        # About Button
        self.btn_about = QPushButton("About", self)
        self.btn_about.setToolTip("View browser and Chromium engine specifications")
        self.btn_about.clicked.connect(self.show_about_dialog)
        self.toolbar.addWidget(self.btn_about)

        self.btn_downloads = QPushButton("Downloads", self)
        self.btn_downloads.setToolTip("Open Download Manager (Ctrl+J)")
        self.btn_downloads.clicked.connect(self.open_downloads)
        self.toolbar.addWidget(self.btn_downloads)

        if not self._is_private:
            self.btn_privacy = QPushButton("Privacy", self)
            self.btn_privacy.setToolTip("Manage cookies, permissions, cache, and browsing data")
            self.btn_privacy.clicked.connect(self.open_privacy_settings)
            self.toolbar.addWidget(self.btn_privacy)

            self.btn_startup_settings = QPushButton("Startup", self)
            self.btn_startup_settings.setToolTip("Choose what LightMq opens at startup")
            self.btn_startup_settings.clicked.connect(self.open_startup_settings)
            self.toolbar.addWidget(self.btn_startup_settings)

    def _build_statusbar(self) -> None:
        """Configure the bottom status bar and loading progress bar."""
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setMaximumWidth(120)
        self.progress_bar.setMaximumHeight(14)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        self.status_bar.addPermanentWidget(self.progress_bar)

    def _connect_tab_signals(self) -> None:
        """Wire TabManager events to TabBar, QStackedWidget, and DevTools."""
        self.tab_manager.tab_created.connect(self._on_tab_created)
        self.tab_manager.tab_closing.connect(self._on_tab_closing)
        self.tab_manager.tab_closed.connect(self._on_tab_closed)
        self.tab_manager.current_changed.connect(self._on_current_tab_changed)
        self.tab_manager.tab_moved.connect(self._on_tab_moved)

        self.tab_bar.tab_close_requested.connect(self.tab_manager.close_tab)
        self.tab_bar.current_changed.connect(self.tab_manager.set_current_index)
        self.tab_bar.new_tab_requested.connect(lambda: self.tab_manager.create_tab(DEFAULT_START_URL))
        self.tab_bar.tab_moved.connect(self.tab_manager.move_tab)

    def _init_shortcuts(self) -> None:
        """Register all default keyboard shortcuts through the ShortcutManager."""
        self.shortcut_manager = ShortcutManager(self)
        self.shortcut_manager.register_all_default_shortcuts()

    # --------------------------------------------------------------------------
    # TabManager Event Handlers
    # --------------------------------------------------------------------------

    def _on_tab_created(self, index: int, view: WebView) -> None:
        """Handle new tab creation: add to stacked widget and connect WebEngine signals."""
        self.stacked_widget.insertWidget(index, view)
        self.tab_bar.insert_tab(index, getattr(view, "restored_title", "") or "New Tab")

        # Connect signals for independent tab state updates
        view.titleChanged.connect(lambda title, v=view: self._on_tab_title_changed(v, title))
        view.iconChanged.connect(lambda icon, v=view: self._on_tab_icon_changed(v, icon))
        view.urlChanged.connect(lambda url, v=view: self._on_tab_url_changed(v, url))
        view.loadStarted.connect(lambda v=view: self._on_tab_load_started(v))
        view.loadProgress.connect(lambda prog, v=view: self._on_tab_load_progress(v, prog))
        view.loadFinished.connect(lambda ok, v=view: self._on_tab_load_finished(v, ok))
        if self._permission_handler is not None:
            self._permission_handler.attach_page(view.page())
        view.page().main_frame_navigation_requested.connect(
            lambda _url, visit_type, v=view: self._history_navigation_pending.__setitem__(v, visit_type)
        )
        view.page().linkHovered.connect(lambda link, v=view: self._on_tab_link_hovered(v, link))

        # History action enabled state changes
        view.page().action(QWebEnginePage.WebAction.Back).changed.connect(
            lambda v=view: self._on_tab_action_changed(v)
        )
        view.page().action(QWebEnginePage.WebAction.Forward).changed.connect(
            lambda v=view: self._on_tab_action_changed(v)
        )

    def _on_tab_closing(self, index: int, view: WebView) -> None:
        """Prepare for tab destruction: detach DevTools if currently attached."""
        self.devtools_manager.on_view_closing(view)
        self._loading_states.pop(view, None)
        self._history_navigation_pending.pop(view, None)
        self._history_urls_by_view.pop(view, None)
        if self._permission_handler is not None:
            self._permission_handler.cancel_for_page(view.page())

    def _on_tab_closed(self, index: int) -> None:
        """Update UI after tab is removed from manager."""
        self.tab_bar.remove_tab(index)
        widget = self.stacked_widget.widget(index)
        if widget is not None:
            self.stacked_widget.removeWidget(widget)

    def _on_current_tab_changed(self, index: int, view: WebView) -> None:
        """Switch active tab: update UI, toolbar, address bar, find bar, and DevTools."""
        self.tab_bar.set_current_index(index)
        self.stacked_widget.setCurrentWidget(view)

        # Attach DevTools to the new active page
        self.devtools_manager.set_target_view(view)

        # Synchronize find bar with newly active tab
        self.find_bar.set_active_view(view)

        # Update address bar and title for the newly active tab
        current_url = view.url()
        self.address_bar.set_url(current_url)

        title = view.title()
        if title:
            self.setWindowTitle(f"{title} - {self._base_title}")
        else:
            self.setWindowTitle(self._base_title)

        # Update navigation controls for active tab
        self._update_navigation_actions(view)

        # Update progress bar state for active tab
        if view in self._loading_states:
            prog = self._loading_states[view]
            self.progress_bar.setValue(prog)
            self.progress_bar.show()
            self.status_bar.showMessage("Loading...")
        else:
            self.progress_bar.hide()
            self.status_bar.clearMessage()

    def _on_tab_moved(self, from_index: int, to_index: int) -> None:
        """Synchronize stacked widget when a tab is moved in the tab bar."""
        widget = self.stacked_widget.widget(from_index)
        if widget is not None:
            self.stacked_widget.removeWidget(widget)
            self.stacked_widget.insertWidget(to_index, widget)

    # --------------------------------------------------------------------------
    # WebEngine Event Handlers (Dispatched with view context)
    # --------------------------------------------------------------------------

    def _on_tab_title_changed(self, view: WebView, title: str) -> None:
        """Update tab label and, if active, update the window title."""
        idx = self.tab_manager.index_of(view)
        if idx != -1:
            self.tab_bar.set_tab_title(idx, title or "New Tab")

        if view is self.tab_manager.current_view():
            if title:
                self.setWindowTitle(f"{title} - {self._base_title}")
            else:
                self.setWindowTitle(self._base_title)

        visited_url = self._history_urls_by_view.get(view)
        if visited_url and not self._is_private and view.url().toString() == visited_url:
            HistoryManager.get_instance().update_title(visited_url, title)

    def _on_title_changed(self, title: str) -> None:
        """Backward-compatible helper to update title for active tab or window."""
        active = self.tab_manager.current_view()
        if active is not None:
            self._on_tab_title_changed(active, title)
        else:
            self.setWindowTitle(f"{title} - {self._base_title}" if title else self._base_title)

    def _on_tab_icon_changed(self, view: WebView, icon: QIcon) -> None:
        """Update tab favicon."""
        idx = self.tab_manager.index_of(view)
        if idx != -1 and not icon.isNull():
            self.tab_bar.set_tab_icon(idx, icon)

    def _on_tab_url_changed(self, view: WebView, url: QUrl) -> None:
        """Update tab tooltip and, if active, update the address bar."""
        idx = self.tab_manager.index_of(view)
        if idx != -1:
            self.tab_bar.set_tab_tooltip(idx, url.toString())

        if view is self.tab_manager.current_view():
            self.address_bar.set_url(url)
            self._update_navigation_actions(view)

    def _on_tab_load_started(self, view: WebView) -> None:
        """Record loading state."""
        self._loading_states[view] = 0
        if view is self.tab_manager.current_view():
            self.progress_bar.setValue(0)
            self.progress_bar.show()
            self.status_bar.showMessage("Loading...")

    def _on_tab_load_progress(self, view: WebView, progress: int) -> None:
        """Update load progress."""
        self._loading_states[view] = progress
        if view is self.tab_manager.current_view():
            self.progress_bar.setValue(progress)

    def _on_tab_load_finished(self, view: WebView, success: bool) -> None:
        """Clear loading state, record history, and update status bar."""
        self._loading_states.pop(view, None)
        visit_type = self._history_navigation_pending.pop(view, None)
        if view is self.tab_manager.current_view():
            self.progress_bar.hide()
            if success:
                self.status_bar.showMessage("Done", 2000)
            else:
                self.status_bar.showMessage(f"Failed to load: {view.url().toString()}", 5000)
            self._update_navigation_actions(view)

        # Commit only a successful top-level navigation in a regular window.
        # This excludes failed loads, internal pages, and download responses that
        # replace a document with a blank page.
        if success and visit_type is not None and not self._is_private:
            url_str = view.url().toString()
            manager = HistoryManager.get_instance()
            manager.add_entry(
                url_str, view.title(), favicon=view.page().iconUrl().toString(), visit_type=visit_type
            )
            self._history_urls_by_view[view] = url_str

    def _on_tab_link_hovered(self, view: WebView, url_str: str) -> None:
        """Display hovered link in status bar if this is the active tab."""
        if view is self.tab_manager.current_view():
            if url_str:
                self.status_bar.showMessage(url_str)
            else:
                self.status_bar.clearMessage()

    def _on_tab_action_changed(self, view: WebView) -> None:
        """Update toolbar back/forward buttons when history state updates for active tab."""
        if view is self.tab_manager.current_view():
            self._update_navigation_actions(view)

    # --------------------------------------------------------------------------
    # Navigation Actions & Dialogs
    # --------------------------------------------------------------------------

    def _update_navigation_actions(self, view: WebView | None) -> None:
        """Synchronize Back and Forward button states with the active view's history."""
        if view is not None:
            can_back = view.page().action(QWebEnginePage.WebAction.Back).isEnabled()
            can_forward = view.page().action(QWebEnginePage.WebAction.Forward).isEnabled()
            self.action_back.setEnabled(can_back)
            self.action_forward.setEnabled(can_forward)
        else:
            self.action_back.setEnabled(False)
            self.action_forward.setEnabled(False)

    def navigate_to(self, text: str) -> None:
        """Instruct the active tab to navigate to the normalized target URL."""
        active_view = self.tab_manager.current_view()
        if active_view is not None:
            target_url = normalize_url(text)
            self.status_bar.showMessage(f"Navigating to {target_url.toString()}...", 2000)
            active_view.navigate(target_url)

    def back(self) -> None:
        """Navigate back on the active tab."""
        view = self.tab_manager.current_view()
        if view is not None:
            view.back()

    def forward(self) -> None:
        """Navigate forward on the active tab."""
        view = self.tab_manager.current_view()
        if view is not None:
            view.forward()

    def reload(self) -> None:
        """Reload the active tab."""
        view = self.tab_manager.current_view()
        if view is not None:
            view.reload()

    def reload_bypass_cache(self) -> None:
        """Reload the active tab while bypassing cached resources."""
        view = self.tab_manager.current_view()
        if view is not None:
            view.triggerPageAction(QWebEnginePage.WebAction.ReloadAndBypassCache)
            self.status_bar.showMessage("Reloading (bypassing cache)...", 2000)

    def stop(self) -> None:
        """Stop loading on the active tab."""
        view = self.tab_manager.current_view()
        if view is not None:
            view.stop()

    def stop_or_dismiss(self) -> None:
        """Dismiss the find bar if active, or stop active page loading."""
        if self.find_bar.isVisible():
            self.find_bar.close_and_clear()
        else:
            self.stop()

    def home(self) -> None:
        """Navigate the active tab to the configured homepage."""
        self.navigate_to(self._startup_settings.homepage())

    def focus_address_bar(self) -> None:
        """Focus the address bar and select all current text."""
        self.address_bar.setFocus()
        self.address_bar.selectAll()

    def _on_go_clicked(self) -> None:
        """Handle click on the Go button."""
        text = self.address_bar.text().strip()
        if text:
            self.navigate_to(text)

    # --------------------------------------------------------------------------
    # Tab & Window Operations (Keyboard Shortcuts)
    # --------------------------------------------------------------------------

    def new_tab(self) -> WebView:
        """Open a new tab with the default start page."""
        return self.tab_manager.create_tab(DEFAULT_START_URL, activate=True)

    def close_tab(self) -> None:
        """Close the currently active tab."""
        self.tab_manager.close_current_tab()

    def restore_closed_tab(self) -> WebView | None:
        """Restore the most recently closed tab."""
        restored = self.tab_manager.restore_closed_tab()
        if restored is None:
            self.status_bar.showMessage("No recently closed tabs to restore.", 2000)
        else:
            self.status_bar.showMessage("Restored recently closed tab.", 2000)
        return restored

    def new_window(self) -> "MainWindow":
        """Open a new regular browser desktop window."""
        win = MainWindow(initial_url=DEFAULT_START_URL, is_private=False)
        win.show()
        return win

    def new_private_window(self) -> "MainWindow":
        """Open an isolated private browsing window."""
        win = MainWindow(initial_url=DEFAULT_START_URL, is_private=True)
        win.show()
        return win

    def next_tab(self) -> None:
        """Switch to next tab with wrap-around."""
        self.tab_manager.next_tab()

    def prev_tab(self) -> None:
        """Switch to previous tab with wrap-around."""
        self.tab_manager.prev_tab()

    def switch_to_tab(self, index: int) -> None:
        """Switch to tab at specified index (0 to 7)."""
        self.tab_manager.switch_to_tab(index)

    def switch_to_last_tab(self) -> None:
        """Switch to the last tab in the tab bar."""
        self.tab_manager.switch_to_last_tab()

    # --------------------------------------------------------------------------
    # Page Controls (Find, Bookmark, Print, Save)
    # --------------------------------------------------------------------------

    def open_find_in_page(self) -> None:
        """Open or focus the find-in-page toolbar."""
        self.find_bar.show_and_focus()

    def bookmark_current_page(self) -> None:
        """Bookmark the active tab's page or edit existing bookmark."""
        view = self.tab_manager.current_view()
        if view is None:
            return

        url = view.url().toString()
        title = view.title() or url
        manager = BookmarkManager.get_instance()

        if not manager.is_bookmarked(url):
            if manager.add_bookmark(title, url):
                self.status_bar.showMessage(f"Bookmark added: {title}", 3000)
        else:
            self._bookmark_dialog = BookmarkDialog(title, url, bookmark_manager=manager, parent=self)
            self._bookmark_dialog.show()

    def print_current_page(self) -> None:
        """Print the active tab's webpage."""
        view = self.tab_manager.current_view()
        if view is None:
            return

        try:
            from PySide6.QtPrintSupport import QPrintDialog, QPrinter

            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            dlg = QPrintDialog(printer, self)
            if dlg.exec() == QPrintDialog.DialogCode.Accepted:
                view.print(printer)
                self.status_bar.showMessage("Printing started...", 2000)
        except Exception as e:
            logger.warning("Print dialog not available or failed: %s", e)
            self.status_bar.showMessage("Printing unavailable.", 2000)

    def save_current_page(self) -> None:
        """Save the active webpage to local disk."""
        view = self.tab_manager.current_view()
        if view is None:
            return

        safe_title = "".join(c for c in (view.title() or "webpage") if c.isalnum() or c in " ._-").strip()
        default_filename = f"{safe_title or 'page'}.html"

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Webpage",
            default_filename,
            "HTML Files (*.html *.htm);;All Files (*)",
        )
        if path:
            try:
                view.page().save(path)
                self.status_bar.showMessage(f"Saved webpage to {path}", 3000)
            except Exception as e:
                logger.error("Failed to save webpage: %s", e)
                self.status_bar.showMessage("Failed to save page.", 3000)

    # --------------------------------------------------------------------------
    # Browser Management (History, Downloads, Clear Data, Fullscreen, Zoom)
    # --------------------------------------------------------------------------

    def open_history(self) -> None:
        """Open the browsing history dialog."""
        self._history_dialog = HistoryDialog(parent=self)
        self._history_dialog.open_url_requested.connect(self.navigate_to)
        self._history_dialog.open_in_new_tab_requested.connect(
            lambda url: self.tab_manager.create_tab(url=url, activate=True)
        )
        self._history_dialog.show()

    def open_downloads(self) -> None:
        """Open the downloads manager dialog."""
        if not hasattr(self, "_downloads_dialog"):
            self._downloads_dialog = DownloadsDialog(self.download_manager, parent=self)
        self._downloads_dialog.show()
        self._downloads_dialog.raise_()
        self._downloads_dialog.activateWindow()

    def _show_download_notification(self, message: str, timeout_ms: int) -> None:
        """Show a lightweight transfer status in the browser status bar."""
        self.status_bar.showMessage(message, timeout_ms)
        peers = [
            window
            for window in MainWindow._all_windows
            if window.download_manager is self.download_manager
        ]
        active_peer = next((window for window in peers if window.isActiveWindow()), None)
        if active_peer is self or (active_peer is None and peers and peers[-1] is self):
            self._notification_toast.show_message(message, timeout_ms)

    def _update_download_button(self, active_count: int) -> None:
        """Show the current active transfer count in the toolbar."""
        self.btn_downloads.setText(f"Downloads ({active_count})" if active_count else "Downloads")

    def open_privacy_settings(self) -> PrivacySettingsDialog | None:
        """Open settings for cookies, permissions, and HTTP cache on the normal profile."""
        if self._is_private or self._privacy_manager is None:
            return None
        dialog = PrivacySettingsDialog(self._privacy_manager, self.open_clear_data, self)
        self._privacy_settings_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        return dialog

    def open_startup_settings(self) -> StartupSettingsDialog | None:
        """Open native startup-mode and homepage preferences."""
        if self._is_private:
            return None
        dialog = StartupSettingsDialog(self._startup_settings, self)
        self._startup_settings_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        return dialog

    def _on_session_save_failed(self, message: str) -> None:
        """Surface session persistence errors without interrupting navigation."""
        self.status_bar.showMessage(message, 8000)

    def _show_permission_request(self, request: PendingPermission) -> None:
        """Show an asynchronous prompt naming the permission's actual origin."""
        if self._permission_handler is None:
            return
        if not request.capability:
            self._permission_handler.resolve(request, False)
            return
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Website Permission Request")
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setText(f"{request.origin}\n\nWants permission to use {request.capability}.")
        dialog.setInformativeText("Allow only if you trust this website. No permission is granted automatically.")
        allow_button = dialog.addButton("Allow", QMessageBox.ButtonRole.AcceptRole)
        block_button = dialog.addButton("Block", QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(block_button)
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._permission_dialogs[request.key] = dialog
        dialog.finished.connect(
            lambda _result, req=request, box=dialog, allow=allow_button:
                self._finish_permission_request(req, box, box.clickedButton() is allow)
        )
        dialog.open()
        dialog.raise_()

    def _finish_permission_request(
        self, request: PendingPermission, dialog: QMessageBox, allow: bool,
    ) -> None:
        """Resolve a prompt and remove its tracking entry."""
        self._permission_dialogs.pop(request.key, None)
        if self._permission_handler is not None:
            self._permission_handler.resolve(request, allow)

    def _dismiss_permission_request(self, request: PendingPermission) -> None:
        """Close a request dialog when navigation or tab destruction invalidates it."""
        dialog = self._permission_dialogs.pop(request.key, None)
        if dialog is not None:
            dialog.close()

    def open_clear_data(self) -> ClearDataDialog | None:
        """Open the clear browsing data dialog."""
        if self._is_private or self._privacy_manager is None:
            return None
        dialog = ClearDataDialog(parent=self)
        self._clear_data_dialog = dialog
        dialog.accepted.connect(lambda: self._on_clear_data_accepted(dialog))
        dialog.show()
        return dialog

    def _on_clear_data_accepted(self, dialog: ClearDataDialog) -> None:
        """Process data clearing options selected in dialog."""
        if self._privacy_manager is None:
            return
        summary: list[str] = []
        if dialog.clear_history:
            start, end = dialog.history_range()
            HistoryManager.get_instance().clear(start=start, end=end)
            summary.append("History deletion completed in LightMq.")
        if dialog.clear_cache:
            if self._privacy_manager.cache.clear():
                if self._privacy_manager.cache.supports_completion_signal:
                    summary.append("HTTP cache deletion requested; Qt will report when it finishes.")
                else:
                    summary.append("HTTP cache deletion was requested; this Qt binding does not report completion.")
        if dialog.clear_cookies:
            self._privacy_manager.cookies.delete_all_cookies()
            summary.append("Cookie deletion requested; Qt provides per-cookie events, not an all-done signal.")
        if dialog.clear_permissions:
            count = self._privacy_manager.reset_permissions()
            summary.append(f"Reset {count} saved permission decision(s) reported by Qt.")
        if summary:
            QMessageBox.information(self, "Browsing data clear requested", "\n\n".join(summary))
            self.status_bar.showMessage("Selected browsing-data operations were submitted.", 5000)

    def toggle_bookmarks_bar(self) -> None:
        """Toggle visibility of the bookmarks bar."""
        visible = self.bookmarks_bar.isHidden()
        self.bookmarks_bar.setVisible(visible)
        if not self._is_private:
            self._settings.setValue("bookmarks_bar_visible", visible)

    def toggle_fullscreen(self) -> None:
        """Toggle window fullscreen mode, preserving previous maximized state."""
        if self.isFullScreen():
            if self._was_maximized:
                self.showMaximized()
            else:
                self.showNormal()
        else:
            self._was_maximized = self.isMaximized()
            self.showFullScreen()

    def zoom_in(self) -> None:
        """Increase the active view's zoom factor by 10% (max 500%)."""
        view = self.tab_manager.current_view()
        if view is not None:
            new_zoom = min(5.0, round(view.zoomFactor() + 0.1, 2))
            view.setZoomFactor(new_zoom)
            self.status_bar.showMessage(f"Zoom: {int(round(new_zoom * 100))}%", 2000)

    def zoom_out(self) -> None:
        """Decrease the active view's zoom factor by 10% (min 25%)."""
        view = self.tab_manager.current_view()
        if view is not None:
            new_zoom = max(0.25, round(view.zoomFactor() - 0.1, 2))
            view.setZoomFactor(new_zoom)
            self.status_bar.showMessage(f"Zoom: {int(round(new_zoom * 100))}%", 2000)

    def reset_zoom(self) -> None:
        """Reset the active view's zoom factor to 100%."""
        view = self.tab_manager.current_view()
        if view is not None:
            view.setZoomFactor(1.0)
            self.status_bar.showMessage("Zoom: 100%", 2000)

    # --------------------------------------------------------------------------
    # Developer Tools Integration
    # --------------------------------------------------------------------------

    def toggle_devtools(self) -> None:
        """Toggle Chromium Developer Tools panel."""
        self.devtools_manager.toggle()

    def open_js_console(self) -> None:
        """Open Developer Tools and focus the inspector panel."""
        if not self.devtools_manager.is_open():
            self.devtools_manager.open()
        self.devtools_panel.setFocus()
        self.status_bar.showMessage("Opened Developer Tools Console", 2000)

    def activate_inspect_element(self) -> None:
        """Activate element inspection and open Developer Tools."""
        view = self.tab_manager.current_view()
        if view is not None:
            view.triggerPageAction(QWebEnginePage.WebAction.InspectElement)
        if not self.devtools_manager.is_open():
            self.devtools_manager.open()
        self.status_bar.showMessage("Inspect Element active", 2000)

    def view_page_source(self) -> None:
        """Open the active tab's HTML source in a new tab using view-source: scheme."""
        view = self.tab_manager.current_view()
        if view is None:
            return

        url_str = view.url().toString()
        if not url_str or url_str == "about:blank":
            url_str = self.address_bar.text().strip()
        if not url_str:
            url_str = self.tab_manager.default_url

        if not url_str.startswith("view-source:"):
            source_url = f"view-source:{url_str}"
        else:
            source_url = url_str

        self.tab_manager.create_tab(url=source_url, activate=True)
        self.status_bar.showMessage("Opening page source in new tab...", 2000)

    def show_about_dialog(self) -> None:
        """Display dialog with actual Chromium engine, Qt, and PySide6 versions."""
        info = get_engine_diagnostics()
        about_text = (
            f"<h3>{info['application_name']} v{info['application_version']}</h3>"
            "<p>A customizable, developer-focused desktop web browser with multiple tabs.</p>"
            "<hr>"
            "<b>Engine & Runtime Specifications:</b><br>"
            f"• <b>Bundled Chromium:</b> v{info['chromium_version']}<br>"
            f"• <b>Qt WebEngine:</b> v{info['qt_version']}<br>"
            f"• <b>PySide6 Framework:</b> v{info['pyside6_version']}<br>"
            f"• <b>Python Runtime:</b> v{info['python_version']}<br>"
            f"• <b>Host Platform:</b> {info['platform']}<br>"
            "<br>"
            "<b>Developer Tools:</b> Built-in Chromium Inspector (F12 / Ctrl+Shift+I)<br>"
            "<b>License:</b> MIT License"
        )
        QMessageBox.about(self, f"About {info['application_name']}", about_text)
