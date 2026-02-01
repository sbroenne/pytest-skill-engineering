# Integration Tests

These tests verify pytest-aitest works with real LLM providers. They demonstrate realistic multi-step workflows — the kind of thing LLMs actually do with MCP servers.

## Test Files

| File | Purpose | Models | Prompts | Tests | ~Runtime |
|------|---------|--------|---------|-------|----------|
| `test_basic_usage.py` | Multi-step workflows | 1 (gpt-5-mini) | 1 | 12 | ~3-5 min |
| `test_model_benchmark.py` | Compare multiple models | 2 (gpt-5-mini, gpt-4.1) | 1 | 6 | ~1 min |
| `test_prompt_arena.py` | Compare multiple prompts | 1 (gpt-5-mini) | 3 | 6 | ~1 min |
| `test_matrix.py` | Model × Prompt grid | 2 | 3 | 12 | ~2 min |

## Quick Start

```bash
# Run basic tests (recommended for first-time setup)
pytest tests/integration/test_basic_usage.py -v

# Run all integration tests
pytest tests/integration/ -v

# Run by category marker
pytest tests/integration/ -m basic       # Multi-step workflows
pytest tests/integration/ -m benchmark   # Model comparison
pytest tests/integration/ -m arena       # Prompt comparison
pytest tests/integration/ -m matrix      # Model × Prompt grid

# Run specific test
pytest tests/integration/test_basic_usage.py::TestWeatherWorkflows::test_trip_planning_compare_destinations -v
```

## Prerequisites

1. **Azure login** (Entra ID auth - no API keys needed):
   ```bash
   az login
   ```

2. **Set endpoint** (LiteLLM standard var):
   ```bash
   export AZURE_API_BASE=https://your-resource.cognitiveservices.azure.com
   ```

## Test Descriptions

### test_basic_usage.py

**Multi-step workflows** — the tests that actually matter. Each test requires:
- Multiple tool calls
- Reasoning between calls
- State management or data synthesis

**TestWeatherWorkflows:**
- `test_trip_planning_compare_destinations` — Get forecasts for Paris + Sydney, recommend best
- `test_packing_advice_workflow` — Check London + Berlin weather, suggest umbrella
- `test_discovery_then_query_workflow` — List cities → find warmest → get forecast
- `test_comparative_analysis_three_cities` — Compare Tokyo/Berlin/New York, rank by temp
- `test_error_recovery_workflow` — Handle invalid city, recover gracefully

**TestTodoWorkflows:**
- `test_project_setup_workflow` — Add 3 items to groceries list, verify all added
- `test_task_lifecycle_workflow` — Create → complete → verify done
- `test_priority_management_workflow` — Create tasks with priorities, recommend first action
- `test_batch_completion_workflow` — Add 3, complete 2, show remaining
- `test_multi_list_organization` — Tasks across personal + work lists

**TestAdvancedPatterns:**
- `test_ambiguous_request_clarification` — Handle "weather in Europe?" intelligently
- `test_conditional_logic_workflow` — Check-then-act based on current state

### test_model_benchmark.py

**Compare LLMs.** Same tests run against multiple models to compare:
- Pass rates
- Token usage
- Response quality

Models: `gpt-5-mini`, `gpt-4.1`

### test_prompt_arena.py

**Compare system prompts.** Same tests run with different prompts to find:
- Which prompt produces better results
- Which is more efficient (fewer tool calls)

Prompts: `PROMPT_BRIEF`, `PROMPT_DETAILED`, `PROMPT_STRUCTURED` (from `prompts/` YAML files)

### test_matrix.py

**Full comparison grid.** Every model × every prompt combination.

Report shows a 2D matrix of results for comprehensive analysis.

## Prompts Directory

```
prompts/
├── brief.yaml       # Minimal instructions
├── detailed.yaml    # Comprehensive guidance
└── structured.yaml  # Step-by-step format
```

## MCP Test Servers

Built-in test servers in `src/pytest_aitest/testing/`:

| Server | Tools | Purpose |
|--------|-------|---------|
| `weather_mcp.py` | get_weather, get_forecast, list_cities, compare_weather | Simple "hello world" |
| `todo_mcp.py` | add_task, complete_task, list_tasks, delete_task, get_lists | Stateful operations |

## Adding New Tests

1. Use `weather_agent_factory` or `todo_agent_factory` for simple tests
2. For custom configurations, create `Agent` directly:

```python
@pytest.mark.asyncio
async def test_my_feature(aitest_run, weather_server):
    agent = Agent(
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[weather_server],
        system_prompt="You are helpful.",
    )
    
    result = await aitest_run(agent, "What's the weather in Paris?")
    
    assert result.success
    assert result.tool_was_called("get_weather")
```
