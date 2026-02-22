"""Custom agent file loader for ``.agent.md`` files.

Loads VS Code custom agent definitions into ``CustomAgentConfig``-compatible
dicts for use with :attr:`CopilotAgent.custom_agents`.

.. note::
    The implementation lives in :mod:`pytest_skill_engineering.core.agents` and is
    re-exported here for backward compatibility.  Import from either location:

    - ``from pytest_skill_engineering.copilot.agents import load_custom_agent``  (legacy)
    - ``from pytest_skill_engineering.core.agents import load_custom_agent``  (preferred)
    - ``from pytest_skill_engineering import load_custom_agent``  (top-level)

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

    from pytest_skill_engineering.copilot.agents import load_custom_agent, load_custom_agents

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

from pytest_skill_engineering.core.agents import (
    _extract_frontmatter,
    _name_from_path,
    load_custom_agent,
    load_custom_agents,
)

__all__ = [
    "_extract_frontmatter",
    "_name_from_path",
    "load_custom_agent",
    "load_custom_agents",
]
