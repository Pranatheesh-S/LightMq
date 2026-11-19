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

### Currently Implemented (Phase 1 & Phase 2)
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

### Planned Features (Future Phases)
- [ ] **Bookmarks & History**: Local SQLite-backed bookmark hierarchy and searchable visit history.
- [ ] **Download Manager**: File download interception, progress tracking, and download shelf.
- [ ] **Session Restoration**: Automatic recovery of open tabs across browser restarts.
- [ ] **Private Browsing (Incognito)**: Ephemeral in-memory profiles leaving no disk trace.
- [ ] **Ad-Blocking & Privacy**: Network request interception for tracker and ad filtering.
- [ ] **AI Assistant Sidecar**: Integrated copilot panel for page summarization and search.

---

## Technology Stack

- **Python**: `3.12+` (Minimum `3.10+`)
- **UI Framework**: [PySide6](https://wiki.qt.io/Qt_for_Python) (`>=6.12.0`)
- **Rendering Engine**: [Qt WebEngine](https://doc.qt.io/qtforpython-6/PySide6/QtWebEngineWidgets/index.html) (Chromium 140 backend)
- **Testing**: [pytest](https://docs.pytest.org/)

---

## Keyboard Shortcuts

| Shortcut | Action |
| :--- | :--- |
| **`Ctrl + T`** | Open new tab |
| **`Ctrl + W`** | Close current tab |
| **`Ctrl + Tab`** | Switch to next tab (forward cycle with wrap-around) |
| **`Ctrl + Shift + Tab`** | Switch to previous tab (backward cycle with wrap-around) |
| **`Ctrl + L`** | Focus Address Bar and select all text |
| **`Enter`** | Navigate to address typed in the Address Bar |
| **`Ctrl + R` / `F5`** | Reload active tab |
| **`Alt + Left`** | Navigate Back |
| **`Alt + Right`** | Navigate Forward |
| **`Esc`** | Stop loading active tab |
| **`F12`** | Toggle Chromium Developer Tools (Inspect Element) for active tab |

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
# Launch browser (opens default page https://example.com)
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
│   └── address_bar.py         # Custom QLineEdit address bar
├── webengine/
│   ├── web_view.py            # QWebEngineView wrapper
│   └── web_page.py            # QWebEnginePage configuration, window open handler & SSL handling
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

All 32 test cases verify:
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
- **No Local Persistence**: History and bookmarks are not yet saved to a persistent SQLite database.
- **Downloads**: File downloads currently use default WebEngine handlers until a dedicated download manager and shelf are implemented.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
