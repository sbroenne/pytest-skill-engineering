---
description: "Write your first AI test in under 5 minutes. Set up pytest-skill-engineering to test MCP servers, tools, skills, and custom agents with the real GitHub Copilot coding agent."
---

# Getting Started

Write your first AI test in under 5 minutes using the **real GitHub Copilot coding agent**.

## What You're Testing

pytest-skill-engineering tests whether GitHub Copilot can understand and use your tools:

- **MCP Server Tools** — Can Copilot discover and call your tools correctly?
- **Agent Skills** — Does domain knowledge improve performance?
- **Custom Agents** — Do your `.agent.md` instructions produce the right behavior and trigger subagent dispatch?
- **MCP Server Prompts** — Do your bundled prompt templates render and produce the right behavior?
- **CLI Tools** — Can Copilot effectively use command-line interfaces?

## Installation

```bash
uv add pytest-skill-engineering
```

## Authentication

Authenticate with GitHub Copilot (one-time):

```bash
gh auth login
```

This gives pytest-skill-engineering access to the real GitHub Copilot coding agent.

## Your First Test

The simplest case: verify GitHub Copilot can use your MCP server correctly.

```python
from pytest_skill_engineering.copilot import CopilotEval

async def test_balance_query(copilot_eval):
    """Verify Copilot can use get_balance correctly."""
    agent = CopilotEval(
        skill_directories=["skills/banking-advisor"],  # Optional skill
        max_turns=10,
    )
    result = await copilot_eval(agent, "What's my checking account balance?")
    
    assert result.success
    assert result.tool_was_called("get_balance")
```

**What this tests:**

- **Tool discovery** — Did Copilot find `get_balance`?
- **Parameter inference** — Did it pass `account="checking"` correctly?
- **Response handling** — Did it interpret the tool output?
- **Skill integration** — Did the banking skill improve performance?

If this fails, your MCP server's tool descriptions, schemas, or skill content need work.

## The Workflow

This is **test-driven skill engineering** — iterate on your AI interface the same way you iterate on code:

1. **Write a test** — describe what a user would say
2. **Run it** — GitHub Copilot tries to use your tools
3. **Fix the interface** — improve tool descriptions, skills, or agent instructions until it passes
4. **Generate a report** — AI analysis tells you what else to optimize

Red/Green/Refactor for the skill stack.

## Running the Test

```bash
pytest tests/test_banking.py -v
```

## AI-Powered Reports

Configure reporting in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
addopts = """
--aitest-summary-model=copilot/gpt-5-mini
--aitest-html=aitest-reports/report.html
"""
```

Run pytest:

```bash
pytest tests/
```

The report includes:

- **Eval Leaderboard** — Which configurations work best (pass rate + cost)
- **AI Analysis** — Deployment recommendation, failure root causes, tool description improvements
- **Tool Feedback** — Specific suggestions with copy-to-clipboard buttons
- **Cost Tracking** — Premium requests and USD estimates

## Next Steps

- [Custom Agents](custom-agents.md) — Test `.agent.md` files and validate subagent dispatch
- [Agent Skills](skills.md) — Add domain knowledge (agentskills.io spec-compliant)
- [Plugin Testing](plugins.md) — Load complete plugin directories
- [Test Coding Agents](../how-to/test-coding-agents.md) — Full `CopilotEval` reference
