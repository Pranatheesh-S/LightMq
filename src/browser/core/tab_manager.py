"""Authoritative lifecycle and ordering model for LightMq browser tabs."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtWebEngineCore import QWebEngineProfile

from browser.core.navigation import normalize_url
from browser.core.tab_group_manager import TabGroupManager
from browser.core.tab_history import ClosedTab, TabHistory
from browser.utils.constants import DEFAULT_START_URL
from browser.storage.session_model import SessionSnapshot
from browser.webengine.web_page import WebPage
from browser.webengine.web_view import WebView

logger = logging.getLogger(__name__)


class TabManager(QObject):
    """Manage WebView instances, stable IDs, pinning, groups, and tab history."""

    tab_created = Signal(int, WebView)
    tab_closing = Signal(int, WebView)
    tab_closed = Signal(int)
    current_changed = Signal(int, WebView)
    tab_moved = Signal(int, int)
    tab_order_changed = Signal()
    state_changed = Signal()
    count_changed = Signal(int)

    def __init__(
        self,
        default_url: str = DEFAULT_START_URL,
        profile: QWebEngineProfile | None = None,
        is_private: bool = False,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._default_url = default_url
        self._profile = profile
        self._is_private = is_private
        self._views: list[WebView] = []
        self._tab_ids: dict[WebView, str] = {}
        self._pinned_ids: set[str] = set()
        self._current_index = -1
        self.group_manager = TabGroupManager(self)
        self.tab_history = TabHistory()

    @property
    def default_url(self) -> str:
        """Return the URL used for a newly created blank tab."""
        return self._default_url

    @property
    def is_private(self) -> bool:
        """Return whether this manager belongs to a private window."""
        return self._is_private

    def count(self) -> int:
        """Return the number of managed tabs."""
        return len(self._views)

    def current_index(self) -> int:
        """Return the active tab's model index."""
        return self._current_index

    def current_view(self) -> WebView | None:
        """Return the active view, if one exists."""
        return self.view_at(self._current_index)

    def view_at(self, index: int) -> WebView | None:
        """Return a view by model index."""
        return self._views[index] if 0 <= index < len(self._views) else None

    def ordered_views(self) -> tuple[WebView, ...]:
        """Return an immutable view of the authoritative tab order."""
        return tuple(self._views)

    def index_of(self, view: WebView) -> int:
        """Return a view's index or -1 if it is not managed here."""
        try:
            return self._views.index(view)
        except ValueError:
            return -1

    def tab_id_for(self, view: WebView | None) -> str | None:
        """Return the stable tab ID for a managed view."""
        return self._tab_ids.get(view) if view is not None else None

    def view_for_tab_id(self, tab_id: str) -> WebView | None:
        """Resolve a stable tab ID to its live view."""
        return next((view for view in self._views if self._tab_ids.get(view) == tab_id), None)

    def is_pinned(self, view: WebView | None) -> bool:
        """Return whether a managed view is pinned."""
        tab_id = self.tab_id_for(view)
        return bool(tab_id and tab_id in self._pinned_ids)

    def is_tab_visible(self, view: WebView | None) -> bool:
        """Return false for a member of a collapsed group."""
        tab_id = self.tab_id_for(view)
        group = self.group_manager.group_for_tab(tab_id)
        return not (group and group.collapsed)

    def visible_indices(self) -> list[int]:
        """Return current model indices visible in the tab strip."""
        return [index for index, view in enumerate(self._views) if self.is_tab_visible(view)]

    def create_tab(
        self,
        url: QUrl | str | None = None,
        activate: bool = True,
        opened_for_popup: bool = False,
        opener_view: WebView | None = None,
        tab_id: str | None = None,
        tab_title: str = "",
        pinned: bool = False,
        group_id: str | None = None,
        insert_index: int | None = None,
        group_position: int | None = None,
    ) -> WebView:
        """Create one WebView and insert its model entry without replacing peers."""
        view = WebView(profile=self._profile)
        existing_ids = set(self._tab_ids.values())
        actual_id = tab_id if tab_id and tab_id not in existing_ids else None
        actual_id = actual_id or SessionSnapshot.new_tab_id()
        self._tab_ids[view] = actual_id
        view.restored_title = tab_title
        if pinned:
            self._pinned_ids.add(actual_id)
        view._custom_page.set_download_context(view, self, opened_for_popup, opener_view)

        def create_popup_page() -> WebPage:
            return self.create_tab(opened_for_popup=True, opener_view=view)._custom_page

        view._custom_page.set_window_factory(create_popup_page)
        target_index = len(self._views) if insert_index is None else max(0, min(insert_index, len(self._views)))
        self._views.insert(target_index, view)
        if group_id and not pinned and self.group_manager.group(group_id) is not None:
            self.group_manager.add_tab(group_id, actual_id, position=group_position)
        old_order = list(self._views)
        self._normalize_order()
        if self._views != old_order:
            self.tab_order_changed.emit()

        new_index = self._views.index(view)
        self.tab_created.emit(new_index, view)
        self.count_changed.emit(len(self._views))
        target = self._default_url if url is None else url
        view.navigate(normalize_url(target) if isinstance(target, str) else target)
        if activate or len(self._views) == 1:
            self.set_current_index(new_index)
        self.state_changed.emit()
        logger.info("Created browser tab at index %d", new_index)
        return view

    def pin_tab(self, view: WebView) -> bool:
        """Pin a tab, ungrouping it and moving it before every regular tab."""
        tab_id = self.tab_id_for(view)
        if tab_id is None or tab_id in self._pinned_ids:
            return False
        self.group_manager.remove_tab(tab_id)
        self._pinned_ids.add(tab_id)
        self._normalize_order()
        self.tab_order_changed.emit()
        self.state_changed.emit()
        return True

    def unpin_tab(self, view: WebView) -> bool:
        """Unpin a tab and move it after all currently pinned tabs."""
        tab_id = self.tab_id_for(view)
        if tab_id is None or tab_id not in self._pinned_ids:
            return False
        self._pinned_ids.remove(tab_id)
        self._normalize_order()
        self.tab_order_changed.emit()
        self.state_changed.emit()
        return True

    def duplicate_tab(self, index: int) -> WebView | None:
        """Duplicate the current URL immediately after its source tab."""
        source = self.view_at(index)
        if source is None:
            return None
        source_id = self.tab_id_for(source)
        group_id = self.group_manager.group_id_for_tab(source_id)
        group = self.group_manager.group(group_id)
        group_position = group.tab_ids.index(source_id) + 1 if group and source_id else None
        return self.create_tab(
            QUrl(source.url()),
            activate=True,
            tab_title=source.title(),
            pinned=self.is_pinned(source),
            group_id=group_id,
            insert_index=index + 1,
            group_position=group_position,
        )

    def create_group(self, name: str, color: str, view: WebView | None = None) -> str:
        """Create a named group, optionally placing a tab in it immediately."""
        if view is not None and (self.tab_id_for(view) is None or self.is_pinned(view)):
            raise ValueError("Pinned or unmanaged tabs cannot be grouped")
        group_id = self.group_manager.create_group(name, color)
        if view is not None:
            self.group_manager.add_tab(group_id, self.tab_id_for(view))
            self._normalize_order()
            self.tab_order_changed.emit()
        self.state_changed.emit()
        return group_id

    def add_tab_to_group(self, view: WebView, group_id: str) -> bool:
        """Move a regular tab into a group and keep its members contiguous."""
        tab_id = self.tab_id_for(view)
        group = self.group_manager.group(group_id)
        if tab_id is None or group is None or self.is_pinned(view):
            return False
        if self.group_manager.group_id_for_tab(tab_id) == group_id:
            return False
        if not self.group_manager.add_tab(group_id, tab_id):
            return False
        self._normalize_order()
        self.tab_order_changed.emit()
        self.state_changed.emit()
        return True

    def remove_tab_from_group(self, view: WebView) -> bool:
        """Ungroup a tab without closing its WebView."""
        tab_id = self.tab_id_for(view)
        if tab_id is None or self.group_manager.group_id_for_tab(tab_id) is None:
            return False
        self.group_manager.remove_tab(tab_id)
        self._normalize_order()
        self.tab_order_changed.emit()
        self.state_changed.emit()
        return True

    def ungroup(self, group_id: str) -> list[str]:
        """Ungroup all members and leave each view open."""
        tab_ids = self.group_manager.ungroup(group_id)
        if tab_ids:
            self._normalize_order()
            self.tab_order_changed.emit()
            self.state_changed.emit()
        return tab_ids

    def reorder_group(self, group_id: str, target_index: int) -> bool:
        """Reorder a complete group section while retaining member view objects."""
        if not self.group_manager.reorder_group(group_id, target_index):
            return False
        old = list(self._views)
        self._normalize_order()
        if self._views != old:
            self.tab_order_changed.emit()
        self.state_changed.emit()
        return True

    def close_group(self, group_id: str, *, record_closed: bool = True) -> int:
        """Close all group tabs by stable ID; the normal last-tab rule still applies."""
        group = self.group_manager.group(group_id)
        if group is None:
            return 0
        view_ids = list(group.tab_ids)
        closed = 0
        for tab_id in reversed(view_ids):
            view = self.view_for_tab_id(tab_id)
            if view is not None:
                index = self.index_of(view)
                if self.close_tab(index, force=True, record_closed=record_closed):
                    closed += 1
        return closed

    def collapse_group(self, group_id: str, collapsed: bool) -> bool:
        """Change visibility while ensuring a collapsed active tab is replaced."""
        group = self.group_manager.group(group_id)
        if group is None or group.collapsed == bool(collapsed):
            return False
        if collapsed and self.tab_id_for(self.current_view()) in group.tab_ids:
            alternatives = [i for i in self.visible_indices() if self.tab_id_for(self.view_at(i)) not in group.tab_ids]
            if alternatives:
                self.set_current_index(alternatives[0])
            else:
                self.create_tab(self._default_url, activate=True)
        self.group_manager.set_collapsed(group_id, collapsed)
        self.state_changed.emit()
        return True

    def move_tab(self, from_index: int, to_index: int) -> None:
        """Reorder a tab, transfer it to the drop target's group, and preserve pins."""
        if not (0 <= from_index < len(self._views) and 0 <= to_index < len(self._views)):
            return
        if from_index == to_index:
            return
        active = self.current_view()
        source = self._views[from_index]
        source_id = self.tab_id_for(source)
        target = self._views[to_index]
        source_group = self.group_manager.group_id_for_tab(source_id)
        target_group = self.group_manager.group_id_for_tab(self.tab_id_for(target))
        was_pinned = self.is_pinned(source)

        self._views.pop(from_index)
        self._views.insert(to_index, source)
        if not was_pinned and target is not source and target_group != source_group:
            if target_group:
                self.group_manager.add_tab(target_group, source_id)
            elif source_group:
                self.group_manager.remove_tab(source_id)
        self._normalize_order()
        if active is not None:
            self._current_index = self._views.index(active)
        self.tab_moved.emit(from_index, self._views.index(source))
        self.tab_order_changed.emit()
        self.state_changed.emit()

    def close_tab(self, index: int, *, force: bool = False, record_closed: bool = True) -> bool:
        """Close a tab, refusing accidental close actions on pinned tabs."""
        view = self.view_at(index)
        if view is None or (self.is_pinned(view) and not force):
            return False
        if record_closed and not self._is_private:
            url = view.url()
            if url.isValid() and not url.isEmpty() and url.toString() != "about:blank":
                tab_id = self.tab_id_for(view)
                group_id = self.group_manager.group_id_for_tab(tab_id)
                group = self.group_manager.group(group_id)
                group_position = group.tab_ids.index(tab_id) if group and tab_id in group.tab_ids else None
                self.tab_history.record(
                    ClosedTab(QUrl(url), view.title(), index, group_id, self.is_pinned(view), group_position)
                )
        was_active = index == self._current_index
        self.tab_closing.emit(index, view)
        self._views.pop(index)
        tab_id = self._tab_ids.pop(view, None)
        if tab_id:
            self.group_manager.remove_tab(tab_id)
            self._pinned_ids.discard(tab_id)
        self.tab_closed.emit(index)
        if not self._views:
            self._current_index = -1
            self.create_tab(self._default_url, activate=True)
        elif was_active:
            self._current_index = -1
            self.set_current_index(min(index, len(self._views) - 1))
        elif index < self._current_index:
            self._current_index -= 1
        self.count_changed.emit(len(self._views))
        self.state_changed.emit()
        try:
            view.stop()
        except RuntimeError:
            pass
        view.deleteLater()
        logger.info("Closed browser tab; %d tabs remain", len(self._views))
        return True

    def close_current_tab(self, *, force: bool = False) -> bool:
        """Close the active tab subject to pinned-tab protection."""
        return self.close_tab(self._current_index, force=force)

    def dispose_all_tabs(self) -> None:
        """Destroy every live view without creating a replacement final tab."""
        for view in tuple(reversed(self._views)):
            index=self.index_of(view)
            if index<0:continue
            self.tab_closing.emit(index,view)
            self._views.pop(index)
            tab_id=self._tab_ids.pop(view,None)
            if tab_id:
                self.group_manager.remove_tab(tab_id)
                self._pinned_ids.discard(tab_id)
            self.tab_closed.emit(index)
            try:view.stop()
            except RuntimeError:pass
            view.deleteLater()
        self._current_index=-1
        self.group_manager.clear_membership()
        self.count_changed.emit(0)
        self.state_changed.emit()

    def close_other_tabs(self, index: int) -> int:
        """Close all unpinned tabs except the selected tab."""
        keep = self.view_at(index)
        if keep is None:
            return 0
        removed = 0
        for view in tuple(self._views):
            if view is not keep and not self.is_pinned(view):
                if self.close_tab(self.index_of(view)):
                    removed += 1
        self.set_current_index(self.index_of(keep))
        return removed

    def close_tabs_to_right(self, index: int) -> int:
        """Close unpinned tabs to the right of the selected tab."""
        selected = self.view_at(index)
        if selected is None:
            return 0
        candidates = tuple(self._views[index + 1 :])
        removed = 0
        for view in reversed(candidates):
            if not self.is_pinned(view) and self.close_tab(self.index_of(view)):
                removed += 1
        return removed

    def restore_closed_tab(self, selected: ClosedTab | None = None) -> WebView | None:
        """Restore a selected recent tab or the newest one, if it remains valid."""
        while True:
            closed = self.tab_history.take(selected) if selected is not None else self.tab_history.pop()
            selected=None
            if closed is None:
                return None
            safe_url = SessionSnapshot.sanitize_url(closed.url.toString())
            if safe_url is None:
                continue
            group = self.group_manager.group(closed.group_id)
            return self.create_tab(
                QUrl(safe_url),
                activate=True,
                tab_title=closed.title,
                pinned=closed.pinned and group is None,
                group_id=group.id if group and not closed.pinned else None,
                insert_index=closed.position,
                group_position=closed.group_position if group else None,
            )

    def clear_closed_tabs(self) -> None:
        """Clear the recently-closed stack."""
        self.tab_history.clear()

    def closed_tabs_count(self) -> int:
        """Return the number of recent tabs available for reopening."""
        return len(self.tab_history)

    def set_current_index(self, index: int) -> None:
        """Select a tab, expanding its group first if it is currently collapsed."""
        if not (0 <= index < len(self._views)):
            return
        view = self._views[index]
        group_id = self.group_manager.group_id_for_tab(self.tab_id_for(view))
        group = self.group_manager.group(group_id)
        if group and group.collapsed:
            self.group_manager.set_collapsed(group.id, False)
        if index == self._current_index:
            return
        self._current_index = index
        self.current_changed.emit(index, view)
        self.state_changed.emit()

    def switch_to_tab(self, index: int) -> None:
        """Switch by model index, revealing collapsed tabs as needed."""
        self.set_current_index(index)

    def switch_to_last_tab(self) -> None:
        """Switch to the final currently visible tab."""
        visible = self.visible_indices()
        if visible:
            self.set_current_index(visible[-1])

    def next_tab(self) -> None:
        """Select the next visible tab, wrapping at the end."""
        self._switch_visible(1)

    def prev_tab(self) -> None:
        """Select the previous visible tab, wrapping at the beginning."""
        self._switch_visible(-1)

    def _switch_visible(self, direction: int) -> None:
        visible = self.visible_indices()
        if len(visible) < 2:
            return
        try:
            current_position = visible.index(self._current_index)
        except ValueError:
            current_position = 0
        self.set_current_index(visible[(current_position + direction) % len(visible)])

    def normalize_order(self) -> None:
        """Publicly normalize pins and group sections after an external model edit."""
        old = list(self._views)
        self._normalize_order()
        if self._views != old:
            self.tab_order_changed.emit()
            self.state_changed.emit()

    def _normalize_order(self) -> None:
        """Keep pins first and each non-empty group in one contiguous section."""
        if not self._views:
            return
        active = self.current_view()
        original = list(self._views)
        pinned = [view for view in original if self.is_pinned(view)]
        regular = [view for view in original if not self.is_pinned(view)]
        sections: list[tuple[str, object]] = []
        seen_groups: set[str] = set()
        members_by_group: dict[str, list[WebView]] = {}
        for view in regular:
            tab_id = self.tab_id_for(view)
            group_id = self.group_manager.group_id_for_tab(tab_id)
            if group_id is None:
                sections.append(("tab", view))
            elif group_id not in seen_groups:
                seen_groups.add(group_id)
                sections.append(("group", group_id))
                members_by_group[group_id] = [
                    member for member in regular
                    if self.group_manager.group_id_for_tab(self.tab_id_for(member)) == group_id
                ]
        group_rank = {group.id: rank for rank, group in enumerate(self.group_manager.groups())}
        group_sections = [item for item in sections if item[0] == "group"]
        group_sections.sort(key=lambda item: group_rank.get(str(item[1]), len(group_rank)))
        group_iter = iter(group_sections)
        normalized: list[WebView] = list(pinned)
        for kind, payload in sections:
            if kind == "tab":
                normalized.append(payload)  # type: ignore[arg-type]
            else:
                next_group = next(group_iter)
                normalized.extend(members_by_group.get(str(next_group[1]), []))
        self._views = normalized
        if active in self._views:
            self._current_index = self._views.index(active)

    def _find_group_member_position(self, group_id: str, tab_id: str) -> int:
        group = self.group_manager.group(group_id)
        return group.tab_ids.index(tab_id) if group and tab_id in group.tab_ids else -1
