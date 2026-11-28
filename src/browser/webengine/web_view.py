"""Custom WebEngineView component for web content rendering.

Subclasses QWebEngineView and integrates with WebPage to provide page navigation,
progress reporting, and lifecycle notifications.
"""

import json

from PySide6.QtCore import QUrl
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel

from browser.utils.constants import DEFAULT_START_URL
from browser.webengine.web_page import WebPage
from browser.webengine.new_tab_content import PRIVATE_START_URL, new_tab_html, private_start_html
from browser.webengine.new_tab_bridge import NewTabBridge


class WebView(QWebEngineView):
    """Customized WebEngineView hosting the Chromium web viewport."""

    def __init__(self, profile: QWebEngineProfile | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self._showing_new_tab = False
        self._internal_url = DEFAULT_START_URL
        self._search_template="https://www.google.com/search?q={searchTerms}"
        self._start_page_theme=None
        self._custom_page = WebPage(profile=profile, parent=self)
        self.setPage(self._custom_page)
        self._custom_page.main_frame_navigation_requested.connect(self._on_main_frame_navigation)

    def configure_start_page(self,settings,search_template:str,theme,private:bool=False,recommendations=None,context_url:str="",context_title:str="")->None:
        """Install the narrow bridge used only by LightMq's internal start page."""
        self._search_template=search_template;self._start_page_theme=theme
        self._new_tab_bridge=NewTabBridge(settings,search_template,private,page=self._custom_page,parent=self._custom_page,recommendations=recommendations)
        self._new_tab_bridge.set_context(context_url,context_title)
        self._web_channel=QWebChannel(self._custom_page)
        self._web_channel.registerObject("lightmq",self._new_tab_bridge)
        self._custom_page.setWebChannel(self._web_channel)

    def set_pdf_viewer_enabled(self, enabled: bool) -> None:
        """Configure Qt's internal PDF viewer on this page before navigation.

        Qt WebEngine requires plugin support for its built-in PDF renderer. The
        view setting is deliberately scoped to this WebView and profile context.
        """
        settings = self.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.PdfViewerEnabled, enabled)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, enabled)

    def update_start_page_theme(self,theme,search_template:str|None=None)->None:
        """Update the built-in start page colors without reloading the page."""
        self._start_page_theme=theme
        if search_template is not None:
            self._search_template=search_template
            self._new_tab_bridge.template=search_template
        if self._showing_new_tab:
            colors={key:getattr(theme,key) for key in ("window_bg","toolbar_bg","omnibox_bg","primary_text","secondary_text","accent_color","border_color","menu_hover_bg")}
            from browser.ui.theme_palette import contrast_text
            colors["button_text"]=contrast_text(QColor(colors["accent_color"])).name()
            self.page().runJavaScript("if(window.setLightMqTheme)window.setLightMqTheme("+json.dumps({"bg":colors["window_bg"],"surface":colors["toolbar_bg"],"input":colors["omnibox_bg"],"text":colors["primary_text"],"secondary":colors["secondary_text"],"accent":colors["accent_color"],"border":colors["border_color"],"hover":colors["menu_hover_bg"],"button-text":colors["button_text"]})+")")

    def url(self) -> QUrl:
        """Return the internal new-tab address while its HTML is being installed."""
        if self._showing_new_tab:
            return QUrl(self._internal_url)
        return super().url()

    def _on_main_frame_navigation(self, target: str, _visit_type: str) -> None:
        """Leave new-tab mode as soon as the user navigates to another page."""
        if target not in (DEFAULT_START_URL,PRIVATE_START_URL):
            self._showing_new_tab = False

    def setUrl(self, url: QUrl) -> None:
        """Load either the built-in start page or the requested external URL."""
        if url.toString() in (DEFAULT_START_URL,PRIVATE_START_URL):
            self._showing_new_tab = True
            self._internal_url=url.toString()
            html=private_start_html(self._search_template) if self._internal_url==PRIVATE_START_URL else new_tab_html(self._search_template,self._start_page_theme)
            super().setHtml(html,QUrl(self._internal_url))
            return
        self._showing_new_tab = False
        super().setUrl(url)

    def navigate(self, url: QUrl) -> None:
        """Navigate to a target QUrl.

        Args:
            url: Validated destination QUrl.
        """
        if url.isValid() and not url.isEmpty():
            self.setUrl(url)
