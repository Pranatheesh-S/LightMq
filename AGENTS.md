# Canonical AI Agent Development Instructions: LightMq Browser

## 1. Project Overview & Identity
- **Project**: LightMq — Scalable Desktop Web Browser
- **Stack**: Python 3.10+, PySide6 (Qt 6.5+), Qt WebEngine (Chromium engine)
- **Architecture**: Modular `src/` layout, Event-driven communication, isolated WebEngine & DevTools layers.

## 2. Universal AI Agent Memory System
All coding agents (Codex, Claude Code, Antigravity, Cursor, etc.) must utilize the centralized memory in `.ai/memory/`.

### Memory Files & Responsibilities:
1. `.ai/memory/PROJECT.md` — Canonical project scope, architectural layers, and tech stack.
2. `.ai/memory/STATUS.md` — Active development phase, current milestone, and blockers.
3. `.ai/memory/COMPLETED.md` — Verified completed tasks and historical milestones.
4. `.ai/memory/TODO.md` — Comprehensive backlog, prioritized implementation checklist.
5. `.ai/memory/DECISIONS.md` — Architecture Decision Records (ADRs) with rationale.
6. `.ai/memory/SESSION_LOG.md` — Chronological log of every agent session.

### Agent Memory Protocol:
- **At Session Start**: Read `.ai/memory/STATUS.md`, `.ai/memory/TODO.md`, and `.ai/memory/PROJECT.md`.
- **During Task Execution**: Respect architecture boundaries, maintain separation of concerns, and avoid circular dependencies.
- **At Session End**:
  - Update `.ai/memory/STATUS.md` with latest phase/state.
  - Move finished items from `.ai/memory/TODO.md` to `.ai/memory/COMPLETED.md`.
  - Document any architectural decisions in `.ai/memory/DECISIONS.md`.
  - Append a concise summary entry in `.ai/memory/SESSION_LOG.md`.

## 3. Architecture Rules
- **Layer Separation**: UI (`src/browser/ui/`) must never directly invoke raw Chromium internals; interact through `core/` abstractions or `webengine/` facades.
- **Qt WebEngine Isolation**: `src/browser/webengine/` isolates `QWebEngineView`, `QWebEnginePage`, and `QWebEngineProfile`.
- **DevTools Subsystem**: Chromium Developer Tools (Inspect Element, DOM, Network, Console) belong exclusively in `src/browser/devtools/`.
- **Event Bus Decoupling**: Cross-module notifications must use `src/browser/core/event_bus.py` rather than direct object references.
- **Feature Modularity**: Each feature in `src/browser/features/` must be self-contained and independently toggleable.
- **Strict Scope**: Do not write monolithic files or bypass established abstractions.

## 4. Coding Standards
- Type hints on all functions and methods.
- Google-style or Sphinx docstrings.
- Ensure all Qt GUI interactions occur on the main thread; long-running operations must use `QThread` or worker pools.
