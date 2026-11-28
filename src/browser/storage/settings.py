"""Persistent startup preferences using the existing native QSettings store."""

from enum import Enum
import re

from PySide6.QtCore import QSettings
from PySide6.QtCore import QObject, Signal

from browser.storage.session_model import SessionSnapshot


class StartupMode(str, Enum):
    """Startup behavior and non-restoring fallback choices."""

    NEW_TAB = "new_tab"
    HOMEPAGE = "homepage"
    CONTINUE = "continue"


class StartupSettings:
    """Read, migrate, validate, and persist startup preferences."""

    MODE_KEY = "startup/mode"
    RESTORE_KEY = "startup/restore_previous_session"
    HOMEPAGE_KEY = "startup/homepage"
    DEFAULT_HOMEPAGE = "https://www.google.com/"

    def __init__(self, settings: QSettings | None = None):
        self.settings = settings or QSettings("LightMq", "LightMq Browser")

    def restore_previous_session(self) -> bool:
        """Return the persisted toggle, migrating the prior startup-mode setting."""
        if self.settings.contains(self.RESTORE_KEY):
            value = self.settings.value(self.RESTORE_KEY)
            if isinstance(value, bool):
                return value
            if isinstance(value, int) and value in (0, 1):
                return bool(value)
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in {"true", "1", "yes", "on"}:
                    return True
                if normalized in {"false", "0", "no", "off"}:
                    return False
            self.settings.setValue(self.RESTORE_KEY, True)
            self.settings.sync()
            return True

        legacy_mode = self._legacy_mode()
        restore = legacy_mode in (None, StartupMode.CONTINUE)
        fallback = (
            legacy_mode
            if legacy_mode in (StartupMode.NEW_TAB, StartupMode.HOMEPAGE)
            else StartupMode.NEW_TAB
        )
        self.settings.setValue(self.MODE_KEY, fallback.value)
        self.settings.setValue(self.RESTORE_KEY, restore)
        self.settings.sync()
        return restore

    def mode(self) -> StartupMode:
        """Return the effective startup mode for compatibility with existing callers."""
        if self.restore_previous_session():
            return StartupMode.CONTINUE
        return self.fallback_mode()

    def fallback_mode(self) -> StartupMode:
        """Return the stored Homepage or New Tab choice used when restore is off."""
        mode = self._legacy_mode()
        return mode if mode in (StartupMode.NEW_TAB, StartupMode.HOMEPAGE) else StartupMode.NEW_TAB

    def homepage(self) -> str:
        """Return a validated HTTP(S) homepage or the safe default."""
        value = str(self.settings.value(self.HOMEPAGE_KEY, self.DEFAULT_HOMEPAGE)).strip()
        safe = SessionSnapshot.sanitize_url(value)
        return safe if safe and safe.startswith(("http://", "https://")) else self.DEFAULT_HOMEPAGE

    def set_restore_previous_session(self, enabled: bool) -> None:
        """Persist only the restoration toggle, preserving all fallback preferences."""
        self.settings.setValue(self.RESTORE_KEY, bool(enabled))
        self.settings.sync()

    def set_fallback_mode(self, mode: StartupMode | str) -> None:
        """Persist a New Tab or Homepage fallback without changing the restore toggle."""
        normalized_mode = StartupMode(mode)
        if normalized_mode is StartupMode.CONTINUE:
            raise ValueError("Fallback startup mode must be New Tab or Homepage")
        self.settings.setValue(self.MODE_KEY, normalized_mode.value)
        self.settings.sync()

    def set_homepage(self, homepage: str) -> None:
        """Persist a normalized HTTP(S) homepage."""
        cleaned = homepage.strip()
        if cleaned and not re.match(r"^[a-zA-Z][a-zA-Z\d+.-]*:", cleaned):
            cleaned = f"https://{cleaned}"
        safe_homepage = SessionSnapshot.sanitize_url(cleaned)
        if not safe_homepage or not safe_homepage.startswith(("http://", "https://")):
            raise ValueError("Homepage must be a valid HTTP or HTTPS URL")
        self.settings.setValue(self.HOMEPAGE_KEY, safe_homepage)
        self.settings.sync()

    def set(self, mode: StartupMode | str, homepage: str) -> None:
        """Compatibility helper for callers using the earlier three-mode API."""
        normalized_mode = StartupMode(mode)
        self.set_homepage(homepage)
        if normalized_mode is StartupMode.CONTINUE:
            self.set_restore_previous_session(True)
        else:
            self.set_fallback_mode(normalized_mode)
            self.set_restore_previous_session(False)

    def _legacy_mode(self) -> StartupMode | None:
        """Read the former mode key defensively for migration and fallback behavior."""
        value = self.settings.value(self.MODE_KEY, None)
        if value is None:
            return None
        try:
            return StartupMode(str(value))
        except ValueError:
            return None


class BrowserSettings(QObject):
    """Typed shared preference access backed by the existing QSettings store."""

    changed = Signal(str, object)
    THEMES = ("light", "dark", "system", "custom")
    ACCENTS = {"blue": "#1A73E8", "green": "#188038", "purple": "#9334E6", "red": "#D93025", "orange": "#E8710A", "cyan": "#007B83", "grey": "#80868B"}
    ZOOMS = (50, 67, 75, 80, 90, 100, 110, 125, 150, 175, 200)

    def __init__(self, settings: QSettings | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self.store = settings or QSettings("LightMq", "LightMq Browser")

    def get(self, key: str, default: object = None) -> object:
        return self.store.value(key, default)

    def set(self, key: str, value: object) -> None:
        self.store.setValue(key, value)
        self.store.sync()
        self.changed.emit(key, value)

    def theme(self) -> str:
        value = str(self.get("appearance/theme", "system")).lower()
        return value if value in self.THEMES else "system"

    def custom_theme_color(self) -> str:
        """Return the validated user-selected base color for Custom mode."""
        from PySide6.QtGui import QColor
        value=str(self.get("appearance/custom_base_color", self.ACCENTS[self.accent()]))
        return value if QColor(value).isValid() else self.ACCENTS["blue"]

    def custom_theme_brightness(self) -> str:
        """Return the saved custom palette surface mode."""
        value=str(self.get("appearance/custom_brightness", "dark")).lower()
        return value if value in {"light","dark"} else "dark"

    def accent(self) -> str:
        value = str(self.get("appearance/accent_color", "blue")).lower()
        return value if value in self.ACCENTS else "blue"

    def default_zoom(self) -> float:
        try:
            value = int(self.get("web/default_zoom", 100))
        except (TypeError, ValueError):
            value = 100
        return (value if value in self.ZOOMS else 100) / 100

    def pdf_open_in_browser(self) -> bool:
        """Return whether PDF navigations should use Qt's internal PDF viewer."""
        value = self.get("pdf/open_in_browser", True)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"0", "false", "no", "off"}:
                return False
            if normalized in {"1", "true", "yes", "on"}:
                return True
            return True
        return bool(value)

    def search_provider(self) -> str:
        value = str(self.get("search/default_provider", "Google"))
        return value if value in {"Google", "Bing", "DuckDuckGo", "Brave Search", "Custom"} else "Google"

    def search_url(self, query: str) -> str:
        from urllib.parse import quote_plus
        templates = {"Google": "https://www.google.com/search?q={searchTerms}", "Bing": "https://www.bing.com/search?q={searchTerms}", "DuckDuckGo": "https://duckduckgo.com/?q={searchTerms}", "Brave Search": "https://search.brave.com/search?q={searchTerms}"}
        provider = self.search_provider()
        template = self.search_template()
        return template.replace("{searchTerms}", quote_plus(query))

    def search_template(self) -> str:
        """Return the validated search URL template for the current provider."""
        templates = {"Google": "https://www.google.com/search?q={searchTerms}", "Bing": "https://www.bing.com/search?q={searchTerms}", "DuckDuckGo": "https://duckduckgo.com/?q={searchTerms}", "Brave Search": "https://search.brave.com/search?q={searchTerms}"}
        provider=self.search_provider()
        template = str(self.get("search/custom_template", "https://www.google.com/search?q={searchTerms}")) if provider == "Custom" else templates[provider]
        if not self.valid_custom_template(template):
            template = templates["Google"]
        return template

    @staticmethod
    def valid_custom_template(template: str) -> bool:
        """Validate an HTTP(S) search URL with one explicit query placeholder."""
        from PySide6.QtCore import QUrl
        if template.count("{searchTerms}") != 1:
            return False
        candidate = QUrl(template.replace("{searchTerms}", "lightmq_query"))
        return candidate.isValid() and candidate.scheme().lower() in {"http", "https"} and bool(candidate.host())
