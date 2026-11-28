"""Persist only explicit local recommendation feedback, never browsing history copies."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit

from browser.features.recommendations.recommendation_engine import recommendation_key


class RecommendationRepository:
    """Store pin/hide decisions in the existing browser SQLite database."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS recommendation_feedback (
                    url_key TEXT PRIMARY KEY,
                    domain TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL DEFAULT '',
                    is_hidden INTEGER NOT NULL DEFAULT 0 CHECK(is_hidden IN (0,1)),
                    is_pinned INTEGER NOT NULL DEFAULT 0 CHECK(is_pinned IN (0,1)),
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_recommendation_feedback_hidden
                    ON recommendation_feedback(is_hidden, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_recommendation_feedback_pinned
                    ON recommendation_feedback(is_pinned, updated_at DESC);
            """)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    @staticmethod
    def _domain(key: str) -> str:
        """Extract a host safely, including IPv6 and non-default ports."""
        try:
            return (urlsplit(key).hostname or "").lower()[:253]
        except ValueError:
            return ""

    def feedback(self) -> list[dict]:
        """Return bounded local feedback rows for the ranking worker."""
        with self._connect() as db:
            rows = db.execute(
                "SELECT url_key,domain,title,is_hidden,is_pinned FROM recommendation_feedback "
                "WHERE is_hidden=1 OR is_pinned=1 ORDER BY updated_at DESC LIMIT 1000"
            ).fetchall()
        return [dict(row) for row in rows]

    def set_hidden(self, url: str, hidden: bool, title: str = "") -> bool:
        """Hide or reveal a candidate using a URL key with queries removed."""
        key = recommendation_key(url)
        if not key:
            return False
        domain = self._domain(key)
        with self._connect() as db:
            db.execute(
                "INSERT INTO recommendation_feedback(url_key,domain,title,is_hidden,is_pinned,updated_at) "
                "VALUES(?,?,?, ?,0,?) ON CONFLICT(url_key) DO UPDATE SET domain=excluded.domain, "
                "title=CASE WHEN excluded.title='' THEN recommendation_feedback.title ELSE excluded.title END, "
                "is_hidden=excluded.is_hidden, updated_at=excluded.updated_at",
                (key, domain, title[:200], int(hidden), self._now()),
            )
            db.execute("DELETE FROM recommendation_feedback WHERE url_key=? AND is_hidden=0 AND is_pinned=0", (key,))
        return True

    def set_pinned(self, url: str, pinned: bool, title: str = "") -> bool:
        """Pin or unpin a candidate independently of history ranking changes."""
        key = recommendation_key(url)
        if not key:
            return False
        domain = self._domain(key)
        with self._connect() as db:
            db.execute(
                "INSERT INTO recommendation_feedback(url_key,domain,title,is_hidden,is_pinned,updated_at) "
                "VALUES(?,?,?,0,?,?) ON CONFLICT(url_key) DO UPDATE SET domain=excluded.domain, "
                "title=CASE WHEN excluded.title='' THEN recommendation_feedback.title ELSE excluded.title END, "
                "is_pinned=excluded.is_pinned, updated_at=excluded.updated_at",
                (key, domain, title[:200], int(pinned), self._now()),
            )
            db.execute("DELETE FROM recommendation_feedback WHERE url_key=? AND is_hidden=0 AND is_pinned=0", (key,))
        return True

    def hidden(self) -> list[dict[str, str]]:
        """Return user-hidden site labels for the Settings manager."""
        with self._connect() as db:
            rows = db.execute(
                "SELECT url_key,domain,title,updated_at FROM recommendation_feedback WHERE is_hidden=1 "
                "ORDER BY domain COLLATE NOCASE,url_key LIMIT 1000"
            ).fetchall()
        return [dict(row) for row in rows]

    def reveal(self, url_key: str) -> bool:
        """Remove a hidden state while preserving an explicit pin, if any."""
        with self._connect() as db:
            cursor = db.execute("UPDATE recommendation_feedback SET is_hidden=0,updated_at=? WHERE url_key=?", (self._now(), url_key))
            db.execute("DELETE FROM recommendation_feedback WHERE url_key=? AND is_hidden=0 AND is_pinned=0", (url_key,))
        return bool(cursor.rowcount)

    def clear(self, include_pins: bool = True) -> None:
        """Clear hidden/pinned feedback without touching history, cookies, or bookmarks."""
        with self._connect() as db:
            if include_pins:
                db.execute("DELETE FROM recommendation_feedback")
            else:
                db.execute("UPDATE recommendation_feedback SET is_hidden=0,updated_at=?", (self._now(),))
                db.execute("DELETE FROM recommendation_feedback WHERE is_pinned=0")
