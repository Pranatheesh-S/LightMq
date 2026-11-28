"""Generate version metadata, original application icon, and dependency notices."""

from pathlib import Path
import importlib.metadata as metadata
import json
import runpy
import shutil
import sys

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWebEngineCore import qWebEngineChromiumVersion

ROOT = Path(__file__).resolve().parents[2]


def prepare() -> None:
    """Build only generated assets inside the known build directory."""
    build = ROOT / 'build/windows'
    build.mkdir(parents=True, exist_ok=True)
    icon = ROOT / 'src/browser/resources/lightmq.ico'
    icon.parent.mkdir(parents=True, exist_ok=True)
    image = QImage(256, 256, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor('#1967d2'))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(QRectF(8, 8, 240, 240), 56, 56)
    painter.setPen(QPen(QColor('white'), 22, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.drawLine(62, 64, 62, 190)
    painter.drawLine(62, 190, 132, 190)
    painter.drawLine(132, 164, 132, 80)
    painter.drawLine(132, 80, 164, 121)
    painter.drawLine(164, 121, 196, 80)
    painter.drawLine(196, 80, 196, 190)
    painter.end()
    if not image.save(str(icon), 'ICO'):
        raise RuntimeError('Cannot generate application icon')
    notices = build / 'notices'
    notices.mkdir(exist_ok=True)
    inventory = {}
    packages = ['PySide6', 'PySide6_Essentials', 'PySide6_Addons', 'PySide6_WebEngine', 'PySide6_Pdf', 'shiboken6', 'openpyxl', 'et_xmlfile']
    for name in packages:
        dist = metadata.distribution(name)
        inventory[name] = dist.version
        for entry in dist.files or []:
            if any(word in str(entry).lower() for word in ['license', 'licence', 'copying', 'notice', 'credits']):
                source = Path(dist.locate_file(entry))
                if source.is_file():
                    target = notices / name / str(entry).replace('..', '_')
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if not python_license.exists():
        raise RuntimeError('Python license unavailable')
    shutil.copy2(python_license, notices / 'Python-LICENSE.txt')
    for name in ['openpyxl', 'et_xmlfile']:
        dist = metadata.distribution(name)
        (notices / (name + '-metadata.txt')).write_text(dist.read_text('METADATA') or '', encoding='utf-8')
    shutil.copy2(ROOT / 'packaging/windows/THIRD_PARTY.md', notices / 'THIRD_PARTY.md')
    info = dict(version=runpy.run_path(str(ROOT / 'src/browser/version.py'))['__version__'],
                python=sys.version, packages=inventory, chromium=qWebEngineChromiumVersion(),
                pyinstaller=metadata.version('pyinstaller'), signing='unsigned')
    (build / 'build-info.json').write_text(json.dumps(info, indent=2), encoding='utf-8')
    (notices / 'build-info.json').write_text(json.dumps(info, indent=2), encoding='utf-8')


if __name__ == '__main__':
    prepare()
