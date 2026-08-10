---
description: "Write your first CopilotEval, attach MCP servers, and compare system prompts, skills, and custom agents."
---

# Getting Started

pytest-skill-engineering uses the real GitHub Copilot coding agent to test AI behavior.

## What you are testing

You are not re-testing your Python functions. You are testing whether Copilot can:

- discover the right tool
- choose the right arguments
- recover from errors
- follow the right system prompt
- route work to the right custom agent

## Install and authenticate

```bash
uv add pytest-skill-engineering
gh auth login
```

In CI, set `GITHUB_TOKEN` instead.

## First complete example

```python
import sys

from pytest_skill_engineering.copilot import CopilotEval


TODO_MCP = {
    "todo": {
        "command": sys.executable,
        "args": ["-m", "pytest_skill_engineering.testing.todo_mcp"],
        "tools": ["*"],
    }
}


async def test_add_task(copilot_eval):
    agent = CopilotEval(
        name="todo-default",
        model="gpt-5.4-mini",
        instructions="Use the todo tools to manage tasks.",
        mcp_servers=TODO_MCP,
    )

    result = await copilot_eval(agent, "Add a task to buy groceries")

    assert result.success
    assert result.tool_was_called("add_task")
```

Run it with:

```bash
uv run python -m pytest tests/test_todo.py -v
```

## What to compare next

- [System prompts](system-prompts.md)
- [Skills](skills.md)
- [Custom agents](custom-agents.md)
- [Comparing configurations](comparing.md)
- [Multi-turn sessions](sessions.md)
