"""Main application window for LightMq Browser.

Coordinates multiple tab management, navigation toolbar, address bar,
stacked WebEngine viewports, status bar, genuine Chromium Developer Tools,
find-in-page, bookmarks bar, and comprehensive keyboard shortcut handling.
"""

import logging
import zipfile
import openpyxl
from pathlib import Path
from PySide6.QtCore import Qt, QUrl, QSettings, QPoint, QSize
from PySide6.QtGui import QAction, QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QFileDialog,
    QDialog,
    QMainWindow,
    QMessageBox,
    QMenu,
    QInputDialog,
    QLabel,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QHBoxLayout,
)
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile

from browser.core.navigation import normalize_url
from browser.core.session_manager import SessionManager
from browser.core.tab_manager import TabManager
from browser.devtools.devtools_manager import DevToolsManager
from browser.devtools.devtools_panel import DevToolsPanel
from browser.features.bookmarks.bookmark_manager import BookmarkManager
from browser.features.downloads.download_manager import DownloadManager
from browser.features.extensions.extension_controller import ExtensionController
from browser.features.extensions.extension_assets import load_extension_icon
from browser.features.extensions.webstore_integration import recognize_webstore_listing
from browser.features.history.history_manager import HistoryManager
from browser.features.recommendations.recommendation_controller import RecommendationController
from browser.features.private_browsing.private_manager import PrivateBrowsingManager
from browser.features.spreadsheets.spreadsheet_viewer import SpreadsheetViewer
from browser.features.privacy.privacy_manager import PrivacyManager
from browser.ui.address_bar import AddressBar
from browser.ui.dialogs.bookmark_dialog import BookmarkDialog
from browser.ui.dialogs.bookmark_manager_dialog import BookmarkManagerDialog
from browser.ui.dialogs.clear_data_dialog import ClearDataDialog
from browser.ui.dialogs.downloads_dialog import DownloadsDialog
from browser.ui.dialogs.history_dialog import HistoryDialog
from browser.ui.dialogs.extensions_dialog import ExtensionsDialog
from browser.ui.dialogs.privacy_settings_dialog import PrivacySettingsDialog
from browser.ui.dialogs.startup_settings_dialog import StartupSettingsDialog
from browser.ui.shortcut_manager import ShortcutManager
from browser.ui.tab_bar import TabBar
from browser.core.tab_group_manager import GROUP_COLORS
from browser.ui.widgets.bookmarks_bar import BookmarksBar
from browser.ui.widgets.find_bar import FindBar
from browser.ui.widgets.notification_toast import NotificationToast
from browser.utils.constants import APP_NAME, DEFAULT_START_URL, get_engine_diagnostics
from browser.storage.session_model import SessionSnapshot
from browser.storage.settings import StartupSettings, BrowserSettings
from browser.ui.settings_window import SettingsWindow
from browser.ui.theme_manager import ThemeManager
from browser.ui.theme_palette import build_palette
from browser.ui.icons.icon_button import IconButton
from browser.ui.icons.icon_manager import IconManager
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
        self._browser_settings = BrowserSettings(self._settings, self)
        self._theme_manager = ThemeManager(self._browser_settings,apply_global=not is_private)
        self._icon_theme = build_palette("#1a73e8", dark=True) if is_private else self._theme_manager.palette()
        self._session_manager = None if is_private else session_manager
        if self._session_manager is not None:
            self._session_manager.document_factory = lambda path: SpreadsheetViewer(path)
        self._private_manager: PrivateBrowsingManager | None = None
        self._startup_settings_dialog: StartupSettingsDialog | None = None
        self._extension_controller: ExtensionController | None = None
        self._recommendation_controller: RecommendationController | None = None

        # Profile initialization
        if self._is_private:
            self._private_manager=PrivateBrowsingManager.get_instance()
            self._profile,self.download_manager=self._private_manager.acquire(self)
            self._privacy_manager: PrivacyManager | None = None
            self._permission_handler=PermissionRequestHandler(self)
            self._permission_handler.permission_requested.connect(self._show_permission_request)
            self._permission_handler.request_cancelled.connect(self._dismiss_permission_request)
            self._base_title = f"{APP_NAME} — Incognito"
        else:
            self._profile = WebProfileManager.default_profile()
            self._extension_controller = ExtensionController.shared_for_profile(
                self._profile, self._settings
            )
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
            self._recommendation_controller = RecommendationController(
                HistoryManager.get_instance(), BookmarkManager.get_instance(),
                self._browser_settings, self,
            )
            self._base_title = APP_NAME

        self.setWindowTitle(self._base_title)
        self.resize(1280, 850)

        self._init_ui()
        if self._is_private:
            self.setStyleSheet("QMainWindow{background:#202124;color:#e8eaed;} QToolBar{background:#292a2d;color:#e8eaed;} QPushButton,QToolButton{background:#303134;color:#e8eaed;border:1px solid #4b4e52;border-radius:5px;padding:4px;} QLineEdit{background:#202124;color:#e8eaed;border:1px solid #5f6368;}")
        self._notification_toast = NotificationToast(self)
        self._init_shortcuts()
        self._browser_settings.changed.connect(self._on_browser_setting_changed)
        self._connect_downloads()

        if self._session_manager is not None:
            self._session_manager.bind(self.tab_manager)
            self._session_manager.save_failed.connect(self._on_session_save_failed)
            self._session_manager.restore_warning.connect(lambda message: self.status_bar.showMessage(message, 8000))

        # Restore before creating a fallback tab so no transient blank tab is saved.
        restored_count = (
            self._session_manager.restore(restore_snapshot)
            if self._session_manager is not None and restore_snapshot is not None
            else 0
        )
        if restored_count == 0:
            start_url=initial_url or ("lightmq://incognito/" if self._is_private else DEFAULT_START_URL)
            self.tab_manager.create_tab(url=start_url, activate=True)

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
        for index, widget in enumerate(self.tab_manager.ordered_views()):
            if isinstance(widget, SpreadsheetViewer) and widget.dirty:
                if not self._close_tab_request(index, force=True):
                    event.ignore(); return
        if self._is_private and self._private_manager is not None and not getattr(self,"_private_close_confirmed",False):
            active=self._private_manager.active_downloads()
            if active and not self._private_manager.has_other_windows(self):
                answer=QMessageBox.question(self,"Close Incognito Session?",f"{len(active)} private download(s) are still active. Closing the final Incognito window will cancel them. Downloaded files already saved will remain on this device. Close anyway?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
                if answer!=QMessageBox.StandardButton.Yes:
                    event.ignore();return
                self._private_close_confirmed=True
                self._private_manager.cancel_active_downloads()
        # Stop picker listeners and restore temporary page edits before the
        # current WebEngine pages and their isolated worlds are torn down.
        self.devtools_manager.close()
        if self._session_manager is not None:
            self._session_manager.finish()
        if self._permission_handler is not None:
            for index in range(self.tab_manager.count()):
                view = self.tab_manager.view_at(index)
                if isinstance(view, WebView):
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
        if self._is_private and self._private_manager is not None and not getattr(self,"_private_released",False):
            views=list(self.tab_manager.ordered_views())
            self.devtools_manager.set_target_view(None)
            self.tab_manager.dispose_all_tabs()
            resources:list[QWidget]=[*views,self.devtools_panel]
            self.devtools_panel.deleteLater()
            self._private_manager.release_window(self,resources)
            self._private_released=True
            self._profile=None
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
        elif self._is_private and hasattr(self,"_download_handler"):
            remaining=next((window for window in MainWindow._all_windows if window.is_private and window.download_manager is self.download_manager),None)
            self._download_handler.set_parent_window(remaining)
        super().closeEvent(event)

    def _connect_downloads(self) -> None:
        """Connect download requests to DownloadManager."""
        self._download_handler = attach_download_handler(
            self._profile, self.download_manager, self, private_session=self._is_private
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
        if self._is_private:
            self.private_banner=QLabel("Incognito — this window won’t save browsing history. Downloads and bookmarks you choose to save remain on this device.",central_widget)
            self.private_banner.setObjectName("incognitoBanner")
            self.private_banner.setWordWrap(True)
            self.private_banner.setStyleSheet("QLabel#incognitoBanner{background:#30343b;color:#f2f3f5;padding:8px 14px;border-bottom:1px solid #4b515a;font-weight:600;}")
            main_layout.addWidget(self.private_banner)
        self.tab_bar = TabBar(central_widget,icon_theme=self._icon_theme if self._is_private else None)
        self.tab_bar.setObjectName("browserTabStrip")
        main_layout.addWidget(self.tab_bar)

        # 2. Tab Manager
        self.tab_manager = TabManager(
            default_url="lightmq://incognito/" if self._is_private else DEFAULT_START_URL,
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
        self.devtools_panel = DevToolsPanel(self.splitter,profile=self._profile)
        panel_position = self._settings.value("devtools/panel_position", "right", type=str)
        self.devtools_panel.position.setCurrentIndex(1 if panel_position == "bottom" else 0)
        self.splitter.setOrientation(Qt.Orientation.Vertical if panel_position == "bottom" else Qt.Orientation.Horizontal)
        self.devtools_panel.position_changed.connect(self._set_devtools_position)
        self.devtools_panel.hide()
        self.splitter.addWidget(self.devtools_panel)

        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)

        # 4. Developer Tools Manager
        self.devtools_manager = DevToolsManager(
            devtools_panel=self.devtools_panel,
            splitter=self.splitter,
            parent=self,
            settings=self._settings,
        )
        self.devtools_panel.open_chromium_requested.connect(self.devtools_manager.open)

        # 5. Navigation Toolbar
        self._build_toolbar()
        main_layout.addWidget(self.toolbar)

        # 6. Bookmarks Bar (Toggled with Ctrl+Shift+B, hidden by default)
        self.bookmarks_bar = BookmarksBar(parent=central_widget,icon_theme=self._icon_theme if self._is_private else None)
        self.bookmarks_bar.open_url_requested.connect(self.navigate_to)
        self.bookmarks_bar.open_new_tab_requested.connect(self._open_bookmark_new_tab)
        self.bookmarks_bar.edit_requested.connect(self.edit_bookmark)
        self.bookmarks_bar.manager_requested.connect(self.open_bookmark_manager)
        self.bookmarks_bar.setVisible(
            not self._is_private and self._settings.value("bookmarks_bar_visible", False, type=bool)
        )
        main_layout.addWidget(self.bookmarks_bar)

        # 7. Find in Page Bar (Toggled with Ctrl+F, hidden by default)
        self.find_bar = FindBar(parent=central_widget,icon_theme=self._icon_theme if self._is_private else None)
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
        self.toolbar.setObjectName("navigationToolbar")
        self.toolbar.setIconSize(QSize(20,20))

        # Back Action
        self.action_back = QAction("Back",self)
        self.action_back.setToolTip("Back (Alt+Left)")
        self.action_back.setEnabled(False)
        self.action_back.triggered.connect(self.back)
        self._add_toolbar_action(self.action_back, "arrow-left")

        # Forward Action
        self.action_forward = QAction("Forward",self)
        self.action_forward.setToolTip("Forward (Alt+Right)")
        self.action_forward.setEnabled(False)
        self.action_forward.triggered.connect(self.forward)
        self._add_toolbar_action(self.action_forward, "arrow-right")

        # Reload Action
        self.action_reload = QAction("Reload",self)
        self.action_reload.setToolTip("Reload (Ctrl+R / F5)")
        self.action_reload.triggered.connect(self.reload)
        self._add_toolbar_action(self.action_reload, "reload")

        # Stop Action
        self.action_stop = QAction("Stop loading",self)
        self.action_stop.setToolTip("Stop (Esc)")
        self.action_stop.triggered.connect(self.stop)
        self.action_stop.setVisible(False)
        self._add_toolbar_action(self.action_stop, "stop")

        self.action_home=QAction("Home",self);self.action_home.setToolTip("Home (Alt+Home)");self.action_home.triggered.connect(self.home)
        self._add_toolbar_action(self.action_home, "home")

        # Address Bar
        self.address_bar = AddressBar(self,icon_theme=self._icon_theme if self._is_private else None)
        self.address_bar.navigate_requested.connect(self.navigate_to)
        self.toolbar.addWidget(self.address_bar)

        self.btn_bookmark = IconButton("bookmark", "Bookmark this page (Ctrl+D)", self,theme=self._icon_theme if self._is_private else None)
        self.btn_bookmark.clicked.connect(self.open_bookmark_editor)
        self.toolbar.addWidget(self.btn_bookmark)
        self.btn_saved_bookmarks=IconButton("chevron-down", "Open saved bookmarks", self, button_size=28, icon_size=15,theme=self._icon_theme if self._is_private else None)
        self.btn_saved_bookmarks.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_saved_bookmarks.setVisible(True)
        self.saved_bookmarks_menu=QMenu(self.btn_saved_bookmarks)
        self.btn_saved_bookmarks.setMenu(self.saved_bookmarks_menu)
        self.toolbar.addWidget(self.btn_saved_bookmarks)
        bookmark_manager=BookmarkManager.get_instance()
        bookmark_manager.bookmarks_changed.connect(
            lambda: self._update_bookmark_button(self.web_view.url().toString()) if self.web_view else None
        )
        bookmark_manager.bookmarks_changed.connect(self._refresh_saved_bookmarks_menu)
        self._refresh_saved_bookmarks_menu()

        # Keep Enter as the primary navigation action; the old button remains
        # addressable for callers but is removed from the compact toolbar.
        self.btn_go = QPushButton("Go", self)
        self.btn_go.setToolTip("Navigate to URL")
        self.btn_go.clicked.connect(self._on_go_clicked)
        self.btn_go.hide()

        self.btn_devtools = IconButton("devtools", "Toggle Chromium Developer Tools (F12)", self,theme=self._icon_theme if self._is_private else None)
        self.btn_devtools.setCheckable(True)
        self.btn_devtools.clicked.connect(self.toggle_devtools)
        self.toolbar.addWidget(self.btn_devtools)
        self.btn_select_element = IconButton("select-element", "Select webpage element (Ctrl+Shift+C)", self, theme=self._icon_theme if self._is_private else None)
        self.btn_select_element.clicked.connect(self.activate_inspect_element)
        self.toolbar.addWidget(self.btn_select_element)
        if self._extension_controller is not None:
            self.btn_extensions = IconButton(
                "extensions", "Extensions", self, theme=self._icon_theme
            )
            self.extensions_action_menu = QMenu(self.btn_extensions)
            self.btn_extensions.setMenu(self.extensions_action_menu)
            self.btn_extensions.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            self.toolbar.addWidget(self.btn_extensions)
            self._extension_controller.extensions_changed.connect(
                self._refresh_extensions_menu
            )
            self._refresh_extensions_menu()
        self.btn_downloads = IconButton("download", "Open Download Manager (Ctrl+J)", self,theme=self._icon_theme if self._is_private else None)
        self.btn_downloads.clicked.connect(self.open_downloads)
        self.toolbar.addWidget(self.btn_downloads)
        self.btn_settings=IconButton("settings","LightMq Settings",self,theme=self._icon_theme if self._is_private else None);self.btn_settings.clicked.connect(self.open_settings)
        self.toolbar.addWidget(self.btn_settings)

        self.btn_profile=IconButton("profile","LightMq local browser profile",self,button_size=36,icon_size=20,theme=self._icon_theme if self._is_private else None);self.btn_profile.setObjectName("profileButton")
        self.profile_menu=QMenu(self.btn_profile)
        profile_action=self._add_menu_action(self.profile_menu,"LightMq browser profile",None,"profile");profile_action.setEnabled(False)
        self.profile_menu.addSeparator();self._add_menu_action(self.profile_menu,"Open Incognito Window",self.new_private_window,"incognito")
        if not self._is_private:self._add_menu_action(self.profile_menu,"Browser settings…",self.open_settings,"settings")
        self.btn_profile.setMenu(self.profile_menu);self.btn_profile.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup);self.toolbar.addWidget(self.btn_profile)

        browser_menu=QMenu(self)
        self._add_menu_action(browser_menu,"Open File…\tCtrl+O",self.open_file,"folder")
        self._add_menu_action(browser_menu,"New Tab\tCtrl+T",self.new_tab,"plus")
        self._add_menu_action(browser_menu,"New Window\tCtrl+N",self.new_window,"new-window")
        self._add_menu_action(browser_menu,"New Incognito Window\tCtrl+Shift+N",self.new_private_window,"incognito")
        browser_menu.addSeparator()
        self._add_menu_action(browser_menu,"History\tCtrl+H",self.open_history,"history")
        self._add_menu_action(browser_menu,"Downloads\tCtrl+J",self.open_downloads,"download")
        if self._extension_controller is not None:
            extension_menu = browser_menu.addMenu("Extensions")
            IconManager.set_action_icon(
                extension_menu.menuAction(), "extensions", 18, self._icon_theme
            )
            self._add_menu_action(
                extension_menu,
                "Manage Extensions…",
                self.open_extensions_manager,
                "settings",
            )
        bookmarks_menu=browser_menu.addMenu("Bookmarks")
        IconManager.set_action_icon(bookmarks_menu.menuAction(),"bookmarks",18,self._icon_theme if self._is_private else None)
        self._populate_bookmark_actions(bookmarks_menu)
        if not self._is_private:self._add_menu_action(bookmarks_menu,"Manage bookmarks…",self.open_bookmark_manager,"settings")
        self._add_menu_action(browser_menu,"Show bookmarks bar\tCtrl+Shift+B",self.toggle_bookmarks_bar,"bookmarks")
        group_menu=browser_menu.addMenu("Tab Groups")
        IconManager.set_action_icon(group_menu.menuAction(),"groups",18,self._icon_theme if self._is_private else None)
        self._add_menu_action(group_menu,"Create group for active tab…",lambda:self._create_group_for(self.tab_manager.current_view()) if self.tab_manager.current_view() else None,"plus")
        self._add_menu_action(group_menu,"Remove active tab from group",lambda:self.tab_manager.remove_tab_from_group(self.tab_manager.current_view()) if self.tab_manager.current_view() else None,"close")
        browser_menu.addSeparator()
        zoom_widget=QWidget(self);zoom_row=QHBoxLayout(zoom_widget);zoom_row.setContentsMargins(8,2,8,2)
        zoom_minus=IconButton("zoom-out","Zoom out",zoom_widget,button_size=28,icon_size=17,theme=self._icon_theme if self._is_private else None);zoom_minus.clicked.connect(self.zoom_out);self.zoom_percent=QLabel("100%",zoom_widget);self.zoom_percent.setMinimumWidth(48);self.zoom_percent.setAlignment(Qt.AlignmentFlag.AlignCenter)
        zoom_reset=IconButton("zoom-reset","Reset zoom",zoom_widget,button_size=28,icon_size=17,theme=self._icon_theme if self._is_private else None);zoom_reset.clicked.connect(self.reset_zoom);zoom_plus=IconButton("zoom-in","Zoom in",zoom_widget,button_size=28,icon_size=17,theme=self._icon_theme if self._is_private else None);zoom_plus.clicked.connect(self.zoom_in)
        zoom_row.addWidget(QLabel("Zoom",zoom_widget));zoom_row.addStretch();zoom_row.addWidget(zoom_minus);zoom_row.addWidget(self.zoom_percent);zoom_row.addWidget(zoom_plus);zoom_row.addWidget(zoom_reset)
        zoom_action=QWidgetAction(browser_menu);zoom_action.setDefaultWidget(zoom_widget);browser_menu.addAction(zoom_action)
        self._add_menu_action(browser_menu,"Print…\tCtrl+P",self.print_current_page,"print")
        self._add_menu_action(browser_menu,"Find in page…\tCtrl+F",self.open_find_in_page,"search")
        browser_menu.addSeparator()
        self._add_menu_action(browser_menu,"Appearance & Themes",lambda:(self.open_settings(),self._settings_window.sidebar.setCurrentRow(1)),"palette")
        self._add_menu_action(browser_menu,"Settings",self.open_settings,"settings")
        self._add_menu_action(browser_menu,"Developer Tools\tF12",self.toggle_devtools,"devtools")
        self._add_menu_action(browser_menu,"Select Element\tCtrl+Shift+C",self.activate_inspect_element,"select-element")
        if not self._is_private:
            self._add_menu_action(browser_menu,"Privacy & Security",self.open_privacy_settings,"shield")
            self._add_menu_action(browser_menu,"Startup settings",self.open_startup_settings,"tabs")
        browser_menu.addSeparator();self._add_menu_action(browser_menu,"Help",self.show_about_dialog,"help");self._add_menu_action(browser_menu,"About LightMq",self.show_about_dialog,"profile")
        browser_menu.addSeparator();self._add_menu_action(browser_menu,"Exit",self.close,"exit")
        self.btn_browser_menu=IconButton("menu","LightMq menu",self,button_size=36,icon_size=20,theme=self._icon_theme if self._is_private else None)
        self.btn_browser_menu.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup);self.btn_browser_menu.setMenu(browser_menu)
        self.toolbar.addWidget(self.btn_browser_menu)

        # Synchronize DevTools button state
        self.devtools_manager.visibility_changed.connect(self.btn_devtools.setChecked)

        # Legacy controls retain their slots for integrations but move into menu.
        self.btn_about = QPushButton("About", self)
        self.btn_about.setToolTip("View browser and Chromium engine specifications")
        self.btn_about.clicked.connect(self.show_about_dialog)
        self.btn_about.hide()

        if not self._is_private:
            self.btn_privacy = QPushButton("Privacy", self)
            self.btn_privacy.setToolTip("Manage cookies, permissions, cache, and browsing data")
            self.btn_privacy.clicked.connect(self.open_privacy_settings)
            self.btn_privacy.hide()

            self.btn_startup_settings = QPushButton("Startup", self)
            self.btn_startup_settings.setToolTip("Choose what LightMq opens at startup")
            self.btn_startup_settings.clicked.connect(self.open_startup_settings)
            self.btn_startup_settings.hide()

    def _add_toolbar_action(self, action: QAction, icon_name: str) -> None:
        """Add a theme-aware action and normalize its generated toolbar button."""
        IconManager.set_action_icon(action, icon_name, 20,self._icon_theme if self._is_private else None)
        self.toolbar.addAction(action)
        button = self.toolbar.widgetForAction(action)
        if isinstance(button, QToolButton):
            button.setProperty("lightmqIconButton", True)
            button.setIconSize(QSize(20, 20))
            button.setFixedSize(36, 36)
            button.style().unpolish(button)
            button.style().polish(button)

    def _add_menu_action(self, menu: QMenu, text: str, callback, icon_name: str | None = None) -> QAction:
        """Create a menu action and attach a matching registered SVG icon."""
        action = menu.addAction(text)
        if callback is not None:
            action.triggered.connect(callback)
        if icon_name:
            IconManager.set_action_icon(action, icon_name, 18,self._icon_theme if self._is_private else None)
        return action

    def _populate_bookmark_actions(self,menu:QMenu)->None:
        """Add existing bookmark folders and pages to a native menu."""
        manager=BookmarkManager.get_instance();count=0
        def add_children(target:QMenu,parent_id:int)->None:
            nonlocal count
            for item in manager.children(parent_id):
                if item.is_folder:
                    nested=target.addMenu(item.title);IconManager.set_action_icon(nested.menuAction(),"folder",18,self._icon_theme if self._is_private else None);add_children(nested,item.id)
                elif item.url:
                    self._add_menu_action(target,item.title,lambda _checked=False,url=item.url:self.navigate_to(url),"bookmark")
                    count+=1
        for root in manager.roots():
            folder=menu.addMenu(root.title)
            IconManager.set_action_icon(folder.menuAction(),"folder",18,self._icon_theme if self._is_private else None)
            add_children(folder,root.id)
        if not count:
            empty=menu.addAction("No saved bookmarks yet");empty.setEnabled(False)
        menu.addSeparator()
        self._add_menu_action(menu,"Bookmark this page…",self.open_bookmark_editor,"bookmark")

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
        self.tab_manager.tab_order_changed.connect(self._sync_tab_order)
        self.tab_bar.tab_list_requested.connect(self._show_tab_list)
        self.tab_manager.group_manager.groups_changed.connect(self._sync_group_headers)
        self.tab_manager.group_manager.group_changed.connect(lambda _group_id: self._sync_group_headers())
        self.tab_manager.state_changed.connect(self._sync_group_visibility)

        self.tab_bar.tab_close_requested.connect(self._close_tab_request)
        self.tab_bar.current_changed.connect(self.tab_manager.set_current_index)
        self.tab_bar.new_tab_requested.connect(self.new_tab)
        self.tab_bar.tab_moved.connect(self.tab_manager.move_tab)
        self.tab_bar.tab_context_requested.connect(self._show_tab_context_menu)
        self.tab_bar.group_context_requested.connect(self._show_group_context_menu)
        self.tab_bar.group_toggle_requested.connect(self._toggle_group)
        self.tab_bar.group_reorder_requested.connect(self.tab_manager.reorder_group)

    def _init_shortcuts(self) -> None:
        """Register all default keyboard shortcuts through the ShortcutManager."""
        self.shortcut_manager = ShortcutManager(self)
        self.shortcut_manager.register_all_default_shortcuts()

    # --------------------------------------------------------------------------
    # TabManager Event Handlers
    # --------------------------------------------------------------------------

    def _on_tab_created(self, index: int, view: QWidget) -> None:
        """Handle new tab creation: add to stacked widget and connect WebEngine signals."""
        if isinstance(view, SpreadsheetViewer):
            self.stacked_widget.insertWidget(index, view)
            tab_id = self.tab_manager.tab_id_for(view) or ""
            self.tab_bar.insert_tab(index, view.title(), view.icon())
            self.tab_bar.set_tab_id(index, tab_id)
            self.tab_bar.set_pinned(index, self.tab_manager.is_pinned(view))
            view.titleChanged.connect(lambda title, v=view: self._on_document_title_changed(v, title))
            view.urlChanged.connect(lambda url, v=view: self._on_document_url_changed(v, url))
            self._sync_group_headers(); self._sync_group_visibility()
            return
        view.set_pdf_viewer_enabled(self._browser_settings.pdf_open_in_browser())
        view.setZoomFactor(self._browser_settings.default_zoom())
        context_view = self.tab_manager.current_view()
        context_url = context_view.url().toString() if isinstance(context_view, WebView) else ""
        context_title = context_view.title() if isinstance(context_view, WebView) else ""
        if context_url.startswith(("lightmq:", "file:", "about:")) or (isinstance(context_view, WebView) and context_view.page().is_pdf_document()):
            context_url = ""; context_title = ""
        view.configure_start_page(
            self._browser_settings.store, self._browser_settings.search_template(),
            self._theme_manager.palette(), self._is_private,
            recommendations=self._recommendation_controller,
            context_url=context_url, context_title=context_title,
        )
        if not self._is_private:
            view._new_tab_bridge.openRecommendationRequested.connect(self._open_newtab_recommendation)
        self.stacked_widget.insertWidget(index, view)
        tab_id = self.tab_manager.tab_id_for(view) or ""
        self.tab_bar.insert_tab(index, getattr(view, "restored_title", "") or "New Tab", view.icon())
        self.tab_bar.set_tab_id(index, tab_id)
        self.tab_bar.set_pinned(index, self.tab_manager.is_pinned(view))
        self._sync_group_headers()
        self._sync_group_visibility()

        # Connect signals for independent tab state updates
        view.titleChanged.connect(lambda title, v=view: self._on_tab_title_changed(v, title))
        view.iconChanged.connect(lambda icon, v=view: self._on_tab_icon_changed(v, icon))
        view.urlChanged.connect(lambda url, v=view: self._on_tab_url_changed(v, url))
        view.loadStarted.connect(lambda v=view: self._on_tab_load_started(v))
        view.loadProgress.connect(lambda prog, v=view: self._on_tab_load_progress(v, prog))
        view.loadFinished.connect(lambda ok, v=view: self._on_tab_load_finished(v, ok))
        view.page().pdf_document_changed.connect(
            lambda is_pdf, v=view: self._pdf_document_state_changed(v, is_pdf)
        )
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
        if not isinstance(view, WebView):
            return
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
        self._sync_group_headers()

    def _on_current_tab_changed(self, index: int, view: QWidget) -> None:
        """Switch active tab: update UI, toolbar, address bar, find bar, and DevTools."""
        self.tab_bar.set_current_index(index)
        self.stacked_widget.setCurrentWidget(view)
        self._refresh_extensions_menu()

        if isinstance(view, SpreadsheetViewer):
            self.devtools_manager.set_target_view(None)
            self.find_bar.close_and_clear()
            self.address_bar.set_url(view.url())
            self._update_bookmark_button("")
            self.setWindowTitle(f"{view.title()} - {self._base_title}")
            self.action_back.setEnabled(False); self.action_forward.setEnabled(False)
            self.action_reload.setEnabled(False); self.action_stop.setVisible(False)
            self.progress_bar.hide(); self._refresh_zoom_label()
            return

        # Attach DevTools to the new active page
        self.devtools_manager.set_target_view(None if view.page().is_pdf_document() else view)
        self.action_reload.setEnabled(True)

        # Synchronize find bar with newly active tab
        self.find_bar.set_active_view(view)

        # Update address bar and title for the newly active tab
        current_url = view.url()
        self.address_bar.set_url(current_url)
        self._update_bookmark_button(current_url.toString())
        self._sync_pdf_find_shortcut(view)

        title = view.page().pdf_display_title() or view.title()
        if title:
            self.setWindowTitle(f"{title} - {self._base_title}")
        else:
            self.setWindowTitle(self._base_title)

        # Update navigation controls for active tab
        self._update_navigation_actions(view)
        self._sync_loading_controls(view)
        self._refresh_zoom_label()

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
        """Synchronize widgets after model normalization of a drag."""
        self._sync_tab_order()

    def _sync_tab_order(self) -> None:
        """Make both UI collections reflect the manager's stable-ID order."""
        views = list(self.tab_manager.ordered_views())
        ids = [self.tab_manager.tab_id_for(view) or "" for view in views]
        self.tab_bar.sync_order(ids)
        for index, view in enumerate(views):
            self.stacked_widget.removeWidget(view)
            self.stacked_widget.insertWidget(index, view)
        active = self.tab_manager.current_view()
        if active is not None:
            self.stacked_widget.setCurrentWidget(active)
            self.tab_bar.set_current_index(self.tab_manager.index_of(active))
        for index, view in enumerate(views):
            self.tab_bar.set_pinned(index, self.tab_manager.is_pinned(view))

    def _show_tab_list(self)->None:
        """Open a searchable list of live and recently closed tabs."""
        menu=QMenu(self);self._tab_list_menu=menu;menu.setMinimumWidth(360)
        panel=QWidget(menu);layout=QVBoxLayout(panel);layout.setContentsMargins(8,8,8,8)
        search=QLineEdit(panel);search.setPlaceholderText("Search open and recently closed tabs");layout.addWidget(search)
        rows=QListWidget(panel);rows.setMinimumHeight(300);layout.addWidget(rows)
        for index,view in enumerate(self.tab_manager.ordered_views()):
            title=view.title() or "New Tab";url=view.url().toString()
            item=QListWidgetItem(f"{title}\n{url}");item.setToolTip(url);item.setData(Qt.ItemDataRole.UserRole,("open",index));rows.addItem(item)
        closed=self.tab_manager.tab_history.items()
        if closed:
            marker=QListWidgetItem("Recently closed");marker.setFlags(Qt.ItemFlag.NoItemFlags);marker.setData(Qt.ItemDataRole.UserRole,("header",None));rows.addItem(marker)
            for closed_tab in closed:
                item=QListWidgetItem(f"{closed_tab.title or 'Recently closed tab'}\n{closed_tab.url.toString()}")
                item.setToolTip(closed_tab.url.toString());item.setData(Qt.ItemDataRole.UserRole,("closed",closed_tab));rows.addItem(item)
        search.textChanged.connect(lambda text:[rows.item(i).setHidden(text.casefold() not in (rows.item(i).text()+" "+rows.item(i).toolTip()).casefold()) for i in range(rows.count()) if rows.item(i).data(Qt.ItemDataRole.UserRole)[0]!="header"])
        def select(item:QListWidgetItem)->None:
            kind,value=item.data(Qt.ItemDataRole.UserRole)
            if kind=="open":self.tab_manager.set_current_index(value)
            elif kind=="closed":self.tab_manager.restore_closed_tab(value)
            menu.close()
        rows.itemClicked.connect(select)
        action=QWidgetAction(menu);action.setDefaultWidget(panel);menu.addAction(action)
        menu.popup(self.tab_bar.tab_list_button.mapToGlobal(self.tab_bar.tab_list_button.rect().bottomLeft()))

    def _sync_group_headers(self) -> None:
        groups = self.tab_manager.group_manager.groups()
        self.tab_bar.set_groups(groups)
        self._sync_group_visibility()

    def _sync_group_visibility(self) -> None:
        for index, view in enumerate(self.tab_manager.ordered_views()):
            self.tab_bar.set_tab_visible(index, self.tab_manager.is_tab_visible(view))

    def _toggle_group(self, group_id: str) -> None:
        group = self.tab_manager.group_manager.group(group_id)
        if group:
            self.tab_manager.collapse_group(group_id, not group.collapsed)

    def _show_tab_context_menu(self, index: int, global_pos: QPoint) -> None:
        view = self.tab_manager.view_at(index)
        if view is None:
            return
        menu = QMenu(self)
        self._add_menu_action(menu,"New Tab",self.new_tab,"plus")
        if isinstance(view, WebView): self._add_menu_action(menu,"Reload",view.reload,"reload")
        if isinstance(view, WebView): self._add_menu_action(menu,"Duplicate Tab",lambda: self.tab_manager.duplicate_tab(self.tab_manager.index_of(view)),"new-window")
        pinned = self.tab_manager.is_pinned(view)
        self._add_menu_action(menu,"Unpin Tab" if pinned else "Pin Tab",lambda: self._toggle_pin(view),"pin")
        group = self.tab_manager.group_manager.group_for_tab(self.tab_manager.tab_id_for(view))
        group_menu = menu.addMenu("Add Tab to Group")
        IconManager.set_action_icon(group_menu.menuAction(),"groups",18,self._icon_theme if self._is_private else None)
        group_menu.setEnabled(not pinned)
        self._add_menu_action(group_menu,"New Group…",lambda: self._create_group_for(view),"plus")
        if self.tab_manager.group_manager.groups():
            group_menu.addSeparator()
        for item in self.tab_manager.group_manager.groups():
            self._add_menu_action(group_menu,item.name,lambda _checked=False, gid=item.id, v=view: self.tab_manager.add_tab_to_group(v, gid),"groups")
        remove = self._add_menu_action(menu,"Remove from Group",lambda: self.tab_manager.remove_tab_from_group(view),"close")
        remove.setEnabled(group is not None)
        menu.addSeparator()
        reopen = self._add_menu_action(menu,"Reopen Closed Tab",self.restore_closed_tab,"history")
        reopen.setEnabled(self.tab_manager.closed_tabs_count() > 0)
        self._add_menu_action(menu,"Close Tab",lambda: self._close_tab_request(self.tab_manager.index_of(view), force=True),"close")
        self._add_menu_action(menu,"Close Other Tabs",lambda: self._close_many_tabs(self.tab_manager.index_of(view), "other"),"tabs")
        self._add_menu_action(menu,"Close Tabs to the Right",lambda: self._close_many_tabs(self.tab_manager.index_of(view), "right"),"arrow-right")
        menu.exec(global_pos)

    def _toggle_pin(self, view: WebView) -> None:
        if self.tab_manager.is_pinned(view):
            self.tab_manager.unpin_tab(view)
        else:
            self.tab_manager.pin_tab(view)
        self._sync_tab_order()

    def _create_group_for(self, view: WebView) -> None:
        name, accepted = QInputDialog.getText(self, "New Tab Group", "Group name:")
        if not accepted or not name.strip():
            return
        color_menu = QMenu(self)
        for color in GROUP_COLORS:
            color_menu.addAction(color.title(), lambda _checked=False, c=color: self.tab_manager.create_group(name, c, view))
        color_menu.exec(self.mapToGlobal(self.rect().center()))

    def _show_group_context_menu(self, group_id: str, global_pos: QPoint) -> None:
        group = self.tab_manager.group_manager.group(group_id)
        if group is None:
            return
        menu = QMenu(self)
        self._add_menu_action(menu,"Rename Group…",lambda: self._rename_group(group_id),"edit")
        colors = menu.addMenu("Change Color")
        IconManager.set_action_icon(colors.menuAction(),"palette",18,self._icon_theme if self._is_private else None)
        for color in GROUP_COLORS:
            colors.addAction(color.title(), lambda _checked=False, c=color: self.tab_manager.group_manager.set_color(group_id, c))
        self._add_menu_action(menu,"Expand Group" if group.collapsed else "Collapse Group",lambda: self.tab_manager.collapse_group(group_id, not group.collapsed),"chevron-right" if group.collapsed else "chevron-down")
        self._add_menu_action(menu,"New Tab in Group",lambda: self.tab_manager.create_tab(DEFAULT_START_URL, group_id=group_id),"plus")
        self._add_menu_action(menu,"Ungroup",lambda: self.tab_manager.ungroup(group_id),"groups")
        menu.addSeparator()
        close = self._add_menu_action(menu,"Close Group",lambda: self._close_group(group_id),"close")
        close.setEnabled(bool(group.tab_ids))
        menu.exec(global_pos)

    def _rename_group(self, group_id: str) -> None:
        group = self.tab_manager.group_manager.group(group_id)
        if group is None:
            return
        name, accepted = QInputDialog.getText(self, "Rename Tab Group", "Group name:", text=group.name)
        if accepted and name.strip():
            self.tab_manager.group_manager.rename_group(group_id, name)

    def _close_group(self, group_id: str) -> None:
        group = self.tab_manager.group_manager.group(group_id)
        if group is None:
            return
        if len(group.tab_ids) > 1 and QMessageBox.question(self, "Close Tab Group", f"Close all {len(group.tab_ids)} tabs in ‘{group.name}’?") != QMessageBox.StandardButton.Yes:
            return
        for tab_id in tuple(group.tab_ids):
            target = self.tab_manager.view_for_tab_id(tab_id)
            if target is not None and not self._close_tab_request(self.tab_manager.index_of(target), force=True):
                return

    # --------------------------------------------------------------------------
    # WebEngine Event Handlers (Dispatched with view context)
    # --------------------------------------------------------------------------

    def _on_tab_title_changed(self, view: WebView, title: str) -> None:
        """Update tab label and, if active, update the window title."""
        display_title = view.page().pdf_display_title() or title
        idx = self.tab_manager.index_of(view)
        if idx != -1:
            self.tab_bar.set_tab_title(idx, display_title or "New Tab")

        if view is self.tab_manager.current_view():
            if display_title:
                self.setWindowTitle(f"{display_title} - {self._base_title}")
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
        if view is self.tab_manager.current_view() and not self._is_private:
            item=BookmarkManager.get_instance().find_by_url(view.url().toString())
            if item:
                reference=view.iconUrl().toString()
                if reference:BookmarkManager.get_instance().set_favicon(item.id,reference)

    def _on_tab_url_changed(self, view: WebView, url: QUrl) -> None:
        """Update tab tooltip and, if active, update the address bar."""
        idx = self.tab_manager.index_of(view)
        if idx != -1:
            self.tab_bar.set_tab_tooltip(idx, url.toString())

        if view is self.tab_manager.current_view():
            self.address_bar.set_url(url)
            self._update_bookmark_button(url.toString())
            self._update_navigation_actions(view)
            self._refresh_extensions_menu()

    def _on_tab_load_started(self, view: WebView) -> None:
        """Record loading state."""
        self._loading_states[view] = 0
        if view is self.tab_manager.current_view():
            self._sync_loading_controls(view)
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
            self._sync_loading_controls(view)

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

    def _sync_loading_controls(self,view:WebView|None)->None:
        """Show Stop only while the active tab has an outstanding load."""
        loading=view is not None and view in self._loading_states
        self.action_reload.setVisible(not loading)
        self.action_stop.setVisible(loading)

    def _refresh_zoom_label(self)->None:
        """Keep the menu zoom percentage in sync with the selected tab."""
        view=self.tab_manager.current_view()
        if hasattr(self,"zoom_percent"):
            self.zoom_percent.setText(f"{int(round(view.zoomFactor()*100)) if isinstance(view, WebView) else 100}%")

    def navigate_to(self, text: str) -> None:
        """Instruct the active tab to navigate to the normalized target URL."""
        active_view = self.tab_manager.current_view()
        if active_view is not None:
            value = text.strip()
            explicit_scheme = value.lower().startswith(("http://", "https://", "file://", "about:", "lightmq:"))
            looks_url = explicit_scheme or (
                " " not in value
                and ("." in value or value.startswith(("localhost", "127.0.0.1", "[")))
            )
            target_url = normalize_url(value) if looks_url else QUrl(self._browser_settings.search_url(value))
            if isinstance(active_view, SpreadsheetViewer):
                self.tab_manager.create_tab(url=target_url, activate=True)
                return
            self.status_bar.showMessage(f"Navigating to {target_url.toString()}...", 2000)
            active_view.navigate(target_url)

    def open_pdf_file(self) -> WebView | None:
        """Open a validated local PDF in a new tab using a file URL."""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Open File",
            "",
            "PDF documents (*.pdf);;All files (*)",
        )
        if not filename:
            return None
        path = Path(filename).expanduser()
        try:
            path = path.resolve(strict=True)
            if not path.is_file():
                raise OSError("The selected path is not a file.")
            with path.open("rb") as source:
                signature = source.read(1024)
        except OSError as exc:
            QMessageBox.warning(self, "Could not open PDF", f"The selected file cannot be read.\n\n{exc}")
            return None
        if b"%PDF-" not in signature:
            QMessageBox.warning(
                self,
                "Invalid PDF",
                "The selected file does not have a valid PDF header.",
            )
            return None
        view = self.tab_manager.create_tab(QUrl.fromLocalFile(str(path)), activate=True)
        self.status_bar.showMessage(f"Opened {path.name}", 3000)
        return view

    def open_file(self) -> QWidget | None:
        """Open a supported local PDF or .xlsx document in a new tab."""
        filename, _ = QFileDialog.getOpenFileName(self, "Open File", "", "Supported documents (*.pdf *.xlsx);;PDF documents (*.pdf);;Excel workbooks (*.xlsx)")
        if not filename: return None
        return self.open_local_document(filename)

    def open_local_document(self, filename: str) -> QWidget | None:
        """Open a validated local document from a dialog or command line."""
        if Path(filename).suffix.lower() == ".xlsx":
            try:
                viewer = SpreadsheetViewer(Path(filename).expanduser())
            except (OSError, ValueError, zipfile.BadZipFile, openpyxl.utils.exceptions.InvalidFileException) as exc:
                QMessageBox.warning(self, "Could not open workbook", str(exc)); return None
            self.tab_manager.create_document_tab(viewer, viewer.url(), viewer.title(), activate=True)
            self.status_bar.showMessage(f"Opened {Path(filename).name}", 3000)
            return viewer
        if Path(filename).suffix.lower() == ".pdf":
            path = Path(filename).expanduser()
            try:
                path = path.resolve(strict=True)
                with path.open("rb") as source: signature = source.read(1024)
            except OSError as exc:
                QMessageBox.warning(self, "Could not open PDF", f"The selected file cannot be read.\n\n{exc}"); return None
            if b"%PDF-" not in signature:
                QMessageBox.warning(self, "Invalid PDF", "The selected file does not have a valid PDF header."); return None
            return self.tab_manager.create_tab(QUrl.fromLocalFile(str(path)), activate=True)
        QMessageBox.information(self, "Unsupported file", "LightMq opens PDF and .xlsx files.")
        return None

    def _on_document_title_changed(self, view: SpreadsheetViewer, title: str) -> None:
        index = self.tab_manager.index_of(view)
        if index >= 0:
            self.tab_bar.set_tab_title(index, title)
            if view is self.tab_manager.current_view(): self.setWindowTitle(f"{title} - {self._base_title}")

    def _on_document_url_changed(self, view: SpreadsheetViewer, url: QUrl) -> None:
        if view is self.tab_manager.current_view(): self.address_bar.set_url(url)

    def _close_tab_request(self, index: int, force: bool = False) -> bool:
        """Ask before discarding an edited workbook, then close the tab."""
        view = self.tab_manager.view_at(index)
        if isinstance(view, SpreadsheetViewer) and view.dirty:
            box = QMessageBox(self); box.setWindowTitle("Unsaved workbook changes")
            box.setText(f"Save changes to {view.path.name} before closing?")
            save = box.addButton("Save", QMessageBox.ButtonRole.AcceptRole)
            discard = box.addButton("Discard", QMessageBox.ButtonRole.DestructiveRole)
            cancel = box.addButton(QMessageBox.StandardButton.Cancel)
            box.exec()
            if box.clickedButton() is cancel: return False
            if box.clickedButton() is save and not view.save_as(): return False
            if box.clickedButton() not in (save, discard): return False
        return self.tab_manager.close_tab(index, force=force)

    def _close_many_tabs(self, index: int, direction: str) -> int:
        keep = self.tab_manager.view_at(index)
        ordered = list(self.tab_manager.ordered_views())
        targets = ([item for item in ordered if item is not keep and not self.tab_manager.is_pinned(item)]
                   if direction == "other" else [item for item in ordered[index + 1:] if not self.tab_manager.is_pinned(item)])
        count = 0
        for item in targets:
            if not self._close_tab_request(self.tab_manager.index_of(item), force=True): break
            count += 1
        if keep is not None: self.tab_manager.set_current_index(self.tab_manager.index_of(keep))
        return count

    def _pdf_document_state_changed(self, view: WebView, is_pdf: bool) -> None:
        """Let native PDF search receive Ctrl+F while a PDF tab is active."""
        self._on_tab_title_changed(view, view.title())
        if view is self.tab_manager.current_view():
            self.devtools_manager.set_target_view(None if is_pdf else view)
            if is_pdf:
                self.find_bar.close_and_clear()
            self._sync_pdf_find_shortcut(view)

    def _sync_pdf_find_shortcut(self, view: WebView | None) -> None:
        """Yield Ctrl+F to Qt's PDF viewer for PDF tabs; keep webpage find UI otherwise."""
        manager = getattr(self, "shortcut_manager", None)
        if manager is not None:
            manager.set_action_enabled(
                "open_find_in_page",
                not (isinstance(view, WebView) and view.page().is_pdf_document()),
            )

    def back(self) -> None:
        """Navigate back on the active tab."""
        view = self.tab_manager.current_view()
        if isinstance(view, WebView):
            view.back()

    def forward(self) -> None:
        """Navigate forward on the active tab."""
        view = self.tab_manager.current_view()
        if isinstance(view, WebView):
            view.forward()

    def reload(self) -> None:
        """Reload the active tab."""
        view = self.tab_manager.current_view()
        if isinstance(view, WebView):
            view.reload()

    def reload_bypass_cache(self) -> None:
        """Reload the active tab while bypassing cached resources."""
        view = self.tab_manager.current_view()
        if isinstance(view, WebView):
            view.triggerPageAction(QWebEnginePage.WebAction.ReloadAndBypassCache)
            self.status_bar.showMessage("Reloading (bypassing cache)...", 2000)

    def stop(self) -> None:
        """Stop loading on the active tab."""
        view = self.tab_manager.current_view()
        if isinstance(view, WebView):
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
        if self._is_private:
            return self.tab_manager.create_tab("lightmq://incognito/", activate=True)
        behavior = str(self._browser_settings.get("general/new_tab_behavior", "LightMq Start Page"))
        url = "about:blank" if behavior == "Blank Page" else self._startup_settings.homepage() if behavior == "Homepage" else DEFAULT_START_URL
        return self.tab_manager.create_tab(url, activate=True)

    def _open_newtab_recommendation(self, url: str, new_tab: bool) -> None:
        """Open a safe recommendation in the current tab or a newly created tab."""
        if new_tab:
            self.tab_manager.create_tab(url=url, activate=True)
        else:
            self.navigate_to(url)

    def close_tab(self) -> None:
        """Close the currently active tab."""
        self._close_tab_request(self.tab_manager.current_index())

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
        win = MainWindow(initial_url="lightmq://incognito/", is_private=True)
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
        view = self.tab_manager.current_view()
        if isinstance(view, SpreadsheetViewer):
            view.search.setFocus(); view.search.selectAll(); return
        if isinstance(view, WebView) and view.page().is_pdf_document():
            self.status_bar.showMessage(
                "Use the PDF reader's Find control or press Ctrl+F.", 3500
            )
            view.setFocus()
            return
        self.find_bar.show_and_focus()

    def bookmark_current_page(self) -> None:
        """Bookmark the active tab's page or edit existing bookmark."""
        view = self.tab_manager.current_view()
        if view is None:
            return
        if self._is_private and not self._confirm_persistent_private_bookmark():
            return

        url = view.url().toString()
        title = view.title() or url
        manager = BookmarkManager.get_instance()

        if not manager.is_bookmarked(url):
            if manager.add_bookmark(title, url):
                self.status_bar.showMessage(f"Bookmark saved outside Incognito: {title}" if self._is_private else f"Bookmark added: {title}", 4000)
        else:
            self._bookmark_dialog = BookmarkDialog(title, url, bookmark_manager=manager, parent=self, item=manager.find_by_url(url))
            self._bookmark_dialog.show()

    def _update_bookmark_button(self, url: str) -> None:
        """Reflect the active page's bookmark state in the address toolbar."""
        supported = BookmarkManager.normalize_url(url) is not None
        bookmarked = supported and BookmarkManager.get_instance().is_bookmarked(url)
        self.btn_bookmark.setEnabled(supported)
        IconManager.set_widget_icon(self.btn_bookmark,"bookmark-filled" if bookmarked else "bookmark",20,self._icon_theme if self._is_private else None)
        label="Edit bookmark" if bookmarked else "Bookmark this page (Ctrl+D)"
        self.btn_bookmark.setToolTip(label)
        self.btn_bookmark.setAccessibleName(label)

    def _refresh_saved_bookmarks_menu(self) -> None:
        """Expose every saved item in a toolbar menu, regardless of bar visibility."""
        if not hasattr(self,"saved_bookmarks_menu"):
            return
        menu=self.saved_bookmarks_menu
        menu.clear()
        manager=BookmarkManager.get_instance()
        count=0
        def add_items(target:QMenu,parent_id:int)->None:
            nonlocal count
            for item in manager.children(parent_id):
                if item.is_folder:
                    submenu=target.addMenu(item.title)
                    IconManager.set_action_icon(submenu.menuAction(),"folder",18,self._icon_theme if self._is_private else None)
                    add_items(submenu,item.id)
                elif item.url:
                    self._add_menu_action(target,item.title,lambda _checked=False,url=item.url:self.navigate_to(url),"bookmark")
                    count+=1
        for root in manager.roots():
            submenu=menu.addMenu(root.title)
            IconManager.set_action_icon(submenu.menuAction(),"folder",18,self._icon_theme if self._is_private else None)
            add_items(submenu,root.id)
            if submenu.isEmpty():
                empty=submenu.addAction("No bookmarks in this folder")
                empty.setEnabled(False)
        if count==0:
            empty=menu.addAction("No saved bookmarks yet")
            empty.setEnabled(False)
        menu.addSeparator()
        self._add_menu_action(menu,"Bookmark this page…",self.open_bookmark_editor,"bookmark")
        if not self._is_private:
            self._add_menu_action(menu,"Manage bookmarks…",self.open_bookmark_manager,"settings")

    def open_bookmark_editor(self) -> None:
        """Open the add/edit dialog for the active HTTP(S) page."""
        view=self.tab_manager.current_view()
        if view is None:return
        if self._is_private and not self._confirm_persistent_private_bookmark():return
        url=view.url().toString(); manager=BookmarkManager.get_instance()
        dialog=BookmarkDialog(view.title() or url,url,manager,self,item=manager.find_by_url(url))
        self._bookmark_dialog=dialog;dialog.show()

    def _confirm_persistent_private_bookmark(self)->bool:
        """Explain that explicitly saved Incognito bookmarks remain afterward."""
        return QMessageBox.question(self,"Save Bookmark Outside Incognito?","This bookmark will be saved to LightMq and remain available after the Incognito session ends. Continue?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes

    def edit_bookmark(self, item_id: int) -> None:
        item=BookmarkManager.get_instance().get_item(item_id)
        if item and not item.is_folder and item.url:
            self._bookmark_dialog=BookmarkDialog(item.title,item.url,parent=self,item=item)
            self._bookmark_dialog.show()

    def _open_bookmark_new_tab(self,url:str)->None:
        self.tab_manager.create_tab(url,activate=True)

    def open_bookmark_manager(self) -> BookmarkManagerDialog | None:
        """Show or raise the window-scoped Bookmark Manager."""
        if self._is_private:return None
        dialog=getattr(self,"_bookmark_manager_dialog",None)
        if dialog is None:
            dialog=BookmarkManagerDialog(parent=self)
            dialog.open_url_requested.connect(lambda url,new_tab:self._open_bookmark_new_tab(url) if new_tab else self.navigate_to(url))
            dialog.finished.connect(lambda _result:setattr(self,"_bookmark_manager_dialog",None))
            self._bookmark_manager_dialog=dialog
        dialog.show();dialog.raise_();dialog.activateWindow();return dialog

    def print_current_page(self) -> None:
        """Open the native printer dialog for the active webpage or PDF viewer."""
        view = self.tab_manager.current_view()
        if not isinstance(view, WebView):
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
        if isinstance(view, SpreadsheetViewer):
            view.save(); return

        if isinstance(view, WebView) and view.page().is_pdf_document():
            # QWebEnginePage.download uses the page's existing profile, preserving
            # cookies and authentication; DownloadHandler owns destination prompts.
            view.page().download(view.url())
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

    def save_active_document_as(self) -> None:
        """Save the active spreadsheet to a user-selected copy."""
        view = self.tab_manager.current_view()
        if isinstance(view, SpreadsheetViewer): view.save_as()

    # --------------------------------------------------------------------------
    # Browser Management (History, Downloads, Clear Data, Fullscreen, Zoom)
    # --------------------------------------------------------------------------

    def open_history(self) -> None:
        """Open the browsing history dialog."""
        self._history_dialog = HistoryDialog(parent=self, recommendation_controller=self._recommendation_controller)
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

    def open_extensions_manager(self) -> ExtensionsDialog | None:
        """Open the native manager bound to this window's shared regular profile."""
        if self._is_private or self._extension_controller is None:
            return None
        dialog = getattr(self, "_extensions_dialog", None)
        if dialog is None:
            dialog = ExtensionsDialog(self._extension_controller, self)
            self._extensions_dialog = dialog
        dialog.refresh()
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        return dialog

    def _refresh_extensions_menu(self) -> None:
        """Show only enabled extensions with Qt-reported action popup URLs."""
        menu = getattr(self, "extensions_action_menu", None)
        controller = self._extension_controller
        if menu is None or controller is None:
            return
        menu.clear()
        active_view = self.tab_manager.current_view()
        active_url = active_view.url().toString() if isinstance(active_view, WebView) else ""
        if recognize_webstore_listing(active_url) is not None:
            self._add_menu_action(
                menu,
                "View Compatibility in LightMq…",
                lambda _checked=False, current_url=active_url: self._inspect_store_listing(
                    current_url
                ),
                "extensions",
            )
            menu.addSeparator()
        actions = [
            extension
            for extension in controller.user_extensions()
            if controller.open_popup_url(extension.id())
        ]
        for extension in actions:
            action = self._add_menu_action(
                menu,
                extension.name() or "Extension",
                lambda _checked=False, extension_id=extension.id(): self._open_extension_popup(
                    extension_id
                ),
                "extensions",
            )
            package_icon = load_extension_icon(controller.installed_package(extension))
            if not package_icon.isNull():
                action.setIcon(package_icon)
            action.setToolTip("Open the extension action popup provided by Qt WebEngine")
        if not actions:
            empty = menu.addAction("No enabled extension popups")
            empty.setEnabled(False)
        menu.addSeparator()
        self._add_menu_action(
            menu, "Manage Extensions…", self.open_extensions_manager, "settings"
        )

    def _inspect_store_listing(self, url: str) -> None:
        """Open the native compatibility flow for a recognized store listing."""
        dialog = self.open_extensions_manager()
        if dialog is not None:
            dialog.inspect_webstore_listing(url)

    def _open_extension_popup(self, extension_id: str) -> None:
        """Open only a popup URL exposed by the enabled Qt extension metadata."""
        controller = self._extension_controller
        if controller is None:
            return
        url_text = controller.open_popup_url(extension_id)
        extension = controller.extension(extension_id)
        if not url_text or extension is None:
            self._refresh_extensions_menu()
            return
        window = QDialog(self, Qt.WindowType.Tool)
        window.setWindowTitle(extension.name() or "Extension")
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        window.resize(360, 480)
        layout = QVBoxLayout(window)
        view = WebView(profile=controller.profile, parent=window)
        view.setUrl(QUrl(url_text))
        layout.addWidget(view)
        window.show()

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
        self.btn_downloads.setText(str(active_count) if active_count else "")
        self.btn_downloads.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon if active_count else Qt.ToolButtonStyle.ToolButtonIconOnly
        )
        self.btn_downloads.setFixedSize(48 if active_count else 36, 36)
        detail=f" — {active_count} active" if active_count else ""
        self.btn_downloads.setToolTip(f"Downloads{detail} (Ctrl+J)")

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

    def open_settings(self) -> SettingsWindow:
        """Show or raise the existing centralized Settings window."""
        dialog = getattr(self, "_settings_window", None)
        if dialog is None:
            dialog = SettingsWindow(self._browser_settings, self._startup_settings, self,
                                   recommendation_controller=self._recommendation_controller)
            dialog.finished.connect(lambda _result: setattr(self, "_settings_window", None))
            self._settings_window = dialog
        dialog.show(); dialog.raise_(); dialog.activateWindow()
        return dialog

    def _on_browser_setting_changed(self, key: str, value: object) -> None:
        if key.startswith("appearance/"):
            applied=False
            for window in tuple(MainWindow._all_windows):
                if not window.is_private:
                    if not applied:window._theme_manager.apply();applied=True
                    for view in window.tab_manager.ordered_views():
                        if isinstance(view, WebView): view.update_start_page_theme(window._theme_manager.palette(),window._browser_settings.search_template())
        elif key.startswith("search/"):
            for window in tuple(MainWindow._all_windows):
                template=window._browser_settings.search_template()
                for view in window.tab_manager.ordered_views():
                    if isinstance(view, WebView): view.update_start_page_theme(window._theme_manager.palette(),template)
        elif key == "pdf/open_in_browser":
            enabled = self._browser_settings.pdf_open_in_browser()
            for window in tuple(MainWindow._all_windows):
                for view in window.tab_manager.ordered_views():
                    if isinstance(view, WebView): view.set_pdf_viewer_enabled(enabled)
        elif key.startswith("recommendations/"):
            for window in tuple(MainWindow._all_windows):
                if window._recommendation_controller is not None:
                    window._recommendation_controller.invalidate()

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
            if start is None and end is None and self._recommendation_controller is not None:
                self._recommendation_controller.clear_data(keep_pins=dialog.keep_recommendation_pins)
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

    def _open_bookmark_manager_shortcut(self) -> None:
        self.open_bookmark_manager()

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
        if isinstance(view, WebView):
            new_zoom = min(5.0, round(view.zoomFactor() + 0.1, 2))
            view.setZoomFactor(new_zoom)
            self._refresh_zoom_label()
            self.status_bar.showMessage(f"Zoom: {int(round(new_zoom * 100))}%", 2000)

    def zoom_out(self) -> None:
        """Decrease the active view's zoom factor by 10% (min 25%)."""
        view = self.tab_manager.current_view()
        if isinstance(view, WebView):
            new_zoom = max(0.25, round(view.zoomFactor() - 0.1, 2))
            view.setZoomFactor(new_zoom)
            self._refresh_zoom_label()
            self.status_bar.showMessage(f"Zoom: {int(round(new_zoom * 100))}%", 2000)

    def reset_zoom(self) -> None:
        """Reset the active view's zoom factor to 100%."""
        view = self.tab_manager.current_view()
        if isinstance(view, WebView):
            view.setZoomFactor(1.0)
            self._refresh_zoom_label()
            self.status_bar.showMessage("Zoom: 100%", 2000)

    # --------------------------------------------------------------------------
    # Developer Tools Integration
    # --------------------------------------------------------------------------

    def toggle_devtools(self) -> None:
        """Toggle Chromium Developer Tools panel."""
        if self.devtools_manager.is_open():
            self.devtools_manager.close(); return
        view = self.tab_manager.current_view()
        if not isinstance(view, WebView) or view.page().is_pdf_document():
            self.status_bar.showMessage("Developer Tools are available for web pages, not document tabs.", 3500); return
        self.devtools_manager.toggle()

    def open_js_console(self) -> None:
        """Open LightMq's bounded page console."""
        if not isinstance(self.tab_manager.current_view(), WebView):
            self.status_bar.showMessage("The page console is available for web pages.", 3500); return
        if not self.devtools_manager.is_open():
            self.devtools_manager.open()
        self.devtools_panel.mode.setCurrentIndex(1)
        self.devtools_panel.tools.setCurrentWidget(self.devtools_panel.console)
        self.devtools_panel.console.command.setFocus()
        self.status_bar.showMessage("Opened Developer Tools Console", 2000)

    def activate_inspect_element(self) -> None:
        """Open LightMq's non-persistent element picker."""
        view = self.tab_manager.current_view()
        if not isinstance(view, WebView) or view.page().is_pdf_document():
            self.status_bar.showMessage("Inspect Element is available for web pages.", 3500); return
        if not self.devtools_manager.is_open():
            self.devtools_manager.open()
        self.devtools_panel.mode.setCurrentIndex(1)
        self.devtools_panel.tools.setCurrentWidget(self.devtools_panel.dom)
        self.devtools_panel.dom.toggle_picker()
        self.status_bar.showMessage("Element picker toggled", 2000)

    def _set_devtools_position(self, position: str) -> None:
        """Dock the resizable developer panel on the right or bottom and remember it."""
        value = "bottom" if position == "bottom" else "right"
        self.splitter.setOrientation(Qt.Orientation.Vertical if value == "bottom" else Qt.Orientation.Horizontal)
        self._settings.setValue("devtools/panel_position", value)

    def view_page_source(self) -> None:
        """Open the active tab's HTML source in a new tab using view-source: scheme."""
        view = self.tab_manager.current_view()
        if not isinstance(view, WebView):
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
