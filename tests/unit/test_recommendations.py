"""Deterministic local recommendation ranking, privacy, and feedback tests."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

from PySide6.QtCore import QEventLoop, QSettings, QTimer
from PySide6.QtWidgets import QApplication

from browser.features.bookmarks.bookmark_manager import BookmarkManager
from browser.features.history.history_manager import HistoryManager
from browser.features.recommendations.recommendation_controller import RecommendationController
from browser.features.recommendations.recommendation_engine import (
    RecommendationEngine,
    recommendation_key,
    safe_recommendation_url,
)
from browser.features.recommendations.recommendation_repository import RecommendationRepository
from browser.storage.settings import BrowserSettings
from browser.ui.dialogs.clear_data_dialog import ClearDataDialog


app = QApplication.instance() or QApplication(sys.argv)


def _history(url: str, title: str, visits: int, last_visit: datetime) -> dict:
    return {
        "url": url,
        "title": title,
        "visit_count": visits,
        "last_visit_at": last_visit.astimezone(timezone.utc).isoformat(),
    }


def _all_cards(result: dict) -> list[dict]:
    return result["recommended"] + result["related"] + result["continue"]


def test_frequency_recency_bookmark_and_stable_category_ranking():
    now = datetime(2026, 11, 27, tzinfo=timezone.utc)
    history = [
        _history("https://frequent.example.com/", "Frequently visited", 25, now - timedelta(days=90)),
        _history("https://recent.example.net/", "Recently visited", 2, now - timedelta(hours=1)),
        _history("https://saved.example.org/", "Saved reference", 1, now - timedelta(days=2)),
        _history("https://another.example.edu/", "Another local page", 1, now - timedelta(days=3)),
    ]
    bookmarks = [{"url": "https://saved.example.org/", "title": "Saved reference", "folder": "Work"}]

    result = RecommendationEngine().recommend(history, bookmarks, [], now=now, limit=2)
    cards = _all_cards(result)
    by_host = {card["domain"]: card for card in cards}
    assert "Frequently visited" in by_host["frequent.example.com"]["reasons"]
    assert "Saved in bookmarks" in by_host["saved.example.org"]["reasons"]
    assert result["recommended"][0]["domain"] == "saved.example.org"
    keys = [card["key"] for card in cards]
    assert len(keys) == len(set(keys))


def test_recent_low_frequency_page_can_outrank_old_frequent_page():
    now = datetime(2026, 11, 27, tzinfo=timezone.utc)
    result = RecommendationEngine().recommend(
        [
            _history("https://old.example.com/", "Old popular", 100, now - timedelta(days=180)),
            _history("https://today.example.net/", "Visited today", 2, now),
        ], [], [], now=now, show_continue=False,
    )
    assert [item["domain"] for item in result["recommended"]][:2] == [
        "today.example.net", "old.example.com",
    ]


def test_related_pages_use_local_title_and_domain_overlap_only():
    now = datetime(2026, 11, 27, tzinfo=timezone.utc)
    result = RecommendationEngine().recommend(
        [
            _history("https://realpython.com/tutorials/", "Python documentation tutorials", 2, now),
            _history("https://sports.example.net/scores", "Football scores", 3, now),
        ], [], [], context_url="https://docs.python.org/3/", context_title="Python documentation",
        now=now, limit=8,
    )
    assert result["related"]
    assert result["related"][0]["domain"] == "realpython.com"
    assert "Related to current page" in result["related"][0]["reasons"]
    related_keys = {item["key"] for item in result["related"]}
    other_keys = {item["key"] for item in result["recommended"] + result["continue"]}
    assert related_keys.isdisjoint(other_keys)


def test_empty_data_and_current_page_are_not_invented_or_recommended():
    engine = RecommendationEngine()
    assert engine.recommend([], [], []) == {"recommended": [], "related": [], "continue": []}
    now = datetime(2026, 11, 27, tzinfo=timezone.utc)
    result = engine.recommend(
        [_history("https://example.com/path?q=old", "Current", 4, now)], [], [],
        context_url="https://example.com/path?q=active", now=now,
    )
    assert _all_cards(result) == []


def test_duplicate_urls_hidden_and_pinned_feedback():
    now = datetime(2026, 11, 27, tzinfo=timezone.utc)
    engine = RecommendationEngine()
    rows = [
        _history("https://keep.example.com/page?source=one", "Keep this", 2, now),
        _history("https://keep.example.com/page?source=two", "Keep this duplicate", 7, now - timedelta(days=1)),
        _history("https://hide.example.net/", "Hide this", 4, now),
    ]
    feedback = [
        {"url_key": "https://hide.example.net/", "is_hidden": 1, "is_pinned": 0},
        {"url_key": "https://pinned.example.org/", "domain": "pinned.example.org",
         "title": "Pinned shortcut", "is_hidden": 0, "is_pinned": 1},
    ]
    result = engine.recommend(rows, [], feedback, now=now)
    cards = _all_cards(result)
    assert sum(card["domain"] == "keep.example.com" for card in cards) == 1
    assert not any(card["domain"] == "hide.example.net" for card in cards)
    assert any(card["domain"] == "pinned.example.org" and card["pinned"] for card in cards)


def test_sensitive_private_and_local_urls_are_excluded():
    unsafe = [
        "file:///C:/Users/person/private.pdf",
        "http://localhost:8080/admin",
        "https://printer.local/",
        "https://example.com/login",
        "https://example.com/reset/password",
        "https://example.com/download?access_token=secret",
        "https://example.com/path?x=" + "a" * 60,
        "https://user:password@example.com/",
        "https://127.0.0.1/",
    ]
    assert all(safe_recommendation_url(url) is None for url in unsafe)
    assert safe_recommendation_url("https://example.com:443/a?campaign=local#section") == "https://example.com/a?campaign=local"
    assert recommendation_key("https://example.com:8443/a?campaign=value#fragment") == "https://example.com:8443/a"


def test_feedback_repository_persists_only_sanitized_keys(tmp_path: Path):
    repository = RecommendationRepository(tmp_path / "recommendations.sqlite3")
    assert repository.set_hidden("https://[2001:4860:4860::8888]/guide?campaign=private", True, "A guide")
    assert repository.set_pinned("https://saved.example.com/path?campaign=secret", True, "Pinned")
    feedback = repository.feedback()
    assert all("?" not in row["url_key"] and "#" not in row["url_key"] for row in feedback)
    assert next(row for row in feedback if row["is_hidden"])["domain"] == "2001:4860:4860::8888"
    hidden = repository.hidden()
    assert len(hidden) == 1
    assert repository.reveal(hidden[0]["url_key"])
    repository.clear(include_pins=False)
    assert len(repository.feedback()) == 1
    repository.clear(include_pins=True)
    assert repository.feedback() == []


def test_history_candidates_ignore_reload_only_frequency(tmp_path: Path):
    manager = HistoryManager(tmp_path / "history.sqlite3")
    now = datetime(2026, 11, 27, tzinfo=timezone.utc)
    for index in range(8):
        manager.add_entry("https://reload.example.com/", "Reload", visit_type="reload",
                          visited_at=now - timedelta(minutes=index))
    manager.add_entry("https://reload.example.com/", "Typed", visit_type="typed", visited_at=now)
    row = manager.recommendation_candidates()[0]
    assert row["visit_count"] == 1
    assert row["last_visit_at"] == now.isoformat(timespec="seconds")


def test_controller_requires_opt_in_and_refreshes_in_worker(tmp_path: Path):
    history = HistoryManager(tmp_path / "history.sqlite3")
    bookmarks = BookmarkManager(tmp_path / "bookmarks.sqlite3")
    prefs = BrowserSettings(QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat))
    controller = RecommendationController(history, bookmarks, prefs)
    assert json.loads(controller.recommendations_json())["recommended"] == []
    assert not controller.show_on_new_tab or not controller.enabled

    now = datetime.now(timezone.utc)
    history.add_entry("https://local-sample.example.com/", "Synthetic local visit", visit_type="typed", visited_at=now)
    prefs.set("recommendations/enabled", True)
    assert json.loads(controller.recommendations_json())["recommended"] == []
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    controller.recommendations_ready.connect(lambda *_: loop.quit())
    timer.start(3000)
    loop.exec()
    timer.stop()
    data = json.loads(controller.recommendations_json())
    assert data["recommended"] or data["continue"]
    assert data["recommended"][0]["domain"] == "local-sample.example.com"
    reopened = BrowserSettings(QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat))
    assert reopened.get("recommendations/enabled", False) is True

    history.clear()
    loop = QEventLoop()
    timer = QTimer();timer.setSingleShot(True);timer.timeout.connect(loop.quit)
    controller.recommendations_ready.connect(lambda *_: loop.quit())
    timer.start(3000);loop.exec();timer.stop()
    after_delete = json.loads(controller.recommendations_json())
    assert after_delete == {"recommended": [], "related": [], "continue": []}

    prefs.set("recommendations/show_new_tab", False)
    assert json.loads(controller.recommendations_json())["recommended"] == []
    assert json.loads(controller.recommendations_json())["continue"] == []
    controller.clear_data()


def test_clear_all_history_pin_retention_requires_an_explicit_choice():
    dialog = ClearDataDialog()
    assert dialog.keep_recommendation_pins is False
    dialog.cb_keep_recommendation_pins.setChecked(True)
    assert dialog.keep_recommendation_pins is True
    dialog.period.setCurrentIndex(0)
    assert dialog.keep_recommendation_pins is False
    assert not dialog.cb_keep_recommendation_pins.isEnabled()
