"""Privacy properties of the supported Qt WebEngine off-the-record profile."""

from PySide6.QtWebEngineCore import QWebEngineProfile
from PySide6.QtWidgets import QApplication

from browser.webengine.web_profile import WebProfileManager


def test_private_profile_is_off_the_record_and_memory_only():
    app=QApplication.instance()
    profile=WebProfileManager.create_off_the_record_profile(app)
    assert profile.isOffTheRecord()
    assert profile.persistentCookiesPolicy()==QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
    assert profile.httpCacheType()==QWebEngineProfile.HttpCacheType.MemoryHttpCache
    # Qt 6.12 reports an internal OffTheRecord path even though this profile
    # cannot persist its cookies/storage; LightMq never assigns a filesystem path.
    assert profile.persistentStoragePath().endswith("OffTheRecord")
    assert not profile.cachePath()
    profile.deleteLater()
