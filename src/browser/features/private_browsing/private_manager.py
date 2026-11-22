"""Own shared, ephemeral resources for each active private browsing session."""

from __future__ import annotations

from dataclasses import dataclass, field
import weakref

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineCore import QWebEngineProfile

from browser.features.downloads.download_manager import DownloadManager
from browser.webengine.web_profile import WebProfileManager


@dataclass
class _PrivateSession:
    profile: QWebEngineProfile
    downloads: DownloadManager
    windows: weakref.WeakSet
    pending_pages: int = 0
    retiring: bool = False
    cleanup_started: bool = False


class PrivateBrowsingManager(QObject):
    """Share one off-the-record profile across private windows until it ends."""

    _instance: "PrivateBrowsingManager | None" = None

    def __init__(self,parent:QObject|None=None):
        super().__init__(parent)
        self._active:_PrivateSession|None=None
        self._retired:list[_PrivateSession]=[]

    @classmethod
    def get_instance(cls)->"PrivateBrowsingManager":
        """Return the application-scoped private session coordinator."""
        if cls._instance is None:
            app=QApplication.instance()
            if app is None:raise RuntimeError("QApplication is required for private browsing")
            cls._instance=cls(app)
        return cls._instance

    def acquire(self,window:QObject)->tuple[QWebEngineProfile,DownloadManager]:
        """Register a private window and return its session profile and downloads."""
        if self._active is None:
            app=QApplication.instance()
            if app is None:raise RuntimeError("QApplication is required for private browsing")
            profile=WebProfileManager.create_off_the_record_profile(self)
            downloads=DownloadManager(parent=self)
            session=_PrivateSession(profile,downloads,weakref.WeakSet())
            self._active=session
            downloads.active_count_changed.connect(lambda _count,s=session:self._maybe_cleanup(s))
        self._active.windows.add(window)
        return self._active.profile,self._active.downloads

    def has_other_windows(self,window:QObject)->bool:
        """Return whether another Incognito window is still in this session."""
        return bool(self._active and any(candidate is not window for candidate in self._active.windows))

    def active_downloads(self)->list:
        """Return currently active private transfers for close confirmation."""
        if self._active is None:return []
        return [item for item in self._active.downloads.get_downloads() if item.is_active]

    def cancel_active_downloads(self)->None:
        """Cancel private transfers only after the user confirms session closure."""
        for item in self.active_downloads():item.cancel()

    def release_window(self,window:QObject,resources:list[QObject])->None:
        """Retire a closed window and release its profile after pages are destroyed."""
        session=self._active
        if session is None or window not in session.windows:return
        session.windows.discard(window)
        session.pending_pages+=len(resources)
        for resource in resources:
            resource.destroyed.connect(lambda _obj=None,s=session:self._resource_destroyed(s))
        if session.windows:
            return
        session.retiring=True
        self._active=None
        self._retired.append(session)
        QTimer.singleShot(0,lambda s=session:self._maybe_cleanup(s))

    def _resource_destroyed(self,session:_PrivateSession)->None:
        session.pending_pages=max(0,session.pending_pages-1)
        self._maybe_cleanup(session)

    def _maybe_cleanup(self,session:_PrivateSession)->None:
        """Drop session records/profile once no windows, pages, or downloads remain."""
        if session.cleanup_started or not session.retiring or session.windows or session.pending_pages:
            return
        if any(item.is_active for item in session.downloads.get_downloads()):
            return
        # clear() emits active_count_changed synchronously; mark this first so the
        # connected callback cannot recursively run cleanup during that emission.
        session.cleanup_started=True
        if session in self._retired:self._retired.remove(session)
        session.downloads.clear()
        session.downloads.deleteLater()
        session.profile.deleteLater()

    @property
    def active_profile(self)->QWebEngineProfile|None:
        """Expose the active profile for diagnostics and isolated tests."""
        return self._active.profile if self._active else None

    @property
    def active_window_count(self)->int:
        """Number of currently open Incognito windows in the active session."""
        return len(self._active.windows) if self._active else 0
