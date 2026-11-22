"""SQLite-backed bookmark hierarchy and compatibility facade."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit, urlunsplit

from PySide6.QtCore import QObject, QStandardPaths, Signal

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BookmarkItem:
    """A persisted bookmark or folder in the hierarchical collection."""

    id: int
    title: str
    url: str | None
    parent_id: int | None
    position: int
    created_at: str
    updated_at: str
    item_type: str = "bookmark"
    favicon: str = ""

    @property
    def is_folder(self) -> bool:
        return self.item_type == "folder"


class BookmarkManager(QObject):
    """Own bookmark persistence in the same SQLite file used by browsing history."""

    bookmarks_changed = Signal()
    _instance: "BookmarkManager | None" = None
    BAR_ROOT_ID = 1
    OTHER_ROOT_ID = 2

    def __init__(self, storage_path: Path | None = None, parent: QObject | None = None):
        super().__init__(parent)
        if storage_path is None:
            app_data = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
            storage_path = Path(app_data or (Path.home() / ".lightmq")) / "browser.sqlite3"
            self._legacy_path = Path.home() / ".lightmq" / "bookmarks.json"
        else:
            self._legacy_path = None
        self._storage_path = Path(storage_path)
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()
        self._migrate_legacy_json()

    @classmethod
    def get_instance(cls) -> "BookmarkManager":
        """Return the shared application bookmark manager."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._storage_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS bookmark_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_id INTEGER REFERENCES bookmark_items(id) ON DELETE CASCADE,
                    item_type TEXT NOT NULL CHECK(item_type IN ('bookmark','folder')),
                    title TEXT NOT NULL,
                    url TEXT,
                    position INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    favicon TEXT NOT NULL DEFAULT '',
                    is_system_root INTEGER NOT NULL DEFAULT 0,
                    CHECK((item_type='bookmark' AND url IS NOT NULL) OR (item_type='folder' AND url IS NULL))
                );
                CREATE INDEX IF NOT EXISTS idx_bookmark_parent_order ON bookmark_items(parent_id, position, id);
                CREATE INDEX IF NOT EXISTS idx_bookmark_url ON bookmark_items(url);
                CREATE TABLE IF NOT EXISTS bookmark_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
            """)
            columns = {row[1] for row in db.execute("PRAGMA table_info(bookmark_items)")}
            if "favicon" not in columns:
                db.execute("ALTER TABLE bookmark_items ADD COLUMN favicon TEXT NOT NULL DEFAULT ''")
            now = self._now()
            for rid, name in ((self.BAR_ROOT_ID, "Bookmarks Bar"), (self.OTHER_ROOT_ID, "Other Bookmarks")):
                db.execute("INSERT OR IGNORE INTO bookmark_items(id,parent_id,item_type,title,url,position,created_at,updated_at,is_system_root) VALUES (?,NULL,'folder',?,NULL,?,?,?,1)", (rid, name, rid, now, now))

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    @staticmethod
    def normalize_url(url: str) -> str | None:
        raw = url.strip()
        try:
            parts = urlsplit(raw)
            if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
                return None
            if parts.username is not None or parts.password is not None:
                return None
            port=parts.port
            host=parts.hostname.lower()
            if ":" in host and not host.startswith("["):host=f"[{host}]"
            if port and not ((parts.scheme.lower()=="http" and port==80) or (parts.scheme.lower()=="https" and port==443)):
                host=f"{host}:{port}"
            return urlunsplit((parts.scheme.lower(),host,parts.path,parts.query,parts.fragment))
        except ValueError:
            return None

    def _migrate_legacy_json(self) -> None:
        path = self._legacy_path
        if path is None or not path.is_file():
            return
        with self._connect() as db:
            if db.execute("SELECT 1 FROM bookmark_migrations WHERE version=2").fetchone():
                return
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    now = self._now()
                    for row in data:
                        if not isinstance(row, dict):
                            continue
                        url = self.normalize_url(str(row.get("url", "")))
                        if url and not db.execute("SELECT 1 FROM bookmark_items WHERE url=?", (url,)).fetchone():
                            self._insert(db, str(row.get("title") or url), url, self.BAR_ROOT_ID)
                db.execute("INSERT OR IGNORE INTO bookmark_migrations(version,applied_at) VALUES(1,?)", (now,))
                db.execute("INSERT OR IGNORE INTO bookmark_migrations(version,applied_at) VALUES(2,?)", (now,))
            except (OSError, ValueError, sqlite3.Error) as exc:
                logger.warning("Could not migrate legacy bookmarks %s: %s", path, exc)

    @staticmethod
    def _insert(db: sqlite3.Connection, title: str, url: str | None, parent_id: int, item_type: str = "bookmark") -> int:
        now = BookmarkManager._now()
        pos = db.execute("SELECT COALESCE(MAX(position)+1,0) FROM bookmark_items WHERE parent_id=?", (parent_id,)).fetchone()[0]
        cursor = db.execute("INSERT INTO bookmark_items(parent_id,item_type,title,url,position,created_at,updated_at) VALUES(?,?,?,?,?,?,?)", (parent_id,item_type,title.strip() or (url or "New Folder"),url,pos,now,now))
        return int(cursor.lastrowid)

    def roots(self) -> list[BookmarkItem]:
        return [item for item in (self.get_item(self.BAR_ROOT_ID), self.get_item(self.OTHER_ROOT_ID)) if item]

    def get_item(self, item_id: int) -> BookmarkItem | None:
        with self._connect() as db:
            row = db.execute("SELECT id,title,url,parent_id,position,created_at,updated_at,item_type FROM bookmark_items WHERE id=?", (item_id,)).fetchone()
        return BookmarkItem(**dict(row)) if row else None

    def children(self, parent_id: int) -> list[BookmarkItem]:
        with self._connect() as db:
            rows = db.execute("SELECT id,title,url,parent_id,position,created_at,updated_at,item_type FROM bookmark_items WHERE parent_id=? ORDER BY position,id", (parent_id,)).fetchall()
        return [BookmarkItem(**dict(row)) for row in rows]

    def all_items(self) -> list[BookmarkItem]:
        """Load a stable ordered snapshot of the bookmark tree in one database query."""
        with self._connect() as db:
            rows=db.execute("SELECT id,title,url,parent_id,position,created_at,updated_at,item_type FROM bookmark_items ORDER BY parent_id,position,id").fetchall()
        return [BookmarkItem(**dict(row)) for row in rows]

    def set_favicon(self,item_id:int,reference:str)->None:
        """Persist a favicon URL reference without downloading image data."""
        with self._connect() as db:
            db.execute("UPDATE bookmark_items SET favicon=?,updated_at=? WHERE id=? AND item_type='bookmark'",(reference.strip(),self._now(),item_id))
        self.bookmarks_changed.emit()

    def folders(self, include_roots: bool = True) -> list[BookmarkItem]:
        with self._connect() as db:
            rows = db.execute("SELECT id,title,url,parent_id,position,created_at,updated_at,item_type FROM bookmark_items WHERE item_type='folder' ORDER BY id").fetchall()
        result = [BookmarkItem(**dict(row)) for row in rows]
        return result if include_roots else [item for item in result if item.id not in (self.BAR_ROOT_ID,self.OTHER_ROOT_ID)]

    def create_folder(self, title: str, parent_id: int = BAR_ROOT_ID) -> int:
        if not title.strip():
            raise ValueError("Folder name cannot be empty")
        with self._connect() as db:
            parent = db.execute("SELECT item_type FROM bookmark_items WHERE id=?", (parent_id,)).fetchone()
            if not parent or parent[0] != "folder":
                raise ValueError("Destination folder does not exist")
            item_id = self._insert(db, title.strip(), None, parent_id, "folder")
        self.bookmarks_changed.emit(); return item_id

    def create_bookmark(self, title: str, url: str, parent_id: int = BAR_ROOT_ID, allow_duplicate: bool = False) -> int:
        clean = self.normalize_url(url)
        if not clean:
            raise ValueError("Only valid HTTP and HTTPS URLs can be bookmarked")
        if not title.strip():
            title = clean
        with self._connect() as db:
            parent = db.execute("SELECT item_type FROM bookmark_items WHERE id=?", (parent_id,)).fetchone()
            if not parent or parent[0] != "folder":
                raise ValueError("Destination folder does not exist")
            existing = db.execute("SELECT id FROM bookmark_items WHERE item_type='bookmark' AND url=? ORDER BY id LIMIT 1", (clean,)).fetchone()
            if existing and not allow_duplicate:
                raise ValueError("This URL is already bookmarked")
            item_id = self._insert(db, title.strip(), clean, parent_id)
        self.bookmarks_changed.emit(); return item_id

    def update_item(self, item_id: int, title: str, url: str | None = None, parent_id: int | None = None) -> None:
        if not title.strip():
            raise ValueError("Title cannot be empty")
        with self._connect() as db:
            row = db.execute("SELECT item_type,is_system_root,parent_id FROM bookmark_items WHERE id=?", (item_id,)).fetchone()
            if not row: raise ValueError("Bookmark no longer exists")
            if row["is_system_root"]: raise ValueError("System folders cannot be renamed")
            clean = self.normalize_url(url) if row["item_type"] == "bookmark" and url is not None else None
            if row["item_type"] == "bookmark" and not clean: raise ValueError("Only HTTP and HTTPS URLs are supported")
            if clean and db.execute("SELECT 1 FROM bookmark_items WHERE item_type='bookmark' AND url=? AND id<>?",(clean,item_id)).fetchone():
                raise ValueError("This URL is already bookmarked")
            old_parent = row["parent_id"]
            if parent_id is not None and parent_id != old_parent:
                self._validate_move(db, item_id, parent_id)
            db.execute("UPDATE bookmark_items SET title=?,url=CASE WHEN item_type='bookmark' THEN ? ELSE NULL END,parent_id=COALESCE(?,parent_id),updated_at=? WHERE id=?", (title.strip(),clean,parent_id,self._now(),item_id))
            if parent_id is not None and parent_id != old_parent:
                next_position=db.execute("SELECT COALESCE(MAX(position)+1,0) FROM bookmark_items WHERE parent_id=? AND id<>?",(parent_id,item_id)).fetchone()[0]
                db.execute("UPDATE bookmark_items SET position=? WHERE id=?",(next_position,item_id))
                if old_parent is not None:self._normalize_positions(db,old_parent)
                self._normalize_positions(db,parent_id)
        self.bookmarks_changed.emit()

    def delete_item(self, item_id: int) -> bool:
        with self._connect() as db:
            row = db.execute("SELECT parent_id,is_system_root FROM bookmark_items WHERE id=?", (item_id,)).fetchone()
            if not row or row["is_system_root"]: return False
            parent_id = row["parent_id"]
            db.execute("DELETE FROM bookmark_items WHERE id=?", (item_id,))
            if parent_id is not None: self._normalize_positions(db, parent_id)
        self.bookmarks_changed.emit(); return True

    def move_item(self, item_id: int, parent_id: int, position: int | None = None) -> None:
        with self._connect() as db:
            self._validate_move(db, item_id, parent_id)
            old = db.execute("SELECT parent_id FROM bookmark_items WHERE id=?", (item_id,)).fetchone()[0]
            siblings = db.execute("SELECT id FROM bookmark_items WHERE parent_id=? AND id<>? ORDER BY position,id", (parent_id,item_id)).fetchall()
            ordered = [int(row[0]) for row in siblings]
            target = len(ordered) if position is None else max(0,min(position,len(ordered)))
            ordered.insert(target,item_id)
            db.execute("UPDATE bookmark_items SET parent_id=?,updated_at=? WHERE id=?", (parent_id,self._now(),item_id))
            self._set_order(db,parent_id,ordered)
            if old is not None and old != parent_id: self._normalize_positions(db,old)
        self.bookmarks_changed.emit()

    def reorder(self, parent_id: int, item_ids: list[int]) -> None:
        with self._connect() as db:
            actual = {int(row[0]) for row in db.execute("SELECT id FROM bookmark_items WHERE parent_id=?", (parent_id,))}
            if len(item_ids) != len(actual) or set(item_ids) != actual:
                raise ValueError("Reorder must include each child exactly once")
            self._set_order(db,parent_id,item_ids)
        self.bookmarks_changed.emit()

    @staticmethod
    def _set_order(db: sqlite3.Connection, parent_id: int, ids: list[int]) -> None:
        now=BookmarkManager._now()
        for pos, item_id in enumerate(ids): db.execute("UPDATE bookmark_items SET position=?,updated_at=? WHERE id=? AND parent_id=?",(pos,now,item_id,parent_id))

    @staticmethod
    def _normalize_positions(db: sqlite3.Connection, parent_id: int) -> None:
        ids=[int(row[0]) for row in db.execute("SELECT id FROM bookmark_items WHERE parent_id=? ORDER BY position,id",(parent_id,))]
        BookmarkManager._set_order(db,parent_id,ids)

    @staticmethod
    def _validate_move(db: sqlite3.Connection, item_id: int, parent_id: int) -> None:
        item=db.execute("SELECT item_type,is_system_root FROM bookmark_items WHERE id=?",(item_id,)).fetchone()
        parent=db.execute("SELECT item_type FROM bookmark_items WHERE id=?",(parent_id,)).fetchone()
        if not item or not parent or parent[0] != "folder" or item["is_system_root"]: raise ValueError("Invalid folder move")
        if item["item_type"] == "folder":
            node=parent_id
            while node is not None:
                if node == item_id: raise ValueError("A folder cannot be moved into itself or a descendant")
                row=db.execute("SELECT parent_id FROM bookmark_items WHERE id=?",(node,)).fetchone()
                node=row[0] if row else None

    def find_by_url(self, url: str) -> BookmarkItem | None:
        clean=self.normalize_url(url)
        if not clean:return None
        with self._connect() as db:
            row=db.execute("SELECT id,title,url,parent_id,position,created_at,updated_at,item_type FROM bookmark_items WHERE item_type='bookmark' AND url=? ORDER BY id LIMIT 1",(clean,)).fetchone()
        return BookmarkItem(**dict(row)) if row else None

    def is_bookmarked(self, url: str) -> bool:
        return self.find_by_url(url) is not None

    def search(self, text: str = "", limit: int = 2000) -> list[BookmarkItem]:
        query=text.strip()
        with self._connect() as db:
            if query:
                escaped=query.replace("\\","\\\\").replace("%","\\%").replace("_","\\_")
                needle=f"%{escaped}%"
                rows=db.execute("WITH RECURSIVE ancestors(bookmark_id,folder_id,title,parent_id) AS (SELECT b.id,p.id,p.title,p.parent_id FROM bookmark_items b JOIN bookmark_items p ON p.id=b.parent_id WHERE b.item_type='bookmark' UNION ALL SELECT a.bookmark_id,p.id,p.title,p.parent_id FROM ancestors a JOIN bookmark_items p ON p.id=a.parent_id WHERE p.parent_id IS NOT NULL) SELECT DISTINCT b.id,b.title,b.url,b.parent_id,b.position,b.created_at,b.updated_at,b.item_type FROM bookmark_items b LEFT JOIN ancestors a ON a.bookmark_id=b.id WHERE b.item_type='bookmark' AND (b.title LIKE ? ESCAPE '\\' COLLATE NOCASE OR b.url LIKE ? ESCAPE '\\' COLLATE NOCASE OR a.title LIKE ? ESCAPE '\\' COLLATE NOCASE) ORDER BY b.parent_id,b.position,b.id LIMIT ?",(needle,needle,needle,max(1,min(limit,10000)))).fetchall()
            else:
                rows=db.execute("SELECT id,title,url,parent_id,position,created_at,updated_at,item_type FROM bookmark_items WHERE item_type='bookmark' ORDER BY parent_id,position,id LIMIT ?",(max(1,min(limit,10000)),)).fetchall()
        return [BookmarkItem(**dict(row)) for row in rows]

    def export_tree(self, parent_id: int | None = None) -> list[dict[str, object]]:
        parent_id = self.BAR_ROOT_ID if parent_id is None else parent_id
        return [self._to_tree(item) for item in self.children(parent_id)]

    def _to_tree(self, item: BookmarkItem) -> dict[str, object]:
        node:dict[str,object]={"type":item.item_type,"title":item.title,"url":item.url,"created_at":item.created_at,"updated_at":item.updated_at}
        if item.is_folder: node["children"]=[self._to_tree(child) for child in self.children(item.id)]
        return node

    def import_tree(self, nodes: list[dict[str, object]], parent_id: int = BAR_ROOT_ID, skip_duplicates: bool = True) -> tuple[int,int,int]:
        bookmarks=folders=skipped=0
        with self._connect() as db:
            check=db.execute("SELECT item_type FROM bookmark_items WHERE id=?",(parent_id,)).fetchone()
            if not check or check[0]!="folder": raise ValueError("Import destination is not a folder")
            def add(children: list[dict[str,object]], parent: int) -> None:
                nonlocal bookmarks,folders,skipped
                for raw in children:
                    title=str(raw.get("title") or "").strip()
                    if raw.get("type")=="folder":
                        folder_id=self._insert(db,title or "Imported Folder",None,parent,"folder"); folders+=1
                        created=str(raw.get("created_at") or "")
                        modified=str(raw.get("updated_at") or created)
                        if created or modified:db.execute("UPDATE bookmark_items SET created_at=COALESCE(NULLIF(?,''),created_at),updated_at=COALESCE(NULLIF(?,''),updated_at) WHERE id=?",(created,modified,folder_id))
                        nested=raw.get("children",[])
                        if isinstance(nested,list): add(nested,folder_id)
                    elif raw.get("type")=="bookmark":
                        url=self.normalize_url(str(raw.get("url") or ""))
                        if not url: skipped+=1; continue
                        if skip_duplicates and db.execute("SELECT 1 FROM bookmark_items WHERE item_type='bookmark' AND url=?",(url,)).fetchone(): skipped+=1; continue
                        bid=self._insert(db,title or url,url,parent); bookmarks+=1
                        created=str(raw.get("created_at") or "")
                        modified=str(raw.get("updated_at") or created)
                        if created or modified: db.execute("UPDATE bookmark_items SET created_at=COALESCE(NULLIF(?,''),created_at),updated_at=COALESCE(NULLIF(?,''),updated_at) WHERE id=?",(created,modified,bid))
                    else: skipped+=1
            add(nodes,parent_id)
        if bookmarks or folders:self.bookmarks_changed.emit()
        return bookmarks,folders,skipped

    # Compatibility facade for the pre-Phase 10 callers/tests.
    def add_bookmark(self, title: str, url: str) -> bool:
        try: self.create_bookmark(title,url)
        except ValueError:return False
        return True

    def remove_bookmark(self, url: str) -> bool:
        item=self.find_by_url(url)
        return self.delete_item(item.id) if item else False

    def get_bookmarks(self) -> list[dict[str,str]]:
        return [{"title":item.title,"url":item.url or ""} for item in self.search()]

    def clear(self) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM bookmark_items WHERE is_system_root=0")
        self.bookmarks_changed.emit()
