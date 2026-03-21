"""CopilotEval configuration for testing GitHub Copilot."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import yaml

if TYPE_CHECKING:
    from pytest_skill_engineering.copilot.personas import Persona

_logger = logging.getLogger(__name__)


def _parse_agent_file(path: Path) -> dict[str, Any]:
    """Parse a ``.agent.md`` file into a ``CustomAgentConfig`` dict.

    Handles optional YAML frontmatter (name, description, tools, mcp-servers)
    followed by the agent's Markdown prompt body.
    """
    content = path.read_text(encoding="utf-8")
    lines = content.split("\n")

    frontmatter: dict[str, Any] = {}
    body = content

    if lines and lines[0].strip() == "---":
        close_idx: int | None = None
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                close_idx = i
                break
        if close_idx is not None:
            try:
                frontmatter = yaml.safe_load("\n".join(lines[1:close_idx])) or {}
            except yaml.YAMLError:
                frontmatter = {}
            body = "\n".join(lines[close_idx + 1 :]).strip()

    # Derive name from filename when not set in frontmatter
    stem = path.name
    if stem.endswith(".agent.md"):
        stem = stem[: -len(".agent.md")]
    name: str = str(frontmatter.get("name") or stem)

    agent: dict[str, Any] = {"name": name}
    if "description" in frontmatter:
        agent["description"] = frontmatter["description"]
    if body:
        agent["prompt"] = body
    if "tools" in frontmatter:
        agent["tools"] = frontmatter["tools"]
    if "mcp-servers" in frontmatter:
        agent["mcp_servers"] = frontmatter["mcp-servers"]

    return agent


@dataclass(slots=True, frozen=True)
class CopilotEval:
    """Configuration for a GitHub Copilot agent test.

    Maps to the Copilot SDK's ``SessionConfig``. User-facing field names
    are kept intuitive (e.g. ``instructions``), while
    ``build_session_config()`` maps them to the SDK's actual
    ``system_message`` TypedDict.

    The SDK's ``SessionConfig`` has no ``maxTurns`` field — turn limits
    are enforced externally by the runner via ``timeout_s``.

    Example:
        # Minimal
        CopilotEval()

        # With instructions and model
        CopilotEval(
            name="security-reviewer",
            model="claude-sonnet-4",
            instructions="Review code for security vulnerabilities.",
        )

        # With custom tools and references
        CopilotEval(
            name="file-creator",
            instructions="Create files as requested.",
            working_directory="/tmp/workspace",
            allowed_tools=["create_file", "read_file"],
        )
    """

    # Identity
    name: str = "copilot"

    # Model selection (None = Copilot's default)
    model: str | None = None
    reasoning_effort: Literal["low", "medium", "high", "xhigh"] | None = None

    # System message content — maps to SDK's system_message.content
    # In the Copilot SDK, this is NOT a "system prompt" — it's instructions
    # appended to (or replacing) the CLI's built-in system message.
    instructions: str | None = None
    system_message_mode: Literal["append", "replace"] = "append"

    # Context
    working_directory: str | None = None

    # Tool control
    allowed_tools: list[str] | None = None  # Allowlist (None = all)
    excluded_tools: list[str] | None = None  # Blocklist

    # Limits — enforced by the runner, NOT part of SDK SessionConfig
    max_turns: int = 25
    timeout_s: float = 300.0

    # Retry on transient SDK errors (fetch failed, model list errors)
    max_retries: int = 2
    retry_delay_s: float = 5.0

    # Permissions — auto-approve by default for deterministic testing
    auto_confirm: bool = True

    # MCP servers to attach to the session
    mcp_servers: dict[str, Any] = field(default_factory=dict)

    # Custom agents (SDK CustomAgentConfig: name, prompt, description,
    # display_name, tools, mcp_servers, infer)
    custom_agents: list[dict[str, Any]] = field(default_factory=list)

    # Skill directories
    skill_directories: list[str] = field(default_factory=list)
    disabled_skills: list[str] = field(default_factory=list)

    # SDK passthrough for unmapped fields
    extra_config: dict[str, Any] = field(default_factory=dict)

    # SDK passthrough: activate a specific custom agent at session start.
    # Maps to the SDK's ``agent`` parameter on ``create_session()``.
    active_agent: str = ""

    # SDK passthrough: lifecycle hooks (SessionHooks).
    # Maps to the SDK's ``hooks`` parameter on ``create_session()``.
    hooks: dict[str, Any] = field(default_factory=dict)

    # IDE persona — controls which polyfill tools are injected to simulate
    # the target runtime environment (VS Code, Claude Code, Copilot CLI, etc.)
    # VSCodePersona is the default: it polyfills runSubagent when custom_agents
    # are present, matching VS Code's native behaviour.
    persona: "Persona" = field(default_factory=lambda: _default_persona())

    def build_session_config(self) -> dict[str, Any]:
        """Build a SessionConfig dict for the Copilot SDK.

        Returns a dict compatible with ``CopilotClient.create_session()``.
        Only includes non-None/non-default fields to avoid overriding
        SDK defaults.

        SDK field mapping (Python snake_case TypedDict keys):
            instructions → system_message: {mode, content}
            allowed_tools → available_tools
            excluded_tools → excluded_tools
            reasoning_effort → reasoning_effort
            working_directory → working_directory
            mcp_servers → mcp_servers
            custom_agents → custom_agents
            skill_directories → skill_directories
            disabled_skills → disabled_skills

        Note: ``max_turns`` is NOT part of ``SessionConfig`` — the runner
        enforces turn limits externally.
        """
        config: dict[str, Any] = {}

        if self.model is not None:
            config["model"] = self.model

        if self.reasoning_effort is not None:
            config["reasoning_effort"] = self.reasoning_effort

        # Map instructions + system_message_mode → SDK's system_message
        if self.instructions:
            config["system_message"] = {
                "mode": self.system_message_mode,
                "content": self.instructions,
            }

        if self.working_directory is not None:
            config["working_directory"] = self.working_directory

        if self.allowed_tools is not None:
            config["available_tools"] = self.allowed_tools

        if self.excluded_tools is not None:
            config["excluded_tools"] = self.excluded_tools

        if self.mcp_servers:
            config["mcp_servers"] = self.mcp_servers

        if self.custom_agents:
            config["custom_agents"] = self.custom_agents

        if self.skill_directories:
            config["skill_directories"] = self.skill_directories

        if self.disabled_skills:
            config["disabled_skills"] = self.disabled_skills

        if self.active_agent:
            config["agent"] = self.active_agent

        if self.hooks:
            config["hooks"] = self.hooks

        # Apply extra_config passthrough
        config.update(self.extra_config)

        return config

    @classmethod
    def from_copilot_config(
        cls,
        path: str | Path = ".",
        **overrides: Any,
    ) -> "CopilotEval":
        """Load a ``CopilotEval`` from a directory containing Copilot config files.

        Looks for the following files under ``path``:

        * ``.github/copilot-instructions.md`` → ``instructions``
        * ``.github/agents/*.agent.md`` → ``custom_agents``

        Point ``path`` at any directory — your production project, a dedicated
        test fixture project, or a shared team config repo.  Any keyword
        argument overrides the loaded value.

        Args:
            path: Root directory to load config from. Defaults to the current
                working directory.
            **overrides: Override any ``CopilotEval`` field after loading,
                e.g. ``model="claude-opus-4.5"``.

        Returns:
            A ``CopilotEval`` initialised from the discovered config files.

        Example::

            # Load from the current project (production config as baseline)
            baseline = CopilotEval.from_copilot_config()

            # A/B test: same config, one instruction changed
            treatment = CopilotEval.from_copilot_config(
                instructions="Always add type hints.",
            )

            # Load from a dedicated test-fixture project
            agent = CopilotEval.from_copilot_config("tests/fixtures/strict-agent")

            # Load from a shared team agent library
            agent = CopilotEval.from_copilot_config("/shared/team/copilot-config")
        """
        root = Path(path).resolve()
        github_dir = root / ".github"

        # Load repository-wide instructions
        instructions: str | None = None
        instructions_file = github_dir / "copilot-instructions.md"
        if instructions_file.exists():
            instructions = instructions_file.read_text(encoding="utf-8").strip() or None

        # Load custom agents — recursive so subagents/ subdirectories are included
        agents: list[dict[str, Any]] = []
        agents_dir = github_dir / "agents"
        if agents_dir.exists():
            for agent_file in sorted(agents_dir.rglob("*.agent.md")):
                agents.append(_parse_agent_file(agent_file))

        config: dict[str, Any] = {
            "instructions": instructions,
            "custom_agents": agents,
        }
        config.update(overrides)
        return cls(**config)

    @classmethod
    def from_plugin(
        cls,
        path: str | Path,
        *,
        model: str = "",
        persona: "Persona | None" = None,
        instructions: str = "",
        working_directory: str = "",
        name: str = "",
    ) -> "CopilotEval":
        """Create a CopilotEval from a plugin directory.

        Loads the plugin's agents, skills, MCP servers, and instructions,
        then constructs a CopilotEval with all components wired together.

        Uses :func:`~pytest_skill_engineering.core.plugin.load_plugin` to
        discover the plugin structure.  The persona is auto-detected from the
        plugin path (``ClaudeCodePersona`` for ``.claude/`` paths,
        ``VSCodePersona`` otherwise) unless explicitly overridden.

        Args:
            path: Path to the plugin directory (may contain ``plugin.json``,
                or be a ``.github/`` / ``.claude/`` project config directory).
            model: Model override for the eval.
            persona: IDE persona override.  Auto-detected when ``None``.
            instructions: Additional instructions to **append** to the
                plugin's discovered instructions.
            working_directory: Override the working directory.
            name: Override the eval name (defaults to plugin metadata name).

        Returns:
            A ``CopilotEval`` initialised from the plugin.

        Example::

            agent = CopilotEval.from_plugin("my-plugin/")

            agent = CopilotEval.from_plugin(
                ".claude/",
                model="claude-sonnet-4",
                instructions="Focus on security reviews.",
            )
        """
        from pytest_skill_engineering.core.plugin import load_plugin  # noqa: PLC0415

        plugin = load_plugin(path)

        # Build combined instructions: plugin base + caller override
        combined_instructions = plugin.instructions
        if instructions:
            if combined_instructions:
                combined_instructions = combined_instructions + "\n\n" + instructions
            else:
                combined_instructions = instructions

        # Map plugin.skills to skill directory paths
        skill_dirs = [str(s.path) for s in plugin.skills]

        # Auto-detect persona from plugin path
        if persona is None:
            resolved = Path(path).resolve()
            if resolved.name == ".claude" or (resolved / ".claude").is_dir():
                from pytest_skill_engineering.copilot.personas import (  # noqa: PLC0415
                    ClaudeCodePersona,
                )

                persona = ClaudeCodePersona()
            else:
                persona = _default_persona()

        return cls(
            name=name or plugin.metadata.name or "plugin-eval",
            model=model or None,
            instructions=combined_instructions or None,
            custom_agents=plugin.agents,
            skill_directories=skill_dirs,
            mcp_servers=plugin.mcp_servers,
            working_directory=working_directory or None,
            persona=persona,
        )

    @classmethod
    def from_claude_config(
        cls,
        path: str | Path = ".",
        *,
        model: str = "",
        persona: "Persona | None" = None,
        instructions: str = "",
        working_directory: str = "",
        name: str = "claude-code-eval",
    ) -> "CopilotEval":
        """Create a CopilotEval from a Claude Code project directory.

        Scans for:

        * ``CLAUDE.md`` (project root) and ``.claude/CLAUDE.md`` → instructions
        * ``.claude/agents/*.md`` → custom agents
        * ``.claude/skills/`` → skill directories (subdirs with ``SKILL.md``)
        * ``.mcp.json`` → MCP server configs

        Args:
            path: Root of the Claude Code project (default: current directory).
            model: Model override for the eval.
            persona: IDE persona override.  Defaults to ``ClaudeCodePersona``.
            instructions: Additional instructions to **append** to the
                discovered ``CLAUDE.md`` content.
            working_directory: Override the working directory.
            name: Override the eval name.

        Returns:
            A ``CopilotEval`` initialised from the discovered config files.

        Example::

            # Load from the current project
            agent = CopilotEval.from_claude_config()

            # Load from a specific directory with model override
            agent = CopilotEval.from_claude_config(
                "tests/fixtures/claude-project",
                model="claude-sonnet-4",
            )
        """
        from pytest_skill_engineering.copilot.config import load_mcp_config  # noqa: PLC0415
        from pytest_skill_engineering.core.evals import load_custom_agent  # noqa: PLC0415

        root = Path(path).resolve()
        claude_dir = root / ".claude"

        # 1. Concatenate instructions from CLAUDE.md files
        instruction_parts: list[str] = []
        for md_path in [root / "CLAUDE.md", claude_dir / "CLAUDE.md"]:
            if md_path.is_file():
                content = md_path.read_text(encoding="utf-8").strip()
                if content:
                    instruction_parts.append(content)
        if instructions:
            instruction_parts.append(instructions)
        combined_instructions = "\n\n".join(instruction_parts) or None

        # 2. Load custom agents from .claude/agents/
        agents: list[dict[str, Any]] = []
        agents_dir = claude_dir / "agents"
        if agents_dir.is_dir():
            # Claude Code uses plain .md files for agents
            for agent_file in sorted(agents_dir.glob("*.md")):
                try:
                    agents.append(load_custom_agent(agent_file))
                except (FileNotFoundError, ValueError) as exc:
                    _logger.warning("Skipping agent file %s: %s", agent_file.name, exc)

        # 3. Discover skill directories from .claude/skills/
        skill_dirs: list[str] = []
        skills_dir = claude_dir / "skills"
        if skills_dir.is_dir():
            for subdir in sorted(skills_dir.iterdir()):
                if subdir.is_dir() and (subdir / "SKILL.md").exists():
                    skill_dirs.append(str(subdir))

        # 4. Parse .mcp.json if it exists
        mcp_servers: dict[str, dict[str, Any]] = {}
        mcp_config_path = root / ".mcp.json"
        if mcp_config_path.is_file():
            try:
                mcp_servers = load_mcp_config(mcp_config_path)
            except (ValueError, FileNotFoundError) as exc:
                _logger.warning("Failed to load .mcp.json: %s", exc)

        # 5. Default persona to ClaudeCodePersona
        if persona is None:
            from pytest_skill_engineering.copilot.personas import (  # noqa: PLC0415
                ClaudeCodePersona,
            )

            persona = ClaudeCodePersona()

        return cls(
            name=name,
            model=model or None,
            instructions=combined_instructions,
            custom_agents=agents,
            skill_directories=skill_dirs,
            mcp_servers=mcp_servers,
            working_directory=working_directory or None,
            persona=persona,
        )


def _default_persona() -> "Persona":
    """Return the default persona (VSCodePersona).

    Defined as a function to avoid a circular-import at module level:
    ``personas.py`` imports ``agent.py``, so we defer the import.
    """
    from pytest_skill_engineering.copilot.personas import VSCodePersona  # noqa: PLC0415

    return VSCodePersona()
