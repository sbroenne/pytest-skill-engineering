"""Agent Skills support following agentskills.io specification.

Skills are domain-specific knowledge modules that enhance agent capabilities.
A skill consists of:
- SKILL.md file with YAML frontmatter (metadata) and markdown body (instructions)
- Optional references/ directory with additional documentation

Example SKILL.md:
    ---
    name: my-skill
    description: What this skill does
    version: 1.0.0
    ---

    # Skill Instructions

    Content that gets prepended to the agent's system prompt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class SkillError(Exception):
    """Error loading or validating a skill."""


@dataclass(slots=True, frozen=True)
class SkillMetadata:
    """Metadata from SKILL.md frontmatter.

    Required fields per agentskills.io spec:
    - name: lowercase letters and hyphens only, 1-64 chars
    - description: what the skill does, max 1024 chars

    Optional fields:
    - version: semantic version string
    - license: SPDX license identifier
    - tags: list of categorization tags
    """

    name: str
    description: str
    version: str | None = None
    license: str | None = None
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate metadata per agentskills.io spec."""
        # Name validation: lowercase letters and hyphens, 1-64 chars
        if not self.name:
            raise SkillError("Skill name is required")
        if len(self.name) > 64:
            raise SkillError(f"Skill name exceeds 64 characters: {len(self.name)}")
        if not re.match(r"^[a-z][a-z0-9-]*$", self.name):
            raise SkillError(
                f"Invalid skill name '{self.name}': must be lowercase letters, "
                "numbers, and hyphens, starting with a letter"
            )

        # Description validation
        if not self.description:
            raise SkillError("Skill description is required")
        if len(self.description) > 1024:
            raise SkillError(f"Skill description exceeds 1024 characters: {len(self.description)}")


@dataclass(slots=True)
class Skill:
    """An Agent Skill loaded from a SKILL.md file.

    Skills provide domain knowledge to agents by:
    1. Prepending instructions to the system prompt
    2. Optionally providing reference documents via virtual tools

    Example:
        skill = Skill.from_path(Path("skills/my-skill"))
        agent = Agent(provider=provider, skill=skill)
    """

    path: Path
    metadata: SkillMetadata
    content: str
    references: dict[str, str] = field(default_factory=dict)

    @property
    def name(self) -> str:
        """Skill name from metadata."""
        return self.metadata.name

    @property
    def description(self) -> str:
        """Skill description from metadata."""
        return self.metadata.description

    @property
    def has_references(self) -> bool:
        """Whether this skill has reference documents."""
        return bool(self.references)

    @classmethod
    def from_path(cls, path: Path | str) -> Skill:
        """Load a skill from a directory containing SKILL.md.

        Args:
            path: Path to skill directory or SKILL.md file

        Returns:
            Loaded Skill instance

        Raises:
            SkillError: If skill cannot be loaded or is invalid
        """
        path = Path(path)

        # Handle both directory and direct file paths
        if path.is_file() and path.name == "SKILL.md":
            skill_file = path
            skill_dir = path.parent
        elif path.is_dir():
            skill_file = path / "SKILL.md"
            skill_dir = path
        else:
            raise SkillError(f"Invalid skill path: {path}")

        if not skill_file.exists():
            raise SkillError(f"SKILL.md not found: {skill_file}")

        # Parse SKILL.md
        raw_content = skill_file.read_text(encoding="utf-8")
        metadata, content = _parse_skill_md(raw_content)

        # Load references if directory exists
        references: dict[str, str] = {}
        refs_dir = skill_dir / "references"
        if refs_dir.is_dir():
            references = _load_references(refs_dir)

        return cls(
            path=skill_dir,
            metadata=metadata,
            content=content,
            references=references,
        )


def _parse_skill_md(content: str) -> tuple[SkillMetadata, str]:
    """Parse SKILL.md into metadata and body content.

    Format:
        ---
        name: my-skill
        description: What this skill does
        version: 1.0.0
        ---

        # Body content here
    """
    # Match YAML frontmatter between --- delimiters
    frontmatter_pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
    match = re.match(frontmatter_pattern, content.strip(), re.DOTALL)

    if not match:
        raise SkillError(
            "Invalid SKILL.md format: must have YAML frontmatter between --- delimiters"
        )

    frontmatter_text = match.group(1)
    body = match.group(2).strip()

    # Parse YAML frontmatter manually (to avoid PyYAML dependency)
    frontmatter = _parse_simple_yaml(frontmatter_text)

    # Extract required fields
    name = frontmatter.get("name")
    description = frontmatter.get("description")

    if not name:
        raise SkillError("SKILL.md missing required field: name")
    if not description:
        raise SkillError("SKILL.md missing required field: description")

    # Extract optional fields
    version = frontmatter.get("version")
    license_str = frontmatter.get("license")
    tags_raw = frontmatter.get("tags", [])

    # Handle tags (could be string or list)
    if isinstance(tags_raw, str):
        tags = tuple(t.strip() for t in tags_raw.split(",") if t.strip())
    elif isinstance(tags_raw, list):
        tags = tuple(str(t) for t in tags_raw)
    else:
        tags = ()

    metadata = SkillMetadata(
        name=str(name),
        description=str(description),
        version=str(version) if version else None,
        license=str(license_str) if license_str else None,
        tags=tags,
    )

    return metadata, body


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    """Parse simple YAML without PyYAML dependency.

    Supports:
    - Simple key: value pairs
    - Lists (- item)
    - Quoted strings

    Does not support:
    - Nested objects
    - Multi-line strings (except with >- or |-)
    - Complex types
    """
    result: dict[str, Any] = {}
    current_key: str | None = None
    current_list: list[str] | None = None

    for line in text.split("\n"):
        stripped = line.strip()

        # Skip empty lines and comments
        if not stripped or stripped.startswith("#"):
            continue

        # Check for list item
        if stripped.startswith("- "):
            if current_list is not None:
                item = stripped[2:].strip()
                # Remove quotes if present
                if (item.startswith('"') and item.endswith('"')) or (
                    item.startswith("'") and item.endswith("'")
                ):
                    item = item[1:-1]
                current_list.append(item)
            continue

        # Check for key: value pair
        if ":" in stripped:
            # Save previous list if any
            if current_key and current_list is not None:
                result[current_key] = current_list

            # Reset list state
            current_list = None

            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()

            # Remove quotes from value
            if value and (
                (value.startswith('"') and value.endswith('"'))
                or (value.startswith("'") and value.endswith("'"))
            ):
                value = value[1:-1]

            if value:
                result[key] = value
                current_key = None
            else:
                # Empty value might mean list follows
                current_key = key
                current_list = []

    # Save final list if any
    if current_key and current_list is not None:
        result[current_key] = current_list

    return result


def _load_references(refs_dir: Path) -> dict[str, str]:
    """Load all files from references/ directory.

    Returns:
        Dict mapping filename to content
    """
    references: dict[str, str] = {}

    for file_path in refs_dir.iterdir():
        if file_path.is_file():
            try:
                content = file_path.read_text(encoding="utf-8")
                references[file_path.name] = content
            except UnicodeDecodeError:
                # Skip binary files
                pass

    return references


def load_skill(path: Path | str) -> Skill:
    """Load a skill from a path.

    Convenience function wrapping Skill.from_path().

    Args:
        path: Path to skill directory or SKILL.md file

    Returns:
        Loaded Skill instance
    """
    return Skill.from_path(path)
