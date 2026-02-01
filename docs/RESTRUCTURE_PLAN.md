# pytest-aitest Restructure Plan

## Overview

Restructure pytest-aitest into a cleaner architecture with smart reporting that auto-detects parametrized dimensions. Use native pytest `@parametrize` for all matrix testing instead of custom markers.

## Core Insight

pytest already solves execution:
```python
@pytest.mark.parametrize("model", ["gpt-4o", "claude-3-haiku"])
@pytest.mark.parametrize("prompt", [PROMPT_V1, PROMPT_V2])
# → 4 tests automatically
```

**We only need to build smart reporting** that pivots results by detected dimensions.

---

## Proposed Architecture

```
pytest-aitest/
├── src/pytest_aitest/
│   ├── __init__.py
│   ├── plugin.py              # Pytest hooks + CLI options
│   │
│   ├── core/                  # Core abstractions
│   │   ├── __init__.py
│   │   ├── agent.py           # Agent, Provider dataclasses
│   │   ├── prompt.py          # Prompt dataclass + YAML loading
│   │   ├── result.py          # AgentResult, Turn, ToolCall
│   │   └── errors.py          # Custom exceptions
│   │
│   ├── execution/             # Test execution
│   │   ├── __init__.py
│   │   ├── engine.py          # AgentEngine (LLM loop + tool dispatch)
│   │   ├── servers.py         # MCP/CLI server management
│   │   └── retry.py           # Rate limit handling, retries
│   │
│   ├── fixtures/              # Pytest fixtures
│   │   ├── __init__.py
│   │   ├── run.py             # aitest_run fixture
│   │   ├── judge.py           # judge fixture (pytest-llm-assert)
│   │   └── factories.py       # agent_factory, server_factory
│   │
│   ├── reporting/             # Smart reporting
│   │   ├── __init__.py
│   │   ├── collector.py       # Collects results + extracts parametrize info
│   │   ├── aggregator.py      # Groups results by dimension, computes stats
│   │   ├── generator.py       # Composes renderers based on detected dimensions
│   │   └── renderers/         # Composable HTML fragments
│   │       ├── __init__.py
│   │       ├── base.py        # BaseRenderer interface
│   │       ├── summary.py     # Overall stats cards
│   │       ├── test_list.py   # Expandable test results
│   │       ├── comparison.py  # 1D comparison table (models OR prompts)
│   │       └── matrix.py      # 2D comparison grid (model × prompt)
│   │
│   ├── templates/             # Jinja2 templates (smaller, focused)
│   │   ├── layout.html        # Base HTML shell with nav
│   │   ├── summary.html       # Stats cards fragment
│   │   ├── test_card.html     # Single test result
│   │   ├── comparison.html    # 1D comparison table
│   │   └── matrix.html        # 2D comparison grid
│   │
│   └── testing/               # Test harnesses (unchanged)
│       ├── __init__.py
│       ├── store.py           # KeyValueStore for testing
│       ├── mcp_server.py      # Test MCP server
│       └── cli_server.py      # Test CLI server
```

---

## YAML Prompt Specification

```yaml
# Required
name: string          # Unique identifier for the prompt

# Optional
version: string       # Semantic version (default: "1.0")
description: string   # Human-readable description
system_prompt: string # The actual system prompt text (can be multi-line)
```

Example:
```yaml
name: weather-detailed
version: "2.1"
description: Detailed weather responses with forecasts
system_prompt: |
  You are a helpful weather assistant.
  
  When asked about weather:
  1. Always include current temperature in Celsius
  2. Include humidity and wind speed
  3. Provide a 3-day forecast if available
  4. Be friendly but concise
```

---

## Report Auto-Composition Logic

```python
dims = aggregator.detect_dimensions(results)

if len(dims) == 0:
    # Simple test list only
    sections = [Summary, TestList]
elif len(dims) == 1:
    # 1D comparison + test list
    sections = [Summary, Comparison(dims[0]), TestList]
elif len(dims) >= 2:
    # 2D matrix + 1D comparisons + test list
    sections = [Summary, Matrix(dims[0], dims[1]), 
                Comparison(dims[0]), Comparison(dims[1]), TestList]
```

---

## Usage Examples

### Basic (no parametrize)
```python
async def test_weather(aitest_run, my_server):
    agent = Agent(provider=Provider(model="gpt-4o-mini"), mcp_servers=[my_server])
    result = await aitest_run(agent, "Weather in Paris?")
    assert result.tool_was_called("get_weather")
```
→ Report: Summary + Test List

### Model Comparison
```python
@pytest.mark.parametrize("model", ["gpt-4o", "gpt-4o-mini", "claude-3-haiku"])
async def test_models(aitest_run, my_server, model):
    agent = Agent(provider=Provider(model=model), mcp_servers=[my_server])
    result = await aitest_run(agent, "Weather in Paris?")
    assert result.success
```
→ Report: Summary + Model Comparison Table + Test List

### YAML Prompt Comparison
```python
# conftest.py
from pytest_aitest import load_prompts
PROMPTS = load_prompts(Path("prompts/"))

# test_prompts.py
@pytest.mark.parametrize("prompt", PROMPTS, ids=lambda p: p.name)
async def test_prompts(aitest_run, my_server, prompt):
    agent = Agent(
        provider=Provider(model="gpt-4o-mini"),
        system_prompt=prompt.system_prompt,
        mcp_servers=[my_server]
    )
    result = await aitest_run(agent, "Weather in Paris?")
    assert result.success
```
→ Report: Summary + Prompt Comparison Table + Test List

### Full Matrix
```python
@pytest.mark.parametrize("model", ["gpt-4o", "claude-3-haiku"])
@pytest.mark.parametrize("prompt", PROMPTS, ids=lambda p: p.name)
async def test_matrix(aitest_run, my_server, model, prompt):
    agent = Agent(
        provider=Provider(model=model),
        system_prompt=prompt.system_prompt,
        mcp_servers=[my_server]
    )
    result = await aitest_run(agent, "Weather in Paris?")
    assert result.success
```
→ Report: Summary + 2D Matrix + Model Comparison + Prompt Comparison + Test List
