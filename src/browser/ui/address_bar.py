"""Address bar component for user URL entry and current location display.

Subclasses QLineEdit to handle keyboard submission, text selection on focus,
and clean synchronization with WebEngine navigation events.
"""

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QAction, QFocusEvent
from PySide6.QtWidgets import QLineEdit, QSizePolicy

from browser.ui.icons.icon_manager import IconManager
from browser.ui.theme_palette import BrowserTheme


class AddressBar(QLineEdit):
    """Custom address bar (omnibox) for URL entry."""

    navigate_requested = Signal(str)

    def __init__(self, parent=None, icon_theme: BrowserTheme | None = None):
        super().__init__(parent)
        self._icon_theme=icon_theme
        self.setObjectName("addressBar")
        self.setMinimumWidth(180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
        self.setPlaceholderText("Search or enter address")
        self.setClearButtonEnabled(False)
        self._site_action=QAction("Search",self)
        self._site_action.setToolTip("Search or site information")
        IconManager.set_action_icon(self._site_action,"search",16,self._icon_theme)
        self.addAction(self._site_action,QLineEdit.ActionPosition.LeadingPosition)
        self._clear_action=QAction("Clear address",self)
        self._clear_action.setToolTip("Clear address")
        IconManager.set_action_icon(self._clear_action,"close",16,self._icon_theme)
        self._clear_action.triggered.connect(self.clear)
        self._clear_action.setVisible(False)
        self.addAction(self._clear_action,QLineEdit.ActionPosition.TrailingPosition)
        self.textChanged.connect(lambda value:self._clear_action.setVisible(bool(value)))

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
            if url_str in ("about:blank", "lightmq://newtab"):
                self.clear()
            else:
                self.setText(url_str)
            IconManager.set_action_icon(
                self._site_action,
                "lock" if url.scheme().lower() == "https" else "search",
                16,
                self._icon_theme,
            )

    def focusInEvent(self, event: QFocusEvent) -> None:
        """Select all text when the address bar receives keyboard focus."""
        super().focusInEvent(event)
        # Select all text for easy replacement
        self.selectAll()
