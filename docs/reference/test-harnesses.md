---
description: "Built-in local MCP test servers and low-level helpers that pair with CopilotEval."
---

# Test harnesses

The public execution harness is `CopilotEval`.
This page documents the built-in local test servers and helper types you can pair with it.

## Built-in MCP servers

### Todo MCP server

```python
import sys

TODO_MCP = {
    "todo": {
        "command": sys.executable,
        "args": ["-m", "pytest_skill_engineering.testing.todo_mcp"],
        "tools": ["*"],
    }
}
```

### Banking MCP server

```python
import sys

BANKING_MCP = {
    "banking": {
        "command": sys.executable,
        "args": ["-m", "pytest_skill_engineering.testing.banking_mcp"],
        "tools": ["*"],
    }
}
```

Attach either mapping to `CopilotEval(mcp_servers=...)`.

## Lower-level helpers

- `MCPServer` — process configuration for local or remote MCP servers
- `MCPServerProcess` — direct protocol interaction for prompt discovery or lower-level checks
- `Wait` — startup readiness helpers such as `Wait.for_tools(...)`
- `CLIServer` — wraps a CLI as a single tool surface; constructor is `CLIServer(command=..., tool_prefix=...)`

These helpers are useful for fixture setup and deterministic process control, but the complete Copilot-facing example should still show the final `mcp_servers={...}` mapping.
