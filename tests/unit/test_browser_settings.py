"""Persistent browser preference validation and search URL generation."""

from PySide6.QtCore import QSettings

from browser.storage.settings import BrowserSettings


def test_search_engines_encode_queries_and_keep_custom_templates_safe(tmp_path):
    prefs = BrowserSettings(QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat))
    prefs.set("search/default_provider", "Bing")
    assert "bing.com/search?q=red+fox" in prefs.search_url("red fox")
    prefs.set("search/default_provider", "Custom")
    prefs.set("search/custom_template", "https://search.example/?q={searchTerms}")
    assert prefs.search_url("a&b") == "https://search.example/?q=a%26b"
    prefs.set("search/custom_template", "javascript:{searchTerms}")
    assert prefs.search_url("term").startswith("https://www.google.com/")


def test_theme_accent_and_zoom_values_validate_and_persist(tmp_path):
    store = QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat)
    prefs = BrowserSettings(store)
    prefs.set("appearance/theme", "dark")
    prefs.set("appearance/accent_color", "purple")
    prefs.set("web/default_zoom", 125)
    restored = BrowserSettings(store)
    assert restored.theme() == "dark"
    assert restored.accent() == "purple"
    assert restored.default_zoom() == 1.25
    store.setValue("web/default_zoom", 999)
    assert restored.default_zoom() == 1.0
