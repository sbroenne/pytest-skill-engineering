---
description: "Generate HTML reports with AI-powered analysis, agent leaderboards, sequence diagrams, and actionable fix recommendations."
---

# How to Generate Reports

Generate HTML, JSON, and Markdown reports with AI-powered insights.

## Quick Start (Recommended)

Configure once in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
addopts = """
--aitest-summary-model=azure/gpt-5.2-chat
--aitest-html=aitest-reports/report.html
"""
```

Then just run:

```bash
pytest tests/
```

Reports are generated automatically with AI insights. This approach is recommended because:

- **Version controlled** — Team shares the same configuration
- **Less typing** — No need to remember CLI flags
- **Consistent** — Every run produces reports the same way

## What Gets Generated

| Output | When | AI Model Required? |
|--------|------|--------------------|
| **JSON** | Always (every test run) | No — raw test data, no AI analysis |
| **HTML report** | When `--aitest-html` is set | **Yes** — `--aitest-summary-model` required |
| **Markdown report** | When `--aitest-md` is set | **Yes** — `--aitest-summary-model` required |

JSON results are always saved to `aitest-reports/results.json` (or a custom path via `--aitest-json`). This raw data can be used later to regenerate HTML/MD reports without re-running tests.

!!! important
    `--aitest-summary-model` is **required for HTML and Markdown reports**. Without it, report generation will error. JSON output works without a summary model.

## CLI Options (Alternative)

You can also use CLI flags directly:

```bash
# Run tests with AI-powered HTML report
pytest tests/ \
    --aitest-summary-model=azure/gpt-5.2-chat \
    --aitest-html=report.html

# Run tests without reports (JSON is still auto-generated)
pytest tests/
```

| Option | Description |
|--------|-------------|
| `--aitest-html=PATH` | Generate HTML report (requires `--aitest-summary-model`) |
| `--aitest-md=PATH` | Generate Markdown report (requires `--aitest-summary-model`) |
| `--aitest-json=PATH` | Custom JSON path (default: `aitest-reports/results.json`) |
| `--aitest-summary-model=MODEL` | Model for AI insights (required for HTML/MD). Accepts `azure/`, `openai/`, `copilot/`, etc. |
| `--aitest-min-pass-rate=N` | Fail if pass rate below N% (e.g., `80`) |

## Report Regeneration

Regenerate reports from saved JSON without re-running tests:

```bash
# Regenerate HTML from saved JSON (reuses existing AI insights)
pytest-skill-engineering-report aitest-reports/results.json \
    --html report.html

# Generate Markdown report
pytest-skill-engineering-report aitest-reports/results.json \
    --md report.md

# Generate both HTML and Markdown
pytest-skill-engineering-report results.json \
    --html report.html \
    --md report.md

# Regenerate with fresh AI insights from a different model
pytest-skill-engineering-report results.json \
    --html report.html \
    --summary --summary-model azure/gpt-4.1
```

This is useful for:

- Iterating on report styling without re-running expensive LLM tests
- Generating different formats from one test run
- Experimenting with different AI summary models

## Agent Leaderboard

When you test multiple agents, the report shows an **Agent Leaderboard** ranking all configurations:

| Agent | Pass Rate | Cost |
|-------|-----------|------|
| ✓ gpt-4.1 (detailed) | 100% | $0.15 |
| ✓ gpt-5-mini (detailed) | 97% | $0.03 |
| ✗ gpt-5-mini (concise) | 82% | $0.02 |

**Winning Agent = Highest pass rate → Lowest cost (tiebreaker)**

### Dimension Detection

The AI detects *what varies* between agents to focus its analysis:

| What Varies | AI Analysis Focuses On |
|-------------|------------------------|
| Model | Which model works best |
| Custom Agent | Which agent instructions work best |
| Skill | Whether domain knowledge helps |
| Server | Which implementation is more reliable |

**Winning = Highest pass rate → Lowest cost (tiebreaker)**

### Leaderboard Ranking

When comparing Agents, rankings are based on:

1. **Pass rate** (primary) — higher is better
2. **Total cost** (tiebreaker) — lower is better

## AI Insights

Reports include AI analysis with actionable recommendations. For a detailed explanation of each insight section, see [AI Analysis](../explanation/ai-analysis.md).

### Recommended Models

Use the **most capable model you can afford** for quality analysis:

| Provider | Recommended Models |
|----------|-------------------|
| Azure OpenAI | `azure/gpt-5.2-chat` (best), `azure/gpt-4.1` |
| OpenAI | `openai/gpt-4.1`, `openai/gpt-4o` |
| Anthropic | `anthropic/claude-opus-4`, `anthropic/claude-sonnet-4` |

!!! warning "Don't Use Cheap Models for Analysis"
    Smaller models (gpt-4o-mini, gpt-5-mini) produce generic, low-quality insights.
    The summary model analyzes your test results and generates actionable feedback.
    Use your most capable model here—this is a one-time cost per test run.

## Report Structure

For details on the HTML report layout including header, leaderboard, and test details, see [Report Structure](../contributing/report-structure.md).

## Next Steps

- [CI/CD Integration](ci-cd.md) — JUnit XML, GitHub Actions, Azure Pipelines
