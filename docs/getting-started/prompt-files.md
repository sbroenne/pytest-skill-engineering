---
description: "Test prompt files (slash commands) — verify that .prompt.md files produce the right LLM behavior when invoked."
---

# Prompt Files (Slash Commands)

**Prompt files** are reusable user prompts that editors expose as slash commands
(e.g. `/review`, `/explain`). VS Code uses `.prompt.md` files in
`.github/prompts/`; Claude Code uses `.md` files in `.claude/commands/`.
The loader tests the file's body as a user prompt, not editor slash-command
registration or variable expansion. A system prompt instead configures agent
behavior through `CopilotEval.instructions`.

## Loading a Prompt File

Use `load_prompt_file()` to load the body of a single prompt file:

```python
from pytest_skill_engineering import load_prompt_file
from pytest_skill_engineering.copilot import CopilotEval

agent = CopilotEval(name="prompt-test")


async def test_review_command(copilot_eval):
    """The /review slash command produces actionable feedback."""
    prompt = load_prompt_file(".github/prompts/review.prompt.md")
    result = await copilot_eval(agent, prompt["body"])
    assert result.success
```

`load_prompt_file()` returns a dict with:

| Key | Description |
|-----|-------------|
| `name` | Derived from filename (e.g. `review`) |
| `body` | The markdown body — what gets sent to the LLM |
| `description` | From frontmatter `description:` field, or an empty string |
| `metadata` | Full frontmatter mapping |

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
from pytest_skill_engineering import load_prompt_files
from pytest_skill_engineering.copilot import CopilotEval

PROMPTS = load_prompt_files(".github/prompts/")

agent = CopilotEval(name="prompt-test")


@pytest.mark.parametrize("prompt", PROMPTS, ids=lambda p: p["name"])
async def test_prompt_files(copilot_eval, prompt):
    """All slash commands produce a successful response."""
    result = await copilot_eval(agent, prompt["body"])
    assert result.success
```

## VS Code vs Claude Code

| Format | Location | Extension | Invoked as |
|--------|----------|-----------|-----------|
| VS Code | `.github/prompts/` | `.prompt.md` | `/review` in Copilot Chat |
| Claude Code | `.claude/commands/` | `.md` | `/review` in Claude Code |

`load_prompt_files()` handles both — `.prompt.md` files take precedence if both exist with the same name.

## Tracking Prompt Names in Reports

Use pytest parameter IDs, as in the example above, to identify each prompt file
in test results. `copilot_eval` accepts an eval and a prompt string; it has no
`prompt_name` keyword, and `CopilotResult` has no `prompt_name` field.

## Combining with Tools

Prompt files often reference tools. Configure the tools and workspace explicitly.
This example uses Copilot's file-reading tools rather than an MCP server:

```python
from pytest_skill_engineering import load_prompt_file
from pytest_skill_engineering.copilot import CopilotEval


async def test_explain_command(copilot_eval, tmp_path):
    """The /explain command reads the file before explaining."""
    prompt = load_prompt_file(".github/prompts/explain.prompt.md")
    (tmp_path / "example.py").write_text("def add(a, b):\n    return a + b\n")
    agent = CopilotEval(name="explain-test", working_directory=str(tmp_path))
    result = await copilot_eval(agent, prompt["body"] + "\nRead and explain example.py.")

    assert result.success
    assert result.tool_was_called("read_file")
```

## Next Steps

- [MCP Server Prompts](mcp-prompts.md) — Test server-side prompt templates
- [Custom Agents](custom-agents.md) — Test `.agent.md` specialist agent files
- [CopilotResult Reference](../reference/result.md) — All result fields
