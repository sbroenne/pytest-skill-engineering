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
from pytest_skill_engineering import Eval, MCPServer, Provider, Wait

@pytest.fixture(scope="module")
def banking_server():
    return MCPServer(
        command=["python", "-m", "my_banking_mcp"],
        wait=Wait.for_tools(["get_balance"]),
    )

async def test_prompts_are_discoverable(banking_server):
    """Server exposes the expected prompt templates."""
    prompts = await banking_server.list_prompts()
    names = [p.name for p in prompts]
    assert "balance_summary" in names
    assert "transfer_confirmation" in names
```

`list_prompts()` returns `list[MCPPrompt]`. Each `MCPPrompt` has:

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Template identifier |
| `description` | `str \| None` | Human-readable description |
| `arguments` | `list[MCPPromptArgument]` | Template parameters |

## Rendering and Testing a Prompt

Use `MCPServer.get_prompt()` to render a template, then pass the result to `eval_run`:

```python
async def test_balance_summary_prompt(eval_run, banking_server):
    """The balance_summary prompt produces a coherent LLM response."""
    # Render the template (like VS Code does when the user invokes the slash command)
    messages = await banking_server.get_prompt(
        "balance_summary",
        {"account_type": "checking"},
    )
    assert messages, "Prompt returned no messages"

    agent = Eval(
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[banking_server],
    )
    result = await eval_run(agent, messages[0]["content"])

    assert result.success
    assert result.mcp_prompts  # prompts were discovered from the server
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

Combine template rendering with LLM behavioral assertions:

```python
from pytest_skill_engineering import Eval, MCPServer, Provider, Wait

@pytest.fixture(scope="module")
def my_server():
    return MCPServer(
        command=["python", "-m", "my_mcp_server"],
        wait=Wait.for_tools(["read_file"]),
    )

async def test_code_review_prompt(eval_run, my_server):
    """The /code_review slash command produces actionable feedback."""
    messages = await my_server.get_prompt("code_review", {"code": "def foo(): pass"})
    
    agent = Eval(
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[my_server],
    )
    result = await eval_run(agent, messages[0]["content"])
    
    assert result.success
    assert "review" in result.final_response.lower()
    assert result.mcp_prompts  # prompts were discovered
```

## EvalResult Fields

When running with an MCP server that exposes prompts, `EvalResult` includes:

| Field | Type | Description |
|-------|------|-------------|
| `mcp_prompts` | `list[MCPPrompt]` | Prompt templates discovered from all MCP servers |
| `prompt_name` | `str \| None` | Name of the prompt used (set via `prompt_name=` kwarg) |

Track which prompt was tested using the `prompt_name` kwarg on `eval_run`:

```python
result = await eval_run(
    agent,
    messages[0]["content"],
    prompt_name="balance_summary",  # tracked in the report
)
assert result.prompt_name == "balance_summary"
```

## Next Steps

- [Prompt Files](prompt-files.md) — Test user-facing slash commands (`.prompt.md` files)
- [Test MCP Servers](../how-to/test-mcp-servers.md) — Full guide for MCP server testing
- [EvalResult Reference](../reference/result.md) — All result fields
