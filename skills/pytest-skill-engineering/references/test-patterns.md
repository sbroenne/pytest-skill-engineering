# Test patterns for framework 1.x

## A concrete file task

Configure `[tool.pytest.ini_options]` with `asyncio_mode = "auto"` in the
consumer's `pyproject.toml` (the framework's `init` command does this). Having
pytest-asyncio installed alone does not make unmarked async tests run.

```python
from __future__ import annotations

import subprocess
import sys

from pytest_skill_engineering.copilot import CopilotEval


async def test_addition(copilot_eval, tmp_path, record_property):
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
    output = tmp_path / "calc.py"
    assert output.is_file()
    checked = subprocess.run(
        [sys.executable, "-c", "from calc import add; assert add(2, 3) == 5; assert add(-2, 2) == 0"],
        cwd=tmp_path, capture_output=True, text=True, timeout=10,
    )
    record_property("verification", {
        "artifact": str(output), "exit_code": checked.returncode,
        "stderr": checked.stderr,
    })
    assert checked.returncode == 0, checked.stderr
```

Run only authorized live cases:

```powershell
uv run python -m pytest "tests\test_addition.py" -q --aitest-json=results.json
```

Executing generated code has the same risks as executing any untrusted code.
Use the project's approved isolation and permissions, bounded subprocesses, and
non-sensitive temporary fixtures; a temporary directory alone is not a sandbox.

## Tool tasks

For an MCP or CLI task, assert the exact business result independently: query
the fixture store, inspect an output file, or parse a captured tool response.
Also check call order, arguments, operation errors, `success`, and
`completion_received` when those are part of the requirement.

A successful transport can return a business error. A missing completion or
missing result is not an empty successful result. Preserve `call_id`,
`evidence_complete`, and `capture_errors`; investigate incomplete evidence rather
than treating it as a pass.

Use `record_property("verification", {...})` to save observed values and checks.
Do not copy a model's claim into a property and call it independent verification.
Write the property before its assertion so a failure still leaves evidence.

## Comparisons and loaded cases

Use `dataclasses.replace` to vary one configuration field, and `ab_run` to execute
baseline and treatment in separate working directories. Locate each artifact
under `result.agent.working_directory`. Both sides must use the same fixed check.
Record `baseline_verification` and `treatment_verification` separately before
asserting the combined test outcome.

`load_skill_evals` loads descriptions and tasks from `evals\evals.json`; it does
not interpret free-text expectations. Translate requirements into concrete
checks yourself. `export_grading` formats explicitly supplied booleans and
evidence; it does not execute or judge a task.
