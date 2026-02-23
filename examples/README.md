# Examples

Working examples are in `tests/integration/` — they are the best reference for how to use pytest-skill-engineering.

## Test Files

| File | What it demonstrates |
|------|---------------------|
| [pydantic/test_01_basic.py](../tests/integration/pydantic/test_01_basic.py) | Natural language → tool usage with Banking and Todo servers |
| [pydantic/test_02_models.py](../tests/integration/pydantic/test_02_models.py) | Model comparison (parametrize) |
| [pydantic/test_03_prompts.py](../tests/integration/pydantic/test_03_prompts.py) | System prompt comparison |
| [pydantic/test_04_matrix.py](../tests/integration/pydantic/test_04_matrix.py) | Model × prompt 2×2 grid |
| [pydantic/test_05_skills.py](../tests/integration/pydantic/test_05_skills.py) | Skills with references and metadata |
| [pydantic/test_06_sessions.py](../tests/integration/pydantic/test_06_sessions.py) | Multi-turn session continuity |
| [pydantic/test_07_clarification.py](../tests/integration/pydantic/test_07_clarification.py) | ClarificationDetection feature |
| [pydantic/test_08_scoring.py](../tests/integration/pydantic/test_08_scoring.py) | llm_score + ScoringDimension |
| [pydantic/test_09_cli.py](../tests/integration/pydantic/test_09_cli.py) | CLIServer wrapping shell commands |
| [pydantic/test_10_ab_servers.py](../tests/integration/pydantic/test_10_ab_servers.py) | A/B server comparison |
| [pydantic/test_11_iterations.py](../tests/integration/pydantic/test_11_iterations.py) | --aitest-iterations=N reliability |
| [pydantic/test_12_custom_agents.py](../tests/integration/pydantic/test_12_custom_agents.py) | Eval.from_agent_file + load_custom_agent |

## Run Examples

```bash
# Prerequisites
uv add pytest-skill-engineering
az login               # For Azure OpenAI

# Run basic usage tests
uv run python -m pytest tests/integration/pydantic/test_01_basic.py -v

# Run all pydantic tests
uv run python -m pytest tests/integration/pydantic/ -v

# Run with report
uv run python -m pytest tests/integration/pydantic/ -v --aitest-html=report.html
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
