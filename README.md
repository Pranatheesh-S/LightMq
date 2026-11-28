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

## Current Status: Multi-Tab Browser with Phase 16 Local Recommendations

LightMq includes a multi-tab browser, persistent regular profile, session restoration, native settings, downloads and history, grouped tabs, Chromium Developer Tools, bookmarks, isolated Incognito sessions, a built-in PDF reader, a native `.xlsx` viewer, and a temporary HTML/CSS/JavaScript element inspector. These features use the existing PySide6/Qt WebEngine architecture.

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
- [x] **Bookmark Manager (Phase 10)**:
  - Saves bookmarks and nested folders in `bookmark_items` tables inside the existing `browser.sqlite3` database shared with browsing history.
  - Migrates legacy `~/.lightmq/bookmarks.json` entries into the Bookmarks Bar without deleting the source JSON file.
  - Address-bar star tracks the active normal tab, opens add/edit controls, and rejects internal/non-HTTP(S) URLs.
  - The toolbar **Bookmarks** menu provides one-click access to saved pages even when the bookmarks bar is hidden; bookmark folders remain nested in the menu.
  - The Bookmarks Bar shows root bookmarks and nested folder menus, has overflow access, context actions, new folders/bookmarks, and open-all folder actions. Visibility persists through Appearance settings or `Ctrl+Shift+B`.
  - `Ctrl+Shift+O` opens the native manager with nested browsing, immediate search, add/edit/delete, cross-folder moves and drag reordering.
  - Imports Netscape bookmark HTML in a worker thread with hierarchy/title/URL/order/timestamp retention, safe URL validation, duplicate skipping, HTML escaping, and transactional database writes; exports use atomic file replacement.
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

- **Incognito / Private Browsing (Phase 11)**:
  - Open a separate Incognito window with `Ctrl+Shift+N` or **Menu → New Incognito Window**. Each window has a visible Incognito banner/title; new private tabs use the private information page.
  - All Incognito windows opened during one active private session share a Qt off-the-record `QWebEngineProfile`, so their tabs share temporary cookies/site storage while remaining isolated from the regular profile. A fresh profile is created after the last private window closes.
  - Private windows do not write browsing history, session snapshots, crash-recovery state, or recently closed tab entries. Tab groups and DevTools remain in memory, and DevTools uses the private profile.
  - Private pages use the existing permission prompt flow. Permission decisions live only in the temporary off-the-record profile and are discarded with the session; requests are not automatically approved.
  - Private windows can read existing bookmarks, but saving/editing one requires a warning that the bookmark is stored outside Incognito. Downloads use a session-only manager and destination prompt; downloaded files remain on disk after the private session ends. Closing the final private window with active downloads asks before cancelling them.
  - Qt reports an internal default `persistentStoragePath()` value for an off-the-record profile in the tested Qt 6.12 build. LightMq does not assign this path, uses `NoPersistentCookies` and `MemoryHttpCache`, and relies on Qt's off-the-record implementation for temporary profile storage. This is not a promise that websites, networks, downloaded files, or operating-system artifacts are hidden or erased.

- **Browsing History**:
  - Successful HTTP(S) top-level navigations are saved as individual UTC-timestamped visits in SQLite under the operating system's application-data directory. The database persists across tabs, browser restarts, and computer restarts. Qt navigation categories are retained where available (link, typed, form, back/forward, reload, redirect, or other).
  - Each visit is committed once after `loadFinished(True)` and only when its page accepted a main-frame navigation. Redirect chains are represented by the final loaded URL; reloads count as new visits. Failed loads, private-window visits, and internal/non-web schemes are excluded.
  - Search titles and URLs (including domains), filter by today, yesterday, the last 7/30 days, or custom local calendar dates, and page through results. History entries can be opened in the current/new tab, copied, or deleted individually or for an entire site.
  - Clear history for the last hour, 24 hours, 7 days, 30 days, or all time. Ctrl+H opens history; Enter opens and Delete removes a selected visit while the results table has focus; Escape closes the dialog.
  - The history database is local and is never uploaded. Private windows do not write history. Clearing this application history database does **not** clear Chromium's per-tab Back/Forward history, HTTP cache, or cookies.
  - Navigation that does not produce a successful main-frame load (including downloads and some single-page-app `pushState` changes) is not represented as a visit. Favicon URLs are retained when WebEngine reports one; favicon image bytes are not cached by history.

- **New Tab Page**:
  - New tabs and new windows open a built-in LightMq start page instead of navigating to `example.com`. Home uses the configured homepage (Google by default).
  - The page is self-contained and includes a search/address field plus editable, removable website shortcuts persisted in LightMq settings. Typed addresses navigate directly; other text uses the configured search provider.
  - The trusted start page loads Qt's bundled WebChannel client under its restrictive Content Security Policy. LightMq registers Qt's documented QRC access flags at startup so the shortcut and local-recommendation bridge functions with Qt 6 custom origins.

- **Local Recommendations (Phase 16)**:
  - Personalized recommendations are **off by default**. Enable them in **Settings → Recommendations**; history and bookmark sources, New Tab display, Continue Browsing, and related-page display can be controlled separately.
  - On opt-in, recommendations use a bounded pool from LightMq's existing SQLite history and bookmark tables. A deterministic score combines capped logarithmic frequency (30%), 14-day exponential recency (30%), bookmark presence (20%), title/hostname/folder word overlap (15%), and explicit pin feedback (5%). Cards show only reasons supported by those signals.
  - The New Tab page provides Recommended, Related, and Continue Browsing sections with open, open-in-new-tab, pin/unpin, hide, right-click actions, and refresh. Empty history remains empty; no sample sites are invented.
  - Hiding and pinning store only a normalized URL path (query and fragment removed), the host, and an optional title in a small `recommendation_feedback` table alongside existing browser metadata. No duplicate history is created. Feedback can be managed or cleared from Settings without removing browsing history, bookmarks, cookies, login sessions, downloads, or session files.
  - Clearing all LightMq history also clears recommendation feedback by default. The clear-data and history dialogs let the user explicitly keep pinned shortcuts; partial time-range deletion only invalidates rankings.
  - Incognito pages never request, render, or write recommendation data. Local files, private/internal addresses, localhost/private IPs, authentication/payment/reset routes, credential URLs, and obvious token-bearing URLs are excluded. Favicons render only when already stored as a small `data:image` value; LightMq does not fetch remote icons.
  - All filtering and ranking run locally. The page Content Security Policy blocks network resources; no cloud AI, telemetry, or recommendation service is used. Context matching is keyword overlap, not semantic understanding. Sparse local data produces fewer or no suggestions.

- **Session Restoration & Startup**:
  - Regular browser tabs are saved in a versioned JSON snapshot below the operating-system application-data directory in `Sessions/current_session.json`; an atomic recovery copy is kept alongside it. URLs, titles, tab order, and active tab are stored. Cookies remain in the separate Qt WebEngine profile.
  - Open **Startup** in a regular window to turn **Restore Previous Session** on or off. It is on by default. When off, choose whether normal startup opens a new tab or your configured homepage. The Home shortcut navigates to that homepage.
  - The setting takes effect on the next launch and does not close current tabs. Session snapshots continue to be updated while restoration is off so crash recovery can still offer the last recovery snapshot. A crash-recovery prompt is separate from normal startup restoration and may still appear while the toggle is off.
  - Existing `startup/mode` preferences are migrated: `continue` enables restoration; `homepage` and `new_tab` disable it and retain that fallback choice. The new boolean setting is authoritative afterward.
  - Session writes are debounced and use Qt atomic file replacement. A separate lifecycle marker distinguishes a clean close from an unclean previous run. When an unclean run has a valid recovery snapshot, LightMq offers **Restore Tabs** or **Start Fresh**.
  - Restoration reloads supported HTTP(S) pages and LightMq's start page in their saved order, with the prior active tab selected. URLs containing user-info or common authentication-token query parameters, and unsupported/internal transient schemes, are excluded from snapshots.
  - Session files are local browsing metadata and may reveal visited URLs. Restoration does not preserve DOM/JavaScript state, form contents, scroll position, complete back/forward history, DevTools state, media playback, or in-progress downloads. Persistent login cookies remain separate and are reused by restored tabs, subject to each website's rules.

- **Privacy & Security**:
  - Open **Privacy** in a regular browser window to inspect cookie metadata, delete one cookie, session cookies, or all cookies, review/reset Qt WebEngine permission decisions, and clear the HTTP cache.
  - Cookie names, domains, paths, expiry, session/persistent status, Secure, and HttpOnly flags are shown; cookie values are never shown or logged. Cookie listing and deletion are asynchronous. Qt emits per-cookie add/remove events but no inventory-finished or delete-all-finished signal, so LightMq reports requests without claiming final completion.
  - Website requests for camera, microphone, screen sharing, mouse lock, desktop notifications, geolocation, clipboard, and local-font access prompt with the requesting origin. Requests are denied by default when unsupported, insecure, stale, or dismissed. Decisions use Qt's profile permission store and its configured persistence policy; LightMq does not create a separate permission database.
  - **Clear Browsing Data** (`Ctrl+Shift+Delete`) supports history ranges of last hour, 24 hours, 7 days, 30 days, and all time. Cookie, HTTP-cache, and saved-permission selections clear the entire selected category regardless of the chosen history time range, and the confirmation dialog states this explicitly.
  - HTTP-cache clearing uses Qt WebEngine's completion signal where available. Clearing LightMq history does not clear cookies, cache, Chromium's visited-link database, or open tabs' Back/Forward lists. Cookie/cache/permission clearing does not remove Local Storage, IndexedDB, downloaded files, or browser settings.
  - These controls operate on the shared regular profile. Cookie persistence is configured as `ForcePersistentCookies`; HTTP caching uses `DiskHttpCache`. Permission decisions retain Qt's configured policy. Incognito uses a separate off-the-record profile with `NoPersistentCookies` and `MemoryHttpCache`; regular privacy controls are not exposed in private windows.
  - Qt's profile diagnostics (`python src/browser/main.py --diagnostics`) report profile name, off-the-record status, storage/cache paths, cookie/cache policies, and Qt WebEngine, PySide6, and Chromium versions. They do not expose cookie values.
  - Login restoration depends on each website's cookie and authentication rules. Google may block sign-in in embedded browsers; LightMq does not bypass that restriction or guarantee Google login compatibility.
  - References: [QWebEngineCookieStore](https://doc.qt.io/qtforpython-6/PySide6/QtWebEngineCore/QWebEngineCookieStore.html), [QWebEnginePermission](https://doc.qt.io/qtforpython-6/PySide6/QtWebEngineCore/QWebEnginePermission.html), and [QWebEngineProfile](https://doc.qt.io/qtforpython-6/PySide6/QtWebEngineCore/QWebEngineProfile.html).

### Planned Features (Future Phases)
- [x] **Session Restoration**: Restore saved regular tabs, order, active tab, startup preferences, and crash recovery choices.
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
| `Ctrl+Shift+O` | Open Bookmark Manager |
| `Ctrl+H` / `Ctrl+J` / `Ctrl+Shift+Delete` | History / downloads / clear browsing data |
| `Ctrl+Shift+B` | Toggle bookmarks bar (visibility is saved for normal windows) |
| `F11` | Toggle fullscreen, restoring the prior maximized or normal state |
| `Ctrl++` (also `Ctrl+=`) / `Ctrl+-` / `Ctrl+0` | Zoom in / out / reset (25%–500%) |
| `F12` / `Ctrl+Shift+I` | Toggle Chromium Developer Tools |
| `Ctrl+Shift+J` | Open Developer Tools and focus its view |
| `Ctrl+Shift+C` | Toggle LightMq's webpage element picker |
| `Ctrl+U` | Open the current URL using Chromium's `view-source:` scheme in a new tab |

### Shortcut support and limitations

- Find-in-page uses `QWebEngineView.findText()`. Cache bypass uses Qt WebEngine's `ReloadAndBypassCache` page action.
- Chromium Developer Tools remain attached through `QWebEnginePage.setDevToolsPage()`. Ctrl+Shift+C starts/stops LightMq's separate element picker; page context-menu Inspect still opens Chromium DevTools. Qt WebEngine does not expose commands to select a specific Chromium panel, so Ctrl+Shift+J cannot guarantee switching to its Console.
- Ctrl+U uses Chromium's built-in `view-source:` URL handling. Printing and saving use Qt WebEngine page APIs.
- Recently closed tabs keep URL and title only; in-memory page state and private tabs are not restored. Private windows use an ephemeral profile and do not write closed-tab restore history.

### Incognito support and limitations

- Incognito sessions use Qt WebEngine's off-the-record profile. Qt 6.12 reports an internal default storage-path string for off-the-record profiles even though LightMq does not set that path and configures memory cache/nonpersistent cookies. The application does not claim that every system component leaves no trace.
- Downloaded files and explicitly saved bookmarks persist by design. Downloads in progress are cancelled only after the user confirms closing the final Incognito window.
- Incognito does not conceal activity from websites or network operators, and does not erase browser-independent OS/network records.

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

## Advanced Tabs and Tab Groups

LightMq supports pinned tabs, per-tab context actions, URL-based duplication, native tab dragging, and reopening recently closed tabs with **Ctrl+Shift+T**. Pinned tabs stay before regular tabs and their strip close affordance is hidden; the tab context menu provides an explicit close action.

Create a group from a tab's context menu, choose a name and color, then manage it from its colored header. Headers can collapse/expand, rename, recolor, create a member tab, ungroup, close the group, and drag to reorder groups. Tabs can move between groups through the tab context menu or by dragging; collapsed tabs remain loaded in their original WebEngine views. Closing a multi-tab group asks for confirmation.

When Session Restoration is enabled, schema v2 snapshots store pinned state, group identity, group order, color, name, collapsed state, and the active tab. Existing schema v1 snapshots migrate as ordinary ungrouped tabs. Recently closed metadata is kept in a per-window stack capped at 20 entries and is not recorded during shutdown or in private windows.

## Browser Settings and Customization

The **Settings** toolbar button opens a native category-based window backed by the existing `QSettings` store. Appearance supports Light, Dark, System, and Custom modes. Custom mode includes a draggable hue ring, saturation/value surface, HEX and RGB inputs, recent-color swatches, light/dark surfaces, and an in-dialog preview. Applying themes updates browser widgets immediately, without replacing tabs or injecting CSS into websites. Palette tokens derive coordinated tab, toolbar, omnibox, menu, dialog, border, text, and focus colors from the chosen accent. The main browser shell includes a compact tab strip, rounded responsive address bar, themed three-dot menu, profile control, download indicator, and tab search/recently closed list.

Search supports Google, Bing, DuckDuckGo, Brave Search, and validated HTTP(S) custom templates. Plain search text is encoded and routed through the selected provider while recognized URLs and localhost addresses retain direct navigation.

Settings also expose the homepage, new-tab destination, the existing session-restoration toggle and fallback, default page zoom, download directory/save prompting, shortcuts, and a link to existing privacy controls. New and restored views use the saved default zoom; later zoom changes remain per tab. Reset Settings confirms before restoring preference defaults and leaves browsing history, downloads, cookies, login sessions, and session files intact. System theme follows Qt's platform color-scheme notification where supported.

Limitations: System appearance follows Qt's OS color-scheme notification where supported. Resetting preferences requires no restart for theme and shortcut updates; settings affecting startup take effect on the next launch. The browser keeps the native Windows title bar to preserve standard resize, snapping, and window controls.

### Frontend and Theme Customization (Phase 12)

The native UI uses coordinated theme tokens across the tab strip, toolbar, rounded omnibox, menu, dialogs, and buttons. Custom color preview is temporary until **Apply theme**; **Cancel preview** restores the stored theme, and **Reset theme** restores System mode and the default accent. Up to eight recent custom colors are available as swatches. Foreground colors are selected by luminance for readable contrast. Existing tab-group colors remain owned by each group, and the regular page renderer is not restyled by browser appearance changes.

The LightMq start page now supports adding, editing, and removing shortcuts. Its narrow QWebChannel bridge validates public URL shortcuts and only writes changes from the trusted internal start page; Incognito can read configured shortcuts but does not persist edits.

### Browser Icon System (Phase 13)

Browser chrome uses an original LightMq SVG outline set rendered through QtSvg. One `IconManager` supplies toolbar, tab, menu, address-bar, find, bookmark, and Settings icons, with reusable accessible `IconButton` controls. Icons use 20 px toolbar artwork, consistent rounded strokes, cached SVG renderers and device-pixel-ratio-aware pixmaps. Normal, hover/active, and disabled colors come from the current theme palette with contrast checks. Website favicons remain untouched; Incognito controls use a dark icon palette that matches the private window.

### Built-in PDF Reader (Phase 13)

LightMq uses Qt WebEngine's built-in Chromium PDF viewer in the existing tab and profile. Inline viewing sets both `PdfViewerEnabled` and `PluginsEnabled`, as required by [Qt WebEngine's PDF viewing support](https://doc.qt.io/qt-6/qtwebengine-features.html). HTTP(S) responses are identified by their response MIME type, so PDF URLs do not need a `.pdf` suffix. Server attachment responses continue through the existing Download Manager.

**Browser Menu → Open File…** and **Ctrl+O** open readable local PDFs in a new tab, including paths with spaces and Unicode characters. LightMq checks the PDF header before opening. Normal PDFs use the shared persistent profile; Incognito PDFs use the existing off-the-record profile. Existing valid local PDF paths can be restored from normal session snapshots; moved or missing files are skipped safely.

### Native Excel Viewer (Phase 13.1)

**Browser Menu → Open File…** and **Ctrl+O** also open `.xlsx` workbooks in native document tabs. The viewer uses a Qt table model and supports multiple worksheets, selection, copy, cell search, and a read-only View Mode by default. Edit Mode allows controlled changes to individual values with per-workbook undo/redo; formulas and merged non-anchor cells remain read-only. Text beginning with `=` is stored as literal text. Numeric, boolean, date, date-time, text, and empty values are displayed and converted where practical.

Save As is recommended and asks before replacing existing targets. Saving uses a same-directory temporary file and atomic replacement. Original-file Save asks for an explicit confirmation; workbooks with formula cells warn that `openpyxl` may invalidate cached formula results, and LightMq never calculates formulas. Workbooks with known drawings, external links, embedded objects, or macro-related package entries open in view-only mode because safe round-trip preservation is not guaranteed. `.xls`, `.xlsm`, `.xlsb`, `.ods`, spreadsheet printing, formula evaluation, and advanced Excel features are unsupported. Session restoration stores only the validated local `.xlsx` path and tab metadata, never workbook contents.

The native viewer provides its own page navigation, zoom/fit, text search, download, and print controls. **Ctrl+F** is left to the native PDF viewer while a PDF tab is active. **Ctrl+S** requests the current PDF download through the page's own WebEngine profile, preserving the existing authentication context and Download Manager destination/overwrite handling. The **Settings → Downloads & PDF** preference chooses inline viewing or downloading instead and persists in the existing `QSettings` store.

**Limitations:** Qt does not expose a supported per-PDF default zoom or “remember PDF reader preferences” API, so LightMq does not add controls that only appear to set these values. Detailed metadata and password-dialog behavior remain owned by Qt's Chromium viewer and were not independently automated. Physical printing depends on the configured OS printer and was not verified in headless tests. OCR, annotations, and PDF editing are out of scope.

### Native Extension Manager (Experimental)

The **Browser Menu → Extensions** entry and puzzle toolbar menu use one controller attached to LightMq's shared regular `QWebEngineProfile`. The native manager validates Manifest V3 manifests and ZIP paths/sizes before handing packages to Qt; it supports profile-persistent installation from ZIP or folder, temporary Developer Mode loading, permission review, extension details, Qt-reported action-popup metadata, and uninstall. The Extensions window can search installed extensions and safely display bounded raster icons from package manifests. SVG icons are ignored. LightMq reloads persisted packages through the same profile manager when this Qt runtime does not enumerate them at startup. Extensions remain unavailable in Incognito. The manager never extracts ZIPs itself or changes regular cookies/storage outside Qt's extension store.

**Phase 17 analysis and diagnostics:** LightMq extracts Manifest V3 background worker, action popup, icon, web-accessible resource, CSP, permission, and other manifest declarations. It statically scans at most 2 MiB/256 JavaScript files for `chrome.*`/`browser.*` namespace references without executing the package. Compatibility reports are tied to the runtime version and label APIs unknown unless LightMq has direct runtime evidence. Permission review separates API permissions, host access, optional permissions, and content-script matches; it flags sensitive and wildcard access but does not claim fine-grained permission enforcement. Diagnostics show Qt's actual loaded/installed/enabled/error state and clearly mark content-script, popup, and worker checks as not run when the extension is disabled.

On a recognized Chrome Web Store listing, **View Compatibility in LightMq** offers inspection of a user-selected local ZIP or unpacked folder. A listing ID is read from the HTTPS URL but is not independently verified. LightMq does not fetch store packages: Google's [documented Chrome Web Store API](https://developer.chrome.com/docs/webstore/api) is an authenticated publisher management API, not a consumer package download interface. No User-Agent spoofing, private endpoint scraping, or CRX mirrors are used.

The **Compare Local Update…** action compares a user-selected package's declared key/version and added required/optional permissions. A matching manifest key is only a claim; LightMq does not cryptographically verify the selected ZIP. Qt provides no verified atomic in-place update/rollback flow here, so this action never changes the managed install.

**Runtime limitation:** This project environment uses Python 3.12.9, PySide6 6.12.0, Qt 6.12.0, and Chromium 140.0.0.0. A prior controlled local MV3 test showed that calling `QWebEngineExtensionManager.setExtensionEnabled()` terminates the process with a native access violation. LightMq blocks that call. Packages install/load disabled, so content script execution, background behavior, and popup rendering cannot currently be verified; enable/disable preferences are not restored. The puzzle menu only opens popups that Qt reports for an enabled extension. The current compatibility result is therefore **Limited Compatibility**, not “Verified Working.” Re-test the native setter after updating the Qt runtime before exposing enablement.

**Chrome Web Store status:** Listing recognition and local-package analysis are implemented. Direct store downloads/installation, automatic updates, and rollback-safe replacement are **unsupported**. A local comparison is not a trusted update channel. Qt documents filesystem-based Manifest V3 loading and profile-scoped managers, but this does not imply full Chrome API compatibility.

## Developer Tools

**F12** opens the existing resizable Chromium DevTools, including its Elements, Console, Sources, and Network tools. In **LightMq Tools**, **Ctrl+Shift+C** or **Select Element** enables a throttled hover overlay; click a target to inspect it, press Esc to cancel, and toggle the picker again to stop it. Tree selections also highlight the page element. The panel can be resized on the right or bottom; its dock side and splitter proportions are remembered in `QSettings`.

The DOM tools display bounded, actual HTML, attributes, text, box dimensions, parent/child information, CSS selectors, XPath, and inline event attributes. Sensitive form values, token-like attributes, and sensitive URL query parameters are filtered from returned markup and CSS. DOM expansion is lazy and supports open shadow roots; cross-origin iframe internals and closed shadow roots remain inaccessible. The CSS tool shows browser-computed properties, accessible matching rules, and a box-model diagram labeled with measured CSS pixel values. CSS overrides and permitted leaf-text/attribute edits are temporary; Undo, Redo, and Reset restore CSS changes, and closing the tools panel restores current temporary edits. Inspector edits are bounded to 100 HTML-edited elements and 200 distinct CSS element/property pairs at a time. Edits never write to site files.

The JavaScript tab only reports observable inline handler attributes. Standard DOM inspection cannot enumerate all `addEventListener()` listeners or reliably map a node to bundled JavaScript sources; it states this limitation and provides **Open Chromium DevTools**. Selection and inspector code use Qt WebEngine's isolated Application World, structured JSON results, bounded payloads, and no remote debugging endpoint. PDF and native document tabs show an unsupported-inspection message. The custom tools follow the active tab and clear stale selection on navigation, renderer termination, tab changes, panel close, and window close. Qt's request interceptor still reports request-side metadata only; Chromium DevTools remains authoritative for protocol-backed debugging.

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

Phase 17 complete run: **184 passed** (`pytest -q`), including isolated extension package, compatibility, listing recognition, permission, update-comparison, dialog, and profile integration checks. `python -m compileall -q src tests` and `git diff --check` passed. The current runtime limitation on extension enabling is documented above; the suite intentionally does not invoke the crashing native setter.

---

## Known Limitations

- **Chromium Version Gap**: Bundled Chromium is pinned to v140 (the latest available via Qt WebEngine 6.12.0), while standalone Google Chrome is currently on v158.
- **Bookmark Storage**: Bookmark records share `browser.sqlite3` with browsing history. Existing `~/.lightmq/bookmarks.json` data is imported on startup and retained as a migration source; newly added data is stored in SQLite.
- **Login Persistence**: Regular browsing uses Qt WebEngine's named `Default` profile in the OS application-data directory. Session cookies are intentionally persisted across normal restarts. Clearing cookies from Privacy or Clear Browsing Data removes stored login cookies.
- **Authentication Compatibility**: Websites may expire or revoke sessions, require reauthentication, or restrict embedded browsers. Google sign-in is not guaranteed and security restrictions are not bypassed.
- **Permission Persistence**: Permission decision persistence follows the active Qt WebEngine profile policy; the settings list shows the state Qt reports for each decision.
- **Website Storage**: Qt's cache and cookie APIs do not clear Local Storage or IndexedDB. Cookie removal is asynchronous and has no operation-complete signal.
- **History Scope**: Clearing LightMq history does not clear Chromium's per-tab Back/Forward entries, visited-link database, or cookies.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Windows release candidate (Phase 18)

Windows x64 packaging is available through `packaging/windows/build.ps1` and
`build_installer.ps1`. PyInstaller builds a standalone directory with Python,
Qt WebEngine/PDF, openpyxl, themes, an original application icon, and license
notices. Inno Setup provides per-user installation, Start Menu and optional
desktop shortcuts, and uninstall without removing browsing data. The existing
Qt profile/settings identity is retained; no data migration is performed.

This is an **unsigned internal test candidate**. Current Qt wheels carry
commercial-license notices; redistribution entitlement has not been verified.
Clean Windows testing, an earlier-version upgrade test, display/GPU/media
checks, signing and complete license review remain release gates. Extension
enabling remains blocked by the existing Qt native crash. Download records
remain session-only. The ZIP uses normal per-user data paths, not isolated
portable profiles. No default file/browser associations are registered.

See [Windows packaging guide](packaging/windows/README.md) for build, install,
uninstall, data paths, diagnostics, signing, verification and release limitations.
The Phase 18 full regression run passed **187 tests**. The standalone probe
verified HTTPS/reload, tabs, themes/icons, DevTools, XLSX, Incognito isolation,
and synthetic settings persistence on the development host. This does not
replace testing on Windows without Python, Qt or a source checkout.
