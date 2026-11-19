"""Bookmark manager subsystem for LightMq Browser.

Manages collection, persistence, and querying of user bookmarks.
"""

from collections.abc import Callable
import json
import logging
from pathlib import Path
from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


class BookmarkManager(QObject):
    """Manages browser bookmarks with JSON persistence and change signals."""

    bookmarks_changed = Signal()
    _instance: "BookmarkManager | None" = None

    def __init__(self, storage_path: Path | None = None, parent: QObject | None = None):
        super().__init__(parent)
        if storage_path is None:
            self._storage_path = Path.home() / ".lightmq" / "bookmarks.json"
        else:
            self._storage_path = storage_path

        self._bookmarks: list[dict[str, str]] = []
        self._load()

    @classmethod
    def get_instance(cls) -> "BookmarkManager":
        """Return the shared singleton instance of BookmarkManager."""
        if cls._instance is None:
            cls._instance = BookmarkManager()
        return cls._instance

    def _load(self) -> None:
        """Load bookmarks from disk if file exists."""
        if self._storage_path.exists():
            try:
                with open(self._storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self._bookmarks = data
            except Exception as e:
                logger.warning("Failed to load bookmarks from %s: %s", self._storage_path, e)
                self._bookmarks = []

    def _save(self) -> None:
        """Persist bookmarks to disk."""
        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._storage_path, "w", encoding="utf-8") as f:
                json.dump(self._bookmarks, f, indent=2)
        except Exception as e:
            logger.warning("Failed to save bookmarks to %s: %s", self._storage_path, e)

    def add_bookmark(self, title: str, url: str) -> bool:
        """Add a bookmark if it does not already exist.

        Args:
            title: Bookmark display title.
            url: Bookmark destination URL string.

        Returns:
            bool: True if added, False if already present or invalid.
        """
        clean_url = url.strip()
        if not clean_url or clean_url == "about:blank":
            return False

        if any(b["url"] == clean_url for b in self._bookmarks):
            return False

        entry = {
            "title": title.strip() or clean_url,
            "url": clean_url,
        }
        self._bookmarks.append(entry)
        self._save()
        self.bookmarks_changed.emit()
        logger.info("Added bookmark: %s (%s)", entry["title"], entry["url"])
        return True

    def remove_bookmark(self, url: str) -> bool:
        """Remove a bookmark matching the given URL.

        Args:
            url: Target URL string.

        Returns:
            bool: True if removed, False if not found.
        """
        initial_len = len(self._bookmarks)
        self._bookmarks = [b for b in self._bookmarks if b["url"] != url.strip()]
        if len(self._bookmarks) < initial_len:
            self._save()
            self.bookmarks_changed.emit()
            logger.info("Removed bookmark: %s", url)
            return True
        return False

    def is_bookmarked(self, url: str) -> bool:
        """Check whether a URL is bookmarked."""
        clean_url = url.strip()
        return any(b["url"] == clean_url for b in self._bookmarks)

    def get_bookmarks(self) -> list[dict[str, str]]:
        """Return a copy of all current bookmarks."""
        return list(self._bookmarks)

    def clear(self) -> None:
        """Clear all bookmarks."""
        self._bookmarks.clear()
        self._save()
        self.bookmarks_changed.emit()
