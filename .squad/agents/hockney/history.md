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

### 2026-03-21: Comprehensive Test Suite Review

**Context:** Full audit of test coverage, harness design, fixture patterns, and gaps across all test directories.

**Test Inventory:**
- Pydantic integration: 12 files, 43 async test methods + 12 sync loading tests = ~72 test invocations with parametrize
- Copilot integration: 6 files, 25 async test methods = ~33 test invocations with parametrize
- Fixtures/scenarios: 10 scenario files for report generation
- Showcase: 1 hero report test file
- Visual: 1 Playwright file (15 DOM tests for agent selector)
- Unit: 33 files (pure logic only, no LLM mocking)

**Coverage Strengths:**
- All 12 pydantic features have dedicated test files (basic→custom agents)
- Copilot tests cover 6 key areas: file ops, model comparison, instructions, skills, events, custom agents
- Session tests (`test_06_sessions.py`) have excellent "Paris trip" context-retention proof
- Clarification detection has full level coverage (INFO/WARNING/ERROR)
- Scoring tests use real rubric dimensions with meaningful thresholds
- Custom agent tests cover loading, filtering, identity tracking, and LLM execution
- A/B server tests parametrize prompt quality to show tool description impact
- Fixture JSONs all generated (not hand-edited), dated Feb 25

**Coverage Gaps Found (by severity):**

🔴 Critical:
1. **No negative test for `result.success == False`** — Pydantic tests always expect success. No test deliberately triggers a failure and asserts on the failure path.
2. **No timeout/retry testing** — Engine retry logic and rate limiting exist in code but are never exercised in integration tests.
3. **Copilot `from_copilot_config()` factory** — Completely untested. Can't load config from disk.
4. **Copilot error event handling** — `session.error`, `subagent.failed` events never triggered in tests.
5. **Copilot permission system** — `auto_confirm=False` never tested; permission flow completely uncovered.

🟡 Important:
6. **Copilot missing feature parity** — No sessions (test_06), no clarification (test_07), no scoring (test_08), no CLI servers (test_09), no A/B servers (test_10), no iterations (test_11). Copilot covers 6/12 of pydantic's feature set.
7. **4 of 5 Copilot personas untested** — Only `VSCodePersona` (default) used. `HeadlessPersona`, `CopilotCLIPersona`, `ClaudeCodePersona` never instantiated.
8. **CopilotResult utility methods** — `tool_call_count()`, `tool_calls_for()`, `files_matching()` never called in copilot tests.
9. **Mixed sync/async in integration tests** — `test_05_skills.py` and `test_12_custom_agents.py` have synchronous loading tests in integration directory. These are really unit tests that happen to live with integration tests.
10. **CLIServer discovery edge cases** — `discover_help=True` failure path, working directory, invalid shell param untested.

🟢 Nice-to-have:
11. **Harness state leakage** — Banking/todo servers are module-scoped but stateful. No explicit reset between test classes within same module.
12. **Todo parameter naming mismatch** — Schema uses `"list"` but code uses `list_name`. Works via manual mapping but confusing.
13. **Banking float precision** — No rounding rules for currency amounts. Could cause micro-cent drift.
14. **Non-deterministic harness state** — UUID-based task IDs and `datetime.now()` timestamps make test replay non-deterministic.

**Harness Design Assessment:**
- Banking: Well-designed, 6 tools with clear enum constraints, good error messages. Missing: transaction limit validation, same-account transfer guard, float rounding.
- Todo: Functional, 7 tools with examples in descriptions. Missing: duplicate detection, timestamps, search capability. Parameter naming inconsistency (`list` vs `list_name`).
- Both: Mixed return types from MCP layer (JSON on success, plain string on error) could confuse LLMs.

**Fixture Design Assessment:**
- Module-scoped server fixtures are correct for expensive startup
- `eval_run` fixture cleanly manages session state
- Pydantic conftest is minimal (inherits from parent) — good
- Copilot conftest has proper auth probing with `integration_judge_model` — good
- No fixture leakage detected between test files

**Pattern Observations:**
- All integration tests use `Eval.from_instructions()` pattern consistently
- Parametrize decorators used correctly for model/prompt comparison
- `llm_assert` fixture used in ~5 test files for semantic assertions
- `llm_score` + `assert_score` used only in test_08_scoring.py
- Custom agent tests properly test both loading (sync) and execution (async)
- Copilot tests use `tmp_path` for workspace isolation — good practice

### Full Repo Review (2026-03-21)

Completed comprehensive test suite review as part of 5-agent session. Filed 10 findings (1 critical, 5 important, 4 nice-to-have) covering test coverage gaps, harness design issues, and missing feature parity. **Critical:** Add negative tests for result.success==False path verification. **Important:** 6 copilot feature areas lack coverage (sessions, clarification, scoring, CLI, A/B, iterations); mixed sync/async in integration directory; harness inconsistencies (return types, parameter naming). All fixtures and patterns well-designed; gaps are in test scenarios and feature parity, not architecture.

### Negative Tests Added (2026-03-21)

**Context:** Critical gap from repo review — zero tests ever expected `result.success == False`. Added 4 negative tests to `test_01_basic.py` as `TestBankingNegative` class.

**Tests written:**
1. `test_tool_not_called_assertions` — Verifies `tool_was_called()` returns False for uncalled and nonexistent tools after a simple balance check. Confirms `transfer`, `withdraw`, `deposit` are not triggered. Also tests `tool_call_count()` returns 0 for nonexistent tools.
2. `test_out_of_scope_request` — Sends "Book me a flight to Paris" to a banking agent. Asserts agent completes (success=True) but does NOT use any tools or fabricate capabilities. Uses `llm_assert` to verify the response indicates inability.
3. `test_max_turns_exhausted` — Sets `max_turns=1` with a complex 4-step prompt. Engine hits `UsageLimitExceeded` → `success=False`. **This is the first test in the suite that expects `result.success == False`.**
4. `test_nonexistent_account_graceful` — Asks for "investment account" balance. Tool schema enums constrain to checking/savings. Verifies agent informs user correctly. Uses `llm_assert` for semantic check.

**Key insight:** `success=False` only occurs via exception paths (timeout, `UsageLimitExceeded`). The `adapt_result()` function in `pydantic_adapter.py` always sets `success=True`. So to get a genuine failure, you need to trigger the exception handler — `max_turns=1` with a tool-calling prompt is the cleanest way.

**Collection result:** 73 tests total (up from 72 parametrized invocations), all collect cleanly. Not yet executed against real LLM (intentionally — expensive).
