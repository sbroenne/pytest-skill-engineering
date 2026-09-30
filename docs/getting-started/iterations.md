# Test repetitions

One passing model execution establishes an observation, not reliability.
Repeat representative tasks with fixed criteria to see variation:

```powershell
uv run python -m pytest "tests\test_tools.py" --aitest-iterations=3
```

The option repeats every collected test, not just eval tests. It multiplies live
execution cost. Authorize the scope before running a large case matrix.

## What is recorded

Each repetition has its own pytest outcome. Native JSON preserves that execution,
its iteration number, configuration, usage, cost estimate, duration, and recorded
checks. There is no grouped dashboard verdict or automatic explanation.

There is no AI flakiness explanation. Inspect the individual traces and source
to distinguish intermittent interface behavior from unstable fixtures or
environment failures.

## Repetitions versus retries

`--aitest-iterations` repeats the whole test with newly created function-scoped
fixtures. It does not reset session-scoped fixtures, a shared desktop, or an
external service automatically.

`CopilotEval(max_retries=2)` retries eligible transient execution failures before
tool activity. Runs with tool admission or observed tool activity are not
replayed. Use `max_retries=0` when the experiment must not retry executions.

## Thresholds and interpretation

```powershell
uv run python -m pytest "tests\test_tools.py" --aitest-iterations=3 --aitest-min-pass-rate=80
```

The threshold is an observed saved-outcome gate, not a production guarantee.
Choose sample size and representative cases for your question. Three
repetitions may reveal variability but cannot establish high reliability.

See [comparisons](comparing.md) and [evidence inspection](../how-to/inspect-evidence.md).
