"""Native centralized browser settings window."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QColor, QKeySequence
from PySide6.QtWidgets import (QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QScrollArea, QSpinBox,
    QStackedWidget, QVBoxLayout, QWidget, QKeySequenceEdit, QCheckBox, QFileDialog,
    QFrame)
from pathlib import Path

from browser.storage.settings import BrowserSettings, StartupSettings, StartupMode
from browser.features.bookmarks.bookmark_manager import BookmarkManager
from browser.features.bookmarks.bookmark_import_export import export_netscape_file
from browser.ui.widgets.color_wheel import HueRingWidget, SaturationValueWidget
from browser.ui.icons.icon_manager import IconManager


class SettingsWindow(QDialog):
    """Resizable settings categories sharing application QSettings."""

    CATEGORIES = ("General", "Appearance", "Search", "Tabs", "Downloads & PDF", "Bookmarks", "Privacy & Security", "Keyboard Shortcuts", "Recommendations", "Advanced")

    @staticmethod
    def _preference_bool(settings: BrowserSettings, key: str, default: bool) -> bool:
        """Read booleans consistently from QSettings INI and native backends."""
        value = settings.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, int) and value in (0, 1):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off", ""}:
                return False
        return default

    def __init__(self, browser_settings: BrowserSettings, startup: StartupSettings, parent=None, recommendation_controller=None):
        super().__init__(parent)
        self.settings, self.startup = browser_settings, startup
        self.recommendation_controller = recommendation_controller
        self.setWindowTitle("LightMq Settings")
        self.setMinimumSize(640, 480)
        self.resize(900, 650)
        root = QHBoxLayout(self)
        self.sidebar = QListWidget(self)
        sidebar_icons=("settings","palette","search","tabs","download","bookmarks","shield","keyboard","search","sliders")
        icon_theme=getattr(self.parent(),"_icon_theme",None)
        for category,icon_name in zip(self.CATEGORIES,sidebar_icons):
            item=QListWidgetItem(category)
            item.setIcon(IconManager.icon(icon_name,18,icon_theme))
            self.sidebar.addItem(item)
        self.sidebar.setIconSize(QSize(18,18))
        self.sidebar.setFixedWidth(175)
        self.pages = QStackedWidget(self)
        self._theme_preview_timer=QTimer(self);self._theme_preview_timer.setSingleShot(True);self._theme_preview_timer.setInterval(50)
        self._theme_preview_timer.timeout.connect(self._apply_pending_theme_preview)
        root.addWidget(self.sidebar)
        root.addWidget(self.pages, 1)
        self.sidebar.currentRowChanged.connect(self.pages.setCurrentIndex)
        builders = (self._general, self._appearance, self._search, self._tabs, self._downloads, self._bookmarks, self._privacy, self._shortcuts, self._recommendations, self._advanced)
        for builder in builders:
            scroll = QScrollArea(self)
            scroll.setWidgetResizable(True)
            content = QWidget(scroll)
            layout = QVBoxLayout(content)
            builder(layout)
            layout.addStretch()
            scroll.setWidget(content)
            self.pages.addWidget(scroll)
        self.sidebar.setCurrentRow(0)
        self.finished.connect(lambda _result:self._cancel_theme_preview())

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
        form=self._page(layout,"Appearance","Choose a built-in mode or create a coordinated palette. Preview changes apply to browser controls only.")
        self._appearance_form=form
        self.theme=QComboBox();self.theme.addItems(["Light","Dark","System","Custom"])
        self.theme.setCurrentText(self.settings.theme().title())
        self.theme.currentTextChanged.connect(self._preview_selected_mode)
        form.addRow("Theme mode",self.theme)
        self.brightness=QComboBox();self.brightness.addItems(["Dark surfaces","Light surfaces"])
        self.brightness.setCurrentIndex(0 if self.settings.custom_theme_brightness()=="dark" else 1)
        self.brightness.currentIndexChanged.connect(lambda _i:self._preview_selected_mode(self.theme.currentText()))
        form.addRow("Custom theme surfaces",self.brightness)

        self.color_controls=QWidget(self)
        color_layout=QVBoxLayout(self.color_controls);color_layout.setContentsMargins(0,4,0,4);color_layout.setSpacing(10)
        wheel_row=QHBoxLayout();wheel_row.setContentsMargins(0,0,0,0);wheel_row.setSpacing(14)
        self.hue_wheel=HueRingWidget(parent=self);self.sv_picker=SaturationValueWidget(parent=self)
        wheel_row.addWidget(self.hue_wheel);wheel_row.addWidget(self.sv_picker)
        wheel_row.addStretch(1);color_layout.addLayout(wheel_row)

        color_inputs=QHBoxLayout();color_inputs.setContentsMargins(0,0,0,0);color_inputs.setSpacing(10)
        self.color_swatch=QFrame(self);self.color_swatch.setFixedSize(58,42);color_inputs.addWidget(self.color_swatch)
        self.hex_edit=QLineEdit(self.settings.custom_theme_color(),self);self.hex_edit.setMaxLength(7);self.hex_edit.setPlaceholderText("#RRGGBB")
        hex_column=QVBoxLayout();hex_column.addWidget(QLabel("HEX color"));hex_column.addWidget(self.hex_edit);color_inputs.addLayout(hex_column)
        color_inputs.addStretch(1);color_layout.addLayout(color_inputs)

        rgb=QHBoxLayout();rgb.setContentsMargins(0,0,0,0);rgb.setSpacing(8);rgb.addWidget(QLabel("RGB"));self.rgb_spins=[]
        for channel in ("R","G","B"):
            channel_box=QVBoxLayout();channel_box.setSpacing(2);channel_box.addWidget(QLabel(channel))
            spin=QSpinBox(self);spin.setRange(0,255);spin.setFixedWidth(66);spin.setAccessibleName(f"RGB {channel} channel")
            channel_box.addWidget(spin);rgb.addLayout(channel_box);self.rgb_spins.append(spin)
        rgb.addStretch(1);color_layout.addLayout(rgb)
        form.addRow("Custom color",self.color_controls)
        self.hue_wheel.hueChanged.connect(self._on_wheel_hue)
        self.sv_picker.colorChanged.connect(self._on_wheel_sv)
        self.hex_edit.editingFinished.connect(self._on_hex_changed)
        for spin in self.rgb_spins:spin.valueChanged.connect(self._on_rgb_changed)

        recent_container=QWidget(self);self.recent_layout=QHBoxLayout(recent_container);self.recent_layout.setContentsMargins(0,0,0,0)
        form.addRow("Recent colors",recent_container);self._refresh_recent_colors()
        self.preview_card=QFrame(self);self.preview_card.setObjectName("themePreviewCard")
        card=QVBoxLayout(self.preview_card);card.setContentsMargins(12,10,12,10)
        self.preview_tabs=QHBoxLayout();self.preview_tabs.addWidget(QLabel("●  Active tab"));self.preview_tabs.addWidget(QLabel("Inactive tab"));card.addLayout(self.preview_tabs)
        self.preview_omnibox=QLineEdit("Search or enter address");self.preview_omnibox.setReadOnly(True);self.preview_omnibox.setObjectName("addressBar");card.addWidget(self.preview_omnibox)
        self.preview_button=QPushButton("Browser menu ··");card.addWidget(self.preview_button,0,Qt.AlignmentFlag.AlignRight)
        form.addRow("Live preview",self.preview_card)
        buttons=QHBoxLayout();self.apply_theme_button=QPushButton("Apply theme");self.cancel_theme_button=QPushButton("Cancel preview");self.reset_theme_button=QPushButton("Reset theme")
        buttons.addWidget(self.reset_theme_button);buttons.addStretch();buttons.addWidget(self.cancel_theme_button);buttons.addWidget(self.apply_theme_button);layout.addLayout(buttons)
        self.apply_theme_button.clicked.connect(self._apply_theme)
        self.cancel_theme_button.clicked.connect(self._cancel_theme_preview)
        self.reset_theme_button.clicked.connect(self._reset_theme)

        self.density=QComboBox();self.density.addItems(["Normal","Compact"]);self.density.setCurrentText(str(self.settings.get("appearance/toolbar_density","Normal")))
        self.density.currentTextChanged.connect(lambda value:self.settings.set("appearance/toolbar_density",value))
        form.addRow("Toolbar spacing",self.density)
        self.show_bookmarks=QCheckBox("Show bookmarks bar",self)
        self.show_bookmarks.setChecked(bool(self.settings.store.value("bookmarks_bar_visible",False,type=bool)))
        self.show_bookmarks.toggled.connect(self._set_bookmarks_bar_visible);form.addRow("Bookmarks",self.show_bookmarks)
        if getattr(self.parent(),"_is_private",False):
            for widget in (self.theme,self.brightness,self.color_controls,recent_container,self.preview_card,self.apply_theme_button,self.cancel_theme_button,self.reset_theme_button):widget.setEnabled(False)
            form.addRow(QLabel("Theme changes are available from a regular LightMq window."))
        self._sync_color_inputs(QColor(self.settings.custom_theme_color()))
        self._preview_selected_mode(self.theme.currentText())

    def _theme_manager(self):
        parent=self.parent()
        return getattr(parent,"_theme_manager",None)

    def _current_color(self)->QColor:
        color=QColor.fromHsv(self.hue_wheel.hue,self.sv_picker.saturation,self.sv_picker.value)
        return color if color.isValid() else QColor("#1a73e8")

    def _sync_color_inputs(self,color:QColor)->None:
        if not color.isValid():return
        self.hue_wheel.setHue(max(0,color.hsvHue()));self.sv_picker.setHue(max(0,color.hsvHue()));self.sv_picker.setColor(color.hsvSaturation(),color.value())
        self.hex_edit.setText(color.name().upper())
        for spin,value in zip(self.rgb_spins,(color.red(),color.green(),color.blue())):
            spin.blockSignals(True);spin.setValue(value);spin.blockSignals(False)
        self.color_swatch.setStyleSheet(f"background:{color.name()};border:1px solid #777;border-radius:8px;")

    def _on_wheel_hue(self,hue:int)->None:
        self.hue_wheel.setHue(hue);self.sv_picker.setHue(hue);self._on_picker_changed()

    def _on_wheel_sv(self,saturation:int,value:int)->None:
        self.sv_picker.setColor(saturation,value);self._on_picker_changed()

    def _on_picker_changed(self)->None:
        color=self._current_color();self._sync_color_inputs(color)
        self._preview_selected_mode(self.theme.currentText())

    def _on_hex_changed(self)->None:
        value=self.hex_edit.text().strip()
        if not value.startswith("#"):value="#"+value
        color=QColor(value)
        if color.isValid():self._sync_color_inputs(color);self._preview_selected_mode(self.theme.currentText())
        else:self.hex_edit.setStyleSheet("border:1px solid #d93025")

    def _on_rgb_changed(self,_value:int)->None:
        if not hasattr(self,"rgb_spins"):return
        color=QColor(*(spin.value() for spin in self.rgb_spins));self._sync_color_inputs(color);self._preview_selected_mode(self.theme.currentText())

    def _preview_selected_mode(self,_mode:str)->None:
        if not hasattr(self,"theme"):return
        is_custom=self.theme.currentText()=="Custom"
        self.color_controls.setVisible(is_custom);self.brightness.setVisible(is_custom)
        for field in (self.color_controls,self.brightness):
            label=self._appearance_form.labelForField(field)
            if label is not None:label.setVisible(is_custom)
        manager=self._theme_manager()
        if manager is None:return
        mode=self.theme.currentText().lower();color=self._current_color().name();brightness="dark" if self.brightness.currentIndex()==0 else "light"
        from browser.ui.theme_palette import build_palette
        palette=build_palette(color,brightness=="dark" if mode=="custom" else manager._resolve_dark(mode))
        self._update_preview_card(mode,color,brightness,palette)
        self._pending_theme_preview=(mode,color,brightness)
        self._theme_preview_timer.start()

    def _apply_pending_theme_preview(self)->None:
        manager=self._theme_manager()
        if manager is None or not hasattr(self,"_pending_theme_preview"):return
        mode,color,brightness=self._pending_theme_preview
        manager.preview_mode(mode,color,brightness)
        from browser.ui.main_window import MainWindow
        for window in tuple(MainWindow._all_windows):
            if not window.is_private:
                for view in window.tab_manager.ordered_views():view.update_start_page_theme(manager.palette(),window._browser_settings.search_template())

    def _update_preview_card(self,mode:str,color:str,brightness:str,palette)->None:
        self.preview_card.setStyleSheet(f"QFrame#themePreviewCard{{background:{palette.window_bg};border:1px solid {palette.border_color};border-radius:12px;}} QFrame#themePreviewCard QLabel{{color:{palette.primary_text};}} QFrame#themePreviewCard QLineEdit{{background:{palette.omnibox_bg};color:{palette.primary_text};border:1px solid {palette.focus_color};border-radius:16px;}} QFrame#themePreviewCard QPushButton{{background:{palette.accent_soft};color:{palette.primary_text};border-radius:8px;padding:6px 10px;}}")
        for index,label in enumerate(self.preview_tabs.parentWidget().findChildren(QLabel)):
            label.setStyleSheet(f"background:{palette.active_tab_bg if index==0 else palette.inactive_tab_bg};color:{palette.primary_text};padding:7px 12px;border-radius:9px;")

    def _apply_theme(self)->None:
        mode=self.theme.currentText().lower();color=self._current_color().name();brightness="dark" if self.brightness.currentIndex()==0 else "light"
        if mode=="custom":
            self.settings.store.setValue("appearance/custom_base_color",color);self.settings.store.setValue("appearance/custom_brightness",brightness)
            recent=list(self.settings.get("appearance/recent_colors",[]));recent=[color,*[item for item in recent if item.lower()!=color.lower()]]
            self.settings.store.setValue("appearance/recent_colors",recent[:8])
        self.settings.store.setValue("appearance/theme",mode);self.settings.store.sync()
        self.settings.changed.emit("appearance/theme",mode);self._refresh_recent_colors()

    def _cancel_theme_preview(self)->None:
        self._theme_preview_timer.stop()
        manager=self._theme_manager()
        if manager:manager.cancel_preview()
        if hasattr(self,"theme"):
            self.theme.blockSignals(True);self.theme.setCurrentText(self.settings.theme().title());self.theme.blockSignals(False)
            color=QColor(self.settings.custom_theme_color());self._sync_color_inputs(color)
            self.brightness.blockSignals(True);self.brightness.setCurrentIndex(0 if self.settings.custom_theme_brightness()=="dark" else 1);self.brightness.blockSignals(False)
            if manager:self._update_preview_card(self.settings.theme(),color.name(),self.settings.custom_theme_brightness(),manager.palette())
            if manager:
                from browser.ui.main_window import MainWindow
                for window in tuple(MainWindow._all_windows):
                    if not window.is_private:
                        for view in window.tab_manager.ordered_views():view.update_start_page_theme(manager.palette(),window._browser_settings.search_template())

    def _reset_theme(self)->None:
        self.theme.blockSignals(True);self.theme.setCurrentText("System");self.theme.blockSignals(False)
        self._sync_color_inputs(QColor("#1a73e8"));self.brightness.setCurrentIndex(0)
        self.settings.store.setValue("appearance/accent_color","blue")
        self.settings.store.remove("appearance/custom_base_color")
        self.settings.store.setValue("appearance/theme","system")
        self.settings.store.sync()
        self.settings.changed.emit("appearance/accent_color","blue")
        self.settings.changed.emit("appearance/theme","system")
        self._preview_selected_mode("System")

    def _refresh_recent_colors(self)->None:
        if not hasattr(self,"recent_layout"):return
        while self.recent_layout.count():
            item=self.recent_layout.takeAt(0)
            if item.widget():item.widget().deleteLater()
        for value in list(self.settings.get("appearance/recent_colors",[]))[:8]:
            color=QColor(str(value))
            if not color.isValid():continue
            chip=QPushButton(" ",self);chip.setToolTip(color.name().upper());chip.setFixedSize(28,24);chip.setStyleSheet(f"background:{color.name()};border:1px solid #777;border-radius:6px;")
            chip.clicked.connect(lambda _checked=False,c=color:self._sync_color_inputs(c))
            chip.clicked.connect(lambda _checked=False:self._preview_selected_mode(self.theme.currentText()))
            self.recent_layout.addWidget(chip)

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
        form = self._page(layout, "Downloads & PDF", "Download handling and PDF documents")
        self.download_dir = QLineEdit(str(self.settings.get("downloads/default_directory", "")))
        self.download_dir.editingFinished.connect(lambda: self.settings.set("downloads/default_directory", self.download_dir.text().strip()))
        form.addRow("Default directory (blank uses system Downloads)", self.download_dir)
        self.ask_download = QComboBox(); self.ask_download.addItems(["Ask where to save", "Save automatically"])
        self.ask_download.setCurrentIndex(0 if bool(self.settings.get("downloads/ask_before_saving", True)) else 1)
        self.ask_download.currentIndexChanged.connect(lambda i: self.settings.set("downloads/ask_before_saving", i == 0))
        form.addRow("Save behavior", self.ask_download)

        self.pdf_handling = QComboBox(self)
        self.pdf_handling.addItem("Open PDFs inside LightMq", True)
        self.pdf_handling.addItem("Download PDFs instead", False)
        self.pdf_handling.setCurrentIndex(0 if self.settings.pdf_open_in_browser() else 1)
        self.pdf_handling.currentIndexChanged.connect(
            lambda index: self.settings.set(
                "pdf/open_in_browser", bool(self.pdf_handling.itemData(index))
            )
        )
        form.addRow("PDF documents", self.pdf_handling)

        pdf_note = QLabel(
            "Inline PDFs use Qt WebEngine's built-in reader for page navigation, zoom, "
            "search, download, and print. The reader does not expose a separate default "
            "PDF zoom setting through Qt's supported API; use its zoom controls.",
            self,
        )
        pdf_note.setWordWrap(True)
        form.addRow(pdf_note)

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

    def _recommendations(self, layout):
        form = self._page(
            layout, "Recommendations",
            "Optional suggestions are calculated locally from LightMq history, bookmark titles, and the page that opened this tab. No page content is read or sent to a service.",
        )
        self.recommendations_enabled = QCheckBox("Enable personalized local recommendations", self)
        self.recommendations_enabled.setChecked(self._preference_bool(self.settings, "recommendations/enabled", False))
        self.recommendations_enabled.toggled.connect(lambda value: self.settings.set("recommendations/enabled", value))
        form.addRow("Personalization", self.recommendations_enabled)
        self.recommendations_history = QCheckBox("Use eligible browsing history", self)
        self.recommendations_history.setChecked(self._preference_bool(self.settings, "recommendations/source_history", True))
        self.recommendations_history.toggled.connect(lambda value: self.settings.set("recommendations/source_history", value))
        form.addRow("Sources", self.recommendations_history)
        self.recommendations_bookmarks = QCheckBox("Use saved bookmarks", self)
        self.recommendations_bookmarks.setChecked(self._preference_bool(self.settings, "recommendations/source_bookmarks", True))
        self.recommendations_bookmarks.toggled.connect(lambda value: self.settings.set("recommendations/source_bookmarks", value))
        form.addRow("", self.recommendations_bookmarks)
        self.recommendations_show_new_tab = QCheckBox("Show recommendations on the LightMq New Tab page", self)
        self.recommendations_show_new_tab.setChecked(self._preference_bool(self.settings, "recommendations/show_new_tab", True))
        self.recommendations_show_new_tab.toggled.connect(lambda value: self.settings.set("recommendations/show_new_tab", value))
        form.addRow("Display", self.recommendations_show_new_tab)
        self.recommendations_continue = QCheckBox("Show Continue Browsing", self)
        self.recommendations_continue.setChecked(self._preference_bool(self.settings, "recommendations/show_continue", True))
        self.recommendations_continue.toggled.connect(lambda value: self.settings.set("recommendations/show_continue", value))
        form.addRow("", self.recommendations_continue)
        self.recommendations_related = QCheckBox("Show pages related by title, hostname, or bookmark folder terms", self)
        self.recommendations_related.setChecked(self._preference_bool(self.settings, "recommendations/show_related", True))
        self.recommendations_related.toggled.connect(lambda value: self.settings.set("recommendations/show_related", value))
        form.addRow("", self.recommendations_related)
        self.recommendations_note = QLabel(
            "Incognito tabs never collect or display recommendations. Hiding and pinning are saved locally. Related-page suggestions use word overlap, not semantic understanding.", self
        )
        self.recommendations_note.setWordWrap(True)
        form.addRow("Privacy", self.recommendations_note)
        actions = QHBoxLayout()
        self.manage_hidden_button = QPushButton("Manage Hidden Websites…", self)
        self.manage_hidden_button.clicked.connect(self._manage_hidden_recommendations)
        actions.addWidget(self.manage_hidden_button)
        self.clear_recommendation_data_button = QPushButton("Clear Recommendation Data…", self)
        self.clear_recommendation_data_button.clicked.connect(self._clear_recommendation_data)
        actions.addWidget(self.clear_recommendation_data_button)
        layout.addLayout(actions)
        if self.recommendation_controller is None or getattr(self.parent(), "_is_private", False):
            for widget in (self.recommendations_enabled, self.recommendations_history, self.recommendations_bookmarks,
                           self.recommendations_show_new_tab, self.recommendations_continue, self.recommendations_related,
                           self.manage_hidden_button, self.clear_recommendation_data_button):
                widget.setEnabled(False)
            self.recommendations_note.setText("Recommendations are unavailable in Incognito. Open a regular LightMq window to manage local recommendation preferences.")

    def _manage_hidden_recommendations(self):
        controller = self.recommendation_controller
        if controller is None:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Hidden Recommendations")
        dialog.resize(520, 380)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Websites hidden from local recommendations"))
        items = QListWidget(dialog)
        for record in controller.hidden_recommendations():
            label = record.get("title") or record.get("domain") or record.get("url_key", "")
            item = QListWidgetItem(f"{label}  ·  {record.get('domain', '')}")
            item.setData(Qt.ItemDataRole.UserRole, record.get("url_key", ""))
            items.addItem(item)
        layout.addWidget(items, 1)
        row = QHBoxLayout(); unhide = QPushButton("Unhide Selected", dialog); close = QPushButton("Close", dialog)
        row.addWidget(unhide); row.addStretch(); row.addWidget(close); layout.addLayout(row)
        def reveal_selected():
            item = items.currentItem()
            if item is None:
                return
            controller.reveal(str(item.data(Qt.ItemDataRole.UserRole)))
            items.takeItem(items.row(item))
        unhide.clicked.connect(reveal_selected); close.clicked.connect(dialog.accept)
        dialog.exec()

    def _clear_recommendation_data(self):
        controller = self.recommendation_controller
        if controller is None:
            return
        answer = QMessageBox.question(
            self, "Clear Recommendation Data",
            "Remove pinned shortcuts, hidden recommendations, and local recommendation feedback? This does not clear history, bookmarks, cookies, login sessions, downloads, or session files.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            controller.clear_data()
            QMessageBox.information(self, "Recommendation Data Cleared", "Local recommendation feedback was removed. Browser history and bookmarks were preserved.")

    def _advanced(self, layout):
        form = self._page(layout, "Advanced", "Zoom and application preferences")
        self.zoom = QComboBox(); self.zoom.addItems([f"{value}%" for value in BrowserSettings.ZOOMS]); self.zoom.setCurrentText(f"{int(self.settings.default_zoom()*100)}%")
        self.zoom.currentTextChanged.connect(lambda text: self.settings.set("web/default_zoom", int(text.rstrip("%"))))
        form.addRow("Default page zoom", self.zoom)
        reset = QPushButton("Reset Settings…"); reset.clicked.connect(self._reset)
        form.addRow("Preferences", reset)

    def _reset(self):
        if QMessageBox.question(self, "Reset Settings", "Reset browser preferences? Cookies, login sessions, history, downloads, and session files will be preserved.") == QMessageBox.StandardButton.Yes:
            keys = ("appearance/theme", "appearance/accent_color", "appearance/custom_base_color", "appearance/custom_brightness", "appearance/recent_colors", "appearance/toolbar_density", "general/new_tab_behavior", "search/default_provider", "search/custom_template", "web/default_zoom", "downloads/default_directory", "downloads/ask_before_saving", "pdf/open_in_browser", "bookmarks_bar_visible", "appearance/new_tab_shortcuts", "recommendations/enabled", "recommendations/source_history", "recommendations/source_bookmarks", "recommendations/show_new_tab", "recommendations/show_continue", "recommendations/show_related")
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
                window._browser_settings.changed.emit("pdf/open_in_browser", True)
                if not window._is_private: window.bookmarks_bar.hide()
            QMessageBox.information(self, "Settings reset", "Preferences reset to safe defaults. Browser data was preserved.")
