# LLM Interface Testing

[![PyPI version](https://img.shields.io/pypi/v/pytest-aitest)](https://pypi.org/project/pytest-aitest/)
[![Python versions](https://img.shields.io/pypi/pyversions/pytest-aitest)](https://pypi.org/project/pytest-aitest/)
[![CI](https://github.com/sbroenne/pytest-aitest/actions/workflows/ci.yml/badge.svg)](https://github.com/sbroenne/pytest-aitest/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

### Agent Contract Testing for MCP Servers and Tools

**Behavioural testing for LLM-operated systems.**

A pytest plugin for validating whether language models can actually understand and operate your interfaces: MCP servers, agents, prompts, and tools.

It tests the *LLM-facing contract* — not just the underlying code.

---

## What Problem This Solves

Traditional tests validate deterministic code paths.  
LLM-driven systems fail differently.

Your implementation can be correct, fully tested, and deployed — and still fail because the model:

- Chooses the wrong tool
- Supplies incorrect parameters
- Can't recover from errors
- Changes behaviour after a prompt or model update

These failures don't show up in unit tests, and manual testing doesn't scale.

**The root cause:**  
Your real API is no longer just functions and endpoints.  
It is the **LLM-facing interface** — descriptions, schemas, prompts, and error semantics.

---

## Core Idea

### Your test is the prompt.

Instead of scripting expected tool calls, you write what a user would say.

The model decides:
- Whether to act
- Which tool to use
- How to supply parameters
- How to respond

Your test asserts on the *observed behaviour*.

```python
@pytest.mark.asyncio
async def test_trip_planning(aitest_run, weather_agent_factory):
    """User asks for trip advice → LLM should compare forecasts."""
    agent = weather_agent_factory("gpt-5-mini", max_turns=10)

    # The test IS the prompt
    result = await aitest_run(
        agent,
        "I'm planning a trip and can't decide between Paris and Sydney. "
        "Get me a 3-day forecast for both and recommend which has better "
        "weather for sightseeing. I prefer sunny weather.",
    )

    assert result.success
    assert result.tool_call_count("get_forecast") >= 2  # Called for both cities
    assert "paris" in result.final_response.lower()
    assert "sydney" in result.final_response.lower()
```

No mocking. No forced tool calls.  
The model infers everything from the interface you expose.

---

## Features

### Test MCP Servers

Run real models against real interfaces:

- Tool discovery and selection
- Parameter inference
- Multi-step workflows
- Error handling and recovery

```python
@pytest.fixture(scope="module")
def weather_server():
    return MCPServer(
        command=[sys.executable, "-m", "my_weather_mcp"],
        wait=Wait.for_tools(["get_weather", "get_forecast"]),
    )
```

### Benchmark Models

Compare models using native pytest parametrize:

```python
@pytest.mark.parametrize("model", ["gpt-5-mini", "gpt-4.1"])
@pytest.mark.asyncio
async def test_tool_selection(aitest_run, weather_server, model):
    agent = Agent(
        provider=Provider(model=f"azure/{model}"),
        mcp_servers=[weather_server],
        system_prompt="You are a helpful weather assistant.",
        max_turns=5,
    )
    result = await aitest_run(agent, "What's the weather in Paris?")
    assert result.success
    assert result.tool_was_called("get_weather")
```

Reports show pass rate, token usage, and cost per model.

### Prompt Arena

Compare system prompts head-to-head:

```python
PROMPTS = load_prompts(Path("tests/integration/prompts/"))

@pytest.mark.parametrize("prompt", PROMPTS, ids=lambda p: p.name)
@pytest.mark.asyncio
async def test_prompt_effectiveness(aitest_run, weather_server, prompt):
    agent = Agent(
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[weather_server],
        system_prompt=prompt.system_prompt,
        max_turns=5,
    )
    result = await aitest_run(agent, "What's the weather in Paris?")
    assert result.success
```

### Matrix Testing

Test every model × prompt combination:

```python
@pytest.mark.parametrize("model", ["gpt-5-mini", "gpt-4.1"])
@pytest.mark.parametrize("prompt", PROMPTS, ids=lambda p: p.name)
@pytest.mark.asyncio
async def test_matrix(aitest_run, weather_server, model, prompt):
    # Full grid: surface brittle pairings
    ...
```

### AI Judge

Semantic assertions using LLM evaluation — validate response quality, not just tool usage:

```python
@pytest.mark.asyncio
async def test_recommendation_quality(aitest_run, weather_agent_factory, judge):
    agent = weather_agent_factory("gpt-5-mini", max_turns=10)

    result = await aitest_run(
        agent,
        "Compare weather in Paris and Sydney. Which is better for sightseeing?",
    )

    assert result.success
    assert judge(result.final_response, """
        - Mentions weather for both Paris and Sydney
        - Makes a recommendation for one city
        - Provides reasoning based on weather data
    """)
```

Uses [pytest-llm-assert](https://github.com/sbroenne/pytest-llm-assert) under the hood.

### CLI Server

Test command-line tools as if they were MCP servers:

```python
@pytest.fixture(scope="module")
def git_server():
    return CLIServer(
        name="git",
        command="git",
        tool_prefix="git",
    )
```

Help is discovered automatically — CLIServer runs `--help` at startup and includes the output in the tool description. Customize with `help_flag="-h"` for different CLIs, or provide a `description` directly for full control.

See [CLI Server Guide](docs/cli-server.md) for shell selection, help discovery, and assertions.

---

## Why pytest?

This is a **pytest plugin**, not a standalone tool.

- Use existing fixtures, markers, and parametrize
- Works with your CI/CD pipeline
- No new syntax to learn
- Combine with other pytest plugins

---

## What This Is Not

- A replacement for unit tests
- A mock-based simulator
- A guarantee of perfect model behaviour

This tool complements traditional testing by covering LLM behaviour, which conventional tests cannot observe.

---

## Who This Is For

- MCP server authors
- Agent and tool builders
- Teams exposing APIs to LLMs
- Anyone shipping systems where models operate tools autonomously

---

## Installation

```bash
pip install pytest-aitest
```

## Setup

Works out of the box with cloud identity:

```bash
# Azure (Entra ID)
export AZURE_API_BASE=https://your-resource.openai.azure.com/
az login

# OpenAI
export OPENAI_API_KEY=sk-...
```

Supports 100+ providers via [LiteLLM](https://docs.litellm.ai/docs/providers).

---

## Documentation

- **[Configuration](docs/configuration.md)** — Providers, agents, fixtures
- **[CLI Server](docs/cli-server.md)** — Test CLI tools with help discovery
- **[MCP Server](docs/mcp-server.md)** — MCP server configuration and wait strategies
- **[Assertions](docs/assertions.md)** — AgentResult API and AI judge patterns
- **[Reporting](docs/reporting.md)** — HTML reports and AI summaries
- **[API Reference](docs/api-reference.md)** — Full API documentation
- **[Design](docs/DESIGN.md)** — Architecture and design decisions

---

## Coming Soon

- **Multi-turn Conversations** — `continue_from()` for stateful sessions
- **Prompt Templates** — YAML-based prompt management

---

## Related

- **[pytest-llm-assert](https://github.com/sbroenne/pytest-llm-assert)** — Semantic assertions for pytest
- **[Contributing](CONTRIBUTING.md)** — Development setup and guidelines

## Requirements

- Python 3.11+
- pytest 9.0+
- An LLM provider (Azure, OpenAI, Anthropic, etc.)

## License

MIT
