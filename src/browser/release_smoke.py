"""Opt-in packaged smoke probe, isolated from real profiles and preferences."""

import json
from pathlib import Path
import tempfile
import time


def run(report_file: str) -> int:
    """Exercise the shipped UI and WebEngine with temporary synthetic data."""
    from PySide6.QtCore import QEventLoop, QSettings, QTimer, QUrl
    from PySide6.QtGui import QIcon, QPainter, QPdfWriter
    from PySide6.QtWidgets import QApplication
    from browser.utils.paths import resource_path
    from browser.webengine.web_profile import WebProfileManager
    from browser.features.history.history_manager import HistoryManager
    from browser.features.bookmarks.bookmark_manager import BookmarkManager
    from browser.ui.main_window import MainWindow
    from browser.version import __version__

    started = time.perf_counter()
    report = {'version': __version__, 'checks': {}, 'limitations': ['Not a clean Windows test', 'No extension execution: native Qt setter blocked', 'No hardware/display/media verification']}
    checks = report['checks']
    app = QApplication.instance() or QApplication([])
    app.setApplicationName('LightMq Browser')
    app.setOrganizationName('LightMq')
    app.setWindowIcon(QIcon(str(resource_path('resources/lightmq.ico'))))
    app.setQuitOnLastWindowClosed(False)

    def wait(milliseconds: int) -> None:
        loop = QEventLoop()
        QTimer.singleShot(milliseconds, loop.quit)
        loop.exec()

    # Keep files until process exit: Qt may still own helper/profile handles.
    root = Path(tempfile.mkdtemp(prefix='LightMq-release-smoke-'))
    report['synthetic_data_directory'] = str(root)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(root / 'settings'))
    WebProfileManager.data_root = classmethod(lambda cls: root / 'profile')
    HistoryManager._instance = HistoryManager(root / 'history.sqlite3')
    BookmarkManager._instance = BookmarkManager(root / 'bookmarks.sqlite3')
    window = None
    try:
        window = MainWindow(initial_url='lightmq://newtab')
        window.show()
        wait(3000)
        checks['window'] = window.isVisible()
        checks['theme_assets'] = all(resource_path('ui/themes/' + p + '.qss').is_file() for p in ['light', 'dark'])
        checks['icon'] = not app.windowIcon().isNull()
        from browser.utils.startup_diagnostics import missing_runtime_components
        checks['runtime_paths'] = not missing_runtime_components()
        window._browser_settings.set('appearance/theme', 'dark')
        checks['theme_applied'] = bool(app.styleSheet())
        first = window.web_view
        view = window.new_tab()
        checks['tabs_shared_profile'] = first.page().profile() is view.page().profile()
        loaded = []
        view.loadFinished.connect(loaded.append)
        view.load(QUrl('https://example.com'))
        for _ in range(40):
            wait(500)
            if loaded:
                break
        checks['https'] = bool(loaded and loaded[-1] and view.url().scheme() == 'https')
        loaded.clear()
        view.reload()
        for _ in range(30):
            wait(500)
            if loaded:
                break
        checks['reload'] = bool(loaded and loaded[-1])
        window.devtools_manager.open()
        wait(1500)
        checks['devtools'] = window.devtools_manager.is_open()
        checks['extension_manager'] = window._extension_controller is not None
        writer = QPdfWriter(str(root / 'sample.pdf'))
        painter = QPainter(writer)
        painter.drawText(100, 100, 'Synthetic release PDF')
        painter.end()
        del writer
        pdf_view = window.open_local_document(str(root / 'sample.pdf'))
        checks['pdf_open'] = pdf_view is not None
        wait(1000)
        from openpyxl import Workbook
        workbook = Workbook()
        workbook.active['A1'] = 'Synthetic release check'
        workbook.save(root / 'sample.xlsx')
        checks['xlsx'] = window.open_local_document(str(root / 'sample.xlsx')) is not None
        private = MainWindow(initial_url='lightmq://incognito/', is_private=True)
        checks['incognito'] = private._profile.isOffTheRecord() and private._profile is not window._profile
        private.close()
        store = window._settings
        store.setValue('release/synthetic', 'preserved')
        store.sync()
        checks['settings_persistence'] = QSettings('LightMq', 'LightMq Browser').value('release/synthetic') == 'preserved'
        checks['profile_outside_installation'] = str(root) in window._profile.persistentStoragePath()
        report['seconds_to_checks'] = round(time.perf_counter() - started, 3)
    except Exception as error:
        report['error_type'] = type(error).__name__
    finally:
        for item in list(MainWindow._all_windows):
            item.close()
        wait(500)
        Path(report_file).resolve().write_text(json.dumps(report, indent=2), encoding='utf-8')
    return 0 if checks and all(checks.values()) and 'error_type' not in report else 1
