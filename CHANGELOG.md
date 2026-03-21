# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
