# LightMq Windows internal candidate

Version and exact runtime inventory: see adjacent build-info.json. SHA256SUMS.txt
contains hashes of the actual versioned EXE and ZIP. The build is unsigned.

Phase 18 supplies a one-directory PyInstaller application with embedded Python,
Qt WebEngine/PDF, openpyxl, QSS assets, original LM icon, and dependency notices.
The Inno Setup installer supports per-user installation, Start Menu entry,
optional desktop shortcut, binary replacement using a stable AppId, and
uninstall with browsing data preserved. Quoted local PDF/XLSX/HTML/HTM inputs
are supported. ZIP builds use the same per-user data paths as installed builds.

The packaged isolated probe passed on the Windows 11 development host: UI,
QSS/icon, HTTPS/reload, shared-profile tabs, DevTools, extension controller,
XLSX, Incognito isolation, temporary QSettings persistence. See the final
verification report for full results and measurements. This is not a clean
Windows test and does not establish extension execution compatibility.

Release gates still open: clean Windows without Python/Qt/source; actual
earlier-version upgrade; GPU/media/DPI/multiple monitors; cold/warm startup
and idle/multiple-tab RAM benchmarks; code signing; complete license clearance.
The installed Qt 6.12 wheels carry commercial notices; redistribution rights
have not been established. Chromium notice/source compliance must be reviewed.
Do not publish this candidate as a release-ready browser.

Known source limitations: native Qt extension enabling remains blocked due to
a reproduced access violation, so enabled-state restoration and action/content/
background execution are not supported. Chrome Web Store package installation
is unsupported. Download records are session-only. No default-browser/file
association takeover, single-instance IPC, or automatic update service is added.

Final verification: installer/Start Menu/installed probe/reinstall/uninstall and
synthetic-data preservation passed on the development host. Final archive and
SHA-256 checks passed. See verification-report.md for exact sizes and limits.
