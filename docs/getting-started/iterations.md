# Test repetitions

Repeat a fixed task and its output checks to observe variation across model
executions. One passing run does not establish reliability.

```bash
uv run python -m pytest tests/test_tools.py --aitest-iterations=3
```

The option repeats every collected test, not just eval tests. It multiplies live
execution cost. Authorize the scope before running a large case matrix.

## What is recorded

Each repetition has its own pytest outcome. Native JSON preserves that execution,
its iteration number, configuration, available usage, cost estimate, duration,
and recorded checks.
Grouped and stacked pytest parameters retain their user-supplied IDs. Only the
framework's repetition axis is removed from the saved case name; the iteration
number remains a separate field.

Saved outcomes are finalized after fixture cleanup. A cleanup failure changes
the captured execution's outcome to failed and retains cleanup-recorded checks,
even when the test body passed.

Inspect the individual traces, fixtures, and source to distinguish variation in
Copilot behavior from unstable test data or environment failures. The saved
outcome does not explain the cause.

## Repetitions versus retries

`--aitest-iterations` repeats the whole test with newly created function-scoped
fixtures. It does not reset session-scoped fixtures, a shared desktop, or an
external service automatically.

Each `copilot_eval` call makes one attempt. The framework does not retry startup,
connection, or task failures. Rerun a selected case explicitly, or request
repetitions with fixed criteria; failed executions remain recorded.

## Thresholds and interpretation

```bash
uv run python -m pytest tests/test_tools.py --aitest-iterations=3 --aitest-min-pass-rate=80
```

The threshold is an observed saved-outcome gate, not a production guarantee.
Choose sample size and representative cases for your question. Three
repetitions may reveal variability but cannot establish high reliability.
For `ab_run`, both entries share the test's outcome; this gate cannot establish
independent per-side pass rates.

See [comparisons](comparing.md) and [evidence inspection](../how-to/inspect-evidence.md).
