"""Narrow, validated QWebChannel API for LightMq's local start page."""

from __future__ import annotations

import json
import re
import weakref

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtCore import QSettings, QUrl


DEFAULT_SHORTCUTS=[
    {"title":"GitHub","url":"https://github.com/"},
    {"title":"Python Docs","url":"https://docs.python.org/3/"},
    {"title":"Qt for Python","url":"https://doc.qt.io/qtforpython-6/"},
]


class NewTabBridge(QObject):
    """Expose only shortcut CRUD and search template data to the built-in page."""

    KEY="appearance/new_tab_shortcuts"
    recommendationsChanged=Signal(str)
    openRecommendationRequested=Signal(str,bool)

    def __init__(self,settings:QSettings,search_template:str,private:bool=False,page:QObject|None=None,parent:QObject|None=None,recommendations=None):
        super().__init__(parent)
        self.settings=settings;self.template=search_template;self.private=private
        self._page_ref=weakref.ref(page) if page is not None else lambda:None
        self.recommendations=recommendations
        self.context_url="";self.context_title=""
        if recommendations is not None:
            recommendations.recommendations_ready.connect(self._recommendations_ready)

    def set_context(self,url:str,title:str)->None:
        """Associate the new tab with its opener page for local related results."""
        self.context_url=url[:2048];self.context_title=title[:300]

    def _trusted_start_page(self)->bool:
        page=self._page_ref()
        if page is None:return False
        try:
            url=page.url()
            return url.scheme()=="lightmq" and url.host() in {"newtab","incognito"}
        except RuntimeError:return False

    @Slot(result=str)
    def loadShortcuts(self)->str:
        """Return validated shortcut metadata as JSON text."""
        if not self._trusted_start_page():return json.dumps(DEFAULT_SHORTCUTS)
        value=self.settings.value(self.KEY,DEFAULT_SHORTCUTS)
        if isinstance(value,str):
            try:value=json.loads(value)
            except (TypeError,ValueError):value=DEFAULT_SHORTCUTS
        clean=[]
        if isinstance(value,(list,tuple)):
            for entry in value[:12]:
                if not isinstance(entry,dict):continue
                title=str(entry.get("title",""))[:40].strip();url=self.valid_url(str(entry.get("url","")))
                if title and url:clean.append({"title":title,"url":url})
        return json.dumps(clean or DEFAULT_SHORTCUTS,ensure_ascii=True)

    @Slot(str,str,int,result=bool)
    def saveShortcut(self,title:str,url:str,index:int)->bool:
        """Add/edit one shortcut after strict title and HTTP(S) URL validation."""
        normalized=self.valid_url(url);name=title.strip()[:40]
        if not self._trusted_start_page() or self.private or not name or not normalized:return False
        entries=json.loads(self.loadShortcuts())
        if index<0:
            if len(entries)>=12:return False
            entries.append({"title":name,"url":normalized})
        elif index<len(entries):entries[index]={"title":name,"url":normalized}
        else:return False
        self.settings.setValue(self.KEY,json.dumps(entries));self.settings.sync();return self.settings.status()==QSettings.Status.NoError

    @Slot(int,result=bool)
    def removeShortcut(self,index:int)->bool:
        """Remove one shortcut by current index."""
        if not self._trusted_start_page() or self.private:return False
        entries=json.loads(self.loadShortcuts())
        if not 0<=index<len(entries):return False
        entries.pop(index);self.settings.setValue(self.KEY,json.dumps(entries));self.settings.sync()
        return self.settings.status()==QSettings.Status.NoError

    @Slot(result=str)
    def searchTemplate(self)->str:
        """Return the already validated HTTP(S) search URL template."""
        return self.template if self._trusted_start_page() else "https://www.google.com/search?q={searchTerms}"

    @Slot(result=str)
    def loadRecommendations(self)->str:
        """Return cached local suggestions; ranking refresh runs in a worker thread."""
        if self.private or not self._trusted_new_tab() or self.recommendations is None:
            return json.dumps({"recommended":[],"related":[],"continue":[]})
        return self.recommendations.recommendations_json(self.context_url,self.context_title)

    @Slot(result=bool)
    def recommendationsEnabled(self)->bool:
        """Expose only the user's New Tab recommendation toggle state."""
        return bool(
            not self.private and self._trusted_new_tab() and self.recommendations is not None
            and self.recommendations.enabled and self.recommendations.show_on_new_tab
        )

    @Slot()
    def refreshRecommendations(self)->None:
        """Refresh the current context without blocking the renderer or GUI."""
        if not self.private and self._trusted_new_tab() and self.recommendations is not None:
            self.recommendations.refresh(self.context_url,self.context_title)

    @Slot(str,str,result=bool)
    def hideRecommendation(self,url:str,title:str)->bool:
        if self.private or not self._trusted_new_tab() or self.recommendations is None:
            return False
        return self.recommendations.hide(url,title)

    @Slot(str,bool,str,result=bool)
    def pinRecommendation(self,url:str,pinned:bool,title:str)->bool:
        if self.private or not self._trusted_new_tab() or self.recommendations is None:
            return False
        return self.recommendations.pin(url,pinned,title)

    @Slot(str,bool,result=bool)
    def openRecommendation(self,url:str,new_tab:bool)->bool:
        if self.private or not self._trusted_new_tab() or not self.valid_url(url):
            return False
        self.openRecommendationRequested.emit(self.valid_url(url) or "",new_tab)
        return True

    def _trusted_new_tab(self)->bool:
        page=self._page_ref()
        if page is None:return False
        try:
            url=page.url()
            return url.scheme()=="lightmq" and url.host()=="newtab"
        except RuntimeError:return False

    @Slot(str,str)
    def _recommendations_ready(self,key:str,payload:str)->None:
        if self.private or not self._trusted_new_tab() or self.recommendations is None:
            return
        expected=self.recommendations.context_key(self.context_url,self.context_title)
        if key==expected:
            self.recommendationsChanged.emit(payload)

    @staticmethod
    def valid_url(value:str)->str|None:
        """Allow normal websites and local development hosts, rejecting other schemes."""
        value=value.strip()
        if not value or len(value)>2048 or re.search(r"[\x00-\x20]",value):return None
        if not re.match(r"^[a-zA-Z][a-zA-Z\d+.-]*:",value):value="https://"+value
        url=QUrl(value)
        if not url.isValid() or url.scheme().lower() not in {"http","https"} or not url.host() or url.userInfo():return None
        return url.toString(QUrl.ComponentFormattingOption.FullyEncoded)
