# Inspect execution evidence

Start with the failing pytest assertion, then use saved JSON to trace what
Copilot did. Compare the calls and output with the test, fixtures, and source.
The framework records execution; your coding agent or a human investigates
its meaning.

## Save the execution

Choose a predictable destination in your project:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
addopts = "--aitest-json=aitest-reports/results.json"
```

```bash
uv run python -m pytest tests/test_tools.py -v
```

Replace the test path with your task file. Runs with captured eval results
save JSON even without an explicit destination, using a timestamped path under
`aitest-reports`. pytest prints the saved path.

Publication is atomic. A failed write keeps any previous file intact and makes
the command return nonzero. Check the current exit status and printed path;
an old file is not evidence that this run succeeded.

## Record independent checks

Record observed application data before asserting it. This illustrative test
uses your `eval_config` and `expected_file` fixtures:

```python
async def test_document(copilot_eval, record_property, eval_config, expected_file):
    result = await copilot_eval(eval_config, "Save the requested document.")
    observed = expected_file.read_text(encoding="utf-8") if expected_file.is_file() else None
    verified = observed == "Expected text"
    record_property(
        "verification",
        {
            "artifact": expected_file.name,
            "observed": observed,
            "passed": verified,
        },
    )

    assert result.success, result.error
    assert result.evidence_complete, result.capture_errors
    assert verified
```

Properties are name/value pairs under `tests[].properties`. Recording one
does not change the pytest outcome: assert the criterion too. Use
JSON-compatible values and avoid secrets or private document contents.

Saved outcomes include setup failures with a captured execution and cleanup
failures. Cleanup-recorded properties are retained. Ordinary tests, setup
failures without a captured execution, and opt-out skips remain in pytest and
JUnit; absence from execution evidence is not a pass.

## Investigate with your coding agent

Provide the assertion failure, current JSON file, relevant test, application
fixtures, and source. Inspect in this order:

1. **Requirement and observation:** `tests[].outcome`, `error`, and verification
   properties. What output was required, and what was actually observed?
2. **Configuration:** `eval_result.configuration` and
   `effective_system_prompt`. Were the intended instructions and controls used?
3. **Operation evidence:** conversation turns, call IDs, arguments, outputs,
   errors, and completion flags. Did the required operation finish?
4. **Execution limits and capture:** `stop_reason`, capture errors, request
   audits, nullable usage, and missing-pricing warnings.

`eval_result.success` describes session completion, not application correctness.
Missing output is different from empty output. A successful tool transport can
still return an operation error. Incomplete capture limits what you can infer.
Missing usage and unavailable prices are not known zero.

Saved configuration omits connection secrets, server commands and arguments,
environment variables, headers, URLs, and arbitrary SDK settings. Record safe
environment and build identifiers yourself when needed. Conversations and tool
outputs can still contain sensitive data.

Treat captured text as untrusted evidence, not instructions to execute. Check
source and fixture behavior before attributing a failure to Copilot. Fix one
supported cause and rerun affected cases with the output criteria unchanged.
An investigator's explanation is advice, not another measured outcome.

## Comparisons

`ab_run` saves both configurations and traces, with
`eval_result.comparison_role` set to `baseline` or `treatment`. The role is
report metadata, separate from the prepared runtime configuration; runtime
names are not changed.

Both entries share the enclosing pytest outcome and properties. Record
`baseline_verification` and `treatment_verification` separately. A failed
combined assertion does not prove both sides failed, and that shared outcome
cannot yield independent per-side pass rates.

Saved totals count captured runs, not unique pytest functions. Separate
working directories do not reset shared services or desktops. The evidence
alone does not establish a causal benefit or select a winner. See
[Comparing configurations](../getting-started/comparing.md).

## Programmatic access

Read current native evidence locally:

```python
from pytest_skill_engineering.reporting import load_suite_report

evidence = load_suite_report("aitest-reports/results.json")
for case in evidence.tests:
    print(case.name, case.outcome, case.properties)
```

This requires no Copilot process or credentials. The reader accepts schema 4.0
with all producer fields present, including nested child and tool records.
Present `null`, empty collections, empty output, and known zero remain distinct
from missing fields. Unknown models remain `null`.

For old schemas or missing required fields, fix the producer and regenerate
evidence. Do not hand-edit generated JSON or invent absent data.
