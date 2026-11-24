"""Bounded metadata stack for tabs closed by the user."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from PySide6.QtCore import QUrl


@dataclass(frozen=True)
class ClosedTab:
    """Restorable metadata for one intentionally closed tab."""

    url: QUrl
    title: str
    position: int
    group_id: str | None = None
    pinned: bool = False
    group_position: int | None = None


class TabHistory:
    """Keep a bounded most-recently-closed stack, excluding shutdown teardown."""

    DEFAULT_LIMIT = 20

    def __init__(self, limit: int = DEFAULT_LIMIT):
        self._limit = max(1, int(limit))
        self._closed: deque[ClosedTab] = deque(maxlen=self._limit)

    def record(self, tab: ClosedTab) -> None:
        """Add a closed tab to the top of the stack."""
        self._closed.append(tab)

    def pop(self) -> ClosedTab | None:
        """Return and remove the most recently closed tab."""
        return self._closed.pop() if self._closed else None

    def items(self) -> tuple[ClosedTab, ...]:
        """Return recently closed tabs, newest first, without removing them."""
        return tuple(reversed(self._closed))

    def take(self, tab: ClosedTab) -> ClosedTab | None:
        """Remove a selected closed tab from the stack."""
        try:self._closed.remove(tab)
        except ValueError:return None
        return tab

    def clear(self) -> None:
        """Clear all recently closed metadata."""
        self._closed.clear()

    def __len__(self) -> int:
        return len(self._closed)
