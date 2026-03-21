"""Eval Skills support following agentskills.io specification.

Skills are domain-specific knowledge modules that enhance agent capabilities.
A skill consists of:
- SKILL.md file with YAML frontmatter (metadata) and markdown body (instructions)
- Optional references/ directory with additional documentation (.md files)
- Optional scripts/ directory with executable scripts (.py, .sh, .js, .bash)
- Optional assets/ directory with supporting files (any type)

Example SKILL.md:
    ---
    name: my-skill
    description: What this skill does
    version: 1.0.0
    license: Apache-2.0
    compatibility: Requires Python 3.11+
    allowed-tools: bash python
    metadata:
      author: my-team
      category: development
    ---

    # Skill Instructions

    Content that gets prepended to the agent's system prompt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import frontmatter


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
    - compatibility: environment requirements, max 500 chars
    - metadata: arbitrary key-value pairs (stored as tuple of tuples for frozen compat)
    - allowed_tools: tool names the skill is designed to work with
    """

    name: str
    description: str
    version: str | None = None
    license: str | None = None
    tags: tuple[str, ...] = ()
    compatibility: str | None = None
    metadata_entries: tuple[tuple[str, str], ...] = ()
    allowed_tools: tuple[str, ...] = ()

    @property
    def metadata_dict(self) -> dict[str, str]:
        """Return metadata entries as a dict for convenient access."""
        return dict(self.metadata_entries)

    def __post_init__(self) -> None:
        """Validate metadata per agentskills.io spec."""
        # Name validation: lowercase letters, numbers, and hyphens, 1-64 chars
        # Must not start/end with hyphen or contain consecutive hyphens.
        if not self.name:
            raise SkillError("Skill name is required")
        if len(self.name) > 64:
            raise SkillError(f"Skill name exceeds 64 characters: {len(self.name)}")
        if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", self.name):
            raise SkillError(
                f"Invalid skill name '{self.name}': must be lowercase letters, "
                "numbers, and hyphens (no leading/trailing/consecutive hyphens)"
            )

        # Description validation
        if not self.description:
            raise SkillError("Skill description is required")
        if len(self.description) > 1024:
            raise SkillError(f"Skill description exceeds 1024 characters: {len(self.description)}")

        # Compatibility validation
        if self.compatibility is not None and len(self.compatibility) > 500:
            raise SkillError(
                f"Skill compatibility exceeds 500 characters: {len(self.compatibility)}"
            )

        # Allowed tools validation
        for tool in self.allowed_tools:
            if not tool or not tool.strip():
                raise SkillError("allowed_tools entries must be non-empty strings")


@dataclass(slots=True)
class Skill:
    """An Eval Skill loaded from a SKILL.md file.

    Skills provide domain knowledge to agents by:
    1. Prepending instructions to the system prompt
    2. Optionally providing reference documents via virtual tools

    Example:
        skill = Skill.from_path(Path("skills/my-skill"))
        agent = Eval(provider=provider, skill=skill)
    """

    path: Path
    metadata: SkillMetadata
    content: str
    references: dict[str, str] = field(default_factory=dict)
    scripts: dict[str, str] = field(default_factory=dict)
    assets: tuple[str, ...] = ()

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

    @property
    def has_scripts(self) -> bool:
        """Whether this skill has executable scripts."""
        return bool(self.scripts)

    @property
    def has_assets(self) -> bool:
        """Whether this skill has asset files."""
        return bool(self.assets)

    @property
    def assets_dir(self) -> Path | None:
        """Path to assets directory, if it exists."""
        d = self.path / "assets"
        return d if d.is_dir() else None

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
        if metadata.name != skill_dir.name:
            raise SkillError(
                f"Skill name '{metadata.name}' must match directory name '{skill_dir.name}'"
            )

        # Load references if directory exists
        references: dict[str, str] = {}
        refs_dir = skill_dir / "references"
        if refs_dir.is_dir():
            references = _load_references(refs_dir)

        # Load scripts if directory exists
        scripts: dict[str, str] = {}
        scripts_dir = skill_dir / "scripts"
        if scripts_dir.is_dir():
            scripts = _load_scripts(scripts_dir)

        # Discover assets if directory exists
        assets: tuple[str, ...] = ()
        assets_dir = skill_dir / "assets"
        if assets_dir.is_dir():
            assets = tuple(sorted(f.name for f in assets_dir.iterdir() if f.is_file()))

        return cls(
            path=skill_dir,
            metadata=metadata,
            content=content,
            references=references,
            scripts=scripts,
            assets=assets,
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
    if not content.lstrip().startswith("---"):
        raise SkillError(
            "Invalid SKILL.md format: must have YAML frontmatter between --- delimiters"
        )
    try:
        post = frontmatter.loads(content)
    except Exception as exc:
        raise SkillError(f"Invalid SKILL.md frontmatter: {exc}") from exc
    body = post.content.strip()
    metadata_raw = post.metadata

    # Extract required fields
    name = metadata_raw.get("name")
    description = metadata_raw.get("description")

    if not name:
        raise SkillError("SKILL.md missing required field: name")
    if not description:
        raise SkillError("SKILL.md missing required field: description")

    # Extract optional fields
    version = metadata_raw.get("version")
    license_str = metadata_raw.get("license")
    tags_raw = metadata_raw.get("tags", [])
    compatibility = metadata_raw.get("compatibility")
    metadata_entries_raw = metadata_raw.get("metadata", {})
    allowed_tools_raw = metadata_raw.get("allowed-tools", "")

    # Handle tags (could be string or list)
    if isinstance(tags_raw, str):
        tags = tuple(t.strip() for t in tags_raw.split(",") if t.strip())
    elif isinstance(tags_raw, list):
        tags = tuple(str(t) for t in tags_raw)
    else:
        tags = ()

    # Handle metadata entries (dict → tuple of tuples for frozen dataclass)
    if isinstance(metadata_entries_raw, dict):
        metadata_entries = tuple((str(k), str(v)) for k, v in metadata_entries_raw.items())
    else:
        metadata_entries = ()

    # Handle allowed-tools (space-delimited string or list)
    if isinstance(allowed_tools_raw, str):
        allowed_tools = tuple(t for t in allowed_tools_raw.split() if t)
    elif isinstance(allowed_tools_raw, list):
        allowed_tools = tuple(str(t) for t in allowed_tools_raw)
    else:
        allowed_tools = ()

    metadata = SkillMetadata(
        name=str(name),
        description=str(description),
        version=str(version) if version else None,
        license=str(license_str) if license_str else None,
        tags=tags,
        compatibility=str(compatibility) if compatibility else None,
        metadata_entries=metadata_entries,
        allowed_tools=allowed_tools,
    )

    return metadata, body


def _load_references(refs_dir: Path) -> dict[str, str]:
    """Load all files from references/ directory.

    Returns:
        Dict mapping filename to content
    """
    references: dict[str, str] = {}

    for file_path in refs_dir.iterdir():
        if not file_path.is_file():
            raise SkillError(f"Invalid references entry (must be a file): {file_path.name}")
        if file_path.suffix.lower() != ".md":
            raise SkillError(
                f"Invalid reference file '{file_path.name}': only .md files are allowed"
            )
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise SkillError(f"Reference file must be valid UTF-8 text: {file_path.name}") from exc
        if not content.strip():
            raise SkillError(f"Reference file must not be empty: {file_path.name}")
        references[file_path.name] = content

    return references


_SCRIPT_EXTENSIONS = frozenset({".py", ".sh", ".js", ".bash"})


def _load_scripts(scripts_dir: Path) -> dict[str, str]:
    """Load executable scripts from scripts/ directory.

    Supports .py, .sh, .js, and .bash files.

    Returns:
        Dict mapping filename to content
    """
    scripts: dict[str, str] = {}

    for file_path in scripts_dir.iterdir():
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in _SCRIPT_EXTENSIONS:
            continue
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise SkillError(f"Script file must be valid UTF-8 text: {file_path.name}") from exc
        if not content.strip():
            raise SkillError(f"Script file must not be empty: {file_path.name}")
        scripts[file_path.name] = content

    return scripts


def load_skill(path: Path | str) -> Skill:
    """Load a skill from a path.

    Convenience function wrapping Skill.from_path().

    Args:
        path: Path to skill directory or SKILL.md file

    Returns:
        Loaded Skill instance
    """
    return Skill.from_path(path)
