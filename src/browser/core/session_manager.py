"""Debounced session snapshots, crash detection, and tab restoration."""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, QUrl, Signal

from browser.core.tab_manager import TabManager
from browser.storage.session_model import SessionGroup, SessionSnapshot, SessionTab
from browser.storage.session_repository import SessionRepository
from browser.webengine.web_view import WebView

class SessionManager(QObject):
    """Coordinate a normal browser window's session lifecycle."""

    save_failed = Signal(str)
    SAVE_DEBOUNCE_MS = 700
    RECOVERY_INTERVAL_MS = 60_000

    def __init__(
        self,
        repository: SessionRepository | None = None,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self.repository = repository or SessionRepository()
        self._tab_manager: TabManager | None = None
        self._suspended = False
        self._started = False
        self._restored = False
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(self.SAVE_DEBOUNCE_MS)
        self._debounce.timeout.connect(self.save_now)
        self._recovery = QTimer(self)
        self._recovery.setInterval(self.RECOVERY_INTERVAL_MS)
        self._recovery.timeout.connect(self.save_now)

    def begin_run(self) -> tuple[bool, SessionSnapshot | None]:
        """Persist the unclean marker and return any verified recovery snapshot."""
        self._started = True
        self._recovery.start()
        return self.repository.begin_run()

    def bind(self, tab_manager: TabManager) -> None:
        """Observe the existing TabManager and its views for session changes."""
        self._tab_manager = tab_manager
        tab_manager.tab_created.connect(self._on_tab_created)
        tab_manager.tab_closed.connect(self.schedule_save)
        tab_manager.current_changed.connect(self._on_current_changed)
        tab_manager.tab_moved.connect(self._on_tab_moved)
        tab_manager.state_changed.connect(self.schedule_save)
        tab_manager.group_manager.state_changed.connect(self.schedule_save)
        for index in range(tab_manager.count()):
            view = tab_manager.view_at(index)
            if view is not None:
                self._watch_view(view)

    def restore(self, snapshot: SessionSnapshot) -> int:
        """Restore valid tab metadata using the existing TabManager API."""
        if self._tab_manager is None or self._restored or self._tab_manager.count() > 0:
            return 0
        self._restored = True
        self._suspended = True
        restored: list[tuple[str, WebView]] = []
        try:
            group_manager = self._tab_manager.group_manager
            group_manager.restore_groups([
                {"id": group.group_id, "name": group.name, "color": group.color,
                 "collapsed": group.collapsed, "position": group.position}
                for group in snapshot.groups
            ])
            for tab in snapshot.tabs:
                url = SessionSnapshot.sanitize_url(tab.url)
                if url is None:
                    continue
                try:
                    view = self._tab_manager.create_tab(
                        QUrl(url), activate=False, tab_id=tab.tab_id, tab_title=tab.title,
                        pinned=tab.pinned, group_id=tab.group_id,
                    )
                except (TypeError, ValueError):
                    continue
                restored.append((tab.tab_id, view))
            group_manager.clear_membership()
            if restored:
                active_id = snapshot.active_tab_id
                active_index = next(
                    (
                        self._tab_manager.index_of(view)
                        for tab_id, view in restored
                        if tab_id == active_id
                    ),
                    0,
                )
                self._tab_manager.set_current_index(active_index)
        finally:
            self._suspended = False
        self.schedule_save()
        return len(restored)

    def schedule_save(self, *_args: object) -> None:
        """Coalesce tab lifecycle and navigation changes into one write."""
        if not self._started or self._suspended or self._tab_manager is None:
            return
        self._debounce.start()

    def capture(self) -> SessionSnapshot:
        """Capture current URL, title, order, and active tab only."""
        tabs: list[SessionTab] = []
        groups: list[SessionGroup] = []
        manager = self._tab_manager
        if manager is not None:
            for index in range(manager.count()):
                view = manager.view_at(index)
                if view is None:
                    continue
                url = SessionSnapshot.sanitize_url(view.url().toString())
                if url is None:
                    continue
                tab_id = manager.tab_id_for(view)
                title = view.title() or getattr(view, "restored_title", "")
                group_id = manager.group_manager.group_id_for_tab(tab_id)
                tabs.append(SessionTab(tab_id, url, title, index, manager.is_pinned(view), group_id))
            active_view = manager.current_view()
            active_id = manager.tab_id_for(active_view) if active_view is not None else None
            groups = [
                SessionGroup(group.id, group.name, group.color, group.collapsed, position)
                for position, group in enumerate(manager.group_manager.groups())
            ]
        else:
            active_id = None
        return SessionSnapshot.create(tabs, active_id, groups)

    def save_now(self) -> bool:
        """Write the latest complete snapshot to current and recovery files."""
        if self._tab_manager is None:
            return False
        self._debounce.stop()
        snapshot = self.capture()
        saved = self.repository.save(snapshot)
        if not saved:
            self.save_failed.emit("Could not save the browser session. Check available disk space and permissions.")
        return saved

    def finish(self) -> bool:
        """Write a final pre-destruction snapshot and mark this run clean."""
        if not self._started:
            return False
        self._debounce.stop()
        self._recovery.stop()
        if not self.save_now():
            return False
        return self.repository.mark_clean_shutdown()

    def _on_tab_created(self, _index: int, view: WebView) -> None:
        self._watch_view(view)
        self.schedule_save()

    def _on_current_changed(self, _index: int, _view: WebView) -> None:
        self.schedule_save()

    def _on_tab_moved(self, _from_index: int, _to_index: int) -> None:
        self.schedule_save()

    def _watch_view(self, view: WebView) -> None:
        view.urlChanged.connect(lambda _url: self.schedule_save())
        view.titleChanged.connect(lambda _title: self.schedule_save())
