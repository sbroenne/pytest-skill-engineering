# Integration Tests

These tests verify pytest-skill-engineering works with real LLM providers. They demonstrate realistic multi-step workflows — the kind of thing LLMs actually do with MCP servers.

## Test Files

| File | Purpose | Tests | ~Runtime |
|------|---------|-------|----------|
| `test_basic_usage.py` | Multi-step banking & todo workflows | 12 | ~3-5 min |
| `test_dimension_detection.py` | Model × prompt comparison | 4+ | ~2 min |
| `test_skills.py` | Skill loading and metadata | 3 | ~1 min |
| `test_skill_improvement.py` | Skill before/after comparisons | 5+ | ~2 min |
| `test_sessions.py` | Multi-turn session continuity | 6 | ~2 min |
| `test_ai_summary.py` | AI insights generation | 3 | ~1 min |
| `test_ab_servers.py` | Server A/B testing | 4+ | ~2 min |
| `test_cli_server.py` | CLI server testing | 2 | ~1 min |

## Quick Start

```bash
# Run basic tests (recommended for first-time setup)
pytest tests/integration/test_basic_usage.py -v

# Run all integration tests
pytest tests/integration/ -v

# Run specific test
pytest tests/integration/test_basic_usage.py::TestBankingWorkflows::test_balance_check_and_transfer -v
```

## Prerequisites

1. **Azure login** (Entra ID auth - no API keys needed):
   ```bash
   az login
   ```

2. **Set endpoint** (Pydantic AI standard var):
   ```bash
   export AZURE_API_BASE=https://your-resource.cognitiveservices.azure.com
   ```

### Copilot integration note

Some Copilot integration tests (for example optimizer integration) require an auxiliary judge model. Those tests now fail fast when no provider model is reachable.

Any supported provider is acceptable for that judge path:
- Azure (`AZURE_API_BASE` or `AZURE_OPENAI_ENDPOINT`)
- OpenAI (`OPENAI_API_KEY`)
- Copilot (`gh auth login` or `GITHUB_TOKEN`)

Optional override for test runs:

```bash
AITEST_INTEGRATION_JUDGE_MODEL=copilot/gpt-5-mini pytest tests/integration/copilot/test_optimizer_integration.py -v
```

## Test Descriptions

### test_basic_usage.py

**Multi-step workflows** — the tests that actually matter. Each test requires:
- Multiple tool calls
- Reasoning between calls
- State management or data synthesis

**TestBankingWorkflows:**
- `test_balance_check_and_transfer` — Check balance, transfer between accounts
- `test_deposit_and_withdrawal` — Deposit and withdraw money
- `test_discovery_then_action` — Get all balances, then act on them
- `test_transaction_history_analysis` — Query and analyze transaction history
- `test_error_recovery` — Handle insufficient funds gracefully

**TestTodoWorkflows:**
- `test_project_setup_workflow` — Add 3 items to groceries list, verify all added
- `test_task_lifecycle_workflow` — Create → complete → verify done
- `test_priority_management_workflow` — Create tasks with priorities, recommend first action
- `test_batch_completion_workflow` — Add 3, complete 2, show remaining
- `test_multi_list_organization` — Tasks across personal + work lists

**TestAdvancedPatterns:**
- `test_ambiguous_request_clarification` — Handle "How much money do I have?" intelligently
- `test_conditional_logic_workflow` — Check-then-act based on current state

### test_dimension_detection.py

**Model × prompt comparison.** Tests with all dimension permutations.

### test_skill_improvement.py

**Skill before/after comparisons.** Financial advisor skill impact on banking tasks.

### test_sessions.py

**Multi-turn sessions.** Banking workflow with session continuity.

## Prompts Directory

```
prompts/
├── concise.md       # Brief, direct responses
├── detailed.md      # Thorough explanations
└── structured.md    # Emoji-formatted output
```

## MCP Test Servers

Built-in test servers in `src/pytest_skill_engineering/testing/`:

| Server | Tools | Purpose |
|--------|-------|---------|
| `banking_mcp.py` | get_balance, get_all_balances, transfer, deposit, withdraw, get_transactions | Financial workflows |
| `todo_mcp.py` | add_task, complete_task, list_tasks, delete_task, get_lists | CRUD operations |

## Adding New Tests

Create agents inline using constants from `conftest.py`:

```python
from pytest_skill_engineering import Agent, Provider
from .conftest import DEFAULT_MODEL, DEFAULT_RPM, DEFAULT_TPM, DEFAULT_MAX_TURNS

async def test_my_feature(aitest_run, banking_server):
    agent = Agent(
        provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
        mcp_servers=[banking_server],
        system_prompt="You are a banking assistant.",
        max_turns=DEFAULT_MAX_TURNS,
    )
    
    result = await aitest_run(agent, "What's my checking balance?")
    
    assert result.success
    assert result.tool_was_called("get_balance")
```
