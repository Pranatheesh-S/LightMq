# LightMq Development Roadmap

This document outlines the strategic development phases for LightMq. All features are currently in the **Planned** stage, as no business logic has been implemented yet.

---

## Phase 1: Browser Window, Navigation, Tabs & Built-in Developer Tools
*Status: Planned (Target Phase)*

- [ ] **Application Shell & Lifecycle**:
  - `src/browser/main.py`: PySide6 `QApplication` lifecycle and command-line argument parsing.
  - `src/browser/core/browser_context.py`: Browser runtime context and profile management.
  - `src/browser/core/event_bus.py`: Decoupled publish/subscribe event dispatcher.
- [ ] **Tab Management & Navigation**:
  - `src/browser/core/tab_manager.py`: Tab model, tab creation, closing, reordering, and pinning.
  - `src/browser/core/navigation.py`: Navigation controller for Back, Forward, Reload, Stop, and URL loading.
  - `src/browser/ui/tab_bar.py`: Custom draggable and closeable tab bar widget.
  - `src/browser/ui/address_bar.py`: Omnibox with URL input, search query detection, and SSL indicator.
  - `src/browser/ui/toolbar.py`: Standard browser navigation and menu actions.
  - `src/browser/ui/main_window.py`: Top-level window hosting the navigation toolbar, tab bar, and active viewport.
- [ ] **Qt WebEngine Integration**:
  - `src/browser/webengine/web_view.py`: Encapsulated `QWebEngineView` integrating with tab lifecycle.
  - `src/browser/webengine/web_page.py`: Subclassed `QWebEnginePage` for custom window requests and certificate overrides.
  - `src/browser/webengine/web_profile.py`: Persistent storage profile configuration.
- [ ] **Built-in Chromium Developer Tools (Inspect Element)**:
  - `src/browser/devtools/devtools_manager.py`: Remote debugging coordinator and inspector bridge.
  - `src/browser/devtools/devtools_panel.py`: Embeddable and dockable DevTools panel.
  - `src/browser/devtools/element_inspector.py`: "Inspect Element" context menu action binding active element to inspector.

---

## Phase 2: Bookmarks, History, Downloads & Session Restoration
*Status: Planned*

- [ ] **Bookmarks Subsystem** (`src/browser/features/bookmarks/`):
  - Bookmark bar, bookmark manager dialog, folder hierarchy, and JSON/SQLite export/import.
- [ ] **Browsing History Subsystem** (`src/browser/features/history/`):
  - SQLite-backed history tracking, search, filtering by date, and privacy clearing.
- [ ] **Download Management** (`src/browser/webengine/download_handler.py`, `src/browser/features/downloads/`):
  - `QWebEngineDownloadRequest` interception, download destination selection, pause/resume, and progress bar UI.
- [ ] **Session Restoration** (`src/browser/core/session_manager.py`):
  - Tab state serialization on exit (URL, scroll position, tab order) and automatic restoration on startup or crash recovery.
- [ ] **Favicon Management** (`src/browser/services/favicon_service.py`):
  - Asynchronous favicon fetching and local SQLite/disk cache.

---

## Phase 3: Custom DOM Inspection, CSS Editing, Network Monitoring & Performance Tools
*Status: Planned*

- [ ] **DOM Tree Viewer** (`src/browser/devtools/dom_tree.py`):
  - Interactive hierarchical DOM inspector with node attribute editing and live highlight overlay in web view.
- [ ] **CSS Inspector & Live Rule Editor** (`src/browser/devtools/css_inspector.py`):
  - Box model visualizer, computed styles viewer, and live CSS rule modification via JavaScript injection.
- [ ] **JavaScript Console Panel** (`src/browser/devtools/console_panel.py`):
  - Interception of `console.log`, `console.warn`, `console.error`, and interactive JS command prompt evaluation.
- [ ] **Network Traffic Monitor** (`src/browser/devtools/network_monitor.py`):
  - HTTP/HTTPS request and response logger, header inspection, payload viewer, and timing waterfall.
- [ ] **Page Source & Resource Viewer** (`src/browser/devtools/source_viewer.py`):
  - Syntax-highlighted HTML, JS, and CSS source code viewer.
- [ ] **Performance Panel** (`src/browser/devtools/performance_panel.py`):
  - Page load milestone metrics (DOMContentLoaded, Load), memory usage, and frame timing.

---

## Phase 4: Private Browsing, Profiles, Permissions & Security Enhancements
*Status: Planned*

- [ ] **Private Browsing Mode** (`src/browser/features/private_browsing/`):
  - Ephemeral off-the-record `QWebEngineProfile` preventing history, cookies, and cache from touching disk.
- [ ] **Multi-User Profile Manager** (`src/browser/features/profiles/`):
  - Multiple isolated profiles (e.g., Personal, Work) with independent cookies, cache, and extensions.
- [ ] **Granular Web Permissions** (`src/browser/webengine/permissions.py`, `src/browser/security/permission_policy.py`):
  - Explicit user authorization dialogs for Geolocation, Camera, Microphone, and Desktop Notifications.
- [ ] **Security Validation & Filtering**:
  - `src/browser/security/url_validator.py`: Safe URL parsing and protocol allow-listing (`http`, `https`, `file`, `about`).
  - `src/browser/security/certificate_handler.py`: Validation of SSL/TLS certificate chains with user override warnings.
  - `src/browser/webengine/request_interceptor.py`: Content request filter for malicious domains and tracker blocking.

---

## Phase 5: Extensions, Advanced Features, Optimization & Application Packaging
*Status: Planned*

- [ ] **Content Ad-Blocking Engine** (`src/browser/features/ad_blocking/`):
  - EasyList-compatible rule parsing and network-level request blocking.
- [ ] **Browser Extensions & User Scripts** (`src/browser/features/extensions/`):
  - Content script injection engine and WebExtension manifest support.
- [ ] **Distraction-Free Reader Mode** (`src/browser/features/reader_mode/`):
  - Article extraction and clean typographic rendering.
- [ ] **Full-Page & Area Screenshots** (`src/browser/features/screenshots/`):
  - Off-screen render capture for full web pages and custom crop regions.
- [ ] **Credential Autofill & Password Manager** (`src/browser/features/password_manager/`):
  - Encrypted local vault for saved login credentials.
- [ ] **Integrated AI Assistant Sidecar** (`src/browser/features/ai_assistant/`):
  - Sidebar copilot for web page summarization, translation, and contextual assistance.
- [ ] **Application Packaging & Distribution** (`packaging/`):
  - Windows: PyInstaller / Nuitka executable with MSIX/InnoSetup installer.
  - Linux: AppImage, Flatpak, and Debian package recipes.
  - macOS: Application bundle (.app) and DMG packaging with code-signing configurations.
