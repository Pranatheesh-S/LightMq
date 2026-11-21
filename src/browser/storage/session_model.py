"""Validated, versioned tab metadata for session snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import parse_qsl
from uuid import uuid4

from PySide6.QtCore import QUrl, QUrlQuery

from browser.utils.constants import DEFAULT_START_URL

SCHEMA_VERSION = 1
MAX_TABS = 100
SENSITIVE_QUERY_NAMES = {
    "access_token", "auth", "authorization", "code", "id_token", "key",
    "password", "refresh_token", "secret", "session", "token",
}


@dataclass(frozen=True)
class SessionTab:
    """One restorable top-level tab's non-secret metadata."""

    tab_id: str
    url: str
    title: str
    position: int


@dataclass(frozen=True)
class SessionSnapshot:
    """Validated session snapshot with explicit schema version and ordering."""

    tabs: tuple[SessionTab, ...]
    active_tab_id: str | None
    saved_at: str
    schema_version: int = SCHEMA_VERSION

    @classmethod
    def create(
        cls,
        tabs: list[SessionTab] | tuple[SessionTab, ...],
        active_tab_id: str | None,
    ) -> "SessionSnapshot":
        """Create an ordered snapshot with a UTC timestamp."""
        ordered = tuple(
            SessionTab(tab.tab_id, tab.url, tab.title, position)
            for position, tab in enumerate(tabs[:MAX_TABS])
        )
        if active_tab_id not in {tab.tab_id for tab in ordered}:
            active_tab_id = ordered[0].tab_id if ordered else None
        return cls(ordered, active_tab_id, datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, object]:
        """Serialize only URL/title/order metadata, never cookies or form data."""
        return {
            "schema_version": self.schema_version,
            "saved_at": self.saved_at,
            "active_tab_id": self.active_tab_id,
            "tabs": [
                {
                    "id": tab.tab_id,
                    "url": tab.url,
                    "title": tab.title,
                    "position": tab.position,
                }
                for tab in self.tabs
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "SessionSnapshot":
        """Validate and sanitize untrusted JSON before it reaches WebEngine."""
        if data.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("Unsupported session schema")
        raw_tabs = data.get("tabs")
        if not isinstance(raw_tabs, list):
            raise ValueError("Session tabs must be a list")

        tabs: list[SessionTab] = []
        seen_ids: set[str] = set()
        for raw in raw_tabs[:MAX_TABS]:
            if not isinstance(raw, dict):
                continue
            raw_id = raw.get("id")
            raw_url = raw.get("url")
            if not isinstance(raw_id, str) or not raw_id.strip() or not isinstance(raw_url, str):
                continue
            tab_id = raw_id.strip()[:80]
            if tab_id in seen_ids:
                continue
            safe_url = cls.sanitize_url(raw_url)
            if safe_url is None:
                continue
            title = raw.get("title", "")
            position = raw.get("position", len(tabs))
            if not isinstance(title, str):
                title = ""
            if isinstance(position, bool) or not isinstance(position, int) or position < 0:
                position = len(tabs)
            tabs.append(SessionTab(tab_id, safe_url, title[:512], position))
            seen_ids.add(tab_id)

        tabs.sort(key=lambda tab: (tab.position, tab.tab_id))
        tabs = [SessionTab(tab.tab_id, tab.url, tab.title, i) for i, tab in enumerate(tabs)]
        ids = {tab.tab_id for tab in tabs}
        active = data.get("active_tab_id")
        if not isinstance(active, str) or active not in ids:
            active = tabs[0].tab_id if tabs else None
        saved_at = data.get("saved_at")
        if not isinstance(saved_at, str):
            saved_at = ""
        return cls(tuple(tabs), active, saved_at, SCHEMA_VERSION)

    @staticmethod
    def sanitize_url(value: str) -> str | None:
        """Allow web and LightMq new-tab URLs; reject credentials and token URLs."""
        if len(value) > 8192:
            return None
        url = QUrl(value.strip())
        if not url.isValid() or url.isEmpty():
            return None
        text = url.toString()
        if text == DEFAULT_START_URL or text == "about:blank":
            return text
        if url.scheme().lower() not in {"http", "https"} or not url.host():
            return None
        if url.userName() or url.password():
            return None
        query = QUrlQuery(url).query()
        for name, _ in parse_qsl(query, keep_blank_values=True):
            normalized_name = name.lower().replace("-", "_")
            if (
                normalized_name in SENSITIVE_QUERY_NAMES
                or any(marker in normalized_name for marker in ("token", "auth", "secret", "password"))
            ):
                return None
        if url.hasFragment():
            url.setFragment("")
        return url.toString(QUrl.ComponentFormattingOption.FullyEncoded)

    @staticmethod
    def new_tab_id() -> str:
        """Generate a stable identifier for a new in-memory tab lifetime."""
        return f"tab-{uuid4().hex}"
