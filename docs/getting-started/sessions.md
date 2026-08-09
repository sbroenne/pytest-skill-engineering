---
description: "Test multi-turn conversations where evals maintain context across tests. Validate session continuity, context retention, and sequential workflows."
---

# Multi-Turn Sessions

So far, each test is independent—the agent has no memory between tests. **Sessions** let multiple tests share conversation history, simulating real multi-turn interactions.

!!! note "Context-in-prompt, not stateful sessions"
    `CopilotEval` has no message-history reuse — the Copilot SDK accepts string prompts only (`send_and_wait(prompt: str)`), so there's no server-side session state to share between tests. Instead, each test embeds whatever prior context it needs directly in its prompt string. See [test_06_sessions.py](https://github.com/sbroenne/pytest-skill-engineering/blob/main/tests/integration/copilot/test_06_sessions.py) for the pattern.

## Why Sessions?

Real coding agents don't answer single questions. Users have conversations:

1. "What's my checking account balance?"
2. "Transfer $200 to savings" ← Requires remembering the accounts
3. "What are my new balances?" ← Requires remembering the transfer

Without sessions, test 2 would fail—the agent doesn't know which accounts were discussed.

## Defining a Session

`CopilotEval` has no message-history reuse, so there's no `@pytest.mark.session`
marker to apply. Instead, embed the prior context **directly in the prompt**
and let the agent use it:

```python
from pytest_skill_engineering.copilot import CopilotEval

banking_agent = CopilotEval(
    name="banking",
    instructions="You are a banking assistant.",
)


class TestBankingConversation:
    """Each test embeds the prior turns' context directly in its prompt."""

    async def test_initial_query(self, copilot_eval):
        """First message - establishes context."""
        result = await copilot_eval(banking_agent, "What's my checking account balance?")
        assert result.success

    async def test_followup(self, copilot_eval):
        """Second message - context from the first turn is embedded in the prompt."""
        result = await copilot_eval(
            banking_agent,
            "Context: we previously discussed my checking account balance.\n\n"
            "Transfer $200 to savings",
        )
        assert result.success

    async def test_verification(self, copilot_eval):
        """Third message - context from all prior turns is embedded in the prompt."""
        result = await copilot_eval(
            banking_agent,
            "Context: we previously discussed my checking balance and a $200 "
            "transfer to savings.\n\n"
            "What are my new balances?",
        )
        assert result.success
```

**Key points:**

- There is no shared conversation state between tests — each `copilot_eval()` call starts a fresh Copilot session
- Each test embeds whatever prior context it needs directly in its prompt string
- See [test_06_sessions.py](https://github.com/sbroenne/pytest-skill-engineering/blob/main/tests/integration/copilot/test_06_sessions.py) for the full working pattern

## Session Context Flow

```
test_initial_query
    User: "What's my checking account balance?"
    Eval: "Your checking balance is $1,500.00..."
    ↓ context embedded in next test's prompt

test_followup
    User: "Context: we previously discussed my checking balance.
            Transfer $200 to savings"
    Eval: "Done! Transferred $200 from checking to savings..."
    ↓ context embedded in next test's prompt

test_verification
    User: "Context: we previously discussed my checking balance and a
            $200 transfer to savings. What are my new balances?"
    Eval: "Checking: $1,300, Savings: $3,200..."
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
@pytest.mark.parametrize("model", ["claude-opus-4.8", "gpt-5.6-sol"])
class TestShoppingWorkflow:
    """Test the same conversation flow with different models."""

    async def test_browse(self, copilot_eval, model):
        agent = CopilotEval(
            name=f"shop-{model}",
            model=model,
            instructions="You are a shopping assistant.",
        )
        result = await copilot_eval(agent, "Show me running shoes")
        assert result.success

    async def test_select(self, copilot_eval, model):
        agent = CopilotEval(
            name=f"shop-{model}",
            model=model,
            instructions=(
                "You are a shopping assistant. Context: the user was just "
                "shown a list of running shoes."
            ),
        )
        result = await copilot_eval(agent, "I'll take the Nike ones")
        assert result.success
```

This creates two separate parametrized runs, each with its own browse → select prompts:

- `test_browse[claude-opus-4.8]` / `test_select[claude-opus-4.8]`
- `test_browse[gpt-5.6-sol]` / `test_select[gpt-5.6-sol]`

The report shows each model's turns side by side for comparison.

## Next Steps

- [Comparing Configurations](comparing.md) — Pattern for parametrized tests
- [Generate Reports](../how-to/generate-reports.md) — Understand report output

> 📁 **Real Example:** [test_06_sessions.py](https://github.com/sbroenne/pytest-skill-engineering/blob/main/tests/integration/copilot/test_06_sessions.py) — Context-in-prompt pattern for simulating session continuity
