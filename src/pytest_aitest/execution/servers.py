"""Server management for MCP and CLI servers."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
import sys
from typing import TYPE_CHECKING, Any

from pytest_aitest.core.errors import ServerStartError

if TYPE_CHECKING:
    from pytest_aitest.core.agent import CLIServer, MCPServer


class MCPServerProcess:
    """Manages a single MCP server process.

    Example:
        server = MCPServerProcess(mcp_config)
        await server.start()
        tools = server.get_tools()
        result = await server.call_tool("read_file", {"path": "foo.txt"})
        await server.stop()
    """

    def __init__(self, config: MCPServer) -> None:
        self.config = config
        self._process: asyncio.subprocess.Process | None = None
        self._tools: dict[str, dict[str, Any]] = {}
        self._reader_task: asyncio.Task[None] | None = None
        self._pending_requests: dict[int, asyncio.Future[Any]] = {}
        self._request_id = 0

    async def start(self) -> None:
        """Start the MCP server process."""
        from pytest_aitest.core.agent import WaitStrategy

        env = {**os.environ, **self.config.env}
        cmd = self.config.command + self.config.args

        try:
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=self.config.cwd,
            )
        except (OSError, FileNotFoundError) as e:
            raise ServerStartError("MCP", cmd, str(e)) from e

        # Start background reader
        self._reader_task = asyncio.create_task(self._read_responses())

        # Wait for server to be ready based on wait strategy
        await self._wait_for_ready()

        # Initialize and get tools
        await self._initialize()
        await self._list_tools()

        # Check tools if wait strategy requires it
        if self.config.wait.strategy == WaitStrategy.TOOLS and self.config.wait.tools:
            missing = set(self.config.wait.tools) - set(self._tools.keys())
            if missing:
                raise ServerStartError("MCP", cmd, f"Required tools not available: {missing}")

    async def stop(self) -> None:
        """Stop the MCP server process."""
        if self._reader_task:
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reader_task

        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except TimeoutError:
                self._process.kill()

    async def _wait_for_ready(self) -> None:
        """Wait for server to be ready based on wait strategy."""
        from pytest_aitest.core.agent import WaitStrategy

        wait = self.config.wait
        timeout_s = wait.timeout_ms / 1000

        match wait.strategy:
            case WaitStrategy.READY:
                # Just wait a brief moment for process to start
                await asyncio.sleep(0.1)

            case WaitStrategy.LOG:
                if wait.pattern and self._process and self._process.stderr:
                    pattern = re.compile(wait.pattern)
                    async with asyncio.timeout(timeout_s):
                        while True:
                            line = await self._process.stderr.readline()
                            if not line:
                                break
                            if pattern.search(line.decode()):
                                break

            case WaitStrategy.TOOLS:
                # Tools will be checked after initialization
                pass

    async def _read_responses(self) -> None:
        """Background task to read JSON-RPC responses."""
        if not self._process or not self._process.stdout:
            return

        buffer = b""
        while True:
            try:
                chunk = await self._process.stdout.read(4096)
                if not chunk:
                    break
                buffer += chunk

                # Try to parse complete JSON messages
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if not line.strip():
                        continue
                    try:
                        msg = json.loads(line)
                        if "id" in msg and msg["id"] in self._pending_requests:
                            future = self._pending_requests.pop(msg["id"])
                            if "error" in msg:
                                future.set_exception(
                                    Exception(msg["error"].get("message", "Unknown error"))
                                )
                            else:
                                future.set_result(msg.get("result"))
                    except json.JSONDecodeError:
                        continue
            except asyncio.CancelledError:
                break

    async def _send_request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """Send a JSON-RPC request and wait for response."""
        if not self._process or not self._process.stdin:
            raise RuntimeError("Server not started")

        self._request_id += 1
        request_id = self._request_id

        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params:
            request["params"] = params

        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._pending_requests[request_id] = future

        data = json.dumps(request) + "\n"
        self._process.stdin.write(data.encode())
        await self._process.stdin.drain()

        return await asyncio.wait_for(future, timeout=30.0)

    async def _send_notification(self, method: str, params: dict[str, Any] | None = None) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        if not self._process or not self._process.stdin:
            raise RuntimeError("Server not started")

        notification: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params:
            notification["params"] = params

        data = json.dumps(notification) + "\n"
        self._process.stdin.write(data.encode())
        await self._process.stdin.drain()

    async def _initialize(self) -> None:
        """Send MCP initialize request."""
        await self._send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "pytest-aitest", "version": "0.1.0"},
            },
        )
        await self._send_notification("notifications/initialized")

    async def _list_tools(self) -> None:
        """Get available tools from server."""
        result = await self._send_request("tools/list")
        for tool in result.get("tools", []):
            self._tools[tool["name"]] = tool

    def get_tools(self) -> dict[str, dict[str, Any]]:
        """Get available tools."""
        return self._tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Call a tool and return result."""
        result = await self._send_request(
            "tools/call",
            {
                "name": name,
                "arguments": arguments,
            },
        )
        # MCP returns content array
        content = result.get("content", [])
        if content and isinstance(content, list):
            return content[0].get("text", str(content[0]))
        return str(result)


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
            # Uses shlex.split to parse the command string into proper arguments,
            # preserving quoted strings (e.g., JSON arrays with double quotes).
            # This avoids shell-specific quoting issues (PowerShell strips inner
            # double quotes when passing to native commands).
            cmd = shlex.split(full_cmd, posix=True)
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
            server_name = getattr(server.config, "name", None) or server.config.command[-1]
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
