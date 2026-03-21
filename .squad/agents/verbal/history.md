# Project Context

- **Owner:** sbroenne
- **Project:** pytest-skill-engineering — pytest plugin for testing MCP servers and CLIs with real LLMs. AI analyzes results and tells you what to fix.
- **Stack:** Python 3.11+, PydanticAI, pydantic-evals, MCP, pytest, htpy, async/await, uv, hatch, ruff, pyright
- **Created:** 2026-03-21

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

### 2026-03-21 — Copilot SDK 0.1.25 → 0.2.0 Upgrade

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

**Test verification:** 33 copilot integration tests all passed after migration. No test code changes needed.

## Cross-Agent Context

**Fenster's parallel work (same session):** Ran `uv lock --upgrade` and brought all ~40 dependencies to latest compatible versions. Key: pydantic-ai 1.61→1.70, openai 2.21→2.29, ruff 0.15.1→0.15.7. The `github-copilot-sdk 0.1→0.2` bump that necessitated this file's migration was part of Fenster's broader upgrade. All static analysis passed clean. See Fenster's history for full transitive dep list.

**Hockney's parallel work (same session):** Integration test verification of combined upgrades. Found that this migration required additional compatibility fixes: subagent event field rename (`agent_name` in SDK 0.2), and event detection fallback from `tool.execution_start` when native subagent events missing. See Hockney's history for detailed fixes. 105/105 integration tests now passing.

### 2026-03-21 — Post-0.2.0 Deep Review (Verbal)

**🔴 CRITICAL BUG FIXED: `ToolInvocation.get()` broken in SDK 0.2.0**
- `ToolInvocation` changed from TypedDict (dict subclass) to a regular class in 0.2.0
- `.get("arguments")` raises `AttributeError` — must use `.arguments` (attribute access)
- Fixed in 2 files: `copilot/model.py:328`, `copilot/personas.py:338`
- Bug survived initial migration because these paths only execute when CopilotModel is used as a PydanticAI provider with tools (model.py) or when the polyfill subagent dispatch handler is invoked (personas.py) — neither path was exercised by existing integration tests

**CORRECTION to earlier learning:** The entry "ToolInvocation is a TypedDict — .get('arguments') pattern still works" was **wrong** for SDK 0.2.0. `ToolInvocation` is now a regular class (`__bases__ = (object,)`), not a dict subclass. Attribute access (`.arguments`, `.tool_name`, etc.) is the correct pattern.

**SDK 0.2.0 API facts verified:**
- `ToolInvocation`: regular class, NOT TypedDict. Use `.arguments`, `.tool_name`, `.tool_call_id`, `.session_id` as attributes
- `SystemMessageAppendConfig`/`SystemMessageReplaceConfig`: still TypedDicts (dict subclasses). Plain dicts work at runtime
- `CustomAgentConfig`: still TypedDict. Plain dicts work
- `create_session()`: now accepts `on_event` callback kwarg directly (alternative to `session.on()`)
- SDK now has 70 event types (up from ~38 in 0.1). EventMapper handles 17 — the rest are silently ignored (safe)
- New notable events: `permission.requested`/`.completed`, `session.task_complete`, `subagent.deselected`, `elicitation.*`, `tool.execution_partial_result`

**Architecture assessment (all ✅):**
- Persona system is well-designed — clean hierarchy, polyfill injection only when needed
- CopilotModel singleton client handles event loop changes correctly
- Runner retry logic for transient errors is solid
- CopilotEval is properly separated from pydantic Eval
- Provider routing (`copilot/` prefix) is clean
