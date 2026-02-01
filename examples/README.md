# Examples

Working examples are in `tests/integration/` — they are the best reference for how to use pytest-aitest.

## Test Files

| File | What it demonstrates |
|------|---------------------|
| [test_basic_usage.py](../tests/integration/test_basic_usage.py) | Natural language → tool usage with Weather and Todo servers |
| [test_model_benchmark.py](../tests/integration/test_model_benchmark.py) | Compare multiple LLMs on same tests |
| [test_prompt_arena.py](../tests/integration/test_prompt_arena.py) | Compare multiple system prompts |
| [test_matrix.py](../tests/integration/test_matrix.py) | Full model × prompt grid |

## Run Examples

```bash
# Prerequisites
pip install pytest-aitest
az login  # For Azure OpenAI

# Run basic usage tests
pytest tests/integration/test_basic_usage.py -v

# Run with report
pytest tests/integration/ -v --aitest-html=report.html
```

## Test Servers

Two built-in test servers for natural language testing:

### Weather Server
```python
@pytest.fixture(scope="module")
def weather_server():
    return MCPServer(
        command=["python", "-m", "pytest_aitest.testing.weather_mcp"],
        wait=Wait.for_tools(["get_weather", "get_forecast"]),
    )

# Test: "What's the weather in Paris?"
```

### Todo Server
```python
@pytest.fixture(scope="module")
def todo_server():
    return MCPServer(
        command=["python", "-m", "pytest_aitest.testing.todo_mcp"],
        wait=Wait.for_tools(["add_task", "list_tasks"]),
    )

# Test: "Add buy milk to my shopping list"
```

## Fixtures

See [conftest.py](../tests/integration/conftest.py) for fixture patterns:

- `weather_server` / `todo_server` — Test MCP servers
- `weather_agent_factory` / `todo_agent_factory` — Create agents
- Azure token handling and temperature quirks
