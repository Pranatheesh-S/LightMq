"""Native dialog for browser startup mode and homepage preferences."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
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
    """Edit startup behavior without introducing a separate settings framework."""

    def __init__(self, settings: StartupSettings, parent=None):
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle("Startup Settings")
        self.setMinimumWidth(430)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("On startup", self))
        self.new_tab_radio = QRadioButton("Open a new tab", self)
        self.homepage_radio = QRadioButton("Open a specific homepage", self)
        self.continue_radio = QRadioButton("Continue where I left off", self)
        self.mode_group = QButtonGroup(self)
        for index, radio in enumerate((self.new_tab_radio, self.homepage_radio, self.continue_radio)):
            self.mode_group.addButton(radio, index)
            layout.addWidget(radio)

        self.homepage_edit = QLineEdit(settings.homepage(), self)
        self.homepage_edit.setPlaceholderText("https://example.com")
        form = QFormLayout()
        form.addRow("Homepage URL", self.homepage_edit)
        layout.addLayout(form)

        current_mode = settings.mode()
        {
            StartupMode.NEW_TAB: self.new_tab_radio,
            StartupMode.HOMEPAGE: self.homepage_radio,
            StartupMode.CONTINUE: self.continue_radio,
        }[current_mode].setChecked(True)
        self.homepage_radio.toggled.connect(self.homepage_edit.setEnabled)
        self.homepage_edit.setEnabled(current_mode is StartupMode.HOMEPAGE)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.buttons.accepted.connect(self._save)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons, alignment=Qt.AlignmentFlag.AlignRight)

    def _save(self) -> None:
        """Validate and commit the selected startup preferences."""
        mode = (
            StartupMode.NEW_TAB if self.new_tab_radio.isChecked()
            else StartupMode.HOMEPAGE if self.homepage_radio.isChecked()
            else StartupMode.CONTINUE
        )
        try:
            self._settings.set(mode, self.homepage_edit.text())
        except ValueError as error:
            QMessageBox.warning(self, "Invalid homepage", str(error))
            return
        self.accept()
