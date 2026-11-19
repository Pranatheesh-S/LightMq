"""Unit tests for AddressBar widget."""

import sys
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication

from browser.ui.address_bar import AddressBar

app = QApplication.instance() or QApplication(sys.argv)


def test_address_bar_signals():
    """Verify that navigate_requested signal emits entered text."""
    bar = AddressBar()
    emitted = []
    bar.navigate_requested.connect(emitted.append)

    bar.setText("example.com")
    bar._on_return_pressed()

    assert emitted == ["example.com"]


def test_address_bar_set_url():
    """Verify set_url updates the text when not focused."""
    bar = AddressBar()
    bar.clearFocus()
    bar.set_url(QUrl("https://example.com/test"))

    assert bar.text() == "https://example.com/test"


def test_address_bar_about_blank():
    """about:blank should clear the address bar."""
    bar = AddressBar()
    bar.clearFocus()
    bar.set_url(QUrl("about:blank"))

    assert bar.text() == ""
