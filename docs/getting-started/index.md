---
description: "Install the harness, run one real Copilot task, and check its output with pytest."
---

# Getting Started

Use pytest-skill-engineering to ask GitHub Copilot to complete a task, assert on
the actual output, and save the execution as JSON. Start with one small task
before comparing models, instructions, skills, or tools.

You write the test and its output checks. `CopilotEval` configures the session;
the `copilot_eval` fixture runs it and captures evidence. pytest decides whether
your assertions pass.

## Install, initialize, and diagnose

In a Python 3.11+ project managed by uv:

```bash
uv add pytest-skill-engineering
gh auth login --hostname github.com
uv run pytest-skill-engineering init
uv run pytest-skill-engineering doctor
```

The signed-in account needs GitHub Copilot access. In CI, use an authorized
`GITHUB_TOKEN` or `GH_TOKEN`; `GITHUB_TOKEN` takes precedence when both are set.
`doctor` checks project configuration, authentication, SDK startup, and access
to the starter model.

`init` creates:

- `tests/test_copilot_eval.py`, using the bundled todo MCP server;
- pytest settings for async tests and JSON output;
- explicit example rates for `gpt-5.6-sol` in `pricing.toml`, preserving any
  existing rate.

It refuses to overwrite the starter test or replace conflicting report settings.
Resolve the named conflict and run it again.

## Run the first eval

```bash
uv run python -m pytest tests/test_copilot_eval.py -v
```

This is a **live Copilot execution** and may consume premium requests. The
starter asks Copilot to add a task titled exactly `buy groceries`. It checks
the tool arguments, completed tool evidence, and the task data returned by
the server—not just Copilot's claim that it finished.

Read the generated test before adapting it. A passing run establishes that this
task satisfied those checks in this environment. It does not establish general
reliability or correctness for your own application.

## Read the outcome and evidence

pytest prints the outcome and assertion failures. The initialized project saves
execution evidence to `aitest-reports/results.json`, using native schema 4.0.
Give your coding agent the failing assertion, test source, and JSON when you
need to investigate.

The JSON includes the captured conversation, tool calls, configuration, usage,
and pytest outcome. It is not an automatic assessment of output quality. See
[Inspect execution evidence](../how-to/inspect-evidence.md).

## Adapt it to your project

Replace four parts of the generated test:

1. **Tools and state:** replace `TODO_MCP` with your server configuration or
   explicitly supplied SDK tools. Your fixtures initialize application state.
2. **System prompt:** set `CopilotEval.instructions` to the behavior you need.
3. **Prompt:** pass a representative user task to `copilot_eval`.
4. **Verification:** check produced files, exact values, or application state
   independently. Tool presence and session completion are not enough.

Use disposable workspaces and test accounts. Permissions are automatically
approved by default; a working directory is not a filesystem or network sandbox.
Bound live work with `timeout_s` and, when needed, `max_tool_calls`. Keep credentials
and production data out of tasks and saved evidence.

The generated test is also in
[`examples/quickstart`](https://github.com/sbroenne/pytest-skill-engineering/tree/main/examples/quickstart).
For an offline-first write, investigate, and repair workflow, see
[`examples/skill-dogfood`](https://github.com/sbroenne/pytest-skill-engineering/tree/main/examples/skill-dogfood).
Its live cases require an explicit opt-in.

## What to compare next

- [System prompts](system-prompts.md): configure `instructions`.
- [Skills](skills.md): load your own skill directories.
- [Custom agents](custom-agents.md): load definitions and inspect dispatch.
- [Comparing configurations](comparing.md): apply fixed checks to variants.
- [Multi-step tasks and explicit context](sessions.md): understand session boundaries.
- [Troubleshooting](troubleshooting.md): diagnose setup and evidence failures.
