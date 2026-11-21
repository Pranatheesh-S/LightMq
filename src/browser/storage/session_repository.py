"""Atomic local JSON storage for browser session and recovery snapshots."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from PySide6.QtCore import QIODevice, QSaveFile

from browser.storage.session_model import SessionSnapshot
from browser.utils.paths import sessions_directory

logger = logging.getLogger(__name__)


class SessionRepository:
    """Read/write validated snapshots and the previous-run lifecycle marker."""

    SCHEMA_VERSION = 1

    def __init__(self, directory: str | Path | None = None):
        self.directory = Path(directory) if directory is not None else sessions_directory()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.current_path = self.directory / "current_session.json"
        self.recovery_path = self.directory / "recovery_session.json"
        self.lifecycle_path = self.directory / "lifecycle.json"

    def load_current(self) -> SessionSnapshot | None:
        """Load a validated current session, returning None on invalid data."""
        return self._load_snapshot(self.current_path)

    def load_recovery(self) -> SessionSnapshot | None:
        """Load the last atomically written recovery snapshot."""
        return self._load_snapshot(self.recovery_path)

    def save(self, snapshot: SessionSnapshot) -> bool:
        """Atomically save the current and recovery snapshots."""
        payload = snapshot.to_dict()
        try:
            SessionSnapshot.from_dict(payload)
        except (TypeError, ValueError):
            logger.exception("Refusing to save an invalid browser session snapshot")
            return False
        current_saved = self._write_json(self.current_path, payload)
        recovery_saved = self._write_json(self.recovery_path, payload)
        return current_saved and recovery_saved

    def begin_run(self) -> tuple[bool, SessionSnapshot | None]:
        """Detect an unclean prior run and persist this run's active marker."""
        marker = self._read_json(self.lifecycle_path)
        previous_unclean = (
            isinstance(marker, dict)
            and marker.get("schema_version") == self.SCHEMA_VERSION
            and marker.get("clean_shutdown") is False
            and isinstance(marker.get("run_id"), str)
        )
        recovery = self.load_recovery() if previous_unclean else None
        self._write_json(
            self.lifecycle_path,
            {
                "schema_version": self.SCHEMA_VERSION,
                "run_id": uuid4().hex,
                "clean_shutdown": False,
            },
        )
        return bool(previous_unclean and recovery and recovery.tabs), recovery

    def mark_clean_shutdown(self) -> bool:
        """Mark the current run clean only after its final snapshot is saved."""
        marker = self._read_json(self.lifecycle_path)
        if not isinstance(marker, dict):
            marker = {"schema_version": self.SCHEMA_VERSION}
        marker["clean_shutdown"] = True
        return self._write_json(self.lifecycle_path, marker)

    def _load_snapshot(self, path: Path) -> SessionSnapshot | None:
        raw = self._read_json(path)
        if not isinstance(raw, dict):
            return None
        try:
            return SessionSnapshot.from_dict(raw)
        except (TypeError, ValueError, KeyError):
            logger.warning("Ignoring invalid browser session file at %s", path)
            return None

    @staticmethod
    def _read_json(path: Path) -> Any:
        try:
            with path.open("r", encoding="utf-8") as stream:
                return json.load(stream)
        except (OSError, json.JSONDecodeError, UnicodeError):
            return None

    @staticmethod
    def _write_json(path: Path, value: dict[str, Any]) -> bool:
        """Commit valid JSON atomically without discarding the prior file on error."""
        try:
            payload = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            save_file = QSaveFile(str(path))
            save_file.setDirectWriteFallback(False)
            if not save_file.open(QIODevice.OpenModeFlag.WriteOnly):
                logger.error("Could not open session file for writing: %s", save_file.errorString())
                return False
            if save_file.write(payload) != len(payload):
                logger.error("Could not write complete session file: %s", save_file.errorString())
                save_file.cancelWriting()
                return False
            if not save_file.commit():
                logger.error("Could not commit session file: %s", save_file.errorString())
                return False
            try:
                os.chmod(path, 0o600)
            except OSError:
                # Windows uses the containing user's profile ACL; chmod is best-effort elsewhere.
                pass
            return True
        except (OSError, TypeError, ValueError):
            logger.exception("Failed to write browser session file: %s", path)
            return False
