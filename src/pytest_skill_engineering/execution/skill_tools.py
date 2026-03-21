"""Virtual tools for skill references, scripts, and assets.

When a skill has a references/, scripts/, or assets/ directory, these tools
are auto-injected to allow the agent to list and read content on demand.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pytest_skill_engineering.core.skill import Skill


def get_skill_tools_schema(skill: Skill) -> list[dict[str, Any]]:
    """Generate OpenAI-compatible tool schemas for skill virtual tools.

    Args:
        skill: Skill with references/scripts/assets to expose

    Returns:
        List of tool definitions in OpenAI function format
    """
    tools: list[dict[str, Any]] = []

    if skill.has_references:
        tools.extend(
            [
                {
                    "type": "function",
                    "function": {
                        "name": "list_skill_references",
                        "description": (
                            f"List available reference documents for the '{skill.name}' skill. "
                            "Returns filenames that can be read with read_skill_reference."
                        ),
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": [],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "read_skill_reference",
                        "description": (
                            f"Read a reference document from the '{skill.name}' skill. "
                            "Use list_skill_references first to see available files."
                        ),
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "filename": {
                                    "type": "string",
                                    "description": "Name of the reference file to read",
                                },
                            },
                            "required": ["filename"],
                        },
                    },
                },
            ]
        )

    if skill.has_scripts:
        tools.extend(
            [
                {
                    "type": "function",
                    "function": {
                        "name": "list_skill_scripts",
                        "description": (
                            f"List available scripts for the '{skill.name}' skill. "
                            "Returns filenames that can be read with read_skill_script."
                        ),
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": [],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "read_skill_script",
                        "description": (
                            f"Read a script from the '{skill.name}' skill. "
                            "Use list_skill_scripts first to see available files."
                        ),
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "filename": {
                                    "type": "string",
                                    "description": "Name of the script file to read",
                                },
                            },
                            "required": ["filename"],
                        },
                    },
                },
            ]
        )

    if skill.has_assets:
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "list_skill_assets",
                    "description": (
                        f"List available asset files for the '{skill.name}' skill. "
                        "Returns filenames of supporting assets."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            }
        )

    return tools


def execute_skill_tool(
    skill: Skill,
    tool_name: str,
    arguments: dict[str, Any],
) -> str:
    """Execute a skill virtual tool.

    Args:
        skill: Skill containing the resources
        tool_name: Tool name to execute
        arguments: Tool arguments

    Returns:
        Tool result as string

    Raises:
        ValueError: If tool_name is unknown
        KeyError: If requested file not found
    """
    if tool_name == "list_skill_references":
        return _list_references(skill)
    elif tool_name == "read_skill_reference":
        filename = arguments.get("filename", "")
        return _read_reference(skill, filename)
    elif tool_name == "list_skill_scripts":
        return _list_scripts(skill)
    elif tool_name == "read_skill_script":
        filename = arguments.get("filename", "")
        return _read_script(skill, filename)
    elif tool_name == "list_skill_assets":
        return _list_assets(skill)
    else:
        raise ValueError(f"Unknown skill tool: {tool_name}")


_SKILL_TOOL_NAMES = frozenset(
    {
        "list_skill_references",
        "read_skill_reference",
        "list_skill_scripts",
        "read_skill_script",
        "list_skill_assets",
    }
)


def is_skill_tool(tool_name: str) -> bool:
    """Check if a tool name is a skill virtual tool."""
    return tool_name in _SKILL_TOOL_NAMES


def _list_references(skill: Skill) -> str:
    """List available reference files."""
    if not skill.references:
        return "No reference documents available."

    files = sorted(skill.references.keys())
    return "Available reference documents:\n" + "\n".join(f"- {f}" for f in files)


def _read_reference(skill: Skill, filename: str) -> str:
    """Read a specific reference file."""
    if not filename:
        return "Error: filename parameter is required"

    if filename not in skill.references:
        available = ", ".join(sorted(skill.references.keys()))
        return f"Error: Reference '{filename}' not found. Available: {available}"

    return skill.references[filename]


def _list_scripts(skill: Skill) -> str:
    """List available script files."""
    if not skill.scripts:
        return "No scripts available."

    files = sorted(skill.scripts.keys())
    return "Available scripts:\n" + "\n".join(f"- {f}" for f in files)


def _read_script(skill: Skill, filename: str) -> str:
    """Read a specific script file."""
    if not filename:
        return "Error: filename parameter is required"

    if filename not in skill.scripts:
        available = ", ".join(sorted(skill.scripts.keys()))
        return f"Error: Script '{filename}' not found. Available: {available}"

    return skill.scripts[filename]


def _list_assets(skill: Skill) -> str:
    """List available asset files."""
    if not skill.assets:
        return "No assets available."

    return "Available assets:\n" + "\n".join(f"- {f}" for f in skill.assets)
