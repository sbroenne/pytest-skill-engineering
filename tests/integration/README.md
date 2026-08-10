# Copilot Integration Tests

These tests validate pytest-skill-engineering with real GitHub Copilot models and tools. They use `CopilotEval` with the `copilot_eval` fixture; no mocked LLM execution is used.

## Structure

```text
tests/integration/
├── conftest.py                  # Shared system prompts and constants
├── agents/                      # Custom agent test fixtures
├── prompts/                     # System prompt test fixtures
├── skills/                      # Skill test fixtures
└── copilot/
    ├── conftest.py              # Copilot models, authentication, and limits
    ├── test_events.py           # SDK event capture
    ├── test_01_basic.py         # Basic file creation and refactoring
    ├── test_02_models.py        # Model comparison
    ├── test_03_instructions.py  # System prompt and tool filtering
    ├── test_04_matrix.py        # Model × system prompt matrix
    ├── test_05_skills.py        # Skill A/B comparison
    ├── test_06_sessions.py      # Multi-turn sessions
    ├── test_07_clarification.py # Clarification detection
    ├── test_08_scoring.py       # LLM scoring
    ├── test_09_cli.py           # CLI workflows
    ├── test_10_ab_servers.py    # Configuration A/B comparison
    ├── test_11_iterations.py    # Iteration reliability
    ├── test_12_custom_agents.py # Custom agent dispatch
    ├── test_13_plugins.py       # Plugin discovery and loading
    ├── test_14_skill_evals.py   # Skill eval execution
    ├── test_15_skill_refinement.py # Skill refinement
    ├── test_16_skill_benchmark.py  # Skill benchmarking
    └── test_17_plugin_skill_workflow.py # End-to-end plugin skill workflow
```

## Quick Start

```bash
# Authenticate once
gh auth login

# Run all Copilot integration tests
uv run python -m pytest tests/integration/copilot/ -v

# Run a specific file
uv run python -m pytest tests/integration/copilot/test_01_basic.py -v

# Run a specific test
uv run python -m pytest \
  tests/integration/copilot/test_01_basic.py::TestBasicFileCreation::test_create_python_file -v
```

## Prerequisites

1. GitHub Copilot authentication through `gh auth login` or `GITHUB_TOKEN`.
2. A model available through the GitHub Copilot SDK.
3. Dependencies installed with `uv sync --all-groups`.

## Adding Tests

Create evals inline and use the shared constants from `copilot/conftest.py`:

```python
from pytest_skill_engineering.copilot import CopilotEval


async def test_my_feature(copilot_eval, tmp_path):
    agent = CopilotEval(
        name="my-feature",
        model="gpt-5.4-mini",
        instructions="Create files as requested.",
        working_directory=str(tmp_path),
    )

    result = await copilot_eval(agent, "Create hello.py that prints 'hello'.")

    assert result.success
    assert (tmp_path / "hello.py").exists()
```
