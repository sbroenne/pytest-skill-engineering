"""Custom agent file loader for ``.agent.md`` files.

Loads VS Code custom agent definitions into ``CustomAgentConfig``-compatible
dicts for use with :attr:`CopilotAgent.custom_agents`.

Agent files use YAML frontmatter for metadata and markdown body for the
agent's prompt/instructions.

Example ``.agent.md`` file::

    ---
    description: 'Research specialist for codebase analysis'
    maturity: stable
    handoffs:
      - label: "📋 Create Plan"
        agent: task-planner
        prompt: /task-plan
        send: true
    ---

    # Task Researcher

    Research-only specialist. Produces findings in `.copilot-tracking/research/`.

Example usage::

    from pytest_aitest.copilot.agents import load_custom_agent, load_custom_agents

    # Single agent
    researcher = load_custom_agent("agents/task-researcher.agent.md")
    # → {"name": "task-researcher", "prompt": "# Task Researcher\\n...",
    #    "description": "...", "metadata": {...}}

    # All agents from a directory
    agents = load_custom_agents("agents/")

    # Use with CopilotAgent
    agent = CopilotAgent(
        name="orchestrator",
        instructions="Dispatch tasks to specialized agents.",
        custom_agents=load_custom_agents("agents/", exclude={"orchestrator"}),
    )
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _extract_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Split content into parsed frontmatter dict and body.

    Returns:
        Tuple of (frontmatter_dict, body). Frontmatter dict is empty
        if no frontmatter block is present or parsing fails.
    """
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}, content

    raw = match.group(1)
    body = content[match.end() :]

    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError:
        return {}, body

    if not isinstance(parsed, dict):
        return {}, body

    return parsed, body


def _name_from_path(path: Path) -> str:
    """Derive agent name from filename.

    ``task-researcher.agent.md`` → ``task-researcher``
    """
    name = path.name
    if name.endswith(".agent.md"):
        return name[: -len(".agent.md")]
    return path.stem


def load_custom_agent(
    path: Path | str,
    *,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Load a ``.agent.md`` file into a ``CustomAgentConfig``-compatible dict.

    Parses YAML frontmatter with PyYAML for structured metadata
    (``description``, ``handoffs``, ``maturity``, etc.) and uses the
    markdown body as the agent's ``prompt``.

    Args:
        path: Path to the ``.agent.md`` file.
        overrides: Additional fields to merge into the result. Use this
            to set ``tools``, ``mcp_servers``, or ``infer`` fields that
            aren't in the agent file itself.

    Returns:
        Dict with keys:
            - ``name`` (str): Derived from filename.
            - ``prompt`` (str): Markdown body after frontmatter.
            - ``description`` (str): From frontmatter, empty if absent.
            - ``metadata`` (dict): Full parsed frontmatter dict.
        Compatible with :attr:`CopilotAgent.custom_agents`.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file has no content after frontmatter stripping.
    """
    path = Path(path)
    if not path.exists():
        msg = f"Agent file not found: {path}"
        raise FileNotFoundError(msg)

    content = path.read_text(encoding="utf-8")
    metadata, body = _extract_frontmatter(content)
    body = body.strip()

    if not body:
        msg = f"Agent file has no content after frontmatter: {path}"
        raise ValueError(msg)

    config: dict[str, Any] = {
        "name": _name_from_path(path),
        "prompt": body,
        "description": metadata.get("description", ""),
        "metadata": metadata,
    }

    if overrides:
        config.update(overrides)

    return config


def load_custom_agents(
    directory: Path | str,
    *,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
    overrides: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Load all ``.agent.md`` files from a directory.

    Args:
        directory: Path to directory containing ``.agent.md`` files.
        include: If set, only load agents with these names. Names are
            derived from filenames (e.g. ``task-researcher.agent.md``
            → ``task-researcher``).
        exclude: Agent names to skip.
        overrides: Per-agent override dicts keyed by agent name. Merged
            into each matching agent's config.

    Returns:
        List of ``CustomAgentConfig``-compatible dicts, sorted by name.

    Raises:
        FileNotFoundError: If the directory does not exist.
    """
    directory = Path(directory)
    if not directory.is_dir():
        msg = f"Agent directory not found: {directory}"
        raise FileNotFoundError(msg)

    agents: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.agent.md")):
        name = _name_from_path(path)

        if include is not None and name not in include:
            continue
        if exclude is not None and name in exclude:
            continue

        agent_overrides = (overrides or {}).get(name)
        agents.append(load_custom_agent(path, overrides=agent_overrides))

    return agents
