---
description: "Command-line options for pytest-aitest: configure reports, AI analysis models, minimum pass rates, and more."
---

# CLI Options

## Recommended: pyproject.toml

Configure once, run simply:

```toml
[tool.pytest.ini_options]
addopts = """
--aitest-summary-model=azure/gpt-5.2-chat
--aitest-html=aitest-reports/report.html
"""
```

Then just `pytest tests/` — reports are generated automatically.

## pytest Options

| Option | Description | Required |
|--------|-------------|----------|
| `--aitest-summary-model=MODEL` | Model for AI insights | Yes (for HTML/MD reports) |
| `--aitest-html=PATH` | Generate HTML report | No |
| `--aitest-md=PATH` | Generate Markdown report | No |
| `--aitest-json=PATH` | Custom JSON path | No (default: `aitest-reports/results.json`) |
| `--aitest-min-pass-rate=N` | Fail if overall pass rate below N% | No |
| `--aitest-iterations=N` | Run each test N times and aggregate results | No (default: `1`) |
| `--aitest-analysis-prompt=PATH` | Custom analysis prompt file for AI insights | No |
| `--llm-model=MODEL` | Model for `llm_assert` semantic assertions (default: `openai/gpt-5-mini`) | No |
| `--llm-vision-model=MODEL` | Vision model for `llm_assert_image` assertions (defaults to `--llm-model`) | No |

!!! note
    **JSON is always generated** after every test run, even without `--aitest-summary-model`. HTML and Markdown reports require a summary model for AI-powered analysis. JSON output contains raw test data that can be used later to regenerate reports via `pytest-aitest-report`.

### CLI Examples

```bash
# Run tests with HTML report
pytest tests/ \
    --aitest-summary-model=azure/gpt-5.2-chat \
    --aitest-html=report.html

# Run tests with Markdown report
pytest tests/ \
    --aitest-summary-model=azure/gpt-5.2-chat \
    --aitest-md=report.md

# With JSON output
pytest tests/ \
    --aitest-summary-model=azure/gpt-5.2-chat \
    --aitest-html=report.html \
    --aitest-json=results.json

# Run each test 3 times for statistical confidence
pytest tests/ \
    --aitest-summary-model=azure/gpt-5.2-chat \
    --aitest-html=report.html \
    --aitest-iterations=3
```

## pytest-aitest-report CLI

Regenerate reports from saved JSON without re-running tests.

```bash
pytest-aitest-report <json-file> [options]
```

| Option | Description | Required |
|--------|-------------|----------|
| `--html PATH` | Generate HTML report | At least one of `--html` or `--md` |
| `--md PATH` | Generate Markdown report | At least one of `--html` or `--md` |
| `--summary` | Generate AI-powered summary | No |
| `--summary-model MODEL` | Model for AI insights | Required with `--summary` |
| `--analysis-prompt PATH` | Custom analysis prompt file for AI insights | No |
| `--compact` | Omit full conversation turns for passed tests (reduces tokens) | No |

`--summary-model` can also be set via `AITEST_SUMMARY_MODEL` env var or `[tool.pytest-aitest-report]` in `pyproject.toml`.

### Examples

```bash
# Regenerate HTML from existing JSON (uses insights already in JSON)
pytest-aitest-report results.json --html report.html

# Generate Markdown report
pytest-aitest-report results.json --md report.md

# Generate both formats
pytest-aitest-report results.json --html report.html --md report.md

# Generate with fresh AI analysis
pytest-aitest-report results.json \
    --html report.html \
    --summary \
    --summary-model azure/gpt-5.2-chat
```

## Environment Variables

LLM authentication is handled by [Pydantic AI](https://ai.pydantic.dev/models/):

| Provider | Variable |
|----------|----------|
| Azure OpenAI | `AZURE_API_BASE` + `az login` |
| OpenAI | `OPENAI_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| Google | `GEMINI_API_KEY` |

### Azure OpenAI Setup

```bash
# Set endpoint
export AZURE_API_BASE=https://your-resource.openai.azure.com/

# Authenticate (no API key needed!)
az login
```

### OpenAI Setup

```bash
export OPENAI_API_KEY=sk-xxx
```
