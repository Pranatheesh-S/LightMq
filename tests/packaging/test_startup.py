"""Missing-component diagnostics must work before starting Chromium."""
from browser.utils import startup_diagnostics


def test_missing_qt_components_are_reported_without_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(startup_diagnostics.QLibraryInfo, 'path', lambda kind: str(tmp_path))
    missing = startup_diagnostics.missing_runtime_components()
    assert 'WebEngine helper' in missing
    assert 'Chromium resources' in missing
    assert 'Chromium ICU data' in missing
    assert all(str(tmp_path) not in label for label in missing)
    (tmp_path / 'resources').mkdir()
    (tmp_path / 'QtWebEngineProcess.exe').touch()
    (tmp_path / 'resources/qtwebengine_resources.pak').touch()
    (tmp_path / 'resources/icudtl.dat').touch()
    assert not startup_diagnostics.missing_runtime_components()
