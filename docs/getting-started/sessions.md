---
description: "Test multi-turn conversations where agents maintain context across tests. Validate session continuity, context retention, and sequential workflows."
---

# Multi-Turn Sessions

So far, each test is independent—the agent has no memory between tests. **Sessions** let multiple tests share conversation history, simulating real multi-turn interactions.

## Why Sessions?

Real agents don't answer single questions. Users have conversations:

1. "What's my checking account balance?"
2. "Transfer $200 to savings" ← Requires remembering the accounts
3. "What are my new balances?" ← Requires remembering the transfer

Without sessions, test 2 would fail—the agent doesn't know which accounts were discussed.

## Defining a Session

Use the `@pytest.mark.session` marker:

```python
import pytest
from pytest_skill_engineering import Agent, Provider, MCPServer

banking_server = MCPServer(command=["python", "banking_mcp.py"])

banking_agent = Agent(
    name="banking",
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[banking_server],
)

@pytest.mark.session("banking-chat")
class TestBankingConversation:
    """Tests run in order, sharing conversation history."""
    
    async def test_initial_query(self, aitest_run):
        """First message - establishes context."""
        result = await aitest_run(banking_agent, "What's my checking account balance?")
        assert result.success
        assert result.tool_was_called("get_balance")
    
    async def test_followup(self, aitest_run):
        """Second message - uses context from first."""
        result = await aitest_run(banking_agent, "Transfer $200 to savings")
        assert result.success
        # Agent remembers we were talking about checking
        assert result.tool_was_called("transfer")
    
    async def test_verification(self, aitest_run):
        """Third message - builds on full conversation."""
        result = await aitest_run(banking_agent, "What are my new balances?")
        assert result.success
```

**Key points:**

- Tests in a session run **in order** (top to bottom)
- Each test sees the **full conversation history** from previous tests

!!! warning "Not compatible with pytest-xdist"
    Sessions require sequential test execution to maintain conversation order.
    Don't use `-n auto` or other parallel execution with session tests.
- The session name (`"banking-chat"`) groups related tests

## Session Context Flow

```
test_initial_query
    User: "What's my checking account balance?"
    Agent: "Your checking balance is $1,500.00..."
    ↓ context passed to next test

test_followup  
    [Previous messages included]
    User: "Transfer $200 to savings"
    Agent: "Done! Transferred $200 from checking to savings..."
    ↓ context passed to next test

test_verification
    [All previous messages included]
    User: "What are my new balances?"
    Agent: "Checking: $1,300, Savings: $3,200..."
```

## When to Use Sessions

| Scenario | Use Session? |
|----------|--------------|
| Single Q&A tests | No |
| Multi-turn conversation | Yes |
| Workflow with multiple steps | Yes |
| Independent feature tests | No |
| Testing context retention | Yes |

## Sessions with Parametrize

You can combine sessions with model comparison:

```python
@pytest.mark.session("shopping-flow")
@pytest.mark.parametrize("model", ["gpt-5-mini", "gpt-4.1"])
class TestShoppingWorkflow:
    """Test the same conversation flow with different models."""
    
    async def test_browse(self, aitest_run, model, shopping_server):
        agent = Agent(
            name=f"shop-{model}",
            provider=Provider(model=f"azure/{model}"),
            mcp_servers=[shopping_server],
        )
        result = await aitest_run(agent, "Show me running shoes")
        assert result.success
    
    async def test_select(self, aitest_run, model, shopping_server):
        agent = Agent(
            name=f"shop-{model}",
            provider=Provider(model=f"azure/{model}"),
            mcp_servers=[shopping_server],
        )
        result = await aitest_run(agent, "I'll take the Nike ones")
        assert result.success
```

This creates two separate session flows:

- `shopping-flow[gpt-5-mini]`: browse → select (with gpt-5-mini)
- `shopping-flow[gpt-4.1]`: browse → select (with gpt-4.1)

The report shows each session as a complete flow with all turns visualized.

## Next Steps

- [Comparing Configurations](comparing.md) — Pattern for parametrized tests
- [Generate Reports](../how-to/generate-reports.md) — Understand report output

> 📁 **Real Example:** [test_sessions.py](https://github.com/sbroenne/pytest-skill-engineering/blob/main/tests/integration/test_sessions.py) — Banking workflow with session continuity
