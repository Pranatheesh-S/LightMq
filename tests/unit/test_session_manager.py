"""Unit coverage for safe session data, repository state, and startup settings."""

import json

import pytest
from PySide6.QtCore import QSettings

from browser.storage.session_model import SessionSnapshot, SessionTab
from browser.storage.session_repository import SessionRepository
from browser.storage.settings import StartupMode, StartupSettings


def _snapshot() -> SessionSnapshot:
    return SessionSnapshot.create(
        [
            SessionTab("tab-a", "https://one.example/", "One", 0),
            SessionTab("tab-b", "https://two.example/", "Two", 1),
        ],
        "tab-b",
    )


def test_snapshot_serialization_preserves_order_and_active_tab():
    snapshot = _snapshot()
    loaded = SessionSnapshot.from_dict(snapshot.to_dict())
    assert [tab.url for tab in loaded.tabs] == ["https://one.example/", "https://two.example/"]
    assert loaded.tabs[0].position == 0
    assert loaded.active_tab_id == "tab-b"


def test_snapshot_validation_skips_invalid_duplicate_and_sensitive_urls():
    loaded = SessionSnapshot.from_dict(
        {
            "schema_version": 1,
            "active_tab_id": "bad-id",
            "tabs": [
                {"id": "same", "url": "https://ok.example/", "title": "OK", "position": 2},
                {"id": "same", "url": "https://duplicate.example/", "position": 1},
                {"id": "internal", "url": "devtools://devtools/", "position": 0},
                {"id": "secret", "url": "https://example.com/?access_token=secret", "position": 3},
                {"id": "credential", "url": "https://user:pass@example.com/", "position": 4},
            ],
        }
    )
    assert [(tab.tab_id, tab.url, tab.position) for tab in loaded.tabs] == [
        ("same", "https://ok.example/", 0)
    ]
    assert loaded.active_tab_id == "same"


def test_snapshot_rejects_unknown_schema_and_handles_empty_state():
    with pytest.raises(ValueError):
        SessionSnapshot.from_dict({"schema_version": 99, "tabs": []})
    empty = SessionSnapshot.from_dict({"schema_version": 1, "tabs": []})
    assert empty.tabs == ()
    assert empty.active_tab_id is None


def test_repository_atomic_snapshot_and_crash_marker(tmp_path):
    repository = SessionRepository(tmp_path / "Sessions")
    assert repository.save(_snapshot())
    assert repository.current_path.exists()
    assert repository.recovery_path.exists()

    crashed, recovery = repository.begin_run()
    assert crashed is False
    assert recovery is None

    crashed, recovery = repository.begin_run()
    assert crashed is True
    assert recovery is not None
    assert recovery.active_tab_id == "tab-b"

    assert repository.mark_clean_shutdown()
    crashed, _ = repository.begin_run()
    assert crashed is False


def test_corrupt_current_session_does_not_destroy_recovery_snapshot(tmp_path):
    repository = SessionRepository(tmp_path)
    assert repository.save(_snapshot())
    original_recovery = repository.recovery_path.read_bytes()
    repository.current_path.write_text("{ broken", encoding="utf-8")

    assert repository.load_current() is None
    recovery = repository.load_recovery()
    assert recovery is not None and len(recovery.tabs) == 2
    assert repository.recovery_path.read_bytes() == original_recovery


def test_startup_settings_default_validate_and_persist(tmp_path):
    settings = QSettings(str(tmp_path / "preferences.ini"), QSettings.Format.IniFormat)
    preferences = StartupSettings(settings)
    assert preferences.mode() is StartupMode.CONTINUE
    assert preferences.homepage() == StartupSettings.DEFAULT_HOMEPAGE

    preferences.set(StartupMode.HOMEPAGE, "example.org")
    assert preferences.mode() is StartupMode.HOMEPAGE
    assert preferences.homepage() == "https://example.org"
    with pytest.raises(ValueError):
        preferences.set(StartupMode.NEW_TAB, "javascript:alert(1)")


def test_qsavefile_failure_preserves_last_valid_snapshot(tmp_path, monkeypatch):
    repository = SessionRepository(tmp_path)
    assert repository.save(_snapshot())
    previous = repository.current_path.read_bytes()

    monkeypatch.setattr(repository, "_write_json", lambda _path, _value: False)
    assert repository.save(_snapshot()) is False
    assert repository.current_path.read_bytes() == previous
    assert json.loads(previous)["active_tab_id"] == "tab-b"
