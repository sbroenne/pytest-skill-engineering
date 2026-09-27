---
description: "Write your first CopilotEval, attach MCP servers, and compare system prompts, skills, and custom agents."
---

# Getting Started

pytest-skill-engineering uses the real GitHub Copilot coding agent to test AI behavior.

## What you are testing

You are not re-testing your Python functions. You are testing whether Copilot can:

- discover the right tool
- choose the right arguments
- recover from errors
- follow the right system prompt
- route work to the right custom agent

## Install, initialize, and diagnose

```bash
uv add pytest-skill-engineering
gh auth login --hostname github.com
uv run pytest-skill-engineering init
uv run pytest-skill-engineering doctor
```

In CI, set `GITHUB_TOKEN` or `GH_TOKEN` instead. The runtime selects
`GITHUB_TOKEN` first when both are set.

`init` makes two explicit changes:

- creates `tests/test_copilot_eval.py`
- adds `asyncio_mode`, HTML output, JSON output, and the `gpt-5.6-sol` analysis
  model to `[tool.pytest.ini_options]`
- adds explicit `gpt-5.6-sol` cost rates to `pricing.toml` while preserving an
  existing rate

It refuses to overwrite the starter test or replace conflicting pytest report
settings. Resolve the named conflict yourself and run the command again.

## Run the first eval

```bash
uv run python -m pytest tests/test_copilot_eval.py -v
```

This starts a real Copilot session and may consume premium requests. A successful
run proves that:

- authentication works
- `gpt-5.6-sol` is available
- Copilot can start and use an MCP server
- pytest captures the execution
- required AI analysis can render a report

Open `aitest-reports/report.html` and find the `todo-add_task` tool call. Raw
execution evidence is in `aitest-reports/results.json`.

## Adapt it to your project

Open the generated test and replace:

1. `TODO_MCP` with your MCP server configuration.
2. The system prompt in `instructions`.
3. `"Add a task to buy groceries"` with a real user prompt.
4. `tool_was_called("todo-add_task")` with the behavior your interface must produce.

The complete generated file is also available in
[`examples/quickstart`](https://github.com/sbroenne/pytest-skill-engineering/tree/main/examples/quickstart).

## What to compare next

- [System prompts](system-prompts.md)
- [Skills](skills.md)
- [Custom agents](custom-agents.md)
- [Comparing configurations](comparing.md)
- [Multi-turn sessions](sessions.md)
- [Troubleshooting](troubleshooting.md)
