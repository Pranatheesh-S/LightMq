"""Color generation keeps custom accents exact and readable."""

from PySide6.QtGui import QColor

from browser.ui.theme_palette import build_palette, contrast_text, palette_stylesheet


def test_custom_palette_is_deterministic_and_uses_the_exact_accent():
    first=build_palette("#8B3A62",dark=True)
    second=build_palette("#8B3A62",dark=True)
    assert first==second
    assert first.accent_color=="#8b3a62"
    assert first.window_bg!=first.menu_bg
    assert first.active_tab_bg==first.toolbar_bg
    assert "QMenu::item:selected" in palette_stylesheet(first)


def test_accent_foreground_contrast_selects_black_or_white():
    assert contrast_text(QColor("#ffff00")).name()=="#202124"
    assert contrast_text(QColor("#172340")).name()=="#ffffff"
