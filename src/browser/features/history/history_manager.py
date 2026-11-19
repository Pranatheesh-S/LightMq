"""History manager subsystem for LightMq Browser.

Tracks visited URLs and page titles with timestamp logging and query capabilities.
"""

from datetime import datetime
import json
import logging
from pathlib import Path
from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


class HistoryManager(QObject):
    """Manages browsing history with JSON persistence and query support."""

    history_changed = Signal()
    _instance: "HistoryManager | None" = None

    def __init__(self, storage_path: Path | None = None, parent: QObject | None = None):
        super().__init__(parent)
        if storage_path is None:
            self._storage_path = Path.home() / ".lightmq" / "history.json"
        else:
            self._storage_path = storage_path

        self._entries: list[dict[str, str]] = []
        self._load()

    @classmethod
    def get_instance(cls) -> "HistoryManager":
        """Return shared singleton instance of HistoryManager."""
        if cls._instance is None:
            cls._instance = HistoryManager()
        return cls._instance

    def _load(self) -> None:
        """Load history entries from disk if file exists."""
        if self._storage_path.exists():
            try:
                with open(self._storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self._entries = data
            except Exception as e:
                logger.warning("Failed to load history from %s: %s", self._storage_path, e)
                self._entries = []

    def _save(self) -> None:
        """Persist history entries to disk."""
        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._storage_path, "w", encoding="utf-8") as f:
                json.dump(self._entries, f, indent=2)
        except Exception as e:
            logger.warning("Failed to save history to %s: %s", self._storage_path, e)

    def add_entry(self, url: str, title: str) -> bool:
        """Add a browsing history entry.

        Args:
            url: Visited page URL.
            title: Page title string.

        Returns:
            bool: True if entry was added, False if ignored (e.g. empty or about:blank).
        """
        clean_url = url.strip()
        if not clean_url or clean_url == "about:blank":
            return False

        entry = {
            "url": clean_url,
            "title": title.strip() or clean_url,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._entries.insert(0, entry)
        # Cap in-memory history at 1000 items
        if len(self._entries) > 1000:
            self._entries = self._entries[:1000]

        self._save()
        self.history_changed.emit()
        return True

    def get_entries(self, search: str = "") -> list[dict[str, str]]:
        """Return history entries, optionally filtered by keyword."""
        if not search:
            return list(self._entries)
        query = search.lower()
        return [
            e for e in self._entries
            if query in e["title"].lower() or query in e["url"].lower()
        ]

    def clear(self) -> None:
        """Clear all browsing history."""
        self._entries.clear()
        self._save()
        self.history_changed.emit()
        logger.info("Cleared browsing history.")
