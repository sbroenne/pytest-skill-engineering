---
description: "Run tests multiple times to measure reliability. Aggregate iteration results, detect flaky tests, and establish stable baselines for AI-powered testing."
---

# Test Iterations

LLM responses are non-deterministic. A test that passes once might fail the next time — or vice versa. **Iterations** let you run each test multiple times and see the real pass rate.

## Why Iterations?

A single test run tells you whether it passed *that time*. It doesn't tell you:

- Is this configuration **reliably** correct? (90%? 100%?)
- Is this test **flaky**? (passes sometimes, fails others)
- Which failures are **intermittent** vs **systematic**?

Iterations answer these questions by running every test N times and aggregating the results.

## Quick Start

Add `--aitest-iterations=N` to your pytest command:

```bash
# Run each test 3 times
pytest tests/ --aitest-iterations=3 --aitest-html=report.html --aitest-summary-model=azure/gpt-5.2-chat
```

No code changes needed. Every test automatically runs N times.

## What the Report Shows

With iterations enabled, the report adds:

- **Iteration pass rate** per test (e.g., "2/3 iterations passed — 67%")
- **Per-iteration breakdown** showing outcome, duration, tokens, and cost for each run
- **Flakiness detection** — AI analysis flags tests with < 100% pass rate
- **Aggregated metrics** — total cost and tokens across all iterations

### Example Output

A test that passes 2 out of 3 times shows:

| Iteration | Outcome | Duration | Tokens | Cost |
|-----------|---------|----------|--------|------|
| 1 | Passed | 1.2s | 450 | $0.002 |
| 2 | Failed | 0.8s | 380 | $0.001 |
| 3 | Passed | 1.1s | 420 | $0.002 |

**Result:** 2/3 iterations passed (67%) — flagged as flaky.

## Configuration

### CLI Option

```bash
# Default: 1 (no iteration)
pytest tests/ --aitest-iterations=5
```

### pyproject.toml

```toml
[tool.pytest.ini_options]
addopts = """
--aitest-iterations=3
--aitest-summary-model=azure/gpt-5.2-chat
--aitest-html=aitest-reports/report.html
"""
```

## How It Works

Under the hood, `--aitest-iterations=N` parametrizes every test with an iteration index:

```
test_balance[iter-1]
test_balance[iter-2]
test_balance[iter-3]
```

The report generator groups these by test name + agent and computes aggregated metrics:

- **Outcome:** `passed` only if ALL iterations pass
- **Pass rate:** Percentage of iterations that passed
- **Duration/tokens/cost:** Summed across all iterations

## Combining with Other Features

Iterations work seamlessly with all other pytest-skill-engineering features:

### With Model Comparison

```bash
# Compare models with 3 iterations each
pytest tests/ --aitest-iterations=3
```

Each model runs each test 3 times. The leaderboard uses aggregated pass rates.

### With Eval Retries

Iterations are different from `Eval.retries`:

| Feature | Purpose | Scope |
|---------|---------|-------|
| `--aitest-iterations=N` | Statistical reliability | Re-runs the entire test N times |
| `Eval(retries=3)` | Error recovery | Retries failed tool calls within a single run |

Use both together for robust testing:

```python
agent = Eval(
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[server],
    retries=3,          # Retry tool errors within each run
    max_turns=10,
)

# Run each test 5 times for statistical confidence
# pytest tests/ --aitest-iterations=5
```

### With Sessions

Each iteration runs the full session independently. Session state is not shared across iterations.

## Best Practices

1. **Start with 3 iterations** — enough to spot flakiness without excessive cost
2. **Use 5+ iterations** for baseline establishment before releases
3. **Check the AI analysis** — it automatically detects and explains flaky patterns
4. **Combine with `--aitest-min-pass-rate`** to fail CI when reliability drops:

```bash
# Fail if overall pass rate drops below 80%
pytest tests/ --aitest-iterations=3 --aitest-min-pass-rate=80
```

## Next Steps

- [Comparing Configurations](comparing.md) — Compare models and prompts
- [CLI Options](../reference/cli.md) — All command-line options
- [Generate Reports](../how-to/generate-reports.md) — Report generation details

> **Real Examples:**
> - [pydantic/test_11_iterations.py](https://github.com/sbroenne/pytest-skill-engineering/blob/main/tests/integration/pydantic/test_11_iterations.py) — Iteration baseline tests
