"""Integration checks for download request decisions and manager controls."""

import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QUrl, Signal
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from PySide6.QtWebEngineCore import QWebEngineDownloadRequest

from browser.features.downloads.download_manager import DownloadManager
from browser.ui.main_window import MainWindow
from browser.webengine.download_handler import DownloadHandler, attach_download_handler

app = QApplication.instance() or QApplication(sys.argv)


class FakeDownloadRequest(QObject):
    """Signal-compatible request double for deterministic lifecycle checks."""

    receivedBytesChanged = Signal()
    totalBytesChanged = Signal()
    stateChanged = Signal(object)
    isPausedChanged = Signal()
    interruptReasonChanged = Signal()

    def __init__(self):
        super().__init__()
        self._id = 7
        self._url = QUrl("https://example.test/download?token=secret")
        self._filename = "../report.pdf"
        self._directory = ""
        self._received = 0
        self._total = 1000
        self._state = QWebEngineDownloadRequest.DownloadState.DownloadRequested
        self._paused = False
        self.accepted = False
        self.cancelled = False

    def id(self): return self._id
    def url(self): return self._url
    def suggestedFileName(self): return self._filename
    def downloadFileName(self): return self._filename
    def downloadDirectory(self): return self._directory
    def setDownloadDirectory(self, value): self._directory = value
    def setDownloadFileName(self, value): self._filename = value
    def receivedBytes(self): return self._received
    def totalBytes(self): return self._total
    def mimeType(self): return "application/pdf"
    def state(self): return self._state
    def isPaused(self): return self._paused
    def interruptReasonString(self): return "network disconnected"

    def accept(self):
        self.accepted = True
        self._state = QWebEngineDownloadRequest.DownloadState.DownloadInProgress
        self.stateChanged.emit(self._state)

    def cancel(self):
        self.cancelled = True
        self._state = QWebEngineDownloadRequest.DownloadState.DownloadCancelled
        self.stateChanged.emit(self._state)

    def pause(self):
        self._paused = True
        self.isPausedChanged.emit()

    def resume(self):
        self._paused = False
        self.isPausedChanged.emit()


def test_request_is_safely_configured_and_accepted(monkeypatch, tmp_path):
    manager = DownloadManager()
    request = FakeDownloadRequest()
    request._filename = "../report"
    destination = tmp_path / "report.pdf"
    initial_names = []

    def choose_destination(*args):
        initial_names.append(args[2])
        return str(destination), ""

    monkeypatch.setattr(QFileDialog, "getSaveFileName", choose_destination)

    DownloadHandler(manager).handle_request(request)

    assert request.accepted
    assert not request.cancelled
    assert request.downloadFileName() == "report.pdf"
    assert Path(initial_names[0]).name == "report.pdf"
    assert Path(request.downloadDirectory()) == tmp_path
    assert manager.get_downloads()[0].destination == str(destination)


def test_rejected_destination_cancels_request(monkeypatch, tmp_path):
    manager = DownloadManager()
    request = FakeDownloadRequest()
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: ("", ""))

    DownloadHandler(manager).handle_request(request)

    assert request.cancelled
    assert not request.accepted
    assert manager.get_downloads() == []


def test_existing_destination_requires_confirmation_and_can_be_changed(monkeypatch, tmp_path):
    manager = DownloadManager()
    request = FakeDownloadRequest()
    existing = tmp_path / "report.pdf"
    alternate = tmp_path / "another.pdf"
    existing.write_text("keep this file", encoding="utf-8")
    selections = iter((str(existing), str(alternate)))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (next(selections), ""))
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.No,
    )

    DownloadHandler(manager).handle_request(request)

    assert existing.read_text(encoding="utf-8") == "keep this file"
    assert request.accepted
    assert manager.get_downloads()[0].destination == str(alternate)


def test_transfer_controls_and_terminal_status_are_independent():
    manager = DownloadManager()
    first = FakeDownloadRequest()
    second = FakeDownloadRequest()
    second._total = 0
    item_one = manager.add_request(first, "C:/downloads/first.pdf")
    item_two = manager.add_request(second, "C:/downloads/second.pdf")
    assert item_two.progress is None

    first._received = 500
    first.receivedBytesChanged.emit()
    assert item_one.progress == 50
    assert item_two.received_bytes == 0

    item_one.pause()
    assert item_one.is_paused
    item_one.resume()
    assert not item_one.is_paused
    item_one.cancel()
    assert item_one.status == "Cancelled"
    assert item_two.status == "Pending"
    assert len(manager.get_downloads()) == 2

    manager.remove(item_one)
    assert len(manager.get_downloads()) == 1
    assert manager.get_downloads()[0] is item_two


def test_completed_download_does_not_show_zero_second_eta():
    request = FakeDownloadRequest()
    item = DownloadManager().add_request(request, "C:/downloads/report.pdf")
    item.speed_bytes_per_second = 100
    request._state = QWebEngineDownloadRequest.DownloadState.DownloadCompleted
    request.stateChanged.emit(request._state)

    assert item.status == "Completed"
    assert item.eta_text == ""


def test_local_http_download_completes_through_webengine_profile(monkeypatch, tmp_path):
    """A browser initiated transfer reaches disk through the profile signal."""
    payload = b"%PDF-1.4\nLightMq local test download\n" + (b"x" * 32768)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                body = (
                    b'<title>ready</title><a id="file" target="_blank" href="/file">'
                    b'Download PDF</a>'
                )
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            else:
                body = payload
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Disposition", 'attachment; filename="sample.pdf"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    destination = tmp_path / "sample.pdf"
    popup_destination = tmp_path / "popup.pdf"
    destinations = iter((destination, popup_destination))
    window = MainWindow(initial_url=f"http://127.0.0.1:{server.server_port}/", is_private=True)
    assert attach_download_handler(
        window._profile, window.download_manager, window
    ) is window._download_handler
    window.show()
    try:
        view = window.tab_manager.current_view()
        assert view is not None
        for _ in range(300):
            app.processEvents()
            if view.title() == "ready":
                break
            QTest.qWait(10)

        def choose_destination(*args):
            """Allow the scheduled restore to run while the save dialog is active."""
            selected = next(destinations)
            if selected == destination:
                for _ in range(100):
                    app.processEvents()
                    if view.title() == "ready" and view.url().path() == "/":
                        break
                    QTest.qWait(10)
                assert view.title() == "ready"
                assert view.url().path() == "/"
            return str(selected), ""

        monkeypatch.setattr(QFileDialog, "getSaveFileName", choose_destination)
        view.navigate(QUrl(f"http://127.0.0.1:{server.server_port}/file"))

        for _ in range(600):
            app.processEvents()
            downloads = window.download_manager.get_downloads()
            if downloads and not downloads[0].is_active:
                break
            QTest.qWait(10)

        downloads = window.download_manager.get_downloads()
        assert downloads, "Qt WebEngine did not emit downloadRequested"
        assert downloads[0].status == "Completed"
        assert destination.read_bytes() == payload
        QTest.qWait(100)
        app.processEvents()
        assert view.title() == "ready"
        assert view.url().path() == "/"

        # A download opened with target=_blank gets a temporary popup tab. It is
        # closed after the request is accepted instead of remaining as New Tab.
        view.page().runJavaScript("document.getElementById('file').click()")
        for _ in range(600):
            app.processEvents()
            current_downloads = window.download_manager.get_downloads()
            if (
                len(current_downloads) >= 2
                and current_downloads[0].status == "Completed"
                and window.tab_manager.count() == 1
            ):
                break
            QTest.qWait(10)
        assert len(window.download_manager.get_downloads()) >= 2
        assert window.tab_manager.count() == 1
        assert window.tab_manager.current_view() is view
        assert popup_destination.read_bytes() == payload
    finally:
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_ctrl_j_opens_and_reuses_download_manager_and_escape_closes_it():
    window = MainWindow(is_private=True)
    window.show()
    app.processEvents()
    shortcut = window.shortcut_manager.get_shortcut("Ctrl+J")
    assert shortcut is not None

    shortcut.activated.emit()
    first_dialog = window._downloads_dialog
    assert first_dialog.isVisible()
    window._show_download_notification("Download completed: sample.pdf", 3500)
    app.processEvents()
    assert window._notification_toast.isVisible()
    assert "sample.pdf" in window._notification_toast.label.text()
    shortcut.activated.emit()
    assert window._downloads_dialog is first_dialog

    first_dialog._escape_shortcut.activated.emit()
    app.processEvents()
    assert not first_dialog.isVisible()
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
