"""Theme-aware, cached SVG icon rendering for LightMq controls."""

from __future__ import annotations

from collections import OrderedDict

from PySide6.QtCore import QByteArray, QRect, QRectF, QSize, Qt
from PySide6.QtGui import (
    QGuiApplication,
    QColor,
    QIcon,
    QIconEngine,
    QImage,
    QPainter,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer

from browser.ui.icons.icon_registry import ICON_MARKUP, svg_document
from browser.ui.theme_palette import BrowserTheme, build_palette, contrast_text


class _LightMqSvgEngine(QIconEngine):
    """Render one registered icon as a vector in the target's current state."""

    def __init__(self, name: str, nominal_size: int, theme: BrowserTheme | None = None) -> None:
        super().__init__()
        self.name = name
        self.nominal_size = QSize(nominal_size, nominal_size)
        self.theme = theme

    def clone(self) -> "_LightMqSvgEngine":
        return _LightMqSvgEngine(self.name, self.nominal_size.width(), self.theme)

    def key(self) -> str:
        return "LightMqSvgIcon"

    def iconName(self) -> str:
        return self.name

    def actualSize(self, size: QSize, mode: QIcon.Mode, state: QIcon.State) -> QSize:
        del mode, state
        if size.isEmpty():
            return self.nominal_size
        side = min(size.width(), size.height(), self.nominal_size.width())
        return QSize(side, side)

    def availableSizes(
        self, mode: QIcon.Mode = QIcon.Mode.Normal, state: QIcon.State = QIcon.State.Off
    ) -> list[QSize]:
        del mode, state
        return [QSize(self.nominal_size)]

    def paint(
        self, painter: QPainter, rect: QRect, mode: QIcon.Mode, state: QIcon.State
    ) -> None:
        color = IconManager.color_for_state(mode, state, self.theme)
        renderer = IconManager._renderer(self.name, color)
        if renderer.isValid():
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            renderer.render(painter, QRectF(rect))
            painter.restore()

    def pixmap(self, size: QSize, mode: QIcon.Mode, state: QIcon.State) -> QPixmap:
        return IconManager._render_pixmap(self.name, size, mode, state, self.theme)


class IconManager:
    """Provide a single icon API and cache SVG renderers and HiDPI pixmaps."""

    _theme: BrowserTheme = build_palette("#1a73e8", dark=False)
    _icons: dict[tuple[str, int, BrowserTheme | None], QIcon] = {}
    _renderers: OrderedDict[tuple[str, str], QSvgRenderer] = OrderedDict()
    _pixmaps: OrderedDict[tuple[str, int, int, str, float], QPixmap] = OrderedDict()
    _MAX_RENDERERS = 96
    _MAX_PIXMAPS = 256

    @classmethod
    def set_theme(cls, theme: BrowserTheme) -> None:
        """Set the shared palette used by all currently assigned icon engines."""
        cls._theme = theme
        cls._pixmaps.clear()

    @classmethod
    def icon(
        cls, name: str, size: int = 20, theme: BrowserTheme | None = None
    ) -> QIcon:
        """Return a scalable icon whose colors follow the current browser theme."""
        if name not in ICON_MARKUP:
            raise ValueError(f"Unknown LightMq icon: {name}")
        key = (name, max(1, int(size)), theme)
        if key not in cls._icons:
            cls._icons[key] = QIcon(_LightMqSvgEngine(*key))
        return cls._icons[key]

    @classmethod
    def set_widget_icon(
        cls, widget, name: str, size: int = 20, theme: BrowserTheme | None = None
    ) -> None:
        """Assign an icon to a QWidget and retain its semantic name for inspection."""
        widget.setProperty("lightmqIconName", name)
        widget.setIcon(cls.icon(name, size, theme))
        widget.setIconSize(QSize(size, size))

    @classmethod
    def set_action_icon(
        cls, action, name: str, size: int = 18, theme: BrowserTheme | None = None
    ) -> None:
        """Assign an accessible, theme-aware icon to a QAction."""
        action.setProperty("lightmqIconName", name)
        action.setIcon(cls.icon(name, size, theme))

    @classmethod
    def color_for_state(
        cls,
        mode: QIcon.Mode,
        state: QIcon.State,
        theme: BrowserTheme | None = None,
    ) -> str:
        """Choose legible normal, hover/active, pressed, and disabled colors."""
        palette = theme or cls._theme
        if mode == QIcon.Mode.Disabled:
            return palette.secondary_text
        if mode in (QIcon.Mode.Active, QIcon.Mode.Selected) or state == QIcon.State.On:
            accent = palette.accent_color
            if min(
                cls._contrast_ratio(accent, palette.toolbar_bg),
                cls._contrast_ratio(accent, palette.menu_bg),
            ) >= 3:
                return accent
            return contrast_text(QColor(palette.toolbar_bg)).name()
        return palette.primary_text

    @classmethod
    def _contrast_ratio(cls, foreground: str, background: str) -> float:
        def luminance(value: str) -> float:
            color = QColor(value)
            channels = []
            for component in (color.redF(), color.greenF(), color.blueF()):
                channels.append(
                    component / 12.92
                    if component <= 0.04045
                    else ((component + 0.055) / 1.055) ** 2.4
                )
            return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]

        first, second = luminance(foreground), luminance(background)
        lighter, darker = max(first, second), min(first, second)
        return (lighter + 0.05) / (darker + 0.05)

    @classmethod
    def _renderer(cls, name: str, color: str) -> QSvgRenderer:
        key = (name, color.lower())
        cached = cls._renderers.get(key)
        if cached is not None:
            cls._renderers.move_to_end(key)
            return cached
        renderer = QSvgRenderer(QByteArray(svg_document(name, color)))
        cls._renderers[key] = renderer
        if len(cls._renderers) > cls._MAX_RENDERERS:
            cls._renderers.popitem(last=False)
        return renderer

    @classmethod
    def _render_pixmap(
        cls,
        name: str,
        size: QSize,
        mode: QIcon.Mode,
        state: QIcon.State,
        theme: BrowserTheme | None = None,
        dpr: float | None = None,
    ) -> QPixmap:
        """Render and cache a DPR-aware pixmap for callers requesting raster data."""
        if dpr is None:
            screen = QGuiApplication.primaryScreen()
            dpr = float(screen.devicePixelRatio()) if screen is not None else 1.0
        dpr = max(1.0, float(dpr))
        color = cls.color_for_state(mode, state, theme)
        width, height = max(1, size.width()), max(1, size.height())
        key = (name, width, height, color.lower(), dpr)
        cached = cls._pixmaps.get(key)
        if cached is not None:
            cls._pixmaps.move_to_end(key)
            return cached

        image = QImage(
            max(1, round(width * dpr)),
            max(1, round(height * dpr)),
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        image.fill(Qt.GlobalColor.transparent)
        image.setDevicePixelRatio(dpr)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        cls._renderer(name, color).render(painter, QRectF(0, 0, width, height))
        painter.end()
        pixmap = QPixmap.fromImage(image)
        pixmap.setDevicePixelRatio(dpr)
        cls._pixmaps[key] = pixmap
        if len(cls._pixmaps) > cls._MAX_PIXMAPS:
            cls._pixmaps.popitem(last=False)
        return pixmap

