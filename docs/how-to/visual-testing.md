---
description: "Validate generated HTML reports with deterministic fixture-backed assertions."
---

# Visual Testing

pytest-skill-engineering no longer uses Playwright for report validation. The checked-in report fixtures are generated deterministically, then exercised through fast HTML assertions in `tests/unit/test_html_reports.py`.

## What is covered

- single-eval reports
- multi-eval comparison layouts
- session grouping
- three-agent selector behavior
- Mermaid embeds and overlay wiring
- stable agent IDs and visible display labels

## Regenerate the report fixtures

```bash
uv run python scripts/generate_fixture_html.py
```

That command refreshes:

- `tests/fixtures/reports/*.json`
- `docs/reports/*.html`
- `docs/reports/*.md`
- `docs/demo/hero-report.{json,html,md}`

The authoritative fixture manifest lives in `tests/fixtures/report_fixtures.py`.

## Run the deterministic HTML checks

```bash
uv run python -m pytest tests/unit/test_html_reports.py -q
uv run python -m pytest tests/unit/test_json_contract.py -q
```

## When to use slow coverage

Model-comparison and other expensive Copilot suites are marked `slow` and skipped by default. Opt in explicitly:

```bash
uv run python -m pytest tests/integration/copilot/test_02_models.py -v --run-slow
```

## Updating report UI

When you change report components, CSS, or serialization:

1. edit the source
2. run `uv run python scripts/generate_fixture_html.py`
3. run the deterministic HTML/JSON tests
4. inspect the generated files in `docs/reports/` or `docs/demo/`
