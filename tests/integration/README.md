# Integration Tests

These tests verify pytest-skill-engineering works with real LLM providers. Tests are split into two harnesses — **pydantic** (Eval + eval_run, BYOM) and **copilot** (CopilotEval + copilot_eval, GitHub Copilot SDK).

## Structure

```
tests/integration/
├── conftest.py           # Shared constants and server fixtures
├── agents/               # .agent.md test fixtures
│   ├── banking-advisor.agent.md
│   ├── todo-manager.agent.md
│   └── minimal.agent.md
├── pydantic/             # Eval + eval_run tests (Azure/OpenAI, BYOM)
│   ├── conftest.py
│   ├── test_01_basic.py          # Single eval, basic MCP tool calls
│   ├── test_02_models.py         # Model comparison (parametrize)
│   ├── test_03_prompts.py        # System prompt comparison
│   ├── test_04_matrix.py         # Model × prompt 2×2 grid
│   ├── test_05_skills.py         # Skill loading + skill-enhanced behavior
│   ├── test_06_sessions.py       # Multi-turn sessions
│   ├── test_07_clarification.py  # ClarificationDetection feature
│   ├── test_08_scoring.py        # llm_score + ScoringDimension
│   ├── test_09_cli.py            # CLIServer wrapping shell commands
│   ├── test_10_ab_servers.py     # A/B server comparison
│   ├── test_11_iterations.py     # --aitest-iterations=N reliability
│   └── test_12_custom_agents.py  # Eval.from_agent_file + load_custom_agent
├── copilot/              # CopilotEval + copilot_eval tests (GitHub Copilot SDK)
│   ├── conftest.py
│   ├── test_events.py            # SDK event capture
│   ├── test_01_basic.py          # File create + refactor
│   ├── test_02_models.py         # Model comparison
│   ├── test_03_instructions.py   # Instruction differentiation + excluded_tools
│   ├── test_05_skills.py         # Skill A/B comparison
│   └── test_12_custom_agents.py  # Custom agents + forced subagent dispatch
└── prompts/              # Plain .md system prompt files
└── skills/               # Test skill directories
```

## Quick Start

### Pydantic harness (Azure OpenAI)

```bash
# Prerequisites
az login
export AZURE_API_BASE=https://your-resource.cognitiveservices.azure.com

# Run all pydantic tests
uv run python -m pytest tests/integration/pydantic/ -v

# Run a specific file
uv run python -m pytest tests/integration/pydantic/test_01_basic.py -v

# Run a specific test
uv run python -m pytest tests/integration/pydantic/test_01_basic.py::TestBankingBasic::test_balance_check_and_transfer -v
```

### Copilot harness (GitHub Copilot SDK)

```bash
# Prerequisites
uv sync --extra copilot
gh auth login

# Run all copilot tests
uv run python -m pytest tests/integration/copilot/ -v
```

> **CRITICAL:** Never mix harnesses in one session. The plugin raises `pytest.UsageError` if both `eval_run` and `copilot_eval` are collected together.

## Prerequisites

1. **Azure login** (Entra ID auth — no API keys needed):
   ```bash
   az login
   export AZURE_API_BASE=https://your-resource.cognitiveservices.azure.com
   ```

2. **Models available** (checked 2026-02-23):
   - `gpt-5-mini` — cheapest, use for most tests
   - `gpt-5.2-chat` — for AI summary generation
   - `gpt-4.1` — most capable

3. **For Copilot tests only:**
   ```bash
   uv sync --extra copilot
   gh auth login  # or set GITHUB_TOKEN
   ```

## MCP Test Servers

Built-in test servers in `src/pytest_skill_engineering/testing/`:

| Server | Tools | Purpose |
|--------|-------|---------|
| `banking_mcp.py` | get_balance, get_all_balances, transfer, deposit, withdraw, get_transactions | Financial workflows |
| `todo_mcp.py` | add_task, complete_task, list_tasks, delete_task, get_task, update_task | CRUD operations |

## Adding New Tests

Create evals inline using constants from `conftest.py`:

```python
from pytest_skill_engineering import Eval, Provider
from ..conftest import DEFAULT_MODEL, DEFAULT_RPM, DEFAULT_TPM, DEFAULT_MAX_TURNS

async def test_my_feature(eval_run, banking_server):
    agent = Eval.from_instructions(
        "my-agent",
        "You are a banking assistant.",
        provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
        mcp_servers=[banking_server],
        max_turns=DEFAULT_MAX_TURNS,
    )

    result = await eval_run(agent, "What's my checking balance?")

    assert result.success
    assert result.tool_was_called("get_balance")
```
