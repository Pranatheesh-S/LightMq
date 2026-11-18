# Claude Code Development Guide — LightMq Browser

## Overview
This is **LightMq**, a modular desktop browser using Python 3, PySide6, and Qt WebEngine with Chromium Developer Tools.

## Canonical Instructions & Memory
1. Always consult `AGENTS.md` for global architecture guidelines.
2. Consult `.ai/memory/` for task tracking and status:
   - Read `.ai/memory/STATUS.md` and `.ai/memory/TODO.md` before planning.
   - Update `.ai/memory/COMPLETED.md`, `.ai/memory/TODO.md`, and `.ai/memory/SESSION_LOG.md` after changes.

## Development Commands
- Install editable with dev dependencies: `pip install -e .[dev]`
- Run tests: `pytest`
- Run single test: `pytest tests/unit/test_tab_manager.py`
- Code formatting & linting: `ruff check src tests`
- Type checking: `mypy src`

## Core Architecture Guidelines
- `src/browser/core/`: Context, tab management, event bus.
- `src/browser/ui/`: Presentation layer (widgets, dialogs, QSS styles).
- `src/browser/webengine/`: Encapsulated Qt WebEngine and Chromium components.
- `src/browser/devtools/`: Chromium DevTools panel, inspect element, console.
- `src/browser/features/`: Pluggable feature modules (bookmarks, history, adblock, etc.).
