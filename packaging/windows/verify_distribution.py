"""Check actual PyInstaller Qt layout and fail on missing runtime assets."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]


def verify() -> None:
    """Do not move helper paths: the PyInstaller Qt hooks configure them."""
    dist = ROOT / 'dist/LightMq'
    required = ['LightMq.exe', 'QtWebEngineProcess.exe', 'qwindows.dll',
                'Qt6WebEngineCore.dll', 'Qt6Pdf.dll', 'icudtl.dat',
                'qtwebengine_resources.pak', 'en-US.pak', 'python312.dll',
                'light.qss', 'dark.qss', 'lightmq.ico']
    files = [p for p in dist.rglob('*') if p.is_file()]
    found = {name: [str(p.relative_to(dist)) for p in files if p.name == name] for name in required}
    missing = [name for name, paths in found.items() if not paths]
    if missing:
        raise RuntimeError(f'Missing runtime components: {missing}')
    for path in files:
        if path.suffix.lower() in {'.sqlite3', '.db', '.ini'} or path.name in {'Cookies', 'Login Data', '.env'}:
            raise RuntimeError(f'Unexpected user data in distribution: {path.name}')
    (ROOT / 'build/windows/distribution.json').write_text(json.dumps(dict(files=found, bytes=sum(p.stat().st_size for p in files)), indent=2), encoding='utf-8')
    print('Distribution runtime files verified')


if __name__ == '__main__':
    verify()
