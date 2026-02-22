---
description: "Compare LLM models, agent skills, custom agent versions, and server configurations side-by-side. Find the most cost-effective setup with automated leaderboards."
---

# Comparing Configurations

The power of pytest-skill-engineering is comparing different configurations to find what works best — whether that's models, skill versions, or custom agent files.

## Pattern 1: Explicit Configurations

Define agents with meaningful names when testing distinct approaches:

```python
from pytest_skill_engineering import Agent, Provider, MCPServer, Skill, load_custom_agent

banking_server = MCPServer(command=["python", "banking_mcp.py"])

# Compare: no skill vs with skill
agent_baseline = Agent(
    name="baseline",
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[banking_server],
)

agent_with_skill = Agent(
    name="with-skill",
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[banking_server],
    skill=Skill.from_path("skills/financial-advisor"),
)

# Compare: two versions of a custom agent file
agent_v1 = Agent.from_agent_file(
    ".github/agents/advisor-v1.agent.md",
    name="advisor-v1",
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[banking_server],
)

agent_v2 = Agent.from_agent_file(
    ".github/agents/advisor-v2.agent.md",
    name="advisor-v2",
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[banking_server],
)

AGENTS = [agent_baseline, agent_with_skill, agent_v1, agent_v2]

@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name)
async def test_balance_query(aitest_run, agent):
    """Which configuration handles balance queries best?"""
    result = await aitest_run(agent, "What's my checking balance?")
    assert result.success
```

**Use explicit configurations when:**

- Testing conceptually different approaches (baseline vs skill, v1 vs v2)
- Names have meaning ("with-skill", "without-skill")
- You want full control over each configuration

## Pattern 2: Generated Configurations

Generate configurations from all permutations for systematic testing:

```python
from pathlib import Path
from pytest_skill_engineering import Agent, Provider, MCPServer, Skill

MODELS = ["gpt-5-mini", "gpt-4.1"]
SKILL_VERSIONS = {
    path.stem: Skill.from_path(path)
    for path in Path("skills").iterdir() if path.is_dir()
}

banking_server = MCPServer(command=["python", "banking_mcp.py"])

# Generate all combinations: 2 models × N skill versions
AGENTS = [
    Agent(
        name=f"{model}-{skill_name}",
        provider=Provider(model=f"azure/{model}"),
        mcp_servers=[banking_server],
        skill=skill,
    )
    for model in MODELS
    for skill_name, skill in SKILL_VERSIONS.items()
]

@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name)
async def test_balance_query(aitest_run, agent):
    """Test MCP server with different model/skill combinations."""
    result = await aitest_run(agent, "What's my checking balance?")
    assert result.success
```

**Use generated configurations when:**

- Testing all combinations systematically
- Looking for interactions (e.g., "skill v2 works with gpt-4.1 but fails with gpt-5-mini")
- Comparing multiple dimensions at once

## What the Report Shows

The report shows an **Agent Leaderboard** (auto-detected when multiple agents are tested):

| Agent | Pass Rate | Tokens | Cost |
|-------|-----------|--------|------|
| gpt-5-mini-v2 | 100% | 747 | $0.002 |
| gpt-4.1-v2 | 100% | 560 | $0.008 |
| gpt-5-mini-v1 | 90% | 1,203 | $0.004 |
| gpt-4.1-v1 | 90% | 892 | $0.012 |

**Winning agent:** Highest pass rate → lowest cost (tiebreaker).

This helps you answer:

- "Does skill v2 outperform v1?"
- "Can I use a cheaper model with my tools?"
- "Which custom agent instructions produce better behavior?"

## Next Steps

- [Custom Agents](custom-agents.md) — A/B test agent instruction files
- [A/B Testing Servers](ab-testing-servers.md) — Compare server implementations
- [Multi-Turn Sessions](sessions.md) — Test conversations with context

> 📁 **Real Examples:**
> - [test_basic_usage.py](https://github.com/sbroenne/pytest-skill-engineering/blob/main/tests/integration/test_basic_usage.py) — Single agent workflows
> - [test_dimension_detection.py](https://github.com/sbroenne/pytest-skill-engineering/blob/main/tests/integration/test_dimension_detection.py) — Multi-dimension comparison
