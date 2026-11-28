"""Native manager for profile-installed Manifest V3 extensions."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot, QUrl
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from browser.features.extensions.extension_controller import ExtensionController
from browser.features.extensions.extension_compatibility import analyze_extension
from browser.features.extensions.extension_diagnostics import collect_extension_diagnostics
from browser.features.extensions.extension_assets import load_extension_icon
from browser.features.extensions.extension_updates import compare_local_update
from browser.features.extensions.package_inspector import (
    ExtensionPackage,
    inspect_extension_package,
)
from browser.features.extensions.permission_analyzer import analyze_permissions
from browser.features.extensions.webstore_integration import (
    WebStoreListing,
    recognize_webstore_listing,
    webstore_install_limitation,
)
from browser.ui.icons.icon_manager import IconManager
from browser.webengine.web_view import WebView


class _InspectionSignals(QObject):
    completed = Signal(object, str)


class _PackageInspectionWorker(QRunnable):
    """Read and validate a selected package away from the GUI thread."""

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path
        self.signals = _InspectionSignals()

    @Slot()
    def run(self) -> None:
        try:
            package = inspect_extension_package(self.path)
            self.signals.completed.emit(package, "")
        except (OSError, RuntimeError, ValueError) as error:
            self.signals.completed.emit(None, str(error))


class ExtensionsDialog(QDialog):
    """Review, install, enable, inspect, and remove local extensions."""

    def __init__(self, controller: ExtensionController, parent=None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.settings = controller.settings
        self._selected_id = ""
        self._inspection_worker: _PackageInspectionWorker | None = None
        self._inspection_mode = "install"
        self._inspection_path = ""
        self._update_extension_id = ""
        self._webstore_listing: WebStoreListing | None = None
        self.setWindowTitle("Extensions")
        self.setMinimumSize(760, 560)
        self._build_ui()
        self.controller.extensions_changed.connect(self.refresh)
        self.controller.operation_finished.connect(self._on_operation_finished)
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        heading = QLabel("Extensions", self)
        heading.setStyleSheet("font-size:20px;font-weight:650;")
        root.addWidget(heading)
        root.addWidget(
            QLabel(
                "Manage extensions installed in LightMq’s regular browser profile. "
                "Extensions are unavailable in Incognito.",
                self,
            )
        )

        controls = QHBoxLayout()
        self.install_zip_button = QPushButton("Install from ZIP…", self)
        self.install_folder_button = QPushButton("Install from Folder…", self)
        self.developer_mode = QCheckBox("Developer Mode", self)
        self.developer_mode.setChecked(
            self.settings.value("extensions/developer_mode", False, type=bool)
        )
        self.load_unpacked_button = QPushButton("Load Unpacked…", self)
        self.load_unpacked_button.setVisible(self.developer_mode.isChecked())
        self.install_zip_button.clicked.connect(self._choose_zip)
        self.install_folder_button.clicked.connect(self._choose_install_folder)
        self.load_unpacked_button.clicked.connect(self._choose_unpacked_folder)
        self.developer_mode.toggled.connect(self._set_developer_mode)
        controls.addWidget(self.install_zip_button)
        controls.addWidget(self.install_folder_button)
        controls.addStretch(1)
        controls.addWidget(self.load_unpacked_button)
        controls.addWidget(self.developer_mode)
        root.addLayout(controls)

        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Search installed extensions…")
        self.search_input.textChanged.connect(lambda _text: self.refresh())
        root.addWidget(self.search_input)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.extension_list = QListWidget(splitter)
        self.extension_list.setMinimumWidth(245)
        self.extension_list.currentItemChanged.connect(self._selection_changed)

        details = QVBoxLayout()
        self.name_label = QLabel("Select an extension", self)
        self.name_label.setWordWrap(True)
        self.name_label.setStyleSheet("font-size:18px;font-weight:600;")
        details.addWidget(self.name_label)
        self.description_label = QLabel("", self)
        self.description_label.setWordWrap(True)
        details.addWidget(self.description_label)
        self.status_label = QLabel("", self)
        self.status_label.setWordWrap(True)
        details.addWidget(self.status_label)
        self.permissions_label = QLabel("", self)
        self.permissions_label.setWordWrap(True)
        self.permissions_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        details.addWidget(self.permissions_label)
        self.compatibility_label = QLabel(
            "Qt WebEngine accepts Manifest V3 packages but does not expose a per-API "
            "support matrix. Declared permissions are shown for review; a package may "
            "still use unsupported Chrome APIs. This installed Qt WebEngine build crashes "
            "when changing extension enabled state, so LightMq keeps extensions disabled "
            "until a safe Qt runtime is available.",
            self,
        )
        self.compatibility_label.setWordWrap(True)
        details.addWidget(self.compatibility_label)
        self.manifest_features_label = QLabel("", self)
        self.manifest_features_label.setWordWrap(True)
        details.addWidget(self.manifest_features_label)
        details.addStretch(1)

        actions = QHBoxLayout()
        self.enabled_checkbox = QCheckBox("Enabled", self)
        self.enabled_checkbox.toggled.connect(self._toggle_enabled)
        self.popup_button = QPushButton("Open action popup", self)
        IconManager.set_widget_icon(self.popup_button, "extensions", 16)
        self.uninstall_button = QPushButton("Uninstall", self)
        self.diagnostics_button = QPushButton("Diagnostics…", self)
        self.update_button = QPushButton("Compare Local Update…", self)
        self.uninstall_button.setVisible(False)
        self.diagnostics_button.setEnabled(False)
        self.update_button.setVisible(False)
        self.popup_button.clicked.connect(self._open_selected_popup)
        self.uninstall_button.clicked.connect(self._uninstall_selected)
        self.diagnostics_button.clicked.connect(self._show_selected_diagnostics)
        self.update_button.clicked.connect(self._choose_local_update)
        actions.addWidget(self.enabled_checkbox)
        actions.addStretch(1)
        actions.addWidget(self.diagnostics_button)
        actions.addWidget(self.update_button)
        actions.addWidget(self.popup_button)
        actions.addWidget(self.uninstall_button)
        details.addLayout(actions)

        detail_container = QWidget(self)
        detail_container.setLayout(details)
        splitter.addWidget(self.extension_list)
        splitter.addWidget(detail_container)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

        self.empty_label = QLabel(
            "No user extensions are installed. Use Install from ZIP or Folder, "
            "or enable Developer Mode to load a temporary unpacked extension.",
            self,
        )
        self.empty_label.setWordWrap(True)
        root.addWidget(self.empty_label)

        footer = QHBoxLayout()
        self.operation_label = QLabel("", self)
        self.operation_label.setWordWrap(True)
        footer.addWidget(self.operation_label, 1)
        self.close_button = QPushButton("Close", self)
        self.close_button.clicked.connect(self.close)
        footer.addWidget(self.close_button)
        root.addLayout(footer)

    def refresh(self) -> None:
        """Rebuild the list from the profile manager while preserving selection."""
        selected_id = self._selected_id
        self.extension_list.blockSignals(True)
        self.extension_list.clear()
        entries = sorted(
            self.controller.user_extensions(),
            key=lambda item: item.name().casefold(),
        )
        query = self.search_input.text().strip().casefold()
        if query:
            entries = [
                extension for extension in entries
                if query in extension.name().casefold()
                or query in extension.description().casefold()
                or query in extension.id().casefold()
            ]
        selected_row = -1
        for extension in entries:
            runtime_enabled = self.controller.is_enabled(extension.id())
            if runtime_enabled:
                state = "Enabled"
            elif extension.error():
                state = "Error"
            else:
                state = "Disabled"
            item = QListWidgetItem(f"{extension.name() or 'Unnamed extension'} — {state}")
            item.setData(Qt.ItemDataRole.UserRole, extension.id())
            item.setToolTip(extension.description() or extension.path())
            icon = load_extension_icon(self.controller.installed_package(extension))
            item.setIcon(icon if not icon.isNull() else IconManager.icon("extensions", 18))
            self.extension_list.addItem(item)
            if extension.id() == selected_id:
                selected_row = self.extension_list.count() - 1
        self.empty_label.setVisible(not entries)
        if not entries and query:
            self.empty_label.setText("No extensions match this search.")
        else:
            self.empty_label.setText(
                "No user extensions are installed. Use Install from ZIP or Folder, "
                "or enable Developer Mode to load a temporary unpacked extension."
            )
        if selected_row >= 0:
            self.extension_list.setCurrentRow(selected_row)
        elif entries:
            self.extension_list.setCurrentRow(0)
        else:
            self._selected_id = ""
            self._render_selection(None)
        self.extension_list.blockSignals(False)
        if selected_row >= 0 or entries:
            self._render_selection(self._selected_extension())
        self._set_busy(self.controller.busy)

    def _selected_extension(self):
        item = self.extension_list.currentItem()
        if item is None:
            return None
        return self.controller.extension(str(item.data(Qt.ItemDataRole.UserRole) or ""))

    def _selection_changed(self, current, _previous) -> None:
        self._render_selection(
            self.controller.extension(str(current.data(Qt.ItemDataRole.UserRole) or ""))
            if current is not None else None
        )

    def _render_selection(self, extension) -> None:
        if extension is None:
            self._selected_id = ""
            self.name_label.setText("Select an extension")
            self.description_label.setText("")
            self.status_label.setText("")
            self.permissions_label.setText("")
            self.compatibility_label.setText("")
            self.manifest_features_label.setText("")
            self.enabled_checkbox.blockSignals(True)
            self.enabled_checkbox.setChecked(False)
            self.enabled_checkbox.setEnabled(False)
            self.enabled_checkbox.blockSignals(False)
            self.popup_button.setEnabled(False)
            self.popup_button.setVisible(False)
            self.uninstall_button.setEnabled(False)
            return

        self._selected_id = extension.id()
        package = self.controller.installed_package(extension)
        version = f" — version {package.version}" if package else ""
        self.name_label.setText(f"{extension.name() or 'Unnamed extension'}{version}")
        self.description_label.setText(extension.description() or "No description provided.")
        runtime_enabled = self.controller.is_enabled(extension.id())
        if extension.error():
            state_text = f"Load or installation error: {extension.error()}"
        elif runtime_enabled:
            state_text = "Enabled"
        else:
            state_text = "Disabled. Enable/disable is unavailable in this Qt WebEngine build."
        origin = (
            "Installed in this profile"
            if self.controller.is_user_installed(extension)
            else "Temporary Developer Mode load; removed when LightMq exits"
        )
        self.status_label.setText(f"{origin}\n{state_text}\nID: {extension.id()}")
        if package:
            findings = analyze_permissions(package)
            entries = "\n".join(
                f"• {item.scope}: {item.value} — {item.explanation}"
                + (" [Sensitive]" if item.elevated and not item.broad else "")
                + (" [Broad access]" if item.broad else "")
                + (" [Optional]" if item.optional else "")
                for item in findings
            )
            self.permissions_label.setText(
                "Manifest-declared permissions (informational; Qt applies its own permission behavior):\n"
                + entries
            )
            report = analyze_extension(
                package,
                self.controller.profile,
                extension_execution_blocked=self.controller.extension_execution_blocked,
            )
            self.compatibility_label.setText(
                f"Compatibility: {report.status.value}\n"
                f"PySide {report.pyside_version} · Qt {report.qt_version} · "
                f"Chromium {report.chromium_version}\n"
                + "\n".join(report.evidence)
            )
            metadata = [
                f"Manifest V{package.manifest_version}",
                f"Background service worker: {package.background_service_worker or 'not declared'}",
                f"Action popup: {package.action_popup or 'not declared'}",
                f"Icons: {', '.join(path for _size, path in package.icons) or 'not declared'}",
                f"Web-accessible resources: {len(package.web_accessible_resources)}",
                f"Content Security Policy: {package.content_security_policy or 'not declared'}",
                f"Other manifest keys: {', '.join(package.other_manifest_keys) or 'none'}",
            ]
            self.manifest_features_label.setText("\n".join(metadata))
        else:
            self.permissions_label.setText(
                "Manifest permission details are unavailable for this extension."
            )
            self.compatibility_label.setText("Compatibility: Unknown — manifest metadata unavailable.")
            self.manifest_features_label.setText("")

        self.enabled_checkbox.blockSignals(True)
        self.enabled_checkbox.setText("Enabled" if runtime_enabled else "Enable / Disable unavailable")
        self.enabled_checkbox.setToolTip(
            "Qt WebEngine's enabled-state setter crashes in this installed runtime."
        )
        self.enabled_checkbox.setChecked(runtime_enabled)
        self.enabled_checkbox.setEnabled(False)
        self.enabled_checkbox.blockSignals(False)
        popup_url = self.controller.open_popup_url(extension.id())
        popup_declared = bool(package and package.action_popup)
        self.popup_button.setVisible(bool(popup_url) or popup_declared)
        self.popup_button.setEnabled(bool(popup_url) and not self.controller.busy)
        self.popup_button.setToolTip(
            "Open the extension popup reported by Qt."
            if popup_url else
            "This extension declares a popup, but it cannot run until Qt safely supports enabling extensions."
            if popup_declared else "No extension popup is available."
        )
        self.uninstall_button.setVisible(self.controller.is_user_installed(extension))
        self.uninstall_button.setEnabled(
            self.controller.is_user_installed(extension) and not self.controller.busy
        )
        self.diagnostics_button.setEnabled(not self.controller.busy)
        self.update_button.setVisible(self.controller.is_user_installed(extension))
        self.update_button.setEnabled(
            self.controller.is_user_installed(extension) and not self.controller.busy
        )

    def _set_developer_mode(self, enabled: bool) -> None:
        self.settings.setValue("extensions/developer_mode", bool(enabled))
        self.settings.sync()
        self.load_unpacked_button.setVisible(enabled)

    def _choose_zip(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Install Extension from ZIP", "", "ZIP archives (*.zip)"
        )
        if path:
            self._inspect_path(Path(path), "install")

    def _choose_install_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Install Extension from Folder")
        if path:
            self._inspect_path(Path(path), "install")

    def _choose_unpacked_folder(self) -> None:
        if not self.developer_mode.isChecked():
            return
        path = QFileDialog.getExistingDirectory(self, "Load Unpacked Extension")
        if path:
            self._inspect_path(Path(path), "load")

    def inspect_webstore_listing(self, url: str) -> None:
        """Explain store limits and offer local ZIP/folder analysis."""
        listing = recognize_webstore_listing(url)
        if listing is None:
            QMessageBox.information(self, "Chrome Web Store", "This is not a recognized HTTPS extension listing.")
            return
        self._webstore_listing = listing
        listing_identity = (
            f"Listing ID from URL: {listing.extension_id} (not independently verified)"
            if listing.extension_id else "No valid extension ID could be read from this listing URL."
        )
        message = QMessageBox(self)
        message.setWindowTitle("View Compatibility in LightMq")
        message.setIcon(QMessageBox.Icon.Information)
        message.setText(listing_identity)
        message.setInformativeText(webstore_install_limitation())
        zip_button = message.addButton("Choose ZIP…", QMessageBox.ButtonRole.ActionRole)
        folder_button = message.addButton("Choose Folder…", QMessageBox.ButtonRole.ActionRole)
        message.addButton(QMessageBox.StandardButton.Cancel)
        message.exec()
        clicked = message.clickedButton()
        path = ""
        if clicked is zip_button:
            path, _ = QFileDialog.getOpenFileName(
                self, "Analyze an Authorized Local Extension ZIP", "", "ZIP archives (*.zip)"
            )
        elif clicked is folder_button:
            path = QFileDialog.getExistingDirectory(
                self, "Analyze an Authorized Local Extension Folder"
            )
        if path:
            self._inspect_path(Path(path), "webstore")

    def _choose_local_update(self) -> None:
        extension = self._selected_extension()
        if extension is None:
            return
        buttons = QMessageBox(self)
        buttons.setWindowTitle("Compare Local Extension Update")
        buttons.setText("Select a ZIP or an unpacked folder that you obtained from a source you trust.")
        zip_button = buttons.addButton("Choose ZIP…", QMessageBox.ButtonRole.ActionRole)
        folder_button = buttons.addButton("Choose Folder…", QMessageBox.ButtonRole.ActionRole)
        buttons.addButton(QMessageBox.StandardButton.Cancel)
        buttons.exec()
        path = ""
        if buttons.clickedButton() is zip_button:
            path, _ = QFileDialog.getOpenFileName(self, "Compare Local Update", "", "ZIP archives (*.zip)")
        elif buttons.clickedButton() is folder_button:
            path = QFileDialog.getExistingDirectory(self, "Compare Local Update Folder")
        if path:
            self._update_extension_id = extension.id()
            self._inspect_path(Path(path), "update")

    def _inspect_path(self, path: Path, mode: str) -> None:
        if self._inspection_worker is not None or self.controller.busy:
            return
        self._inspection_mode = mode
        self._inspection_path = str(path)
        self.operation_label.setText("Checking the extension manifest and package paths…")
        self._set_busy(True)
        worker = _PackageInspectionWorker(path)
        worker.signals.completed.connect(self._inspection_finished)
        self._inspection_worker = worker
        QThreadPool.globalInstance().start(worker)

    @Slot(object, str)
    def _inspection_finished(self, package: ExtensionPackage | None, error: str) -> None:
        self._inspection_worker = None
        self._set_busy(False)
        if package is None:
            self.operation_label.setText(error)
            QMessageBox.warning(self, "Invalid Extension Package", error)
            return
        if self._inspection_mode == "webstore":
            self._show_package_compatibility(package)
            return
        if self._inspection_mode == "update":
            self._show_update_comparison(package)
            return
        if self._inspection_mode == "load" and not package.path.is_dir():
            QMessageBox.warning(
                self, "Unpacked Folder Required", "Developer Mode loads an unpacked folder only."
            )
            return
        enable_after = self._review_package(package, self._inspection_mode)
        if enable_after is None:
            return
        started = (
            self.controller.load_unpacked(package, enable_after)
            if self._inspection_mode == "load"
            else self.controller.install(package, enable_after)
        )
        if started:
            self.operation_label.setText("Waiting for Qt WebEngine…")
            self._set_busy(True)

    def _review_package(self, package: ExtensionPackage, mode: str) -> bool | None:
        """Show declared permissions before a package can be enabled."""
        operation = "Load" if mode == "load" else "Install"
        findings = analyze_permissions(package)
        permissions = "\n".join(
            f"• {item.scope}: {item.value} — {item.explanation}"
            + (" [Sensitive]" if item.elevated and not item.broad else "")
            + (" [BROAD SITE ACCESS]" if item.broad else "")
            + (" [Optional]" if item.optional else "")
            for item in findings
        )
        message = QMessageBox(self)
        message.setIcon(QMessageBox.Icon.Warning)
        message.setWindowTitle(f"Review {operation.lower()} permissions")
        message.setText(f"{operation} “{package.name}” version {package.version}?")
        message.setInformativeText(
            f"{package.description or 'No description provided.'}\n\n"
            "Review these manifest-declared capabilities. Qt WebEngine does not publish "
            "a per-API compatibility list, and some Chrome extension APIs may not work."
        )
        message.setDetailedText(permissions)
        accepted = message.addButton(
            f"{operation} Disabled", QMessageBox.ButtonRole.AcceptRole
        )
        message.addButton(QMessageBox.StandardButton.Cancel)
        message.setDefaultButton(accepted)
        message.exec()
        clicked = message.clickedButton()
        if clicked is accepted:
            return False
        return None

    def _show_package_compatibility(self, package: ExtensionPackage) -> None:
        """Show listing-package analysis without implying the package came from Google."""
        report = analyze_extension(
            package, self.controller.profile,
            extension_execution_blocked=self.controller.extension_execution_blocked,
        )
        permission_lines = "\n".join(
            f"{finding.scope}: {finding.value}"
            + (" — broad access" if finding.broad else "")
            + (" — sensitive" if finding.elevated and not finding.broad else "")
            for finding in analyze_permissions(package)
        )
        QMessageBox.information(
            self,
            "Local Package Compatibility",
            f"{package.name} · {package.version}\n"
            f"Compatibility: {report.status.value}\n"
            f"PySide {report.pyside_version} · Qt {report.qt_version} · Chromium {report.chromium_version}\n\n"
            + "\n".join(report.evidence)
            + "\n\nManifest permissions:\n" + permission_lines
            + "\n\nThis step only analyzes the user-selected local file. It does not verify the file's publisher or install it."
        )

    def _show_update_comparison(self, candidate: ExtensionPackage) -> None:
        """Compare a local package to the current install without replacing files."""
        extension = self.controller.extension(self._update_extension_id)
        current = self.controller.installed_package(extension) if extension else None
        if current is None:
            QMessageBox.warning(self, "Update Comparison", "The selected installed extension is no longer available.")
            return
        result = compare_local_update(current, candidate)
        changes = [
            f"Version: {current.version} → {candidate.version}",
            f"Result: {result.status}",
            result.explanation,
        ]
        if result.added_permissions:
            changes.append("Added permissions: " + ", ".join(result.added_permissions))
        if result.added_hosts:
            changes.append("Added host permissions: " + ", ".join(result.added_hosts))
        if result.added_optional_permissions:
            changes.append(
                "Added optional permissions: " + ", ".join(result.added_optional_permissions)
            )
        if result.added_optional_hosts:
            changes.append("Added optional hosts: " + ", ".join(result.added_optional_hosts))
        if result.update_available:
            changes.append(
                "No update was installed. LightMq will not modify Qt's extension directory "
                "because this Qt API has no verified rollback-safe replacement workflow."
            )
        QMessageBox.information(self, "Local Update Comparison", "\n\n".join(changes))

    def _show_selected_diagnostics(self) -> None:
        """Display Qt-reported state and clearly label checks that were not run."""
        report = self.controller.diagnostics(self._selected_id)
        if report is None:
            return
        text = [
            f"Extension: {report.name}",
            f"ID: {report.extension_id}",
            f"Manifest: {('V' + str(report.manifest_version)) if report.manifest_version else 'Unavailable'} · {report.version}",
            f"Installation: {report.installation}",
            f"Loaded: {report.loaded}",
            f"Enabled: {report.enabled}",
            f"Compatibility: {report.compatibility.status.value}",
            f"Runtime versions: PySide {report.compatibility.pyside_version}; Qt {report.compatibility.qt_version}; Chromium {report.compatibility.chromium_version}",
            "\nRuntime observations:",
            *(f"• {name}: {value}" for name, value in report.runtime_checks),
            "\nQt-reported/manager errors:",
            *(f"• {error}" for error in report.error_messages),
            "\nManifest features:",
            *(f"• {feature}" for feature in report.manifest_features),
            "\nCompatibility evidence:",
            *(f"• {item}" for item in report.compatibility.evidence),
            "\nCapability registry:",
            *(
                f"• {item.capability}: {item.status} — {item.evidence}"
                for item in report.compatibility.capabilities
            ),
        ]
        message = QMessageBox(self)
        message.setWindowTitle("Extension Diagnostics")
        message.setText(report.name)
        message.setDetailedText("\n".join(text))
        message.setStandardButtons(QMessageBox.StandardButton.Close)
        message.exec()

    def _toggle_enabled(self, enabled: bool) -> None:
        extension = self.controller.extension(self._selected_id)
        if extension is None:
            self.refresh()
            return
        if enabled and not self._confirm_enable(extension):
            self._render_selection(extension)
            return
        if not self.controller.set_enabled(
            self._selected_id, enabled, user_approved=(enabled is True)
        ):
            self._render_selection(self.controller.extension(self._selected_id))

    def _confirm_enable(self, extension) -> bool:
        package = self.controller.installed_package(extension)
        if package:
            details = "\n".join(package.requested_capabilities)
        else:
            details = "The extension manifest is unavailable; requested permissions could not be listed."
        answer = QMessageBox.question(
            self,
            "Enable Extension?",
            f"Enable “{extension.name()}” in all regular tabs?\n\n"
            "This permits the extension's installed scripts and APIs to run. "
            "Review its manifest-declared capabilities before continuing.\n\n"
            f"{details}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _uninstall_selected(self) -> None:
        extension = self.controller.extension(self._selected_id)
        if extension is None:
            self.refresh()
            return
        answer = QMessageBox.question(
            self,
            "Uninstall Extension?",
            f"Remove “{extension.name()}” and its profile-installed extension files?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            if self.controller.uninstall(extension.id()):
                self.operation_label.setText("Uninstalling…")
                self._set_busy(True)

    def _open_selected_popup(self) -> None:
        extension_id = self._selected_id
        url_text = self.controller.open_popup_url(extension_id)
        if not url_text:
            self.refresh()
            return
        extension = self.controller.extension(extension_id)
        if extension is None:
            self.refresh()
            return
        popup = QDialog(self, Qt.WindowType.Tool)
        popup.setWindowTitle(extension.name() or "Extension")
        popup.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        popup.resize(360, 480)
        layout = QVBoxLayout(popup)
        view = WebView(profile=self.controller.profile, parent=popup)
        view.setUrl(QUrl(url_text))
        layout.addWidget(view)
        popup.show()

    def _on_operation_finished(
        self, operation: str, _extension_id: str, message: str, success: bool
    ) -> None:
        self._set_busy(False)
        self.operation_label.setText(message)
        self.refresh()
        if not success:
            QMessageBox.warning(self, f"Extension {operation.title()} Failed", message)

    def _set_busy(self, busy: bool) -> None:
        self.install_zip_button.setEnabled(not busy)
        self.install_folder_button.setEnabled(not busy)
        self.developer_mode.setEnabled(not busy)
        self.search_input.setEnabled(not busy)
        self.load_unpacked_button.setEnabled(not busy and self.developer_mode.isChecked())
        self.extension_list.setEnabled(not busy)
        self.close_button.setEnabled(True)
        if hasattr(self, "uninstall_button"):
            extension = self._selected_extension()
            self.uninstall_button.setEnabled(
                bool(not busy and extension is not None and self.controller.is_user_installed(extension))
            )
            popup_available = bool(
                extension is not None and self.controller.open_popup_url(extension.id())
            )
            self.popup_button.setEnabled(not busy and popup_available)

