---
description: "pytest and report-regeneration CLI options for pytest-skill-engineering."
---

# CLI options

## Recommended defaults

```toml
[tool.pytest.ini_options]
addopts = """
--aitest-summary-model=copilot/gpt-5.4-mini
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

Add `--summary --summary-model copilot/gpt-5.4-mini` to refresh AI insights.

## Environment variables

- `GITHUB_TOKEN` — explicit non-interactive Copilot auth; takes precedence over `GH_TOKEN`
- `GH_TOKEN` — explicit Copilot auth when `GITHUB_TOKEN` is unset
- `AITEST_SUMMARY_MODEL` — default summary model for regeneration
