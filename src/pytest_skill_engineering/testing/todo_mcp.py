"""Todo MCP server for integration testing.

Run as: python -m pytest_skill_engineering.testing.todo_mcp

Supports all three transports:
- stdio (default): ``python -m pytest_skill_engineering.testing.todo_mcp``
- streamable-http: ``python -m pytest_skill_engineering.testing.todo_mcp --transport streamable-http --port 8080``
- sse: ``python -m pytest_skill_engineering.testing.todo_mcp --transport sse --port 8080``
"""

from __future__ import annotations

import argparse
import json

from mcp.server.fastmcp import FastMCP

from pytest_skill_engineering.testing.todo import TodoStore

# ---------------------------------------------------------------------------
# Server & service
# ---------------------------------------------------------------------------

mcp = FastMCP("pytest-skill-engineering-todo-server")
_store = TodoStore()

# ---------------------------------------------------------------------------
# Tools – thin wrappers that delegate to TodoStore
# ---------------------------------------------------------------------------


@mcp.tool()
def add_task(title: str, list: str = "default", priority: str = "normal") -> str:
    """Add a new task to a todo list.

    Args:
        title: The task description (e.g., 'Buy groceries', 'Call dentist').
        list: Which list to add to (e.g., 'shopping', 'work', 'personal'). Default: 'default'.
        priority: Task priority ('low', 'normal', 'high'). Default: 'normal'.
    """
    result = _store.add_task(title, list, priority)
    if result.success:
        return json.dumps(result.value)
    return f"Error: {result.error}"


@mcp.tool()
def complete_task(task_id: str) -> str:
    """Mark a task as completed/done.

    Args:
        task_id: The ID of the task to complete.
    """
    result = _store.complete_task(task_id)
    if result.success:
        return json.dumps(result.value)
    return f"Error: {result.error}"


@mcp.tool()
def uncomplete_task(task_id: str) -> str:
    """Mark a completed task as not done (reopen it).

    Args:
        task_id: The ID of the task to reopen.
    """
    result = _store.uncomplete_task(task_id)
    if result.success:
        return json.dumps(result.value)
    return f"Error: {result.error}"


@mcp.tool()
def delete_task(task_id: str) -> str:
    """Delete/remove a task permanently.

    Args:
        task_id: The ID of the task to delete.
    """
    result = _store.delete_task(task_id)
    if result.success:
        return json.dumps(result.value)
    return f"Error: {result.error}"


@mcp.tool()
def list_tasks(list: str | None = None, show_completed: bool = True) -> str:
    """List all tasks, optionally filtered by list name or completion status.

    Args:
        list: Filter by list name (e.g., 'shopping'). Omit for all lists.
        show_completed: Include completed tasks? Default: true.
    """
    result = _store.list_tasks(list, show_completed)
    if result.success:
        return json.dumps(result.value)
    return f"Error: {result.error}"


@mcp.tool()
def get_lists() -> str:
    """Get all available todo list names."""
    result = _store.get_lists()
    if result.success:
        return json.dumps(result.value)
    return f"Error: {result.error}"


@mcp.tool()
def set_priority(task_id: str, priority: str) -> str:
    """Change the priority of a task.

    Args:
        task_id: The ID of the task.
        priority: New priority level ('low', 'normal', 'high').
    """
    result = _store.set_priority(task_id, priority)
    if result.success:
        return json.dumps(result.value)
    return f"Error: {result.error}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Parse args and run the server with the chosen transport."""
    parser = argparse.ArgumentParser(description="Todo MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
    )
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    # Configure host/port via FastMCP settings
    mcp.settings.host = args.host
    mcp.settings.port = args.port

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    elif args.transport == "sse":
        mcp.run(transport="sse")
    elif args.transport == "streamable-http":
        mcp.settings.stateless_http = True
        mcp.settings.json_response = True
        mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
