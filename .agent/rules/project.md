# Antigravity Agent Rules — LightMq Browser

## Architectural Integrity
- Follow `AGENTS.md` as the canonical reference.
- Consult `.ai/memory/PROJECT.md` for project scope and technical stack.
- Check `.ai/memory/STATUS.md` and `.ai/memory/TODO.md` before starting any task.
- Update `.ai/memory/COMPLETED.md` and `.ai/memory/SESSION_LOG.md` upon task completion.

## Modularity & Separation of Concerns
1. **No Circular Imports**: Keep `core/`, `ui/`, `webengine/`, and `devtools/` isolated. Use `core/event_bus.py`.
2. **Encapsulate WebEngine**: Never instantiate unconfigured `QWebEngineView` directly in UI widgets. Use `webengine/web_view.py`.
3. **Preserve Existing Code**: Never overwrite existing verified features or delete user configurations.
