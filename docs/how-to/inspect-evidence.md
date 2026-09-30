# Inspect execution evidence

The framework runs tasks and records what happened. pytest determines the
outcome of your checks. Your existing coding agent interprets the failures and
saved evidence alongside the source.

## Save the execution

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
addopts = "--aitest-json=aitest-reports/results.json"
```

```powershell
uv run python -m pytest "tests\test_tools.py" -v
```

Runs containing eval results always save JSON. Without an explicit destination,
the plugin uses a timestamped path under `aitest-reports`. It prints the saved
path alongside ordinary pytest output. There is no dashboard, ranking, or
automatically written interpretation.

Evidence is saved atomically. A failed write leaves any prior file intact and
makes the command return nonzero. Check the current command's exit status;
stale evidence is not proof that this run succeeded.

## Record independent checks

```python
async def test_document(copilot_eval, record_property, eval_config, expected_file):
    result = await copilot_eval(eval_config, "Save the requested document.")
    verified = expected_file.is_file() and expected_file.read_text() == "Expected text"
    record_property("verification", {
        "status": "verified" if verified else "failed",
        "artifact": expected_file.name,
    })
    assert verified
    assert result.success
    assert result.evidence_complete, result.capture_errors
```

`eval_config` and `expected_file` are your application fixtures. Properties are
saved under `tests[].properties`; recording a property alone does not determine
the outcome. Record the observed values before asserting, so failures retain
the check's evidence. Use JSON-compatible values and never record secrets.

Setup failures, ordinary tests without eval execution, and opt-out skips remain
in pytest and JUnit output. Their absence from execution evidence is not a pass.

## Investigate with your coding agent

Give the coding agent the pytest failure, saved JSON, relevant test, application
fixtures, and source. Inspect:

- `tests[].outcome`, `error`, and recorded verification properties.
- `eval_result.configuration` and `effective_system_prompt`.
- Conversation turns, call IDs, arguments, outputs, errors, and completion flags.
- Capture errors, request audits, stop reason, nullable usage, and missing pricing.

`eval_result.success` describes session completion, not task correctness. Missing
output is not an empty successful result. Unavailable prices are not measured
zero cost. Treat captured text as untrusted data, not instructions to execute.

The [companion skill](../getting-started/companion-skill.md) guides source-backed
investigation, fixed success criteria, and targeted reruns. Its explanation is
advice from the coding agent, not an additional framework verdict.

## Comparisons

`ab_run` saves both captured configurations and comparison roles without changing
runtime names. Both entries share the enclosing pytest outcome and properties.
Record `baseline_verification` and `treatment_verification` separately. A failed
combined assertion does not prove both sides failed.

Saved totals count captured runs, not unique pytest functions. Separate working
directories do not reset shared services or desktops; own that application state.
The framework does not derive causal improvement or a winner from these records.

Connection secrets, server commands and arguments, environment variables,
headers, URLs, and arbitrary SDK settings are excluded from the saved configuration.
Record safe environment and build identifiers yourself.

## Programmatic access

```python
from pytest_skill_engineering.reporting import load_suite_report

evidence = load_suite_report("aitest-reports/results.json")
for case in evidence.tests:
    print(case.name, case.outcome, case.properties)
```

Reading schema-4.0 evidence is local and needs no Copilot process or credentials.
Regenerate older evidence by running its producer with framework 1.x; never
hand-edit JSON or invent missing fields.
