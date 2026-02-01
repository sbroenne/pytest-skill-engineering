# Reporting

Generate HTML and JSON reports with auto-detected comparison views.

## Quick Start

```bash
# Generate HTML report
pytest tests/ --aitest-html=report.html

# Generate JSON report
pytest tests/ --aitest-json=report.json

# Both formats
pytest tests/ --aitest-html=report.html --aitest-json=report.json

# With AI-powered summary
pytest tests/ --aitest-html=report.html --aitest-summary
```

## CLI Options

| Option | Description |
|--------|-------------|
| `--aitest-html=PATH` | Generate HTML report |
| `--aitest-json=PATH` | Generate JSON report |
| `--aitest-summary` | Include AI-powered analysis |
| `--aitest-model=MODEL` | Model for AI summary |

## pyproject.toml Configuration

Set defaults once:

```toml
[tool.pytest.ini_options]
addopts = """
--aitest-model=azure/gpt-5-mini
--aitest-html=reports/report.html
--aitest-summary
"""
```

## Adaptive Reports

Reports auto-detect test dimensions from `@pytest.mark.parametrize` and adapt:

| Test Pattern | Report Shows |
|--------------|--------------|
| No parametrize | Test list |
| `@parametrize("model", ...)` | Model comparison table |
| `@parametrize("prompt", ...)` | Prompt comparison table |
| Both | 2D matrix grid |

### Simple Test List

With no parametrize, you get a clean test list:

```python
@pytest.mark.asyncio
async def test_weather(aitest_run, agent):
    result = await aitest_run(agent, "What's the weather?")
    assert result.success
```

### Model Comparison

Parametrize on model to get a comparison table:

```python
@pytest.mark.parametrize("model", ["gpt-5-mini", "gpt-4.1"])
@pytest.mark.asyncio
async def test_weather(aitest_run, model):
    agent = Agent(provider=Provider(model=f"azure/{model}"), ...)
    result = await aitest_run(agent, "What's the weather?")
    assert result.success
```

Report shows:
- Pass rate per model
- Token usage per model
- Cost comparison

### Prompt Comparison

Parametrize on prompt to compare prompts:

```python
PROMPTS = [
    Prompt(name="concise", system_prompt="Be brief."),
    Prompt(name="detailed", system_prompt="Be thorough."),
]

@pytest.mark.parametrize("prompt", PROMPTS, ids=lambda p: p.name)
@pytest.mark.asyncio
async def test_weather(aitest_run, prompt):
    agent = Agent(system_prompt=prompt.system_prompt, ...)
    result = await aitest_run(agent, "What's the weather?")
    assert result.success
```

### Matrix Comparison

Combine both for full grid:

```python
@pytest.mark.parametrize("model", ["gpt-5-mini", "gpt-4.1"])
@pytest.mark.parametrize("prompt", PROMPTS, ids=lambda p: p.name)
@pytest.mark.asyncio
async def test_matrix(aitest_run, model, prompt):
    ...
```

Report shows a 2D matrix: models vs prompts.

## AI Summary

Enable AI-powered analysis of test results:

```bash
pytest tests/ --aitest-html=report.html --aitest-summary
```

The summary includes:
- Overall verdict
- Key observations
- Failure patterns
- Recommendations

Requires `--aitest-model` to specify which model generates the summary.

## HTML Report Contents

The HTML report includes:

### Summary Dashboard
- Total/passed/failed counts
- Success rate
- Total tokens and cost

### Model/Prompt Comparison (if parametrized)
- Side-by-side metrics
- Success rates
- Token usage

### Detailed Test Results
- Each test with pass/fail status
- Tool calls made
- Token usage
- Execution time

### AI Summary (if enabled)
- LLM-generated analysis
- Recommendations

## JSON Report Structure

```json
{
  "summary": {
    "total": 10,
    "passed": 8,
    "failed": 2,
    "success_rate": 0.8
  },
  "dimensions": {
    "models": ["gpt-5-mini", "gpt-4.1"],
    "prompts": ["concise", "detailed"]
  },
  "tests": [
    {
      "name": "test_weather",
      "parameters": {
        "model": "gpt-5-mini",
        "prompt": "concise"
      },
      "passed": true,
      "duration_ms": 2500,
      "tokens": 450,
      "tool_calls": ["get_weather"]
    }
  ]
}
```

## Report Examples

### Basic Usage

```bash
# Run tests and generate report
pytest tests/integration/ --aitest-html=report.html

# Open report
open report.html
```

### CI/CD Integration

```yaml
# .github/workflows/test.yml
- name: Run agent tests
  run: |
    pytest tests/ \
      --aitest-html=reports/report.html \
      --aitest-json=reports/report.json

- name: Upload reports
  uses: actions/upload-artifact@v4
  with:
    name: test-reports
    path: reports/
```

### Compare Models in CI

```yaml
- name: Benchmark models
  run: |
    pytest tests/integration/test_benchmark.py \
      --aitest-html=benchmark-report.html \
      --aitest-summary
```
