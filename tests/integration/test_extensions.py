"""Live local-extension tests using isolated Qt profiles and a local HTTP server."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import uuid
import zipfile
from urllib.parse import quote

from PySide6.QtCore import QEventLoop, QSettings, QTimer, QUrl
from PySide6.QtWebEngineCore import QWebEngineProfile
from PySide6.QtWidgets import QApplication

from browser.features.extensions.extension_controller import (
    ENABLED_STATES_KEY,
    ExtensionController,
)
from browser.features.extensions.package_inspector import inspect_extension_package
from browser.webengine.web_view import WebView
from browser.ui.dialogs.extensions_dialog import ExtensionsDialog


app = QApplication.instance() or QApplication(sys.argv)
FIXTURE = Path(__file__).parents[1] / "fixtures" / "extensions" / "simple_mv3"


def _saved_state(settings, extension_id):
    key = f"{ENABLED_STATES_KEY}/{quote(extension_id, safe='')}"
    if not settings.contains(key):
        return None
    return settings.value(key, False, type=bool)


class _PageHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"<!doctype html><html><head><title>Extension test</title></head><body>page</body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format, *_args):
        return


def _profile(tmp_path, name=None):
    app = QApplication.instance()
    assert app is not None
    root = tmp_path / "profile"
    profile = QWebEngineProfile(name or f"ExtTest-{uuid.uuid4().hex}", app)
    profile.setPersistentStoragePath(str(root / "storage"))
    profile.setCachePath(str(root / "cache"))
    return profile


def _wait_for_signal(signal, start, timeout_ms=30000):
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    result = []

    def finish(*args):
        result.append(args)
        loop.quit()

    signal.connect(finish)
    try:
        assert start()
        if not result:
            timer.timeout.connect(loop.quit)
            timer.start(timeout_ms)
            loop.exec()
        assert result, f"Qt signal did not arrive within {timeout_ms} ms"
        return result[0]
    finally:
        timer.stop()
        signal.disconnect(finish)


def _wait_for_load(view, navigate):
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    result = []

    def finish(success):
        result.append(success)
        loop.quit()

    view.loadFinished.connect(finish)
    try:
        navigate()
        timer.timeout.connect(loop.quit)
        timer.start(15000)
        if not result:
            loop.exec()
        assert result, "WebEngine page load did not finish within 15 seconds"
        assert result[0], "WebEngine page failed to load"
    finally:
        timer.stop()
        view.loadFinished.disconnect(finish)


def _read_js(page, script):
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    values = []
    page.runJavaScript(script, lambda value: (values.append(value), loop.quit()))
    timer.timeout.connect(loop.quit)
    timer.start(5000)
    if not values:
        loop.exec()
    timer.stop()
    assert values, "JavaScript evaluation timed out"
    return values[0]


def test_local_mv3_install_stays_disabled_safely_across_tabs(tmp_path):
    """Verify install, safe enable rejection, and shared profile behavior."""
    profile = _profile(tmp_path)
    settings = QSettings(str(tmp_path / "extension-settings.ini"), QSettings.Format.IniFormat)
    controller = ExtensionController(profile, settings)
    package = inspect_extension_package(FIXTURE)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _PageHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    url = QUrl(f"http://127.0.0.1:{server.server_port}/")
    views = []

    try:
        installed = _wait_for_signal(
            controller.operation_finished,
            lambda: controller.install(package, enable_after=False),
        )
        assert installed[0] == "install"
        assert installed[3] is True
        extension = next(
            item for item in controller.user_extensions()
            if item.name() == package.name
        )
        extension_id = extension.id()
        assert extension.isInstalled() and extension.isLoaded()
        assert not controller.is_enabled(extension_id)
        assert controller.open_popup_url(extension_id) is None
        assert controller.is_user_installed(extension)
        assert _saved_state(settings, extension_id) is None
        diagnostics = controller.diagnostics(extension_id)
        assert diagnostics is not None
        assert diagnostics.manifest_version == 3
        assert diagnostics.compatibility.status.value == "Limited Compatibility"
        assert diagnostics.compatibility.pyside_version
        assert diagnostics.compatibility.qt_version
        assert diagnostics.compatibility.chromium_version != "Unknown"
        assert any("cannot be enabled safely" in result for _name, result in diagnostics.runtime_checks)

        # Enabling is explicitly blocked before entering Qt's crashing setter.
        results = []
        controller.operation_finished.connect(lambda *args: results.append(args))
        assert not controller.set_enabled(extension_id, True)
        assert not controller.set_enabled(extension_id, True, user_approved=True)
        controller.operation_finished.disconnect()
        assert len(results) == 2
        assert "approval is required" in results[0][2]
        assert "crashes natively" in results[1][2]
        assert not controller.is_enabled(extension_id)
        assert controller.open_popup_url(extension_id) is None

        # Two pages using the same persistent profile share the installed extension.
        views = [WebView(profile=profile) for _ in range(2)]
        for view in views:
            view.show()
            _wait_for_load(view, lambda: view.setUrl(url))
            assert _read_js(
                view.page(), "document.documentElement.dataset.lightmqExtension || ''"
            ) == ""

        for view in views:
            _wait_for_load(view, view.reload)
            assert _read_js(
                view.page(), "document.documentElement.dataset.lightmqExtension || ''"
            ) == ""
    finally:
        for view in views:
            view.close()
            view.deleteLater()
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=3)
        QApplication.processEvents()


def test_old_enable_preferences_do_not_activate_extensions(tmp_path):
    """Ignore legacy approval flags while the native Qt setter is unsafe."""
    profile = _profile(tmp_path)
    settings = QSettings(str(tmp_path / "restore-settings.ini"), QSettings.Format.IniFormat)
    controller = ExtensionController(profile, settings)
    package = inspect_extension_package(FIXTURE)
    installed = _wait_for_signal(
        controller.operation_finished,
        lambda: controller.install(package, enable_after=False),
    )
    assert installed[3] is True
    extension_id = next(
        extension.id() for extension in controller.user_extensions()
        if extension.name() == package.name
    )

    # A value written by an earlier build must not trigger the crashing setter.
    key = f"{ENABLED_STATES_KEY}/{quote(extension_id, safe='')}"
    settings.setValue(key, True)
    settings.sync()
    restored_controller = ExtensionController(profile, settings)
    assert not restored_controller.is_enabled(extension_id)

    server = ThreadingHTTPServer(("127.0.0.1", 0), _PageHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    view = WebView(profile=profile)
    try:
        view.show()
        _wait_for_load(view, lambda: view.setUrl(QUrl(f"http://127.0.0.1:{server.server_port}/")))
        assert _read_js(
            view.page(), "document.documentElement.dataset.lightmqExtension || ''"
        ) == ""
    finally:
        view.close()
        view.deleteLater()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        QApplication.processEvents()


def test_installed_extension_can_be_uninstalled(tmp_path):
    """Qt removes a persistent install and LightMq clears stale preferences."""
    profile = _profile(tmp_path)
    settings = QSettings(str(tmp_path / "uninstall-settings.ini"), QSettings.Format.IniFormat)
    controller = ExtensionController(profile, settings)
    package = inspect_extension_package(FIXTURE)
    installed = _wait_for_signal(
        controller.operation_finished,
        lambda: controller.install(package, enable_after=False),
    )
    assert installed[3] is True
    extension_id = next(
        extension.id() for extension in controller.user_extensions()
        if extension.name() == package.name
    )
    key = f"{ENABLED_STATES_KEY}/{quote(extension_id, safe='')}"
    settings.setValue(key, True)
    settings.sync()
    removed = _wait_for_signal(
        controller.operation_finished,
        lambda: controller.uninstall(extension_id),
    )
    assert removed[0] == "uninstall" and removed[3] is True, removed[2]
    assert controller.extension(extension_id) is None
    assert _saved_state(settings, extension_id) is None


def test_duplicate_manifest_install_is_rejected_before_qt_creates_second_copy(tmp_path):
    """Avoid Qt's documented duplicate install behavior for identical packages."""
    profile = _profile(tmp_path)
    settings = QSettings(str(tmp_path / "duplicate-settings.ini"), QSettings.Format.IniFormat)
    controller = ExtensionController(profile, settings)
    package = inspect_extension_package(FIXTURE)
    installed = _wait_for_signal(
        controller.operation_finished,
        lambda: controller.install(package, enable_after=False),
    )
    assert installed[3] is True
    before = len(controller.user_extensions())
    outcomes = []
    controller.operation_finished.connect(lambda *args: outcomes.append(args))
    try:
        assert not controller.install(package, enable_after=False)
    finally:
        controller.operation_finished.disconnect()
    assert len(controller.user_extensions()) == before
    assert outcomes and "already installed" in outcomes[-1][2]
    assert not outcomes[-1][3]


def test_extensions_dialog_search_permission_analysis_and_runtime_diagnostics(tmp_path):
    """Render real installed metadata without invoking the unsafe enabled setter."""
    profile = _profile(tmp_path)
    settings = QSettings(str(tmp_path / "dialog-settings.ini"), QSettings.Format.IniFormat)
    controller = ExtensionController(profile, settings)
    package = inspect_extension_package(FIXTURE)
    installed = _wait_for_signal(
        controller.operation_finished,
        lambda: controller.install(package, enable_after=False),
    )
    assert installed[3] is True
    dialog = ExtensionsDialog(controller)
    try:
        assert dialog.extension_list.count() == 1
        assert "Limited Compatibility" in dialog.compatibility_label.text()
        assert "storage" in dialog.permissions_label.text()
        diagnostics = controller.diagnostics(controller.user_extensions()[0].id())
        assert diagnostics is not None
        assert "cannot be enabled safely" in dict(diagnostics.runtime_checks)[
            "Content script execution"
        ]
        dialog.search_input.setText("not installed")
        assert dialog.extension_list.count() == 0
        dialog.search_input.clear()
        assert dialog.extension_list.count() == 1
    finally:
        dialog.close()
        dialog.deleteLater()
        QApplication.processEvents()


def test_installed_extension_persists_with_its_profile(tmp_path):
    """An installed package reloads from Qt's profile-managed extension store."""
    profile_name = f"ExtPersist-{uuid.uuid4().hex}"
    storage = tmp_path / "profile" / "storage"
    cache = tmp_path / "profile" / "cache"
    storage.mkdir(parents=True)
    cache.mkdir(parents=True)
    probe = r'''
import json, sys
from pathlib import Path
from PySide6.QtCore import QSettings, QTimer, QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from browser.features.extensions.extension_controller import ExtensionController

mode, profile_name, storage, cache, package, extension_name = sys.argv[1:]
app = QApplication([])
profile = QWebEngineProfile(profile_name, app)
profile.setPersistentStoragePath(storage)
profile.setCachePath(cache)
settings = QSettings(str(Path(storage).parent / "extension-settings.ini"), QSettings.Format.IniFormat)
controller = ExtensionController(profile, settings)
manager = controller.manager
found = False

def report(info):
    global found
    if info.name() == extension_name:
        found = True
        print(json.dumps({"name": info.name(), "installed": info.isInstalled(),
                          "loaded": info.isLoaded(), "enabled": info.isEnabled(),
                          "error": info.error(), "path": info.path()}), flush=True)
        app.quit()

if mode == "install":
    manager.installFinished.connect(report)
    QTimer.singleShot(30000, app.quit)
    manager.installExtension(package)
else:
    manager.loadFinished.connect(report)
    infos = manager.extensions()
    for info in infos:
        report(info)
    matches = [info for info in infos if info.name() == extension_name]
    if matches:
        report(matches[0])
    else:
        page = QWebEnginePage(profile)
        page.load(QUrl("about:blank"))
        QTimer.singleShot(10000, app.quit)
        app.exec()
        page.deleteLater()
        sys.exit(0 if found else 2)
if mode == "install":
    app.exec()
'''
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    project_root = Path(__file__).resolve().parents[2]
    environment["PYTHONPATH"] = str(project_root / "src")
    common = [profile_name, str(storage), str(cache), str(FIXTURE), "LightMq Local Test Extension"]
    installed = subprocess.run(
        [sys.executable, "-c", probe, "install", *common],
        capture_output=True,
        text=True,
        timeout=40,
        env=environment,
        cwd=project_root,
    )
    assert installed.returncode == 0, installed.stderr
    installed_record = next(
        record for line in installed.stdout.splitlines() if line.startswith("{")
        for record in [json.loads(line)] if record.get("name") == "LightMq Local Test Extension"
    )
    assert installed_record["installed"] and installed_record["loaded"]
    assert not installed_record["enabled"]

    restored = subprocess.run(
        [sys.executable, "-c", probe, "check", *common],
        capture_output=True,
        text=True,
        timeout=40,
        env=environment,
        cwd=project_root,
    )
    assert restored.returncode == 0, restored.stderr or restored.stdout
    restored_record = next(
        record for line in restored.stdout.splitlines() if line.startswith("{")
        for record in [json.loads(line)] if record.get("name") == "LightMq Local Test Extension"
    )
    assert restored_record["installed"] and restored_record["loaded"]
    assert not restored_record["enabled"]
    assert Path(restored_record["path"]).exists()


def test_profile_shares_controller_and_incognito_is_rejected(tmp_path):
    """A profile gets one manager; private profiles cannot instantiate one."""
    profile = _profile(tmp_path / "regular")
    settings = QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat)
    first = ExtensionController.shared_for_profile(profile, settings)
    second = ExtensionController.shared_for_profile(profile, settings)
    assert first is second
    assert first.manager is profile.extensionManager()

    private = QWebEngineProfile(QApplication.instance())
    assert private.isOffTheRecord()
    try:
        try:
            ExtensionController(private, settings)
        except ValueError as error:
            assert "Incognito" in str(error)
        else:
            raise AssertionError("Extensions must not be enabled in an off-the-record profile.")
    finally:
        private.deleteLater()
        QApplication.processEvents()


def test_developer_mode_load_is_temporary_and_starts_disabled(tmp_path):
    """Unpacked developer loads use Qt loadExtension and never persist approval."""
    profile = _profile(tmp_path)
    settings = QSettings(str(tmp_path / "developer-settings.ini"), QSettings.Format.IniFormat)
    controller = ExtensionController(profile, settings)
    package = inspect_extension_package(FIXTURE)

    loaded = _wait_for_signal(
        controller.operation_finished,
        lambda: controller.load_unpacked(package, enable_after=False),
    )

    assert loaded[0] == "load"
    assert loaded[3] is True
    extension_id = loaded[1]
    extension = controller.extension(extension_id)
    assert extension is not None and extension.isLoaded()
    assert not extension.isInstalled() and not controller.is_enabled(extension_id)
    assert controller.is_temporary(extension)
    assert not any(
        key.startswith(ENABLED_STATES_KEY + "/") for key in settings.allKeys()
    )


def test_zip_package_can_be_installed_without_enabling(tmp_path):
    """Qt receives a validated ZIP and keeps its persistent install disabled."""
    profile = _profile(tmp_path)
    settings = QSettings(str(tmp_path / "zip-settings.ini"), QSettings.Format.IniFormat)
    controller = ExtensionController(profile, settings)
    archive = tmp_path / "simple_mv3.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as package_zip:
        for source in FIXTURE.iterdir():
            package_zip.write(source, source.name)
    package = inspect_extension_package(archive)

    installed = _wait_for_signal(
        controller.operation_finished,
        lambda: controller.install(package, enable_after=False),
    )

    assert installed[0] == "install"
    assert installed[3] is True
    extension = next(item for item in controller.user_extensions() if item.name() == package.name)
    assert extension.isInstalled() and not controller.is_enabled(extension.id())
