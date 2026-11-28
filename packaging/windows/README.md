# Windows release engineering

These are **unsigned internal test candidates**, not a production release.
Windows 10/11 x64 is the target; only the current Windows 11 development host
has been exercised. Clean Windows testing and license clearance are mandatory
before public distribution.

## Tool choice

Qt's `pyside6-deploy` wraps Nuitka and supports standalone mode. It requires a
C compiler toolchain, which this host does not have on PATH. PyInstaller 6.22.0
is the primary implementation here: its PySide6/WebEngine hooks collect the Qt
helper, resources, plugins, and translations without a C compiler. Only one
packaging configuration is maintained. Qt's hooks determine the actual layout;
no helper path, sandbox, TLS, GPU, or remote-debugging workaround is applied.

## Build

Use Windows x64 Python **3.12.9**, from the repository root in PowerShell:

```powershell
./packaging/windows/build.ps1
./packaging/windows/build_installer.ps1 -ISCC 'C:\Path\To\Inno Setup 6\ISCC.exe' -Portable
```

Both scripts were executed during Phase 18 (see the verification report for results). The application build used `-SkipInstall` after manually preparing the pinned venv; automatic first-use dependency bootstrap has not been exercised end to end.
The build creates `.build-venv`, installs the pinned dependency set, generates
an original LM icon and notices, and produces `dist/LightMq/LightMq.exe`.
Inno Setup 6.7.4 was used; install its official signed compiler separately.
The script accepts an explicit compiler path and fails clearly when unavailable.
Build logs, version inventory, layout checks, and smoke reports live in
`build/windows`. Rebuilds use PyInstaller's scoped output cleanup; neither
script enumerates user directories for deletion. Do not build from an untrusted
checkout. Pins make versions repeatable, not byte-for-byte reproducible.

`src/browser/version.py` is the single version source read by setuptools,
About, executable metadata, installer compilation, and artifact names.

## Install, launch, uninstall, data

Run `LightMq-Setup-0.1.0-x64.exe`. The installer uses
`%LOCALAPPDATA%\Programs\LightMq`, creates a Start Menu entry, and offers an
optional desktop shortcut. It does not request elevation or register default
file/browser associations. Uninstall through Windows Installed Apps.
The stable Inno AppId reuses the installation for upgrades. Restart Manager
requests closure of files in use; users should close LightMq normally first.
Application binaries are replaced; user data is never removed by setup or
uninstall. No “delete user data” option is supplied.

The existing Qt application identity **LightMq / LightMq Browser** is retained
for data compatibility. On Windows the Qt AppDataLocation normally resolves to
`%APPDATA%\LightMq\LightMq Browser`; profiles are under
`Browser/Profiles/Default`, session JSON under `Sessions`, history/bookmarks in
SQLite, and startup diagnostics under `logs`. QSettings retains the existing
Windows registry preferences. Download files remain in user-selected locations;
download records are currently session-only. No profile migration is required.

The ZIP contains the same standalone directory, using the same normal per-user
data paths. It is **not** an isolated-profile portable mode. Extract completely
before launch. No separately installed Python is required by the bundle.

Quoted URL/PDF/XLSX/HTML/HTM command-line destinations are supported; XLSX uses
the existing native viewer. Multiple instances are possible; no IPC was added.
Use `--release-smoke "C:\Temp\report.json"` for the explicit isolated probe.
Its synthetic temporary profile path is recorded in the report and retained
for inspection. It does not access the normal profile, history, or bookmarks.

## Verification and release gates

The distribution validator checks QtWebEngineProcess, platform/PDF DLLs, ICU,
Chromium resources/locales, Python runtime, QSS, and icon assets. The bundled
smoke probe exercises the window, themes, shared-profile tabs, HTTPS/reload,
DevTools, extension controller availability, XLSX, Incognito isolation, and
temporary preferences. It does not prove extension execution. Qt 6.12's native
enable-state crash remains blocked in source.

Before publication use a fresh Windows 10/11 x64 VM without Python, Qt, source
checkout, or development environment variables. Test installer shortcuts,
HTTPS, multiple tabs/groups, downloads, PDF, XLSX, DevTools, persistent cookies,
history/bookmarks, session restoration, recommendations, themes, TLS and
shutdown. Test 100/125/150% scaling, multiple monitors, GPU/software rendering,
supported HTML5 media, helper termination, and RAM/startup timings. Install an
earlier release with synthetic data, upgrade, uninstall, reinstall, and compare
the same data. Do not substitute a same-version reinstall for a version upgrade.
Record results in release notes; unchecked gates remain unverified.

## Integrity, signing, licensing

SHA256SUMS.txt is generated from actual EXE/ZIP bytes. Verify with
`Get-FileHash -Algorithm SHA256`. No signing certificate is configured. With a
legitimate certificate, sign the application **before** installer compilation,
then sign the installer, verify both using Authenticode/signtool, and regenerate
checksums. SmartScreen may warn on unsigned candidates; no bypass is provided.

Read THIRD_PARTY.md and bundled notices. Current Qt wheels identify commercial
terms; redistribution entitlement has not been established. Obtain license
clearance (including Chromium third-party notices/source obligations where
applicable) before public release. The artifacts contain no personal profiles.
For problems report the version, Windows build, failing action, and redacted
local startup.log; avoid sending cookies, private URLs, or personal documents.
