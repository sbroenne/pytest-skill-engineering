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

## Cross-Agent Context

**Verbal's parallel work (same session):** Upgraded Copilot SDK 0.1.25 → 0.2.0 with breaking API changes. See Verbal's history for detailed migration notes on SubprocessConfig, create_session(**kwargs), send_and_wait(str), and snake_case ToolResult fields. The new `typer` and `shellingham` transitive deps added by this project are now in uv.lock.

**Hockney's parallel work (same session):** Integration test verification found 4 compatibility issues during test run; all fixed. 105/105 tests now passing. See Hockney's history for detailed fix patterns.
