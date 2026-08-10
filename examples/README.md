# Examples

Working examples live in [`tests/integration/copilot/`](../tests/integration/copilot/). They use real GitHub Copilot models and are the best reference for pytest-skill-engineering.

## Test Files

| File | What it demonstrates |
|------|----------------------|
| [`test_01_basic.py`](../tests/integration/copilot/test_01_basic.py) | Basic file creation and refactoring |
| [`test_02_models.py`](../tests/integration/copilot/test_02_models.py) | Model comparison |
| [`test_03_instructions.py`](../tests/integration/copilot/test_03_instructions.py) | System prompt comparison and tool restrictions |
| [`test_04_matrix.py`](../tests/integration/copilot/test_04_matrix.py) | Model × system prompt matrix |
| [`test_05_skills.py`](../tests/integration/copilot/test_05_skills.py) | Skill A/B comparison |
| [`test_06_sessions.py`](../tests/integration/copilot/test_06_sessions.py) | Multi-turn sessions |
| [`test_07_clarification.py`](../tests/integration/copilot/test_07_clarification.py) | Clarification detection |
| [`test_08_scoring.py`](../tests/integration/copilot/test_08_scoring.py) | LLM scoring |
| [`test_09_cli.py`](../tests/integration/copilot/test_09_cli.py) | CLI workflows |
| [`test_10_ab_servers.py`](../tests/integration/copilot/test_10_ab_servers.py) | Configuration A/B comparison |
| [`test_11_iterations.py`](../tests/integration/copilot/test_11_iterations.py) | Iteration reliability |
| [`test_12_custom_agents.py`](../tests/integration/copilot/test_12_custom_agents.py) | Custom agent dispatch |
| [`test_13_plugins.py`](../tests/integration/copilot/test_13_plugins.py) | Plugin discovery and loading |
| [`test_14_skill_evals.py`](../tests/integration/copilot/test_14_skill_evals.py) | Skill eval execution |
| [`test_15_skill_refinement.py`](../tests/integration/copilot/test_15_skill_refinement.py) | Skill refinement |
| [`test_16_skill_benchmark.py`](../tests/integration/copilot/test_16_skill_benchmark.py) | Skill benchmarking |
| [`test_17_plugin_skill_workflow.py`](../tests/integration/copilot/test_17_plugin_skill_workflow.py) | End-to-end plugin skill workflow |
| [`test_events.py`](../tests/integration/copilot/test_events.py) | Copilot SDK event capture |

## Run Examples

```bash
# Authenticate once
gh auth login

# Run basic usage tests
uv run python -m pytest tests/integration/copilot/test_01_basic.py -v

# Run all Copilot integration tests
uv run python -m pytest tests/integration/copilot/ -v

# Generate a report
uv run python -m pytest tests/integration/copilot/test_04_matrix.py -v \
  --aitest-html=report.html
```

## MCP Server Example

`CopilotEval` accepts MCP server configurations in the Copilot SDK format:

```python
import sys

from pytest_skill_engineering.copilot import CopilotEval


banking_eval = CopilotEval(
    name="banking",
    instructions="Use the banking tools for every account request.",
    mcp_servers={
        "banking": {
            "command": sys.executable,
            "args": ["-m", "pytest_skill_engineering.testing.banking_mcp"],
            "tools": ["*"],
        }
    },
)
```

The package includes banking and todo MCP servers for integration scenarios. See [`tests/showcase/`](../tests/showcase/) for a complete banking example.
