"""Native centralized browser settings window."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QMessageBox, QPushButton, QScrollArea, QSpinBox,
    QStackedWidget, QVBoxLayout, QWidget, QKeySequenceEdit, QCheckBox, QFileDialog)
from pathlib import Path

from browser.storage.settings import BrowserSettings, StartupSettings, StartupMode
from browser.features.bookmarks.bookmark_manager import BookmarkManager
from browser.features.bookmarks.bookmark_import_export import export_netscape_file


class SettingsWindow(QDialog):
    """Resizable settings categories sharing application QSettings."""

    CATEGORIES = ("General", "Appearance", "Search", "Tabs", "Downloads", "Bookmarks", "Privacy & Security", "Keyboard Shortcuts", "Advanced")

    def __init__(self, browser_settings: BrowserSettings, startup: StartupSettings, parent=None):
        super().__init__(parent)
        self.settings, self.startup = browser_settings, startup
        self.setWindowTitle("LightMq Settings")
        self.resize(800, 560)
        root = QHBoxLayout(self)
        self.sidebar = QListWidget(self)
        self.sidebar.addItems(self.CATEGORIES)
        self.sidebar.setFixedWidth(175)
        self.pages = QStackedWidget(self)
        root.addWidget(self.sidebar)
        root.addWidget(self.pages, 1)
        self.sidebar.currentRowChanged.connect(self.pages.setCurrentIndex)
        builders = (self._general, self._appearance, self._search, self._tabs, self._downloads, self._bookmarks, self._privacy, self._shortcuts, self._advanced)
        for builder in builders:
            scroll = QScrollArea(self)
            scroll.setWidgetResizable(True)
            content = QWidget(scroll)
            layout = QVBoxLayout(content)
            title = QLabel(self.CATEGORIES[len([None for _ in []])] if False else "")
            builder(layout)
            layout.addStretch()
            scroll.setWidget(content)
            self.pages.addWidget(scroll)
        self.sidebar.setCurrentRow(0)

    def _page(self, layout, heading: str, description: str) -> QFormLayout:
        layout.addWidget(QLabel(f"<h2>{heading}</h2><p>{description}</p>"))
        form = QFormLayout()
        layout.addLayout(form)
        return form

    def _general(self, layout):
        form = self._page(layout, "General", "Homepage and startup behavior")
        self.homepage = QLineEdit(self.startup.homepage())
        self.homepage.editingFinished.connect(self._save_homepage)
        form.addRow("Homepage URL", self.homepage)
        self.start_mode = QComboBox(); self.start_mode.addItems(["New Tab", "Homepage"])
        self.start_mode.setCurrentIndex(1 if self.startup.fallback_mode() is StartupMode.HOMEPAGE else 0)
        self.start_mode.currentIndexChanged.connect(lambda i: self.startup.set_fallback_mode(StartupMode.HOMEPAGE if i else StartupMode.NEW_TAB))
        form.addRow("When session restore is off", self.start_mode)
        self.new_tab = QComboBox(); self.new_tab.addItems(["LightMq Start Page", "Blank Page", "Homepage"])
        self.new_tab.setCurrentText(str(self.settings.get("general/new_tab_behavior", "LightMq Start Page")))
        self.new_tab.currentTextChanged.connect(lambda value: self.settings.set("general/new_tab_behavior", value))
        form.addRow("New tabs open", self.new_tab)

    def _save_homepage(self):
        try:
            self.startup.set_homepage(self.homepage.text())
            self.homepage.setStyleSheet("")
        except ValueError:
            self.homepage.setStyleSheet("border:1px solid #d93025")

    def _appearance(self, layout):
        form = self._page(layout, "Appearance", "Changes apply to browser controls, not webpage content.")
        self.theme = QComboBox(); self.theme.addItems(["Light", "Dark", "System"]); self.theme.setCurrentText(self.settings.theme().title())
        self.theme.currentTextChanged.connect(lambda value: self.settings.set("appearance/theme", value.lower()))
        form.addRow("Theme", self.theme)
        self.accent = QComboBox(); self.accent.addItems(["Blue", "Green", "Purple", "Red", "Orange", "Cyan", "Grey"]); self.accent.setCurrentText(self.settings.accent().title())
        self.accent.currentTextChanged.connect(lambda value: self.settings.set("appearance/accent_color", value.lower()))
        form.addRow("Accent color", self.accent)
        self.density = QComboBox(); self.density.addItems(["Normal", "Compact"]); self.density.setCurrentText(str(self.settings.get("appearance/toolbar_density", "Normal")))
        self.density.currentTextChanged.connect(lambda value: self.settings.set("appearance/toolbar_density", value))
        form.addRow("Toolbar spacing", self.density)
        self.show_bookmarks = QCheckBox("Show bookmarks bar", self)
        self.show_bookmarks.setChecked(bool(self.settings.store.value("bookmarks_bar_visible", False, type=bool)))
        self.show_bookmarks.toggled.connect(self._set_bookmarks_bar_visible)
        form.addRow("Bookmarks", self.show_bookmarks)

    def _set_bookmarks_bar_visible(self, visible: bool) -> None:
        self.settings.store.setValue("bookmarks_bar_visible", visible)
        self.settings.store.sync()
        from browser.ui.main_window import MainWindow
        for window in tuple(MainWindow._all_windows):
            if not window._is_private:
                window.bookmarks_bar.setVisible(visible)

    def _search(self, layout):
        form = self._page(layout, "Search", "Choose the provider used for non-URL address bar input.")
        self.provider = QComboBox(); self.provider.addItems(["Google", "Bing", "DuckDuckGo", "Brave Search", "Custom"]); self.provider.setCurrentText(self.settings.search_provider())
        self.provider.currentTextChanged.connect(lambda value: self.settings.set("search/default_provider", value))
        form.addRow("Default provider", self.provider)
        self.template = QLineEdit(str(self.settings.get("search/custom_template", "https://www.google.com/search?q={searchTerms}")))
        self.template.editingFinished.connect(self._save_template)
        form.addRow("Custom URL template", self.template)

    def _save_template(self):
        value = self.template.text().strip()
        if self.settings.valid_custom_template(value):
            self.settings.set("search/custom_template", value)
            self.template.setStyleSheet("")
        else:
            self.template.setStyleSheet("border:1px solid #d93025")

    def _tabs(self, layout):
        form = self._page(layout, "Tabs", "Session restoration remains the existing authoritative setting.")
        self.restore = QComboBox(); self.restore.addItems(["On", "Off"]); self.restore.setCurrentIndex(0 if self.startup.restore_previous_session() else 1)
        self.restore.currentIndexChanged.connect(lambda i: self.startup.set_restore_previous_session(i == 0))
        form.addRow("Restore previous session", self.restore)

    def _downloads(self, layout):
        form = self._page(layout, "Downloads", "Download directory and save prompts")
        self.download_dir = QLineEdit(str(self.settings.get("downloads/default_directory", "")))
        self.download_dir.editingFinished.connect(lambda: self.settings.set("downloads/default_directory", self.download_dir.text().strip()))
        form.addRow("Default directory (blank uses system Downloads)", self.download_dir)
        self.ask_download = QComboBox(); self.ask_download.addItems(["Ask where to save", "Save automatically"])
        self.ask_download.setCurrentIndex(0 if bool(self.settings.get("downloads/ask_before_saving", True)) else 1)
        self.ask_download.currentIndexChanged.connect(lambda i: self.settings.set("downloads/ask_before_saving", i == 0))
        form.addRow("Save behavior", self.ask_download)

    def _bookmarks(self, layout):
        self._page(layout, "Bookmarks", "Manage saved websites and transfer bookmarks using browser-compatible HTML files.")
        manager = QPushButton("Open Bookmark Manager…", self)
        manager.clicked.connect(lambda: self.parent().open_bookmark_manager() if self.parent() else None)
        layout.addWidget(manager)
        importer = QPushButton("Import Bookmarks…", self)
        importer.clicked.connect(self._import_bookmarks)
        layout.addWidget(importer)
        exporter = QPushButton("Export Bookmarks…", self)
        exporter.clicked.connect(self._export_bookmarks)
        layout.addWidget(exporter)

    def _import_bookmarks(self):
        dialog=self.parent().open_bookmark_manager() if self.parent() else None
        if dialog:dialog._import()

    def _export_bookmarks(self):
        filename,_=QFileDialog.getSaveFileName(self,"Export Bookmarks","bookmarks.html","HTML bookmark files (*.html)")
        if not filename:return
        try:
            manager=BookmarkManager.get_instance()
            nodes=[node for root in manager.roots() for node in manager.export_tree(root.id)]
            export_netscape_file(Path(filename),nodes)
        except OSError as exc:QMessageBox.warning(self,"Export failed",str(exc))

    def _privacy(self, layout):
        self._page(layout, "Privacy & Security", "Open the existing profile-based cookie, cache, and permission controls.")
        button = QPushButton("Open Privacy Controls")
        button.clicked.connect(lambda: self.parent().open_privacy_settings() if self.parent() else None)
        layout.addWidget(button)

    def _shortcuts(self, layout):
        layout.addWidget(QLabel("<h2>Keyboard Shortcuts</h2><p>Set an empty sequence to disable an action. Conflicts are rejected.</p>"))
        self.shortcut_edits = {}
        manager = self.parent().shortcut_manager
        for entry in manager.get_registered_shortcuts():
            action = entry["action"]
            if action in self.shortcut_edits:
                continue
            row = QHBoxLayout(); row.addWidget(QLabel(entry["description"]), 1)
            edit = QKeySequenceEdit(QKeySequence(str(self.settings.get(f"shortcuts/{action}", entry["key"]))))
            self.shortcut_edits[action] = (edit, entry)
            row.addWidget(edit); layout.addLayout(row)
        save = QPushButton("Apply Shortcuts")
        save.clicked.connect(self._save_shortcuts)
        layout.addWidget(save)

    def _save_shortcuts(self):
        proposed = {}
        for action, (edit, _) in self.shortcut_edits.items():
            sequence = edit.keySequence().toString()
            if sequence and sequence in proposed.values():
                QMessageBox.warning(self, "Shortcut conflict", f"{sequence} is assigned more than once.")
                return
            proposed[action] = sequence
        from browser.ui.main_window import MainWindow
        if not all(window.shortcut_manager.apply_custom(proposed) for window in tuple(MainWindow._all_windows)):
            QMessageBox.warning(self, "Shortcut conflict", "One or more shortcuts conflict with an existing browser binding.")
            return
        for action, sequence in proposed.items():
            self.settings.set(f"shortcuts/{action}", sequence)

    def _advanced(self, layout):
        form = self._page(layout, "Advanced", "Zoom and application preferences")
        self.zoom = QComboBox(); self.zoom.addItems([f"{value}%" for value in BrowserSettings.ZOOMS]); self.zoom.setCurrentText(f"{int(self.settings.default_zoom()*100)}%")
        self.zoom.currentTextChanged.connect(lambda text: self.settings.set("web/default_zoom", int(text.rstrip("%"))))
        form.addRow("Default page zoom", self.zoom)
        reset = QPushButton("Reset Settings…"); reset.clicked.connect(self._reset)
        form.addRow("Preferences", reset)

    def _reset(self):
        if QMessageBox.question(self, "Reset Settings", "Reset browser preferences? Cookies, login sessions, history, downloads, and session files will be preserved.") == QMessageBox.StandardButton.Yes:
            keys = ("appearance/theme", "appearance/accent_color", "appearance/toolbar_density", "general/new_tab_behavior", "search/default_provider", "search/custom_template", "web/default_zoom", "downloads/default_directory", "downloads/ask_before_saving", "bookmarks_bar_visible")
            for key in keys:
                self.settings.store.remove(key)
            for key in self.settings.store.allKeys():
                if key.startswith("shortcuts/"):
                    self.settings.store.remove(key)
            self.startup.set_restore_previous_session(True)
            self.startup.set_fallback_mode(StartupMode.NEW_TAB)
            self.settings.store.sync()
            self.settings.changed.emit("appearance/theme", "system")
            self.settings.changed.emit("appearance/accent_color", "blue")
            from browser.ui.main_window import MainWindow
            for window in tuple(MainWindow._all_windows):
                window.shortcut_manager.reset_defaults()
                window._browser_settings.changed.emit("web/default_zoom", 100)
                if not window._is_private: window.bookmarks_bar.hide()
            QMessageBox.information(self, "Settings reset", "Preferences reset to safe defaults. Browser data was preserved.")
