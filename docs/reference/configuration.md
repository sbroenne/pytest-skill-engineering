# Configuration

## Quick Setup (pyproject.toml)

The recommended way to configure pytest-aitest is via `pyproject.toml`:

```toml
[tool.pytest.ini_options]
addopts = """
--aitest-summary-model=azure/gpt-5.2-chat
--aitest-html=aitest-reports/report.html
"""
```

With this configuration, just run:

```bash
pytest tests/
```

Reports are generated automatically with AI insights.

## LLM Provider Setup

pytest-aitest uses [LiteLLM](https://docs.litellm.ai/) for LLM access. Configure via environment variables.

### Azure OpenAI (Recommended)

```bash
export AZURE_API_BASE=https://your-resource.openai.azure.com/
az login
```

### OpenAI

```bash
export OPENAI_API_KEY=sk-xxx
```

### Other Providers

See [LiteLLM provider docs](https://docs.litellm.ai/docs/providers) for Anthropic, Google, etc.

| Provider | Variable |
|----------|----------|
| Azure OpenAI | `AZURE_API_BASE` + `az login` |
| OpenAI | `OPENAI_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| Google | `GEMINI_API_KEY` |

## Provider Configuration

```python
from pytest_aitest import Provider

# Basic - LiteLLM handles auth via env vars
provider = Provider(model="azure/gpt-5-mini")

# With generation parameters
provider = Provider(
    model="openai/gpt-4o-mini",
    temperature=0.7,
    max_tokens=1000,
)

# With rate limits (model-specific)
provider = Provider(
    model="azure/gpt-5-mini",
    rpm=10,    # Requests per minute
    tpm=10000, # Tokens per minute
)
```

## Agent Configuration

```python
from pytest_aitest import Agent, Provider, MCPServer

agent = Agent(
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[server],               # MCP servers
    cli_servers=[cli],                  # CLI servers (optional)
    system_prompt="You are...",         # System prompt (optional)
    skill=my_skill,                     # Agent Skill (optional)
    max_turns=10,                       # Max tool-call rounds
    name="my-agent",                    # Identifier for reports (optional)
    allowed_tools=["tool1", "tool2"],   # Filter tools (optional, reduces tokens)
)
```

## MCP Server Configuration

```python
from pytest_aitest import MCPServer, Wait

server = MCPServer(
    command=["python", "-m", "my_server"],
    args=["--debug"],
    env={"API_KEY": "xxx"},
    cwd="/path/to/server",
    wait=Wait.for_tools(["tool1", "tool2"]),
)
```

See [Test MCP Servers](../how-to/test-mcp-servers.md) for complete options.

## CLI Server Configuration

```python
from pytest_aitest import CLIServer

cli = CLIServer(
    name="git-cli",
    command="git",
    tool_prefix="git",
    shell="bash",
    cwd="/path/to/repo",
)
```

See [Test CLI Tools](../how-to/test-cli-tools.md) for complete options.

## Fixtures

### aitest_run

The main fixture for running tests:

```python
async def test_weather(aitest_run):
    agent = Agent(
        name="weather",
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[weather_server],
    )
    
    result = await aitest_run(agent, "What's the weather?")
    assert result.success
```

## CLI Override

You can override pyproject.toml settings via CLI:

```bash
# Use a different model for this run
pytest tests/ --aitest-summary-model=azure/gpt-5.2-chat

# Different output path
pytest tests/ --aitest-html=custom-report.html
```
