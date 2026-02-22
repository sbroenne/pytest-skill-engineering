"""Unit tests for MCP server process management.

These tests verify that MCP servers start correctly, tools are discovered,
and basic tool calls work - WITHOUT using LLM. This ensures the infrastructure
works before expensive integration tests.

Tests all three MCP transports: stdio, SSE, and streamable-http.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time

import pytest

from pytest_skill_engineering import MCPServer, Wait
from pytest_skill_engineering.execution.servers import MCPServerProcess

# ---------------------------------------------------------------------------
# Helper functions for HTTP transports
# ---------------------------------------------------------------------------


def _free_port() -> int:
    """Find a free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_port(port: int, host: str = "127.0.0.1", timeout: float = 10.0) -> None:
    """Block until host:port accepts a TCP connection or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return
        except OSError:
            time.sleep(0.2)
    msg = f"Server on {host}:{port} did not start within {timeout}s"
    raise TimeoutError(msg)


# ---------------------------------------------------------------------------
# stdio transport tests
# ---------------------------------------------------------------------------


class TestMCPServerStdio:
    """Test stdio transport for MCP servers."""

    @pytest.mark.asyncio
    async def test_todo_mcp_starts_and_lists_tools(self):
        """Todo MCP server (FastMCP) starts and discovers tools via stdio."""
        config = MCPServer(
            command=[sys.executable, "-u", "-m", "pytest_skill_engineering.testing.todo_mcp"],
            wait=Wait.for_tools(["add_task", "list_tasks", "complete_task"]),
        )
        server = MCPServerProcess(config)

        try:
            await server.start()
            tools = server.get_tools()

            # Verify all expected tools are present
            expected_tools = [
                "add_task",
                "complete_task",
                "uncomplete_task",
                "delete_task",
                "list_tasks",
                "get_lists",
                "set_priority",
            ]
            for tool_name in expected_tools:
                assert tool_name in tools, f"Tool {tool_name} not found"
                assert "description" in tools[tool_name]
                assert "inputSchema" in tools[tool_name]
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_banking_mcp_starts_and_lists_tools(self):
        """Banking MCP server (FastMCP) starts and discovers tools via stdio."""
        config = MCPServer(
            command=[sys.executable, "-u", "-m", "pytest_skill_engineering.testing.banking_mcp"],
            wait=Wait.for_tools(
                ["get_balance", "get_all_balances", "transfer", "deposit", "withdraw"]
            ),
        )
        server = MCPServerProcess(config)

        try:
            await server.start()
            tools = server.get_tools()

            # Verify all expected tools are present
            expected_tools = [
                "get_balance",
                "get_all_balances",
                "transfer",
                "deposit",
                "withdraw",
                "get_transactions",
            ]
            for tool_name in expected_tools:
                assert tool_name in tools, f"Tool {tool_name} not found"
                assert "description" in tools[tool_name]
                assert "inputSchema" in tools[tool_name]
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_todo_mcp_tool_call(self):
        """Can call tools on todo MCP server via stdio."""
        config = MCPServer(
            command=[sys.executable, "-u", "-m", "pytest_skill_engineering.testing.todo_mcp"],
            wait=Wait.for_tools(["add_task", "list_tasks"]),
        )
        server = MCPServerProcess(config)

        try:
            await server.start()

            # Add a task
            result = await server.call_tool("add_task", {"title": "Test task"})
            assert "Test task" in result or "message" in result.lower()

            # List tasks
            result = await server.call_tool("list_tasks", {})
            assert "Test task" in result or "[]" in result
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_banking_mcp_tool_call(self):
        """Can call tools on banking MCP server via stdio."""
        config = MCPServer(
            command=[sys.executable, "-u", "-m", "pytest_skill_engineering.testing.banking_mcp"],
            wait=Wait.for_tools(["get_balance"]),
        )
        server = MCPServerProcess(config)

        try:
            await server.start()

            # Get balance
            result = await server.call_tool("get_balance", {"account": "checking"})
            assert "balance" in result.lower() or "1500" in result or "1,500" in result
        finally:
            await server.stop()


# ---------------------------------------------------------------------------
# SSE transport tests
# ---------------------------------------------------------------------------


class TestMCPServerSSE:
    """Test SSE transport for MCP servers."""

    @pytest.mark.asyncio
    async def test_todo_mcp_sse_starts_and_lists_tools(self):
        """Todo MCP server starts and discovers tools via SSE."""
        port = _free_port()
        proc = subprocess.Popen(
            [
                sys.executable,
                "-u",
                "-m",
                "pytest_skill_engineering.testing.todo_mcp",
                "--transport",
                "sse",
                "--port",
                str(port),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            _wait_for_port(port)

            config = MCPServer(
                transport="sse",
                url=f"http://127.0.0.1:{port}/sse",
                wait=Wait.for_tools(["add_task", "list_tasks"]),
            )
            server = MCPServerProcess(config)

            await server.start()
            tools = server.get_tools()

            # Verify expected tools
            assert "add_task" in tools
            assert "list_tasks" in tools
            assert "complete_task" in tools

            await server.stop()
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    @pytest.mark.asyncio
    async def test_banking_mcp_sse_starts_and_lists_tools(self):
        """Banking MCP server starts and discovers tools via SSE."""
        port = _free_port()
        proc = subprocess.Popen(
            [
                sys.executable,
                "-u",
                "-m",
                "pytest_skill_engineering.testing.banking_mcp",
                "--transport",
                "sse",
                "--port",
                str(port),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            _wait_for_port(port)

            config = MCPServer(
                transport="sse",
                url=f"http://127.0.0.1:{port}/sse",
                wait=Wait.for_tools(["get_balance", "transfer"]),
            )
            server = MCPServerProcess(config)

            await server.start()
            tools = server.get_tools()

            # Verify expected tools
            assert "get_balance" in tools
            assert "transfer" in tools
            assert "get_all_balances" in tools

            await server.stop()
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    @pytest.mark.asyncio
    async def test_todo_mcp_sse_tool_call(self):
        """Can call tools on todo MCP server via SSE."""
        port = _free_port()
        proc = subprocess.Popen(
            [
                sys.executable,
                "-u",
                "-m",
                "pytest_skill_engineering.testing.todo_mcp",
                "--transport",
                "sse",
                "--port",
                str(port),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            _wait_for_port(port)

            config = MCPServer(
                transport="sse",
                url=f"http://127.0.0.1:{port}/sse",
                wait=Wait.for_tools(["add_task", "list_tasks"]),
            )
            server = MCPServerProcess(config)

            await server.start()

            # Add a task
            result = await server.call_tool("add_task", {"title": "SSE test task"})
            assert "SSE test task" in result or "message" in result.lower()

            await server.stop()
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    @pytest.mark.asyncio
    async def test_banking_mcp_sse_tool_call(self):
        """Can call tools on banking MCP server via SSE."""
        port = _free_port()
        proc = subprocess.Popen(
            [
                sys.executable,
                "-u",
                "-m",
                "pytest_skill_engineering.testing.banking_mcp",
                "--transport",
                "sse",
                "--port",
                str(port),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            _wait_for_port(port)

            config = MCPServer(
                transport="sse",
                url=f"http://127.0.0.1:{port}/sse",
                wait=Wait.for_tools(["get_balance"]),
            )
            server = MCPServerProcess(config)

            await server.start()

            # Get balance
            result = await server.call_tool("get_balance", {"account": "checking"})
            assert "balance" in result.lower() or "1500" in result or "1,500" in result

            await server.stop()
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


# ---------------------------------------------------------------------------
# Streamable HTTP transport tests
# ---------------------------------------------------------------------------


class TestMCPServerStreamableHTTP:
    """Test streamable-http transport for MCP servers."""

    @pytest.mark.asyncio
    async def test_todo_mcp_http_starts_and_lists_tools(self):
        """Todo MCP server starts and discovers tools via streamable-http."""
        port = _free_port()
        proc = subprocess.Popen(
            [
                sys.executable,
                "-u",
                "-m",
                "pytest_skill_engineering.testing.todo_mcp",
                "--transport",
                "streamable-http",
                "--port",
                str(port),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            _wait_for_port(port)

            config = MCPServer(
                transport="streamable-http",
                url=f"http://127.0.0.1:{port}/mcp",
                wait=Wait.for_tools(["add_task", "list_tasks"]),
            )
            server = MCPServerProcess(config)

            await server.start()
            tools = server.get_tools()

            # Verify expected tools
            assert "add_task" in tools
            assert "list_tasks" in tools
            assert "complete_task" in tools

            await server.stop()
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    @pytest.mark.asyncio
    async def test_banking_mcp_http_starts_and_lists_tools(self):
        """Banking MCP server starts and discovers tools via streamable-http."""
        port = _free_port()
        proc = subprocess.Popen(
            [
                sys.executable,
                "-u",
                "-m",
                "pytest_skill_engineering.testing.banking_mcp",
                "--transport",
                "streamable-http",
                "--port",
                str(port),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            _wait_for_port(port)

            config = MCPServer(
                transport="streamable-http",
                url=f"http://127.0.0.1:{port}/mcp",
                wait=Wait.for_tools(["get_balance", "transfer"]),
            )
            server = MCPServerProcess(config)

            await server.start()
            tools = server.get_tools()

            # Verify expected tools
            assert "get_balance" in tools
            assert "transfer" in tools
            assert "get_all_balances" in tools

            await server.stop()
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    @pytest.mark.asyncio
    async def test_todo_mcp_http_tool_call(self):
        """Can call tools on todo MCP server via streamable-http."""
        port = _free_port()
        proc = subprocess.Popen(
            [
                sys.executable,
                "-u",
                "-m",
                "pytest_skill_engineering.testing.todo_mcp",
                "--transport",
                "streamable-http",
                "--port",
                str(port),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            _wait_for_port(port)

            config = MCPServer(
                transport="streamable-http",
                url=f"http://127.0.0.1:{port}/mcp",
                wait=Wait.for_tools(["add_task", "list_tasks"]),
            )
            server = MCPServerProcess(config)

            await server.start()

            # Add a task
            result = await server.call_tool("add_task", {"title": "HTTP test task"})
            assert "HTTP test task" in result or "message" in result.lower()

            await server.stop()
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    @pytest.mark.asyncio
    async def test_banking_mcp_http_tool_call(self):
        """Can call tools on banking MCP server via streamable-http."""
        port = _free_port()
        proc = subprocess.Popen(
            [
                sys.executable,
                "-u",
                "-m",
                "pytest_skill_engineering.testing.banking_mcp",
                "--transport",
                "streamable-http",
                "--port",
                str(port),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            _wait_for_port(port)

            config = MCPServer(
                transport="streamable-http",
                url=f"http://127.0.0.1:{port}/mcp",
                wait=Wait.for_tools(["get_balance"]),
            )
            server = MCPServerProcess(config)

            await server.start()

            # Get balance
            result = await server.call_tool("get_balance", {"account": "checking"})
            assert "balance" in result.lower() or "1500" in result or "1,500" in result

            await server.stop()
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
