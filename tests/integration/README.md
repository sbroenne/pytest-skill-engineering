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
    ├── test_09_cli.py           # CLI workflows
    ├── test_10_ab_servers.py    # Configuration A/B comparison
    ├── test_11_iterations.py    # Iteration reliability
    ├── test_12_custom_agents.py # Custom agent dispatch
    ├── test_13_plugins.py       # Plugin discovery and loading
    ├── test_14_skill_evals.py   # Loaded skill cases with explicit checks
    ├── test_16_skill_benchmark.py # Controlled skill comparisons
    ├── test_17_plugin_skill_workflow.py # Plugin skill execution with concrete checks
    ├── test_18_config_validation.py # Configuration validation
    └── test_19_customer_workflow.py # Ordinary author-run-fix-rerun workflow
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
3. Dependencies installed with `uv sync --frozen --all-extras`.

pytest determines outcomes from ordinary assertions. Saved JSON records execution
evidence for the coding agent to investigate; there are no judges or report renderers.

## Customer workflow

`test_19_customer_workflow.py` reuses the customer workflow from
[`examples/skill-dogfood`](../../examples/skill-dogfood/), rather than supplying
synthetic failure evidence. It requires no framework companion skill. The sample
separately preserves the historical skill comparison through frozen fixtures,
not a currently distributed feature.

The initial consumer test must genuinely fail on invoice rounding. The coding
agent reads its actual native evidence, repairs only the CLI, and reruns the
unchanged test. Fixed independent checks verify the repaired output. Child
before/after JSON and outer authoring/repair evidence remain separate; do not
treat outer usage as the total cost of all sessions.

## Adding Tests

Create evals inline and use the shared constants from `copilot/conftest.py`:

```python
from pytest_skill_engineering.copilot import CopilotEval


async def test_my_feature(copilot_eval, tmp_path):
    agent = CopilotEval(
        name="my-feature",
        model="gpt-5.6-sol",
        instructions="Create files as requested.",
        working_directory=str(tmp_path),
    )

    result = await copilot_eval(agent, "Create hello.py that prints 'hello'.")

    assert result.success
    assert (tmp_path / "hello.py").exists()
```
