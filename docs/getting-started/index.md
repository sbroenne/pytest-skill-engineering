# Getting Started

Write your first AI test in under 5 minutes.

## What You're Testing

pytest-aitest tests whether an LLM can understand and use your tools:

- **MCP Servers** — Can the LLM discover and call your tools correctly?
- **System Prompts** — Do your instructions produce the behavior you want?
- **Agent Skills** — Does domain knowledge help the agent perform?

## The Agent

An **Agent** is the test harness that bundles your configuration:

```python
from pytest_aitest import Agent, Provider, MCPServer

Agent(
    provider=Provider(model="azure/gpt-5-mini"),   # LLM provider (required)
    mcp_servers=[weather_server],                   # MCP servers with tools
    system_prompt="Be concise.",                    # Agent behavior (optional)
    skill=weather_skill,                            # Agent Skill (optional)
)
```

## Your First Test

The simplest case: verify an LLM can use your MCP server correctly.

```python
import pytest
from pytest_aitest import Agent, Provider, MCPServer

# The MCP server you're testing
weather_server = MCPServer(command=["python", "weather_mcp.py"])

agent = Agent(
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[weather_server],
)

async def test_weather_query(aitest_run):
    """Verify the LLM can use get_weather correctly."""
    result = await aitest_run(agent, "What's the weather in Paris?")
    
    assert result.success
    assert result.tool_was_called("get_weather")
```

**What this tests:**

- **Tool discovery** — Did the LLM find `get_weather`?
- **Parameter inference** — Did it pass `location="Paris"` correctly?
- **Response handling** — Did it interpret the tool output?

If this fails, your MCP server's tool descriptions or schemas need work.

## Running the Test

```bash
pytest tests/test_weather.py -v
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

- [System Prompts](system-prompts.md) — Control agent behavior
- [Agent Skills](skills.md) — Add domain knowledge
- [Comparing Configurations](comparing.md) — Find what works best
- [A/B Testing Servers](ab-testing-servers.md) — Compare MCP server versions
