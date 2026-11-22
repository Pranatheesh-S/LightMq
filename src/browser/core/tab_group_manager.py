"""Source-of-truth model for named, colored tab groups."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from PySide6.QtCore import QObject, Signal

GROUP_COLORS: dict[str, str] = {
    "grey": "#80868B",
    "blue": "#1A73E8",
    "red": "#D93025",
    "yellow": "#F9AB00",
    "green": "#188038",
    "purple": "#9334E6",
    "pink": "#D01884",
    "cyan": "#007B83",
}
MAX_GROUP_NAME_LENGTH = 40


@dataclass
class TabGroup:
    """One group definition and its ordered member tab IDs."""

    id: str
    name: str
    color: str
    collapsed: bool = False
    tab_ids: list[str] = field(default_factory=list)


class TabGroupManager(QObject):
    """Manage group identity, ordered membership, and display properties."""

    groups_changed = Signal()
    group_changed = Signal(str)
    state_changed = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._groups: list[TabGroup] = []

    def groups(self) -> tuple[TabGroup, ...]:
        """Return copies of groups in their visual order."""
        return tuple(
            TabGroup(group.id, group.name, group.color, group.collapsed, list(group.tab_ids))
            for group in self._groups
        )

    def group(self, group_id: str | None) -> TabGroup | None:
        """Return a copy of a group by stable ID."""
        found = next((item for item in self._groups if item.id == group_id), None)
        if found is None:
            return None
        return TabGroup(found.id, found.name, found.color, found.collapsed, list(found.tab_ids))

    def group_id_for_tab(self, tab_id: str | None) -> str | None:
        """Return the unique group containing ``tab_id``."""
        if tab_id is None:
            return None
        return next((group.id for group in self._groups if tab_id in group.tab_ids), None)

    def group_for_tab(self, tab_id: str | None) -> TabGroup | None:
        """Return a copy of the group containing ``tab_id``."""
        return self.group(self.group_id_for_tab(tab_id))

    def create_group(
        self,
        name: str,
        color: str = "blue",
        group_id: str | None = None,
        collapsed: bool = False,
        position: int | None = None,
    ) -> str:
        """Create a group; duplicate names are valid, IDs must be unique."""
        cleaned_name = self._clean_name(name)
        normalized_color = self.normalize_color(color)
        candidate_id = group_id if group_id and not self.group(group_id) else f"group-{uuid4().hex}"
        group = TabGroup(candidate_id, cleaned_name, normalized_color, bool(collapsed))
        if position is None or position < 0 or position >= len(self._groups):
            self._groups.append(group)
        else:
            self._groups.insert(position, group)
        self._emit_changed(candidate_id)
        return candidate_id

    def restore_groups(self, groups: list[dict[str, object]]) -> None:
        """Replace group definitions with validated, empty groups for restoration."""
        self._groups.clear()
        seen: set[str] = set()
        def position(entry: dict[str, object]) -> int:
            value = entry.get("position", 0)
            return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0

        for raw in sorted(groups, key=position):
            group_id = raw.get("id")
            if not isinstance(group_id, str) or not group_id or group_id in seen:
                continue
            name = raw.get("name", "Group")
            color = raw.get("color", "blue")
            if not isinstance(name, str) or not isinstance(color, str):
                continue
            try:
                cleaned_name = self._clean_name(name)
            except ValueError:
                cleaned_name = "Group"
            self._groups.append(
                TabGroup(
                    group_id[:80],
                    cleaned_name,
                    self.normalize_color(color),
                    bool(raw.get("collapsed", False)),
                )
            )
            seen.add(group_id)
        self.groups_changed.emit()
        self.state_changed.emit()

    def add_tab(self, group_id: str, tab_id: str, *, position: int | None = None) -> bool:
        """Move a tab into a group, ensuring it belongs to at most one group."""
        target = self._find_group(group_id)
        if target is None or not tab_id:
            return False
        previous = self._find_group(self.group_id_for_tab(tab_id))
        if previous is target and tab_id in target.tab_ids:
            if position is None:
                return False
            target.tab_ids.remove(tab_id)
        elif previous is not None:
            previous.tab_ids.remove(tab_id)
        if position is None or position < 0 or position >= len(target.tab_ids):
            target.tab_ids.append(tab_id)
        else:
            target.tab_ids.insert(position, tab_id)
        if previous is not None and previous is not target:
            self._remove_if_empty(previous)
        self._emit_changed(group_id)
        return True

    def remove_tab(self, tab_id: str) -> str | None:
        """Remove a tab from its group and delete the group if now empty."""
        group = self._find_group(self.group_id_for_tab(tab_id))
        if group is None:
            return None
        group.tab_ids.remove(tab_id)
        group_id = group.id
        self._remove_if_empty(group)
        self._emit_changed(group_id)
        return group_id

    def rename_group(self, group_id: str, name: str) -> bool:
        """Rename a group without requiring names to be unique."""
        group = self._find_group(group_id)
        if group is None:
            return False
        group.name = self._clean_name(name)
        self._emit_changed(group_id)
        return True

    def set_color(self, group_id: str, color: str) -> bool:
        """Set a supported named group color."""
        group = self._find_group(group_id)
        if group is None:
            return False
        group.color = self.normalize_color(color)
        self._emit_changed(group_id)
        return True

    def set_collapsed(self, group_id: str, collapsed: bool) -> bool:
        """Collapse or expand a group without changing its member tabs."""
        group = self._find_group(group_id)
        if group is None:
            return False
        if group.collapsed != bool(collapsed):
            group.collapsed = bool(collapsed)
            self._emit_changed(group_id)
        return True

    def toggle_collapsed(self, group_id: str) -> bool:
        """Toggle group visibility and return the new collapsed state."""
        group = self._find_group(group_id)
        if group is None:
            return False
        self.set_collapsed(group_id, not group.collapsed)
        return group.collapsed

    def reorder_group(self, group_id: str, target_index: int) -> bool:
        """Move an entire group in the group header order."""
        source_index = next((i for i, group in enumerate(self._groups) if group.id == group_id), -1)
        if source_index < 0 or not self._groups:
            return False
        target_index = max(0, min(target_index, len(self._groups) - 1))
        if source_index == target_index:
            return False
        group = self._groups.pop(source_index)
        self._groups.insert(target_index, group)
        self.groups_changed.emit()
        self.state_changed.emit()
        return True

    def ungroup(self, group_id: str) -> list[str]:
        """Remove a group while returning its tabs in their current member order."""
        group = self._find_group(group_id)
        if group is None:
            return []
        tab_ids = list(group.tab_ids)
        self._groups.remove(group)
        self.groups_changed.emit()
        self.state_changed.emit()
        return tab_ids

    def clear_membership(self) -> None:
        """Remove groups with no tabs after restoration has completed."""
        old_count = len(self._groups)
        self._groups = [group for group in self._groups if group.tab_ids]
        if len(self._groups) != old_count:
            self.groups_changed.emit()
            self.state_changed.emit()

    @staticmethod
    def normalize_color(color: str) -> str:
        """Return a palette color key, defaulting unknown values to blue."""
        key = str(color).strip().lower()
        return key if key in GROUP_COLORS else "blue"

    @staticmethod
    def _clean_name(name: str) -> str:
        cleaned = " ".join(str(name).split())
        if not cleaned:
            raise ValueError("Group name cannot be empty")
        return cleaned[:MAX_GROUP_NAME_LENGTH]

    def _find_group(self, group_id: str | None) -> TabGroup | None:
        return next((group for group in self._groups if group.id == group_id), None)

    def _remove_if_empty(self, group: TabGroup) -> None:
        if not group.tab_ids and group in self._groups:
            self._groups.remove(group)

    def _emit_changed(self, group_id: str) -> None:
        self.group_changed.emit(group_id)
        self.groups_changed.emit()
        self.state_changed.emit()
