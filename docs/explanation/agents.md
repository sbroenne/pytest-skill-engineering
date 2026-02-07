# Agents

The core concept in pytest-aitest.

## What is an Agent?

An **Agent** is a test configuration that bundles everything needed to run a test:

```
Agent = Model + System Prompt + Skill + Server(s)
```

```python
from pytest_aitest import Agent, Provider, MCPServer, Skill

weather_server = MCPServer(command=["python", "weather_mcp.py"])

agent = Agent(
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[weather_server],
    system_prompt="Be concise.",
    skill=Skill.from_path("skills/weather"),  # Optional
)
```

## The Agent is NOT What You Test

**You don't test agents. You USE agents to test:**

| Target | Question |
|--------|----------|
| **MCP Server** | Can the LLM understand and use my tools? |
| **System Prompt** | Do these instructions produce the behavior I want? |
| **Agent Skill** | Does this domain knowledge improve performance? |

The Agent is the **test harness** that bundles an LLM with the configuration you want to evaluate.

## Agent Components

| Component | Required | Example |
|-----------|----------|---------|
| Provider | ✓ | `Provider(model="azure/gpt-5-mini")` |
| MCP Servers | Optional | `MCPServer(command=["python", "server.py"])` |
| System Prompt | Optional | `"Be concise and direct."` |
| Skill | Optional | `Skill.from_path("skills/weather")` |

## Agent Leaderboard

**When you test multiple agents, the report shows an Agent Leaderboard.**

This happens automatically - no configuration needed. Just parametrize your tests:

```python
from pathlib import Path
import pytest
from pytest_aitest import Agent, Provider, MCPServer, load_system_prompts

weather_server = MCPServer(command=["python", "weather_mcp.py"])
PROMPTS = load_system_prompts(Path("prompts/"))

@pytest.mark.parametrize("prompt_name,system_prompt", PROMPTS.items())
async def test_weather(aitest_run, prompt_name, system_prompt):
    agent = Agent(
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[weather_server],
        system_prompt=system_prompt,
    )
    result = await aitest_run(agent, "What's the weather in Paris?")
    assert result.success
```

The report shows:

| Agent | Pass Rate | Cost |
|-------|-----------|------|
| gpt-5-mini (concise) | 100% | $0.002 |
| gpt-5-mini (detailed) | 100% | $0.004 |

## Winning Criteria

**Winning Agent = Highest pass rate → Lowest cost (tiebreaker)**

1. **Pass rate** (primary) — 100% beats 95%, always
2. **Cost** (tiebreaker) — Among equal pass rates, cheaper wins

## Dimension Detection

The AI analysis detects *what varies* between agents to provide targeted feedback:

| What Varies | AI Feedback Focuses On |
|-------------|------------------------|
| Model | Which model works best with your tools |
| System Prompt | Which instructions produce better behavior |
| Skill | Whether domain knowledge helps |
| Server | Which implementation is more reliable |

This is for **AI analysis only** - the leaderboard always appears when multiple agents are tested.

## Examples

### Compare Models

```python
MODELS = ["azure/gpt-5-mini", "azure/gpt-4.1"]
weather_server = MCPServer(command=["python", "weather_mcp.py"])

@pytest.mark.parametrize("model", MODELS)
async def test_with_model(aitest_run, model):
    agent = Agent(
        provider=Provider(model=model),
        mcp_servers=[weather_server],
    )
    result = await aitest_run(agent, "What's the weather in Paris?")
    assert result.success
```

### Compare System Prompts

```python
from pathlib import Path
from pytest_aitest import load_system_prompts

PROMPTS = load_system_prompts(Path("prompts/"))
weather_server = MCPServer(command=["python", "weather_mcp.py"])

@pytest.mark.parametrize("prompt_name,system_prompt", PROMPTS.items())
async def test_with_prompt(aitest_run, prompt_name, system_prompt):
    agent = Agent(
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[weather_server],
        system_prompt=system_prompt,
    )
    result = await aitest_run(agent, "What's the weather in Paris?")
    assert result.success
```

### Compare Multiple Dimensions

```python
MODELS = ["gpt-5-mini", "gpt-4.1"]
PROMPTS = load_system_prompts(Path("prompts/"))
weather_server = MCPServer(command=["python", "weather_mcp.py"])

@pytest.mark.parametrize("model", MODELS)
@pytest.mark.parametrize("prompt_name,system_prompt", PROMPTS.items())
async def test_combinations(aitest_run, model, prompt_name, system_prompt):
    agent = Agent(
        provider=Provider(model=f"azure/{model}"),
        mcp_servers=[weather_server],
        system_prompt=system_prompt,
    )
    result = await aitest_run(agent, "What's the weather in Paris?")
    assert result.success
```

## Next Steps

- [Comparing Configurations](../getting-started/comparing.md) — More comparison patterns
- [A/B Testing Servers](../getting-started/ab-testing-servers.md) — Test server versions
- [AI Analysis](ai-reports.md) — What the AI evaluation produces
