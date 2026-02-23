# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

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
