---
description: "Test MCP server prompt templates — verify that bundled slash commands produce the right LLM behavior."
---

# MCP Server Prompts

MCP servers can bundle **prompt templates** alongside their tools — reusable message templates that surface in VS Code as slash commands (e.g. `/mcp.servername.code_review`). The plugin discovers and tests these templates so you can verify they produce the expected LLM behavior.

## What are MCP Prompts?

A prompt template is a server-side message recipe. When a user invokes `/mcp.myserver.code_review`, the MCP server renders the template (filling in arguments) and sends the resulting messages to the LLM. Testing prompt templates means verifying:

- The server exposes the expected templates (`list_prompts`)
- The rendered output contains what you expect
- The LLM behaves correctly when given the rendered prompt

## Discovering Prompts

Use `MCPServer.list_prompts()` to discover what templates your server exposes:

```python
import pytest
from pytest_skill_engineering.copilot import CopilotEval

@pytest.fixture(scope="module")
def banking_server():
    # MCP server setup handled by CopilotEval
    pass

async def test_prompts_are_discoverable(banking_server):
    """Server exposes the expected prompt templates."""
    # Note: Copilot SDK provides built-in MCP server integration
    # Prompt discovery is automatic
```

`list_prompts()` returns `list[MCPPrompt]`. Each `MCPPrompt` has:

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Template identifier |
| `description` | `str \| None` | Human-readable description |
| `arguments` | `list[MCPPromptArgument]` | Template parameters |

## Rendering and Testing a Prompt

Use `CopilotEval` with the Copilot SDK's built-in MCP integration:

```python
async def test_balance_summary_prompt(copilot_eval):
    """The balance_summary prompt produces a coherent LLM response."""
    agent = CopilotEval(
        name="banking-test",
        instructions="You are a banking assistant. Use MCP tools to access account data.",
    )
    result = await copilot_eval(agent, "Get a balance summary for checking account")

    assert result.success
    assert "balance" in result.final_response.lower()
```

`get_prompt()` returns `list[{"role": str, "content": str}]` — the assembled messages produced by the template. Use `messages[0]["content"]` as the test prompt.

## Asserting on Rendered Content

Before running through the LLM, check that the template filled arguments correctly:

```python
async def test_code_review_template_renders(banking_server):
    """Template arguments are substituted into the rendered prompt."""
    messages = await banking_server.get_prompt(
        "code_review",
        {"code": "def foo(): pass", "language": "python"},
    )
    assert len(messages) > 0
    content = messages[0]["content"]
    assert "foo" in content          # argument was injected
    assert "python" in content.lower()
```

## Testing the Full Flow

Combine MCP tools with LLM behavioral assertions:

```python
from pytest_skill_engineering.copilot import CopilotEval

async def test_code_review_prompt(copilot_eval):
    """The code review slash command produces actionable feedback."""
    agent = CopilotEval(
        name="code-reviewer",
        instructions="You are a code reviewer. Use MCP tools to read files and provide feedback.",
    )
    result = await copilot_eval(agent, "Review this code: def foo(): pass")
    
    assert result.success
    assert "review" in result.final_response.lower()
```

## EvalResult Fields

When running with an MCP server that exposes prompts, `EvalResult` includes:

| Field | Type | Description |
|-------|------|-------------|
| `mcp_prompts` | `list[MCPPrompt]` | Prompt templates discovered from all MCP servers |
| `prompt_name` | `str \| None` | Name of the prompt used (set via `prompt_name=` kwarg) |

Track which prompt was tested using the `prompt_name` kwarg on `copilot_eval`:

```python
result = await copilot_eval(
    agent,
    "Get a balance summary",
    prompt_name="balance_summary",  # tracked in the report
)
assert result.prompt_name == "balance_summary"
```

## Next Steps

- [Prompt Files](prompt-files.md) — Test user-facing slash commands (`.prompt.md` files)
- [Test MCP Servers](../how-to/test-mcp-servers.md) — Full guide for MCP server testing
- [EvalResult Reference](../reference/result.md) — All result fields
