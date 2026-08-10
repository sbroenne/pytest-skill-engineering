---
description: "Attach MCP servers directly to CopilotEval using the current Copilot SDK mcp_servers config shape."
---

# How to test MCP servers

The primary pattern is to attach MCP servers directly to `CopilotEval(mcp_servers={...})`.

## Local stdio server

```python
import sys

from pytest_skill_engineering.copilot import CopilotEval


BANKING_MCP = {
    "banking": {
        "command": sys.executable,
        "args": ["-m", "pytest_skill_engineering.testing.banking_mcp"],
        "tools": ["*"],
    }
}


async def test_balance(copilot_eval):
    agent = CopilotEval(
        name="banking-default",
        model="gpt-5.4-mini",
        instructions="Use the banking tools for account requests.",
        mcp_servers=BANKING_MCP,
    )

    result = await copilot_eval(agent, "What's my checking balance?")

    assert result.success
    assert result.tool_was_called("get_balance")
```

Use `tools: ["*"]` unless you intentionally want the server itself to expose only a subset of tools.

## SSE server

```python
REMOTE_MCP = {
    "crm": {
        "url": "http://localhost:8000/sse",
        "transport": "sse",
        "tools": ["*"],
    }
}
```

## Streamable HTTP server

```python
REMOTE_MCP = {
    "crm": {
        "url": "http://localhost:8000/mcp",
        "transport": "streamable-http",
        "headers": {"Authorization": "Bearer ${CRM_TOKEN}"},
        "tools": ["*"],
    }
}
```

## Multiple servers

```python
import sys

ASSISTANT_MCP = {
    "banking": {
        "command": sys.executable,
        "args": ["-m", "pytest_skill_engineering.testing.banking_mcp"],
        "tools": ["*"],
    },
    "todo": {
        "command": sys.executable,
        "args": ["-m", "pytest_skill_engineering.testing.todo_mcp"],
        "tools": ["*"],
    },
}
```

## Restrict what the eval can use

`mcp_servers` controls what each server exposes. `allowed_tools` controls what the eval is allowed to call overall.

```python
agent = CopilotEval(
    name="balance-only",
    model="gpt-5.4-mini",
    instructions="Use balance tools only.",
    mcp_servers=BANKING_MCP,
    allowed_tools=["get_balance", "get_all_balances"],
)
```

## When to use lower-level helpers

`MCPServer`, `Wait`, and `MCPServerProcess` still exist for lower-level process control and prompt discovery, but your **complete Copilot-facing example** should still show the final `mcp_servers={...}` configuration.
