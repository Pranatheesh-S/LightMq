"""Persistent, visit-oriented browsing history backed by SQLite."""

from datetime import datetime, timezone
import logging
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit, urlunsplit

from PySide6.QtCore import QObject, QStandardPaths, Signal

logger = logging.getLogger(__name__)


class HistoryManager(QObject):
    """Store and query successful public web visits in an application database."""

    history_changed = Signal()
    _instance: "HistoryManager | None" = None

    def __init__(
        self, storage_path: Path | None = None, parent: QObject | None = None,
        recording_enabled: bool = True,
    ):
        super().__init__(parent)
        if storage_path is None:
            app_data = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
            if not app_data:
                app_data = str(Path.home() / ".lightmq")
            storage_path = Path(app_data) / "browser.sqlite3"
        self._storage_path = Path(storage_path)
        self._recording_enabled = recording_enabled
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @classmethod
    def get_instance(cls) -> "HistoryManager":
        """Return the process-wide history manager."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _connect(self) -> sqlite3.Connection:
        """Open a short-lived SQLite connection with foreign keys enabled."""
        connection = sqlite3.connect(self._storage_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        """Create or migrate the history schema."""
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS history_urls (
                    id INTEGER PRIMARY KEY,
                    url TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL DEFAULT '',
                    favicon TEXT NOT NULL DEFAULT '',
                    visit_count INTEGER NOT NULL DEFAULT 0,
                    last_visit_at TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS history_visits (
                    id INTEGER PRIMARY KEY,
                    url_id INTEGER NOT NULL REFERENCES history_urls(id) ON DELETE CASCADE,
                    visited_at TEXT NOT NULL,
                    visit_type TEXT NOT NULL DEFAULT 'link',
                    title TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_history_visits_time
                    ON history_visits(visited_at DESC, id DESC);
                CREATE INDEX IF NOT EXISTS idx_history_visits_url_time
                    ON history_visits(url_id, visited_at DESC);
                CREATE INDEX IF NOT EXISTS idx_history_urls_url ON history_urls(url);
                """
            )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(history_visits)")}
            if "title" not in columns:
                connection.execute("ALTER TABLE history_visits ADD COLUMN title TEXT NOT NULL DEFAULT ''")
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (1, datetime.now(timezone.utc).isoformat(timespec="seconds")),
            )

    @staticmethod
    def _eligible_url(url: str) -> str | None:
        """Return a safe HTTP(S) URL, rejecting internal and malformed schemes."""
        raw = url.strip()
        try:
            parts = urlsplit(raw)
            if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
                return None
            # Do not persist URL user-info; keep the requested page path/query intact.
            host = parts.hostname
            if ":" in host and not host.startswith("["):
                host = f"[{host}]"
            if parts.port:
                host = f"{host}:{parts.port}"
            return urlunsplit((parts.scheme.lower(), host, parts.path, parts.query, parts.fragment))
        except ValueError:
            return None

    def add_entry(
        self, url: str, title: str, favicon: str = "", visit_type: str = "navigation",
        visited_at: datetime | None = None,
    ) -> bool:
        """Persist one successful visit; private/internal and non-web URLs are ignored."""
        clean_url = self._eligible_url(url)
        if clean_url is None or not self._recording_enabled:
            return False
        timestamp = (visited_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(timespec="seconds")
        clean_title = title.strip() or clean_url
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO history_urls(url, title, favicon) VALUES (?, ?, ?) "
                "ON CONFLICT(url) DO UPDATE SET title=excluded.title, "
                "favicon=CASE WHEN excluded.favicon='' THEN history_urls.favicon ELSE excluded.favicon END",
                (clean_url, clean_title, favicon),
            )
            url_id = connection.execute("SELECT id FROM history_urls WHERE url=?", (clean_url,)).fetchone()[0]
            connection.execute(
                "INSERT INTO history_visits(url_id, visited_at, visit_type, title) VALUES (?, ?, ?, ?)",
                (url_id, timestamp, visit_type, clean_title),
            )
            connection.execute(
                "UPDATE history_urls SET visit_count=visit_count+1, last_visit_at=? WHERE id=?",
                (timestamp, url_id),
            )
        self.history_changed.emit()
        return True

    def update_title(self, url: str, title: str) -> None:
        """Update the displayed title for a visited URL."""
        clean_url = self._eligible_url(url)
        if not clean_url or not title.strip():
            return
        with self._connect() as connection:
            cursor = connection.execute("UPDATE history_urls SET title=? WHERE url=?", (title.strip(), clean_url))
            connection.execute(
                "UPDATE history_visits SET title=? WHERE url_id=(SELECT id FROM history_urls WHERE url=?) "
                "AND id=(SELECT MAX(id) FROM history_visits WHERE url_id=(SELECT id FROM history_urls WHERE url=?))",
                (title.strip(), clean_url, clean_url),
            )
        if cursor.rowcount:
            self.history_changed.emit()

    def get_entries(
        self, search: str = "", limit: int = 100, offset: int = 0,
        start: datetime | None = None, end: datetime | None = None,
    ) -> list[dict[str, str | int]]:
        """Return newest individual visits with optional search, date bounds, and pagination."""
        clauses: list[str] = []
        params: list[object] = []
        query = search.strip()
        if query:
            clauses.append("(u.title LIKE ? ESCAPE '\\' OR u.url LIKE ? ESCAPE '\\')")
            escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            params.extend((f"%{escaped}%", f"%{escaped}%"))
        if start:
            clauses.append("v.visited_at >= ?")
            params.append(start.astimezone(timezone.utc).isoformat(timespec="seconds"))
        if end:
            clauses.append("v.visited_at < ?")
            params.append(end.astimezone(timezone.utc).isoformat(timespec="seconds"))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT v.id, u.url, COALESCE(NULLIF(v.title,''),u.title) AS title, u.favicon, v.visited_at AS timestamp, "
                "v.visit_type, u.visit_count FROM history_visits v "
                "JOIN history_urls u ON u.id=v.url_id "
                f"{where} ORDER BY v.visited_at DESC, v.id DESC LIMIT ? OFFSET ?",
                (*params, max(1, min(limit, 500)), max(0, offset)),
            ).fetchall()
        return [dict(row) for row in rows]

    def count_entries(self, search: str = "", start: datetime | None = None, end: datetime | None = None) -> int:
        """Count visits matching filters for pagination."""
        clauses: list[str] = []
        params: list[object] = []
        if search.strip():
            clauses.append("(u.title LIKE ? OR u.url LIKE ?)")
            params.extend((f"%{search.strip()}%", f"%{search.strip()}%"))
        if start:
            clauses.append("v.visited_at >= ?")
            params.append(start.astimezone(timezone.utc).isoformat(timespec="seconds"))
        if end:
            clauses.append("v.visited_at < ?")
            params.append(end.astimezone(timezone.utc).isoformat(timespec="seconds"))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            return int(connection.execute(
                "SELECT COUNT(*) FROM history_visits v JOIN history_urls u ON u.id=v.url_id "
                f"{where}", params,
            ).fetchone()[0])

    def delete_entry(self, visit_id: int) -> bool:
        """Delete one visit and remove its URL summary when no visits remain."""
        with self._connect() as connection:
            row = connection.execute("SELECT url_id FROM history_visits WHERE id=?", (visit_id,)).fetchone()
            if row is None:
                return False
            url_id = int(row[0])
            connection.execute("DELETE FROM history_visits WHERE id=?", (visit_id,))
            connection.execute(
                "UPDATE history_urls SET visit_count=(SELECT COUNT(*) FROM history_visits WHERE url_id=?), "
                "last_visit_at=COALESCE((SELECT MAX(visited_at) FROM history_visits WHERE url_id=?), '') WHERE id=?",
                (url_id, url_id, url_id),
            )
            connection.execute("DELETE FROM history_urls WHERE id=? AND visit_count=0", (url_id,))
        self.history_changed.emit()
        return True

    def delete_url(self, url: str) -> int:
        """Delete all recorded visits for one URL."""
        clean_url = self._eligible_url(url)
        if not clean_url:
            return 0
        with self._connect() as connection:
            row = connection.execute("SELECT id FROM history_urls WHERE url=?", (clean_url,)).fetchone()
            if row is None:
                return 0
            count = connection.execute("SELECT COUNT(*) FROM history_visits WHERE url_id=?", (row[0],)).fetchone()[0]
            connection.execute("DELETE FROM history_urls WHERE id=?", (row[0],))
        self.history_changed.emit()
        return int(count)

    def clear(self, start: datetime | None = None, end: datetime | None = None) -> None:
        """Delete all history or visits within a half-open UTC time range."""
        with self._connect() as connection:
            if start is None and end is None:
                connection.execute("DELETE FROM history_visits")
                connection.execute("DELETE FROM history_urls")
            else:
                clauses, params = [], []
                if start:
                    clauses.append("visited_at >= ?")
                    params.append(start.astimezone(timezone.utc).isoformat(timespec="seconds"))
                if end:
                    clauses.append("visited_at < ?")
                    params.append(end.astimezone(timezone.utc).isoformat(timespec="seconds"))
                connection.execute(f"DELETE FROM history_visits WHERE {' AND '.join(clauses)}", params)
                connection.execute(
                    "DELETE FROM history_urls WHERE NOT EXISTS "
                    "(SELECT 1 FROM history_visits WHERE history_visits.url_id=history_urls.id)"
                )
                connection.execute(
                    "UPDATE history_urls SET visit_count=(SELECT COUNT(*) FROM history_visits "
                    "WHERE history_visits.url_id=history_urls.id), last_visit_at=(SELECT MAX(visited_at) "
                    "FROM history_visits WHERE history_visits.url_id=history_urls.id)"
                )
        self.history_changed.emit()
