# LightMq

A customizable, developer-focused desktop web browser built with **Python**, **PySide6**, and **Qt WebEngine (Chromium)**.

---

## Project Overview

**LightMq** is an open-source desktop browser designed for developers, power users, and privacy-conscious web workflows. It separates browser rendering, presentation, and developer tooling into clean, modular layers.

### Rendering Architecture
LightMq uses **Qt WebEngine**, which embeds the **Chromium** browser engine and Google V8 JavaScript runtime:
- **Multi-Process Architecture**: Web pages render in isolated Chromium worker processes for stability and sandboxing.
- **Modern Web Standards**: Native rendering of HTML5, CSS3, modern ECMAScript, WebGL, and media.
- **Genuine Chromium Developer Tools**: Built-in inspector (`devtools://devtools/bundled/inspector.html`) powered by `QWebEnginePage.setDevToolsPage()`.

---

## Current Status: Multi-Tab Browser with Built-in Chromium DevTools (Phase 2)

The browser is currently at the **Multi-Tab Browser** stage. Full tab lifecycle management (creation, closing, switching, reordering, independent navigation states, background tab isolation), URL navigation, Chromium rendering, and dynamic Chromium Developer Tools inspection across active tabs are fully functional and verified.

---

## Verified Engine Specifications

The browser engine runs on the latest stable PySide6 and Qt WebEngine distribution available:

| Subsystem | Verified Version | Notes |
| :--- | :--- | :--- |
| **Python Runtime** | `3.12.9` (64-bit) | Recommended `>=3.10` |
| **PySide6 Framework** | `6.12.0` | Official Qt 6 Python bindings |
| **Qt Core Library** | `6.12.0` | High-performance C++ application framework |
| **Bundled Chromium** | `140.0.0.0` | High-performance multi-process rendering engine |
| **PySide6-WebEngine** | `6.12.0.140` | Qt WebEngine binary package with bundled Chromium |
| **Chromium DevTools** | Bundled v140 | Native Elements, Console, Network, and Sources panels |

### Diagnostic Commands
You can inspect the engine and runtime versions directly from the command line:

```powershell
# Display short version summary
python src/browser/main.py --version

# Display complete engine and environment diagnostics
python src/browser/main.py --diagnostics
```

Alternatively, click the **About** button in the browser toolbar to view the live engine version dialog.

---

## Upstream Chromium Gap Analysis & Security Model

### Understanding the Version Gap
- **Bundled Chromium in Qt WebEngine**: Version **140.0.0.0** (via PySide6 6.12.0)
- **Current Standalone Google Chrome**: Version **158.x**

### Why Does This Gap Exist?
1. **Upstream Chromium Rapid Release Cycle**: Google Chrome releases a new major version every 4 weeks.
2. **Qt Stabilization & Synchronization**: The Qt Company synchronizes Qt WebEngine with specific Chromium LTS (Long Term Support) snapshots. Each snapshot requires stabilizing Chromium's multi-process IPC, GPU process, and network stack against Qt's cross-platform windowing (QPA) and event loop architecture.
3. **Security Backports**: The Qt Company continuously backports upstream Chromium security fixes into supported Qt WebEngine releases without breaking ABI stability.

### Important Engineering Constraints
- **Do Not Replace Qt WebEngine Binaries with Chrome Binaries**: Qt WebEngine is not a standalone Chromium executable; it is compiled with deep C++ hooks into Qt's event loop, graphics pipeline, and type system. Swapping DLLs or binaries will cause immediate ABI crashes.
- **No Fictitious User-Agent Spoofing**: LightMq does not spoof the User-Agent to falsely report a newer Chromium version, as this breaks feature detection on modern websites.
- **Recommended Maintenance Path**: Keep PySide6 and PySide6-WebEngine updated to the latest minor releases using `pip install --upgrade PySide6`.

---

## Features

### Currently Implemented
- [x] **Multiple Tab Management (Phase 2)**:
  - Chrome-style native tab bar positioned above the navigation toolbar (`QTabBar` + `QStackedWidget`).
  - Open new tabs via the `+` button, `Ctrl+T`, or links opening in new windows (`target="_blank"`, `window.open()`).
  - Close tabs via the tab `×` button or `Ctrl+W` shortcut with clean asynchronous `deleteLater()` memory cleanup.
  - Closing the last remaining tab automatically creates a fresh start page tab, preventing an empty UI shell.
  - Tab switching via click or keyboard navigation (`Ctrl+Tab` forward with wrap-around, `Ctrl+Shift+Tab` backward with wrap-around).
  - Tab reordering via drag-and-drop with persistent viewport alignment.
  - Independent navigation and history states: active tab synchronizes the Address Bar, Back/Forward button states, window title, and loading progress.
  - Background tab isolation: background tabs never overwrite the active tab's toolbar, address bar, or window title.
  - Dynamic tab titles and site favicons with automatic text elision.
- [x] **URL Navigation & Normalization**:
  - Address bar with keyboard submission (`Enter`).
  - Automatic `https://` prefixing for domain names (e.g. `example.com` → `https://example.com`).
  - Localhost development URL support (e.g. `localhost:8000` → `http://localhost:8000`).
  - Full URL synchronization upon redirection or navigation (`urlChanged`).
- [x] **Webpage Rendering (Chromium Backend)**:
  - Real webpage loading and rendering powered by `QWebEngineView` and `QWebEnginePage`.
  - Full JavaScript execution and page interaction.
  - Page loading progress bar and status bar indicators.
  - Dynamic window title updates based on active webpage `<title>`.
- [x] **Persistent Browser Profile**:
  - Regular windows and tabs share the named `Default` Qt WebEngine profile, stored under the operating system's application-data directory at `Browser/Profiles/Default/` (`Storage/` and `Cache/` are separate). On Windows with the current app identity, this resolves below `%APPDATA%\LightMq\LightMq Browser\Browser\Profiles\Default\`.
  - `ForcePersistentCookies` saves persistent and session cookies across normal application restarts when the website permits session restoration. This also means session cookies remain on disk until they expire or are explicitly cleared; use **Privacy** or **Clear Browsing Data** to remove them.
  - Qt WebEngine retains supported origin storage in the profile. LightMq does not export or log cookies. This profile is shared by regular browser windows; private-window behavior remains separate.
- [x] **Navigation Controls**:
  - Back (`←`), Forward (`→`), Reload (`↻`), and Stop (`✕`).
  - Dynamic button enabling/disabling linked to page history.
  - Dedicated "Go" navigation button.
- [x] **Chromium Developer Tools (Inspect Element)**:
  - Genuine Chromium DevTools attached via `QWebEnginePage.setDevToolsPage()`.
  - Resizable panel docked on the right side using `QSplitter`.
  - Seamless re-attachment across tab switches: inspecting follows the active tab automatically.
  - Safe detachment when inspected tabs close.
  - Toggle DevTools via `F12` key or the toolbar button.
  - Right-click "Inspect" context menu support.
  - Full access to built-in Elements, Console, Network, and Sources inspector tabs.
  - Crash-proof open/close and tab-switch lifecycle.
- [x] **Engine Diagnostics & About Dialog**:
  - Live About dialog showing exact PySide6, Qt, and Chromium versions.
  - Command-line `--version` and `--diagnostics` flags.
- [x] **Download Manager**:
  - Detects downloads from all tabs through each browser profile's `downloadRequested` signal.
  - Prompts with the server's suggested name and OS Downloads folder; a user-selected existing file requires explicit overwrite confirmation.
  - Preserves the suggested file extension, or infers a missing one from Qt/Python MIME databases, common MIME aliases, structured MIME suffixes, or the source URL.
  - WebEngine saves the original response bytes without converting formats. If a server provides no filename extension, recognized MIME type, or URL suffix, the format cannot be inferred and no extension is guessed.
  - Tracks simultaneous transfers with byte counts, progress, smoothed speed, estimated time, source host, MIME/file type, destination, and state.
  - Provides pause, resume, cancel, open completed file, show containing folder, and remove finished record controls.
  - Shows brief nonmodal popups for started, completed, cancelled, and failed downloads; completed rows show “Completed” with no remaining-time estimate.
  - If a direct top-level download response would replace the current tab with a blank document, LightMq returns to the previous history entry; a tab without prior history shows a short download notice instead.
  - Temporary `target="_blank"` tabs created only to serve a download are closed after the request is accepted, preventing empty tabs from remaining after the transfer.
  - Open from the toolbar or with `Ctrl+J`. `Esc` closes the dialog when it has focus.
  - Regular windows share the normal profile's session download list. Private windows use a separate in-memory list.

- **Browsing History**:
  - Successful HTTP(S) top-level navigations are saved as individual UTC-timestamped visits in SQLite under the operating system's application-data directory. The database persists across tabs, browser restarts, and computer restarts. Qt navigation categories are retained where available (link, typed, form, back/forward, reload, redirect, or other).
  - Each visit is committed once after `loadFinished(True)` and only when its page accepted a main-frame navigation. Redirect chains are represented by the final loaded URL; reloads count as new visits. Failed loads, private-window visits, and internal/non-web schemes are excluded.
  - Search titles and URLs (including domains), filter by today, yesterday, the last 7/30 days, or custom local calendar dates, and page through results. History entries can be opened in the current/new tab, copied, or deleted individually or for an entire site.
  - Clear history for the last hour, 24 hours, 7 days, 30 days, or all time. Ctrl+H opens history; Enter opens and Delete removes a selected visit while the results table has focus; Escape closes the dialog.
  - The history database is local and is never uploaded. Private windows do not write history. Clearing this application history database does **not** clear Chromium's per-tab Back/Forward history, HTTP cache, or cookies.
  - Navigation that does not produce a successful main-frame load (including downloads and some single-page-app `pushState` changes) is not represented as a visit. Favicon URLs are retained when WebEngine reports one; favicon image bytes are not cached by history.

- **New Tab Page**:
  - New tabs and new windows open a built-in LightMq start page instead of navigating to `example.com`. Home uses the configured homepage (Google by default).
  - The page is self-contained and includes a search/address field plus quick links for Google, YouTube, GitHub, and Wikipedia. Typed addresses navigate directly; other text is searched with Google.

- **Session Restoration & Startup**:
  - Regular browser tabs are saved in a versioned JSON snapshot below the operating-system application-data directory in `Sessions/current_session.json`; an atomic recovery copy is kept alongside it. URLs, titles, tab order, and active tab are stored. Cookies remain in the separate Qt WebEngine profile.
  - The **Startup** toolbar button selects **Open a new tab**, **Open a specific homepage**, or **Continue where I left off**. Continue is the default; the homepage is configurable and the Home shortcut navigates there.
  - Session writes are debounced and use Qt atomic file replacement. A separate lifecycle marker distinguishes a clean close from an unclean previous run. When an unclean run has a valid recovery snapshot, LightMq offers **Restore Tabs** or **Start Fresh**.
  - Restoration reloads supported HTTP(S) pages and LightMq's start page in their saved order, with the prior active tab selected. URLs containing user-info or common authentication-token query parameters, and unsupported/internal transient schemes, are excluded from snapshots.
  - Session files are local browsing metadata and may reveal visited URLs. Restoration does not preserve DOM/JavaScript state, form contents, scroll position, complete back/forward history, DevTools state, media playback, or in-progress downloads. Persistent login cookies remain separate and are reused by restored tabs, subject to each website's rules.

- **Privacy & Security**:
  - Open **Privacy** in a regular browser window to inspect cookie metadata, delete one cookie, session cookies, or all cookies, review/reset Qt WebEngine permission decisions, and clear the HTTP cache.
  - Cookie names, domains, paths, expiry, session/persistent status, Secure, and HttpOnly flags are shown; cookie values are never shown or logged. Cookie listing and deletion are asynchronous. Qt emits per-cookie add/remove events but no inventory-finished or delete-all-finished signal, so LightMq reports requests without claiming final completion.
  - Website requests for camera, microphone, screen sharing, mouse lock, desktop notifications, geolocation, clipboard, and local-font access prompt with the requesting origin. Requests are denied by default when unsupported, insecure, stale, or dismissed. Decisions use Qt's profile permission store and its configured persistence policy; LightMq does not create a separate permission database.
  - **Clear Browsing Data** (`Ctrl+Shift+Delete`) supports history ranges of last hour, 24 hours, 7 days, 30 days, and all time. Cookie, HTTP-cache, and saved-permission selections clear the entire selected category regardless of the chosen history time range, and the confirmation dialog states this explicitly.
  - HTTP-cache clearing uses Qt WebEngine's completion signal where available. Clearing LightMq history does not clear cookies, cache, Chromium's visited-link database, or open tabs' Back/Forward lists. Cookie/cache/permission clearing does not remove Local Storage, IndexedDB, downloaded files, or browser settings.
  - These controls operate on the shared regular profile. Cookie persistence is configured as `ForcePersistentCookies`; HTTP caching uses `DiskHttpCache`. Permission decisions retain Qt's configured policy. The existing private-window behavior is unchanged; privacy controls are not exposed there.
  - Qt's profile diagnostics (`python src/browser/main.py --diagnostics`) report profile name, off-the-record status, storage/cache paths, cookie/cache policies, and Qt WebEngine, PySide6, and Chromium versions. They do not expose cookie values.
  - Login restoration depends on each website's cookie and authentication rules. Google may block sign-in in embedded browsers; LightMq does not bypass that restriction or guarantee Google login compatibility.
  - References: [QWebEngineCookieStore](https://doc.qt.io/qtforpython-6/PySide6/QtWebEngineCore/QWebEngineCookieStore.html), [QWebEnginePermission](https://doc.qt.io/qtforpython-6/PySide6/QtWebEngineCore/QWebEnginePermission.html), and [QWebEngineProfile](https://doc.qt.io/qtforpython-6/PySide6/QtWebEngineCore/QWebEngineProfile.html).

### Planned Features (Future Phases)
- [ ] **Bookmarks**: Local SQLite-backed bookmark hierarchy.
- [x] **Session Restoration**: Restore saved regular tabs, order, active tab, startup preferences, and crash recovery choices.
- [ ] **Private Browsing (Incognito)**: Ephemeral in-memory profiles leaving no disk trace.
- [ ] **Ad-Blocking**: Network request interception for tracker and ad filtering.
- [ ] **AI Assistant Sidecar**: Integrated copilot panel for page summarization and search.

### Download Manager Notes

- Download records are session-only and are not written to a database or restored after restarting LightMq.
- Closing a tab does not stop its profile's active transfer. Closing the last browser window exits the application and ends active transfers; their incomplete files are not resumed automatically on the next launch.
- Pausing/resuming uses Qt WebEngine's request API. Resume is available only while the current request remains resumable; interrupted downloads are marked failed/interrupted and are not promised to resume after restart.
- Download choices, transfer, pause/resume, cancellation, and file opening were verified with Qt WebEngine 6.12.0 using a controlled local HTTP download. Opening a file or folder uses the operating system's registered handler and always requires a button click.

---

## Technology Stack

- **Python**: `3.12+` (Minimum `3.10+`)
- **UI Framework**: [PySide6](https://wiki.qt.io/Qt_for_Python) (`>=6.12.0`)
- **Rendering Engine**: [Qt WebEngine](https://doc.qt.io/qtforpython-6/PySide6/QtWebEngineWidgets/index.html) (Chromium 140 backend)
- **Testing**: [pytest](https://docs.pytest.org/)

---

## Keyboard Shortcuts

Shortcuts are registered once per browser window by `ShortcutManager` with window scope, so each command operates on that window's active tab. Standard editing keys such as Ctrl+C, Ctrl+V, Ctrl+X, Ctrl+A, Ctrl+Z, and Ctrl+Y remain available to text inputs and pages.

| Shortcut | Action |
| :--- | :--- |
| `Ctrl+T` / `Ctrl+W` / `Ctrl+Shift+T` | Open tab / close tab / restore recently closed tab (up to 25 URLs per normal window) |
| `Ctrl+N` / `Ctrl+Shift+N` | Open normal window / private window |
| `Ctrl+Tab` / `Ctrl+Shift+Tab` | Next / previous tab, wrapping at the ends |
| `Ctrl+1` … `Ctrl+8` / `Ctrl+9` | Select tab 1–8 / last tab |
| `Ctrl+L` | Focus and select the address bar |
| `Alt+Left` / `Alt+Right` / `Alt+Home` | Back / forward / home |
| `F5` / `Ctrl+R` / `Ctrl+Shift+R` | Reload / reload / reload bypassing cache |
| `Esc` | Stop loading, or close the find bar when it is open |
| `Ctrl+F` | Find text in the active page; Enter and Shift+Enter move through matches |
| `Ctrl+D` / `Ctrl+P` / `Ctrl+S` | Bookmark / print / save active page |
| `Ctrl+H` / `Ctrl+J` / `Ctrl+Shift+Delete` | History / downloads / clear browsing data |
| `Ctrl+Shift+B` | Toggle bookmarks bar (visibility is saved for normal windows) |
| `F11` | Toggle fullscreen, restoring the prior maximized or normal state |
| `Ctrl++` (also `Ctrl+=`) / `Ctrl+-` / `Ctrl+0` | Zoom in / out / reset (25%–500%) |
| `F12` / `Ctrl+Shift+I` | Toggle Chromium Developer Tools |
| `Ctrl+Shift+J` | Open Developer Tools and focus its view |
| `Ctrl+Shift+C` | Invoke Chromium's Inspect Element page action and open Developer Tools |
| `Ctrl+U` | Open the current URL using Chromium's `view-source:` scheme in a new tab |

### Shortcut support and limitations

- Find-in-page uses `QWebEngineView.findText()`. Cache bypass uses Qt WebEngine's `ReloadAndBypassCache` page action.
- Developer Tools are Chromium's bundled inspector attached through `QWebEnginePage.setDevToolsPage()`. Qt WebEngine does not expose commands to select a specific DevTools panel; therefore Ctrl+Shift+J opens and focuses the DevTools view but cannot guarantee switching to the Console panel. Inspect Element relies on Qt's exposed `InspectElement` action.
- Ctrl+U uses Chromium's built-in `view-source:` URL handling. Printing and saving use Qt WebEngine page APIs.
- Recently closed tabs keep URL and title only; in-memory page state and private tabs are not restored. Private windows use an ephemeral profile and do not write closed-tab restore history.

---

## Installation & Setup

### 1. Requirements
- **Windows 10 / 11** (Linux and macOS compatible)
- **Python 3.10+** (Python 3.12 recommended)

### 2. Set Up Virtual Environment
```powershell
# Navigate to the repository
cd LightMq

# Create virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\activate
```

### 3. Install Dependencies
```powershell
pip install -e .[dev]
```
*Or install runtime dependencies directly:*
```powershell
pip install "PySide6>=6.12.0"
```

### 4. Updating the Engine
To ensure your browser runs the newest compatible Chromium engine supported by PySide6:
```powershell
pip install --upgrade PySide6
```

### 5. Run the Browser
```powershell
# Launch browser (opens the built-in LightMq new-tab page)
python src/browser/main.py

# Launch browser with a custom target URL
python src/browser/main.py https://github.com
python src/browser/main.py localhost:8000

# View engine diagnostics
python src/browser/main.py --diagnostics
```

---

## Project Architecture

```text
src/browser/
├── main.py                    # Application initialization & CLI entry point
├── core/
│   ├── navigation.py          # URL normalization & validation logic
│   ├── tab_manager.py         # Tab collection management & lifecycle signals
│   ├── browser_context.py     # Application context (Phase 3)
│   └── event_bus.py           # Decoupled event dispatcher (Phase 3)
├── ui/
│   ├── main_window.py         # Main browser window, toolbar, tab bar, and splitter layout
│   ├── tab_bar.py             # Custom QTabBar wrapper with '+' button and close buttons
│   ├── address_bar.py         # Custom QLineEdit address bar
│   └── dialogs/
│       └── downloads_dialog.py # Native Qt download list and controls
├── webengine/
│   ├── web_view.py            # QWebEngineView wrapper
│   ├── web_page.py            # QWebEnginePage configuration, window open handler & SSL handling
│   └── download_handler.py    # Per-profile request routing and destination prompt
├── features/
│   └── downloads/
│       ├── download_manager.py # Session transfer coordinator
│       ├── download_item.py    # Per-request progress and control model
│       └── download_utils.py   # Safe names and transfer formatting
├── devtools/
│   ├── devtools_manager.py    # DevTools attachment, dynamic re-targeting & toggle coordinator
│   └── devtools_panel.py      # Resizable DevTools container widget
└── utils/
    ├── constants.py           # Engine metadata, diagnostics & constants
    └── paths.py               # OS path resolution
```

---

## Testing

The project includes comprehensive unit, integration, and end-to-end automated tests:

```powershell
# Run the complete test suite
python -m pytest tests/

# Run unit tests only
python -m pytest tests/unit/

# Run integration tests only
python -m pytest tests/integration/

# Run with verbose output
python -m pytest tests/ -v
```

The automated suite covers:
- Tab manager creation, closing, wrap-around switching, and index bounds.
- UI synchronization when switching tabs (Address Bar, Back/Forward actions, window title).
- Background tab isolation (background tabs never overwrite active tab's address bar).
- Chromium DevTools dynamic attachment across tab switches and safe detachment when closing tabs.
- Final tab closure behavior (automatically recreating a clean start page tab).
- Engine version detection and diagnostics formatting.
- URL normalization and address bar signal emission.
- Repeated DevTools open/close stability and live page loading.

---

## Known Limitations

- **No Search Query Fallback**: Text entered into the address bar must be a URL or domain name (e.g., `example.com`). Integrated search engine fallback is scheduled for Phase 3.
- **Chromium Version Gap**: Bundled Chromium is pinned to v140 (the latest available via Qt WebEngine 6.12.0), while standalone Google Chrome is currently on v158.
- **Bookmark Storage**: Bookmarks remain in their existing JSON store; only browsing history uses SQLite.
- **Login Persistence**: Regular browsing uses Qt WebEngine's named `Default` profile in the OS application-data directory. Session cookies are intentionally persisted across normal restarts. Clearing cookies from Privacy or Clear Browsing Data removes stored login cookies.
- **Authentication Compatibility**: Websites may expire or revoke sessions, require reauthentication, or restrict embedded browsers. Google sign-in is not guaranteed and security restrictions are not bypassed.
- **Permission Persistence**: Permission decision persistence follows the active Qt WebEngine profile policy; the settings list shows the state Qt reports for each decision.
- **Website Storage**: Qt's cache and cookie APIs do not clear Local Storage or IndexedDB. Cookie removal is asynchronous and has no operation-complete signal.
- **History Scope**: Clearing LightMq history does not clear Chromium's per-tab Back/Forward entries, visited-link database, or cookies.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
