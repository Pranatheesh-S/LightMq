# LightMq Architecture Documentation

## 1. Architectural Overview

LightMq is a modular, high-performance desktop web browser designed with **Python 3**, **PySide6**, and **Qt WebEngine** (Chromium engine).

The application follows clean architecture principles, separating the user interface from browser business logic, isolating the Chromium rendering engine behind clean facades, and decoupling components using an asynchronous Event Bus.

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        UI Presentation Layer                           │
│  (MainWindow, AddressBar, TabBar, ToolBar, Sidebar, StatusBar, Themes) │
└───────────────────▲────────────────────────────────▲───────────────────┘
                    │                                │
                    ▼                                ▼
┌──────────────────────────────────────┐  ┌──────────────────────────────┐
│           Core Browser Layer         │  │   Developer Tools Subsystem  │
│  (BrowserContext, TabManager,        │◄─┤  (DevToolsManager, Panel,    │
│   Navigation, SessionManager, Event) │  │   ElementInspector, Console) │
└───────────────────▲──────────────────┘  └──────────────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        Qt WebEngine Layer                              │
│  (WebView, WebPage, WebProfile, RequestInterceptor, DownloadHandler)   │
└───────────────────▲────────────────────────────────▲───────────────────┘
                    │                                │
                    ▼                                ▼
┌──────────────────────────────────────┐  ┌──────────────────────────────┐
│        Storage & Security Layer      │  │      Services & Features     │
│  (SQLite Database, Settings,         │  │ (Bookmarks, History, Search, │
│   URLValidator, CertificateHandler)  │  │  AdBlock, AI Assistant)      │
└──────────────────────────────────────┘  └──────────────────────────────┘
```

---

## 2. Architectural Principles

1. **Modularity**: Each component lives in a dedicated package with clearly delineated interfaces.
2. **Separation of Concerns**: UI components never directly execute WebEngine low-level operations; WebEngine views are wrapped in domain abstractions.
3. **Decoupled Communication (Event Bus)**: Modules publish and subscribe to strongly typed domain events via `core/event_bus.py`, preventing circular import dependencies.
4. **Qt WebEngine Isolation**: `src/browser/webengine/` isolates Chromium process controls, profiles, request filtering, and permission handling from the rest of the application.
5. **Dedicated Developer Tools Subsystem**: Built-in Chromium Developer Tools (Inspect Element, DOM, Network, CSS, Console) are architected as an independent subsystem (`src/browser/devtools/`) that can be embedded, docked, or opened in detached windows.
6. **Extensibility & Pluggable Features**: Future browser features (such as bookmarks, history, reader mode, ad blocking, and AI assistant) reside in `src/browser/features/` as independent feature packages.
7. **Cross-Platform Readiness**: Designed primarily for Windows while maintaining POSIX filesystem compatibility for Linux and macOS.

---

## 3. Subsystem Breakdown and Responsibilities

### `src/browser/core/` — Core Engine & Orchestration
- **`browser_context.py`**: Singleton application context managing global state, profile lifecycles, and configuration.
- **`navigation.py`**: Manages URL history stacks, navigation state machines (loading, completed, failed), and dispatch.
- **`tab_manager.py`**: Controls tab collections, active tab selection, tab creation/destruction, and tab metadata models.
- **`session_manager.py`**: Serializes tab states, open windows, and viewports to disk for crash recovery and session restart.
- **`event_bus.py`**: Asynchronous publish/subscribe message broker for decoupled communication across all subsystems.

### `src/browser/ui/` — Presentation Layer (PySide6)
- **`main_window.py`**: Top-level `QMainWindow` integrating tab bar, toolbars, active viewport, and status bar.
- **`address_bar.py`**: Omnibox supporting direct URL entry, search engine queries, and SSL security lock indicators.
- **`tab_bar.py`**: Custom draggable, closeable, and pinnable tab header bar.
- **`toolbar.py`**: Action buttons for navigation (Back, Forward, Reload, Home), extension actions, and settings menu.
- **`sidebar.py`**: Collapsible side panel hosting bookmarks, history, and developer tools.
- **`status_bar.py`**: Bottom status bar displaying hovered hyperlink targets, zoom levels, and page load progress.
- **`widgets/`**: Reusable standalone widgets (e.g., search popup, security info card).
- **`dialogs/`**: Application dialogs (Preferences, About, Certificate Warning).
- **`themes/`**: Custom Qt Style Sheets (`light.qss`, `dark.qss`) for seamless UI theme switching.

### `src/browser/webengine/` — Chromium / Qt WebEngine Wrapper
- **`web_view.py`**: Subclassed `QWebEngineView` exposing high-level page control and event emissions.
- **`web_page.py`**: Subclassed `QWebEnginePage` handling custom window creation, JavaScript dialogs, and certificate errors.
- **`web_profile.py`**: Profile factory for persistent disk-backed storage and ephemeral incognito browsing.
- **`permissions.py`**: Handler for web feature permission requests (geolocation, camera, microphone, notifications).
- **`request_interceptor.py`**: `QWebEngineUrlRequestInterceptor` implementation for ad blocking, header injection, and privacy filtering.
- **`download_handler.py`**: Intercepts `QWebEngineDownloadRequest`, manages download directories, and reports progress.

### `src/browser/devtools/` — Chromium Developer Tools Subsystem
- **`devtools_manager.py`**: Orchestrates the Chromium remote debugging interface and connects DevTools views to the active page.
- **`devtools_panel.py`**: Dockable container hosting the inspection interface.
- **`element_inspector.py`**: Context menu "Inspect Element" action handler that focuses and highlights the clicked DOM node.
- **`dom_tree.py`**: Visual interactive DOM hierarchy tree.
- **`css_inspector.py`**: Live CSS rules, computed styles, and box model visualizer.
- **`console_panel.py`**: JavaScript console for log output and live command evaluation.
- **`network_monitor.py`**: HTTP/HTTPS request, header, payload, and timing waterfall viewer.
- **`source_viewer.py`**: Syntax-highlighted resource and script inspection.
- **`performance_panel.py`**: Rendering and memory consumption monitor.

### `src/browser/features/` — Independent Modular Features
Each feature in this directory operates as an independent module with its own models, views, and controllers:
- **`bookmarks/`**: Bookmark storage, folder hierarchies, and omnibox integration.
- **`history/`**: Visited URLs, visit timestamps, and history searching.
- **`downloads/`**: Download shelf UI and persistent download log.
- **`search/`**: In-page search bar (Ctrl+F) and search engine providers.
- **`private_browsing/`**: Incognito browsing mode controller.
- **`profiles/`**: Multi-profile management (Work, Personal).
- **`extensions/`**: WebExtension and user-script support.
- **`reader_mode/`**: Article content extractor and distraction-free renderer.
- **`screenshots/`**: Full-page and clipped region screenshot utility.
- **`ad_blocking/`**: Network-level tracker and advertisement blocker.
- **`password_manager/`**: Local encrypted credential vault and autofill.
- **`ai_assistant/`**: Sidecar AI assistant for web page analysis and summarization.

### `src/browser/storage/` — Persistence Layer
- **`database.py`**: SQLite database connection manager with connection pooling and schema migrations.
- **`settings.py`**: Application configuration and user preferences persistence via `QSettings` or JSON.
- **`migrations/`**: Versioned schema migration scripts.
- **`repositories/`**: Repository pattern implementations for bookmarks, history entries, and credentials.

### `src/browser/security/` — Security Subsystem
- **`url_validator.py`**: Validates URL formats, schemes (`http`, `https`, `file`, `about`), and detects malicious patterns.
- **`certificate_handler.py`**: Evaluates TLS/SSL certificate trust chains and enforces security overrides.
- **`permission_policy.py`**: Enforces strict origin-based permission rules.

### `src/browser/services/` — Application Services
- **`search_service.py`**: Query builder and autocomplete suggestions for Google, DuckDuckGo, and Bing.
- **`favicon_service.py`**: Asynchronous site icon fetcher and disk cache.
- **`update_service.py`**: Background checks for new browser versions.

### `src/browser/utils/` — Cross-Cutting Utilities
- **`logging.py`**: Centralized structured logging setup with file and console handlers.
- **`paths.py`**: Cross-platform path resolver for config, cache, and profile data directories.
- **`constants.py`**: Application constants, default URLs, version strings, and user-agent strings.
