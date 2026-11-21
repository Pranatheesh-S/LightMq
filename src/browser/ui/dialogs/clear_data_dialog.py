"""Confirmed, truthful clear-browsing-data selection dialog."""

from datetime import datetime, timedelta, timezone

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QLabel, QMessageBox,
    QVBoxLayout, QWidget,
)


class ClearDataDialog(QDialog):
    """Choose supported history and profile-data categories before clearing."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Clear Browsing Data")
        self.resize(460, 370)
        self._init_ui()

    def _init_ui(self) -> None:
        """Build the date range, category controls, warnings, and buttons."""
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Time range for browsing history:"))
        self.period = QComboBox(self)
        for label, value in (("Last hour", "hour"), ("Last 24 hours", "day"),
                             ("Last 7 days", "week"), ("Last 30 days", "month"),
                             ("All time", "all")):
            self.period.addItem(label, value)
        self.period.setCurrentIndex(4)
        layout.addWidget(self.period)

        self.cb_history = QCheckBox("Browsing history (selected time range)", self)
        self.cb_history.setChecked(True)
        layout.addWidget(self.cb_history)
        self.cb_cookies = QCheckBox("Cookies (all dates; may sign you out)", self)
        self.cb_cookies.setChecked(True)
        layout.addWidget(self.cb_cookies)
        self.cb_cache = QCheckBox("HTTP cache (all dates)", self)
        self.cb_cache.setChecked(True)
        layout.addWidget(self.cb_cache)
        self.cb_permissions = QCheckBox("Website permission decisions (all decisions)", self)
        layout.addWidget(self.cb_permissions)

        note = QLabel(
            "The time range applies only to LightMq history. Cookie, cache, and permission "
            "APIs clear the selected category for all dates. This does not clear Local Storage, "
            "IndexedDB, per-tab Back/Forward entries, or downloaded files."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Clear Data")
        buttons.accepted.connect(self._confirm)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def clear_history(self) -> bool:
        """Whether to remove application history."""
        return self.cb_history.isChecked()

    @property
    def clear_cache(self) -> bool:
        """Whether to request full HTTP-cache clearing."""
        return self.cb_cache.isChecked()

    @property
    def clear_cookies(self) -> bool:
        """Whether to request deletion of all profile cookies."""
        return self.cb_cookies.isChecked()

    @property
    def clear_permissions(self) -> bool:
        """Whether to reset saved profile permission decisions."""
        return self.cb_permissions.isChecked()

    def history_range(self) -> tuple[datetime | None, datetime | None]:
        """Return UTC bounds for the selected history time range."""
        now = datetime.now(timezone.utc)
        durations = {
            "hour": timedelta(hours=1), "day": timedelta(hours=24),
            "week": timedelta(days=7), "month": timedelta(days=30),
        }
        duration = durations.get(str(self.period.currentData()))
        return (now - duration, None) if duration else (None, None)

    def _confirm(self) -> None:
        """Require explicit consent and explain the actual category scope."""
        selected: list[str] = []
        if self.clear_history:
            selected.append(f"Browsing history ({self.period.currentText().lower()})")
        if self.clear_cookies:
            selected.append("all cookies (you may be signed out)")
        if self.clear_cache:
            selected.append("the full HTTP cache")
        if self.clear_permissions:
            selected.append("all website permission decisions reported by Qt")
        if not selected:
            QMessageBox.information(self, "Nothing selected", "Select at least one data category to clear.")
            return
        answer = QMessageBox.warning(
            self,
            "Confirm data deletion",
            "Clear the following data?\n\n• " + "\n• ".join(selected)
            + "\n\nCookies and cache are cleared for all dates when selected.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.accept()
