"""Unit tests for execution server configuration and process wrappers."""

from __future__ import annotations

import contextlib
import json
import shlex
import shutil
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace
from typing import Any, AsyncIterator, Iterator, Literal, cast
from uuid import uuid4

import pytest
from mcp import types

from pytest_skill_engineering.core.errors import ServerStartError
from pytest_skill_engineering.core.result import MCPPrompt
from pytest_skill_engineering.execution.servers import (
    CLIServer,
    CLIServerProcess,
    MCPServer,
    MCPServerProcess,
    Wait,
    WaitStrategy,
    _expand_env,
)


def _python_command(code: str) -> str:
    """Build a direct Python command string for shell='none' tests."""
    return f"{shlex.quote(sys.executable)} -c {shlex.quote(code)}"


def _write_test_mcp_server(runtime_dir: Path) -> Path:
    """Create a tiny real MCP stdio server for round-trip tests."""
    script_path = runtime_dir / "test_mcp_server.py"
    script_path.write_text(
        """
from __future__ import annotations

from mcp.server import MCPServer

mcp = MCPServer("unit-test-server", log_level="CRITICAL")


@mcp.tool(description="Add two integers.")
def add(a: int, b: int) -> str:
    return str(a + b)


@mcp.prompt(description="Build a greeting.")
def greet(name: str) -> str:
    return f"Hello, {name}!"


if __name__ == "__main__":
    mcp.run()
""".strip(),
        encoding="utf-8",
    )
    return script_path


@pytest.fixture
def runtime_dir() -> Iterator[Path]:
    """Create a project-local scratch directory for runtime artifacts."""
    path = Path.cwd() / ".pytest-execution-servers" / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


class TestServerConfigurations:
    """Tests for lightweight server configuration helpers."""

    def test_wait_strategy_tools_value(self) -> None:
        """WaitStrategy exposes the MCP tool-readiness sentinel."""
        assert WaitStrategy.TOOLS == "tools"

    def test_wait_for_tools_returns_expected_configuration(self) -> None:
        """Wait.for_tools builds a frozen wait configuration."""
        wait = Wait.for_tools(["read_file", "write_file"], timeout_ms=1_500)

        assert wait.strategy is WaitStrategy.TOOLS
        assert wait.tools == ["read_file", "write_file"]
        assert wait.timeout_ms == 1_500

    def test_wait_is_frozen(self) -> None:
        """Wait instances reject mutation."""
        wait = Wait.for_tools(["search"])

        with pytest.raises(FrozenInstanceError):
            wait.timeout_ms = 10  # type: ignore[misc]

    @pytest.mark.parametrize("transport", ["sse", "streamable-http"])
    def test_mcp_server_remote_transports_require_url(
        self, transport: Literal["sse", "streamable-http"]
    ) -> None:
        """Remote MCP transports validate that a URL is present."""
        with pytest.raises(ValueError, match="requires a url"):
            MCPServer(transport=transport)

    def test_cli_server_defaults(self) -> None:
        """CLIServer exposes the documented defaults."""
        config = CLIServer(command="git", tool_prefix="git")

        assert config.env == {}
        assert config.shell is None
        assert config.cwd is None
        assert not config.discover_help
        assert config.help_flag == "--help"
        assert config.timeout == 30
        assert config.description is None

    def test_expand_env_uses_os_path_expandvars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """_expand_env expands shell-style variables."""
        monkeypatch.setenv("EXECUTION_SERVERS_TOKEN", "secret")

        assert _expand_env("Bearer $EXECUTION_SERVERS_TOKEN") == "Bearer secret"


class TestMCPServerProcessWithRealServer:
    """Tests for MCPServerProcess using a real stdio MCP subprocess."""

    async def test_start_discovers_tools_and_prompts(self, runtime_dir: Path) -> None:
        """start() initializes a real MCP server and stores its metadata."""
        script_path = _write_test_mcp_server(runtime_dir)
        server = MCPServerProcess(
            MCPServer(
                command=[sys.executable, str(script_path)],
                wait=Wait.for_tools(["add"]),
            )
        )

        try:
            await server.start()

            tools = server.get_tools()
            prompts = server.get_prompts()

            assert list(tools) == ["add"]
            assert tools["add"]["description"] == "Add two integers."
            assert tools["add"]["inputSchema"]["required"] == ["a", "b"]

            assert list(prompts) == ["greet"]
            prompt = prompts["greet"]
            assert isinstance(prompt, MCPPrompt)
            assert prompt.description == "Build a greeting."
            assert len(prompt.arguments) == 1
            assert prompt.arguments[0].name == "name"
            assert prompt.arguments[0].required
        finally:
            await server.stop()

    async def test_call_tool_get_prompt_and_list_prompts_round_trip(
        self, runtime_dir: Path
    ) -> None:
        """The real MCP subprocess can execute tools and render prompts."""
        script_path = _write_test_mcp_server(runtime_dir)
        server = MCPServerProcess(MCPServer(command=[sys.executable, str(script_path)]))

        try:
            await server.start()

            assert await server.call_tool("add", {"a": 2, "b": 3}) == "5"
            prompts = await server.list_prompts()
            assert len(prompts) == 1
            assert prompts[0].name == "greet"
            assert prompts[0].description == "Build a greeting."
            assert len(prompts[0].arguments) == 1
            assert prompts[0].arguments[0].name == "name"
            assert prompts[0].arguments[0].required
            assert await server.get_prompt("greet", {"name": "Ada"}) == [
                {"role": "user", "content": "Hello, Ada!"}
            ]
        finally:
            await server.stop()

    async def test_start_wraps_transport_errors_in_server_start_error(self) -> None:
        """Transport failures are wrapped in ServerStartError."""
        server = MCPServerProcess(MCPServer(command=["/definitely/missing-executable"]))

        with pytest.raises(ServerStartError, match="Failed to start MCP server"):
            await server.start()

    async def test_start_raises_when_required_tools_are_missing(self, runtime_dir: Path) -> None:
        """Wait.for_tools raises when discovery does not expose required tools."""
        script_path = _write_test_mcp_server(runtime_dir)
        server = MCPServerProcess(
            MCPServer(
                command=[sys.executable, str(script_path)],
                wait=Wait.for_tools(["missing_tool"]),
            )
        )

        try:
            with pytest.raises(ServerStartError, match="Required tools not available"):
                await server.start()
        finally:
            if server._exit_stack is not None:
                await server.stop()

    async def test_start_cleans_up_after_missing_required_tools(self, runtime_dir: Path) -> None:
        """Startup failures from Wait.for_tools should release opened resources."""
        script_path = _write_test_mcp_server(runtime_dir)
        server = MCPServerProcess(
            MCPServer(
                command=[sys.executable, str(script_path)],
                wait=Wait.for_tools(["missing_tool"]),
            )
        )

        try:
            with pytest.raises(ServerStartError):
                await server.start()

            assert server._exit_stack is None
            assert server._session is None
        finally:
            if server._exit_stack is not None:
                await server.stop()


class TestMCPServerProcessHelpers:
    """Tests for MCPServerProcess helper and error-handling paths."""

    async def test_list_prompts_raises_when_not_started(self) -> None:
        """list_prompts requires an active session."""
        server = MCPServerProcess(MCPServer())

        with pytest.raises(RuntimeError, match="Server not started"):
            await server.list_prompts()

    async def test_get_prompt_raises_when_not_started(self) -> None:
        """get_prompt requires an active session."""
        server = MCPServerProcess(MCPServer())

        with pytest.raises(RuntimeError, match="Server not started"):
            await server.get_prompt("review")

    async def test_call_tool_raises_when_not_started(self) -> None:
        """call_tool requires an active session."""
        server = MCPServerProcess(MCPServer())

        with pytest.raises(RuntimeError, match="Server not started"):
            await server.call_tool("search", {})

    async def test_list_prompts_returns_empty_list_on_session_error(self) -> None:
        """Prompt capability discovery is best-effort."""

        class ErrorSession:
            async def list_prompts(self) -> Any:
                raise RuntimeError("prompt support missing")

        server = MCPServerProcess(MCPServer())
        server._session = cast(Any, ErrorSession())

        assert await server.list_prompts() == []

    async def test_get_prompt_converts_supported_content_types(self) -> None:
        """get_prompt flattens MCP content objects into simple role/content dicts."""

        class OtherContent:
            def __str__(self) -> str:
                return "other content"

        class PromptSession:
            async def get_prompt(self, name: str, arguments: dict[str, str] | None) -> Any:
                assert name == "compose"
                assert arguments == {"topic": "testing"}
                return SimpleNamespace(
                    messages=[
                        SimpleNamespace(
                            role="user",
                            content=types.TextContent(type="text", text="plain text"),
                        ),
                        SimpleNamespace(
                            role=SimpleNamespace(value="assistant"),
                            content=types.EmbeddedResource(
                                type="resource",
                                resource=types.TextResourceContents(
                                    uri=cast(Any, "file:///prompt.txt"),
                                    mime_type="text/plain",
                                    text="embedded text",
                                ),
                            ),
                        ),
                        SimpleNamespace(
                            role="assistant",
                            content=OtherContent(),
                        ),
                    ]
                )

        server = MCPServerProcess(MCPServer())
        server._session = cast(Any, PromptSession())

        assert await server.get_prompt("compose", {"topic": "testing"}) == [
            {"role": "user", "content": "plain text"},
            {"role": "assistant", "content": "embedded text"},
            {"role": "assistant", "content": "other content"},
        ]

    async def test_call_tool_prefers_first_text_content_block(self) -> None:
        """call_tool extracts the first TextContent block from the MCP response."""

        class ToolSession:
            async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
                assert name == "tool"
                assert arguments == {"x": 1}
                return SimpleNamespace(
                    content=[
                        types.EmbeddedResource(
                            type="resource",
                            resource=types.TextResourceContents(
                                uri=cast(Any, "file:///tool.txt"),
                                mime_type="text/plain",
                                text="ignored",
                            ),
                        ),
                        types.TextContent(type="text", text="wanted"),
                    ]
                )

        server = MCPServerProcess(MCPServer())
        server._session = cast(Any, ToolSession())

        assert await server.call_tool("tool", {"x": 1}) == "wanted"

    async def test_call_tool_falls_back_to_string_and_empty_content(self) -> None:
        """call_tool falls back to str(block) and to an empty string when needed."""

        class FallbackBlock:
            def __str__(self) -> str:
                return "fallback"

        class FallbackSession:
            async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
                if arguments.get("mode") == "string":
                    return SimpleNamespace(content=[FallbackBlock()])
                return SimpleNamespace(content=[])

        server = MCPServerProcess(MCPServer())
        server._session = cast(Any, FallbackSession())

        assert await server.call_tool("tool", {"mode": "string"}) == "fallback"
        assert await server.call_tool("tool", {"mode": "empty"}) == ""

    async def test_stop_swallows_teardown_errors(self) -> None:
        """stop() clears state even if the exit stack raises during teardown."""

        class FailingExitStack:
            async def aclose(self) -> None:
                raise RuntimeError("teardown failed")

        server = MCPServerProcess(MCPServer())
        server._exit_stack = cast(Any, FailingExitStack())
        server._session = cast(Any, object())

        await server.stop()

        assert server._exit_stack is None
        assert server._session is None

    def test_transport_label_uses_command_for_stdio_and_url_for_remote(self) -> None:
        """Transport labels match the active connection style."""
        stdio_server = MCPServerProcess(
            MCPServer(command=["python", "-m", "server"], args=["--port", "1"])
        )
        http_server = MCPServerProcess(
            MCPServer(transport="streamable-http", url="http://example.test/mcp")
        )

        assert stdio_server._transport_label() == ["python", "-m", "server", "--port", "1"]
        assert http_server._transport_label() == ["streamable-http", "http://example.test/mcp"]

    async def test_open_transport_uses_sse_client_with_expanded_headers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SSE transport expands environment variables before connecting."""
        import mcp.client.sse as mcp_sse

        captured: dict[str, Any] = {}

        @contextlib.asynccontextmanager
        async def fake_sse_client(
            url: str, headers: dict[str, str] | None = None
        ) -> AsyncIterator[tuple[str, str]]:
            captured["url"] = url
            captured["headers"] = headers
            yield ("read-stream", "write-stream")

        monkeypatch.setenv("MCP_TOKEN", "abc123")
        monkeypatch.setattr(mcp_sse, "sse_client", fake_sse_client)

        server = MCPServerProcess(
            MCPServer(
                transport="sse",
                url="http://example.test/sse",
                headers={"Authorization": "Bearer $MCP_TOKEN"},
            )
        )

        async with contextlib.AsyncExitStack() as exit_stack:
            server._exit_stack = exit_stack
            assert await server._open_transport() == ("read-stream", "write-stream")

        assert captured == {
            "url": "http://example.test/sse",
            "headers": {"Authorization": "Bearer abc123"},
        }

    async def test_open_transport_uses_streamable_http_client_with_headers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Streamable HTTP transport creates an httpx client when headers are configured."""
        import httpx2
        import mcp.client.streamable_http as mcp_http

        captured: dict[str, Any] = {}

        class FakeAsyncClient:
            def __init__(self, headers: dict[str, str]) -> None:
                self.headers = headers

            async def __aenter__(self) -> FakeAsyncClient:
                return self

            async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
                return None

        @contextlib.asynccontextmanager
        async def fake_streamable_http_client(
            url: str, http_client: Any = None
        ) -> AsyncIterator[tuple[str, str]]:
            captured["url"] = url
            captured["http_client"] = http_client
            yield ("http-read", "http-write")

        monkeypatch.setenv("MCP_TOKEN", "xyz789")
        monkeypatch.setattr(httpx2, "AsyncClient", FakeAsyncClient)
        monkeypatch.setattr(mcp_http, "streamable_http_client", fake_streamable_http_client)

        server = MCPServerProcess(
            MCPServer(
                transport="streamable-http",
                url="http://example.test/mcp",
                headers={"Authorization": "Bearer $MCP_TOKEN"},
            )
        )

        async with contextlib.AsyncExitStack() as exit_stack:
            server._exit_stack = exit_stack
            assert await server._open_transport() == ("http-read", "http-write")

        assert captured["url"] == "http://example.test/mcp"
        assert captured["http_client"].headers == {"Authorization": "Bearer xyz789"}


class TestCLIServerProcess:
    """Tests for the CLI-to-tool wrapper."""

    def test_init_uses_explicit_shell_and_auto_detects_platform(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Shell selection honors explicit config and platform defaults."""
        explicit = CLIServerProcess(CLIServer(command="git", tool_prefix="git", shell="none"))
        assert explicit._shell == "none"

        monkeypatch.setattr(sys, "platform", "win32")
        windows_default = CLIServerProcess(CLIServer(command="git", tool_prefix="git"))
        assert windows_default._shell == "powershell"

        monkeypatch.setattr(sys, "platform", "linux")
        linux_default = CLIServerProcess(CLIServer(command="git", tool_prefix="git"))
        assert linux_default._shell == "bash"

    async def test_start_discovers_help_and_truncates_long_output(self) -> None:
        """Discovered help text is truncated before being exposed to the LLM."""
        server = CLIServerProcess(
            CLIServer(
                command=_python_command("print('x' * 3001)"),
                tool_prefix="python",
                shell="none",
                discover_help=True,
                help_flag="",
            )
        )

        await server.start()

        assert server._help_text is not None
        assert server._help_text.startswith("x" * 2_000)
        assert server._help_text.endswith("\n... (truncated)")
        assert "Help:" in server.get_tools()["python_execute"]["description"]

    @pytest.mark.parametrize(
        ("command", "shell"),
        [
            ("printf ''", "bash"),
            ("exit 4", "bash"),
        ],
    )
    async def test_discover_help_returns_none_for_empty_or_failed_output(
        self, command: str, shell: str
    ) -> None:
        """Help discovery is skipped when stdout is empty or the command fails."""
        server = CLIServerProcess(
            CLIServer(
                command=command,
                tool_prefix="cmd",
                shell=shell,
                discover_help=True,
                help_flag="",
            )
        )

        await server.start()

        assert server._help_text is None

    async def test_run_command_shell_none_splits_arguments_and_records_execution(self) -> None:
        """Direct execution splits base command and user args independently."""
        server = CLIServerProcess(
            CLIServer(
                command=_python_command("import json, sys; print(json.dumps(sys.argv[1:]))"),
                tool_prefix="python",
                shell="none",
            )
        )

        execution = await server._run_command("'alpha beta' gamma")

        assert execution["command"] == server.config.command
        assert execution["args"] == "'alpha beta' gamma"
        assert execution["exit_code"] == 0
        assert json.loads(execution["stdout"]) == ["alpha beta", "gamma"]
        assert execution["duration_ms"] >= 0
        assert server.get_executions() == [execution]

    async def test_run_command_uses_env_and_cwd_and_captures_nonzero_exit(
        self, runtime_dir: Path
    ) -> None:
        """CLI execution passes env/cwd through and records stderr plus exit code."""
        work_dir = runtime_dir / "cwd"
        work_dir.mkdir()
        server = CLIServerProcess(
            CLIServer(
                command=_python_command(
                    "import os, pathlib, sys; "
                    "print(os.environ['EXEC_SERVER_VAR']); "
                    "print(pathlib.Path.cwd()); "
                    "print('boom', file=sys.stderr); "
                    "raise SystemExit(7)"
                ),
                tool_prefix="python",
                shell="none",
                cwd=str(work_dir),
                env={"EXEC_SERVER_VAR": "set"},
            )
        )

        execution = await server._run_command("")
        stdout_lines = execution["stdout"].strip().splitlines()

        assert execution["exit_code"] == 7
        assert stdout_lines == ["set", str(work_dir)]
        assert execution["stderr"].strip() == "boom"

    async def test_run_command_times_out_and_records_execution(self) -> None:
        """Timeouts kill the process and return a synthetic error result."""
        server = CLIServerProcess(
            CLIServer(
                command=_python_command("import time; time.sleep(2)"),
                tool_prefix="python",
                shell="none",
                timeout=1,
            )
        )

        execution = await server._run_command("")

        assert execution["exit_code"] == -1
        assert execution["stdout"] == ""
        assert "timed out" in execution["stderr"].lower()
        assert 800 <= execution["duration_ms"] < 4_000

    async def test_run_command_records_spawn_errors(self) -> None:
        """Process spawn failures are converted into execution records."""
        server = CLIServerProcess(
            CLIServer(
                command="/definitely/missing-command",
                tool_prefix="missing",
                shell="none",
            )
        )

        execution = await server._run_command("")

        assert execution["exit_code"] == -1
        assert execution["stdout"] == ""
        assert execution["stderr"].startswith("Error:")

    def test_get_tools_description_priority(self) -> None:
        """Custom description wins, then discovered help, then the generic fallback."""
        custom = CLIServerProcess(
            CLIServer(command="git", tool_prefix="git", description="Custom description.")
        )
        with_help = CLIServerProcess(CLIServer(command="git", tool_prefix="git"))
        with_help._help_text = "git help text"
        default = CLIServerProcess(CLIServer(command="git", tool_prefix="git"))

        custom_description = custom.get_tools()["git_execute"]["description"]
        help_description = with_help.get_tools()["git_execute"]["description"]
        default_description = default.get_tools()["git_execute"]["description"]

        assert custom_description == "Execute git CLI command.\n\nCustom description."
        assert help_description == "Execute git CLI command.\n\nHelp:\ngit help text"
        assert default_description == "Execute git CLI command with arguments."

    async def test_call_tool_returns_json_and_validates_tool_name(self) -> None:
        """call_tool validates the synthetic tool name and returns JSON output."""
        server = CLIServerProcess(
            CLIServer(
                command=_python_command("import sys; print(' '.join(sys.argv[1:]))"),
                tool_prefix="python",
                shell="none",
            )
        )

        with pytest.raises(ValueError, match="Unknown tool: wrong_execute"):
            await server.call_tool("wrong_execute", {})

        result = json.loads(await server.call_tool("python_execute", {"args": "one two"}))

        assert result == {"exit_code": 0, "stdout": "one two\n", "stderr": ""}

    async def test_get_executions_accumulates_and_stop_clears(self) -> None:
        """Execution history persists across runs until stop() is called."""
        server = CLIServerProcess(
            CLIServer(
                command=_python_command("import sys; print(' '.join(sys.argv[1:]))"),
                tool_prefix="python",
                shell="none",
            )
        )

        await server.call_tool("python_execute", {"args": "alpha"})
        await server.call_tool("python_execute", {"args": "beta"})

        executions = server.get_executions()
        assert len(executions) == 2
        assert [item["args"] for item in executions] == ["alpha", "beta"]

        await server.stop()

        assert server.get_executions() == []
