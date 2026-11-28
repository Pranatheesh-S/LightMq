"""Application-wide theme resolution, live preview, and QSS application."""

from __future__ import annotations

from browser.utils.paths import resource_path

from PySide6.QtGui import QGuiApplication

from browser.storage.settings import BrowserSettings
from browser.ui.icons.icon_manager import IconManager
from browser.ui.theme_palette import BrowserTheme, build_palette, palette_stylesheet


class ThemeManager:
    """Resolve persisted theme preferences into semantic UI palette tokens."""

    def __init__(self, settings: BrowserSettings, apply_global: bool = True):
        self.settings=settings
        self._apply_global=apply_global
        self.app=QGuiApplication.instance()
        self._preview:tuple[str,str,bool]|None=None
        if self.app is not None and self._apply_global:
            self.apply()
            hints=self.app.styleHints()
            if hasattr(hints,"colorSchemeChanged"):
                hints.colorSchemeChanged.connect(lambda _scheme:self.apply() if not self._preview else None)

    def palette(self,mode:str|None=None,base_color:str|None=None,brightness:str|None=None)->BrowserTheme:
        """Return the currently selected or temporary preview palette."""
        if self._preview and mode is None:
            mode,base_color,dark=self._preview
        else:
            mode=mode or self.settings.theme()
            base_color=base_color or str(self.settings.get("appearance/custom_base_color",self.settings.ACCENTS[self.settings.accent()]))
            dark=self._resolve_dark(mode,brightness)
        return build_palette(base_color or "#1a73e8",dark)

    def apply(self)->None:
        """Apply the saved appearance across the Qt application without reloading pages."""
        if self.app is None or not self._apply_global:return
        self._preview=None
        mode=self.settings.theme()
        base=str(self.settings.get("appearance/custom_base_color",self.settings.ACCENTS[self.settings.accent()]))
        dark=self._resolve_dark(mode)
        self.app.setStyleSheet(self._stylesheet(mode,base,dark))

    def preview_theme(self,base_color:str,brightness:str="dark")->None:
        """Temporarily preview a custom theme without changing persisted settings."""
        self.preview_mode("custom",base_color,brightness)

    def preview_mode(self,mode:str,base_color:str|None=None,brightness:str="dark")->None:
        """Preview any theme mode without writing preferences."""
        if self.app is None or not self._apply_global:return
        color=base_color or str(self.settings.get("appearance/custom_base_color",self.settings.ACCENTS[self.settings.accent()]))
        if not color.startswith("#"):color="#"+color
        dark=self._resolve_dark(mode,brightness)
        self._preview=(mode,color,dark)
        self.app.setStyleSheet(self._stylesheet(mode,color,dark))

    def cancel_preview(self)->None:
        """Restore the persisted palette after preview cancellation."""
        self.apply()

    def _compact(self)->bool:
        return str(self.settings.get("appearance/toolbar_density","Normal"))=="Compact"

    def _resolve_dark(self,mode:str|None,brightness:str|None=None)->bool:
        if mode=="custom":
            value=brightness if brightness is not None else str(self.settings.get("appearance/custom_brightness","dark"))
            return value.lower()=="dark"
        if mode=="dark":return True
        if mode=="light":return False
        scheme=self.app.styleHints().colorScheme() if self.app is not None else None
        return str(scheme).lower().endswith("dark")

    def _stylesheet(self,mode:str,base_color:str,dark:bool)->str:
        """Reuse the existing mode stylesheet, then apply current token values."""
        stylesheet_mode=dark
        filename="dark.qss" if stylesheet_mode else "light.qss"
        path=resource_path("ui/themes/" + filename)
        original=path.read_text(encoding="utf-8") if path.exists() else ""
        if mode!="custom":
            base_color=self.settings.ACCENTS[self.settings.accent()]
        palette=build_palette(base_color,dark)
        IconManager.set_theme(palette)
        return original+"\n"+palette_stylesheet(palette,self._compact())
