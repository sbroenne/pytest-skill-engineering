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

`init` makes three explicit changes:

- creates `tests/test_copilot_eval.py`
- adds `asyncio_mode` and JSON evidence output to `[tool.pytest.ini_options]`
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
- the starter's exact tool arguments and returned task state satisfy its checks

pytest prints the outcome and assertion failures. Ask your coding agent to read
`aitest-reports/results.json` and inspect the `todo-add_task` call, its arguments,
and returned state alongside the test source. There is no HTML or Markdown
dashboard and no separate model judging the result.

## Adapt it to your project

Open the generated test and replace:

1. `TODO_MCP` with your MCP server configuration.
2. The system prompt in `instructions`.
3. The task prompt with a real user request.
4. The starter's tool argument and returned-state checks with independent checks
   of your application's required output. Session success alone is not enough.

The complete generated file is also available in
[`examples/quickstart`](https://github.com/sbroenne/pytest-skill-engineering/tree/main/examples/quickstart).

For the full test-write, failure-investigation, and repair cycle, use the
[customer workflow sample](https://github.com/sbroenne/pytest-skill-engineering/tree/main/examples/skill-dogfood).
It also preserves the historical comparison that led us to remove our proposed
companion skill. Default sample tests are offline; paid runs are explicit.

## What to compare next

- [System prompts](system-prompts.md)
- [Skills](skills.md)
- [Custom agents](custom-agents.md)
- [Comparing configurations](comparing.md)
- [Multi-turn sessions](sessions.md)
- [Troubleshooting](troubleshooting.md)
- [Inspecting captured evidence](../how-to/inspect-evidence.md)
