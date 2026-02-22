---
description: "Moved — see Skill Engineering."
---

# Test-Driven Development for AI Interfaces

> This page has moved. See **[Skill Engineering](skill-engineering.md)** for the updated content.

## The Problem TDD Solves

Traditional code has a fast feedback loop. Write a function, the compiler catches type errors, a linter catches style issues, unit tests catch logic bugs. You iterate quickly.

AI interfaces have **no feedback loop**. You write a tool description, deploy it, and discover it's broken when users complain that the LLM picks the wrong tool. There's no compiler for "this description is confusing to an LLM." There's no linter for "this parameter name is ambiguous."

pytest-skill-engineering creates that missing feedback loop.

## The TDD Cycle

The classic Red/Green/Refactor cycle maps directly to AI interface development:

### Red: Write a Failing Test

Start with what a user would say. Don't think about implementation — think about intent:

```python
async def test_balance_check(aitest_run):
    agent = Agent(
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[banking_server],
    )
    result = await aitest_run(agent, "What's my checking account balance?")

    assert result.success
    assert result.tool_was_called("get_balance")
```

Run it. The LLM reads your tool descriptions, tries to use them, and fails. Maybe it called `get_all_balances` instead of `get_balance`. Maybe it passed `{"account_id": "checking"}` when the parameter is `account`. The test tells you exactly what went wrong.

### Green: Fix the Interface

Now improve the thing the LLM actually sees — your tool descriptions, schemas, or skill instructions:

```python
# Before: LLM confused get_balance with get_all_balances
@mcp.tool()
def get_balance(account_id: str) -> str:
    """Get balance."""  # Too vague

# After: clear name, clear description, clear parameter
@mcp.tool()
def get_balance(account: str) -> str:
    """Get the current balance for a single account (checking or savings).
    Use this for one account, not all accounts."""
```

Run the test again. It passes. The LLM now picks the right tool with the right parameters.

### Refactor: Let AI Analysis Guide You

Generate a report. The AI analysis reads your full test results and tells you what else to improve:

```
🔧 MCP Tool Feedback
- get_all_balances: Consider strengthening description to encourage
  single-call usage instead of multiple get_balance calls.
  Estimated impact: ~15–25% cost reduction on multi-account queries.

💡 Suggested description:
  "Return balances for all accounts belonging to the current user
  in a single call, including checking and savings.
  Use instead of calling get_balance for each account separately."
```

You didn't know this was a problem. The AI found it by analyzing actual LLM behavior across your test suite.

## What You're Designing

In traditional TDD, you design functions and classes. In pytest-skill-engineering, you design the **skill engineering stack** — the modular, callable capabilities the LLM actually sees and has to orchestrate:

| Traditional TDD | Skill Engineering TDD |
|-----------------|-----------------|
| Function signatures | Tool descriptions |
| Type definitions | Parameter schemas |
| API documentation | Agent skills |
| Serialized responses | MCP prompt templates |
| — | Custom agent instructions |

These are your "code." They have no type system, no compiler, no static analysis. The only way to validate them is to let an LLM try to use them — which is exactly what pytest-skill-engineering does.

## Why Not Just Manual Testing?

You could test manually: open a chat, type a prompt, see if the LLM uses the right tool. But:

- **No regression detection** — You changed a description and broke three other tools. Manual testing won't catch that.
- **No comparison** — Is `gpt-5-mini` better than `gpt-4.1` for your tools? Manual testing can't tell you.
- **No CI/CD** — You can't gate deployments on "I chatted with it and it seemed fine."
- **No analysis** — You see what failed, but not *why* or *how to fix it*.

pytest-skill-engineering gives you automated, repeatable, analyzable tests for your AI interfaces — the same guarantees TDD gives you for code.

## The Feedback Loop

The key insight: **AI analysis closes the loop that traditional testing leaves open.**

```
Write test → Run → Fail → Fix interface → Pass → AI analysis → Improve further → ...
```

Traditional test frameworks stop at pass/fail. pytest-skill-engineering continues: the AI reads your results and produces specific, actionable suggestions for tool descriptions, skill engineering, and cost optimization. This is the refactoring step that makes TDD powerful — applied to AI interfaces.

## Getting Started

Write your first test: [Getting Started](../getting-started/index.md)

See AI analysis in action: [Sample Reports](ai-analysis.md#sample-reports)
