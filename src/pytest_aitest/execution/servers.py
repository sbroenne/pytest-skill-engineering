"""Server management for MCP and CLI servers."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sys
from typing import TYPE_CHECKING, Any

from pytest_aitest.core.errors import ServerStartError

if TYPE_CHECKING:
    from mcp import ClientSession

    from pytest_aitest.core.agent import CLIServer, MCPServer


class MCPServerProcess:
    """Manages an MCP server connection using the MCP SDK.

    Supports all three transports via the SDK's ``ClientSession``:

    - **stdio** — Launches a subprocess and communicates via stdin/stdout
    - **sse** — Connects to a remote SSE endpoint
    - **streamable-http** — Connects to a remote Streamable HTTP endpoint

    Example:
        server = MCPServerProcess(mcp_config)
        await server.start()
        tools = server.get_tools()
        result = await server.call_tool("read_file", {"path": "foo.txt"})
        await server.stop()
    """

    def __init__(self, config: MCPServer) -> None:
        self.config = config
        self._session: ClientSession | None = None
        self._tools: dict[str, dict[str, Any]] = {}
        self._exit_stack: contextlib.AsyncExitStack | None = None

    async def start(self) -> None:
        """Start or connect to the MCP server and discover tools."""
        from mcp import ClientSession as _ClientSession

        from pytest_aitest.core.agent import WaitStrategy

        self._exit_stack = contextlib.AsyncExitStack()
        label = self._transport_label()

        try:
            read_stream, write_stream = await self._open_transport()

            self._session = await self._exit_stack.enter_async_context(
                _ClientSession(read_stream, write_stream)
            )
            await self._session.initialize()

            # Discover tools
            tools_result = await self._session.list_tools()
            for tool in tools_result.tools:
                self._tools[tool.name] = {
                    "name": tool.name,
                    "description": tool.description or "",
                    "inputSchema": tool.inputSchema,
                }

            # Check tools if wait strategy requires it
            if self.config.wait.strategy == WaitStrategy.TOOLS and self.config.wait.tools:
                missing = set(self.config.wait.tools) - set(self._tools.keys())
                if missing:
                    raise ServerStartError("MCP", label, f"Required tools not available: {missing}")

        except ServerStartError:
            raise
        except Exception as e:
            if self._exit_stack:
                await self._exit_stack.aclose()
                self._exit_stack = None
            raise ServerStartError("MCP", label, str(e)) from e

    async def _open_transport(self) -> tuple[Any, Any]:
        """Open the appropriate transport and return (read_stream, write_stream)."""
        assert self._exit_stack is not None  # noqa: S101

        match self.config.transport:
            case "stdio":
                from mcp.client.stdio import StdioServerParameters, stdio_client

                cmd = self.config.command
                params = StdioServerParameters(
                    command=cmd[0],
                    args=[*cmd[1:], *self.config.args],
                    env={**os.environ, **self.config.env} if self.config.env else None,
                    cwd=self.config.cwd,
                )
                streams = await self._exit_stack.enter_async_context(stdio_client(params))
                return streams[0], streams[1]

            case "sse":
                from mcp.client.sse import sse_client

                url = self.config.url
                assert url is not None  # noqa: S101 — validated in MCPServer.__post_init__
                streams = await self._exit_stack.enter_async_context(
                    sse_client(url, headers=self.config.headers or None)
                )
                return streams[0], streams[1]

            case "streamable-http":
                import httpx
                from mcp.client.streamable_http import streamable_http_client

                url = self.config.url
                assert url is not None  # noqa: S101 — validated in MCPServer.__post_init__

                http_client: httpx.AsyncClient | None = None
                if self.config.headers:
                    http_client = await self._exit_stack.enter_async_context(
                        httpx.AsyncClient(headers=self.config.headers)
                    )

                streams = await self._exit_stack.enter_async_context(
                    streamable_http_client(url, http_client=http_client)
                )
                return streams[0], streams[1]

            case _:
                msg = f"Unknown transport: {self.config.transport}"
                raise ValueError(msg)

    async def stop(self) -> None:
        """Stop the MCP server / disconnect from remote."""
        if self._exit_stack:
            await self._exit_stack.aclose()
            self._exit_stack = None
        self._session = None

    def get_tools(self) -> dict[str, dict[str, Any]]:
        """Get available tools."""
        return self._tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Call a tool and return result as text."""
        if not self._session:
            raise RuntimeError("Server not started")

        from mcp import types

        result = await self._session.call_tool(name, arguments)

        # Extract text from content blocks
        if result.content:
            for block in result.content:
                if isinstance(block, types.TextContent):
                    return block.text
            return str(result.content[0])
        return ""

    def _transport_label(self) -> list[str]:
        """Human-readable label for error messages."""
        if self.config.transport == "stdio":
            return self.config.command + self.config.args
        return [self.config.transport, self.config.url or ""]


class CLIServerProcess:
    """Manages a CLI command wrapped as an MCP-like tool.

    Wraps a single CLI command and exposes it as a tool that accepts
    an `args` parameter. Optionally discovers help text to improve
    the tool description.

    Example:
        server = CLIServerProcess(cli_config)
        await server.start()  # Discovers help if enabled
        tools = server.get_tools()  # Returns {prefix}_execute tool
        result = await server.call_tool("git_execute", {"args": "status"})
        await server.stop()
    """

    def __init__(self, config: CLIServer) -> None:
        self.config = config
        self._env = {**os.environ, **config.env}
        self._tool_name = f"{config.tool_prefix}_execute"
        self._help_text: str | None = None
        self._executions: list[dict[str, Any]] = []

        # Determine shell
        if config.shell:
            self._shell = config.shell
        elif sys.platform == "win32":
            self._shell = "powershell"
        else:
            self._shell = "bash"

    async def start(self) -> None:
        """Initialize the CLI server and discover help if enabled."""
        if self.config.discover_help:
            self._help_text = await self._discover_help()

    async def stop(self) -> None:
        """Stop the CLI server (clears execution history)."""
        self._executions = []

    async def _discover_help(self) -> str | None:
        """Run command with help flag to get tool description."""
        try:
            result = await self._run_command(self.config.help_flag)
            if result["exit_code"] == 0 and result["stdout"]:
                # Truncate help text to avoid token bloat
                help_text = result["stdout"]
                if len(help_text) > 2000:
                    help_text = help_text[:2000] + "\n... (truncated)"
                return help_text
        except (TimeoutError, OSError):
            # Help discovery is optional - if it fails, just skip it
            return None
        return None

    async def _run_command(self, args: str) -> dict[str, Any]:
        """Execute the CLI command with given arguments."""
        import shlex
        import time

        start_time = time.perf_counter()

        full_cmd = self.config.command
        if args:
            full_cmd = f"{full_cmd} {args}"

        # Build shell command
        if self._shell == "none":
            # Direct execution: no shell wrapper.
            # Split base command and args separately:
            # - Base command: use posix=False on Windows to preserve backslashes
            #   in paths (posix=True treats backslash as escape character).
            # - Args: always use posix=True to properly handle quoted strings
            #   (e.g., JSON arrays like "[1,2,3]").
            base_parts = shlex.split(self.config.command, posix=(sys.platform != "win32"))
            if args:
                base_parts.extend(shlex.split(args, posix=True))
            cmd = base_parts
        elif self._shell in ("powershell", "pwsh"):
            shell_exe = "powershell" if self._shell == "powershell" else "pwsh"
            cmd = [shell_exe, "-NoProfile", "-NonInteractive", "-Command", full_cmd]
        elif self._shell == "cmd":
            cmd = ["cmd", "/C", full_cmd]
        else:
            # bash, sh, zsh
            cmd = [self._shell, "-c", full_cmd]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._env,
                cwd=self.config.cwd,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)

            duration_ms = int((time.perf_counter() - start_time) * 1000)

            execution = {
                "command": self.config.command,
                "args": args,
                "full_cmd": full_cmd,
                "exit_code": proc.returncode or 0,
                "stdout": stdout.decode() if stdout else "",
                "stderr": stderr.decode() if stderr else "",
                "duration_ms": duration_ms,
            }

            self._executions.append(execution)
            return execution

        except TimeoutError:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            execution = {
                "command": self.config.command,
                "args": args,
                "full_cmd": full_cmd,
                "exit_code": -1,
                "stdout": "",
                "stderr": "Error: Command timed out after 30 seconds",
                "duration_ms": duration_ms,
            }
            self._executions.append(execution)
            return execution

        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            execution = {
                "command": self.config.command,
                "args": args,
                "full_cmd": full_cmd,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Error: {e}",
                "duration_ms": duration_ms,
            }
            self._executions.append(execution)
            return execution

    def get_tools(self) -> dict[str, dict[str, Any]]:
        """Get available tools as MCP-compatible schema."""
        # Priority: custom description > discovered help > default
        cmd = self.config.command
        if self.config.description:
            description = f"Execute {cmd} CLI command.\n\n{self.config.description}"
        elif self._help_text:
            description = f"Execute {cmd} CLI command.\n\nHelp:\n{self._help_text}"
        else:
            description = f"Execute {cmd} CLI command with arguments."

        args_desc = f"Command-line arguments to pass to {cmd}"
        return {
            self._tool_name: {
                "name": self._tool_name,
                "description": description,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "args": {
                            "type": "string",
                            "description": args_desc,
                        }
                    },
                    "required": [],
                },
            }
        }

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Execute a CLI tool and return JSON result with exit_code, stdout, stderr."""
        if name != self._tool_name:
            raise ValueError(f"Unknown tool: {name}")

        args = arguments.get("args", "")
        execution = await self._run_command(args)

        # Return JSON result like agent-benchmark
        return json.dumps(
            {
                "exit_code": execution["exit_code"],
                "stdout": execution["stdout"],
                "stderr": execution["stderr"],
            }
        )

    def get_executions(self) -> list[dict[str, Any]]:
        """Get all recorded command executions for assertions."""
        return self._executions


class ServerManager:
    """Manages all servers for an agent.

    Example:
        manager = ServerManager(mcp_servers=[...], cli_servers=[...])
        await manager.start_all()
        tools = await manager.get_tools_schema()
        result = await manager.call_tool("read_file", {"path": "foo.txt"})
        await manager.stop_all()
    """

    def __init__(
        self,
        mcp_servers: list[MCPServer],
        cli_servers: list[CLIServer],
    ) -> None:
        self._mcp_servers = [MCPServerProcess(cfg) for cfg in mcp_servers]
        self._cli_servers = [CLIServerProcess(cfg) for cfg in cli_servers]
        self._tool_to_mcp_server: dict[str, MCPServerProcess] = {}
        self._tool_to_cli_server: dict[str, CLIServerProcess] = {}

    async def start_all(self) -> None:
        """Start all servers."""
        # Start all MCP servers
        for server in self._mcp_servers:
            await server.start()
            for tool_name in server.get_tools():
                self._tool_to_mcp_server[tool_name] = server

        # Start all CLI servers
        for server in self._cli_servers:
            await server.start()
            for tool_name in server.get_tools():
                self._tool_to_cli_server[tool_name] = server

    async def stop_all(self) -> None:
        """Stop all servers."""
        for server in self._mcp_servers:
            await server.stop()
        for server in self._cli_servers:
            await server.stop()

    async def get_tools_schema(self) -> list[dict[str, Any]]:
        """Get OpenAI-compatible tools schema for all servers."""
        tools = []

        # MCP server tools
        for server in self._mcp_servers:
            for name, tool_def in server.get_tools().items():
                tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": name,
                            "description": tool_def.get("description", ""),
                            "parameters": tool_def.get(
                                "inputSchema", {"type": "object", "properties": {}}
                            ),
                        },
                    }
                )

        # CLI server tools
        for server in self._cli_servers:
            for name, tool_def in server.get_tools().items():
                tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": name,
                            "description": tool_def.get("description", ""),
                            "parameters": tool_def.get(
                                "inputSchema", {"type": "object", "properties": {}}
                            ),
                        },
                    }
                )

        return tools

    def get_tools_info(self) -> list:
        """Get ToolInfo for all tools across all servers.

        Returns:
            List of ToolInfo objects with metadata for AI analysis.
        """
        from pytest_aitest.core.result import ToolInfo

        tools_info = []

        # MCP server tools
        for server in self._mcp_servers:
            cfg = server.config
            if cfg.transport == "stdio":
                server_name = getattr(cfg, "name", None) or cfg.command[-1]
            else:
                server_name = getattr(cfg, "name", None) or cfg.url or cfg.transport
            for name, tool_def in server.get_tools().items():
                tools_info.append(
                    ToolInfo(
                        name=name,
                        description=tool_def.get("description", ""),
                        input_schema=tool_def.get(
                            "inputSchema", {"type": "object", "properties": {}}
                        ),
                        server_name=server_name,
                    )
                )

        # CLI server tools
        for server in self._cli_servers:
            server_name = getattr(server.config, "name", None) or server.config.command[0]
            for name, tool_def in server.get_tools().items():
                tools_info.append(
                    ToolInfo(
                        name=name,
                        description=tool_def.get("description", ""),
                        input_schema=tool_def.get(
                            "inputSchema", {"type": "object", "properties": {}}
                        ),
                        server_name=server_name,
                    )
                )

        return tools_info

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Call a tool by name."""
        # Check MCP servers first
        if name in self._tool_to_mcp_server:
            return await self._tool_to_mcp_server[name].call_tool(name, arguments)

        # Check CLI servers
        if name in self._tool_to_cli_server:
            return await self._tool_to_cli_server[name].call_tool(name, arguments)

        raise ValueError(f"Unknown tool: {name}")
