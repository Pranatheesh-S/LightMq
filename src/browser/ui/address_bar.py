"""Address bar component for user URL entry and current location display.

Subclasses QLineEdit to handle keyboard submission, text selection on focus,
and clean synchronization with WebEngine navigation events.
"""

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QFocusEvent
from PySide6.QtWidgets import QLineEdit


class AddressBar(QLineEdit):
    """Custom address bar (omnibox) for URL entry."""

    navigate_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Enter URL or domain (e.g. example.com)...")
        self.setClearButtonEnabled(True)

        # Trigger navigation on Enter key
        self.returnPressed.connect(self._on_return_pressed)

    def _on_return_pressed(self) -> None:
        """Handle Enter key press by emitting navigate_requested."""
        text = self.text().strip()
        if text:
            self.navigate_requested.emit(text)

    def set_url(self, url: QUrl) -> None:
        """Update the displayed URL unless the user is actively typing.

        Args:
            url: Current QUrl of the active page.
        """
        # Avoid overwriting user text if the address bar is currently focused
        if not self.hasFocus():
            url_str = url.toString()
            if url_str == "about:blank":
                self.clear()
            else:
                self.setText(url_str)

    def focusInEvent(self, event: QFocusEvent) -> None:
        """Select all text when the address bar receives keyboard focus."""
        super().focusInEvent(event)
        # Select all text for easy replacement
        self.selectAll()
