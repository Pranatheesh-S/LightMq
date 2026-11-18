# LightMq

A customizable, developer-focused desktop web browser built with **Python**, **PySide6**, and **Qt WebEngine (Chromium)**.

---

## Project Overview

**LightMq** is an open-source desktop browser designed for developers, power users, and privacy-conscious browsing. Rather than relying on a monolithic architecture, LightMq separates browser engine controls, user interface components, and developer tooling into clean, modular layers.

### Rendering Architecture
LightMq utilizes **Qt WebEngine**, which encapsulates the **Chromium** browser engine and Google V8 JavaScript runtime:
- **Multi-Process Architecture**: Web content renders in isolated Chromium renderer processes, keeping rendering crashes independent from the main browser UI.
- **Modern Web Standards**: Full support for HTML5, CSS3, modern JavaScript standards, WebGL, and media playback.
- **Native Developer Tools Integration**: Direct access to Chromium's built-in remote debugging protocol and DevTools inspector.

The goal of LightMq is to provide a clean, hackable, and extensible browser environment where developers can inspect web applications, manage custom network interceptors, automate browsing workflows, and customize UI themes without unnecessary browser bloat.

---

## Project Status

> **Current State: Scaffolding & Initial Architecture**
> 
> The project is currently in the initial scaffolding and architecture definition phase. The folder structure, packaging configurations (`pyproject.toml`), and technical documentation have been established. Core browser runtime features, UI controls, and WebEngine bindings are scheduled for implementation starting in **Phase 1**.

---

## Technology Stack

- **Python**: `3.12+` (Minimum `3.10+`)
- **UI Toolkit**: [PySide6](https://wiki.qt.io/Qt_for_Python) (Official Qt 6 Python bindings)
- **Rendering Engine**: [Qt WebEngine](https://doc.qt.io/qtforpython-6/PySide6/QtWebEngineWidgets/index.html) (Chromium backend)
- **Styling**: Qt Style Sheets (QSS) for light and dark themes
- **Storage (Planned)**: SQLite for history, bookmarks, user settings, and cache management
- **Testing**: [pytest](https://docs.pytest.org/) and `pytest-qt` for GUI and component testing

---

## Features

### Currently Implemented
- **Project Scaffolding**: Modular directory structure separating core engine, UI, WebEngine, DevTools, storage, and features.
- **Packaging & Dependencies Configuration**: Configured `pyproject.toml` with packaging metadata and optional development dependencies.
- **Theme Scaffolding**: Base QSS definitions for light and dark themes (`src/browser/ui/themes/`).
- **Architecture & Design Documentation**: Technical specifications in `docs/` detailing architecture, security design, and development roadmaps.

### Planned Features
- **Tabbed Browsing**: Multi-tab management with draggable, closeable, and pinnable tabs (`core/tab_manager.py`, `ui/tab_bar.py`).
- **Navigation & Omnibox**: URL bar with search query parsing, navigation controls (Back, Forward, Reload, Home), and SSL security indicators (`ui/address_bar.py`).
- **Built-in Developer Tools (Inspect Element)**: Chromium DevTools protocol integration, dockable inspector panel, and right-click "Inspect Element" action (`devtools/`).
- **Advanced Developer Panels**: Custom DOM tree visualizer, live CSS rule inspector, JS console bridge, and network traffic monitor (`devtools/`).
- **Bookmarks & History**: Hierarchical bookmark manager and searchable browsing history backed by SQLite (`features/bookmarks/`, `features/history/`).
- **Download Management**: File download interception, progress monitoring, and download shelf (`webengine/download_handler.py`).
- **Privacy & Security**: Ephemeral private browsing (Incognito) using in-memory profiles, granular web permissions, and URL validation (`features/private_browsing/`, `security/`).
- **Content Filtering**: Request interceptor for network-level ad and tracker blocking (`features/ad_blocking/`).
- **AI Assistant Sidecar**: Collapsible assistant sidebar for webpage summarization and contextual tasks (`features/ai_assistant/`).

---

## Project Architecture

LightMq enforces strict separation of concerns across dedicated modules within `src/browser/`:

```text
LightMq/
│
├── pyproject.toml             # Project packaging, metadata, and dependencies
├── README.md                  # Project overview and developer documentation
├── LICENSE                    # MIT License
├── .gitignore                 # Version control exclusions
├── .env.example               # Environment variable templates
│
├── src/
│   └── browser/               # Main application package
│       ├── main.py            # Application entry point (Planned)
│       ├── core/              # State management, tab models, navigation, EventBus
│       ├── ui/                # PySide6 widgets, main window, address bar, themes
│       ├── webengine/         # Qt WebEngine / Chromium encapsulation and profiles
│       ├── devtools/          # Chromium DevTools inspector, DOM, console, network
│       ├── features/          # Pluggable features (bookmarks, history, adblock, etc.)
│       ├── storage/           # SQLite database, schema migrations, repositories
│       ├── security/          # URL validator, certificate handler, permission policy
│       ├── services/          # Search suggestions, favicon caching, update service
│       └── utils/             # Logging, filesystem paths, constants
│
├── assets/                    # Static resources (icons, graphics)
├── tests/                     # Test suite (unit, integration, e2e)
├── docs/                      # Technical documentation
├── scripts/                   # Utility and maintenance scripts
└── packaging/                 # Distribution recipes (Windows, Linux, macOS)
```

### Module Responsibilities

| Subsystem | Responsibility |
| :--- | :--- |
| **`core/`** | Application lifecycle, tab collections, navigation state machine, session persistence, and decoupled `EventBus`. |
| **`ui/`** | Pure PySide6 presentation layer (main window, address bar, tab bar, toolbars, sidebars, status bar, and QSS themes). |
| **`webengine/`** | Subclasses of `QWebEngineView` and `QWebEnginePage`, profile management (persistent & incognito), request interceptors, and download handlers. |
| **`devtools/`** | Dedicated Chromium Developer Tools subsystem: remote debugging coordinator, inspector dock panel, element inspector, console, and network monitor. |
| **`features/`** | Isolated, toggleable browser features (bookmarks, history, downloads, private browsing, reader mode, ad blocking, and AI assistant). |
| **`storage/`** | SQLite database manager, versioned schema migrations, user preferences, and repository access abstractions. |
| **`security/`** | Safe URL scheme validation, TLS/SSL certificate verification, and origin-based permission enforcement. |
| **`services/`** | Background operational services such as search query suggestions, asynchronous favicon caching, and update checks. |
| **`utils/`** | Centralized logging, cross-platform application path resolvers, and global browser constants. |
| **`tests/`** | Structured test suites: unit tests (`tests/unit/`), integration tests (`tests/integration/`), and end-to-end browser tests (`tests/e2e/`). |

---

## Installation and Setup

### Prerequisites
- **Operating System**: Windows 10/11 (Linux and macOS support planned)
- **Python**: Version `3.10` or higher (`3.12` recommended)

### 1. Clone the Repository
```bash
git clone https://github.com/Pranatheesh-S/LightMq.git
cd LightMq
```

### 2. Set Up a Virtual Environment (Windows)
```powershell
# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
.venv\Scripts\activate
```

### 3. Install Dependencies
Install the package in editable mode along with development and testing dependencies:
```powershell
pip install -e .[dev]
```

### 4. Running the Browser
> **Note**: An executable entry point is planned for **Phase 1**. Running the browser will be available once the core window and event loop are implemented:
> ```powershell
> # Planned launch command (Phase 1)
> python -m browser.main
> # Or via console script:
> lightmq
> ```

---

## Development Roadmap

The development of LightMq is planned in five incremental phases:

- **Phase 1: Browser MVP & Inspect Element**
  - Application window shell (`main_window.py`).
  - Draggable, closeable tab bar (`tab_bar.py`) and tab collection manager (`tab_manager.py`).
  - Navigation controls and omnibox address bar (`address_bar.py`, `navigation.py`).
  - Qt WebEngine integration (`web_view.py`, `web_page.py`, `web_profile.py`).
  - Built-in Chromium Developer Tools integration and right-click "Inspect Element" (`devtools/`).

- **Phase 2: Bookmarks, History & Downloads**
  - SQLite database layer and schema migrations (`storage/database.py`).
  - Bookmarks manager bar and storage (`features/bookmarks/`).
  - Searchable browsing history with privacy clearing (`features/history/`).
  - Download interception and progress tracking (`webengine/download_handler.py`, `features/downloads/`).
  - Session save and crash restoration (`core/session_manager.py`).

- **Phase 3: Custom Developer Tools**
  - Interactive DOM hierarchy tree viewer (`devtools/dom_tree.py`).
  - Live CSS rule inspector and box model visualizer (`devtools/css_inspector.py`).
  - JavaScript console input/output panel (`devtools/console_panel.py`).
  - Network traffic monitor for requests, headers, and timings (`devtools/network_monitor.py`).

- **Phase 4: Privacy & Security**
  - Incognito / private browsing mode with ephemeral in-memory profiles (`features/private_browsing/`).
  - Multi-profile management for work and personal browsing (`features/profiles/`).
  - Strict URL scheme validation (`security/url_validator.py`).
  - SSL/TLS certificate validation and warning interstitials (`security/certificate_handler.py`).
  - Granular web permission policy management (`security/permission_policy.py`).

- **Phase 5: Advanced Features & Packaging**
  - Network-level ad and tracker blocker (`features/ad_blocking/`).
  - User extensions and script injection support (`features/extensions/`).
  - Distraction-free article reader mode (`features/reader_mode/`).
  - Integrated AI Assistant sidecar panel (`features/ai_assistant/`).
  - Application packaging for Windows (installer/MSIX), Linux (AppImage/Flatpak), and macOS (`packaging/`).

---

## Testing

The testing suite is structured using `pytest` and `pytest-qt` under `tests/`:

```text
tests/
├── unit/           # Unit tests for core models, event bus, and utilities
├── integration/    # Integration tests for storage, profiles, and interceptors
└── e2e/            # End-to-end GUI and browsing workflow tests
```

### Running Tests
The test directory scaffolding is initialized. Test execution will be enabled as test cases are added alongside Phase 1 implementations:

```powershell
# Run the test suite
pytest

# Run unit tests only
pytest tests/unit

# Run tests with verbose output
pytest -v
```

---

## Documentation

Comprehensive technical documentation is available in the `docs/` directory:

- [docs/architecture.md](docs/architecture.md) — System architecture, subsystem breakdown, and component interaction.
- [docs/development.md](docs/development.md) — Development conventions, coding standards, and environment setup.
- [docs/security.md](docs/security.md) — Security model, process isolation, and permission policies.
- [docs/roadmap.md](docs/roadmap.md) — Detailed feature roadmap and milestone breakdown.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
