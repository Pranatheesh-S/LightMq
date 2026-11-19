"""Bookmark editor and confirmation dialog for LightMq Browser."""

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from browser.features.bookmarks.bookmark_manager import BookmarkManager


class BookmarkDialog(QDialog):
    """Dialog allowing the user to inspect, edit title, or remove a bookmark."""

    def __init__(
        self,
        title: str,
        url: str,
        bookmark_manager: BookmarkManager | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Edit Bookmark")
        self.resize(380, 160)
        self._manager = bookmark_manager or BookmarkManager.get_instance()
        self._url = url
        self._title = title

        self._init_ui()

    def _init_ui(self) -> None:
        """Construct the dialog form."""
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.edit_name = QLineEdit(self._title, self)
        self.edit_url = QLineEdit(self._url, self)
        self.edit_url.setReadOnly(True)

        form_layout.addRow("Name:", self.edit_name)
        form_layout.addRow("URL:", self.edit_url)
        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.btn_remove = QPushButton("Remove", self)
        self.btn_remove.clicked.connect(self._on_remove_clicked)
        button_box.addButton(self.btn_remove, QDialogButtonBox.ButtonRole.DestructiveRole)

        button_box.accepted.connect(self._on_save_clicked)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _on_save_clicked(self) -> None:
        """Save or update the bookmark."""
        new_title = self.edit_name.text().strip()
        self._manager.remove_bookmark(self._url)
        self._manager.add_bookmark(new_title or self._title, self._url)
        self.accept()

    def _on_remove_clicked(self) -> None:
        """Remove the bookmark."""
        self._manager.remove_bookmark(self._url)
        self.accept()
