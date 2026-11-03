# pytest-copilot - pytest for GitHub Copilot

[![PyPI version](https://img.shields.io/pypi/v/pytest-copilot)](https://pypi.org/project/pytest-copilot/)
[![CI](https://github.com/sbroenne/pytest-copilot/actions/workflows/ci.yml/badge.svg)](https://github.com/sbroenne/pytest-copilot/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Test whether GitHub Copilot can complete tasks with your tools and instructions.**

Independently maintained; not an official GitHub product or endorsed by GitHub.

pytest-copilot runs real GitHub Copilot sessions from pytest. Give GitHub Copilot a
task, check the actual output with ordinary assertions, and save the execution
as JSON.

Use it to test MCP servers, CLI tools, skills, system prompts, plugins, and custom
agents. It answers a different question from your tool's unit tests: **can
GitHub Copilot use the interface correctly?** A working tool can still have confusing
descriptions or arguments that lead the agent to the wrong result.

You define what correctness means. The framework manages the Copilot session,
execution limits, usage, and evidence; it does not grade answers with another AI.

## Quick start

You need Python 3.11+, [uv](https://docs.astral.sh/uv/), and a GitHub account with
Copilot access.

Run these commands in an existing Python project with a `pyproject.toml`:

```bash
uv add pytest-copilot
gh auth login --hostname github.com
uv run pytest-copilot init
uv run pytest-copilot doctor
uv run python -m pytest tests/test_copilot_run.py -v
```

`init` creates a test using the bundled Todo MCP server, configures JSON output,
and adds starter-model rates to `pricing.toml`. It reports conflicts rather than
overwriting existing files or settings. `doctor` checks setup and Copilot access.
Real task execution may consume Copilot premium requests.

For installation from a downloaded package instead of PyPI, see
[install from a release download](docs/getting-started/index.md#install-from-a-release-download).

The test checks the tool's arguments and returned task state. pytest prints the
result; `aitest-reports/results.json` preserves the execution. See the
[setup guide](docs/getting-started/index.md) or the standalone
[quickstart project](examples/quickstart/).

## A test that checks the result

```python
from __future__ import annotations

import json

from pytest_copilot.copilot import CopilotTask


async def test_order_total(copilot_run, tmp_path):
    agent = CopilotTask(
        name="order-total",
        model="gpt-5.6-sol",
        instructions="Save the requested output as JSON. Use integer cents.",
        working_directory=str(tmp_path),
    )
    result = await copilot_run(
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

`CopilotTask` configures the session. The second argument to `copilot_run` is
the user task. `result.success` checks execution completion; the file assertions
check that the task produced the right result.

For your own tools, check the resulting application state, saved files, or
operation output. A tool call or a model's claim is not proof of task success.
Use approved isolation for live tests: a temporary directory is not a sandbox,
and generated code or tool calls can act with your user's access.

## What the framework provides

| You need | Use |
| --- | --- |
| Real task execution | `CopilotTask` and the `copilot_run` pytest fixture |
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

- [Getting started](https://sbroenne.github.io/pytest-copilot/getting-started/)
- [Task guides](docs/how-to/index.md) and [API reference](docs/reference/api.md)
- [Examples](examples/README.md), including historical skill comparisons
- [Upgrading to 2.0](docs/migration.md): new package, imports, and task names,
  without compatibility aliases

No framework companion skill is required or distributed. Testing your own
domain skills is supported.

## License

MIT. Inspired by [agent-benchmark](https://github.com/mykhaliev/agent-benchmark).
