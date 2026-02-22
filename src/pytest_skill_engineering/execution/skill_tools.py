"""Virtual tools for skill references.

When a skill has a references/ directory, these tools are auto-injected
to allow the agent to list and read reference documents on demand.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pytest_skill_engineering.core.skill import Skill


def get_skill_tools_schema(skill: Skill) -> list[dict[str, Any]]:
    """Generate OpenAI-compatible tool schemas for skill references.

    Args:
        skill: Skill with references to expose

    Returns:
        List of tool definitions in OpenAI function format
    """
    if not skill.has_references:
        return []

    return [
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


def execute_skill_tool(
    skill: Skill,
    tool_name: str,
    arguments: dict[str, Any],
) -> str:
    """Execute a skill reference tool.

    Args:
        skill: Skill containing the references
        tool_name: Either 'list_skill_references' or 'read_skill_reference'
        arguments: Tool arguments

    Returns:
        Tool result as string

    Raises:
        ValueError: If tool_name is unknown
        KeyError: If reference file not found
    """
    if tool_name == "list_skill_references":
        return _list_references(skill)
    elif tool_name == "read_skill_reference":
        filename = arguments.get("filename", "")
        return _read_reference(skill, filename)
    else:
        raise ValueError(f"Unknown skill tool: {tool_name}")


def is_skill_tool(tool_name: str) -> bool:
    """Check if a tool name is a skill reference tool."""
    return tool_name in ("list_skill_references", "read_skill_reference")


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
