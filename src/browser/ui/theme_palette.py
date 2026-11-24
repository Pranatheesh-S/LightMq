"""Color utilities and coordinated palettes for LightMq browser chrome."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor


@dataclass(frozen=True)
class BrowserTheme:
    """Semantic colors used to style browser-owned controls."""

    window_bg: str
    tab_strip_bg: str
    active_tab_bg: str
    inactive_tab_bg: str
    toolbar_bg: str
    omnibox_bg: str
    omnibox_focus_bg: str
    menu_bg: str
    menu_hover_bg: str
    primary_text: str
    secondary_text: str
    border_color: str
    accent_color: str
    accent_soft: str
    focus_color: str
    button_hover: str


def _mix(first: QColor, second: QColor, ratio: float) -> QColor:
    """Interpolate two colors, clamping ratio to the unit interval."""
    ratio = max(0.0, min(1.0, ratio))
    return QColor(
        round(first.red() * (1-ratio) + second.red() * ratio),
        round(first.green() * (1-ratio) + second.green() * ratio),
        round(first.blue() * (1-ratio) + second.blue() * ratio),
    )


def contrast_text(background: QColor) -> QColor:
    """Return black or white with the stronger WCAG relative-luminance contrast."""
    def luminance(color: QColor) -> float:
        channels=[]
        for component in (color.redF(),color.greenF(),color.blueF()):
            channels.append(component/12.92 if component <= .04045 else ((component+.055)/1.055)**2.4)
        return .2126*channels[0]+.7152*channels[1]+.0722*channels[2]
    value=luminance(background)
    white=1.05/(value+.05)
    black=(value+.05)/.05
    return QColor("#ffffff" if white >= black else "#202124")


def build_palette(base_color: str | QColor, dark: bool = False) -> BrowserTheme:
    """Generate stable light/dark browser surfaces from an arbitrary accent color."""
    base=QColor(base_color)
    if not base.isValid():
        base=QColor("#1a73e8")
    # Keep the selected accent exactly; only derived surfaces are adjusted.
    accent=QColor(base)
    white=QColor("#ffffff"); black=QColor("#141820")
    if dark:
        window=_mix(black,accent,.055)
        toolbar=_mix(QColor("#20242b"),accent,.07)
        tab=_mix(QColor("#252a32"),accent,.10)
        inactive=_mix(toolbar,accent,.055)
        input_bg=_mix(QColor("#171b21"),accent,.06)
        menu=_mix(QColor("#252a32"),accent,.08)
        hover=_mix(menu,accent,.20)
        border=_mix(QColor("#414853"),accent,.20)
        text=QColor("#f3f5f8"); secondary=QColor("#b6bfcc")
        accent_soft=_mix(menu,accent,.24)
    else:
        window=_mix(QColor("#f5f7fa"),accent,.045)
        toolbar=_mix(QColor("#f0f2f5"),accent,.08)
        tab=window
        inactive=_mix(toolbar,accent,.055)
        input_bg=_mix(QColor("#e9edf2"),accent,.07)
        menu=_mix(white,accent,.035)
        hover=_mix(menu,accent,.12)
        border=_mix(QColor("#c5ccd5"),accent,.20)
        text=QColor("#20252d"); secondary=QColor("#586474")
        accent_soft=_mix(white,accent,.16)
    # For unusually bright/dark user colors, select legible icon/text colors.
    return BrowserTheme(*(color.name(QColor.NameFormat.HexRgb) for color in (
        window,window,toolbar,inactive,toolbar,input_bg,window,menu,hover,text,
        secondary,border,accent,accent_soft,accent,
        _mix(accent,white if dark else black,.12),
    )))


def palette_stylesheet(theme: BrowserTheme, compact: bool = False) -> str:
    """Build application-wide QSS from semantic palette tokens."""
    pad="3px" if compact else "6px"
    return f"""
QMainWindow, QDialog {{ background:{theme.window_bg}; color:{theme.primary_text}; }}
QWidget {{ color:{theme.primary_text}; }}
QToolBar {{ background:{theme.toolbar_bg}; border:0; spacing:{pad}; padding:4px 10px; }}
QToolButton, QPushButton {{ background:transparent; color:{theme.primary_text}; border:0; border-radius:9px; padding:6px 9px; min-height:22px; }}
QToolButton:hover, QPushButton:hover {{ background:{theme.button_hover}; }}
QToolButton:pressed, QPushButton:pressed, QPushButton:checked {{ background:{theme.accent_soft}; }}
QToolButton:disabled, QPushButton:disabled {{ color:{theme.secondary_text}; }}
QToolButton#profileButton {{ border-radius:17px; min-width:30px; min-height:30px; padding:0; background:{theme.accent_soft}; font-weight:700; }}
QToolButton[lightmqIconButton="true"] {{ background:transparent; border:1px solid transparent; border-radius:9px; padding:4px; }}
QToolButton[lightmqIconButton="true"]:hover {{ background:{theme.button_hover}; }}
QToolButton[lightmqIconButton="true"]:pressed, QToolButton[lightmqIconButton="true"]:checked {{ background:{theme.accent_soft}; }}
QToolButton[lightmqIconButton="true"]:disabled {{ color:{theme.secondary_text}; }}
QToolButton[lightmqIconButton="true"]:focus {{ border:1px solid {theme.focus_color}; }}
QLineEdit {{ background:{theme.omnibox_bg}; color:{theme.primary_text}; border:1px solid {theme.border_color}; border-radius:19px; padding:8px 15px; selection-background-color:{theme.accent_color}; }}
QLineEdit#addressBar {{ min-height:24px; border-radius:20px; }}
QLineEdit#addressBar:hover {{ background:{theme.menu_bg}; }}
QLineEdit:focus {{ background:{theme.omnibox_focus_bg}; border:2px solid {theme.focus_color}; }}
QTabBar {{ background:{theme.tab_strip_bg}; qproperty-drawBase:0; }}
QTabBar::tab {{ background:{theme.inactive_tab_bg}; color:{theme.secondary_text}; border:0; border-top-left-radius:11px; border-top-right-radius:11px; padding:8px 12px; margin:4px 2px 0 0; min-width:96px; max-width:230px; }}
QTabBar::tab:selected {{ background:{theme.active_tab_bg}; color:{theme.primary_text}; margin-top:1px; padding-top:10px; }}
QTabBar::tab:hover:!selected {{ background:{theme.menu_hover_bg}; }}
QMenu {{ background:{theme.menu_bg}; color:{theme.primary_text}; border:1px solid {theme.border_color}; border-radius:12px; padding:6px; }}
QMenu::item {{ padding:8px 34px 8px 12px; border-radius:7px; }}
QMenu::item:selected {{ background:{theme.menu_hover_bg}; }}
QMenu::separator {{ height:1px; background:{theme.border_color}; margin:5px 8px; }}
QListWidget, QTreeWidget, QTableWidget, QStackedWidget {{ background:{theme.window_bg}; color:{theme.primary_text}; border-color:{theme.border_color}; }}
QListWidget::item:selected, QTreeWidget::item:selected {{ background:{theme.accent_soft}; color:{theme.primary_text}; }}
QStatusBar {{ background:{theme.toolbar_bg}; color:{theme.secondary_text}; border-top:1px solid {theme.border_color}; }}
QScrollBar:vertical {{ width:10px; background:transparent; margin:2px; }}
QScrollBar::handle:vertical {{ background:{theme.border_color}; border-radius:5px; min-height:24px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
QToolTip {{ background:{theme.menu_bg}; color:{theme.primary_text}; border:1px solid {theme.border_color}; padding:5px; }}
"""
