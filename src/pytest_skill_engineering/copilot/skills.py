"""Validate explicit skill inputs and verify native SDK availability before sending."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from pytest_skill_engineering.core.result import DiscoveredSkill, SkillDiscovery
from pytest_skill_engineering.core.skill import Skill, SkillError

if TYPE_CHECKING:
    from copilot.session import CopilotSession

logger = logging.getLogger(__name__)


def requested_skill_files(directories: list[str]) -> dict[Path, str]:
    """Validate individual skill directories or parents of immediate skill directories.

    Relative directories are resolved from the Python caller's current directory,
    then passed to the SDK as absolute paths.
    """
    requested: dict[Path, str] = {}
    names: dict[str, Path] = {}
    for raw_directory in directories:
        if not isinstance(raw_directory, str) or not raw_directory.strip():
            raise SkillError("skill_directories entries must be non-empty directory paths")
        directory = Path(raw_directory).resolve()
        if not directory.is_dir():
            raise SkillError(
                f"Requested skill directory does not exist or is not a directory: {directory}"
            )
        try:
            candidates = (
                [directory]
                if (directory / "SKILL.md").exists()
                else [
                    child
                    for child in sorted(directory.iterdir())
                    if child.is_dir() and (child / "SKILL.md").exists()
                ]
            )
            if not candidates:
                raise SkillError(f"No SKILL.md found in requested skill directory: {directory}")
            for candidate in candidates:
                skill = Skill.from_path(candidate)
                path = (skill.path / "SKILL.md").resolve()
                if skill.name in names and names[skill.name] != path:
                    raise SkillError(
                        f"Duplicate requested skill name '{skill.name}': "
                        f"{names[skill.name]} and {path}"
                    )
                names[skill.name] = path
                requested[path] = skill.name
        except OSError as exc:
            raise SkillError(f"Cannot read requested skill directory {directory}: {exc}") from exc
    return requested


async def discover_requested_skills(
    session: CopilotSession,
    requested: dict[Path, str],
    disabled: list[str],
    evidence: SkillDiscovery,
) -> None:
    """Record SDK discovery and reject missing or unexpectedly disabled requested skills."""
    await session.rpc.skills.ensure_loaded()
    diagnostics = await session.rpc.skills.reload()
    evidence.warnings = list(diagnostics.warnings)
    evidence.errors = list(diagnostics.errors)
    for warning in evidence.warnings:
        logger.warning("SDK skill discovery: %s", warning)
    listed = await session.rpc.skills.list()
    evidence.skills = [
        DiscoveredSkill(
            name=skill.name,
            description=skill.description,
            source=skill.source.value,
            enabled=skill.enabled,
            user_invocable=skill.user_invocable,
            path=skill.path,
            plugin_name=skill.plugin_name,
            command_name=skill.command_name,
            argument_hint=skill.argument_hint,
        )
        for skill in listed.skills
    ]
    evidence.complete = True
    available = {
        (Path(skill.path).resolve(), skill.name): skill
        for skill in evidence.skills
        if skill.path is not None
    }
    for path, name in requested.items():
        skill = available.get((path, name))
        if skill is None:
            evidence.errors.append(
                f"Requested skill '{name}' was not discovered by the SDK: {path}"
            )
        elif not skill.enabled and name not in disabled:
            evidence.errors.append(f"Requested skill '{name}' is unexpectedly disabled: {path}")
    if evidence.errors:
        raise SkillError("Skill setup failed before model execution: " + "; ".join(evidence.errors))
