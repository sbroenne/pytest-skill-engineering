# How to Test MCP Servers

Test your Model Context Protocol (MCP) servers by running LLM agents against them.

## How It Works

pytest-aitest uses the [official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) to connect to MCP servers:

1. **Starts** the server as a subprocess via stdio transport
2. **Discovers tools** via MCP protocol
3. **Routes tool calls** from the LLM to the server
4. **Returns results** back to the LLM

## Defining a Server

Start an MCP server as a subprocess:

```python
import pytest
from pytest_aitest import MCPServer, Wait

@pytest.fixture(scope="module")
def weather_server():
    return MCPServer(
        command=["python", "-m", "my_weather_mcp"],
        wait=Wait.for_tools(["get_weather"]),
    )
```

### Configuration Options

```python
MCPServer(
    command=["python", "-m", "server"],  # Command to start server (required)
    args=["--debug"],                     # Additional arguments
    env={"API_KEY": "xxx"},               # Environment variables
    cwd="/path/to/server",                # Working directory
    wait=Wait.for_tools(["tool1"]),       # Wait condition
)
```

| Option | Description | Default |
|--------|-------------|---------|
| `command` | Command to start the MCP server | Required |
| `args` | Additional command-line arguments | `[]` |
| `env` | Environment variables (supports `${VAR}` expansion) | `{}` |
| `cwd` | Working directory | Current directory |
| `wait` | Wait condition for server startup | `Wait.ready()` |

### Wait Strategies

Control how pytest-aitest waits for the server to be ready.

**Wait.ready()** — Wait briefly for the process to start (default):

```python
wait=Wait.ready()
```

**Wait.for_tools()** — Wait until specific tools are available (recommended):

```python
wait=Wait.for_tools(["get_weather", "set_reminder"])
```

**Wait.for_log()** — Wait for a specific log pattern (regex):

```python
wait=Wait.for_log(r"Server started on port \d+")
```

All wait strategies accept a timeout:

```python
wait=Wait.for_tools(["tool1"], timeout_ms=60000)  # 60 seconds
```

### NPX-based Servers

```python
@pytest.fixture(scope="module")
def filesystem_server():
    return MCPServer(
        command=["npx", "-y", "@modelcontextprotocol/server-filesystem"],
        args=["/tmp/workspace"],
        wait=Wait.for_tools(["read_file", "write_file"]),
    )
```

### Environment Variables

```python
import os

@pytest.fixture(scope="module")
def api_server():
    return MCPServer(
        command=["python", "-m", "my_api_server"],
        env={
            "API_BASE_URL": "https://api.example.com",
            "API_KEY": os.environ["MY_API_KEY"],
        },
    )
```

## Complete Example

```python
import pytest
from pytest_aitest import Agent, MCPServer, Provider, Wait

@pytest.fixture(scope="module")
def weather_server():
    return MCPServer(
        command=["python", "-m", "my_weather_mcp"],
        wait=Wait.for_tools(["get_weather", "get_forecast"]),
    )

@pytest.fixture
def weather_agent(weather_server):
    return Agent(
        name="weather",
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[weather_server],
        system_prompt="You are a weather assistant.",
        max_turns=5,
    )

async def test_weather_query(aitest_run, weather_agent):
    result = await aitest_run(weather_agent, "What's the weather in Paris?")
    
    assert result.success
    assert result.tool_was_called("get_weather")
```

## Multiple Servers

Combine multiple MCP servers in a single agent:

```python
@pytest.fixture(scope="module")
def weather_server():
    return MCPServer(
        command=["python", "-m", "weather_mcp"],
        wait=Wait.for_tools(["get_weather"]),
    )

@pytest.fixture(scope="module")
def calendar_server():
    return MCPServer(
        command=["python", "-m", "calendar_mcp"],
        wait=Wait.for_tools(["create_event", "list_events"]),
    )

@pytest.fixture
def assistant_agent(weather_server, calendar_server):
    return Agent(
        name="assistant",
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[weather_server, calendar_server],
        system_prompt="You can check weather and manage calendar.",
        max_turns=10,
    )
```

## Filtering Tools

Use `allowed_tools` on the Agent to limit which tools are exposed to the LLM. This reduces token usage and focuses the agent.

```python
@pytest.fixture
def balance_agent(banking_server):
    # banking_server has 16 tools, but this test only needs 2
    return Agent(
        name="balance-checker",
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[banking_server],
        allowed_tools=["get_balance", "get_all_balances"],
        system_prompt="You check account balances.",
    )
```

## Troubleshooting

### Server Doesn't Start

Check that the command works standalone:

```bash
python -m my_server
```

### Tools Not Discovered

Use `Wait.for_tools()` and check server logs:

```python
MCPServer(
    command=["python", "-m", "server"],
    wait=Wait.for_tools(["expected_tool"]),
)
```

### Timeout During Startup

Increase the timeout:

```python
MCPServer(
    command=["python", "-m", "slow_server"],
    wait=Wait.for_tools(["tool"], timeout_ms=120000),  # 2 minutes
)
```
