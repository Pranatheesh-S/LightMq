"""Registered SVG icons render cleanly and follow theme state colors."""

import sys

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QGuiApplication
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

from browser.ui.icons.icon_manager import IconManager
from browser.ui.icons.icon_registry import ICON_MARKUP, svg_document
from browser.ui.theme_palette import build_palette


app = QApplication.instance() or QApplication(sys.argv)


def test_every_registered_icon_has_valid_vector_and_renders():
    for name in ICON_MARKUP:
        renderer = QSvgRenderer(svg_document(name, "#425466"))
        assert renderer.isValid(), name
        icon = IconManager.icon(name, 20)
        assert not icon.isNull(), name
        assert not icon.pixmap(QSize(20, 20)).isNull(), name


def test_icons_follow_theme_colors_and_use_dpr_aware_pixmap_cache():
    original = IconManager._theme
    try:
        light = build_palette("#2468c7", dark=False)
        dark = build_palette("#8b3a62", dark=True)
        IconManager.set_theme(light)
        light_normal = IconManager.color_for_state(QIcon.Mode.Normal, QIcon.State.Off)
        light_disabled = IconManager.color_for_state(QIcon.Mode.Disabled, QIcon.State.Off)
        IconManager.set_theme(dark)
        assert IconManager.color_for_state(QIcon.Mode.Normal, QIcon.State.Off) == dark.primary_text
        assert IconManager.color_for_state(QIcon.Mode.Disabled, QIcon.State.Off) == dark.secondary_text
        assert light_normal == light.primary_text
        assert light_disabled == light.secondary_text

        screen = QGuiApplication.primaryScreen()
        dpr = screen.devicePixelRatio() if screen else 1.0
        first = IconManager._render_pixmap(
            "home", QSize(20, 20), QIcon.Mode.Normal, QIcon.State.Off
        )
        cache_size = len(IconManager._pixmaps)
        second = IconManager._render_pixmap(
            "home", QSize(20, 20), QIcon.Mode.Normal, QIcon.State.Off
        )
        assert first is second
        assert len(IconManager._pixmaps) == cache_size
        assert second.devicePixelRatio() == dpr
        assert second.width() == round(20 * dpr)
        for scale in (1.0, 1.25, 1.5, 2.0):
            scaled = IconManager._render_pixmap(
                "home",
                QSize(20, 20),
                QIcon.Mode.Normal,
                QIcon.State.Off,
                dpr=scale,
            )
            assert scaled.devicePixelRatio() == scale
            assert scaled.width() == round(20 * scale)
    finally:
        IconManager.set_theme(original)
