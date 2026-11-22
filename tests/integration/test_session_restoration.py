"""Integration coverage for tab restore order, active selection, and profile reuse."""

from PySide6.QtWidgets import QApplication

from browser.core.session_manager import SessionManager
from browser.storage.session_repository import SessionRepository
from browser.storage.settings import StartupMode, StartupSettings
from browser.ui.main_window import MainWindow
from browser.ui.dialogs.startup_settings_dialog import StartupSettingsDialog
from PySide6.QtCore import QSettings

app = QApplication.instance() or QApplication([])


def test_session_restores_tabs_order_active_tab_and_shared_profile(tmp_path):
    repository = SessionRepository(tmp_path / "Sessions")
    first_manager = SessionManager(repository, app)
    first_manager.begin_run()
    first = MainWindow(initial_url="https://one.example/", session_manager=first_manager)
    first.tab_manager.create_tab("https://two.example/", activate=False)
    first.tab_manager.create_tab("https://three.example/", activate=False)
    first.tab_manager.set_current_index(1)

    assert first_manager.save_now()
    snapshot = repository.load_current()
    assert snapshot is not None

    second_manager = SessionManager(repository, app)
    second_manager.begin_run()
    restored = MainWindow(
        session_manager=second_manager,
        restore_snapshot=snapshot,
    )

    assert restored.tab_manager.count() == 3
    assert [restored.tab_manager.view_at(i).url().toString() for i in range(3)] == [
        "https://one.example/", "https://two.example/", "https://three.example/"
    ]
    assert restored.tab_manager.current_index() == 1
    assert restored.tab_bar.current_index() == 1
    assert second_manager.restore(snapshot) == 0
    assert restored.tab_manager.count() == 3
    assert restored.tab_manager.view_at(1).page().profile() is restored._profile
    assert all(
        restored.tab_manager.view_at(i).page().profile() is restored._profile
        for i in range(3)
    )
    restored.devtools_manager.open()
    assert restored.tab_manager.current_view().page().devToolsPage() == (
        restored.devtools_panel.get_page()
    )


def test_session_restores_pinned_tabs_and_named_collapsed_group(tmp_path):
    repository = SessionRepository(tmp_path / "Sessions")
    manager = SessionManager(repository, app)
    manager.begin_run()
    window = MainWindow(initial_url="https://one.example/", session_manager=manager)
    first = window.tab_manager.current_view()
    second = window.tab_manager.create_tab("https://two.example/", activate=False)
    third = window.tab_manager.create_tab("https://three.example/", activate=False)
    group_id = window.tab_manager.create_group("Research", "purple", second)
    window.tab_manager.add_tab_to_group(third, group_id)
    window.tab_manager.collapse_group(group_id, True)
    window.tab_manager.pin_tab(first)
    manager.save_now()
    snapshot = repository.load_current()
    assert snapshot is not None

    restored_manager = SessionManager(repository, app)
    restored_manager.begin_run()
    restored = MainWindow(session_manager=restored_manager, restore_snapshot=snapshot)
    restored_group = restored.tab_manager.group_manager.group(group_id)
    assert restored.tab_manager.is_pinned(restored.tab_manager.view_at(0))
    assert restored_group is not None
    assert restored_group.name == "Research" and restored_group.color == "purple"
    assert restored_group.collapsed is True
    assert len(restored_group.tab_ids) == 2
    assert restored.tab_bar.count() == 3
    assert all(restored.tab_manager.view_at(i) is not None for i in range(3))


def test_closing_tab_updates_snapshot_without_resurrecting_it(tmp_path):
    manager = SessionManager(SessionRepository(tmp_path / "Sessions"), app)
    manager.begin_run()
    window = MainWindow(initial_url="https://one.example/", session_manager=manager)
    window.tab_manager.create_tab("https://two.example/", activate=False)
    window.tab_manager.create_tab("https://three.example/", activate=False)
    window.tab_manager.close_tab(1)

    snapshot = manager.capture()
    assert [tab.url for tab in snapshot.tabs] == [
        "https://one.example/", "https://three.example/"
    ]
    assert manager.save_now()
    saved = manager.repository.load_current()
    assert saved is not None
    assert [tab.url for tab in saved.tabs] == [
        "https://one.example/", "https://three.example/"
    ]


def test_session_manager_skips_private_windows(tmp_path):
    manager = SessionManager(SessionRepository(tmp_path / "Sessions"), app)
    manager.begin_run()
    private = MainWindow(initial_url="https://secret.example/", is_private=True)
    assert private._session_manager is None


def test_startup_settings_dialog_saves_homepage_and_mode(tmp_path):
    preferences = StartupSettings(
        QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    )
    dialog = StartupSettingsDialog(preferences)
    assert dialog.restore_checkbox.isChecked() is True
    dialog.restore_checkbox.setChecked(False)
    dialog.homepage_radio.setChecked(True)
    dialog.homepage_edit.setText("lightmq.example")
    dialog._save_homepage()

    assert preferences.restore_previous_session() is False
    assert preferences.mode() is StartupMode.HOMEPAGE
    assert preferences.homepage() == "https://lightmq.example"


def test_runtime_toggle_keeps_tabs_open_and_does_not_restore_duplicates(tmp_path):
    window = MainWindow(initial_url="https://one.example/")
    window.tab_manager.create_tab("https://two.example/", activate=False)
    window._startup_settings = StartupSettings(
        QSettings(str(tmp_path / "runtime.ini"), QSettings.Format.IniFormat)
    )
    dialog = window.open_startup_settings()

    dialog.restore_checkbox.setChecked(False)
    assert window.tab_manager.count() == 2
    assert window._startup_settings.restore_previous_session() is False

    dialog.restore_checkbox.setChecked(True)
    assert window.tab_manager.count() == 2
    assert window._startup_settings.restore_previous_session() is True
