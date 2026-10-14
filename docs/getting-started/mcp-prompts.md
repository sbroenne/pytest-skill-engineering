---
description: "Discover an MCP prompt template, render it, and send its task text to Copilot."
---

# MCP Server Prompts

Use `MCPServerProcess` to discover and render server-provided prompt templates.
Then pass the rendered task text to `copilot_eval`. These are two different
checks: template rendering can be tested without a model; task execution uses
real Copilot and may consume premium requests.

## What are MCP Prompts?

A prompt template is a server-side message recipe with named arguments.
Editors may expose it as a slash command. This harness tests the server's
template API and the rendered task, not an editor's slash-command registration.

## Discovering Prompts

The bundled banking server provides an `account_summary` template:

```python
from __future__ import annotations

import sys

from pytest_skill_engineering import MCPServer
from pytest_skill_engineering.execution.servers import MCPServerProcess


async def test_prompts_are_discoverable():
    config = MCPServer(
        command=[sys.executable],
        args=["-m", "pytest_skill_engineering.testing.banking_mcp"],
    )
    async with MCPServerProcess(config) as server:
        prompts = await server.list_prompts()
    assert "account_summary" in {prompt.name for prompt in prompts}
```

`list_prompts()` returns `MCPPrompt` objects with `name`, `description`, and
`arguments`. Each argument has a name, description, and required flag. Assert
expected names explicitly: the current helper can return an empty list when
listing fails or prompts are unsupported.

## Rendering and Testing a Prompt

Using the imports above:

```python
async def test_account_summary_template():
    config = MCPServer(
        command=[sys.executable],
        args=["-m", "pytest_skill_engineering.testing.banking_mcp"],
    )
    async with MCPServerProcess(config) as server:
        messages = await server.get_prompt("account_summary", {"account": "checking"})
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert "checking" in messages[0]["content"]
```

`get_prompt()` returns dictionaries containing `role` and `content`. Validate
both before executing the task. `copilot_eval` accepts one prompt string, not
a list of role-tagged messages. For a multi-message template, explicitly decide
how to represent its context and roles; do not silently discard messages.

## Testing the Full Flow

This test renders the bundled template, starts a separate banking server for
Copilot, and checks the returned account data:

```python
import json

from pytest_skill_engineering.copilot import CopilotEval


async def test_account_summary_prompt(copilot_eval):
    config = MCPServer(
        command=[sys.executable],
        args=["-m", "pytest_skill_engineering.testing.banking_mcp"],
    )
    async with MCPServerProcess(config) as server:
        messages = await server.get_prompt("account_summary", {"account": "checking"})
    assert len(messages) == 1 and messages[0]["role"] == "user"
    agent = CopilotEval(
        name="account-summary",
        model="gpt-5.6-sol",
        instructions="Use banking tools for account data.",
        mcp_servers={
            "banking": {
                "command": sys.executable,
                "args": ["-m", "pytest_skill_engineering.testing.banking_mcp"],
                "tools": ["*"],
            }
        },
    )
    result = await copilot_eval(agent, messages[0]["content"])

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

The two server processes do not share in-memory state. This read-only fixture
has a known starting balance. For stateful templates, own initialization and
output verification in your application fixtures. Checking the returned balance
does not assess the quality of Copilot's prose summary.

## Naming tests

Use test names or parameter IDs to identify templates. `CopilotResult` does not
expose discovered prompts or a `prompt_name` field; `copilot_eval` has no
`prompt_name` keyword.

## Next Steps

- [Prompt files](prompt-files.md): load reusable file bodies.
- [Test MCP servers](../how-to/test-mcp-servers.md): attach tools and verify operations.
- [Result reference](../reference/result.md): inspect captured calls.
