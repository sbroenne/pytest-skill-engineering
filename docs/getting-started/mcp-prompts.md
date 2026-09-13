---
description: "Test MCP server prompt templates — verify that bundled slash commands produce the right LLM behavior."
---

# MCP Server Prompts

MCP servers can bundle **prompt templates** alongside their tools — reusable message templates that surface in VS Code as slash commands (e.g. `/mcp.servername.code_review`). Discover and render them explicitly with `MCPServerProcess`, then pass the rendered text to `copilot_eval`.

## What are MCP Prompts?

A prompt template is a server-side message recipe. When a user invokes `/mcp.myserver.code_review`, the MCP server renders the template (filling in arguments) and sends the resulting messages to the LLM. Testing prompt templates means verifying:

- The server exposes the expected templates (`list_prompts`)
- The rendered output contains what you expect
- The LLM behaves correctly when given the rendered prompt

## Discovering Prompts

Use `MCPServerProcess.list_prompts()` to discover what templates your server exposes:

```python
import sys
from pytest_skill_engineering import MCPServer
from pytest_skill_engineering.execution.servers import MCPServerProcess


async def test_prompts_are_discoverable():
    """Server exposes the expected prompt templates."""
    config = MCPServer(
        command=sys.executable,
        args=["-m", "pytest_skill_engineering.testing.banking_mcp"],
    )
    async with MCPServerProcess(config) as server:
        prompts = await server.list_prompts()
        assert "account_summary" in {prompt.name for prompt in prompts}
```

`list_prompts()` returns `list[MCPPrompt]`. Each `MCPPrompt` has:

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Template identifier |
| `description` | `str` | Human-readable description (empty if omitted) |
| `arguments` | `list[MCPPromptArgument]` | Template parameters |

## Rendering and Testing a Prompt

Render a template using its advertised arguments:

```python
async def test_account_summary_template():
    config = MCPServer(
        command=sys.executable,
        args=["-m", "pytest_skill_engineering.testing.banking_mcp"],
    )
    async with MCPServerProcess(config) as server:
        messages = await server.get_prompt("account_summary", {"account": "checking"})
    assert messages
    assert messages[0]["role"] == "user"
    assert "checking" in messages[0]["content"]
```

`get_prompt()` returns a list of dictionaries with `role` and `content` keys.
The banking template returns one user message, which can be sent directly.
For templates with several messages, explicitly decide how to represent their
roles and context in the single prompt string accepted by `copilot_eval`; do
not silently discard all but the first message.

## Testing the Full Flow

Combine MCP tools with LLM behavioral assertions:

```python
from pytest_skill_engineering.copilot import CopilotEval


async def test_account_summary_prompt(copilot_eval):
    """The rendered account-summary prompt produces a balance response."""
    config = MCPServer(
        command=sys.executable,
        args=["-m", "pytest_skill_engineering.testing.banking_mcp"],
    )
    async with MCPServerProcess(config) as server:
        messages = await server.get_prompt("account_summary", {"account": "checking"})
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    agent = CopilotEval(
        name="account-summary",
        instructions="You are a banking assistant. Use MCP tools for account data.",
        mcp_servers={
            "banking": {
                "type": "local",
                "command": sys.executable,
                "args": ["-m", "pytest_skill_engineering.testing.banking_mcp"],
                "tools": ["*"],
            }
        },
    )
    result = await copilot_eval(agent, messages[0]["content"])
    assert result.success
    assert "balance" in (result.final_response or "").lower()
```

## Naming tests

Use descriptive test names or pytest parameter IDs to identify templates in
reports. `CopilotResult` does not expose discovered MCP prompts or a
`prompt_name` field; `copilot_eval` does not accept a `prompt_name` keyword.

## Next Steps

- [Prompt Files](prompt-files.md) — Test user-facing slash commands (`.prompt.md` files)
- [Test MCP Servers](../how-to/test-mcp-servers.md) — Full guide for MCP server testing
- [CopilotResult Reference](../reference/result.md) — All result fields
