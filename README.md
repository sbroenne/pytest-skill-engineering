# pytest-skill-engineering

[![PyPI version](https://img.shields.io/pypi/v/pytest-skill-engineering)](https://pypi.org/project/pytest-skill-engineering/)
[![CI](https://github.com/sbroenne/pytest-skill-engineering/actions/workflows/ci.yml/badge.svg)](https://github.com/sbroenne/pytest-skill-engineering/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**A test runner for people working with coding agents.**

Test whether real GitHub Copilot sessions can use your MCP servers, CLI tools,
skills, system prompts, and custom agents. Write a user task, execute it through
pytest, and verify the actual output with ordinary assertions.

The framework runs the task and records what happened. Your existing coding agent
investigates the evidence, reads the source, and helps you improve the interface.
**Version 1.0 removes AI judging, report dashboards, rankings, and skill refinement.**
See the [migration guide](docs/migration.md) for this breaking change.

## Why this exists

Your tool can pass its own tests while Copilot chooses the wrong operation,
supplies the wrong arguments, or misunderstands its descriptions. That is a
different question from whether the tool implementation works.

Use real task execution to test the AI-facing interface, and independent output
checks to establish correctness. A completed session or a tool call by itself
does not prove that the requested task succeeded.

## Quick start

You need Python 3.11+, [uv](https://docs.astral.sh/uv/), and a GitHub account with
Copilot access.

```powershell
uv add pytest-skill-engineering
gh auth login --hostname github.com
uv run pytest-skill-engineering init
uv run pytest-skill-engineering doctor
uv run python -m pytest "tests\test_copilot_eval.py" -v
```

`init` creates a Todo MCP starter test, explicit JSON evidence settings, and
explicit starter-model rates in `pricing.toml`. It refuses conflicting settings
or an existing starter. Live execution can consume Copilot premium requests.

pytest shows ordinary test results and assertion failures. Give your coding
agent `aitest-reports\results.json` and the relevant source to investigate what
happened. No dashboard or second AI judgment is generated.

## Give your coding agent the companion skill

```powershell
npx skills add sbroenne/pytest-skill-engineering --skill pytest-skill-engineering
```

For an explicit host, add `--agent github-copilot`. The repository is the
canonical skill source; Node is needed for installation, not the Python runtime.
The remote command needs a published repository ref containing the skill.

The skill teaches your existing coding agent to define concrete success criteria,
investigate evidence and source, make one supported change, and rerun affected
cases. It does not add another runner or an automated judge.

## A test that checks the result

```python
from __future__ import annotations

import subprocess
import sys

from pytest_skill_engineering.copilot import CopilotEval


async def test_addition(copilot_eval, tmp_path):
    agent = CopilotEval(
        name="addition",
        model="gpt-5.6-luna",
        instructions="Write Python code and save the requested file.",
        working_directory=str(tmp_path),
    )
    result = await copilot_eval(
        agent, "Create calc.py with add(a, b) returning a + b."
    )
    assert result.success, result.error
    assert (tmp_path / "calc.py").is_file()
    checked = subprocess.run(
        [sys.executable, "-c", "from calc import add; assert add(2, 3) == 5; assert add(-2, 2) == 0"],
        cwd=tmp_path, capture_output=True, text=True, timeout=10,
    )
    assert checked.returncode == 0, checked.stderr
```

Use your approved isolation when executing generated code. A temporary directory
is not a security sandbox.

## What stays in the framework

| Capability | What it provides |
| --- | --- |
| `CopilotEval` and `copilot_eval` | Real SDK sessions with explicit configuration |
| MCP, CLI, skills, plugins, custom agents | The interfaces and definitions under test |
| Execution controls | Time, usage, request, tool, permission, and retry controls |
| Captured evidence | Configuration, calls, arguments, outputs, completion flags, errors, and usage |
| Ordinary pytest checks | Consumer-owned verification and recorded properties |
| `ab_run` and repetitions | Isolated working directories and repeated observations |
| Structured JSON | Captured execution and ordinary pytest outcomes, without rankings or advice |
| Pricing | Explicit USD estimates and recorded Copilot premium requests |

A/B entries share one pytest outcome. Record side-specific checks; do not read
that shared outcome as independent per-side success or causal improvement.
Missing prices and incomplete evidence are recorded explicitly.

## Let your coding agent investigate

Ask your existing coding agent to inspect a failed test, its saved JSON evidence,
and the source. It can explain the supported cause and help fix it, without
changing the test's success criteria after seeing the failure.

Reading current schema-4.0 evidence needs no authentication or paid call.
The framework records results; the coding agent interprets them. Subjective
review is advice, not an automatic pytest verdict.

Read the [full documentation](https://sbroenne.github.io/pytest-skill-engineering/).

## License

MIT. Inspired by [agent-benchmark](https://github.com/mykhaliev/agent-benchmark).
