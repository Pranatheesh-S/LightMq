# Phase 18 verification — 2026-11-28

Status: **unsigned internal candidate; not cleared for public release**.

## Runtime and tools

- Python 3.12.9 x64; PySide6/Qt 6.12.0; Chromium 140.0.7339.225.
- PyInstaller 6.22.0, hooks-contrib 2026.10, Inno Setup 6.7.4.
- PyInstaller standalone selected after a working WebEngine proof; no C compiler
  was available on PATH for Qt's preferred Nuitka-based deployment mechanism.
- Publisher PRANATHEESH S and version 0.1.0 match project metadata.

## Artifacts

- Executable: `C:\Users\Pranatheesh\Desktop\Mqueen\LightMq\dist\LightMq\LightMq.exe`
- Installer: `C:\Users\Pranatheesh\Desktop\Mqueen\LightMq\release\LightMq-Setup-0.1.0-x64.exe`
- ZIP: `C:\Users\Pranatheesh\Desktop\Mqueen\LightMq\release\LightMq-Portable-0.1.0-x64.zip`
- Complete standalone application: 594,739,807 bytes (567.19 MiB).
- LightMq-Setup-0.1.0-x64.exe: 197,198,557 bytes (188.06 MiB)
- LightMq-Portable-0.1.0-x64.zip: 224,923,114 bytes (214.50 MiB)

SHA256SUMS.txt was regenerated from these actual files and independently checked.
The ZIP passed CRC/integrity validation. Both artifacts are unsigned. A preceding
candidate was also extracted and launched from a Unicode path containing spaces
with an unrelated CWD; all probe checks passed. The final bundle's additional
runtime-path diagnostics passed the standalone and installed probes.

## Executed checks

- `build.ps1 -SkipInstall` succeeded using the prepared pinned isolated venv.
- `build_installer.ps1 -ISCC ./build/windows/inno/ISCC.exe -Portable` succeeded.
- `verify_installer.ps1 -Installer ./release/LightMq-Setup-0.1.0-x64.exe` succeeded.
- Full source regression suite: **187 passed in 202.34 seconds** before the final
  missing-component diagnostic addition. Focused packaging tests after that
  addition: **4 passed**. Compileall, PowerShell syntax checks and diff checks passed.
- Final packaged probe: all 15 checks passed, including window,
  QSS/icon, runtime helper/resource paths, shared-profile tabs, HTTPS/reload,
  DevTools, extension controller, PDF opening, XLSX, Incognito isolation,
  temporary preference persistence and profile location outside installation.
- Probe elapsed 7.681 seconds measures the test sequence,
  **not** cold/warm startup time.
- Installer verification: installed, start_menu, installed_probe, same_version_reinstall, data_survived_reinstall, uninstall, shortcut_removed, data_survived_uninstall.
  The synthetic data sentinel was outside the install directory. The test refused
  an existing registered installation, used a temporary target and test Start
  Menu group, and left no registered installation or test shortcut after uninstall.
- Bundled WebEngine helpers were observed running from the distribution and
  terminating after its probe; no sandbox, certificate or GPU bypass was added.
- Pytest emitted non-fatal network/SSL/download shutdown diagnostics. PyInstaller
  warned about an absent unused QML assetdownloader plugin; Widgets/WebEngine
  probes passed. Neither warning was hidden by disabling security features.

## Files created or changed for Phase 18

- `packaging/windows/`: LightMq.spec, build.ps1, build_installer.ps1,
  installer.iss, launcher.py, prepare.py, requirements-build.txt,
  verify_distribution.py, verify_installer.ps1, README.md, THIRD_PARTY.md,
  release-notes.md and this verification report.
- New `src/browser/version.py`, `src/browser/release_smoke.py`,
  `src/browser/utils/startup_diagnostics.py`, `src/browser/resources/lightmq.ico`.
- Updated main.py, ui/main_window.py (reuse local document opener),
  ui/theme_manager.py, utils/paths.py, utils/constants.py, pyproject.toml,
  README.md and .gitignore. Earlier dirty Phase 9–17 changes were preserved.
- Added tests/packaging/test_resource_paths.py and test_startup.py.
- Updated canonical project memory status, backlog, decisions and session log.

## Remaining release gates

- No clean Windows 10/11 VM without Python/Qt/source was available. Host checks
  do not satisfy this mandatory acceptance criterion.
- Same-version reinstall is verified; an actual earlier-version upgrade with
  synthetic history/bookmarks/cookies/session data remains untested.
- Optional desktop shortcut selection was configured but not exercised.
- Hardware/media/DPI/multiple monitors and cold/warm startup, idle/multiple-tab
  RAM and shutdown benchmarks were not performed.
- Qt wheels include commercial notices; redistribution entitlement is unverified.
  Exact matching Chromium third-party notices/source compliance remain incomplete.
- No signing certificate configured. Public distribution is blocked on license
  clearance, clean-machine testing, upgrade verification and release review.
- Existing extension native enabling crash remains blocked; enabled-state
  persistence/extension execution and Chrome Web Store package downloads are
  unsupported. Download records are session-only. ZIP uses normal user-data
  paths; no isolated portable profile, default-app association or IPC was added.

Next recommended work: validate this candidate in a disposable clean Windows VM,
exercise genuine upgrade/uninstall persistence, resolve licensing and signing,
then consider publishing a versioned release. Phase 18 acceptance is partial.
