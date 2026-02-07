"""Agent and provider configuration models."""

from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pytest_aitest.core.skill import Skill


class WaitStrategy(Enum):
    """Wait strategy for server startup."""

    READY = "ready"
    LOG = "log"
    TOOLS = "tools"


@dataclass(slots=True, frozen=True)
class Wait:
    """Wait configuration for server startup.

    Example:
        Wait.for_log("Server started")
        Wait.for_tools(["read_file", "write_file"])
        Wait.ready()
    """

    strategy: WaitStrategy
    pattern: str | None = None
    tools: tuple[str, ...] | None = None
    timeout_ms: int = 30000

    @classmethod
    def ready(cls, timeout_ms: int = 30000) -> Wait:
        """Wait for server to signal ready (default)."""
        return cls(strategy=WaitStrategy.READY, timeout_ms=timeout_ms)

    @classmethod
    def for_log(cls, pattern: str, timeout_ms: int = 30000) -> Wait:
        """Wait for specific log pattern in stderr."""
        return cls(strategy=WaitStrategy.LOG, pattern=pattern, timeout_ms=timeout_ms)

    @classmethod
    def for_tools(cls, tools: Sequence[str], timeout_ms: int = 30000) -> Wait:
        """Wait until specific tools are available."""
        return cls(strategy=WaitStrategy.TOOLS, tools=tuple(tools), timeout_ms=timeout_ms)


def _expand_env(value: str | None) -> str | None:
    """Expand ${VAR} patterns in string for server environment variables."""
    if value is None:
        return None
    pattern = r"\$\{([^}]+)\}"
    return re.sub(pattern, lambda m: os.environ.get(m.group(1), m.group(0)), value)


@dataclass(slots=True)
class Provider:
    """LLM provider configuration.

    Authentication is handled by LiteLLM via standard environment variables:
    - Azure: AZURE_API_BASE + `az login` (Entra ID)
    - OpenAI: OPENAI_API_KEY
    - Anthropic: ANTHROPIC_API_KEY

    See https://docs.litellm.ai/docs/providers for full list.

    Rate limits (rpm/tpm) enable LiteLLM's built-in rate limiting.
    When set, LiteLLM will automatically queue requests and wait
    to stay within limits.

    Example:
        Provider(model="openai/gpt-4o-mini")
        Provider(model="azure/gpt-5-mini", temperature=0.7)
        Provider(model="azure/gpt-5-mini", rpm=10, tpm=10000)  # Rate limited
    """

    model: str
    temperature: float | None = None
    max_tokens: int | None = None
    rpm: int | None = None  # Requests per minute
    tpm: int | None = None  # Tokens per minute


@dataclass(slots=True)
class MCPServer:
    """MCP server configuration.

    Example:
        MCPServer(
            command=["npx", "-y", "@modelcontextprotocol/server-filesystem"],
            args=["--directory", "/workspace"],
        )
    """

    command: list[str]
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    wait: Wait = field(default_factory=Wait.ready)
    cwd: str | None = None

    def __post_init__(self) -> None:
        # Expand env vars in environment
        self.env = {k: _expand_env(v) or v for k, v in self.env.items()}


@dataclass(slots=True)
class CLIServer:
    """CLI server that wraps a command-line tool as an MCP-like tool.

    Wraps a single CLI command (like `git`, `docker`, `echo`) and exposes it
    as a tool the LLM can call with arbitrary arguments.

    By default, help discovery is DISABLED. The LLM must run `command --help`
    itself to discover available subcommands. This tests that your skill/prompt
    properly instructs the LLM to discover CLI capabilities.

    Example:
        CLIServer(
            name="git-cli",
            command="git",
            tool_prefix="git",      # Creates "git_execute" tool
            shell="bash",           # Shell to use (default: auto-detect)
        )

        # Enable auto-discovery (pre-populates tool description with help output)
        CLIServer(
            name="my-cli",
            command="my-tool",
            discover_help=True,     # Runs --help and includes in tool description
        )

        # Custom description instead of discovery
        CLIServer(
            name="legacy-cli",
            command="old-tool",
            description="Manages legacy data. Use: list, get <id>, delete <id>",
        )

    The generated tool accepts an `args` parameter:
        git_execute(args="status --porcelain")
        git_execute(args="log -n 5 --oneline")
    """

    name: str
    command: str
    tool_prefix: str | None = None
    shell: str | None = None  # auto-detect: bash on Unix, powershell on Windows
    cwd: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    discover_help: bool = False  # LLM must discover help itself (tests skill instructions)
    help_flag: str = "--help"  # Flag to get help text (when discover_help=True)
    description: str | None = None  # Custom description (overrides help discovery)

    def __post_init__(self) -> None:
        self.env = {k: _expand_env(v) or v for k, v in self.env.items()}
        if self.tool_prefix is None:
            # Use command name as prefix (e.g., "git" -> "git_execute")
            self.tool_prefix = self.command.split()[0].split("/")[-1]


@dataclass(slots=True)
class CLIExecution:
    """Result of a CLI command execution.

    Captures exit code, stdout, stderr for assertions.
    """

    command: str
    args: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


@dataclass(slots=True)
class Agent:
    """AI agent configuration combining provider and servers.

    The Agent is the unit of comparison in pytest-aitest. Each agent has
    a unique ``id`` (auto-generated UUID) that flows through the entire
    pipeline — from test execution to report rendering.

    Define agents at module level and parametrize tests with them so the
    same Agent object (same UUID) is reused across tests:

    Example:
        Agent(
            name="weather-fast",
            provider=Provider(model="azure/gpt-5-mini"),
            mcp_servers=[weather_server],
            system_prompt="Be concise.",
        )

    Comparing agents:
        agents = [agent_fast, agent_smart, agent_expert]

        @pytest.mark.parametrize("agent", agents, ids=lambda a: a.name)
        async def test_query(aitest_run, agent):
            result = await aitest_run(agent, "What's the weather?")

    Filtering tools:
        Agent(
            provider=Provider(model="azure/gpt-5-mini"),
            mcp_servers=[excel_server],
            allowed_tools=["read_cell", "write_cell"],  # Only expose these tools
        )
    """

    provider: Provider
    name: str | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    mcp_servers: list[MCPServer] = field(default_factory=list)
    cli_servers: list[CLIServer] = field(default_factory=list)
    system_prompt: str | None = None
    max_turns: int = 10
    skill: Skill | None = None
    allowed_tools: list[str] | None = None  # Filter to specific tools (None = all)
    system_prompt_name: str | None = None  # Label for system prompt (for report grouping)
