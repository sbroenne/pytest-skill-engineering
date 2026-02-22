"""Custom agent file loader for ``.agent.md`` and ``.md`` files.

Loads VS Code (``.github/agents/*.agent.md``) and Claude Code
(``.claude/agents/*.md``) custom agent definitions into dicts
compatible with both :attr:`Eval.from_agent_file` and
:attr:`CopilotEval.custom_agents`.

Eval files use YAML frontmatter for metadata and a markdown body for
the agent's prompt/instructions.

Example ``.agent.md`` file::

    ---
    description: 'Research specialist for codebase analysis'
    maturity: stable
    tools:
      - read_file
      - list_directory
    ---

    # Task Researcher

    Research-only specialist. Produces findings in ``.copilot-tracking/research/``.

Example usage::

    from pytest_skill_engineering.core.evals import load_custom_agent, load_custom_agents

    # Single agent
    researcher = load_custom_agent("agents/task-researcher.agent.md")
    # → {"name": "task-researcher", "prompt": "# Task Researcher\\n...",
    #    "description": "...", "metadata": {...}}

    # All agents from a directory
    agents = load_custom_agents("agents/")

    # Use with Eval.from_agent_file()
    from pytest_skill_engineering import Eval, Provider
    agent = Eval.from_agent_file(
        ".github/agents/reviewer.agent.md",
        provider=Provider(model="azure/gpt-5-mini"),
    )

    # Use with CopilotEval
    from pytest_skill_engineering.copilot import CopilotEval
    agent = CopilotEval(
        name="orchestrator",
        instructions="Dispatch tasks to specialized agents.",
        custom_agents=load_custom_agents("agents/", exclude={"orchestrator"}),
    )

Also provides prompt file loaders for VS Code prompt files
(``.github/prompts/*.prompt.md``) and Claude Code commands
(``.claude/commands/*.md``) — reusable slash-command prompts::

    from pytest_skill_engineering.core.evals import load_prompt_file, load_prompt_files

    # Single prompt file
    prompt = load_prompt_file(".github/prompts/review.prompt.md")
    # → {"name": "review", "body": "Review this code for...",
    #    "description": "...", "metadata": {...}}

    # Use the body as the test input
    result = await eval_run(agent, prompt["body"])

    # Load all from directory
    prompts = load_prompt_files(".github/prompts/")
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
    """Load a ``.agent.md`` or ``.md`` file into a custom agent dict.

    Parses YAML frontmatter with PyYAML for structured metadata
    (``description``, ``tools``, ``handoffs``, ``maturity``, etc.) and uses
    the markdown body as the agent's ``prompt``.

    Args:
        path: Path to the ``.agent.md`` or ``.md`` file.
        overrides: Additional fields to merge into the result. Use this
            to set ``tools``, ``mcp_servers``, or ``infer`` fields that
            aren't in the agent file itself.

    Returns:
        Dict with keys:
            - ``name`` (str): Derived from filename.
            - ``prompt`` (str): Markdown body after frontmatter.
            - ``description`` (str): From frontmatter, empty if absent.
            - ``metadata`` (dict): Full parsed frontmatter dict.
        Compatible with :attr:`CopilotEval.custom_agents` and
        :meth:`Eval.from_agent_file`.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file has no content after frontmatter stripping.
    """
    path = Path(path)
    if not path.exists():
        msg = f"Eval file not found: {path}"
        raise FileNotFoundError(msg)

    content = path.read_text(encoding="utf-8")
    metadata, body = _extract_frontmatter(content)
    body = body.strip()

    if not body:
        msg = f"Eval file has no content after frontmatter: {path}"
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
        exclude: Eval names to skip.
        overrides: Per-agent override dicts keyed by agent name. Merged
            into each matching agent's config.

    Returns:
        List of custom agent dicts, sorted by name.

    Raises:
        FileNotFoundError: If the directory does not exist.
    """
    directory = Path(directory)
    if not directory.is_dir():
        msg = f"Eval directory not found: {directory}"
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


def _prompt_name_from_path(path: Path) -> str:
    """Derive prompt name from filename.

    ``review.prompt.md`` → ``review``
    ``code-review.md``   → ``code-review``
    """
    name = path.name
    if name.endswith(".prompt.md"):
        return name[: -len(".prompt.md")]
    return path.stem


def load_prompt_file(path: Path | str) -> dict[str, Any]:
    """Load a VS Code prompt file or Claude Code command file.

    Reads a ``.prompt.md`` file (VS Code: ``.github/prompts/``) or a plain
    ``.md`` command file (Claude Code: ``.claude/commands/``). Strips YAML
    frontmatter and returns the body — the text that is sent to the agent
    when a user invokes the slash command.

    Args:
        path: Path to the ``.prompt.md`` or ``.md`` file.

    Returns:
        Dict with keys ``name`` (str, derived from filename),
        ``body`` (str, the prompt text to pass to :func:`eval_run`),
        ``description`` (str, from frontmatter or empty), and
        ``metadata`` (dict, full frontmatter).

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file has no body after frontmatter stripping.

    Example::

        from pytest_skill_engineering import load_prompt_file

        # VS Code prompt file
        prompt = load_prompt_file(".github/prompts/review.prompt.md")
        result = await eval_run(agent, prompt["body"])

        # Claude Code command
        prompt = load_prompt_file(".claude/commands/review.md")
        result = await eval_run(agent, prompt["body"])
    """
    path = Path(path)
    if not path.exists():
        msg = f"Prompt file not found: {path}"
        raise FileNotFoundError(msg)

    content = path.read_text(encoding="utf-8")
    metadata, body = _extract_frontmatter(content)
    body = body.strip()

    if not body:
        msg = f"Prompt file has no body after frontmatter: {path}"
        raise ValueError(msg)

    return {
        "name": _prompt_name_from_path(path),
        "body": body,
        "description": metadata.get("description", ""),
        "metadata": metadata,
    }


def load_prompt_files(
    directory: Path | str,
    *,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Load all prompt files from a directory.

    Loads ``.prompt.md`` files (VS Code convention) and plain ``.md`` files
    (Claude Code convention). Sorted by name.

    Args:
        directory: Path to directory containing prompt files.
            Typically ``.github/prompts/`` (VS Code) or
            ``.claude/commands/`` (Claude Code).
        include: If set, only load prompts with these names.
        exclude: Prompt names to skip.

    Returns:
        List of prompt dicts (see :func:`load_prompt_file`), sorted by name.

    Raises:
        FileNotFoundError: If the directory does not exist.

    Example::

        from pytest_skill_engineering import load_prompt_files

        prompts = load_prompt_files(".github/prompts/")

        @pytest.mark.parametrize("prompt", prompts, ids=lambda p: p["name"])
        async def test_prompt_files(eval_run, agent, prompt):
            result = await eval_run(agent, prompt["body"])
            assert result.success
    """
    directory = Path(directory)
    if not directory.is_dir():
        msg = f"Prompt directory not found: {directory}"
        raise FileNotFoundError(msg)

    prompts: list[dict[str, Any]] = []
    seen: set[str] = set()

    # Load .prompt.md files first (VS Code convention)
    for path in sorted(directory.glob("*.prompt.md")):
        name = _prompt_name_from_path(path)
        if include is not None and name not in include:
            continue
        if exclude is not None and name in exclude:
            continue
        prompts.append(load_prompt_file(path))
        seen.add(name)

    # Also load plain .md files (Claude Code convention) if not already loaded
    for path in sorted(directory.glob("*.md")):
        if path.name.endswith(".prompt.md"):
            continue  # already handled above
        name = _prompt_name_from_path(path)
        if name in seen:
            continue
        if include is not None and name not in include:
            continue
        if exclude is not None and name in exclude:
            continue
        try:
            prompts.append(load_prompt_file(path))
            seen.add(name)
        except ValueError:
            continue  # skip empty files

    return sorted(prompts, key=lambda p: p["name"])


def _instruction_name_from_path(path: Path) -> str:
    """Derive instruction name from filename.

    ``coding-standards.instructions.md`` → ``coding-standards``
    ``copilot-instructions.md``          → ``copilot-instructions``
    ``AGENTS.md``                        → ``AGENTS``
    """
    name = path.name
    if name.endswith(".instructions.md"):
        return name[: -len(".instructions.md")]
    return path.stem


def load_instruction_file(path: Path | str) -> dict[str, Any]:
    """Load a custom instruction file.

    Supports VS Code instruction files (``.github/copilot-instructions.md``,
    ``*.instructions.md``), AGENTS.md (Codex), and CLAUDE.md (Claude Code).
    YAML frontmatter is stripped; ``applyTo`` field maps to the ``apply_to`` key.

    Args:
        path: Path to the instruction file.

    Returns:
        Dict with keys ``name`` (str), ``content`` (str, the instruction text),
        ``apply_to`` (str, glob pattern or empty), ``description`` (str),
        and ``metadata`` (dict, full frontmatter).

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file has no content after frontmatter stripping.
    """
    path = Path(path)
    if not path.exists():
        msg = f"Instruction file not found: {path}"
        raise FileNotFoundError(msg)

    content = path.read_text(encoding="utf-8")
    metadata, body = _extract_frontmatter(content)
    body = body.strip()

    if not body:
        msg = f"Instruction file has no content after frontmatter: {path}"
        raise ValueError(msg)

    return {
        "name": _instruction_name_from_path(path),
        "content": body,
        "apply_to": metadata.get("applyTo", ""),
        "description": metadata.get("description", ""),
        "metadata": metadata,
        "path": str(path),
    }


def load_instruction_files(
    directory: Path | str,
    *,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Load all instruction files from a directory.

    Loads ``*.instructions.md`` files and well-known files:
    ``copilot-instructions.md``, ``AGENTS.md``, ``CLAUDE.md``.
    Sorted by name.

    Args:
        directory: Path to directory (or parent) containing instruction files.
        include: If set, only load files with these names.
        exclude: File names to skip.

    Returns:
        List of instruction file dicts (see :func:`load_instruction_file`), sorted by name.

    Raises:
        FileNotFoundError: If the directory does not exist.
    """
    directory = Path(directory)
    if not directory.is_dir():
        msg = f"Instruction directory not found: {directory}"
        raise FileNotFoundError(msg)

    instructions: list[dict[str, Any]] = []
    seen: set[str] = set()

    # Load *.instructions.md files
    for path in sorted(directory.glob("*.instructions.md")):
        name = _instruction_name_from_path(path)
        if include is not None and name not in include:
            continue
        if exclude is not None and name in exclude:
            continue
        try:
            instructions.append(load_instruction_file(path))
            seen.add(name)
        except ValueError:
            continue  # skip empty files

    # Also check for well-known files: copilot-instructions.md, AGENTS.md, CLAUDE.md
    well_known = ["copilot-instructions.md", "AGENTS.md", "CLAUDE.md"]
    for filename in well_known:
        path = directory / filename
        if not path.exists():
            continue
        name = _instruction_name_from_path(path)
        if name in seen:
            continue
        if include is not None and name not in include:
            continue
        if exclude is not None and name in exclude:
            continue
        try:
            instructions.append(load_instruction_file(path))
            seen.add(name)
        except ValueError:
            continue  # skip empty files

    return sorted(instructions, key=lambda p: p["name"])
