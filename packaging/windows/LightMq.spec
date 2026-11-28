"""One-directory Windows build; Qt hooks own helper/resource deployment paths."""
from pathlib import Path
import runpy
from PyInstaller.utils.win32.versioninfo import VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable, StringStruct, VarFileInfo, VarStruct

root = Path(SPECPATH).resolve().parents[1]
version = runpy.run_path(str(root / 'src/browser/version.py'))['__version__']
parts = tuple(int(p) for p in version.split('.')) + (0,)
version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=parts, prodvers=parts, mask=0x3f, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0, 0)),
    kids=[StringFileInfo([StringTable('040904B0', [StringStruct(k, v) for k, v in {
        'CompanyName': 'PRANATHEESH S', 'FileDescription': 'LightMq Desktop Web Browser',
        'FileVersion': version, 'ProductName': 'LightMq', 'ProductVersion': version,
        'OriginalFilename': 'LightMq.exe', 'LegalCopyright': 'Copyright 2026 PRANATHEESH S'
    }.items()])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])])
datas = [(str(root / 'src/browser/ui/themes'), 'browser/ui/themes'),
         (str(root / 'src/browser/resources'), 'browser/resources'),
         (str(root / 'build/windows/notices'), 'notices'),
         (str(root / 'LICENSE'), '.')]
a = Analysis([str(root / 'packaging/windows/launcher.py')], pathex=[str(root / 'src')],
             datas=datas, binaries=[], hiddenimports=['browser.release_smoke'],
             excludes=['PyQt5', 'PyQt6', 'PySide2', 'pytest', 'numpy', 'pandas', 'tkinter'],
             hookspath=[], runtime_hooks=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='LightMq', debug=False,
          strip=False, upx=False, console=False, version=version_info,
          icon=str(root / 'src/browser/resources/lightmq.ico'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='LightMq')
