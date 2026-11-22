"""Apply the persisted Qt UI theme and accent color."""

from pathlib import Path

from PySide6.QtGui import QGuiApplication

from browser.storage.settings import BrowserSettings


class ThemeManager:
    """Application-wide QSS theme coordinator."""

    def __init__(self, settings: BrowserSettings, apply_global: bool = True):
        self.settings = settings
        self._apply_global=apply_global
        self.app = QGuiApplication.instance()
        if self.app is not None and self._apply_global:
            self.apply()
            hints = self.app.styleHints()
            if hasattr(hints, "colorSchemeChanged"):
                hints.colorSchemeChanged.connect(lambda _scheme: self.apply())

    def apply(self) -> None:
        if self.app is None or not self._apply_global:
            return
        choice = self.settings.theme()
        dark = choice == "dark"
        if choice == "system":
            scheme = self.app.styleHints().colorScheme()
            dark = str(scheme).lower().endswith("dark")
        name = "dark.qss" if dark else "light.qss"
        path = Path(__file__).parent / "themes" / name
        qss = path.read_text(encoding="utf-8") if path.exists() else ""
        accent = self.settings.ACCENTS[self.settings.accent()]
        compact = self.settings.get("appearance/toolbar_density", "Normal") == "Compact"
        spacing = "3px" if compact else "6px"
        padding = "2px" if compact else "4px"
        qss += f"\nQToolBar{{spacing:{spacing};padding:{padding};}}\nQToolButton:hover,QPushButton:hover,QCheckBox::indicator:checked{{border-color:{accent};}}\nQLineEdit:focus{{border-color:{accent};}}\nQTabBar::tab:selected{{border-bottom:2px solid {accent};}}"
        self.app.setStyleSheet(qss)
