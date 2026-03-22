---
description: "Understanding the CopilotEval test harness and when to use it for testing MCP servers, skills, and custom agents with GitHub Copilot."
---

# Test Harness

pytest-skill-engineering uses the **GitHub Copilot coding agent** as its test harness.

## CopilotEval — The Only Harness

`CopilotEval` runs the actual **GitHub Copilot coding agent** via the [github-copilot-sdk](https://github.com/github-copilot/sdk). This tests what your users experience when they use your MCP server, skill, or custom agent in GitHub Copilot.

```python
from pytest_skill_engineering.copilot import CopilotEval

async def test_skill_integration(copilot_eval):
    agent = CopilotEval(
        name="banking-test",
        skill_directories=["skills/banking-advisor"],
        max_turns=10,
    )
    result = await copilot_eval(agent, "What's my checking balance?")
    assert result.success
    assert result.tool_was_called("get_balance")
```

## Why Test with Real Copilot?

Traditional unit tests can't catch skill stack failures:

- **Tool discovery** — Can Copilot find the right tool?
- **Parameter inference** — Does it pass correct arguments?
- **Skill integration** — Does domain knowledge improve performance?
- **Subagent dispatch** — Do custom `.agent.md` files trigger correctly?
- **Multi-turn context** — Does conversation state persist?

CopilotEval validates all of this using the **exact same agent your users have**.

## Features

| Feature | CopilotEval |
|---------|-------------|
| **What runs** | Real GitHub Copilot coding agent (CLI SDK) |
| **Model** | Copilot's active model (or override with `model=`) |
| **Model setup** | None — `gh auth login` is all you need |
| **MCP auth** | Handled automatically by Copilot CLI |
| **Skill loading** | Native (`SKILL.md`, Agent Skills spec) |
| **Custom agents** | Native dispatch via `custom_agents=[]` |
| **Cost tracking** | Premium requests (Copilot billing) |
| **Speed** | ~5-10s CLI startup per test |
| **Install** | `uv add pytest-skill-engineering` |
| **Auth** | `gh auth login` (Copilot subscription required) |

## When to Use CopilotEval

**Always.** It's the only harness — designed to test the real user experience.

**Best for:**

- **End-to-end validation** — Test what actually ships to users
- **Zero setup** — No API keys, Azure deployments, or provider config
- **MCP OAuth** — Copilot CLI handles authentication automatically
- **Native skills** — Agent Skills loaded exactly as users experience them
- **Subagent testing** — Validate custom `.agent.md` agent selection
- **Regression testing** — Catch skill stack regressions before publishing

## Quick Start

```bash
# Install
uv add pytest-skill-engineering

# Authenticate (one-time)
gh auth login

# Write test
from pytest_skill_engineering.copilot import CopilotEval

async def test_balance(copilot_eval):
    agent = CopilotEval(skill_directories=["skills/banking"])
    result = await copilot_eval(agent, "What's my checking balance?")
    assert result.success
```

## Requirements

- Python 3.11+
- pytest 9.0+
- GitHub Copilot subscription (`gh auth login`)

## Next Steps

- [Test MCP Servers](../how-to/test-mcp-servers.md) — Test tool discovery and usage
- [Test Coding Agents](../how-to/test-coding-agents.md) — Full CopilotEval reference
- [Agent Skills](../getting-started/skills.md) — Add domain knowledge
- [Custom Agents](../getting-started/custom-agents.md) — Test `.agent.md` files
