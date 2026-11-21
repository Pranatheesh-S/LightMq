"""Persistent startup preferences using the existing native QSettings store."""

from enum import Enum
import re

from PySide6.QtCore import QSettings

from browser.storage.session_model import SessionSnapshot


class StartupMode(str, Enum):
    """Supported regular-browser startup behaviors."""

    NEW_TAB = "new_tab"
    HOMEPAGE = "homepage"
    CONTINUE = "continue"


class StartupSettings:
    """Read and validate the startup mode and homepage preference."""

    MODE_KEY = "startup/mode"
    HOMEPAGE_KEY = "startup/homepage"
    DEFAULT_HOMEPAGE = "https://www.google.com/"

    def __init__(self, settings: QSettings | None = None):
        self.settings = settings or QSettings("LightMq", "LightMq Browser")

    def mode(self) -> StartupMode:
        """Return the stored startup mode, defaulting to continue previous tabs."""
        try:
            return StartupMode(str(self.settings.value(self.MODE_KEY, StartupMode.CONTINUE.value)))
        except ValueError:
            return StartupMode.CONTINUE

    def homepage(self) -> str:
        """Return a validated HTTP(S) homepage or the safe default."""
        value = str(self.settings.value(self.HOMEPAGE_KEY, self.DEFAULT_HOMEPAGE)).strip()
        safe = SessionSnapshot.sanitize_url(value)
        return safe if safe and safe.startswith(("http://", "https://")) else self.DEFAULT_HOMEPAGE

    def set(self, mode: StartupMode | str, homepage: str) -> None:
        """Persist a supported startup mode and normalized HTTP(S) homepage."""
        normalized_mode = StartupMode(mode)
        cleaned = homepage.strip()
        if cleaned and not re.match(r"^[a-zA-Z][a-zA-Z\d+.-]*:", cleaned):
            cleaned = f"https://{cleaned}"
        safe_homepage = SessionSnapshot.sanitize_url(cleaned)
        if not safe_homepage or not safe_homepage.startswith(("http://", "https://")):
            raise ValueError("Homepage must be a valid HTTP or HTTPS URL")
        self.settings.setValue(self.MODE_KEY, normalized_mode.value)
        self.settings.setValue(self.HOMEPAGE_KEY, safe_homepage)
        self.settings.sync()
