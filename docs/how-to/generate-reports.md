---
description: "Generate HTML and Markdown reports from pytest runs or from saved JSON, using Copilot models for AI insights."
---

# How to generate reports

## Recommended pytest configuration

```toml
[tool.pytest.ini_options]
addopts = """
--aitest-summary-model=copilot/gpt-5.4-mini
--aitest-html=aitest-reports/report.html
"""
```

Start with `copilot/gpt-5.4-mini` for routine report analysis. Opt into larger models only when you need a more expensive comparison or deeper write-up.

## Run pytest

```bash
uv run python -m pytest tests/ -v
```

JSON is always written. HTML and Markdown reports require a summary model.

## Regenerate from saved JSON

Use this for report-template work and for re-rendering without new LLM calls:

```bash
uv run pytest-skill-engineering-report aitest-reports/results.json   --html aitest-reports/report.html
```

## Refresh AI insights

```bash
uv run pytest-skill-engineering-report aitest-reports/results.json   --html aitest-reports/report.html   --summary   --summary-model copilot/gpt-5.4-mini
```

## Compact mode

Use `--aitest-summary-compact` or `--compact` when you want analysis without sending full passing transcripts.
