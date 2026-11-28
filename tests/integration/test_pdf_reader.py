"""Integration coverage for Qt WebEngine's native PDF reader."""

import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PySide6.QtCore import QSettings, QUrl
from PySide6.QtGui import QPdfWriter, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings

from browser.ui.main_window import MainWindow
from browser.core.session_manager import SessionManager
from browser.storage.session_model import SessionSnapshot, SessionTab
from browser.storage.session_repository import SessionRepository
from browser.webengine.web_view import WebView


app = QApplication.instance() or QApplication(sys.argv)


def _make_pdf(path: Path) -> bytes:
    writer = QPdfWriter(str(path))
    writer.setTitle("LightMq PDF Test")
    painter = QPainter(writer)
    assert painter.isActive()
    painter.drawText(100, 100, "LightMq searchable PDF sample")
    painter.end()
    del writer
    data = path.read_bytes()
    assert data.startswith(b"%PDF-")
    return data


def _wait_until(predicate, timeout_ms: int = 8000) -> bool:
    elapsed = 0
    while elapsed < timeout_ms:
        app.processEvents()
        if predicate():
            return True
        QTest.qWait(10)
        elapsed += 10
    app.processEvents()
    return bool(predicate())


def _isolate_window_settings(tmp_path: Path, monkeypatch, filename: str = "settings.ini") -> QSettings:
    """Keep GUI integration settings in a test-owned temporary INI file."""
    store = QSettings(str(tmp_path / filename), QSettings.Format.IniFormat)
    monkeypatch.setattr("browser.ui.main_window.QSettings", lambda *_args: store)
    return store


def test_ctrl_o_opens_local_unicode_pdf_and_settings_apply(tmp_path, monkeypatch):
    pdf_path = tmp_path / "résumé with spaces.pdf"
    _make_pdf(pdf_path)
    store = _isolate_window_settings(tmp_path, monkeypatch)
    window = MainWindow(initial_url="about:blank", is_private=True)
    window._browser_settings.set("pdf/open_in_browser", True)
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (str(pdf_path), "PDF documents (*.pdf)"),
    )
    window.show()
    previous_count = window.tab_manager.count()

    window.shortcut_manager.get_shortcut("Ctrl+O").activated.emit()
    assert _wait_until(lambda: window.tab_manager.count() == previous_count + 1)
    view = window.tab_manager.current_view()
    assert view is not None
    assert _wait_until(lambda: view.page().is_pdf_document())
    assert Path(view.url().toLocalFile()).resolve() == pdf_path.resolve()
    local_tab_index = window.tab_manager.index_of(view)
    assert window.tab_bar._tab_bar.tabText(local_tab_index) == pdf_path.name
    assert view.settings().testAttribute(QWebEngineSettings.WebAttribute.PdfViewerEnabled)
    assert view.settings().testAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled)
    assert view.page().profile().isOffTheRecord()
    assert window._session_manager is None
    assert not window.shortcut_manager.get_shortcut("Ctrl+F").isEnabled()

    settings = window.open_settings()
    settings.sidebar.setCurrentRow(4)
    settings.pdf_handling.setCurrentIndex(1)
    assert store.value("pdf/open_in_browser", True, type=bool) is False
    assert not view.settings().testAttribute(QWebEngineSettings.WebAttribute.PdfViewerEnabled)
    assert not view.settings().testAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled)
    settings.pdf_handling.setCurrentIndex(0)
    assert view.settings().testAttribute(QWebEngineSettings.WebAttribute.PdfViewerEnabled)

    window.tab_manager.create_tab("about:blank", activate=True)
    assert window.shortcut_manager.get_shortcut("Ctrl+F").isEnabled()


def test_open_file_rejects_invalid_pdf_without_creating_a_tab(tmp_path, monkeypatch):
    invalid = tmp_path / "broken.pdf"
    invalid.write_bytes(b"not a PDF document")
    _isolate_window_settings(tmp_path, monkeypatch)
    window = MainWindow(initial_url="about:blank", is_private=True)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_a, **_kw: (str(invalid), ""))
    warnings = []
    monkeypatch.setattr(
        "browser.ui.main_window.QMessageBox.warning",
        lambda *_args: warnings.append(_args[1]),
    )
    count = window.tab_manager.count()

    assert window.open_pdf_file() is None
    assert window.tab_manager.count() == count
    assert warnings == ["Invalid PDF"]


def test_session_restores_existing_local_pdf_in_the_regular_profile(tmp_path, monkeypatch):
    pdf_path = tmp_path / "session document.pdf"
    _make_pdf(pdf_path)
    url = QUrl.fromLocalFile(str(pdf_path)).toString()
    snapshot = SessionSnapshot.create(
        [SessionTab("local-pdf", url, pdf_path.name, 0)], "local-pdf"
    )
    repository = SessionRepository(tmp_path / "Sessions")
    assert repository.save(snapshot)
    manager = SessionManager(repository, app)
    manager.begin_run()

    _isolate_window_settings(tmp_path, monkeypatch)
    window = MainWindow(session_manager=manager, restore_snapshot=snapshot)
    assert window.tab_manager.count() == 1
    view = window.tab_manager.current_view()
    assert view is not None
    assert Path(view.url().toLocalFile()).resolve() == pdf_path.resolve()
    assert view.page().profile() is window._profile


def test_online_pdf_uses_mime_type_without_url_extension_and_download_mode(tmp_path):
    payload = _make_pdf(tmp_path / "source.pdf")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", "inline; filename=from-server.pdf")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    profile = QWebEngineProfile(app)
    try:
        inline_view = WebView(profile=profile)
        inline_view.set_pdf_viewer_enabled(True)
        inline_view.show()
        inline_view.navigate(QUrl(f"http://127.0.0.1:{server.server_port}/opaque-resource"))
        assert _wait_until(lambda: inline_view.page().is_pdf_document())
        assert inline_view.url().path() == "/opaque-resource"
        assert inline_view.settings().testAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled)

        download_requests = []

        def cancel_download(request):
            download_requests.append(request.mimeType())
            request.cancel()

        profile.downloadRequested.connect(cancel_download)
        download_view = WebView(profile=profile)
        download_view.set_pdf_viewer_enabled(False)
        download_view.show()
        download_view.navigate(QUrl(f"http://127.0.0.1:{server.server_port}/download-without-suffix"))
        assert _wait_until(lambda: bool(download_requests))
        assert download_requests[0] == "application/pdf"
        assert not download_view.settings().testAttribute(QWebEngineSettings.WebAttribute.PdfViewerEnabled)
    finally:
        server.shutdown()
        server.server_close()


def test_save_from_open_pdf_uses_existing_profile_download_manager(tmp_path, monkeypatch):
    payload = _make_pdf(tmp_path / "source.pdf")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", "inline; filename=reader-save.pdf")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    settings = _isolate_window_settings(tmp_path, monkeypatch, "download-settings.ini")
    destination = tmp_path / "saved"
    destination.mkdir()
    settings.setValue("downloads/default_directory", str(destination))
    settings.setValue("downloads/ask_before_saving", False)
    settings.setValue("pdf/open_in_browser", True)

    from browser.webengine import download_handler

    monkeypatch.setattr(download_handler, "QSettings", lambda *_args, **_kwargs: settings)
    window = MainWindow(
        initial_url=f"http://127.0.0.1:{server.server_port}/document",
        is_private=True,
    )
    window.show()
    try:
        view = window.tab_manager.current_view()
        assert view is not None
        assert _wait_until(lambda: view.page().is_pdf_document())
        tab_index = window.tab_manager.index_of(view)
        assert window.tab_bar._tab_bar.tabText(tab_index) == "reader-save.pdf"
        view.page().download(view.url())
        assert _wait_until(
            lambda: any(item.status == "Completed" for item in window.download_manager.get_downloads())
        )
        item = next(
            item for item in window.download_manager.get_downloads() if item.status == "Completed"
        )
        saved_path = Path(item.destination)
        assert saved_path.exists()
        assert saved_path.read_bytes() == payload
    finally:
        server.shutdown()
        server.server_close()

