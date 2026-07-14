# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added

- **Cache-read tokens now count toward cost estimates** — `estimate_cost()` accepts a `cache_read_tokens` argument priced via an optional per-model `cache_read` rate in `pricing.toml` (defaults to `0.0`, so cost is unchanged unless a rate is configured). `pricing.toml` documents the new field and sets `cache_read` for the two frontier models.
- **Type checking now covers `tests/`** — pyright's `include` was widened from `src` to `["src", "tests"]` (excluding `tests/visual`, which needs the optional `playwright` extra), and CI runs `uv run pyright` (config-driven) instead of a hard-coded `src/` path. Fixed the type errors this surfaced in `test_08_scoring.py`, `test_13_plugins.py`, and the event-mapper test helper.
- **Unit tests for cost estimation** — `tests/unit/test_cost.py` covers the input/output/cache-read arithmetic, unknown-model handling, and the zero-token short-circuit.

### Changed

- **`--strict-markers` is now enforced** — unregistered pytest markers now fail collection instead of silently passing, preventing typo'd markers.
- **Report generation is more resilient** — in `pytest_sessionfinish`, AI-insight and HTML/Markdown rendering are wrapped so a rendering failure no longer discards the already-written JSON, skips the `--aitest-min-pass-rate` gate, or bypasses session cleanup.

### Removed

- **Squad CI workflows** — removed the 11 `squad-*.yml` / `sync-squad-labels.yml` GitHub Actions workflows and the `.squad/templates/workflows/` copies that could regenerate them.

## [0.6.14] - 2026-07-14

### Changed

- **Docs now match the shipped behaviour of `max_turns`** — corrected `CopilotEval` docstrings that claimed the runner "enforces turn limits externally". The runner enforces `timeout_s` as the hard wall-clock limit; `max_turns` is advisory for the top-level session (not hard-enforced mid-run) and is used only to cap subagent turns.
- **`pyproject.toml` version corrected** — bumped from a stale `0.5.7` to track the real release line, and moved the Trove classifier from `Development Status :: 3 - Alpha` to `4 - Beta`.

### Removed

- **Dead clarification-detection code** — `execution/clarification.py` (`check_clarification`) had zero callers anywhere in the codebase and was never wired into the Copilot execution path, yet the feature was advertised in the README. Removed the unused module and the corresponding README claims to keep docs honest (per the project's no-dead-code policy).

### Fixed

- **`.pytest-execution-servers/` scratch directory** — some server tests created this directory in the repo root; it is now git-ignored.

## [0.6.13] - 2026-07-13

### Added

- **Agent Skills spec compliance** — Full support for `agentskills.io` compatibility metadata, `allowed-tools`, `scripts`, and `assets` fields in `SKILL.md`
- **`skill_eval_runner` fixture** — Auto-discovers `evals/evals.json`, runs cases via `copilot_eval`, validates with `llm_assert`, exports skill-creator compatible `grading.json`
- **`MCPServer`, `CLIServer`, `Wait`, `WaitStrategy` dataclasses restored** — Config types for MCP and CLI servers are now importable from `pytest_skill_engineering` directly (`from pytest_skill_engineering import MCPServer, Wait`)
- **`slow` pytest marker** — Expensive benchmarking tests now use `@pytest.mark.slow` instead of `@pytest.mark.skip`

### Changed

- **Integration tests now target frontier flagship models** — `DEFAULT_MODEL` and the parametrized `MODELS` list moved from `gpt-5.5`/`gpt-5.4-mini` to `claude-opus-4.8` and `gpt-5.6-sol` (verified live via `list_models()` on the account and a passing `test_01_basic` run).
- **Upgraded all dependencies** (`uv lock --upgrade`) — 39 packages bumped to their latest compatible versions, including `mcp` 1.27→1.28, `htpy` 25.12→26.5, `pytest` 9.0→9.1, `cryptography` 48→49, and `pymdown-extensions` 10→11 (docs-only).
- **`github-copilot-sdk` 0.3.0 → 1.0.6 (minimum now `>=1.0.6`)** — the 1.x client API is a breaking change. Migrated `runner.py` and `judge.py`: the removed `SubprocessConfig` + `CopilotClient(config, auto_start=True)` is replaced with the keyword-only `CopilotClient(working_directory=…, log_level=…, github_token=…)`, and the permission handler now returns `PermissionDecisionApproveOnce()` (was `PermissionRequestResult(kind="approve-once")`). Session, event-mapping, and persona tool APIs were verified unchanged.
- **`copilot/` module now fully type-checked** — Removed `exclude = ["src/pytest_skill_engineering/copilot"]` from pyright config; all modules are type-checked
- **Auth documentation** — `.env.example` updated to document `gh auth login` / `GITHUB_TOKEN` (LiteLLM references removed)

### Fixed

- **`MCPServerProcess.start()` resource leak** — when `Wait.for_tools(...)` failed (required tools missing after discovery), `start()` raised `ServerStartError` without closing the already-opened `AsyncExitStack`/`ClientSession`, leaking the underlying subprocess/connection. Now cleans up in both the `ServerStartError` and generic-exception branches. Caught by the new `execution/servers.py` unit tests.
- **Cost estimation wired up (was dead code)** — `CopilotEval` now computes `cost_usd` from captured token usage via `execution.cost.estimate_cost()` and `pricing.toml`, instead of hardcoding `0.0`. The report's "⚠️ Incomplete Pricing Data" warning now reads the live `models_without_pricing` set (previously shadowed by a local empty set), so models missing from `pricing.toml` are correctly surfaced in AI analysis. Cleaned up stale `litellm`/"SDK does not expose token usage" comments in `pricing.toml` and `insights.py`. Pre-filled `pricing.toml` with vendor list pricing for the new default test models (`claude-opus-4.8`, `gpt-5.6-sol`) so cost estimates render out of the box; verified `$0.12`/test locally.
- **Broken docs examples** — `docs/getting-started/sessions.md` used a nonexistent `@pytest.mark.session` marker with `CopilotEval` (only ever valid on the removed PydanticAI harness); rewritten to the real context-in-prompt pattern. `docs/explanation/evals.md` used a nonexistent `CopilotEval(skill=...)` param; fixed to `skill_directories=[str(skill.path)]`. `CONTRIBUTING.md` referenced the deleted `tests/integration/pydantic/` directory and a dual-harness "Copilot SDK First / Test Both Harnesses" section that no longer applies.
- **`SECURITY.md`** — replaced a nonexistent maintainer email with GitHub's private vulnerability reporting link; replaced a stale "0.1.x supported" version table with a generic latest-release policy.
- **GitHub Actions hardening** — pinned all core workflow actions (`ci`, `integration`, `hero-tests`, `release`, `codeql`, `docs`, `dependency-review`, `dependabot-auto-merge`, `auto-release`, `stale`) to commit SHAs instead of mutable tags; added missing workflow-level `permissions: contents: read` to `ci.yml` and `release.yml`; replaced a hardcoded Azure endpoint in `hero-tests.yml` with a `secrets.AZURE_OPENAI_ENDPOINT` reference.
- **Removed dead hover-popup report feature** — `showDiagramHover`/`hideDiagramHover`/`keepDiagramHover` in `scripts.js` and the matching markup in `overlay.py`/`report.css` had no callers anywhere and used `innerHTML` inconsistently with the live `showDiagram()` path; deleted rather than patched.
- **Replaced placeholder assertion** in `tests/visual/test_04_agent_selector.py::test_mermaid_renders` (`assert True`) with a real check that no `console`/`pageerror` events fire while the Mermaid diagram renders.
- **New unit test coverage** for four previously-untested core modules: `plugin_options.py`, `plugin_recording.py`, `plugin.py` (hook implementations), and `execution/servers.py` — 89 new tests total (`tests/unit/test_plugin_options.py`, `test_plugin_recording.py`, `test_plugin_hooks.py`, `test_execution_servers.py`).

### Known Issues

- **`premium_requests` is always 0.0** — investigated the stale `session.usage_info` premium-request read (that event no longer carries the field in SDK 1.0.6; it's context-window stats only) and added a schema-correct `session.shutdown` handler for it. However, verified live that `session.shutdown` is never delivered to `session.on()` listeners via the `client.stop()` teardown this runner uses — no event in a real session carries any premium-related field. This is an upstream SDK gap, not something fixable from this codebase today; see the docstring on `EventMapper._handle_session_shutdown` for details and what to check if upgrading `github-copilot-sdk` later.
- **Stale `copilot.types.CustomAgent` and `SkillCompatibility` removed** from API reference docs
- **Release version selection** — fixed edge case in version selection logic
- **Documentation** — Removed all `@pytest.mark.session` references from docs and instructions (multi-turn sessions were removed in v0.3.0; docs still referenced them)
- **Project structure in `copilot-instructions.md`** — `copilot/engine.py` → `copilot/runner.py`, removed non-existent `copilot/servers.py` and `copilot/skill_tools.py`, fixed fixture paths

## [0.3.0] — 2026-03-21

### ⚠️ Breaking Changes

This release completes the **Copilot pivot** — PydanticAI has been fully removed. CopilotEval is now the only eval harness. All tests must use the real GitHub Copilot coding agent via the `github-copilot-sdk`.

- **Removed PydanticAI dependency** — `Eval`, `Provider`, `MCPServer`, `CLIServer`, `Wait` types removed
- **Removed `eval_run` fixture** — use `copilot_eval` instead
- **Removed all PydanticAI dependencies** — `pydantic-ai`, `pydantic-evals`, `litellm` removed
- **`github-copilot-sdk` is now required** (was optional `[copilot]` extra)
- **Removed `CopilotModel`** — PydanticAI model adapter no longer needed
- **Removed multi-turn session support** — `@pytest.mark.session` pattern removed (CopilotEval uses context-in-prompt)
- **Removed all PydanticAI integration tests** — `tests/integration/pydantic/` deleted

### Added

- **Agent Skills spec compliance** ([agentskills.io](https://agentskills.io)) — Full support for compatibility, metadata, allowed-tools fields
- **skill-creator eval automation** — `skill_eval_runner` fixture auto-discovers `evals/evals.json`, runs cases via CopilotEval, validates with `llm_assert`, exports skill-creator compatible `grading.json`
- **skill-creator eval bridge** — Import evals from `evals/evals.json`, export grading results to skill-creator format
- **Scripts and assets directory support** per Agent Skills spec — package Python scripts, prompts, and resources with skills
- **Shared Copilot SDK judge utility** (`copilot/judge.py`) — unified LLM judge for assertions, scoring, and clarification detection
- **LLM assertions rewritten for Copilot SDK** — `llm_assert`, `llm_score`, clarification detection all use github-copilot-sdk

### Changed

- **CopilotEval is THE eval harness** — no alternative harnesses
- **Install command** — `uv add pytest-skill-engineering` (no `[copilot]` extra needed)
- **AI insights generation** — rewritten to use Copilot SDK instead of PydanticAI
- **Cost estimation** — now uses `pricing.toml` only (litellm pricing removed)
- **Documentation** — fully rewritten for Copilot-only workflow

### Removed

- **PydanticAI execution engine** — `execution/engine.py`, `execution/pydantic_adapter.py`, `execution/cli_toolset.py`, `execution/optimizer.py`
- **PydanticAI fixtures** — `eval_run`, `skill_factory` removed
- **Multi-turn sessions** — `@pytest.mark.session` no longer supported
- **Showcase/hero report tests** — to be rewritten for Copilot harness
- **Fixture scenario files** — all PydanticAI-based fixture generation removed
- **Dual harness infrastructure** — plugin detection of mixed harness usage removed

## v0.2.0

### Added

- **Copilot SDK Feature Parity** — CopilotEval now covers 11 of 12 feature areas, up from 5:
  - Multi-turn sessions (context-in-prompt pattern — SDK has no stateful sessions)
  - Clarification detection (substring + semantic assertion)
  - LLM-based scoring (`llm_score` + `ScoringDimension`)
  - CLI tool testing (Copilot's native shell tools)
  - A/B instruction variant comparison
  - Iteration reliability testing (`--aitest-iterations=N`)
- **Negative test cases** — `TestBankingNegative` class covers error handling, ambiguous prompts, impossible requests

### Changed

- **Copilot SDK 0.1.25 → 0.2.0** — Breaking API migration:
  - `CopilotClient` → `SubprocessConfig`
  - `create_session()` keyword arguments
  - `send_and_wait()` plain string signature
  - `ToolResult` snake_case fields
  - `PermissionHandler.approve_all`
  - `ToolInvocation` class (replaces TypedDict)
- **Pydantic AI 1.61 → 1.70** — `tool_plain` deprecation fix
- **Plugin decomposition** — `plugin.py` split from 1073 → 590 lines into focused submodules: `plugin_options.py`, `plugin_recording.py`, `plugin_report.py`
- **Dataclass conventions** — All `@dataclass` now use `slots=True`; immutable configs (`Provider`, `Prompt`) use `frozen=True`
- **Azure auth cache** — Now keyed on `(model, endpoint, tenant_id, api_key)` instead of just model string
- **Serialization performance** — `serialize_dataclass` skips private fields before deep-copy
- **Rate limiter lifecycle** — Reset on session finish to prevent cross-session leaks

### Security

- **HTML report sanitization** — Added `nh3>=0.3.3` to fix 3 XSS vectors:
  - Mermaid `securityLevel` changed from `loose` to `strict`
  - `innerHTML` → `textContent` in diagram hover popup
  - LLM-generated markdown sanitized with explicit HTML allowlist
- **YAML error handling** — System prompt loader no longer silently swallows parse errors

### Dependencies

- ~40 packages upgraded via `uv lock --upgrade`
- `nh3>=0.3.3` added for HTML sanitization
- `github-copilot-sdk>=0.2.0` (optional `[copilot]` extra)

## v0.1.0

### Overview

**pytest-skill-engineering** supersedes [`pytest-aitest`](https://github.com/sbroenne/pytest-aitest) with full Skill Engineering support for all six VS Code / GitHub Copilot SE concepts.

### Added

- **Full Skill Engineering pipeline** covering all six SE concepts:
  1. MCP server tools
  2. Prompt templates (`.prompt.md`)
  3. Agent definitions (`.agent.md` / `.claude/agents/`)
  4. Skills (`SKILL.md` + references)
  5. Multi-eval orchestration
  6. Copilot Extension evaluation (`CopilotEval`)

- **`Eval.from_instructions(name, instructions, *, provider, **kwargs)`** factory method — replaces the raw `Eval(system_prompt=..., system_prompt_name=...)` pattern with a named, documented eval. Eval identity (name) flows through the entire pipeline including HTML reports, JUnit XML, and AI summaries.

- **`load_custom_agents(directory)`** — loads `.agent.md` files from a directory and returns a list of dicts with `name`, `prompt`, and `description` keys. Replaces `load_system_prompts()`.

- **`CopilotEval`** (replaces `CopilotAgent`) — evaluation harness for GitHub Copilot Extensions and VS Code Chat participants.

- **`copilot_eval`** fixture (replaces `copilot_run`) and **`eval_run`** fixture (replaces `aitest_run`) for running evaluations.

### Renamed (from pytest-aitest)

| Old name (pytest-aitest) | New name (pytest-skill-engineering) |
|--------------------------|--------------------------------------|
| `Agent` | `Eval` |
| `AgentResult` | `EvalResult` |
| `aitest_run` fixture | `eval_run` fixture |
| `copilot_run` fixture | `copilot_eval` fixture |
| `CopilotAgent` | `CopilotEval` |

### Deprecated

- **`load_system_prompts(directory)`** — use `load_custom_agents(directory)` instead. `load_system_prompts` returns `dict[str, str]`; `load_custom_agents` returns `list[dict]` with `name`, `prompt`, and `description` keys.

- **`Eval(system_prompt=..., system_prompt_name=...)`** constructor pattern — use `Eval.from_instructions(name, instructions, *, provider)` instead.

### Migration

See [`docs/migration.md`](docs/migration.md) for a complete migration guide from `pytest-aitest`.
