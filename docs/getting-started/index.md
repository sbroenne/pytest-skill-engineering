---
description: "Write your first AI test in under 5 minutes. Set up pytest-skill-engineering to test MCP servers, tools, agent skills, and custom agents with real LLMs."
---

# Getting Started

Write your first AI test in under 5 minutes.

> **New here?** pytest-skill-engineering has two harnesses — `Agent + aitest_run` (for MCP servers and tool testing) and `CopilotAgent + copilot_run` (for GitHub Copilot skills). Read [Choosing a Test Harness](../explanation/choosing-a-harness.md) first if you're unsure which to use.

## What You're Testing

pytest-skill-engineering tests whether an LLM can understand and use your tools:

- **MCP Server Tools** — Can the LLM discover and call your tools correctly?
- **MCP Server Prompts** — Do your bundled prompt templates render and produce the right behavior?
- **Prompt Files** — Does invoking a slash command (`.prompt.md` / `.claude/commands/`) produce the right agent behavior?
- **Agent Skills** — Does domain knowledge help the agent perform?
- **Custom Agents** — Do your `.agent.md` instructions produce the right behavior?

## The Agent

An **Agent** is the test harness that bundles your configuration:

```python
from pytest_skill_engineering import Agent, Provider, MCPServer

Agent(
    provider=Provider(model="azure/gpt-5-mini"),   # LLM provider (required)
    mcp_servers=[banking_server],                   # MCP servers with tools
    skill=financial_skill,                          # Agent Skill (optional)
)
```

## Your First Test

The simplest case: verify an LLM can use your MCP server correctly.

```python
import pytest
from pytest_skill_engineering import Agent, Provider, MCPServer

# The MCP server you're testing
banking_server = MCPServer(command=["python", "banking_mcp.py"])

agent = Agent(
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[banking_server],
)

async def test_balance_query(aitest_run):
    """Verify the LLM can use get_balance correctly."""
    result = await aitest_run(agent, "What's my checking account balance?")
    
    assert result.success
    assert result.tool_was_called("get_balance")
```

**What this tests:**

- **Tool discovery** — Did the LLM find `get_balance`?
- **Parameter inference** — Did it pass `account="checking"` correctly?
- **Response handling** — Did it interpret the tool output?

If this fails, your MCP server's tool descriptions or schemas need work.

## The Workflow

This is **skill engineering** — iterate on what you're testing the same way you iterate on code:

1. **Write a test** — describe what a user would say
2. **Run it** — the LLM tries to use your tools
3. **Fix the interface** — improve descriptions, schemas, or prompts until it passes
4. **Generate a report** — AI analysis tells you what else to optimize

You iterate on your skills the same way you iterate on code. See [Skill Engineering](../explanation/skill-engineering.md) for the full concept.

## Running the Test

```bash
pytest tests/test_banking.py -v
```

## Generating Reports

First, configure reporting in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
addopts = """
--aitest-summary-model=azure/gpt-5.2-chat
--aitest-html=aitest-reports/report.html
"""
```

Then just run pytest:

```bash
pytest tests/
```

AI analysis is included automatically. See [Configuration](../reference/configuration.md) for details.

The report shows:

- **Configuration Leaderboard** — Which setups work best
- **Failure Analysis** — Root cause + suggested fix for each failure
- **Tool Feedback** — How to improve your tool descriptions

## Next Steps

- [Custom Agents](custom-agents.md) — Test `.agent.md` files and A/B test agent instructions
- [Agent Skills](skills.md) — Add domain knowledge
- [Comparing Configurations](comparing.md) — Find what works best
- [A/B Testing Servers](ab-testing-servers.md) — Compare MCP server versions
