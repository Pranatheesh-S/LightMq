"""Native settings for session restoration and its startup fallback."""

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QRadioButton,
    QVBoxLayout,
)

from browser.storage.settings import StartupMode, StartupSettings


class StartupSettingsDialog(QDialog):
    """Edit restoration and fallback preferences in one existing settings window."""

    def __init__(self, settings: StartupSettings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle("Settings — On Startup")
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("On Startup", self))

        self.restore_checkbox = QCheckBox("Restore Previous Session", self)
        self.restore_checkbox.setChecked(settings.restore_previous_session())
        self.restore_checkbox.setToolTip(
            "Reopen tabs from the previous normal browsing session at startup."
        )
        layout.addWidget(self.restore_checkbox)
        layout.addWidget(
            QLabel("Reopen tabs from your last browsing session.", self)
        )
        self.recovery_note = QLabel(
            "Crash recovery is separate. After an unexpected exit, LightMq may still "
            "offer the last recovery snapshot even when this option is off.",
            self,
        )
        self.recovery_note.setWordWrap(True)
        layout.addWidget(self.recovery_note)

        layout.addWidget(QLabel("When session restoration is off:", self))
        self.new_tab_radio = QRadioButton("Open a new tab", self)
        self.homepage_radio = QRadioButton("Open a specific homepage", self)
        self.fallback_group = QButtonGroup(self)
        self.fallback_group.addButton(self.new_tab_radio)
        self.fallback_group.addButton(self.homepage_radio)
        layout.addWidget(self.new_tab_radio)
        layout.addWidget(self.homepage_radio)

        self.homepage_edit = QLineEdit(settings.homepage(), self)
        self.homepage_edit.setPlaceholderText("https://example.com")
        form = QFormLayout()
        form.addRow("Homepage URL", self.homepage_edit)
        layout.addLayout(form)

        if settings.fallback_mode() is StartupMode.HOMEPAGE:
            self.homepage_radio.setChecked(True)
        else:
            self.new_tab_radio.setChecked(True)
        self.homepage_edit.setEnabled(self.homepage_radio.isChecked())

        self.restore_checkbox.toggled.connect(settings.set_restore_previous_session)
        self.new_tab_radio.toggled.connect(self._fallback_changed)
        self.homepage_radio.toggled.connect(self._fallback_changed)
        self.homepage_edit.editingFinished.connect(self._save_homepage)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        self.buttons.rejected.connect(self.accept)
        layout.addWidget(self.buttons)

    def _fallback_changed(self, _checked: bool) -> None:
        """Persist a selected fallback immediately and update homepage editing."""
        self.homepage_edit.setEnabled(self.homepage_radio.isChecked())
        if self.new_tab_radio.isChecked():
            self._settings.set_fallback_mode(StartupMode.NEW_TAB)
        elif self.homepage_radio.isChecked():
            self._settings.set_fallback_mode(StartupMode.HOMEPAGE)

    def _save_homepage(self) -> None:
        """Persist a valid homepage as soon as the field loses focus or Enter is pressed."""
        try:
            self._settings.set_homepage(self.homepage_edit.text())
        except ValueError as error:
            QMessageBox.warning(self, "Invalid homepage", str(error))
