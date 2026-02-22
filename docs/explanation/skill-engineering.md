---
description: "Skill engineering — designing modular, reliable, callable capabilities for LLMs. How to test and iterate your tool descriptions, schemas, agent skills, prompt templates, and custom agents."
---

# Skill Engineering

**Skill engineering** is the discipline of designing modular, reliable, callable capabilities that an LLM can discover, invoke, and orchestrate to perform real tasks. It's the shift from prompt engineering — crafting one-off text — to building a library of tools, skills, and agents that a model can use on demand.

## What Skill Engineering Covers

A "skill" in the SE sense is anything an LLM calls or invokes:

- **MCP Server Tools** — callable functions (`get_balance()`, `submit_order()`)
- **Prompt Templates** — server-side reasoning starters exposed via `prompts/list`
- **Agent Skills** — domain knowledge and behavioral guidelines the agent carries
- **Custom Agents** — specialist sub-agents the orchestrator routes tasks to
- **Prompt Files** — user-invoked slash commands (`/review`, `/explain`)

Together, these form the **skill engineering stack** — the full AI-facing package that determines whether an LLM can actually perform tasks.

## Why Skill Engineering Needs Testing

Skills are not code. They have no type system, no compiler, no linter. The only validator is an LLM trying to use them.

Traditional code has a fast feedback loop:

> Write a function → compiler catches type errors → linter catches style → unit tests catch bugs. Iterate quickly.

Skill engineering has **no feedback loop by default**. You write a tool description, deploy it, and discover it's broken when users complain the LLM picked the wrong tool. There's no compiler for "this description is confusing to an LLM." There's no linter for "this parameter name is ambiguous."

pytest-skill-engineering creates that missing feedback loop.

## The SE Testing Cycle

Skill engineering maps directly onto the Red/Green/Refactor cycle — with the target being your skills, not your code:

### 🔴 Red: Write a Failing Test

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

### 🟢 Green: Refine the Skill

Improve the thing the LLM actually sees — your tool description, schema, or skill instructions:

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

Run the test again. It passes. The LLM now picks the right skill with the right parameters.

### 🔵 Refactor: Let AI Analysis Guide You

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

## What You're Engineering

In traditional software, you design functions and classes. In skill engineering, you design the **skill stack** — the modular capabilities the LLM actually sees and orchestrates:

| Traditional Software | Skill Engineering |
|---------------------|------------------|
| Function signatures | Tool descriptions |
| Type definitions | Parameter schemas |
| API documentation | Agent skills |
| Serialized responses | MCP prompt templates |
| — | Custom agent instructions |

These have no type system, no compiler. The only way to validate them is to let an LLM try to use them.

## Why Not Just Manual Testing?

You could test manually: open a chat, type a prompt, see if the LLM uses the right tool. But:

- **No regression detection** — You changed a description and broke three other tools. Manual testing won't catch that.
- **No comparison** — Is `gpt-5-mini` better than `gpt-4.1` for your tools? Manual testing can't tell you.
- **No CI/CD** — You can't gate deployments on "I chatted with it and it seemed fine."
- **No A/B testing** — Which version of the skill is better? You can't know without running both.

pytest-skill-engineering gives you automated, repeatable, comparable tests for your skill stack — the same guarantees automated testing gives you for code.

## The Feedback Loop

**AI analysis closes the loop that traditional testing leaves open.**

```
Write test → 🔴 Red → Refine skill → 🟢 Green → AI analysis → 🔵 Refactor → ...
```

Traditional test frameworks stop at pass/fail. pytest-skill-engineering continues: the AI reads your results and produces specific, actionable suggestions for tool descriptions, skill structure, and cost optimization. This is the Refactor step that makes TDD powerful — applied to your skill engineering stack.

## Getting Started

Write your first test: [Getting Started](../getting-started/index.md)

See AI analysis in action: [Sample Reports](ai-analysis.md#sample-reports)
