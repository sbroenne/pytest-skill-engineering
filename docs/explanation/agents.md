---
description: "Understand Agents in pytest-skill-engineering: an Agent combines an LLM provider, MCP servers, skills, and custom agents into a test harness."
---

# Agents

The core concept in pytest-skill-engineering.

## What is an Agent?

An **Agent** is a test configuration that bundles everything needed to run a test:

```
Agent = Model + Skill + Custom Agents + Server(s)
```

```python
from pytest_skill_engineering import Agent, Provider, MCPServer, Skill, load_custom_agent

banking_server = MCPServer(command=["python", "banking_mcp.py"])

agent = Agent(
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[banking_server],
    skill=Skill.from_path("skills/financial-advisor"),        # Optional
    custom_agents=[load_custom_agent("agents/advisor.agent.md")],  # Optional
)
```

## The Agent is NOT What You Test

**You don't test agents. You USE agents to test:**

| Target | Question |
|--------|----------|
| **MCP Server** | Can the LLM understand and use my tools? |
| **Agent Skill** | Does this domain knowledge improve performance? |
| **Custom Agent** | Do these `.agent.md` instructions produce the right behavior? |

The Agent is the **test harness** that bundles an LLM with the configuration you want to evaluate.

## Agent Components

| Component | Required | Example |
|-----------|----------|---------|
| Provider | ✓ | `Provider(model="azure/gpt-5-mini")` |
| MCP Servers | Optional | `MCPServer(command=["python", "server.py"])` |
| Skill | Optional | `Skill.from_path("skills/financial-advisor")` |
| Custom Agent File | Optional | `Agent.from_agent_file("agents/reviewer.agent.md", provider=...)` |

## Agent Leaderboard

**When you test multiple agents, the report shows an Agent Leaderboard.**

This happens automatically — no configuration needed. Just parametrize your tests:

```python
from pathlib import Path
import pytest
from pytest_skill_engineering import Agent, Provider, MCPServer, Skill

banking_server = MCPServer(command=["python", "banking_mcp.py"])

SKILLS = {
    "v1": Skill.from_path("skills/financial-advisor-v1"),
    "v2": Skill.from_path("skills/financial-advisor-v2"),
}

@pytest.mark.parametrize("skill_name,skill", SKILLS.items())
async def test_banking(aitest_run, skill_name, skill):
    agent = Agent(
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[banking_server],
        skill=skill,
    )
    result = await aitest_run(agent, "What's my checking balance?")
    assert result.success
```

The report shows:

| Agent | Pass Rate | Cost |
|-------|-----------|------|
| gpt-5-mini (v1) | 100% | $0.002 |
| gpt-5-mini (v2) | 100% | $0.004 |

## Winning Criteria

**Winning Agent = Highest pass rate → Lowest cost (tiebreaker)**

1. **Pass rate** (primary) — 100% beats 95%, always
2. **Cost** (tiebreaker) — Among equal pass rates, cheaper wins

## Dimension Detection

The AI analysis detects *what varies* between agents to provide targeted feedback:

| What Varies | AI Feedback Focuses On |
|-------------|------------------------|
| Model | Which model works best with your tools |
| Skill | Whether domain knowledge helps |
| Custom Agent | Which agent instructions produce better behavior |
| Server | Which implementation is more reliable |

This is for **AI analysis only** - the leaderboard always appears when multiple agents are tested.

## Examples

### Compare Models

```python
MODELS = ["azure/gpt-5-mini", "azure/gpt-4.1"]
banking_server = MCPServer(command=["python", "banking_mcp.py"])

@pytest.mark.parametrize("model", MODELS)
async def test_with_model(aitest_run, model):
    agent = Agent(
        provider=Provider(model=model),
        mcp_servers=[banking_server],
    )
    result = await aitest_run(agent, "What's my checking balance?")
    assert result.success
```

### Compare Custom Agent Versions

A/B test two versions of a `.agent.md` file to find which instructions work better:

```python
from pathlib import Path
from pytest_skill_engineering import Agent, Provider

AGENT_VERSIONS = {
    path.stem: path
    for path in Path(".github/agents").glob("reviewer-*.agent.md")
}

@pytest.mark.parametrize("name,path", AGENT_VERSIONS.items())
async def test_reviewer(aitest_run, name, path):
    agent = Agent.from_agent_file(
        path,
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[code_server],
    )
    result = await aitest_run(agent, "Review src/auth.py for security issues")
    assert result.success
```

### Compare Multiple Dimensions

```python
MODELS = ["gpt-5-mini", "gpt-4.1"]
SKILLS = {
    "v1": Skill.from_path("skills/advisor-v1"),
    "v2": Skill.from_path("skills/advisor-v2"),
}

@pytest.mark.parametrize("model", MODELS)
@pytest.mark.parametrize("skill_name,skill", SKILLS.items())
async def test_combinations(aitest_run, model, skill_name, skill):
    agent = Agent(
        provider=Provider(model=f"azure/{model}"),
        mcp_servers=[banking_server],
        skill=skill,
    )
    result = await aitest_run(agent, "What's my checking balance?")
    assert result.success
```

## Custom Agents

A **custom agent** is a specialized sub-agent defined in a `.agent.md` or `.md` file with YAML frontmatter (`name`, `description`, `tools`) and a markdown prompt body.

```python
from pytest_skill_engineering import Agent, Provider

# Load and test a custom agent's instructions synthetically
agent = Agent.from_agent_file(
    ".github/agents/reviewer.agent.md",
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[code_server],
)
```

The `tools` frontmatter field maps to `allowed_tools` — restricting which tools the agent can call. See [Custom Agents](../getting-started/custom-agents.md) for a full guide.

## Next Steps

- [Choosing a Test Harness](choosing-a-harness.md) — `Agent` vs `CopilotAgent`: full trade-off guide
- [Comparing Configurations](../getting-started/comparing.md) — More comparison patterns
- [A/B Testing Servers](../getting-started/ab-testing-servers.md) — Test server versions
- [AI Analysis](ai-analysis.md) — What the AI evaluation produces
