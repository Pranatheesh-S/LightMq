"""Unit tests for BookmarkManager, HistoryManager, and DownloadManager."""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication

from browser.features.bookmarks.bookmark_manager import BookmarkManager
from browser.features.history.history_manager import HistoryManager
from browser.features.downloads.download_manager import DownloadManager

app = QApplication.instance() or QApplication(sys.argv)


def test_bookmark_manager_operations(tmp_path):
    """Verify add, check, list, remove, and clear operations."""
    storage_file = tmp_path / "test_bookmarks.json"
    mgr = BookmarkManager(storage_path=storage_file)

    assert mgr.get_bookmarks() == []

    # Add bookmark
    assert mgr.add_bookmark("Google", "https://google.com") is True
    assert mgr.is_bookmarked("https://google.com") is True

    # Duplicate add returns False
    assert mgr.add_bookmark("Google Duplicate", "https://google.com") is False

    # Remove bookmark
    assert mgr.remove_bookmark("https://google.com") is True
    assert mgr.is_bookmarked("https://google.com") is False
    assert mgr.remove_bookmark("https://google.com") is False

    # Clear
    mgr.add_bookmark("Item 1", "https://item1.com")
    mgr.add_bookmark("Item 2", "https://item2.com")
    assert len(mgr.get_bookmarks()) == 2
    mgr.clear()
    assert len(mgr.get_bookmarks()) == 0


def test_history_manager_operations(tmp_path):
    """Verify history entry addition, query filtering, and clearing."""
    storage_file = tmp_path / "test_history.json"
    mgr = HistoryManager(storage_path=storage_file)

    # Empty URL or about:blank is rejected
    assert mgr.add_entry("", "Empty") is False
    assert mgr.add_entry("about:blank", "Blank") is False

    # Valid entry
    assert mgr.add_entry("https://python.org", "Python Home") is True
    assert mgr.add_entry("https://github.com/topics", "GitHub Topics") is True

    # Query
    results = mgr.get_entries("python")
    assert len(results) == 1
    assert results[0]["title"] == "Python Home"

    # Clear
    mgr.clear()
    assert mgr.get_entries() == []


def test_history_sqlite_persistence_filters_and_visit_deletion(tmp_path):
    """SQLite history keeps independent visits and supports range and search filters."""
    storage_file = tmp_path / "browser.sqlite3"
    mgr = HistoryManager(storage_path=storage_file)
    old = datetime.now(timezone.utc) - timedelta(days=2)
    now = datetime.now(timezone.utc)
    assert mgr.add_entry("https://example.org/page", "Example", visited_at=old)
    assert mgr.add_entry("https://example.org/page", "Example latest", visited_at=now)
    assert mgr.add_entry("https://other.org/100%_done", "Other", visited_at=now)

    reopened = HistoryManager(storage_path=storage_file)
    assert reopened.count_entries() == 3
    assert reopened.count_entries("100%_done") == 1
    recent = reopened.get_entries(start=now - timedelta(hours=1))
    assert len(recent) == 2
    assert recent[0]["title"] in {"Example latest", "Other"}
    first = reopened.get_entries()[0]
    assert reopened.delete_entry(int(first["id"])) is True
    assert reopened.count_entries() == 2
    reopened.clear(start=now - timedelta(hours=1))
    assert reopened.count_entries() == 1
    assert reopened.get_entries()[0]["url"] == "https://example.org/page"
    assert reopened.delete_url("https://example.org/page") == 1
    assert reopened.count_entries() == 0


def test_history_rejects_non_web_urls_and_removes_url_credentials(tmp_path):
    """Only public HTTP(S) visits are recorded; user-info is never persisted."""
    mgr = HistoryManager(storage_path=tmp_path / "history.sqlite3")
    for url in ("", "about:blank", "file:///private.txt", "javascript:alert(1)", "devtools://devtools"):
        assert mgr.add_entry(url, "internal") is False
    assert mgr.add_entry("https://person:secret@example.com/path", "Example") is True
    assert mgr.get_entries()[0]["url"] == "https://example.com/path"

    private_policy = HistoryManager(storage_path=tmp_path / "private.sqlite3", recording_enabled=False)
    assert private_policy.add_entry("https://example.com", "private") is False
    assert private_policy.count_entries() == 0


def test_download_manager_operations():
    """Verify download manager list and clear."""
    mgr = DownloadManager()
    assert mgr.get_downloads() == []
    mgr.clear()
    assert mgr.get_downloads() == []
