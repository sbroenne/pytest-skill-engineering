from __future__ import annotations

import json
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

    result = await copilot_eval(agent, "Add a task titled exactly 'buy groceries'")

    assert result.success
    assert result.tool_was_called("todo-add_task")
    calls = result.tool_calls_for("todo-add_task")
    assert len(calls) == 1
    assert calls[0].arguments["title"] == "buy groceries"
    assert calls[0].success is True
    assert calls[0].evidence_complete
    assert calls[0].result is not None
    # The SDK includes both display text and the structured MCP string result.
    display, structured = calls[0].result.rsplit("\n\n", 1)
    assert json.loads(structured) == {"result": display}
    saved = json.loads(display)
    assert saved["title"] == "buy groceries"
    assert saved["completed"] is False
