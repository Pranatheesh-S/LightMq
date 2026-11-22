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


def test_schema_one_migrates_and_schema_two_preserves_tab_group_metadata():
    legacy = SessionSnapshot.from_dict({
        "schema_version": 1,
        "tabs": [{"id": "legacy", "url": "https://example.com", "title": "Example", "position": 0}],
    })
    assert legacy.tabs[0].pinned is False
    assert legacy.tabs[0].group_id is None
    assert legacy.to_dict()["schema_version"] == 2
    snapshot = SessionSnapshot.from_dict({
        "schema_version": 2,
        "tabs": [
            {"id": "p", "url": "https://example.com", "position": 0, "pinned": True, "group_id": "g"},
            {"id": "n", "url": "https://example.org", "position": 1, "group_id": "g"},
        ],
        "groups": [{"id": "g", "name": "Work", "color": "cyan", "collapsed": True, "position": 0}],
    })
    assert snapshot.tabs[0].group_id is None
    assert snapshot.tabs[1].group_id == "g"
    assert snapshot.groups[0].collapsed is True


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


def test_restore_toggle_persists_and_parses_false_as_false(tmp_path):
    settings = QSettings(str(tmp_path / "restore.ini"), QSettings.Format.IniFormat)
    preferences = StartupSettings(settings)
    assert preferences.restore_previous_session() is True

    settings.setValue(StartupSettings.RESTORE_KEY, "false")
    settings.sync()
    restarted = StartupSettings(
        QSettings(str(tmp_path / "restore.ini"), QSettings.Format.IniFormat)
    )
    assert restarted.restore_previous_session() is False
    assert restarted.mode() is StartupMode.NEW_TAB

    restarted.set_restore_previous_session(True)
    assert StartupSettings(
        QSettings(str(tmp_path / "restore.ini"), QSettings.Format.IniFormat)
    ).restore_previous_session() is True


@pytest.mark.parametrize(
    ("legacy_mode", "expected_restore", "expected_fallback"),
    [
        ("continue", True, StartupMode.NEW_TAB),
        ("homepage", False, StartupMode.HOMEPAGE),
        ("new_tab", False, StartupMode.NEW_TAB),
    ],
)
def test_startup_setting_migrates_existing_mode(
    tmp_path, legacy_mode, expected_restore, expected_fallback
):
    settings = QSettings(str(tmp_path / f"{legacy_mode}.ini"), QSettings.Format.IniFormat)
    settings.setValue(StartupSettings.MODE_KEY, legacy_mode)
    settings.sync()
    preferences = StartupSettings(settings)

    assert preferences.restore_previous_session() is expected_restore
    assert preferences.fallback_mode() is expected_fallback
    assert preferences.settings.value(StartupSettings.RESTORE_KEY) is expected_restore


def test_qsavefile_failure_preserves_last_valid_snapshot(tmp_path, monkeypatch):
    repository = SessionRepository(tmp_path)
    assert repository.save(_snapshot())
    previous = repository.current_path.read_bytes()

    monkeypatch.setattr(repository, "_write_json", lambda _path, _value: False)
    assert repository.save(_snapshot()) is False
    assert repository.current_path.read_bytes() == previous
    assert json.loads(previous)["active_tab_id"] == "tab-b"
