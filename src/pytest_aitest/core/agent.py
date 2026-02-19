"""Agent and provider configuration models."""

from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Literal, overload

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pytest_aitest.core.skill import Skill

#: Supported MCP transport types.
Transport = Literal["stdio", "sse", "streamable-http"]


class ClarificationLevel(Enum):
    """Severity level when clarification is detected."""

    INFO = "info"  # Log only, don't affect test outcome
    WARNING = "warning"  # Log and record as warning
    ERROR = "error"  # Treat as test error


@dataclass(slots=True, frozen=True)
class ClarificationDetection:
    """Configuration for detecting when an agent asks for clarification.

    When enabled, uses a judge LLM to detect if the agent is asking the user
    for clarification (e.g., \"Would you like me to...?\") instead of executing
    the requested task. This is important because agents being tested should
    act autonomously, not ask questions.

    The judge model can be the same as the agent's model (default) or a
    separate, cheaper model.

    Example:
        # Use agent's own model as judge
        Agent(
            provider=Provider(model="azure/gpt-5-mini"),
            clarification_detection=ClarificationDetection(enabled=True),
        )

        # Use a separate cheaper model as judge
        Agent(
            provider=Provider(model="azure/gpt-4.1"),
            clarification_detection=ClarificationDetection(
                enabled=True,
                level=ClarificationLevel.ERROR,
                judge_model="azure/gpt-5-mini",
            ),
        )
    """

    enabled: bool = False
    level: ClarificationLevel = ClarificationLevel.WARNING
    judge_model: str | None = None  # None = use agent's own model


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


@overload
def _expand_env(value: str) -> str: ...


@overload
def _expand_env(value: None) -> None: ...


def _expand_env(value: str | None) -> str | None:
    """Expand ${VAR} patterns in string for server environment variables."""
    if value is None:
        return None
    pattern = r"\$\{([^}]+)\}"
    return re.sub(pattern, lambda m: os.environ.get(m.group(1), m.group(0)), value)


@dataclass(slots=True)
class Provider:
    """LLM provider configuration.

    Authentication is handled via standard environment variables:
    - Azure: AZURE_API_BASE + `az login` (Entra ID)
    - OpenAI: OPENAI_API_KEY
    - Anthropic: ANTHROPIC_API_KEY

    See https://ai.pydantic.dev/models/ for supported providers.

    Example:
        Provider(model="openai/gpt-4o-mini")
        Provider(model="azure/gpt-5-mini", temperature=0.7)
        Provider(model="azure/gpt-5-mini", rpm=10, tpm=10000)
    """

    model: str
    temperature: float | None = None
    max_tokens: int | None = None
    rpm: int | None = None  # Requests per minute
    tpm: int | None = None  # Tokens per minute


@dataclass(slots=True)
class MCPServer:
    """MCP server configuration.

    Supports three transports:

    **stdio** (default) — Launches a local subprocess and communicates via
    stdin/stdout. Requires ``command``.

    **sse** — Connects to a remote server using Server-Sent Events.
    Requires ``url``.

    **streamable-http** — Connects to a remote server using the
    Streamable HTTP transport (recommended for production).
    Requires ``url``.

    Example:
        # stdio (default)
        MCPServer(
            command=["npx", "-y", "@modelcontextprotocol/server-filesystem"],
            args=["--directory", "/workspace"],
        )

        # SSE remote server
        MCPServer(
            transport="sse",
            url="http://localhost:8000/sse",
        )

        # Streamable HTTP remote server
        MCPServer(
            transport="streamable-http",
            url="http://localhost:8000/mcp",
        )

        # With custom headers (e.g. auth)
        MCPServer(
            transport="streamable-http",
            url="https://mcp.example.com/mcp",
            headers={"Authorization": "Bearer ${MCP_TOKEN}"},
        )
    """

    command: list[str] = field(default_factory=list)
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    wait: Wait = field(default_factory=Wait.ready)
    cwd: str | None = None
    transport: Transport = "stdio"
    url: str | None = None
    headers: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Expand env vars in environment
        self.env = {k: _expand_env(v) for k, v in self.env.items()}
        # Expand env vars in headers
        self.headers = {k: _expand_env(v) for k, v in self.headers.items()}
        # Validate transport/field combinations
        if self.transport == "stdio":
            if not self.command:
                msg = "MCPServer with transport='stdio' requires 'command'"
                raise ValueError(msg)
            if self.url:
                msg = "MCPServer with transport='stdio' does not use 'url'"
                raise ValueError(msg)
        elif self.transport in ("sse", "streamable-http"):
            if not self.url:
                msg = f"MCPServer with transport='{self.transport}' requires 'url'"
                raise ValueError(msg)
            if self.command:
                msg = f"MCPServer with transport='{self.transport}' does not use 'command'"
                raise ValueError(msg)


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
    timeout: float = 30.0  # Timeout in seconds for each CLI command execution

    def __post_init__(self) -> None:
        self.env = {k: _expand_env(v) for k, v in self.env.items()}
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
            name="banking-fast",
            provider=Provider(model="azure/gpt-5-mini"),
            mcp_servers=[banking_server],
            system_prompt="Be concise.",
        )

    Comparing agents:
        agents = [agent_fast, agent_smart, agent_expert]

        @pytest.mark.parametrize("agent", agents, ids=lambda a: a.name)
        async def test_query(aitest_run, agent):
            result = await aitest_run(agent, "What's my balance?")

    Filtering tools:
        Agent(
            provider=Provider(model="azure/gpt-5-mini"),
            mcp_servers=[excel_server],
            allowed_tools=["read_cell", "write_cell"],  # Only expose these tools
        )
    """

    provider: Provider
    name: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    mcp_servers: list[MCPServer] = field(default_factory=list)
    cli_servers: list[CLIServer] = field(default_factory=list)
    system_prompt: str | None = None
    max_turns: int = 10
    skill: Skill | None = None
    allowed_tools: list[str] | None = None  # Filter to specific tools (None = all)
    system_prompt_name: str | None = None  # Label for system prompt (for report grouping)
    retries: int = 1  # Max tool error retries (Pydantic AI default)
    clarification_detection: ClarificationDetection = field(default_factory=ClarificationDetection)

    def __post_init__(self) -> None:
        """Auto-construct name from dimensions if not explicitly set."""
        if not self.name:
            model = self.provider.model
            display_model = model.split("/")[-1] if "/" in model else model
            parts = [display_model]
            if self.system_prompt_name:
                parts.append(self.system_prompt_name)
            if self.skill:
                parts.append(self.skill.name)
            self.name = " + ".join(parts)
