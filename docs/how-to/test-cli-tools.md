---
description: "Test CLI workflows with Copilot's native shell tools, or document CLIServer correctly when you need a wrapped CLI tool."
---

# How to test CLI tools

For Copilot workflows, the simplest path is usually to let Copilot use its native shell tools in a controlled working directory.

## Preferred pattern: native shell workflow

```python
from pytest_skill_engineering.copilot import CopilotEval


async def test_git_status(copilot_eval, tmp_path):
    agent = CopilotEval(
        name="git-helper",
        model="gpt-5.4-mini",
        instructions="Use terminal tools to inspect the repository state.",
        working_directory=str(tmp_path),
    )

    result = await copilot_eval(agent, "Show me the repository status")

    assert result.success
```

## When you have a wrapped CLI tool

`CLIServer` is a lower-level helper for wrapping a CLI as a tool surface.
Its constructor does **not** take `name=`.

```python
from pytest_skill_engineering import CLIServer


git_server = CLIServer(
    command="git",
    tool_prefix="git",
    discover_help=True,
)
```

## Configuration options

```python
CLIServer(
    command="git",
    tool_prefix="git",
    cwd="/path/to/repo",
    env={"LC_ALL": "C"},
    discover_help=False,
    help_flag="--help",
    description="Run git commands through a single wrapped tool.",
)
```

## Complete Copilot-facing example

If you expose a CLI through your own MCP wrapper, attach that wrapper to `CopilotEval` using `mcp_servers={...}`:

```python
import sys

from pytest_skill_engineering.copilot import CopilotEval


GIT_MCP = {
    "git": {
        "command": sys.executable,
        "args": ["-m", "my_project.git_mcp"],
        "tools": ["*"],
    }
}


async def test_git_log(copilot_eval):
    agent = CopilotEval(
        name="git-mcp",
        model="gpt-5.4-mini",
        instructions="Use the git tools to inspect repository history.",
        mcp_servers=GIT_MCP,
    )

    result = await copilot_eval(agent, "Show me the last three commits")

    assert result.success
```
