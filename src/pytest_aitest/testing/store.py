"""Shared test store backend for MCP and CLI servers.

Implements a key-value store with tools designed to require agent reasoning.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any


class StoreError(Exception):
    """Error from store operations."""


@dataclass
class ToolResult:
    """Result from a tool call."""

    success: bool
    value: Any
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        if self.success:
            return {"success": True, "result": self.value}
        return {"success": False, "error": self.error}


@dataclass
class KeyValueStore:
    """Key-value store with tools for agent reasoning tests.

    All tools are synchronous for simplicity. The servers handle async wrapping.
    """

    data: dict[str, str] = field(default_factory=dict)

    def get(self, key: str) -> ToolResult:
        """Get value for a key."""
        if key not in self.data:
            return ToolResult(success=False, value=None, error=f"Key '{key}' not found")
        return ToolResult(success=True, value=self.data[key])

    def set(self, key: str, value: str) -> ToolResult:
        """Set a key to a value."""
        self.data[key] = str(value)
        return ToolResult(success=True, value=f"Set '{key}' = '{value}'")

    def delete(self, key: str) -> ToolResult:
        """Delete a key."""
        if key not in self.data:
            return ToolResult(success=False, value=None, error=f"Key '{key}' not found")
        del self.data[key]
        return ToolResult(success=True, value=f"Deleted '{key}'")

    def list_keys(self) -> ToolResult:
        """List all keys in the store."""
        return ToolResult(success=True, value=list(self.data.keys()))

    def calculate(self, expression: str) -> ToolResult:
        """Evaluate a math expression safely.

        Supports: +, -, *, /, //, %, **, (, ), integers, floats
        """
        # Only allow safe characters
        if not re.match(r"^[\d\s+\-*/%().]+$", expression):
            return ToolResult(
                success=False,
                value=None,
                error=f"Invalid expression: '{expression}'. Only numbers and +,-,*,/,%,**,() allowed.",
            )
        try:
            # Use eval with restricted builtins
            result = eval(expression, {"__builtins__": {}}, {})  # noqa: S307
            return ToolResult(success=True, value=result)
        except Exception as e:
            return ToolResult(success=False, value=None, error=f"Calculation error: {e}")

    def compare(self, a: str, b: str) -> ToolResult:
        """Compare two values as numbers if possible, else as strings."""
        try:
            a_num = float(a)
            b_num = float(b)
            if a_num > b_num:
                return ToolResult(success=True, value="greater")
            elif a_num < b_num:
                return ToolResult(success=True, value="less")
            else:
                return ToolResult(success=True, value="equal")
        except ValueError:
            # Fall back to string comparison
            if a > b:
                return ToolResult(success=True, value="greater")
            elif a < b:
                return ToolResult(success=True, value="less")
            else:
                return ToolResult(success=True, value="equal")

    def search(self, pattern: str) -> ToolResult:
        """Find keys matching a regex pattern."""
        try:
            regex = re.compile(pattern)
            matches = [k for k in self.data.keys() if regex.search(k)]
            return ToolResult(success=True, value=matches)
        except re.error as e:
            return ToolResult(success=False, value=None, error=f"Invalid regex: {e}")

    def transform(self, key: str, operation: str) -> ToolResult:
        """Transform a value in place.

        Operations: uppercase, lowercase, reverse, length, trim
        """
        if key not in self.data:
            return ToolResult(success=False, value=None, error=f"Key '{key}' not found")

        value = self.data[key]
        operations = {
            "uppercase": lambda v: v.upper(),
            "lowercase": lambda v: v.lower(),
            "reverse": lambda v: v[::-1],
            "length": lambda v: str(len(v)),
            "trim": lambda v: v.strip(),
        }

        if operation not in operations:
            return ToolResult(
                success=False,
                value=None,
                error=f"Unknown operation: '{operation}'. Supported: {list(operations.keys())}",
            )

        new_value = operations[operation](value)
        self.data[key] = new_value
        return ToolResult(success=True, value=new_value)

    def fail(self, message: str) -> ToolResult:
        """Always fail with the given message. For testing error handling."""
        return ToolResult(success=False, value=None, error=message)

    async def slow(self, ms: int, message: str) -> ToolResult:
        """Return message after a delay. For testing timeouts."""
        await asyncio.sleep(ms / 1000)
        return ToolResult(success=True, value=message)

    def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Dispatch a tool call by name."""
        tools = {
            "get": lambda args: self.get(args["key"]),
            "set": lambda args: self.set(args["key"], args["value"]),
            "delete": lambda args: self.delete(args["key"]),
            "list_keys": lambda _: self.list_keys(),
            "calculate": lambda args: self.calculate(args["expression"]),
            "compare": lambda args: self.compare(args["a"], args["b"]),
            "search": lambda args: self.search(args["pattern"]),
            "transform": lambda args: self.transform(args["key"], args["operation"]),
            "fail": lambda args: self.fail(args["message"]),
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
        """Async dispatch for tools that need it (like slow)."""
        if name == "slow":
            return await self.slow(arguments.get("ms", 0), arguments.get("message", ""))
        return self.call_tool(name, arguments)

    @classmethod
    def get_tool_schemas(cls) -> list[dict[str, Any]]:
        """Return JSON schemas for all tools (for MCP)."""
        return [
            {
                "name": "get",
                "description": "Get the value stored at a key",
                "inputSchema": {
                    "type": "object",
                    "properties": {"key": {"type": "string", "description": "The key to retrieve"}},
                    "required": ["key"],
                },
            },
            {
                "name": "set",
                "description": "Store a value at a key",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "The key to set"},
                        "value": {
                            "type": "string",
                            "description": "The value to store",
                        },
                    },
                    "required": ["key", "value"],
                },
            },
            {
                "name": "delete",
                "description": "Delete a key from the store",
                "inputSchema": {
                    "type": "object",
                    "properties": {"key": {"type": "string", "description": "The key to delete"}},
                    "required": ["key"],
                },
            },
            {
                "name": "list_keys",
                "description": "List all keys in the store",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "calculate",
                "description": "Evaluate a mathematical expression. Supports +, -, *, /, %, **",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "Math expression like '2+3*4'",
                        }
                    },
                    "required": ["expression"],
                },
            },
            {
                "name": "compare",
                "description": "Compare two values. Returns 'greater', 'less', or 'equal'",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "string", "description": "First value"},
                        "b": {"type": "string", "description": "Second value"},
                    },
                    "required": ["a", "b"],
                },
            },
            {
                "name": "search",
                "description": "Find keys matching a regex pattern",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Regex pattern to match keys",
                        }
                    },
                    "required": ["pattern"],
                },
            },
            {
                "name": "transform",
                "description": "Transform a value. Operations: uppercase, lowercase, reverse, length, trim",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "Key to transform"},
                        "operation": {
                            "type": "string",
                            "enum": [
                                "uppercase",
                                "lowercase",
                                "reverse",
                                "length",
                                "trim",
                            ],
                            "description": "Transformation to apply",
                        },
                    },
                    "required": ["key", "operation"],
                },
            },
            {
                "name": "fail",
                "description": "Always fails with the given message. For testing error handling.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "Error message to return",
                        }
                    },
                    "required": ["message"],
                },
            },
            {
                "name": "slow",
                "description": "Returns a message after a delay. For testing timeouts.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "ms": {
                            "type": "integer",
                            "description": "Delay in milliseconds",
                        },
                        "message": {
                            "type": "string",
                            "description": "Message to return",
                        },
                    },
                    "required": ["ms", "message"],
                },
            },
        ]
