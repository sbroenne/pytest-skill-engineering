# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

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
