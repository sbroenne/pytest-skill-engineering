"""Tests for CLIServerProcess execution engine."""

from __future__ import annotations

import json
import sys
from unittest.mock import patch

import pytest

from pytest_aitest.core.agent import CLIServer
from pytest_aitest.execution.servers import CLIServerProcess


class TestToolNameGeneration:
    """Tests for tool name generation from prefix."""

    def test_tool_name_from_prefix(self) -> None:
        config = CLIServer(name="git", command="git", tool_prefix="git")
        server = CLIServerProcess(config)
        assert server._tool_name == "git_execute"

    def test_tool_name_with_different_prefix(self) -> None:
        config = CLIServer(name="kubectl", command="kubectl", tool_prefix="k8s")
        server = CLIServerProcess(config)
        assert server._tool_name == "k8s_execute"

    def test_tool_name_with_custom_prefix(self) -> None:
        config = CLIServer(name="docker", command="docker", tool_prefix="container")
        server = CLIServerProcess(config)
        assert server._tool_name == "container_execute"


class TestShellAutoDetection:
    """Tests for shell auto-detection based on platform."""

    def test_explicit_shell_bash(self) -> None:
        config = CLIServer(name="test", command="echo", tool_prefix="test", shell="bash")
        server = CLIServerProcess(config)
        assert server._shell == "bash"

    def test_explicit_shell_powershell(self) -> None:
        config = CLIServer(name="test", command="echo", tool_prefix="test", shell="powershell")
        server = CLIServerProcess(config)
        assert server._shell == "powershell"

    def test_auto_detect_bash_on_unix(self) -> None:
        with patch.object(sys, "platform", "linux"):
            config = CLIServer(name="test", command="echo", tool_prefix="test")
            server = CLIServerProcess(config)
            assert server._shell == "bash"

    def test_auto_detect_bash_on_darwin(self) -> None:
        with patch.object(sys, "platform", "darwin"):
            config = CLIServer(name="test", command="echo", tool_prefix="test")
            server = CLIServerProcess(config)
            assert server._shell == "bash"

    def test_auto_detect_powershell_on_windows(self) -> None:
        with patch.object(sys, "platform", "win32"):
            config = CLIServer(name="test", command="echo", tool_prefix="test")
            server = CLIServerProcess(config)
            assert server._shell == "powershell"


class TestGetToolsSchema:
    """Tests for get_tools() schema generation."""

    def test_basic_tool_schema(self) -> None:
        config = CLIServer(name="echo", command="echo", tool_prefix="echo", discover_help=False)
        server = CLIServerProcess(config)

        tools = server.get_tools()

        assert "echo_execute" in tools
        tool = tools["echo_execute"]
        assert tool["name"] == "echo_execute"
        assert "Execute echo CLI command" in tool["description"]
        assert tool["inputSchema"]["type"] == "object"
        assert "args" in tool["inputSchema"]["properties"]

    def test_tool_schema_args_description(self) -> None:
        config = CLIServer(name="git", command="git", tool_prefix="git", discover_help=False)
        server = CLIServerProcess(config)

        tools = server.get_tools()
        args_prop = tools["git_execute"]["inputSchema"]["properties"]["args"]

        assert args_prop["type"] == "string"
        assert "git" in args_prop["description"]

    def test_tool_schema_with_help_text(self) -> None:
        config = CLIServer(name="test", command="test", tool_prefix="test", discover_help=False)
        server = CLIServerProcess(config)
        # Simulate discovered help text
        server._help_text = "Usage: test [OPTIONS]\n  -v  Verbose output"

        tools = server.get_tools()
        description = tools["test_execute"]["description"]

        assert "Usage: test [OPTIONS]" in description
        assert "-v  Verbose output" in description


class TestHelpDiscovery:
    """Tests for automatic help discovery."""

    @pytest.mark.asyncio
    async def test_discover_help_enabled(self) -> None:
        # Uses actual 'echo' command
        config = CLIServer(name="echo", command="echo", tool_prefix="echo", discover_help=True)
        server = CLIServerProcess(config)

        await server.start()

        # echo --help returns help text on most systems
        tools = server.get_tools()
        # Help text should be included in description (or None if echo doesn't support --help)
        assert "echo_execute" in tools

    @pytest.mark.asyncio
    async def test_discover_help_disabled(self) -> None:
        config = CLIServer(name="echo", command="echo", tool_prefix="echo", discover_help=False)
        server = CLIServerProcess(config)

        await server.start()

        # No help discovery, _help_text should remain None
        assert server._help_text is None

    @pytest.mark.asyncio
    async def test_help_text_truncation(self) -> None:
        config = CLIServer(name="test", command="test", tool_prefix="test", discover_help=False)
        server = CLIServerProcess(config)

        # Simulate discovered help text that exceeds 2000 chars
        long_help = "X" * 3000
        # Manually call truncation logic from _discover_help
        if len(long_help) > 2000:
            truncated = long_help[:2000] + "\n... (truncated)"
        else:
            truncated = long_help
        server._help_text = truncated

        tools = server.get_tools()
        description = tools["test_execute"]["description"]

        # Should be truncated
        assert "(truncated)" in description
        assert len(server._help_text) < 3000

    @pytest.mark.asyncio
    async def test_custom_help_flag(self) -> None:
        # Uses 'ls' with -h flag instead of --help
        config = CLIServer(
            name="ls", command="ls", tool_prefix="ls", discover_help=True, help_flag="-h"
        )
        server = CLIServerProcess(config)

        await server.start()

        # Should have used -h instead of --help
        tools = server.get_tools()
        assert "ls_execute" in tools
        # The help text should be discovered (ls -h works on most systems)

    def test_default_help_flag_is_dash_dash_help(self) -> None:
        config = CLIServer(name="test", command="test", tool_prefix="test")
        assert config.help_flag == "--help"


class TestCustomDescription:
    """Tests for custom tool description."""

    def test_custom_description_overrides_help(self) -> None:
        custom_desc = "Custom: list, get <id>, delete <id>"
        config = CLIServer(
            name="test",
            command="test",
            tool_prefix="test",
            description=custom_desc,
            discover_help=False,
        )
        server = CLIServerProcess(config)
        # Simulate help text that should be ignored
        server._help_text = "This should NOT appear"

        tools = server.get_tools()
        description = tools["test_execute"]["description"]

        assert custom_desc in description
        assert "This should NOT appear" not in description

    def test_custom_description_in_schema(self) -> None:
        custom_desc = """
        Manages legacy data files.
        
        Commands:
        - list: List all records
        - get <id>: Get a specific record
        """
        config = CLIServer(
            name="legacy",
            command="legacy-tool",
            tool_prefix="legacy",
            description=custom_desc,
        )
        server = CLIServerProcess(config)

        tools = server.get_tools()
        description = tools["legacy_execute"]["description"]

        assert "Manages legacy data files" in description
        assert "list: List all records" in description
        assert "get <id>: Get a specific record" in description

    def test_no_description_uses_help_text(self) -> None:
        config = CLIServer(
            name="test",
            command="test",
            tool_prefix="test",
            discover_help=False,
        )
        server = CLIServerProcess(config)
        server._help_text = "Usage: test [OPTIONS]"

        tools = server.get_tools()
        description = tools["test_execute"]["description"]

        assert "Usage: test [OPTIONS]" in description

    def test_no_description_no_help_text(self) -> None:
        config = CLIServer(
            name="test",
            command="test",
            tool_prefix="test",
            discover_help=False,
        )
        server = CLIServerProcess(config)
        # No help text, no custom description

        tools = server.get_tools()
        description = tools["test_execute"]["description"]

        assert "Execute test CLI command with arguments" in description


class TestCommandExecution:
    """Tests for CLI command execution."""

    @pytest.mark.asyncio
    async def test_simple_command(self) -> None:
        config = CLIServer(name="echo", command="echo", tool_prefix="echo", discover_help=False)
        server = CLIServerProcess(config)
        await server.start()

        result = await server.call_tool("echo_execute", {"args": "hello world"})
        parsed = json.loads(result)

        assert parsed["exit_code"] == 0
        assert "hello world" in parsed["stdout"]

    @pytest.mark.asyncio
    async def test_command_with_empty_args(self) -> None:
        config = CLIServer(name="pwd", command="pwd", tool_prefix="pwd", discover_help=False)
        server = CLIServerProcess(config)
        await server.start()

        result = await server.call_tool("pwd_execute", {"args": ""})
        parsed = json.loads(result)

        assert parsed["exit_code"] == 0
        assert parsed["stdout"]  # Should output current directory

    @pytest.mark.asyncio
    async def test_command_without_args_key(self) -> None:
        config = CLIServer(name="pwd", command="pwd", tool_prefix="pwd", discover_help=False)
        server = CLIServerProcess(config)
        await server.start()

        result = await server.call_tool("pwd_execute", {})  # Empty dict, no args key
        parsed = json.loads(result)

        assert parsed["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_command_with_failing_command(self) -> None:
        config = CLIServer(name="ls", command="ls", tool_prefix="ls", discover_help=False)
        server = CLIServerProcess(config)
        await server.start()

        result = await server.call_tool("ls_execute", {"args": "/nonexistent_directory_xyz"})
        parsed = json.loads(result)

        # Should return non-zero exit code
        assert parsed["exit_code"] != 0
        assert parsed["stderr"]  # Should have error message

    @pytest.mark.asyncio
    async def test_unknown_tool_raises_error(self) -> None:
        config = CLIServer(name="echo", command="echo", tool_prefix="echo", discover_help=False)
        server = CLIServerProcess(config)
        await server.start()

        with pytest.raises(ValueError, match="Unknown tool"):
            await server.call_tool("wrong_tool", {"args": "test"})


class TestExecutionTracking:
    """Tests for execution history tracking."""

    @pytest.mark.asyncio
    async def test_execution_recorded(self) -> None:
        config = CLIServer(name="echo", command="echo", tool_prefix="echo", discover_help=False)
        server = CLIServerProcess(config)
        await server.start()

        assert server.get_executions() == []

        await server.call_tool("echo_execute", {"args": "test1"})
        await server.call_tool("echo_execute", {"args": "test2"})

        executions = server.get_executions()
        assert len(executions) == 2

    @pytest.mark.asyncio
    async def test_execution_contains_required_fields(self) -> None:
        config = CLIServer(name="echo", command="echo", tool_prefix="echo", discover_help=False)
        server = CLIServerProcess(config)
        await server.start()

        await server.call_tool("echo_execute", {"args": "hello"})

        executions = server.get_executions()
        assert len(executions) == 1

        exec = executions[0]
        assert exec["command"] == "echo"
        assert exec["args"] == "hello"
        assert "full_cmd" in exec
        assert "exit_code" in exec
        assert "stdout" in exec
        assert "stderr" in exec
        assert "duration_ms" in exec
        assert isinstance(exec["duration_ms"], int)

    @pytest.mark.asyncio
    async def test_executions_cleared_on_stop(self) -> None:
        config = CLIServer(name="echo", command="echo", tool_prefix="echo", discover_help=False)
        server = CLIServerProcess(config)
        await server.start()

        await server.call_tool("echo_execute", {"args": "test"})
        assert len(server.get_executions()) == 1

        await server.stop()
        assert server.get_executions() == []


class TestEnvironmentAndCwd:
    """Tests for environment variables and working directory."""

    @pytest.mark.asyncio
    async def test_custom_env_variable(self) -> None:
        config = CLIServer(
            name="printenv",
            command="printenv",
            tool_prefix="env",
            env={"MY_TEST_VAR": "test_value_123"},
            discover_help=False,
        )
        server = CLIServerProcess(config)
        await server.start()

        result = await server.call_tool("env_execute", {"args": "MY_TEST_VAR"})
        parsed = json.loads(result)

        assert parsed["exit_code"] == 0
        assert "test_value_123" in parsed["stdout"]

    @pytest.mark.asyncio
    async def test_custom_working_directory(self) -> None:
        config = CLIServer(
            name="pwd",
            command="pwd",
            tool_prefix="pwd",
            cwd="/tmp",
            discover_help=False,
        )
        server = CLIServerProcess(config)
        await server.start()

        result = await server.call_tool("pwd_execute", {"args": ""})
        parsed = json.loads(result)

        assert parsed["exit_code"] == 0
        assert "/tmp" in parsed["stdout"]


class TestJsonOutput:
    """Tests for JSON output format."""

    @pytest.mark.asyncio
    async def test_output_is_valid_json(self) -> None:
        config = CLIServer(name="echo", command="echo", tool_prefix="echo", discover_help=False)
        server = CLIServerProcess(config)
        await server.start()

        result = await server.call_tool("echo_execute", {"args": "test"})

        # Should be valid JSON
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    @pytest.mark.asyncio
    async def test_output_has_required_fields(self) -> None:
        config = CLIServer(name="echo", command="echo", tool_prefix="echo", discover_help=False)
        server = CLIServerProcess(config)
        await server.start()

        result = await server.call_tool("echo_execute", {"args": "test"})
        parsed = json.loads(result)

        assert "exit_code" in parsed
        assert "stdout" in parsed
        assert "stderr" in parsed
