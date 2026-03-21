# Project Context

- **Owner:** sbroenne
- **Project:** pytest-skill-engineering — pytest plugin for testing MCP servers and CLIs with real LLMs. AI analyzes results and tells you what to fix.
- **Stack:** Python 3.11+, **Copilot SDK only** (PydanticAI removed 2026-03-21), MCP, pytest, htpy, async/await, uv, hatch, ruff, pyright
- **Created:** 2026-03-21
- **Current Phase:** Copilot-only pivot complete. Plugin system design phase.

## Cross-Agent Context

### 2026-03-21 — Copilot Pivot Session (COMPLETE)

**Directive:** User decision (2026-03-21T10:35Z) to remove PydanticAI harness and make Copilot SDK the **only** eval infrastructure.

**What Hockney did in this session:**
- Removed `tests/integration/pydantic/` directory (12 test files, ~72 tests)
  - test_01_basic.py, test_02_models.py, test_03_prompts.py, test_04_matrix.py, test_05_skills.py, test_06_sessions.py, test_07_clarification.py, test_08_scoring.py, test_09_cli.py, test_10_ab_servers.py, test_11_iterations.py, test_12_custom_agents.py
- Deleted fixture scenarios (13 files, ~68KB) that generated test JSON reports
- Updated `tests/integration/copilot/conftest.py` for isolated Copilot-only testing
- Updated `tests/integration/conftest.py` to only shared server fixtures (Banking, Todo MCP servers)
- Commits: `b2098ef`, `ce68c7c`

**BLOCKER discovered:** `copilot/model.py` still has PydanticAI imports (lines 21–38):
```python
from pydantic_ai.messages import (ModelMessage, ModelRequest, ...)
from pydantic_ai.models import Model
```
- **Impact:** Cannot run ANY tests — pytest plugin fails to load with `ModuleNotFoundError: No module named 'pydantic_ai'`
- **Root cause:** Fenster listed file as "needs rewrite" but deleted pydantic-ai dependency without removing file
- **Options:** 1) Delete file entirely, 2) Rewrite to not import pydantic_ai, 3) Re-add pydantic-ai (reverses pivot)
- **Flagged to:** Fenster/Verbal (src/ code, outside Hockney's charter)

**Cross-team parallel work:**
- **Fenster:** Removed 6 core PydanticAI files, deleted dependencies
- **Verbal:** Rewrote 6 modules to use Copilot SDK
- **McManus:** Docs rewrite (IN PROGRESS, blocked on copilot/model.py fix)

---

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

### 2026-03-21: Post-Fix Verification Run (McManus + Fenster + Hockney changes)

**Context:** Three agents made significant changes in the same session:
- **McManus:** XSS fixes (nh3 sanitization), removed legacy alias, removed duplicate CSS, added CSS utilities
- **Fenster:** serialize_dataclass deep-copy fix, rate limiter reset, Azure model cache fix, slots=True on 9 dataclasses, frozen=True on Provider/Prompt, plugin.py decomposition (→ plugin_recording.py, plugin_options.py, plugin_report.py), YAML silent swallow fix, deprecated asyncio.get_event_loop() fix
- **Hockney (earlier):** 4 negative test cases in TestBankingNegative class

**Verification Results:**
- Lint (ruff check): **CLEAN** — 0 issues
- Format (ruff format): **CLEAN** — 135 files unchanged
- Type check (pyright): **CLEAN** — 0 errors, 0 warnings
- Test collection: **73 tests collected** in 0.02s — plugin decomposition did NOT break imports
- Integration tests: **73/73 PASSED** across all 12 test files, zero failures, zero flaky

| File | Tests | Result | Duration |
|------|-------|--------|----------|
| test_01_basic.py | 7 | ✅ | 2m27s |
| test_02_models.py | 4 | ✅ | 57s |
| test_03_prompts.py | 4 | ✅ | 57s |
| test_04_matrix.py | 8 | ✅ | 1m29s |
| test_05_skills.py | 10 | ✅ | 1m01s |
| test_06_sessions.py | 8 | ✅ | 2m34s |
| test_07_clarification.py | 3 | ✅ | 1m27s |
| test_08_scoring.py | 2 | ✅ | 59s |
| test_09_cli.py | 6 | ✅ | 2m15s |
| test_10_ab_servers.py | 7 | ✅ | 1m40s |
| test_11_iterations.py | 3 | ✅ | 48s |
| test_12_custom_agents.py | 11 | ✅ | 1m18s |

- Report regeneration: **WORKS** — CLI successfully generates HTML from JSON with AI insights

**Issues found:** None. All three sets of changes integrate cleanly. The plugin decomposition (Fenster) was the highest-risk change and test collection confirmed no import breakage. The frozen=True on Provider/Prompt didn't cause any test issues. The XSS sanitization (McManus) runs in the report pipeline which was exercised on every test file run. My negative tests (TestBankingNegative) all passed on first run against real LLMs.

**Note:** `AZURE_TENANT_ID` must be set for all runs (known from previous session). Without it, every test fails with tenant mismatch error.

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

### 2026-03-21: Copilot Feature Parity — Scoring, A/B, Iterations

**Context:** Closing the Copilot integration test feature gap. Created 3 new test files to bring CopilotEval closer to parity with the Pydantic harness.

**Files created:**

1. **`test_08_scoring.py`** — LLM-judged rubric scoring via `llm_score` fixture
   - 3 tests: verbose, direct, and production instruction styles
   - Uses `PROMPT_QUALITY_RUBRIC` with instruction_adherence, code_quality, actionability dimensions
   - `llm_score` is harness-agnostic — operates on `result.final_response` text
   - `assert_score(score, min_pct=0.4)` threshold keeps tests realistic for LLM variability

2. **`test_10_ab_servers.py`** — A/B instruction comparison (not server comparison)
   - 6 tests (3 parametrized × 2 variants: "detailed" vs "minimal")
   - `TestInstructionABComparison`: code creation quality, error handling presence
   - `TestDocumentationQualityImpact`: documentation presence across variants
   - Key difference from pydantic: no MCP servers — compares instruction quality via file output

3. **`test_11_iterations.py`** — Reliability baselines for `--aitest-iterations=N`
   - 3 tests: file creation, code refactoring, multi-file operations
   - Tests are stable enough to run N times without flakiness
   - Refactor test seeds `messy.py` then asserts modification occurred
   - Multi-file test asserts ≥2 `.py` files created

**Validation:**
- ruff check: 0 issues
- ruff format: clean (1 file reformatted during creation)
- pyright: 0 errors, 0 warnings
- Collection: 12 new tests, all collect in 0.02s
- Total copilot tests: 45 (33 existing + 12 new)

**Pattern decisions:**
- `llm_score` works on text, not result objects — no harness coupling needed
- A/B tests use `tmp_path / variant` subdirectories for workspace isolation (same pattern as `test_05_skills.py`)
- Iteration tests avoid stateful assertions (no banking server state) — file existence is idempotent
- All files use `pytestmark = [pytest.mark.copilot]` — no `pytest.mark.integration` (copilot tests are implicitly integration)

**Remaining parity gaps:** Sessions (test_06), Clarification (test_07), CLI servers (test_09). Sessions and CLI may not apply to CopilotEval's architecture.

### Plugin Test Fixtures and Integration Tests (2026-03-21)

**Context:** First-class plugin testing feature. Created test fixtures and integration tests ahead of implementation (Fenster/Verbal building `Plugin`, `load_plugin`, `Eval.from_plugin()`, `CopilotEval.from_plugin()`, `CopilotEval.from_claude_config()`).

**Created — Fixture Directories (8 files):**
- `tests/integration/plugins/banking-plugin/` — plugin.json, agents/banking-advisor.agent.md, skills/financial-literacy/SKILL.md, copilot-instructions.md
- `tests/integration/plugins/claude-project/` — CLAUDE.md, .claude/agents/code-reviewer.md, .claude/skills/python-patterns/SKILL.md, .mcp.json

**Created — Test Files:**
1. `tests/integration/pydantic/test_13_plugins.py` — 12 tests across 4 classes:
   - `TestPluginLoading` (5 sync): metadata parsing, agent/skill discovery, instructions loading, Claude project layout
   - `TestPluginEval` (3 async): `Eval.from_plugin()` with banking server, instruction verification via `llm_assert`, Claude project layout
   - `TestPluginMetadata` (2 sync): PluginMetadata field assertions, default metadata for projects without plugin.json

2. `tests/integration/copilot/test_13_plugins.py` — 10 tests across 4 classes:
   - `TestCopilotPluginLoading` (5 sync): `from_plugin()`, agent discovery, `from_claude_config()`, agent loading, field overrides
   - `TestActiveAgent` (2 sync): `active_agent` field, default None
   - `TestCopilotPluginExecution` (2 async): plugin eval file creation, Claude config eval execution

**API Surface Tested (not yet implemented):**
- `load_plugin(path)` → Plugin object with `.metadata`, `.agents`, `.skills`, `.instructions`
- `PluginMetadata` — name, version, description, author
- `Eval.from_plugin(path, provider=, mcp_servers=, max_turns=)`
- `CopilotEval.from_plugin(path, model=, **overrides)`
- `CopilotEval.from_claude_config(path, model=, **overrides)`
- `CopilotEval.active_agent` field (str | None)

**Validation:** ruff check 0 errors, ruff format clean. Tests will fail at import time until implementation lands — this is intentional.

**Key decisions:**
- Pydantic plugin tests reuse `banking_server` fixture from conftest (plugin defines config, but real MCP server is needed)
- Claude project tests exercise the `.claude/` directory convention (different from `.github/` Copilot convention)
- `active_agent` tests are pure sync since they only test the dataclass field, not SDK dispatch
- Both test files follow existing patterns: `pytestmark`, section separators, docstring-per-method

### 2026-03-21: Copilot Pivot Test Migration (PARTIAL - BLOCKED)

**Context:** After full Copilot pivot (commits `622a508`, `09ff5e1`), tasked to remove pydantic tests and update conftest files for Copilot-only harness.

**Work Completed:**

1. **Deleted `tests/integration/pydantic/`** — 12 test files (~72 tests) that used the deleted `eval_run` fixture and `Eval`/`Provider` classes

2. **Updated `tests/integration/conftest.py`** — Removed all PydanticAI-specific content:
   - Removed `DEFAULT_MODEL`, `BENCHMARK_MODELS`, `DEFAULT_RPM`, `DEFAULT_TPM` constants
   - Removed `.env` loading and `AZURE_API_BASE` workaround (Pydantic-specific)
   - Changed `DEFAULT_MAX_TURNS` from 5 to 25 (Copilot's default)
   - Updated docstring with CopilotEval example
   - Kept `todo_server`, `banking_server` fixtures (unused by copilot tests, but harmless)

3. **Updated `tests/integration/copilot/conftest.py`** — Removed broken imports:
   - Deleted `from pydantic_ai import Agent as Eval`
   - Deleted `from pytest_skill_engineering.execution.pydantic_adapter import build_model_from_string`
   - Deleted `integration_judge_model` fixture (used PydanticAI for model probing)
   - Replaced with simple `_check_github_auth()` autouse fixture

**BLOCKER DISCOVERED:**

**Cannot run ANY tests** — pytest plugin fails to load:
```
ModuleNotFoundError: No module named 'pydantic_ai'
  File "src/pytest_skill_engineering/copilot/model.py", line 21
    from pydantic_ai.messages import (...)
```

**Root cause:** Copilot pivot removed `pydantic-ai` from dependencies but left imports in `src/pytest_skill_engineering/copilot/model.py` (lines 21-38). This file is a PydanticAI Model adapter that depends on the deleted package.

**Impact:** 
- ✗ Cannot run `pytest --collect-only`
- ✗ Cannot verify copilot test imports
- ✗ Cannot run structural validation
- ✗ Blocked from completing charter tasks

**Also found:** `tests/showcase/test_hero.py` imports from deleted `core.eval` module and uses `eval_run` fixture. Hero report generation is broken.

**Action taken:** 
- Documented blocker in `.squad/decisions/inbox/hockney-copilot-pivot-blocker.md`
- Completed structural cleanup (conftest updates, pydantic test removal)
- Cannot proceed further without src/ code fix

**Decision needed:** Fenster/Verbal must either:
1. Delete `copilot/model.py` (if no longer needed)
2. Rewrite `copilot/model.py` without pydantic_ai dependency
3. Fix/delete `tests/showcase/test_hero.py`

**Key learning:** The Copilot pivot is INCOMPLETE. Commits `622a508` and `09ff5e1` removed PydanticAI from dependencies and deleted core modules, but missed updating dependent code in `copilot/` and `tests/showcase/`. The codebase is in a broken state that blocks all testing.
