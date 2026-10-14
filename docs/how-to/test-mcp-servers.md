---
description: "Attach MCP tools to a Copilot task and check completed calls and returned data."
---

# How to test MCP servers

Attach servers with `CopilotEval(mcp_servers={...})`. Ask for a task that needs
their tools, then assert on completed operation data or application state.
Use the server's ordinary unit tests for implementation behavior that does not
need Copilot.

## Local stdio server

This configuration starts the bundled banking fixture server in the current
Python environment:

```python
from __future__ import annotations

import json
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
        name="banking-balance",
        model="gpt-5.6-sol",
        instructions="Use banking tools for account requests.",
        mcp_servers=BANKING_MCP,
    )
    result = await copilot_eval(agent, "Use get_balance to retrieve the checking balance.")

    assert result.success, result.error
    calls = result.tool_calls_for("banking-get_balance")
    assert calls
    call = calls[-1]
    assert call.arguments == {"account": "checking"}
    assert call.success is True and call.evidence_complete
    assert call.result is not None
    display, structured = call.result.rsplit("\n\n", 1)
    assert json.loads(structured) == {"result": display}
    assert json.loads(display)["balance"] == 1500
```

The string-result decoding above is specific to this server's display and
structured MCP output. Use your server's actual output contract rather than
assuming every MCP response has this shape. A completed protocol call can
still contain an application error.

For mutations, initialize disposable state and verify it through an independent
application fixture. Reading a known balance here verifies the returned data;
it does not assess the assistant's prose.

## SSE server

This configuration requires an already-running test service:

```python
REMOTE_MCP = {
    "crm": {
        "url": "http://localhost:8000/sse",
        "type": "sse",
        "tools": ["*"],
    }
}
```

## Streamable HTTP server

```python
import os

REMOTE_MCP = {
    "crm": {
        "url": "http://localhost:8000/mcp",
        "type": "http",
        "headers": {"Authorization": f"Bearer {os.environ['CRM_TEST_TOKEN']}"},
        "tools": ["*"],
    }
}
```

Use an authorized test credential supplied by your environment, not a token
embedded in source. Your fixtures own remote-service startup, readiness, state
reset, and cleanup. Cancelling a local request does not prove a remote action
stopped.

## Multiple servers

Add another named entry to the mapping:

```python
ASSISTANT_MCP = {
    **BANKING_MCP,
    "todo": {
        "command": sys.executable,
        "args": ["-m", "pytest_skill_engineering.testing.todo_mcp"],
        "tools": ["*"],
    },
}
```

Use actual captured tool names, such as `banking-get_balance`, in result
helpers. Server prefixes distinguish tools with similar names; there is no
`CopilotResult.tool_was_called_from_server()` helper.

## Restrict what the eval can use

The server's `tools` list selects the tools exposed to the session. For example,
replace `["*"]` with `["get_balance", "get_all_balances"]` for a read-only
banking test. `["*"]` exposes all tools from that server.

`allowed_tools` and `excluded_tools` configure the SDK's overall available and
excluded tool lists. Use the runtime tool identifiers for your environment;
do not assume a server-local name is the same as a captured runtime name.
These filters do not replace guarded adapters, server authorization, or
application-level permissions.

## When to use lower-level helpers

Use `MCPServer`, `Wait`, and `MCPServerProcess` for direct process control,
readiness checks, or [prompt-template discovery](../getting-started/mcp-prompts.md).
Their configuration shape differs from the SDK's `mcp_servers` dictionary.
A Copilot-facing test should still show the final `CopilotEval` configuration
and its output assertions.

See [Compare server variants](../getting-started/ab-testing-servers.md) when
investigating a description, schema, or backend change.
