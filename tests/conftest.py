"""Keep Qt browser windows and WebEngine child processes scoped to each test."""

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QSettings
from PySide6.QtWidgets import QApplication

from browser.webengine.scheme import register_webchannel_resource_access

register_webchannel_resource_access()


@pytest.fixture(scope="session", autouse=True)
def isolate_browser_profile(tmp_path_factory):
    """Keep all browser tests on one temporary profile, never user data."""
    from browser.webengine.web_profile import WebProfileManager

    WebProfileManager._profile = None
    profile_root = tmp_path_factory.mktemp("lightmq-profile") / "Browser" / "Profiles" / "Default"
    original_data_root = WebProfileManager.data_root
    WebProfileManager.data_root = classmethod(lambda cls: profile_root)
    yield
    WebProfileManager.data_root = original_data_root


@pytest.fixture(scope="session", autouse=True)
def isolate_application_settings(tmp_path_factory):
    """Keep GUI integration tests from reading or changing real LightMq preferences."""
    previous_format = QSettings.defaultFormat()
    settings_root = tmp_path_factory.mktemp("lightmq-settings")
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(settings_root))
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    yield
    QSettings.setDefaultFormat(previous_format)


@pytest.fixture(autouse=True)
def close_browser_windows_after_test():
    """Close test-created windows while leaving the shared profile alive."""
    yield

    app = QApplication.instance()
    try:
        from browser.ui.main_window import MainWindow

        for window in list(MainWindow._all_windows):
            window.close()
            window.deleteLater()
    except ImportError:
        return

    if app is not None:
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()


@pytest.fixture(autouse=True)
def isolate_bookmark_store(tmp_path):
    """Keep singleton bookmark mutations out of the user's browser database."""
    from browser.features.bookmarks.bookmark_manager import BookmarkManager

    previous = BookmarkManager._instance
    BookmarkManager._instance = BookmarkManager(tmp_path / "bookmarks.sqlite3")
    yield
    BookmarkManager._instance = previous


@pytest.fixture(autouse=True)
def isolate_history_store(tmp_path):
    """Keep history and recommendation tests out of the user's browser database."""
    from browser.features.history.history_manager import HistoryManager

    previous = HistoryManager._instance
    HistoryManager._instance = HistoryManager(tmp_path / "history.sqlite3")
    yield
    HistoryManager._instance = previous

