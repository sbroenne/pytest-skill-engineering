# Architecture

How pytest-aitest executes tests and dispatches tools.

## Overview

```
┌─────────────────────────────────────────────────────────┐
│                     pytest-aitest                        │
├─────────────────────────────────────────────────────────┤
│  Test: "What's the weather in Paris?"                   │
│                         │                                │
│                         ▼                                │
│  ┌─────────────────────────────────────────────────┐    │
│  │              AgentEngine                         │    │
│  │  ┌─────────┐    ┌─────────┐    ┌─────────────┐  │    │
│  │  │ LiteLLM │◄──►│  Tool   │◄──►│ MCP/CLI     │  │    │
│  │  │ (LLM)   │    │Dispatch │    │ Servers     │  │    │
│  │  └─────────┘    └─────────┘    └─────────────┘  │    │
│  └─────────────────────────────────────────────────┘    │
│                         │                                │
│                         ▼                                │
│  AgentResult { turns, tool_calls, final_response }      │
└─────────────────────────────────────────────────────────┘
```

## The Agent Execution Loop

When you call `await aitest_run(agent, "prompt")`, here's what happens:

### 1. Server Startup

All MCP and CLI servers defined in the agent are started as subprocesses:

```python
agent = Agent(
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[weather_server, calendar_server],  # Started
    cli_servers=[git_cli],                           # Started
)
```

Servers remain running for the duration of the test session.

### 2. Tool Discovery

The engine queries each server for its available tools:

- **MCP servers**: Uses the MCP protocol's `tools/list` method
- **CLI servers**: Reads the tool definitions from the server wrapper

Tools are converted to a unified format that LiteLLM understands.

### 3. LLM Loop

The engine enters a turn-based loop:

```
Turn 1: Send prompt + tool definitions to LLM
        LLM responds: "I'll check the weather" + tool_call(get_weather, city="Paris")
        
Turn 2: Execute tool, send result to LLM
        LLM responds: "The weather in Paris is 20°C and sunny"
        
Done: No more tool calls, return final response
```

The loop continues until:
- The LLM responds without requesting tool calls (success)
- Maximum turns reached (configurable via `max_turns`)
- An error occurs

### 4. Tool Dispatch

When the LLM requests a tool call:

1. Engine finds which server owns the tool
2. Sends the call to that server (MCP protocol or CLI execution)
3. Captures the result
4. Returns it to the LLM in the next turn

### 5. Result Collection

Every turn is recorded in the `AgentResult`:

```python
result = await aitest_run(agent, "What's the weather?")

result.turns          # List of all conversation turns
result.all_tool_calls # All tool calls made
result.final_response # The LLM's final text response
result.success        # True if completed without errors
```

## MCP vs CLI Servers

Both server types provide tools, but work differently:

### MCP Servers

Native MCP protocol over stdio:

```python
MCPServer(
    command=["python", "my_server.py"],
)
```

- Tools defined via `@server.tool()` decorator
- Full MCP protocol support
- Bidirectional communication

### CLI Servers

Command-line tools wrapped as callable tools:

```python
CLIServer(
    name="git",
    command="git",
    tool_prefix="git",  # Creates "git_execute" tool
)
```

The LLM calls it like: `git_execute(args="status --porcelain")`

- Stdout captured as tool result
- Simple wrapper for existing CLIs

## Skill Injection

When an agent has a skill, it's injected into the system prompt:

```python
agent = Agent(
    provider=Provider(model="azure/gpt-5-mini"),
    skill=Skill.from_path("skills/weather-expert"),
    system_prompt="You are a helpful assistant.",
)
```

The skill content is prepended to the system prompt, giving the LLM domain knowledge before it sees the user's request.

## Rate Limiting & Retries

LiteLLM handles transient failures automatically via its built-in `num_retries` parameter:

- **429 Too Many Requests**: Automatic retry with backoff
- **Connection errors**: Automatic retry
- **API errors**: Automatic retry for transient failures

By default, pytest-aitest uses 3 retries. This is handled internally by LiteLLM using [tenacity](https://tenacity.readthedocs.io/).

