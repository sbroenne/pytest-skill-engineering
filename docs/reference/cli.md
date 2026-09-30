# CLI options

## Project setup

```powershell
uv run pytest-skill-engineering init [PROJECT_DIR]
uv run pytest-skill-engineering doctor [PROJECT_DIR]
```

`init` requires an existing `pyproject.toml`. It creates
`tests\test_copilot_eval.py`, sets `asyncio_mode = "auto"`, adds a JSON evidence
destination, and records explicit starter-model pricing. Existing rates are
preserved; conflicts fail without overwriting existing content.

`doctor` checks installation, project settings, authentication, SDK startup,
and starter-model availability. It contacts Copilot but does not execute a task
under test. Failed checks produce a nonzero exit code.

## pytest options

| Option | Meaning |
| --- | --- |
| `--aitest-json=PATH` | Save captured execution evidence and pytest outcomes |
| `--aitest-min-pass-rate=N` | Fail when the saved eval outcomes fall below N percent |
| `--aitest-iterations=N` | Repeat each test N times with newly created pytest fixtures |

```powershell
uv run python -m pytest "tests\test_tools.py" -v --aitest-json=results.json
```

pytest prints ordinary results and assertion failures. Without an explicit JSON
path, runs containing eval results save a timestamped file under `aitest-reports`.
Tests without an eval result, setup failures, and opt-out skips remain in ordinary
pytest output and optional JUnit output, not the captured-execution file.

An A/B test has one pytest outcome shared by both saved runs. Record side-specific
verification properties; the framework does not generate rankings or choose winners.

Evidence-save errors are visible and make the command return nonzero. A file from
an earlier run is not evidence that the current command succeeded.

## Reading saved evidence

Read the JSON directly with your coding agent or load its dataclasses:

```python
from pytest_skill_engineering.reporting import load_suite_report

evidence = load_suite_report("results.json")
for case in evidence.tests:
    print(case.name, case.outcome, case.error)
```

Loading needs neither Copilot authentication nor a running Copilot process.
Schema 4.0 is required; older evidence is rejected explicitly.
There is no HTML/Markdown renderer or report CLI.

## Authentication

Task execution selects `GITHUB_TOKEN` first, then `GH_TOKEN`; otherwise the SDK
uses its signed-in user. The retired `AITEST_SUMMARY_MODEL` setting has no effect.
