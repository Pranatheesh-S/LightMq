"""Native privacy settings for cookies, HTTP cache, and site permissions."""

from collections.abc import Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
    QPushButton, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from browser.features.privacy.cookie_manager import CookieInfo
from browser.features.privacy.privacy_manager import PermissionInfo, PrivacyManager


class PrivacySettingsDialog(QDialog):
    """Display cookie metadata and manage the selected regular profile."""

    def __init__(
        self,
        privacy_manager: PrivacyManager,
        clear_data_callback: Callable[[], object],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Privacy & Security")
        self.resize(920, 590)
        self._manager = privacy_manager
        self._clear_data_callback = clear_data_callback
        self._displayed_cookies: list[CookieInfo] = []
        self._displayed_permissions: list[PermissionInfo] = []
        self._init_ui()
        self._manager.cookies.cookies_changed.connect(self._populate_cookies)
        self._manager.cookies.operation_requested.connect(self._set_cookie_status)
        self._manager.cache.clear_started.connect(lambda: self.cache_status.setText("Clearing HTTP cache…"))
        self._manager.cache.clear_completed.connect(self._cache_cleared)
        self._manager.cache.clear_failed.connect(self.cache_status.setText)
        self._manager.permissions_changed.connect(self._populate_permissions)
        self._manager.cookies.load_all()
        QTimer.singleShot(1500, self._finish_cookie_load_status)
        self._populate_permissions()

    def _init_ui(self) -> None:
        """Build cookie, permission, and cache/data tabs."""
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        self.tabs.addTab(self._build_cookies_tab(), "Cookies")
        self.tabs.addTab(self._build_permissions_tab(), "Website Permissions")
        self.tabs.addTab(self._build_cache_tab(), "Cache & Data")
        layout.addWidget(self.tabs)
        close = QPushButton("Close", self)
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(close)
        layout.addLayout(row)

    def _build_cookies_tab(self) -> QWidget:
        """Create cookie metadata inventory and asynchronous delete controls."""
        page = QWidget(self)
        layout = QVBoxLayout(page)
        note = QLabel("Cookie values are intentionally hidden. Listing and deletion are asynchronous.", page)
        note.setWordWrap(True)
        layout.addWidget(note)
        self.cookie_table = QTableWidget(page)
        self.cookie_table.setColumnCount(7)
        self.cookie_table.setHorizontalHeaderLabels(
            ["Name", "Domain", "Path", "Expires", "Lifetime", "Secure", "HttpOnly"]
        )
        self.cookie_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.cookie_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.cookie_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.cookie_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.cookie_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.cookie_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.cookie_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.cookie_table)
        self.cookie_status = QLabel("Loading cookie metadata…", page)
        layout.addWidget(self.cookie_status)
        buttons = QHBoxLayout()
        refresh = QPushButton("Refresh", page)
        refresh.clicked.connect(self._refresh_cookies)
        buttons.addWidget(refresh)
        delete_one = QPushButton("Delete selected", page)
        delete_one.clicked.connect(self._delete_selected_cookie)
        buttons.addWidget(delete_one)
        delete_session = QPushButton("Delete session cookies…", page)
        delete_session.clicked.connect(self._delete_session_cookies)
        buttons.addWidget(delete_session)
        delete_all = QPushButton("Delete all cookies…", page)
        delete_all.clicked.connect(self._delete_all_cookies)
        buttons.addWidget(delete_all)
        layout.addLayout(buttons)
        return page

    def _build_permissions_tab(self) -> QWidget:
        """Create a sortable view of permission decisions retained by Qt."""
        page = QWidget(self)
        layout = QVBoxLayout(page)
        note = QLabel(
            "This list comes from Qt WebEngine's profile permission store. Only decisions exposed by Qt are shown.",
            page,
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        order_row = QHBoxLayout()
        order_row.addWidget(QLabel("Sort by:"))
        self.permission_sort = QComboBox(page)
        self.permission_sort.addItems(["Website", "Capability"])
        self.permission_sort.currentIndexChanged.connect(self._sort_permissions)
        order_row.addWidget(self.permission_sort)
        order_row.addStretch()
        refresh = QPushButton("Refresh", page)
        refresh.clicked.connect(self._populate_permissions)
        order_row.addWidget(refresh)
        layout.addLayout(order_row)
        self.permission_table = QTableWidget(page)
        self.permission_table.setColumnCount(4)
        self.permission_table.setHorizontalHeaderLabels(["Website origin", "Capability", "Decision", "Persistence"])
        self.permission_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.permission_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.permission_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.permission_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.permission_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.permission_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.permission_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.permission_table)
        self.permission_status = QLabel(page)
        layout.addWidget(self.permission_status)
        reset = QPushButton("Reset selected permission…", page)
        reset.clicked.connect(self._reset_selected_permission)
        layout.addWidget(reset, alignment=Qt.AlignmentFlag.AlignRight)
        return page

    def _build_cache_tab(self) -> QWidget:
        """Create HTTP cache and clear-data controls with explicit scope."""
        page = QWidget(self)
        layout = QVBoxLayout(page)
        note = QLabel(
            "Clear HTTP cache removes cached web resources for all dates. It does not clear cookies, "
            "Local Storage, IndexedDB, history, or downloaded files.",
            page,
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        clear_cache = QPushButton("Clear HTTP cache…", page)
        clear_cache.clicked.connect(self._clear_cache)
        layout.addWidget(clear_cache, alignment=Qt.AlignmentFlag.AlignLeft)
        self.cache_status = QLabel("HTTP cache is unchanged.", page)
        layout.addWidget(self.cache_status)
        layout.addSpacing(22)
        clear_data = QPushButton("Clear Browsing Data…", page)
        clear_data.clicked.connect(self._clear_data_callback)
        layout.addWidget(clear_data, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch()
        return page

    def _populate_cookies(self) -> None:
        """Render safe cookie metadata only, never cookie values."""
        self._displayed_cookies = self._manager.cookies.cookies()
        self.cookie_table.setRowCount(len(self._displayed_cookies))
        for row, cookie in enumerate(self._displayed_cookies):
            values = (
                cookie.name, cookie.domain, cookie.path, cookie.expires, cookie.lifetime,
                "Yes" if cookie.secure else "No", "Yes" if cookie.http_only else "No",
            )
            for column, value in enumerate(values):
                self.cookie_table.setItem(row, column, QTableWidgetItem(value))
        self.cookie_status.setText(f"{len(self._displayed_cookies)} cookies received so far.")

    def _refresh_cookies(self) -> None:
        """Start a fresh asynchronous cookie listing."""
        self.cookie_status.setText("Loading cookie metadata…")
        self._manager.cookies.load_all()
        QTimer.singleShot(1500, self._finish_cookie_load_status)

    def _finish_cookie_load_status(self) -> None:
        """Clarify that cookie events may continue after the initial request."""
        self.cookie_status.setText(
            f"{len(self._displayed_cookies)} cookies received. WebEngine streams results asynchronously; "
            "there is no inventory-complete signal."
        )

    def _set_cookie_status(self, message: str) -> None:
        """Show the request state without claiming asynchronous deletion finished."""
        self.cookie_status.setText(message)

    def _delete_selected_cookie(self) -> None:
        """Confirm and delete the selected cookie without exposing its value."""
        rows = self.cookie_table.selectionModel().selectedRows()
        if not rows:
            return
        cookie = self._displayed_cookies[rows[0].row()]
        name = cookie.name
        answer = QMessageBox.warning(
            self, "Delete cookie", f"Delete cookie ‘{name}’? This may sign you out of a website.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._manager.cookies.delete_cookie(cookie)

    def _delete_session_cookies(self) -> None:
        """Confirm and request deletion of session cookies."""
        answer = QMessageBox.warning(
            self, "Delete session cookies", "Delete all session cookies? Websites may sign you out.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._manager.cookies.delete_session_cookies()

    def _delete_all_cookies(self) -> None:
        """Confirm and request deletion of all cookies."""
        answer = QMessageBox.warning(
            self, "Delete all cookies", "Delete all cookies for this profile? Websites may sign you out.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._manager.cookies.delete_all_cookies()

    def _populate_permissions(self) -> None:
        """Display decisions exposed by Qt WebEngine, including persistence state."""
        self._displayed_permissions = self._manager.permissions()
        self.permission_table.setRowCount(len(self._displayed_permissions))
        for row, permission in enumerate(self._displayed_permissions):
            values = (
                permission.origin, permission.capability, permission.decision, permission.persistence,
            )
            for column, value in enumerate(values):
                self.permission_table.setItem(row, column, QTableWidgetItem(value))
            self.permission_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, row)
        self.permission_status.setText(f"{len(self._displayed_permissions)} saved decisions exposed by Qt WebEngine.")
        self._sort_permissions()

    def _sort_permissions(self, *_args: object) -> None:
        """Sort the permission table by the selected grouping key."""
        column = 1 if self.permission_sort.currentIndex() == 1 else 0
        self.permission_table.sortItems(column, Qt.SortOrder.AscendingOrder)

    def _reset_selected_permission(self) -> None:
        """Confirm and reset one selected Qt permission decision."""
        rows = self.permission_table.selectionModel().selectedRows()
        if not rows:
            return
        selected_row = rows[0].row()
        source_row = int(self.permission_table.item(selected_row, 0).data(Qt.ItemDataRole.UserRole))
        permission = self._displayed_permissions[source_row]
        answer = QMessageBox.question(
            self, "Reset website permission",
            f"Reset {permission.capability} for {permission.origin}? The website will need to ask again.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._manager.reset_permission(permission)

    def _clear_cache(self) -> None:
        """Confirm and request profile HTTP-cache clearing."""
        answer = QMessageBox.question(
            self, "Clear HTTP cache",
            "Clear the full HTTP cache for this profile? Cookies and other website storage are not affected.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            if not self._manager.cache.clear():
                self.cache_status.setText("HTTP cache clearing is already in progress or could not be started.")

    def _cache_cleared(self) -> None:
        """Report the cache operation only after Qt confirms completion."""
        self.cache_status.setText("HTTP cache clearing completed.")
