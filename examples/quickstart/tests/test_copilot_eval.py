from __future__ import annotations

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
        name="todo-quickstart",
        model="gpt-5.6-sol",
        instructions="Use the todo tools to manage tasks.",
        mcp_servers=TODO_MCP,
    )

    result = await copilot_eval(agent, "Add a task to buy groceries")

    assert result.success
    assert result.tool_was_called("todo-add_task")
