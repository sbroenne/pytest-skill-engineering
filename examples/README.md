# Examples

Working examples are in `tests/integration/` — they are the best reference for how to use pytest-skill-engineering.

## Test Files

| File | What it demonstrates |
|------|---------------------|
| [test_basic_usage.py](../tests/integration/test_basic_usage.py) | Natural language → tool usage with Banking and Todo servers |
| [test_dimension_detection.py](../tests/integration/test_dimension_detection.py) | Multi-dimension comparison (model × prompt) |
| [test_skills.py](../tests/integration/test_skills.py) | Skills with references and metadata |
| [test_skill_improvement.py](../tests/integration/test_skill_improvement.py) | Skill before/after comparisons |

## Run Examples

```bash
# Prerequisites
uv add pytest-skill-engineering
az login               # For Azure OpenAI

# Run basic usage tests
pytest tests/integration/test_basic_usage.py -v

# Run with report
pytest tests/integration/ -v --aitest-html=report.html
```

## Test Servers

Two built-in test servers for natural language testing:

### Banking Server
```python
@pytest.fixture(scope="module")
def banking_server():
    return MCPServer(
        command=["python", "-m", "pytest_skill_engineering.testing.banking_mcp"],
        wait=Wait.for_tools(["get_balance", "transfer"]),
    )

# Test: "What's my checking balance?"
```

### Todo Server
```python
@pytest.fixture(scope="module")
def todo_server():
    return MCPServer(
        command=["python", "-m", "pytest_skill_engineering.testing.todo_mcp"],
        wait=Wait.for_tools(["add_task", "list_tasks"]),
    )

# Test: "Add buy milk to my shopping list"
```

## Fixtures

See [conftest.py](../tests/integration/conftest.py) for fixture patterns:

- `banking_server` / `todo_server` — Test MCP servers  
- `DEFAULT_MODEL`, `DEFAULT_RPM`, `DEFAULT_TPM`, `DEFAULT_MAX_TURNS` — Constants for eval creation
- Azure token handling
