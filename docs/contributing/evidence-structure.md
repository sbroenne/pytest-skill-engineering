# Evidence structure

Native JSON is a record of captured execution and ordinary pytest outcomes.
Preserve the data needed to investigate a run; do not turn it into a score or
an explanation.

## Pipeline

`CopilotResult -> consumer-owned pytest checks -> TestReport -> SuiteReport -> JSON`

`reporting/collector.py` holds the native dataclasses and suite outcome counts.
`reporting/generator.py` atomically saves JSON and loads current-schema evidence.
`core/serialization.py` preserves the dataclass hierarchy, including binary images
encoded as base64.

## What schema 4.0 preserves

Schema 4.0 saves test IDs, outcomes, assertion errors, verification properties,
execution configuration, turns, tool arguments and outputs, completion status,
capture errors, request audits, stop reasons, usage, and missing-pricing models.
Private SDK/session fields are not serialized.
Prepared session settings reflect overrides and persona additions. A missing
snapshot or unknown model is explicit `null`. Framework-owned child results
remain nested under invocation IDs, with inclusive top-level accounting; tool
image bytes and any additional images round-trip without loss.

`eval_result.skill_discovery` saves actual public SDK availability separately
from requested configuration and observed reads. It preserves metadata, loading
warnings/errors, and whether discovery completed; `null` means no check was
attempted. This field is required by the current schema-4.0 producer/reader.
Regenerate older evidence missing it with the current producer; do not infer
availability from supplied paths or patch saved JSON.

## Missing data must stay missing

Preserve `null` output separately from `""`, and unknown usage separately from
zero. Do not replace unsupported property values with strings or synthesize
uncaptured successful assertions.
The loader rejects old schemas and missing current-schema fields at every record
level; there is no compatibility reader or reconstruction from default values.

## pytest outcomes are shared within a test

Each captured run retains its pytest outcome. Multiple executions in one test
share that outcome, so their entries are not independently graded task verdicts.
Preserve side-specific properties and captured comparison roles.
Finalize outcomes and verification properties after fixture cleanup; setup and
cleanup errors with captured executions must not be saved as passes.

## Validate producer and reader together

```bash
uv run --frozen python -m pytest tests/contracts/test_native_evidence.py tests/contracts/test_usage_evidence.py -q -o addopts=
```

These checks validate round trips, missing data, publication failures, and
framework boundaries without model calls. They do not measure model performance.
Execution changes also require relevant authorized real-Copilot tests.

Persistence failures must be visible and make pytest return nonzero. Publishing
must be atomic so a partially written file cannot look like a complete run.
Never hand-edit generated JSON: change the producer and regenerate its evidence.
