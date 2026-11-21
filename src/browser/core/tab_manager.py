"""Tab manager subsystem for LightMq Browser.

Manages the lifecycle, collection, and activation of independent WebView instances.
Provides decoupled signals for tab creation, switching, reordering, and safe destruction.
Also maintains a bounded history of recently closed tabs for Ctrl+Shift+T restoration.
"""

from collections import deque
import logging
from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtWebEngineCore import QWebEngineProfile

from browser.core.navigation import normalize_url
from browser.utils.constants import DEFAULT_START_URL
from browser.webengine.web_view import WebView
from browser.webengine.web_page import WebPage
from browser.storage.session_model import SessionSnapshot

logger = logging.getLogger(__name__)


class TabManager(QObject):
    """Manages collection, active tracking, and lifecycle of browser tabs."""

    tab_created = Signal(int, WebView)
    tab_closing = Signal(int, WebView)
    tab_closed = Signal(int)
    current_changed = Signal(int, WebView)
    tab_moved = Signal(int, int)
    count_changed = Signal(int)

    def __init__(
        self,
        default_url: str = DEFAULT_START_URL,
        profile: QWebEngineProfile | None = None,
        is_private: bool = False,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._default_url = default_url
        self._profile = profile
        self._is_private = is_private
        self._views: list[WebView] = []
        self._tab_ids: dict[WebView, str] = {}
        self._current_index: int = -1
        # Bounded stack of closed tab states: (url, title), maxlen=25
        self._closed_tabs: deque[tuple[QUrl, str]] = deque(maxlen=25)

    @property
    def default_url(self) -> str:
        """Return the default homepage / start URL."""
        return self._default_url

    @property
    def is_private(self) -> bool:
        """Return True if this manager belongs to a private browsing session."""
        return self._is_private

    def count(self) -> int:
        """Return the total number of open tabs."""
        return len(self._views)

    def current_index(self) -> int:
        """Return the zero-based index of the currently active tab."""
        return self._current_index

    def current_view(self) -> WebView | None:
        """Return the active WebView instance, or None if no tabs exist."""
        if 0 <= self._current_index < len(self._views):
            return self._views[self._current_index]
        return None

    def view_at(self, index: int) -> WebView | None:
        """Return the WebView at the specified index."""
        if 0 <= index < len(self._views):
            return self._views[index]
        return None

    def index_of(self, view: WebView) -> int:
        """Return the index of the specified WebView, or -1 if not found."""
        try:
            return self._views.index(view)
        except ValueError:
            return -1

    def tab_id_for(self, view: WebView | None) -> str | None:
        """Return a tab's stable in-memory identifier, if it is managed here."""
        return self._tab_ids.get(view) if view is not None else None

    def create_tab(
        self,
        url: QUrl | str | None = None,
        activate: bool = True,
        opened_for_popup: bool = False,
        opener_view: WebView | None = None,
        tab_id: str | None = None,
        tab_title: str = "",
    ) -> WebView:
        """Create a new tab hosting an independent WebView.

        Args:
            url: Optional destination URL. Defaults to self._default_url.
            activate: If True, immediately sets the new tab as active.

        Returns:
            WebView: The newly instantiated WebView.
        """
        view = WebView(profile=self._profile)
        existing_ids = set(self._tab_ids.values())
        candidate_id = tab_id if tab_id and tab_id not in existing_ids else None
        self._tab_ids[view] = candidate_id or SessionSnapshot.new_tab_id()
        view.restored_title = tab_title
        view._custom_page.set_download_context(view, self, opened_for_popup, opener_view)

        # Connect window factory so target="_blank" links create a new tab in this manager
        def create_popup_page() -> WebPage:
            """Create and mark a tab opened by web content's new-window request."""
            return self.create_tab(
                opened_for_popup=True,
                opener_view=view,
            )._custom_page

        view._custom_page.set_window_factory(create_popup_page)

        # Append to tab collection
        self._views.append(view)
        new_index = len(self._views) - 1

        self.tab_created.emit(new_index, view)
        self.count_changed.emit(len(self._views))

        # Navigate to target or default URL
        target = url if url is not None else self._default_url
        if isinstance(target, str):
            target_qurl = normalize_url(target)
        else:
            target_qurl = target
        view.navigate(target_qurl)

        if activate or len(self._views) == 1:
            self.set_current_index(new_index)

        logger.info("Created tab %d", new_index)
        return view

    def close_tab(self, index: int) -> None:
        """Safely close and destroy the tab at the given index.

        If the final tab is closed, automatically creates a new default tab to
        prevent terminating the browser window.
        Saves closed tab to restore stack unless in private browsing mode.

        Args:
            index: Zero-based tab index to close.
        """
        if not (0 <= index < len(self._views)):
            return

        closing_view = self._views[index]
        was_active = (index == self._current_index)

        # Record tab URL and title for restoration (never in private browsing)
        if not self._is_private:
            closed_url = closing_view.url()
            closed_title = closing_view.title()
            if (
                closed_url.isValid()
                and not closed_url.isEmpty()
                and closed_url.toString() != "about:blank"
            ):
                self._closed_tabs.append((closed_url, closed_title))

        # Notify listeners before removing from list
        self.tab_closing.emit(index, closing_view)

        del self._views[index]
        self._tab_ids.pop(closing_view, None)
        self.tab_closed.emit(index)

        # Prevent browser termination when last tab is closed
        if len(self._views) == 0:
            self._current_index = -1
            self.create_tab(self._default_url, activate=True)
        else:
            if was_active:
                new_index = min(index, len(self._views) - 1)
                self._current_index = -1
                self.set_current_index(new_index)
            elif index < self._current_index:
                self._current_index -= 1

        self.count_changed.emit(len(self._views))

        # Safely disconnect and schedule deletion
        try:
            closing_view.stop()
        except Exception:
            pass
        closing_view.deleteLater()
        logger.info("Closed tab %d. Remaining tabs: %d", index, len(self._views))

    def close_current_tab(self) -> None:
        """Close the currently active tab."""
        if 0 <= self._current_index < len(self._views):
            self.close_tab(self._current_index)

    def restore_closed_tab(self) -> WebView | None:
        """Restore the most recently closed tab from the stack.

        Returns:
            WebView | None: The recreated tab, or None if stack is empty.
        """
        if not self._closed_tabs:
            return None

        url, title = self._closed_tabs.pop()
        new_view = self.create_tab(url=url, activate=True)
        logger.info("Restored a closed tab")
        return new_view

    def clear_closed_tabs(self) -> None:
        """Clear recently closed tabs history."""
        self._closed_tabs.clear()

    def closed_tabs_count(self) -> int:
        """Return the count of restoreable closed tabs."""
        return len(self._closed_tabs)

    def set_current_index(self, index: int) -> None:
        """Switch the active tab to the specified index.

        Args:
            index: Target tab index.
        """
        if not (0 <= index < len(self._views)):
            return
        if index == self._current_index:
            return

        self._current_index = index
        active_view = self._views[index]
        self.current_changed.emit(index, active_view)
        logger.debug("Switched active tab to %d", index)

    def switch_to_tab(self, index: int) -> None:
        """Switch to tab at specified zero-based index if within range.

        Args:
            index: Target tab index (0 to 7 for Ctrl+1..Ctrl+8).
        """
        if 0 <= index < len(self._views):
            self.set_current_index(index)

    def switch_to_last_tab(self) -> None:
        """Switch to the rightmost/last tab in the collection (Ctrl+9)."""
        if self._views:
            self.set_current_index(len(self._views) - 1)

    def next_tab(self) -> None:
        """Switch to the next tab, wrapping around if at the end."""
        if len(self._views) > 1:
            next_idx = (self._current_index + 1) % len(self._views)
            self.set_current_index(next_idx)

    def prev_tab(self) -> None:
        """Switch to the previous tab, wrapping around if at the beginning."""
        if len(self._views) > 1:
            prev_idx = (self._current_index - 1) % len(self._views)
            self.set_current_index(prev_idx)

    def move_tab(self, from_index: int, to_index: int) -> None:
        """Reorder a tab from one index to another.

        Args:
            from_index: Origin index.
            to_index: Destination index.
        """
        if (
            0 <= from_index < len(self._views)
            and 0 <= to_index < len(self._views)
            and from_index != to_index
        ):
            active_view = self.current_view()
            view = self._views.pop(from_index)
            self._views.insert(to_index, view)

            if active_view is not None:
                self._current_index = self._views.index(active_view)

            self.tab_moved.emit(from_index, to_index)
            logger.debug("Moved tab from %d to %d", from_index, to_index)
