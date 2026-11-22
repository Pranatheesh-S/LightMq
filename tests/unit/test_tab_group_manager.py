"""Group identity and membership invariants."""

import sys

from PySide6.QtWidgets import QApplication

from browser.core.tab_group_manager import TabGroupManager

app = QApplication.instance() or QApplication(sys.argv)


def test_group_membership_is_unique_and_empty_groups_are_removed():
    manager = TabGroupManager()
    first = manager.create_group("Study", "blue")
    second = manager.create_group("Study", "green")
    manager.add_tab(first, "tab-a")
    manager.add_tab(first, "tab-b")
    manager.add_tab(second, "tab-a")
    assert manager.group_id_for_tab("tab-a") == second
    assert manager.group(first).tab_ids == ["tab-b"]
    manager.remove_tab("tab-b")
    assert manager.group(first) is None


def test_group_name_color_collapse_and_order_are_editable():
    manager = TabGroupManager()
    first = manager.create_group(" Work   tasks ", "red")
    second = manager.create_group("Study", "not-a-color")
    assert manager.rename_group(first, "Development")
    assert manager.set_color(second, "purple")
    assert manager.set_collapsed(first, True)
    assert manager.reorder_group(second, 0)
    groups = manager.groups()
    assert [group.id for group in groups] == [second, first]
    assert groups[0].color == "purple"
    assert groups[1].name == "Development" and groups[1].collapsed


def test_restore_groups_ignores_invalid_positions_and_duplicate_ids():
    manager = TabGroupManager()
    manager.restore_groups([
        {"id": "g1", "name": "One", "color": "blue", "position": "broken"},
        {"id": "g1", "name": "Duplicate", "color": "red", "position": 1},
        {"id": "", "name": "Invalid", "color": "red"},
    ])
    assert len(manager.groups()) == 1
    assert manager.groups()[0].id == "g1"
