"""Reusable, accessible QToolButton for browser chrome icons."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QToolButton, QWidget

from browser.ui.icons.icon_manager import IconManager
from browser.ui.theme_palette import BrowserTheme


class IconButton(QToolButton):
    """A compact button with a scalable icon and consistent focus behavior."""

    def __init__(
        self,
        icon_name: str,
        tooltip: str,
        parent: QWidget | None = None,
        button_size: int = 36,
        icon_size: int = 20,
        theme: BrowserTheme | None = None,
    ) -> None:
        super().__init__(parent)
        self._icon_theme = theme
        self.setProperty("lightmqIconButton", True)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.setAutoRaise(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedSize(button_size, button_size)
        self.setAccessibleName(tooltip)
        self.setToolTip(tooltip)
        self.set_icon_name(icon_name, icon_size, theme)

    def set_icon_name(
        self, icon_name: str, icon_size: int = 20, theme: BrowserTheme | None = None
    ) -> None:
        """Change the semantic icon without changing button behavior."""
        if theme is not None:
            self._icon_theme = theme
        IconManager.set_widget_icon(self, icon_name, icon_size, self._icon_theme)
        self.setProperty("lightmqIconButton", True)
        self.setIconSize(QSize(icon_size, icon_size))
