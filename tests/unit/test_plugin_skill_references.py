"""Deterministic tests for plugin skill reference validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from pytest_skill_engineering.core.plugin import _validate_skill_reference_names
from pytest_skill_engineering.core.skill import Skill


def _make_skill(root: Path, name: str, reference_name: str) -> Skill:
    skill_dir = root / name
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {name} description\n---\n# {name}\n",
        encoding="utf-8",
    )
    refs = skill_dir / "references"
    refs.mkdir()
    (refs / reference_name).write_text(f"# {reference_name}\n", encoding="utf-8")
    return Skill.from_path(skill_dir)


def test_duplicate_skill_reference_basenames_are_rejected(tmp_path: Path) -> None:
    skill_a = _make_skill(tmp_path, "alpha", "guide.md")
    skill_b = _make_skill(tmp_path, "beta", "guide.md")

    with pytest.raises(ValueError, match="Duplicate skill reference filename 'guide.md'"):
        _validate_skill_reference_names([skill_a, skill_b])


def test_unique_skill_reference_basenames_are_allowed(tmp_path: Path) -> None:
    skill_a = _make_skill(tmp_path, "alpha", "guide.md")
    skill_b = _make_skill(tmp_path, "beta", "lookup.md")

    _validate_skill_reference_names([skill_a, skill_b])
