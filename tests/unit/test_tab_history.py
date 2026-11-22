"""Recently closed tab stack behavior."""

from PySide6.QtCore import QUrl

from browser.core.tab_history import ClosedTab, TabHistory


def test_history_is_bounded_and_pops_newest_first():
    history = TabHistory(limit=2)
    for i in range(3):
        history.record(ClosedTab(QUrl(f"https://example{i}.com"), str(i), i))
    assert len(history) == 2
    assert history.pop().title == "2"
    assert history.pop().title == "1"
    assert history.pop() is None
