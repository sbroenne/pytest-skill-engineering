# Evidence structure

The framework records execution and ordinary pytest outcomes without interpreting
them. The coding agent reads the evidence together with source and test criteria.

## Pipeline

`CopilotResult -> consumer-owned pytest checks -> TestReport -> SuiteReport -> JSON`

`reporting/collector.py` holds the native dataclasses and suite outcome counts.
`reporting/generator.py` atomically saves JSON and loads current-schema evidence.
`core/serialization.py` preserves the dataclass hierarchy, including binary images
encoded as base64. No renderer, UI contract, leaderboard, or winner selection exists.

## Current contract

Schema 4.0 saves test IDs, outcomes, assertion errors, verification properties,
execution configuration, turns, tool arguments and outputs, completion status,
capture errors, request audits, stop reasons, usage, and missing-pricing models.
Private SDK/session fields are not serialized.

Preserve missing versus empty output and nullable usage. Do not replace unsupported
property values with strings or synthesize uncaptured successful assertions.
The loader rejects old schemas; there is no compatibility reader.

Each captured run retains its pytest outcome. Multiple executions in one test
share that outcome, so their entries are not independently graded task verdicts.
Preserve side-specific properties and captured comparison roles.

## Validation

```powershell
uv run python -m pytest "tests\contracts\test_native_evidence.py" "tests\contracts\test_usage_evidence.py" -q -o addopts=
```

These checks validate round trips, missing data, publication failures, and
framework boundaries without model calls. They do not measure model performance.
Execution changes also require relevant authorized real-Copilot tests.

There are no checked-in demo reports or rendering fixtures to regenerate.
Never hand-edit generated JSON.
