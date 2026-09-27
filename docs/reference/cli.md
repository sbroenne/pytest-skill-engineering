---
description: "pytest and report-regeneration CLI options for pytest-skill-engineering."
---

# CLI options

## Project setup

Create a first eval and explicit report configuration in an existing Python
project:

```bash
uv run pytest-skill-engineering init [PROJECT_DIR]
```

The command requires an existing `pyproject.toml`. It creates
`tests/test_copilot_eval.py`, sets `asyncio_mode = "auto"`, adds HTML, JSON, and
`gpt-5.6-sol` analysis options, and records explicit cost rates in
`pricing.toml`. Existing model rates are preserved. It fails without changing
existing content when the starter file or one of the pytest settings conflicts.

Validate the complete first-run environment:

```bash
uv run pytest-skill-engineering doctor [PROJECT_DIR]
```

`doctor` checks Python and package versions, starter configuration, GitHub
credentials, Copilot SDK startup, and `gpt-5.6-sol` availability. Each failed
check is printed and produces a nonzero exit code.

## Recommended defaults

```toml
[tool.pytest.ini_options]
addopts = """
--aitest-summary-model=copilot/gpt-5.6-sol
--aitest-html=aitest-reports/report.html
"""
```

## pytest options

| Option | Meaning |
|---|---|
| `--aitest-summary-model=MODEL` | Copilot model for AI insights |
| `--aitest-html=PATH` | Write HTML report |
| `--aitest-md=PATH` | Write Markdown report |
| `--aitest-json=PATH` | Write JSON report |
| `--aitest-min-pass-rate=N` | Fail if overall pass rate drops below `N` |
| `--aitest-iterations=N` | Run each test `N` times; reports strip only the synthetic iteration suffix |
| `--aitest-analysis-prompt=PATH` | Override the AI analysis system prompt file |
| `--aitest-summary-compact` | Omit full passing transcripts from AI analysis |
| `--aitest-print-analysis-prompt` | Print the resolved analysis prompt source |
| `--llm-model=MODEL` | Copilot model for `llm_assert` / `llm_score` |

Run pytest with:

```bash
uv run python -m pytest tests/ -v
```

## Report regeneration CLI

```bash
uv run pytest-skill-engineering-report aitest-reports/results.json   --html aitest-reports/report.html
```

Add `--summary --summary-model copilot/gpt-5.6-sol` to refresh AI insights.

## Environment variables

- `GITHUB_TOKEN` — explicit non-interactive Copilot auth; takes precedence over `GH_TOKEN`
- `GH_TOKEN` — explicit Copilot auth when `GITHUB_TOKEN` is unset
- `AITEST_SUMMARY_MODEL` — default summary model for regeneration
