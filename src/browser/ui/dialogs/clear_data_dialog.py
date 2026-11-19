"""Clear browsing data dialog for LightMq Browser."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class ClearDataDialog(QDialog):
    """Dialog allowing user to choose which browsing data to clear."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Clear Browsing Data")
        self.resize(380, 240)
        self._init_ui()

    def _init_ui(self) -> None:
        """Construct checkboxes and action buttons."""
        layout = QVBoxLayout(self)

        info_label = QLabel("Select the types of browsing data you wish to clear:")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        self.cb_history = QCheckBox("Browsing history", self)
        self.cb_history.setChecked(True)
        layout.addWidget(self.cb_history)

        self.cb_cache = QCheckBox("Cached images and files", self)
        self.cb_cache.setChecked(True)
        layout.addWidget(self.cb_cache)

        self.cb_cookies = QCheckBox("Cookies and other site data", self)
        self.cb_cookies.setChecked(True)
        layout.addWidget(self.cb_cookies)

        self.cb_closed_tabs = QCheckBox("Recently closed tabs stack", self)
        self.cb_closed_tabs.setChecked(True)
        layout.addWidget(self.cb_closed_tabs)

        layout.addStretch()

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        button_box.button(QDialogButtonBox.StandardButton.Ok).setText("Clear Data")
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    @property
    def clear_history(self) -> bool:
        return self.cb_history.isChecked()

    @property
    def clear_cache(self) -> bool:
        return self.cb_cache.isChecked()

    @property
    def clear_cookies(self) -> bool:
        return self.cb_cookies.isChecked()

    @property
    def clear_closed_tabs(self) -> bool:
        return self.cb_closed_tabs.isChecked()
