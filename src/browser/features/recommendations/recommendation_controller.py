"""Debounced background refresh and short-lived cache for local recommendations."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal, Slot

from browser.features.recommendations.recommendation_engine import RecommendationEngine
from browser.features.recommendations.recommendation_repository import RecommendationRepository


EMPTY_RESULT = {"recommended": [], "related": [], "continue": []}


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"0", "false", "no", "off", ""}:
            return False
        if normalized in {"1", "true", "yes", "on"}:
            return True
        return default
    return bool(value)


class _WorkerSignals(QObject):
    completed = Signal(int, object)


class _RecommendationWorker(QRunnable):
    """Fetch bounded SQL inputs and rank them away from the GUI thread."""

    def __init__(self, generation: int, history_manager, bookmark_manager,
                 repository: RecommendationRepository, engine: RecommendationEngine,
                 contexts: list[tuple[str, str, str]], include_history: bool,
                 include_bookmarks: bool, show_continue: bool, show_related: bool) -> None:
        super().__init__()
        self.signals = _WorkerSignals()
        self.generation = generation
        self.history_manager = history_manager
        self.bookmark_manager = bookmark_manager
        self.repository = repository
        self.engine = engine
        self.contexts = contexts
        self.include_history = include_history
        self.include_bookmarks = include_bookmarks
        self.show_continue = show_continue
        self.show_related = show_related

    @Slot()
    def run(self) -> None:
        try:
            history = self.history_manager.recommendation_candidates(500) if self.include_history else []
            bookmarks = self.bookmark_manager.recommendation_candidates(1000) if self.include_bookmarks else []
            feedback = self.repository.feedback()
            results = []
            for key, url, title in self.contexts:
                data = self.engine.recommend(
                    history, bookmarks, feedback, context_url=url, context_title=title,
                    show_continue=self.show_continue, show_related=self.show_related,
                )
                results.append((key, data))
            self.signals.completed.emit(self.generation, results)
        except Exception:
            self.signals.completed.emit(self.generation, [(key, EMPTY_RESULT) for key, _url, _title in self.contexts])


class RecommendationController(QObject):
    """Keep recommendations local, opt-in, cached, and isolated from private windows."""

    recommendations_ready = Signal(str, str)
    feedback_changed = Signal()
    CACHE_SECONDS = 30.0
    MAX_CONTEXTS = 16

    def __init__(self, history_manager, bookmark_manager, settings, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.history_manager = history_manager
        self.bookmark_manager = bookmark_manager
        self.settings = settings
        self.repository = RecommendationRepository(history_manager.storage_path)
        self.engine = RecommendationEngine()
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self._cache: dict[str, tuple[float, dict[str, list[dict]]]] = {}
        self._contexts: dict[str, tuple[str, str]] = {}
        self._generation = 0
        self._running = False
        self._pending_refresh = False
        self._worker: _RecommendationWorker | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._start_worker)
        history_manager.history_changed.connect(self.invalidate)
        bookmark_manager.bookmarks_changed.connect(self.invalidate)
        settings.changed.connect(self._setting_changed)

    @staticmethod
    def context_key(url: str, title: str) -> str:
        """Hash page context in memory so the renderer receives no raw context key."""
        from urllib.parse import urlsplit
        host = (urlsplit(url).hostname or "").lower()
        words = " ".join(title.casefold().split())[:300]
        return hashlib.sha256(f"{host}\n{words}".encode("utf-8", errors="ignore")).hexdigest()[:24]

    @property
    def enabled(self) -> bool:
        return _as_bool(self.settings.get("recommendations/enabled", False), False)

    def options(self) -> tuple[bool, bool, bool, bool]:
        return (
            _as_bool(self.settings.get("recommendations/source_history", True), True),
            _as_bool(self.settings.get("recommendations/source_bookmarks", True), True),
            _as_bool(self.settings.get("recommendations/show_continue", True), True),
            _as_bool(self.settings.get("recommendations/show_related", True), True),
        )

    def recommendations_json(self, context_url: str = "", context_title: str = "") -> str:
        """Return a cached snapshot immediately and enqueue any required refresh."""
        if not self.enabled or not self.show_on_new_tab:
            return json.dumps(EMPTY_RESULT, separators=(",", ":"))
        key = self.context_key(context_url, context_title)
        self._contexts[key] = (context_url, context_title)
        if len(self._contexts) > self.MAX_CONTEXTS:
            oldest = next(iter(self._contexts))
            self._contexts.pop(oldest, None); self._cache.pop(oldest, None)
        cached = self._cache.get(key)
        if cached and time.monotonic() - cached[0] < self.CACHE_SECONDS:
            return json.dumps(cached[1], separators=(",", ":"), ensure_ascii=False)
        self._schedule()
        return json.dumps(EMPTY_RESULT, separators=(",", ":"))

    @property
    def show_on_new_tab(self) -> bool:
        """Whether recommendation cards are allowed on the built-in start page."""
        return _as_bool(self.settings.get("recommendations/show_new_tab", True), True)

    def refresh(self, context_url: str, context_title: str) -> None:
        """Request a fresh ranking for one existing start page."""
        if not self.enabled or not self.show_on_new_tab:
            return
        key = self.context_key(context_url, context_title)
        self._contexts[key] = (context_url, context_title)
        self._cache.pop(key, None)
        self._generation += 1
        self._schedule()

    def pin(self, url: str, pinned: bool, title: str = "") -> bool:
        if not self.enabled or not self.repository.set_pinned(url, pinned, title):
            return False
        self.feedback_changed.emit(); self.invalidate()
        return True

    def hide(self, url: str, title: str = "") -> bool:
        if not self.enabled or not self.repository.set_hidden(url, True, title):
            return False
        self.feedback_changed.emit(); self.invalidate()
        return True

    def reveal(self, url_key: str) -> bool:
        result = self.repository.reveal(url_key)
        if result:
            self.feedback_changed.emit(); self.invalidate()
        return result

    def hidden_recommendations(self) -> list[dict[str, str]]:
        return self.repository.hidden()

    def clear_data(self, keep_pins: bool = False) -> None:
        """Clear feedback, optionally preserving user-pinned shortcuts."""
        self.repository.clear(include_pins=not keep_pins)
        self._cache.clear()
        self.feedback_changed.emit()
        self.invalidate()

    @Slot()
    def invalidate(self) -> None:
        """Invalidate stale local results and debounce one refresh for live contexts."""
        self._generation += 1
        self._cache.clear()
        if self.enabled and self.show_on_new_tab and self._contexts:
            self._schedule()
        else:
            self._emit_empty_for_contexts()

    def _schedule(self) -> None:
        if self.enabled:
            self._pending_refresh = True
            self._timer.start()

    def _setting_changed(self, key: str, _value: Any) -> None:
        if key.startswith("recommendations/"):
            self.invalidate()

    def _emit_empty_for_contexts(self) -> None:
        payload = json.dumps(EMPTY_RESULT, separators=(",", ":"))
        for key in tuple(self._contexts):
            self.recommendations_ready.emit(key, payload)

    @Slot(int, object)
    def _worker_done(self, generation: int, results: object) -> None:
        self._running = False
        self._worker = None
        if generation == self._generation and isinstance(results, list) and self.enabled:
            for key, data in results:
                if key not in self._contexts or not isinstance(data, dict):
                    continue
                self._cache[key] = (time.monotonic(), data)
                self.recommendations_ready.emit(key, json.dumps(data, separators=(",", ":"), ensure_ascii=False))
        if self._pending_refresh:
            self._timer.start()

    @Slot()
    def _start_worker(self) -> None:
        if self._running or not self.enabled or not self.show_on_new_tab or not self._contexts:
            return
        self._pending_refresh = False
        include_history, include_bookmarks, show_continue, show_related = self.options()
        self._running = True
        worker = _RecommendationWorker(
            self._generation, self.history_manager, self.bookmark_manager, self.repository,
            self.engine, [(key, *self._contexts[key]) for key in self._contexts],
            include_history, include_bookmarks, show_continue, show_related,
        )
        worker.signals.completed.connect(self._worker_done)
        self._worker = worker
        self.pool.start(worker)
