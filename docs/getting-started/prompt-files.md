---
description: "Test prompt files (slash commands) — verify that .prompt.md files produce the right LLM behavior when invoked."
---

# Prompt Files (Slash Commands)

**Prompt files** are reusable prompts that users invoke as slash commands (e.g. `/review`, `/explain`). VS Code uses `.prompt.md` files in `.github/prompts/`; Claude Code uses `.md` files in `.claude/commands/`. Testing them means verifying the LLM behaves correctly when the slash command is invoked.

## Loading a Prompt File

Use `load_prompt_file()` to load the body of a single prompt file:

```python
from pytest_skill_engineering import Eval, Provider, MCPServer, load_prompt_file

code_server = MCPServer(command=["python", "code_server.py"])
agent = Eval(
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[code_server],
)

async def test_review_command(eval_run):
    """The /review slash command produces actionable feedback."""
    prompt = load_prompt_file(".github/prompts/review.prompt.md")
    result = await eval_run(
        agent,
        prompt["body"],
        prompt_name="review",  # tracked in the report
    )
    assert result.success
    assert result.prompt_name == "review"
```

`load_prompt_file()` returns a dict with:

| Key | Description |
|-----|-------------|
| `name` | Derived from filename (e.g. `review`) |
| `body` | The markdown body — what gets sent to the LLM |
| `description` | From frontmatter `description:` field, or `None` |
| `metadata` | All other frontmatter fields |

## Prompt File Format

```markdown title=".github/prompts/review.prompt.md"
---
description: Review code for quality and security issues
mode: agent
---

Review the current file for:
- Security vulnerabilities
- Performance issues
- Code style problems

Provide specific line numbers and suggested fixes.
```

The `body` is the content below the frontmatter separator.

## Testing All Prompt Files

Use `load_prompt_files()` to load every prompt file in a directory and parametrize over them:

```python
import pytest
from pytest_skill_engineering import Eval, Provider, MCPServer, load_prompt_files

PROMPTS = load_prompt_files(".github/prompts/")

code_server = MCPServer(command=["python", "code_server.py"])
agent = Eval(
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[code_server],
)

@pytest.mark.parametrize("prompt", PROMPTS, ids=lambda p: p["name"])
async def test_prompt_files(eval_run, prompt):
    """All slash commands produce a successful response."""
    result = await eval_run(
        agent,
        prompt["body"],
        prompt_name=prompt["name"],
    )
    assert result.success
    assert result.prompt_name == prompt["name"]
```

## VS Code vs Claude Code

| Format | Location | Extension | Invoked as |
|--------|----------|-----------|-----------|
| VS Code | `.github/prompts/` | `.prompt.md` | `/review` in Copilot Chat |
| Claude Code | `.claude/commands/` | `.md` | `/review` in Claude Code |

`load_prompt_files()` handles both — `.prompt.md` files take precedence if both exist with the same name.

## Tracking Prompt Names in Reports

The `prompt_name` kwarg on `eval_run` tags the result so reports can group tests by slash command:

```python
result = await eval_run(agent, prompt["body"], prompt_name=prompt["name"])
# result.prompt_name == "review"
```

This appears in the HTML report's per-prompt breakdown, letting you compare how different slash commands perform across models.

## Combining with MCP Servers

Prompt files often reference tools. Test them with the appropriate MCP servers:

```python
from pytest_skill_engineering import Eval, Provider, MCPServer, Wait, load_prompt_file

@pytest.fixture(scope="module")
def code_server():
    return MCPServer(
        command=["python", "-m", "code_tools_mcp"],
        wait=Wait.for_tools(["read_file", "list_directory"]),
    )

async def test_explain_command(eval_run, code_server):
    """The /explain command reads the file before explaining."""
    prompt = load_prompt_file(".github/prompts/explain.prompt.md")
    agent = Eval(
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[code_server],
    )
    result = await eval_run(agent, prompt["body"], prompt_name="explain")
    
    assert result.success
    assert result.tool_was_called("read_file")
    assert result.prompt_name == "explain"
```

## Next Steps

- [MCP Server Prompts](mcp-prompts.md) — Test server-side prompt templates
- [Custom Agents](custom-agents.md) — Test `.agent.md` specialist agent files
- [EvalResult Reference](../reference/result.md) — All result fields
