"""Isolation tests for hierarchical SQLite bookmarks."""

import pytest
import json

from browser.features.bookmarks.bookmark_manager import BookmarkManager


def test_hierarchy_order_and_circular_moves_are_safe(tmp_path):
    manager=BookmarkManager(tmp_path/"browser.sqlite3")
    folder=manager.create_folder("Development")
    nested=manager.create_folder("Python",folder)
    one=manager.create_bookmark("Docs","https://docs.python.org/",nested)
    two=manager.create_bookmark("Code","https://github.com/",folder)
    assert [item.id for item in manager.children(folder)]==[nested,two]
    assert manager.get_item(one).parent_id==nested
    assert {item.id for item in manager.search("develop")}=={one,two}
    with pytest.raises(ValueError):manager.move_item(folder,nested)
    manager.move_item(two,nested,0)
    assert [item.id for item in manager.children(nested)]==[two,one]
    assert manager.delete_item(folder)
    assert manager.get_item(one) is None
    assert [root.id for root in manager.roots()]==[1,2]


def test_duplicate_and_unsafe_urls_rejected_and_legacy_api_works(tmp_path):
    manager=BookmarkManager(tmp_path/"bookmarks.sqlite3")
    assert manager.add_bookmark("Example","https://example.com")
    assert not manager.add_bookmark("Duplicate","https://example.com")
    assert not manager.add_bookmark("Internal","javascript:alert(1)")
    assert manager.is_bookmarked("https://example.com")
    assert manager.remove_bookmark("https://example.com")
    assert not manager.is_bookmarked("https://example.com")


def test_import_is_transactional_and_preserves_folder_order(tmp_path):
    manager=BookmarkManager(tmp_path/"bookmarks.sqlite3")
    nodes=[{"type":"folder","title":"A","children":[
        {"type":"bookmark","title":"One","url":"https://one.test/"},
        {"type":"bookmark","title":"Unsafe","url":"javascript:alert(1)"},
        {"type":"folder","title":"Nested","children":[{"type":"bookmark","title":"Two","url":"https://two.test/"}]},
    ]}]
    assert manager.import_tree(nodes)==(2,2,1)
    folder=manager.children(manager.BAR_ROOT_ID)[0]
    assert folder.title=="A"
    assert [item.title for item in manager.children(folder.id)]==["One","Nested"]
    assert manager.children(manager.children(folder.id)[1].id)[0].title=="Two"


def test_legacy_json_migration_is_one_time_and_keeps_source(tmp_path):
    database=tmp_path/"browser.sqlite3"
    legacy=tmp_path/"bookmarks.json"
    legacy.write_text(json.dumps([{"title":"Legacy","url":"https://legacy.example/"}]),encoding="utf-8")
    manager=BookmarkManager(database)
    manager._legacy_path=legacy
    with manager._connect() as db:
        db.execute("INSERT OR IGNORE INTO bookmark_migrations(version,applied_at) VALUES(1,'old-migration')")
    manager._migrate_legacy_json()
    assert manager.is_bookmarked("https://legacy.example/")
    assert legacy.exists()
    assert manager.remove_bookmark("https://legacy.example/")
    manager._migrate_legacy_json()
    assert not manager.is_bookmarked("https://legacy.example/")
