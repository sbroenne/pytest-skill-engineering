# Quickstart: one Copilot task with pytest

This project asks real GitHub Copilot to add a task through the bundled Todo MCP
server. The test checks the exact title, completed tool evidence, and returned
task state. pytest decides whether the checks pass; JSON records the execution.

## Requirements

Use Python 3.11+, uv, and a GitHub account with Copilot access. The test uses
`gpt-5.6-sol` and may consume premium requests. `pricing.toml` supplies explicit
rates for estimates; adjust them to your billing basis.

## Run from this directory

From the repository root, first change to the example:

```bash
cd examples/quickstart
```

```bash
gh auth login --hostname github.com
uv sync
uv run python -m pytest tests/test_copilot_eval.py -v
```

## Read the result

pytest prints the outcome and assertion failures. Captured execution is saved
to `aitest-reports/results.json` in this directory, including failed runs that
produced execution evidence.

The check is stronger than asking whether Copilot said it added a task: it
parses the tool's documented response and verifies the values. The test also
checks that the SDK's display and structured representations agree.

## Adapt it to your application

Replace `TODO_MCP` in `tests/test_copilot_eval.py` with your server mapping and
replace the task and assertions together. Check your application's actual
output, not just whether the tool was called.

Give your coding agent the failed test, saved JSON, requirements, and relevant
source when investigating a failure. Keep output criteria fixed during a
comparison.

To generate this starter in an existing Python project:

```bash
uv add "pytest-skill-engineering>=1.0.0,<2"
uv run pytest-skill-engineering init
uv run pytest-skill-engineering doctor
```

`init` requires a `pyproject.toml` and reports existing-file or settings conflicts
rather than overwriting them.
