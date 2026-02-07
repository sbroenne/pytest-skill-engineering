# pytest-aitest

[![PyPI version](https://img.shields.io/pypi/v/pytest-aitest)](https://pypi.org/project/pytest-aitest/)
[![Python versions](https://img.shields.io/pypi/pyversions/pytest-aitest)](https://pypi.org/project/pytest-aitest/)
[![CI](https://github.com/sbroenne/pytest-aitest/actions/workflows/ci.yml/badge.svg)](https://github.com/sbroenne/pytest-aitest/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Test your AI interfaces. AI analyzes your results.**

A pytest plugin for validating whether language models can understand and operate your MCP servers, tools, prompts, and skills.

## Why?

Your MCP server passes all unit tests. Then an LLM tries to use it and picks the wrong tool, passes garbage parameters, or ignores your system prompt.

**Because you tested the code, not the AI interface.** For LLMs, your API is tool descriptions, schemas, and prompts — not functions and types. Traditional tests can't validate them.

## How It Works

Write tests as natural language prompts. An **Agent** bundles an LLM with your tools — you assert on what happened:

```python
from pytest_aitest import Agent, Provider, MCPServer

async def test_weather_query(aitest_run):
    agent = Agent(
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[MCPServer(command=["python", "-m", "my_weather_server"])],
    )

    result = await aitest_run(agent, "What's the weather in Paris?")

    assert result.success
    assert result.tool_was_called("get_weather")
```

If the test fails, your tool descriptions need work — not your code.

## AI-Powered Reports

AI analyzes your results and tells you **what to fix**: which model to deploy, how to improve tool descriptions, where to cut costs. [See a sample report →](https://sbroenne.github.io/pytest-aitest/reports/05_hero.html)

> **Deploy: gpt-5-mini** — Highest pass rate at ~4–6x lower cost than gpt-4.1. gpt-4.1 disqualified due to failed core transfer test and session-planning failure.

## Quick Start

Install:

```bash
uv add pytest-aitest
```

Configure in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
addopts = """
--aitest-summary-model=azure/gpt-5.2-chat
"""
```

Set credentials and run:

```bash
export AZURE_API_BASE=https://your-resource.openai.azure.com/
az login
pytest tests/
```

## Features

- **MCP Server Testing** — Real models against real tool interfaces
- **CLI Server Testing** — Wrap CLIs as testable tool servers
- **Agent Comparison** — Compare models, prompts, skills, and server versions
- **Agent Leaderboard** — Auto-ranked by pass rate and cost
- **Multi-Turn Sessions** — Test conversations that build on context
- **AI Analysis** — Actionable feedback on tool descriptions, prompts, and costs
- **100+ LLM Providers** — Any model via [LiteLLM](https://docs.litellm.ai/docs/providers) (Azure, OpenAI, Anthropic, Google, and more)
- **Semantic Assertions** — AI judge via [pytest-llm-assert](https://github.com/sbroenne/pytest-llm-assert)

## Documentation

📚 **[Full Documentation](https://sbroenne.github.io/pytest-aitest/)**

## Requirements

- Python 3.11+
- pytest 9.0+
- An LLM provider (Azure, OpenAI, Anthropic, etc.)

## Acknowledgments

Inspired by [agent-benchmark](https://github.com/mykhaliev/agent-benchmark).

## License

MIT
