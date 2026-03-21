# Project Context

- **Owner:** sbroenne
- **Project:** pytest-skill-engineering — pytest plugin for testing MCP servers and CLIs with real LLMs. AI analyzes results and tells you what to fix.
- **Stack:** Python 3.11+, PydanticAI, pydantic-evals, MCP, pytest, htpy, async/await, uv, hatch, ruff, pyright
- **Created:** 2026-03-21

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

### 2026-03-21: Dependency Upgrade Integration Test Run & Compatibility Fixes

**Context:** Fenster upgraded ~40 deps (pydantic-ai 1.61→1.70, openai 2.21→2.29, github-copilot-sdk 0.1→0.2), Verbal upgraded Copilot SDK with breaking API changes.

**Test Results:**
- Pydantic integration: 12 files, 72 tests — **ALL PASSED** after fixes
- Copilot integration: 6 files, 33 tests — **ALL PASSED** after fixes
- Total: **105/105 passed** (0 flaky after code fixes)

**Issues Found & Fixed:**
1. **Azure cross-tenant auth** (`pydantic_adapter.py`): `DefaultAzureCredential` ignores `AZURE_TENANT_ID` env var for `get_bearer_token_provider`. Built custom token provider that passes `tenant_id` to `credential.get_token()`. The resource moved to MCAPS tenant `16b3c013-d300-468d-ac64-7eda0820b6d3`.
2. **Subagent event field rename** (`events.py`): Copilot SDK 0.2.0 uses `agent_name` instead of `eval_name` in subagent event data. Added `_resolve_subagent_name()` helper.
3. **Subagent detection from tool calls** (`events.py`): SDK doesn't always emit `subagent.*` events when `runSubagent` is called natively. Added fallback: detect subagent invocations from `tool.execution_start` events when tool name is `runSubagent` or `task`.
4. **PydanticAI deprecation** (`engine.py`): `FunctionToolset.tool()` for plain functions deprecated in 1.70. Changed to `tool_plain()`.

**Key Patterns:**
- `AZURE_TENANT_ID` must be set for cross-tenant Azure auth. `DefaultAzureCredential` with `additionally_allowed_tenants=["*"]` + explicit `tenant_id` in `get_token()` is the workaround.
- Copilot SDK `Data` object uses `agent_name` for subagent events, `agentSlug` in tool arguments.
- Tests that rely on LLM subagent dispatch can be flaky — `test_docs_writer_agent_creates_readme` failed once, passed on retry.
- Always run with default `addopts` (not `-o "addopts="`) to get proper `--aitest-summary-model` for `llm_assert`.

**Decisions:**
- `AZURE_TENANT_ID` env var is now required for integration tests
- Document in README/CONTRIBUTING (Verbal)
- Consider adding to CI env vars if/when CI is set up (Fenster)
