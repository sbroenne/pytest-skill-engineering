---
description: "Bundled Todo and Banking MCP servers and lower-level process helpers."
---

# Test servers and helpers

The bundled servers provide small applications for examples and framework
tests. They are not alternative runners: real Copilot execution still uses
`CopilotEval` and `copilot_eval`.

## Bundled MCP servers

Use the current Python executable so the server runs in the same environment as
the test.

### Todo MCP server

Use Todo for a small first test of task creation and returned task state.

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

Use Banking for account lookup and transfer scenarios. Check returned operation
values or actual fixture state, not just the presence of a transfer call.

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

Attach either mapping to `CopilotEval(mcp_servers=...)`. The
[quickstart](../getting-started/index.md) shows Todo execution and verification.

## Lower-level helpers

- `MCPServer` — process configuration for local or remote MCP servers
- `MCPServerProcess` — direct protocol interaction for prompt discovery or lower-level checks
- `Wait` — startup readiness helpers such as `Wait.for_tools(...)`
- `CLIServer` — wraps a CLI as a single tool surface; constructor is `CLIServer(command=..., tool_prefix=...)`

Use these helpers when a fixture needs direct protocol access or deterministic
process setup. Do not pass an `MCPServer` object where `CopilotEval` expects an SDK
`mcp_servers` mapping; they have different configuration shapes. See
[MCP server prompts](../getting-started/mcp-prompts.md) for direct protocol use
and [CLI testing](../how-to/test-cli-tools.md) for tool adapters.
