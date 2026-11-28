"""Packaging invariants that do not depend on the working directory."""
from pathlib import Path
import runpy
import tomllib

import pytest
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from browser.utils.paths import resource_path
from browser.utils.constants import APP_VERSION


def test_resources_from_unrelated_unicode_directory(tmp_path, monkeypatch):
    directory = tmp_path / 'LightMq test 日本語'
    directory.mkdir()
    monkeypatch.chdir(directory)
    assert resource_path('ui/themes/dark.qss').read_text(encoding='utf-8')
    assert resource_path('ui/themes/light.qss').read_text(encoding='utf-8')
    app = QApplication.instance() or QApplication([])
    assert not QIcon(str(resource_path('resources/lightmq.ico'))).isNull()


def test_resource_traversal_rejected():
    with pytest.raises(ValueError):
        resource_path('../private.ini')


def test_release_version_is_authoritative():
    root = Path(__file__).resolve().parents[2]
    project = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))
    assert project['tool']['setuptools']['dynamic']['version']['attr'] == 'browser.version.__version__'
    assert APP_VERSION == runpy.run_path(str(root / 'src/browser/version.py'))['__version__']
