"""Validated, versioned tab metadata for session snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import zipfile
from urllib.parse import parse_qsl
from uuid import uuid4

from PySide6.QtCore import QUrl, QUrlQuery

from browser.utils.constants import DEFAULT_START_URL

SCHEMA_VERSION = 2
MAX_TABS = 100
SENSITIVE_QUERY_NAMES = {
    "access_token", "auth", "authorization", "code", "id_token", "key",
    "password", "refresh_token", "secret", "session", "token",
}


def _group_position(entry: dict[str, object]) -> int:
    value = entry.get("position", 0)
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


@dataclass(frozen=True)
class SessionTab:
    """One restorable top-level tab's non-secret metadata."""

    tab_id: str
    url: str
    title: str
    position: int
    pinned: bool = False
    group_id: str | None = None


@dataclass(frozen=True)
class SessionGroup:
    """Restorable presentation state for one tab group."""

    group_id: str
    name: str
    color: str
    collapsed: bool
    position: int


@dataclass(frozen=True)
class SessionSnapshot:
    """Validated session snapshot with explicit schema version and ordering."""

    tabs: tuple[SessionTab, ...]
    active_tab_id: str | None
    saved_at: str
    schema_version: int = SCHEMA_VERSION
    groups: tuple[SessionGroup, ...] = ()

    @classmethod
    def create(
        cls,
        tabs: list[SessionTab] | tuple[SessionTab, ...],
        active_tab_id: str | None,
        groups: list[SessionGroup] | tuple[SessionGroup, ...] = (),
    ) -> "SessionSnapshot":
        """Create an ordered snapshot with a UTC timestamp."""
        ordered = tuple(
            SessionTab(tab.tab_id, tab.url, tab.title, position, tab.pinned, tab.group_id)
            for position, tab in enumerate(tabs[:MAX_TABS])
        )
        valid_ids = {tab.tab_id for tab in ordered if not tab.pinned}
        referenced_groups = {tab.group_id for tab in ordered if tab.group_id and not tab.pinned}
        valid_groups = tuple(group for group in groups[:MAX_TABS] if group.group_id in referenced_groups)
        memberships = {group.group_id for group in valid_groups}
        ordered = tuple(
            SessionTab(tab.tab_id, tab.url, tab.title, tab.position, tab.pinned,
                       tab.group_id if tab.group_id in memberships and tab.tab_id in valid_ids else None)
            for tab in ordered
        )
        if active_tab_id not in {tab.tab_id for tab in ordered}:
            active_tab_id = ordered[0].tab_id if ordered else None
        return cls(ordered, active_tab_id, datetime.now(timezone.utc).isoformat(), SCHEMA_VERSION, valid_groups)

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
                    "pinned": tab.pinned,
                    "group_id": tab.group_id,
                }
                for tab in self.tabs
            ],
            "groups": [
                {"id": group.group_id, "name": group.name, "color": group.color,
                 "collapsed": group.collapsed, "position": group.position}
                for group in self.groups
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "SessionSnapshot":
        """Validate and sanitize untrusted JSON before it reaches WebEngine."""
        version = data.get("schema_version")
        if version not in {1, SCHEMA_VERSION}:
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
            pinned = raw.get("pinned", False) if version >= 2 else False
            if not isinstance(pinned, bool):
                pinned = False
            group_id = raw.get("group_id") if version >= 2 else None
            if not isinstance(group_id, str) or not group_id:
                group_id = None
            tabs.append(SessionTab(tab_id, safe_url, title[:512], position, pinned, group_id))
            seen_ids.add(tab_id)

        tabs.sort(key=lambda tab: (tab.position, tab.tab_id))
        raw_groups = data.get("groups", []) if version >= 2 else []
        groups: list[SessionGroup] = []
        seen_groups: set[str] = set()
        if isinstance(raw_groups, list):
            for raw in sorted((item for item in raw_groups if isinstance(item, dict)), key=_group_position):
                group_id, name, color = raw.get("id"), raw.get("name"), raw.get("color")
                if not all(isinstance(item, str) and item for item in (group_id, name, color)) or group_id in seen_groups:
                    continue
                groups.append(SessionGroup(group_id[:80], " ".join(name.split())[:40] or "Group",
                                           color.lower() if color.lower() in {"grey", "blue", "red", "yellow", "green", "purple", "pink", "cyan"} else "blue",
                                           bool(raw.get("collapsed", False)), len(groups)))
                seen_groups.add(group_id)
        group_ids = {group.group_id for group in groups}
        clean_tabs = []
        for i, tab in enumerate(tabs):
            group_id = tab.group_id if tab.group_id in group_ids and not tab.pinned else None
            clean_tabs.append(SessionTab(tab.tab_id, tab.url, tab.title, i, tab.pinned, group_id))
        tabs = clean_tabs
        referenced_groups = {tab.group_id for tab in tabs if tab.group_id}
        groups = [group for group in groups if group.group_id in referenced_groups]
        ids = {tab.tab_id for tab in tabs}
        active = data.get("active_tab_id")
        if not isinstance(active, str) or active not in ids:
            active = tabs[0].tab_id if tabs else None
        saved_at = data.get("saved_at")
        if not isinstance(saved_at, str):
            saved_at = ""
        return cls(tuple(tabs), active, saved_at, SCHEMA_VERSION, tuple(groups))

    @staticmethod
    def sanitize_url(value: str) -> str | None:
        """Allow web/start-page URLs and existing local PDFs; reject unsafe URLs."""
        if len(value) > 8192:
            return None
        url = QUrl(value.strip())
        if not url.isValid() or url.isEmpty():
            return None
        text = url.toString()
        if text == DEFAULT_START_URL or text == "about:blank":
            return text
        if url.scheme().lower() == "file":
            if url.host() not in ("", "localhost") or url.hasQuery() or url.hasFragment():
                return None
            local_path = Path(url.toLocalFile())
            try:
                suffix = local_path.suffix.lower()
                if not local_path.is_file() or suffix not in {".pdf", ".xlsx"}:
                    return None
                if suffix == ".pdf":
                    with local_path.open("rb") as document:
                        if b"%PDF-" not in document.read(1024):
                            return None
                elif not zipfile.is_zipfile(local_path):
                    return None
            except OSError:
                return None
            return QUrl.fromLocalFile(str(local_path.resolve())).toString(
                QUrl.ComponentFormattingOption.FullyEncoded
            )
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
