# LightMq Development Guide

## 1. Prerequisites
- **Python**: Version 3.10, 3.11, or 3.12 (64-bit recommended).
- **Qt / PySide6**: Version 6.5.0 or later (installed via pip).
- **Git**: For version control.

---

## 2. Environment Setup

### Create and Activate Virtual Environment
```bash
# Navigate to project repository root
cd LightMq

# Create virtual environment
python -m venv .venv

# Activate on Windows:
.venv\Scripts\activate

# Activate on Linux/macOS:
source .venv/bin/activate
```

### Install in Editable Mode with Development Dependencies
```bash
# Installs lightmq-browser in editable mode with test and lint tools
pip install -e .[dev]
```

*(Note: Do not install dependencies until instructed during implementation tasks.)*

---

## 3. Code Conventions & Standards

- **PEP 8**: Follow standard Python formatting.
- **Type Annotations**: All public classes, methods, and functions must have type hints.
- **Docstrings**: Provide Google-style docstrings for modules, classes, and complex functions.
- **Qt Thread Safety**:
  - All UI updates and widget manipulations must occur strictly on the main Qt GUI thread.
  - Background tasks (file I/O, network requests, DB queries) must run on `QThread` workers or thread pools and communicate via Qt signals or the `EventBus`.
- **Imports**: Group imports into standard library, third-party (PySide6), and local application modules (`browser.*`).
- **No Circular Imports**: Keep `core/`, `ui/`, `webengine/`, and `devtools/` isolated. Use `core/event_bus.py` for decoupled events.

---

## 4. Testing Suite

The testing suite is structured into three tiers under `tests/`:

```text
tests/
├── unit/           # Fast tests for individual models, validators, and event bus
├── integration/    # Multi-component interaction (e.g., storage + history, webengine + interceptor)
└── e2e/            # Full browser automation using pytest-qt
```

### Running Tests
```bash
# Run entire test suite
pytest

# Run unit tests only
pytest tests/unit

# Run tests with verbose output
pytest -v
```

---

## 5. Static Analysis & Linting

```bash
# Code style and lint checking
ruff check src tests

# Automatic formatting check
ruff format --check src tests

# Static type verification
mypy src
```
