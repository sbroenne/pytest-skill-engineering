"""Custom PydanticAI toolset wrapping CLI servers.

PydanticAI has no built-in CLI server support, so we build a custom
AbstractToolset that wraps our CLIServerProcess.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_ai.mcp import TOOL_SCHEMA_VALIDATOR
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets import AbstractToolset, ToolsetTool

from pytest_skill_engineering.execution.servers import CLIServerProcess

if TYPE_CHECKING:
    from pydantic_ai.tools import RunContext

    from pytest_skill_engineering.core.eval import CLIServer


class CLIToolset(AbstractToolset[Any]):
    """PydanticAI toolset that wraps CLI servers as callable tools."""

    def __init__(self, cli_servers: list[CLIServer], max_retries: int = 1) -> None:
        self._processes = [CLIServerProcess(cfg) for cfg in cli_servers]
        self._tool_to_process: dict[str, CLIServerProcess] = {}
        self._max_retries = max_retries

    @property
    def id(self) -> str | None:
        return "cli-toolset"

    async def __aenter__(self) -> CLIToolset:
        """Start all CLI server processes."""
        started: list[CLIServerProcess] = []
        try:
            for process in self._processes:
                await process.start()
                started.append(process)
                for tool_name in process.get_tools():
                    self._tool_to_process[tool_name] = process
        except Exception:
            for process in started:
                await process.stop()
            raise
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Stop all CLI server processes."""
        for process in self._processes:
            await process.stop()

    async def get_tools(self, ctx: RunContext[Any]) -> dict[str, ToolsetTool[Any]]:
        """Return tool definitions for all CLI servers."""
        tools: dict[str, ToolsetTool[Any]] = {}
        for process in self._processes:
            for name, tool_def in process.get_tools().items():
                tools[name] = ToolsetTool(
                    toolset=self,
                    tool_def=ToolDefinition(
                        name=name,
                        description=tool_def.get("description", ""),
                        parameters_json_schema=tool_def.get(
                            "inputSchema", {"type": "object", "properties": {}}
                        ),
                    ),
                    max_retries=self._max_retries,
                    args_validator=TOOL_SCHEMA_VALIDATOR,
                )
        return tools

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: RunContext[Any],
        tool: ToolsetTool[Any],
    ) -> str:
        """Execute a CLI tool and return the result."""
        if name not in self._tool_to_process:
            raise ValueError(f"Unknown CLI tool: {name}")
        return await self._tool_to_process[name].call_tool(name, tool_args)
