# Project Context

- **Owner:** sbroenne
- **Project:** pytest-skill-engineering — pytest plugin for testing MCP servers and CLIs with real LLMs. AI analyzes results and tells you what to fix.
- **Stack:** Python 3.11+, PydanticAI, pydantic-evals, MCP, pytest, htpy, async/await, uv, hatch, ruff, pyright
- **Created:** 2026-03-21

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

### 2026-07-23 — Copilot SDK 0.1.25 → 0.2.0 Upgrade

**Breaking changes migrated:**
1. **`CopilotClient` constructor**: `options=CopilotClientOptions(...)` → `CopilotClient(SubprocessConfig(...), auto_start=True)`. `CopilotClientOptions` is gone; replaced by `SubprocessConfig` (from `copilot` top-level).
2. **`create_session()` API**: No longer takes a single dict. Now takes keyword arguments. `on_permission_request` is **required** (keyword-only). This means `build_session_config()` dicts must be unpacked: `create_session(**config)`.
3. **`send_and_wait()` signature**: Takes `prompt: str` directly, not `{"prompt": prompt}` dict.
4. **`ToolResult` fields**: Renamed from camelCase to snake_case — `textResultForLlm` → `text_result_for_llm`, `resultType` → `result_type`.
5. **Permission handling**: `PermissionHandler.approve_all` is the built-in approved handler. Old pattern of returning `{"kind": "approved"}` dicts is replaced by `PermissionRequestResult(kind="approved")`.
6. **Imports moved**: `Tool`, `ToolResult`, `ToolInvocation`, `SubprocessConfig` now live at `copilot` top-level, not `copilot.types`.

**What still works:**
- `session.send_and_wait()` still exists (not removed, just signature changed)
- `session.session_id` still works as an instance attribute
- `session.on(handler)` event subscription is unchanged
- `SessionEvent` type and `.type.value` / `.data` field access is unchanged
- `Tool(name=, description=, handler=, parameters=)` constructor is compatible
- `ToolInvocation` is a TypedDict — `.get("arguments")` pattern still works
- `CustomAgentConfig` is a TypedDict — passing plain dicts still works

## Cross-Agent Context

**Fenster's parallel work (same session):** Ran `uv lock --upgrade` and brought all ~40 dependencies to latest compatible versions. Key: pydantic-ai 1.61→1.70, openai 2.21→2.29, ruff 0.15.1→0.15.7. The `github-copilot-sdk 0.1→0.2` bump that necessitated this file's migration was part of Fenster's broader upgrade. All static analysis passed clean. See Fenster's history for full transitive dep list.
