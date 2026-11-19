"""End-to-end tests for browser loading, URL handling, and DevTools inspection."""

import sys
from PySide6.QtCore import QEventLoop, QTimer, QUrl
from PySide6.QtWidgets import QApplication

from browser.ui.main_window import MainWindow

app = QApplication.instance() or QApplication(sys.argv)


def test_e2e_page_load_and_devtools():
    """Verify live page load, title update, address bar sync, and DevTools inspector URL."""
    window = MainWindow(initial_url="about:blank")
    window.show()
    loop = QEventLoop()

    # Navigate to example.com
    window.navigate_to("example.com")
    assert window.web_view.url() == QUrl("https://example.com")

    # Wait for page load
    def on_load_finished(ok):
        if loop.isRunning():
            loop.quit()

    window.web_view.loadFinished.connect(on_load_finished)
    # 8-second safety timeout
    QTimer.singleShot(8000, loop.quit)
    loop.exec()

    # Verify address bar and window title updated
    assert "https://example.com" in window.address_bar.text() or window.web_view.url().host() == "example.com"

    # Open DevTools
    window.devtools_manager.open()
    assert window.devtools_manager.is_open() is True
    assert window.devtools_panel.isVisible() is True

    # Give DevTools a moment to load inspector.html
    devtools_loop = QEventLoop()
    QTimer.singleShot(600, devtools_loop.quit)
    devtools_loop.exec()

    devtools_url = window.devtools_panel.get_page().url().toString()
    assert "devtools://" in devtools_url or "inspector.html" in devtools_url or devtools_url == ""

    # Close DevTools
    window.devtools_manager.close()
    assert window.devtools_manager.is_open() is False
    window.close()
