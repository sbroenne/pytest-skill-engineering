# pytest-skill-engineering

[![PyPI version](https://img.shields.io/pypi/v/pytest-skill-engineering)](https://pypi.org/project/pytest-skill-engineering/)
[![CI](https://github.com/sbroenne/pytest-skill-engineering/actions/workflows/ci.yml/badge.svg)](https://github.com/sbroenne/pytest-skill-engineering/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Test whether GitHub Copilot can complete tasks with your tools and instructions.**

pytest-skill-engineering runs real Copilot sessions from pytest. Give Copilot a
task, check the actual output with ordinary assertions, and save the execution
as JSON.

Use it to test MCP servers, CLI tools, skills, system prompts, plugins, and custom
agents. It answers a different question from your tool's unit tests: **can
Copilot use the interface correctly?** A working tool can still have confusing
descriptions or arguments that lead the agent to the wrong result.

You define what correctness means. The framework manages the Copilot session,
execution limits, usage, and evidence; it does not grade answers with another AI.

## Quick start

You need Python 3.11+, [uv](https://docs.astral.sh/uv/), and a GitHub account with
Copilot access.

Run these commands in an existing Python project with a `pyproject.toml`:

```bash
uv add pytest-skill-engineering
gh auth login --hostname github.com
uv run pytest-skill-engineering init
uv run pytest-skill-engineering doctor
uv run python -m pytest tests/test_copilot_eval.py -v
```

`init` creates a test using the bundled Todo MCP server, configures JSON output,
and adds starter-model rates to `pricing.toml`. It reports conflicts rather than
overwriting existing files or settings. `doctor` checks setup and Copilot access.
Real task execution may consume Copilot premium requests.

The test checks the tool's arguments and returned task state. pytest prints the
result; `aitest-reports/results.json` preserves the execution. See the
[setup guide](docs/getting-started/index.md) or the standalone
[quickstart project](examples/quickstart/).

## A test that checks the result

```python
from __future__ import annotations

import json

from pytest_skill_engineering.copilot import CopilotEval


async def test_order_total(copilot_eval, tmp_path):
    agent = CopilotEval(
        name="order-total",
        model="gpt-5.6-sol",
        instructions="Save the requested output as JSON. Use integer cents.",
        working_directory=str(tmp_path),
    )
    result = await copilot_eval(
        agent,
        "Save order.json for two items at 1250 cents each plus 20% tax. "
        "Include subtotal_cents, tax_cents, and total_cents.",
    )
    assert result.success, result.error
    output = tmp_path / "order.json"
    assert output.is_file()
    assert json.loads(output.read_text(encoding="utf-8")) == {
        "subtotal_cents": 2500,
        "tax_cents": 500,
        "total_cents": 3000,
    }
```

`CopilotEval` configures the session. The second argument to `copilot_eval` is
the user task. `result.success` checks execution completion; the file assertions
check that the task produced the right result.

For your own tools, check the resulting application state, saved files, or
operation output. A tool call or a model's claim is not proof of task success.
Use approved isolation for live tests: a temporary directory is not a sandbox,
and generated code or tool calls can act with your user's access.

## What the framework provides

| You need | Use |
| --- | --- |
| Real task execution | `CopilotEval` and the `copilot_eval` pytest fixture |
| Controlled runs | Timeouts, tool budgets, request controls, and permission settings |
| Debugging evidence | Configuration, calls, arguments, outputs, errors, and completion records |
| Repeatable comparisons | `ab_run` and pytest repetitions |
| Usage visibility | Captured tokens, Copilot premium requests, and explicit price estimates |
| Saved results | Native JSON with execution evidence and ordinary pytest outcomes |

Your tests supply application fixtures, guarded tool adapters, and independent
output checks. The framework makes one execution attempt per call; it does not
retry failures automatically. Missing usage, prices, and incomplete evidence
remain visible.

## Investigate and compare

Give your coding agent a failed test, its JSON evidence, the requirements, and
the relevant source. It can investigate the failure and help you change the
interface. Keep the success criteria fixed when rerunning a comparison.

For A/B tests, record verification separately for each side: both saved
executions share one pytest outcome. That outcome alone cannot establish
independent pass rates or a causal improvement. See
[comparing configurations](docs/getting-started/comparing.md).

## Documentation

- [Getting started](https://sbroenne.github.io/pytest-skill-engineering/getting-started/)
- [Task guides](docs/how-to/index.md) and [API reference](docs/reference/api.md)
- [Examples](examples/README.md), including historical skill comparisons
- [Upgrading from 0.6.x](docs/migration.md): 1.0 removed AI judging, renderers,
  rankings, and skill refinement

No framework companion skill is required or distributed. Testing your own
domain skills is supported.

## License

MIT. Inspired by [agent-benchmark](https://github.com/mykhaliev/agent-benchmark).
