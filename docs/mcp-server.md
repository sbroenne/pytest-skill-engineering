# MCP Server

Connect to Model Context Protocol (MCP) servers for testing tool-using agents.

## Quick Start

```python
from pytest_aitest import MCPServer

@pytest.fixture(scope="module")
def weather_server():
    return MCPServer(
        command=["python", "-m", "my_weather_mcp"],
    )
```

## How It Works

MCP servers expose tools via the Model Context Protocol. pytest-aitest:

1. **Starts the server** as a subprocess
2. **Discovers tools** via MCP protocol
3. **Routes tool calls** from the LLM to the server
4. **Returns results** back to the LLM

## Configuration Options

```python
MCPServer(
    command=["python", "-m", "server"],  # Command to start server (required)
    args=["--debug"],                     # Additional arguments (optional)
    env={"API_KEY": "xxx"},               # Environment variables (optional)
    cwd="/path/to/server",                # Working directory (optional)
    wait=Wait.for_tools(["tool1"]),       # Wait condition (optional)
)
```

| Option | Description | Default |
|--------|-------------|---------|
| `command` | Command to start the MCP server | Required |
| `args` | Additional command-line arguments | `[]` |
| `env` | Environment variables | `{}` |
| `cwd` | Working directory | Current directory |
| `wait` | Wait condition for server startup | `Wait.ready()` |

## Wait Strategies

Control how pytest-aitest waits for the server to be ready.

### Wait.ready()

Wait briefly for the process to start (default):

```python
MCPServer(
    command=["python", "-m", "server"],
    wait=Wait.ready(),  # Default: quick startup
)
```

### Wait.for_tools()

Wait until specific tools are available:

```python
MCPServer(
    command=["python", "-m", "server"],
    wait=Wait.for_tools(["get_weather", "set_reminder"]),
)
```

This is the recommended approach for reliable tests.

### Wait.for_log()

Wait for a specific log pattern (regex):

```python
MCPServer(
    command=["python", "-m", "server"],
    wait=Wait.for_log(r"Server started on port \d+"),
)
```

### Custom Timeout

All wait strategies accept a timeout:

```python
MCPServer(
    command=["python", "-m", "server"],
    wait=Wait.for_tools(["tool1"], timeout_ms=60000),  # 60 seconds
)
```

## Complete Examples

### Basic Weather Server

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
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[weather_server],
        system_prompt="You are a weather assistant.",
        max_turns=5,
    )

@pytest.mark.asyncio
async def test_weather_query(aitest_run, weather_agent):
    result = await aitest_run(weather_agent, "What's the weather in Paris?")
    
    assert result.success
    assert result.tool_was_called("get_weather")
```

### NPX-based Server

```python
@pytest.fixture(scope="module")
def filesystem_server():
    return MCPServer(
        command=["npx", "-y", "@modelcontextprotocol/server-filesystem"],
        args=["/tmp/workspace"],
        wait=Wait.for_tools(["read_file", "write_file", "list_directory"]),
    )
```

### Server with Environment Variables

```python
@pytest.fixture(scope="module")
def api_server():
    return MCPServer(
        command=["python", "-m", "my_api_server"],
        env={
            "API_BASE_URL": "https://api.example.com",
            "API_KEY": os.environ["MY_API_KEY"],
        },
        wait=Wait.for_tools(["query_api"]),
    )
```

### Multiple Servers

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
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[weather_server, calendar_server],
        system_prompt="You can check weather and manage calendar.",
        max_turns=10,
    )
```

## Writing an MCP Server for Testing

A minimal MCP server for testing:

```python
# my_test_server.py
import json
import sys

def main():
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        
        request = json.loads(line)
        method = request.get("method")
        
        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": request["id"],
                "result": {"protocolVersion": "2024-11-05"}
            }
        elif method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": request["id"],
                "result": {
                    "tools": [{
                        "name": "my_tool",
                        "description": "Does something useful",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"arg": {"type": "string"}},
                        }
                    }]
                }
            }
        elif method == "tools/call":
            response = {
                "jsonrpc": "2.0",
                "id": request["id"],
                "result": {"content": [{"type": "text", "text": "Result"}]}
            }
        else:
            continue
            
        print(json.dumps(response), flush=True)

if __name__ == "__main__":
    main()
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

### Environment Variables Not Set

Pass them explicitly:

```python
MCPServer(
    command=["python", "-m", "server"],
    env={
        "PATH": os.environ["PATH"],
        "HOME": os.environ["HOME"],
        "MY_VAR": "value",
    },
)
```
