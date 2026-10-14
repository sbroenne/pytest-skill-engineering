---
description: "Load reusable prompt-file bodies as user tasks and verify their output."
---

# Prompt Files (Slash Commands)

Use `load_prompt_file()` to test the task text in a reusable prompt file.
Editors may expose these files as slash commands, but this harness sends the
body as a user prompt. It does not test editor registration, frontmatter-driven
routing, or variable expansion.

## Loading a Prompt File

Create `.github/prompts/save-total.prompt.md`:

```markdown
---
description: Save a calculated total as JSON.
---

Write total.json containing only the numeric field total, equal to 2 + 3.
```

Then check its output:

```python
import json

from pytest_skill_engineering import load_prompt_file
from pytest_skill_engineering.copilot import CopilotEval


async def test_save_total_prompt(copilot_eval, tmp_path):
    prompt = load_prompt_file(".github/prompts/save-total.prompt.md")
    agent = CopilotEval(
        name=f"prompt-{prompt['name']}",
        model="gpt-5.6-sol",
        working_directory=str(tmp_path),
    )
    result = await copilot_eval(agent, prompt["body"])

    assert result.success, result.error
    assert json.loads((tmp_path / "total.json").read_text(encoding="utf-8")) == {"total": 5}
```

This establishes that the prompt produced the specified artifact in this run,
not that an editor's `/save-total` command works.

The returned dictionary contains:

| Key | Value |
|---|---|
| `name` | Filename-derived name, such as `save-total` |
| `body` | Markdown below the frontmatter |
| `description` | Frontmatter description, or `""` |
| `metadata` | Full frontmatter mapping |

## Prompt File Format

Frontmatter is parsed and retained as metadata; the loader does not use it to
select the eval's model, tools, or custom agent. Configure those explicitly on
`CopilotEval`. Missing files, malformed frontmatter, or an empty body are errors.

## Testing All Prompt Files

`load_prompt_files(directory)` reads immediate prompt files. For a directory
whose prompts all share the same output contract:

```python
import pytest

from pytest_skill_engineering import load_prompt_files

PROMPTS = load_prompt_files(".github/prompts/total-variants")


@pytest.mark.parametrize("prompt", PROMPTS, ids=lambda item: item["name"])
async def test_total_variants(copilot_eval, tmp_path, prompt):
    agent = CopilotEval(
        name=prompt["name"],
        model="gpt-5.6-sol",
        working_directory=str(tmp_path),
    )
    result = await copilot_eval(agent, prompt["body"])
    assert result.success, result.error
    assert json.loads((tmp_path / "total.json").read_text(encoding="utf-8")) == {"total": 5}
```

This builds on the imports above and requires your own variant files. Give
different tasks their own fixtures and checks instead of using one generic
session-success assertion.

## VS Code vs Claude Code

| Source format | Typical location | Extension |
|---|---|---|
| VS Code prompt file | `.github/prompts/` | `.prompt.md` |
| Claude Code command | `.claude/commands/` | `.md` |

Both bodies can be loaded. Duplicate filename-derived names, including a
`.prompt.md` and `.md` with the same name, raise an error. Execution remains
GitHub Copilot in either case.

## Identifying prompt files in evidence

Use eval names and pytest parameter IDs. `copilot_eval` takes an eval and a
prompt string; it has no `prompt_name` keyword, and `CopilotResult` has no
`prompt_name` field. Record safe source names with `record_property` if needed.

## Combining with Tools

Configure tools and workspace explicitly when a prompt depends on them. Seed
any referenced files or application state in your fixtures. Tool presence only
shows that a call occurred; validate returned data or final state too.

See [MCP server prompts](mcp-prompts.md) for server-rendered tasks,
[System prompts](system-prompts.md) for instructions, and
[Custom agents](custom-agents.md) for definitions.
