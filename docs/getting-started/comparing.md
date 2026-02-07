# Comparing Configurations

The power of pytest-aitest is comparing different configurations to find what works best.

## Pattern 1: Explicit Configurations

Define agents with meaningful names when testing distinct approaches:

```python
from pytest_aitest import Agent, Provider, MCPServer, Skill

weather_server = MCPServer(command=["python", "weather_mcp.py"])

# Test different prompts with the same MCP server
agent_brief = Agent(
    name="brief-prompt",
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[weather_server],
    system_prompt="Be concise. One sentence max.",
)

agent_detailed = Agent(
    name="detailed-prompt",
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[weather_server],
    system_prompt="Be thorough. Explain your reasoning.",
)

agent_with_skill = Agent(
    name="with-skill",
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[weather_server],
    skill=Skill.from_path("skills/weather-expert"),
)

AGENTS = [agent_brief, agent_detailed, agent_with_skill]

@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name)
async def test_weather_query(aitest_run, agent):
    """Which configuration handles weather queries best?"""
    result = await aitest_run(agent, "What's the weather in Paris?")
    assert result.success
```

This runs 3 tests:

- `test_weather_query[brief-prompt]`
- `test_weather_query[detailed-prompt]`
- `test_weather_query[with-skill]`

**Use explicit configurations when:**

- Testing conceptually different approaches
- Names have meaning ("with-skill", "without-skill")
- You want full control over each configuration

## Pattern 2: Generated Configurations

Generate configurations from all permutations for systematic testing:

```python
MODELS = ["gpt-5-mini", "gpt-4.1"]
PROMPTS = {
    "brief": "Be concise.",
    "detailed": "Explain your reasoning step by step.",
}

weather_server = MCPServer(command=["python", "weather_mcp.py"])

# Generate all combinations
AGENTS = [
    Agent(
        name=f"{model}-{prompt_name}",
        provider=Provider(model=f"azure/{model}"),
        mcp_servers=[weather_server],
        system_prompt=prompt,
    )
    for model in MODELS
    for prompt_name, prompt in PROMPTS.items()
]

# 2 models × 2 prompts = 4 configurations
@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name)
async def test_weather_query(aitest_run, agent):
    """Test MCP server with different model/prompt combinations."""
    result = await aitest_run(agent, "What's the weather in Paris?")
    assert result.success
```

This runs 4 tests:

- `test_weather_query[gpt-5-mini-brief]`
- `test_weather_query[gpt-5-mini-detailed]`
- `test_weather_query[gpt-4.1-brief]`
- `test_weather_query[gpt-4.1-detailed]`

**Use generated configurations when:**

- You want to test all combinations systematically
- Looking for interactions (e.g., "this MCP server works with gpt-4.1 but fails with gpt-5-mini")
- Comparing multiple dimensions at once

## What the Report Shows

The report shows an **Agent Leaderboard** (auto-detected when multiple agents are tested):

| Agent | Pass Rate | Tokens | Cost |
|-------|-----------|--------|------|
| gpt-5-mini-brief | 100% | 747 | $0.002 |
| gpt-4.1-brief | 100% | 560 | $0.008 |
| gpt-5-mini-detailed | 100% | 1,203 | $0.004 |
| gpt-4.1-detailed | 100% | 892 | $0.012 |

**Winning agent:** Highest pass rate → lowest cost (tiebreaker).

This helps you answer:

- "Which configuration works best for my MCP server?"
- "Can I use a cheaper model with my tools?"
- "Does this prompt improve tool usage?"

## Next Steps

- [Multi-Turn Sessions](sessions.md) — Test conversations with context
- [A/B Testing Servers](ab-testing-servers.md) — Compare server implementations

> 📁 **Real Examples:**
> - [test_basic_usage.py](https://github.com/sbroenne/pytest-aitest/blob/main/tests/integration/test_basic_usage.py) — Single agent workflows
> - [test_dimension_detection.py](https://github.com/sbroenne/pytest-aitest/blob/main/tests/integration/test_dimension_detection.py) — Multi-dimension comparison
