"""Cross-process check for session and persistent cookie restoration."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import subprocess
import sys
from threading import Thread


def test_cookies_survive_a_controlled_webengine_restart(tmp_path):
    """Both ordinary and session cookies return from the same profile after restart."""
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            if self.path == "/set":
                self.send_header("Set-Cookie", "persistent_test=kept; Max-Age=3600; Path=/")
                self.send_header("Set-Cookie", "session_test=kept; Path=/")
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<!doctype html><title>cookie test</title>")

        def log_message(self, _format, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server_thread = Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    root = tmp_path / "profile"
    storage = root / "Storage"
    cache = root / "Cache"
    storage.mkdir(parents=True)
    cache.mkdir(parents=True)
    script = r'''
import sys
from PySide6.QtCore import QCoreApplication, QEvent, QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile

app = QApplication([])
profile = QWebEngineProfile("Default", app)
profile.setPersistentStoragePath(sys.argv[2])
profile.setCachePath(sys.argv[3])
profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
page = QWebEnginePage(profile)
def loaded(_ok):
    page.runJavaScript("document.cookie", lambda value: (print(value or ""), app.quit()))
page.loadFinished.connect(loaded)
page.load(QUrl(sys.argv[1]))
app.exec()
page.triggerAction(QWebEnginePage.WebAction.Stop)
page.deleteLater()
QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
profile.deleteLater()
QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
'''
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    try:
        first = subprocess.run(
            [
                sys.executable,
                "-c",
                script,
                f"http://127.0.0.1:{server.server_port}/set",
                str(storage),
                str(cache),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            env=environment,
            cwd=Path(__file__).resolve().parents[2],
        )
        assert first.returncode == 0, first.stderr
        assert "persistent_test=kept" in first.stdout
        assert "session_test=kept" in first.stdout

        second = subprocess.run(
            [
                sys.executable,
                "-c",
                script,
                f"http://127.0.0.1:{server.server_port}/check",
                str(storage),
                str(cache),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            env=environment,
            cwd=Path(__file__).resolve().parents[2],
        )
        assert second.returncode == 0, second.stderr
        assert "persistent_test=kept" in second.stdout
        assert "session_test=kept" in second.stdout
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)
