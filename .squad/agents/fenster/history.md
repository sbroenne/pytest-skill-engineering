# Project Context

- **Owner:** sbroenne
- **Project:** pytest-skill-engineering — pytest plugin for testing MCP servers and CLIs with real LLMs. AI analyzes results and tells you what to fix.
- **Stack:** Python 3.11+, PydanticAI, pydantic-evals, MCP, pytest, htpy, async/await, uv, hatch, ruff, pyright
- **Created:** 2026-03-21

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

### 2026-03-21 — Full dependency upgrade via `uv lock --upgrade`

Key version bumps:
- **pydantic-ai** 1.61.0 → 1.70.0 (minor, no breaking changes detected)
- **pydantic-evals** 1.61.0 → 1.70.0
- **openai** 2.21.0 → 2.29.0
- **litellm** 1.81.13 → 1.82.5
- **github-copilot-sdk** 0.1.25 → 0.2.0 (minor→major-ish, new typer/shellingham deps added)
- **mkdocs-material** 9.6.23 → 9.7.6
- **ruff** 0.15.1 → 0.15.7
- **mistralai** 1.12.3 → 2.1.2 (major bump, transitive dep via pydantic-ai)
- **websockets** 15.0.1 → 16.0 (major bump, transitive)
- **huggingface-hub** 0.36.2 → 1.7.2 (major bump, transitive via litellm)
- **virtualenv** 20.36.1 → 21.2.0 (major bump, transitive via pre-commit)

**Required 3 code compatibility fixes** (see Hockney's parallel work):
1. **Azure cross-tenant auth** — Custom token provider to pass `AZURE_TENANT_ID` to `DefaultAzureCredential.get_token()`
2. **Copilot SDK 0.2.0 subagent events** — Subagent field renamed from `eval_name` to `agent_name`
3. **PydanticAI 1.70 deprecation** — `FunctionToolset.tool()` → `tool_plain()` for plain functions
4. **Subagent detection fallback** — Detect from `tool.execution_start` events when native `runSubagent` doesn't emit subagent events

**Integration test results:** 105/105 tests passed after fixes.

The `griffe`/`griffecli`/`invoke`/`rsa` packages were removed (no longer needed by updated deps).
New transitive deps added: `typer`, `shellingham`, `annotated-doc`, `uncalled-for`, `python-discovery`.

### 2026-03-21 — Deep code review of core/ and execution/

**Reviewed modules:** `core/`, `execution/`, `fixtures/`, `plugin.py`

**Key findings by severity:**

🔴 **Critical:**
- `serialize_dataclass()` (`core/serialization.py:20`) calls `dataclasses.asdict()` which deep-copies ALL fields including `_messages` (list of PydanticAI `ModelMessage` Pydantic models) before discarding them via `_` prefix filter. Wasteful and fragile — `copy.deepcopy` on Pydantic models can fail or be extremely slow for large message histories.
- `reset_rate_limiters()` (`execution/rate_limiter.py:60`) is never called in the plugin lifecycle — only in unit tests. Rate limiter state leaks across sessions in long-lived processes. Should be called in `pytest_sessionfinish`.
- `_build_azure_model` cached with `@functools.lru_cache(maxsize=8)` (`execution/pydantic_adapter.py:72`) — reads env vars at call time but caches result. If `AZURE_TENANT_ID` or `AZURE_API_BASE` changes between calls with same model string, stale credentials are used. Low risk in practice but architecturally unsound.

🟡 **Important:**
- `Provider` (`core/eval.py:121`) is `@dataclass(slots=True)` but not `frozen=True` — violates project convention for immutable config. Same for `Prompt` (`core/prompt.py:12`).
- `_ToolResult` (`execution/pydantic_adapter.py:357`) and `InstructionSuggestion` (`execution/optimizer.py:38`) missing `slots=True`.
- `TestReport` and `SuiteReport` (`reporting/collector.py:13,91`) missing `slots=True`.
- `_extract_frontmatter` in `evals.py:97` silently swallows YAML parse errors — should log warning.
- `_collect_tool_info` in `engine.py:291-300` creates `RunContext(model=None, usage=None)` violating type contract.
- `adapt_result` parameters use bare `list | None` and `Any | None` instead of specific types (`list[MCPPrompt]`, `CustomAgentInfo`).
- `Eval.instruction_files: list[dict[str, Any]]` stores raw dicts instead of typed dataclasses.
- `_shutdown_copilot_model_client` in `plugin.py:759` uses deprecated `asyncio.get_event_loop()` pattern — fragile on Python 3.12+.

🟢 **Nice-to-have / Clean:**
- `from __future__ import annotations` present in ALL 49 source modules — perfect.
- `ClarificationDetection`, `Wait`, `SkillMetadata` correctly use `frozen=True` — good pattern.
- `CLIToolset` cleanup pattern (`__aenter__`/`__aexit__` with partial rollback) is solid.
- `clarification.py` fail-open design is correct — detection never breaks test execution.
- Rate limiter's sliding window implementation is clean and well-documented.
- Error extraction in `plugin.py:488-503` (E-lines from pytest) is a nice touch for AI-friendly reports.
- `_expand_env` lazy header expansion (NOTE on `eval.py:199`) is well-designed for autouse fixtures.

**Key file paths:**
- `core/eval.py` — Eval, Provider, MCPServer, CLIServer, Wait (all core config)
- `core/serialization.py` — serialize/deserialize pipeline (critical bug here)
- `execution/engine.py` — EvalEngine orchestration
- `execution/pydantic_adapter.py` — our types ↔ PydanticAI bridge
- `execution/rate_limiter.py` — global rate limiter registry
- `fixtures/run.py` — eval_run fixture with session continuity
- `plugin.py` — pytest hooks, report generation, CLI options

## Cross-Agent Context

**Verbal's parallel work (same session):** Upgraded Copilot SDK 0.1.25 → 0.2.0 with breaking API changes. See Verbal's history for detailed migration notes on SubprocessConfig, create_session(**kwargs), send_and_wait(str), and snake_case ToolResult fields. The new `typer` and `shellingham` transitive deps added by this project are now in uv.lock.

**Hockney's parallel work (same session):** Integration test verification found 4 compatibility issues during test run; all fixed. 105/105 tests now passing. See Hockney's history for detailed fix patterns.
