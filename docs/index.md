---
title: "Test your AI interfaces. AI analyzes your results."
description: "A pytest plugin for testing MCP servers, tools, system prompts, and agent skills with real LLMs. AI analyzes results and tells you what to fix."
icon: material/flask-outline
---

# Test your AI interfaces. AI analyzes your results.

A pytest plugin for validating whether language models can understand and operate your MCP servers, tools, prompts, and skills. AI analyzes your test results and tells you *what to fix*, not just *what failed*.

## The Problem

Your MCP server passes all unit tests. Then an LLM tries to use it and:

- Picks the wrong tool
- Passes garbage parameters
- Can't recover from errors
- Ignores your system prompt instructions

**Why?** Because you tested the code, not the AI interface.

For LLMs, your API isn't functions and types — it's **tool descriptions, system prompts, skills, and schemas**. These are what the LLM actually sees. Traditional tests can't validate them.

## The Solution

Write tests as natural language prompts. An **Agent** is your test harness — it combines an LLM provider, MCP servers, and optional configuration:

```python
async def test_balance_and_transfer(aitest_run, banking_server):
    agent = Agent(
        provider=Provider(model="azure/gpt-5-mini"),   # LLM provider
        mcp_servers=[banking_server],                  # MCP servers with tools
        system_prompt="Be concise.",                   # System Prompt (optional)
        skill=financial_skill,                         # Agent Skill (optional)
    )

    result = await aitest_run(
        agent,
        "Transfer $200 from checking to savings and show me the new balances.",
    )

    assert result.success
    assert result.tool_was_called("transfer")
```

The agent runs your prompt, calls tools, and returns results. You assert on what happened. If the test fails, your tool descriptions need work — not your code.

This is **test-driven development for AI interfaces**: write a test, watch it fail, fix your tool descriptions until it passes, then let AI analysis tell you what else to improve. See [TDD for AI Interfaces](explanation/tdd-for-ai.md) for the full concept.

**What you're testing:**

| Component | Question It Answers |
|-----------|---------------------|
| MCP Server | Can an LLM understand and use my tools? |
| System Prompt | Does this behavior definition produce the results I want? |
| Agent Skill | Does this domain knowledge help the agent perform? |

## What Makes This Different?

AI analyzes your test results and tells you **what to fix**, not just what failed. It generates [interactive HTML reports](explanation/ai-analysis.md#sample-reports) with agent leaderboards, comparison tables, and sequence diagrams.

![AI Analysis — winner recommendation, metrics, and comparative analysis](assets/images/ai_analysis.png)

[See a full sample report →](demo/hero-report.html){ .md-button }

    **Suggested improvement for `get_all_balances`:**

    > Return balances for all accounts belonging to the current user in a single call. Use instead of calling `get_balance` separately for each account.

    **💡 Optimizations**

    **Cost reduction opportunity:** Strengthen `get_all_balances` description to encourage single-call logic instead of multiple `get_balance` calls. **Estimated impact: ~15–25% cost reduction** on multi-account queries.




## Quick Start

```python
from pytest_aitest import Agent, Provider, MCPServer

banking_server = MCPServer(command=["python", "banking_mcp.py"])

async def test_balance_check(aitest_run):
    agent = Agent(
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[banking_server],
    )
    
    result = await aitest_run(agent, "What's my checking account balance?")
    
    assert result.success
    assert result.tool_was_called("get_balance")
```

> 📁 See [test_basic_usage.py](https://github.com/sbroenne/pytest-aitest/blob/main/tests/integration/test_basic_usage.py) for complete examples.

## Features

- **Test MCP Servers** — Verify LLMs can discover and use your tools
- **A/B Test Servers** — Compare MCP server versions or implementations
- **Test CLI Tools** — Wrap command-line interfaces as testable servers
- **Compare Models** — Benchmark different LLMs against your tools
- **Compare System Prompts** — Find the system prompt that works best
- **Multi-Turn Sessions** — Test conversations that build on context
- **Agent Skills** — Add domain knowledge following [agentskills.io](https://agentskills.io)
- **AI Analysis** — Tells you what to fix, not just what failed
- **Image Assertions** — AI-graded visual evaluation of screenshots and visual tool output

## Installation

```bash
uv add pytest-aitest
```

## Who This Is For

- **MCP server authors** — Validate tool descriptions work
- **Agent builders** — Compare models and prompts
- **Teams shipping AI systems** — Catch LLM-facing regressions

## Why pytest?

This is a **pytest plugin**, not a standalone tool. Use existing fixtures, markers, parametrize. Works with CI/CD pipelines. No new syntax to learn.

## Documentation

- [Getting Started](getting-started/index.md) — Write your first test
- [How-To Guides](how-to/index.md) — Solve specific problems
- [Reference](reference/index.md) — API and configuration details
- [Explanation](explanation/index.md) — Understand the design

## License

MIT
