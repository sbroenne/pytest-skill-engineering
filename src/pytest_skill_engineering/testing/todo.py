"""Todo store for testing - task management.

Provides a stateful todo list for testing natural language → CRUD operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from pytest_skill_engineering.testing.types import ToolResult


@dataclass
class Task:
    """A todo task."""

    id: str
    title: str
    list_name: str = "default"
    completed: bool = False
    priority: str = "normal"  # low, normal, high


@dataclass
class TodoStore:
    """In-memory todo list store for testing."""

    tasks: dict[str, Task] = field(default_factory=dict)

    def add_task(
        self, title: str, list_name: str = "default", priority: str = "normal"
    ) -> ToolResult:
        """Add a new task.

        Args:
            title: Task description
            list_name: Which list to add to (default: "default")
            priority: Task priority (low, normal, high)

        Returns:
            ToolResult with the created task
        """
        if priority not in ("low", "normal", "high"):
            return ToolResult(
                success=False,
                value=None,
                error=f"Invalid priority '{priority}'. Must be: low, normal, high",
            )

        task_id = str(uuid4())[:8]
        task = Task(
            id=task_id,
            title=title,
            list_name=list_name.lower().strip(),
            priority=priority,
        )
        self.tasks[task_id] = task

        return ToolResult(
            success=True,
            value={
                "id": task.id,
                "title": task.title,
                "list": task.list_name,
                "priority": task.priority,
                "completed": task.completed,
                "message": f"Added task '{title}' to {list_name} list",
            },
        )

    def complete_task(self, task_id: str) -> ToolResult:
        """Mark a task as completed.

        Args:
            task_id: The task ID to complete

        Returns:
            ToolResult with updated task
        """
        if task_id not in self.tasks:
            return ToolResult(
                success=False,
                value=None,
                error=f"Task '{task_id}' not found",
            )

        task = self.tasks[task_id]
        task.completed = True

        return ToolResult(
            success=True,
            value={
                "id": task.id,
                "title": task.title,
                "completed": True,
                "message": f"Completed task: {task.title}",
            },
        )

    def uncomplete_task(self, task_id: str) -> ToolResult:
        """Mark a task as not completed.

        Args:
            task_id: The task ID to uncomplete

        Returns:
            ToolResult with updated task
        """
        if task_id not in self.tasks:
            return ToolResult(
                success=False,
                value=None,
                error=f"Task '{task_id}' not found",
            )

        task = self.tasks[task_id]
        task.completed = False

        return ToolResult(
            success=True,
            value={
                "id": task.id,
                "title": task.title,
                "completed": False,
                "message": f"Reopened task: {task.title}",
            },
        )

    def delete_task(self, task_id: str) -> ToolResult:
        """Delete a task.

        Args:
            task_id: The task ID to delete

        Returns:
            ToolResult confirming deletion
        """
        if task_id not in self.tasks:
            return ToolResult(
                success=False,
                value=None,
                error=f"Task '{task_id}' not found",
            )

        task = self.tasks.pop(task_id)
        return ToolResult(
            success=True,
            value={"message": f"Deleted task: {task.title}"},
        )

    def list_tasks(self, list_name: str | None = None, show_completed: bool = True) -> ToolResult:
        """List tasks, optionally filtered.

        Args:
            list_name: Filter by list name (optional)
            show_completed: Include completed tasks (default True)

        Returns:
            ToolResult with list of tasks
        """
        tasks = list(self.tasks.values())

        if list_name:
            tasks = [t for t in tasks if t.list_name == list_name.lower().strip()]

        if not show_completed:
            tasks = [t for t in tasks if not t.completed]

        # Sort by priority (high first), then by title
        priority_order = {"high": 0, "normal": 1, "low": 2}
        tasks.sort(key=lambda t: (priority_order.get(t.priority, 1), t.title))

        return ToolResult(
            success=True,
            value=[
                {
                    "id": t.id,
                    "title": t.title,
                    "list": t.list_name,
                    "priority": t.priority,
                    "completed": t.completed,
                }
                for t in tasks
            ],
        )

    def get_lists(self) -> ToolResult:
        """Get all list names.

        Returns:
            ToolResult with list of unique list names
        """
        lists = sorted(set(t.list_name for t in self.tasks.values()))
        if not lists:
            lists = ["default"]
        return ToolResult(success=True, value=lists)

    def set_priority(self, task_id: str, priority: str) -> ToolResult:
        """Set task priority.

        Args:
            task_id: The task ID
            priority: New priority (low, normal, high)

        Returns:
            ToolResult with updated task
        """
        if task_id not in self.tasks:
            return ToolResult(
                success=False,
                value=None,
                error=f"Task '{task_id}' not found",
            )

        if priority not in ("low", "normal", "high"):
            return ToolResult(
                success=False,
                value=None,
                error=f"Invalid priority '{priority}'. Must be: low, normal, high",
            )

        task = self.tasks[task_id]
        task.priority = priority

        return ToolResult(
            success=True,
            value={
                "id": task.id,
                "title": task.title,
                "priority": priority,
                "message": f"Set priority of '{task.title}' to {priority}",
            },
        )

    def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Dispatch a tool call by name."""
        tools = {
            "add_task": lambda args: self.add_task(
                args["title"],
                args.get("list", "default"),
                args.get("priority", "normal"),
            ),
            "complete_task": lambda args: self.complete_task(args["task_id"]),
            "uncomplete_task": lambda args: self.uncomplete_task(args["task_id"]),
            "delete_task": lambda args: self.delete_task(args["task_id"]),
            "list_tasks": lambda args: self.list_tasks(
                args.get("list"),
                args.get("show_completed", True),
            ),
            "get_lists": lambda _: self.get_lists(),
            "set_priority": lambda args: self.set_priority(args["task_id"], args["priority"]),
        }

        if name not in tools:
            return ToolResult(success=False, value=None, error=f"Unknown tool: {name}")

        try:
            return tools[name](arguments)
        except KeyError as e:
            return ToolResult(success=False, value=None, error=f"Missing argument: {e}")
        except Exception as e:
            return ToolResult(success=False, value=None, error=str(e))

    async def call_tool_async(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Async dispatch (all tools are sync for todo)."""
        return self.call_tool(name, arguments)

    @classmethod
    def get_tool_schemas(cls) -> list[dict[str, Any]]:
        """Return JSON schemas for all tools (for MCP)."""
        return [
            {
                "name": "add_task",
                "description": "Add a new task to a todo list. Use for adding items like 'buy milk' or 'call mom'.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "The task description (e.g., 'Buy groceries', 'Call dentist')",
                        },
                        "list": {
                            "type": "string",
                            "description": "Which list to add to (e.g., 'shopping', 'work', 'personal'). Default: 'default'",
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["low", "normal", "high"],
                            "description": "Task priority. Default: 'normal'",
                        },
                    },
                    "required": ["title"],
                },
            },
            {
                "name": "complete_task",
                "description": "Mark a task as completed/done.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "The ID of the task to complete",
                        },
                    },
                    "required": ["task_id"],
                },
            },
            {
                "name": "uncomplete_task",
                "description": "Mark a completed task as not done (reopen it).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "The ID of the task to reopen",
                        },
                    },
                    "required": ["task_id"],
                },
            },
            {
                "name": "delete_task",
                "description": "Delete/remove a task permanently.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "The ID of the task to delete",
                        },
                    },
                    "required": ["task_id"],
                },
            },
            {
                "name": "list_tasks",
                "description": "List all tasks, optionally filtered by list name or completion status.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "list": {
                            "type": "string",
                            "description": "Filter by list name (e.g., 'shopping'). Omit for all lists.",
                        },
                        "show_completed": {
                            "type": "boolean",
                            "description": "Include completed tasks? Default: true",
                        },
                    },
                },
            },
            {
                "name": "get_lists",
                "description": "Get all available todo list names.",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "set_priority",
                "description": "Change the priority of a task.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task_id": {
                            "type": "string",
                            "description": "The ID of the task",
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["low", "normal", "high"],
                            "description": "New priority level",
                        },
                    },
                    "required": ["task_id", "priority"],
                },
            },
        ]
