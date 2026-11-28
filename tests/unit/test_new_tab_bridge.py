"""The local start-page bridge accepts only safe shortcuts from its own origin."""

import json

from PySide6.QtCore import QObject, QSettings, QUrl

from browser.webengine.new_tab_bridge import NewTabBridge


class _Page(QObject):
    def __init__(self,url:str):
        super().__init__();self._url=QUrl(url)
    def url(self):return self._url


def test_shortcut_validation_and_persistence_are_scoped_to_local_start_page(tmp_path):
    store=QSettings(str(tmp_path/"settings.ini"),QSettings.Format.IniFormat)
    page=_Page("lightmq://newtab")
    bridge=NewTabBridge(store,"https://duckduckgo.com/?q={searchTerms}",page=page)
    assert bridge.saveShortcut("Docs","docs.python.org",-1)
    saved=json.loads(bridge.loadShortcuts())
    assert saved[-1]=={"title":"Docs","url":"https://docs.python.org"}
    assert not bridge.saveShortcut("Unsafe","javascript:alert(1)",-1)
    assert not bridge.saveShortcut("Credentials","https://user:secret@example.com",-1)

    page._url=QUrl("https://example.com/")
    assert json.loads(bridge.loadShortcuts())==[
        {"title":"GitHub","url":"https://github.com/"},
        {"title":"Python Docs","url":"https://docs.python.org/3/"},
        {"title":"Qt for Python","url":"https://doc.qt.io/qtforpython-6/"},
    ]
    assert not bridge.removeShortcut(0)
    assert "google.com" in bridge.searchTemplate()


def test_private_start_page_can_read_but_not_persist_shortcuts(tmp_path):
    store=QSettings(str(tmp_path/"settings.ini"),QSettings.Format.IniFormat)
    bridge=NewTabBridge(store,"https://search.brave.com/search?q={searchTerms}",private=True,page=_Page("lightmq://incognito/"))
    assert len(json.loads(bridge.loadShortcuts()))==3
    assert not bridge.saveShortcut("Private","https://example.com",-1)
    assert store.value(bridge.KEY) is None


def test_incognito_start_page_never_exposes_recommendation_data(tmp_path):
    store=QSettings(str(tmp_path/"settings.ini"),QSettings.Format.IniFormat)
    bridge=NewTabBridge(
        store,"https://search.brave.com/search?q={searchTerms}",private=True,
        page=_Page("lightmq://incognito/"),
    )
    assert not bridge.recommendationsEnabled()
    assert json.loads(bridge.loadRecommendations())=={"recommended":[],"related":[],"continue":[]}
    assert not bridge.hideRecommendation("https://example.com/","Example")
    assert not bridge.pinRecommendation("https://example.com/",True,"Example")
    assert not bridge.openRecommendation("https://example.com/",True)
