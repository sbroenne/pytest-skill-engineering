"""Tests for core.skill module."""

from pathlib import Path

import pytest

from pytest_skill_engineering.core.skill import Skill, SkillError, SkillMetadata


def test_skill_name_rejects_trailing_hyphen() -> None:
    """Name must not end with a hyphen per Agent Skills naming rules."""
    with pytest.raises(SkillError, match="Invalid skill name"):
        SkillMetadata(name="bad-name-", description="desc")


def test_skill_name_rejects_consecutive_hyphens() -> None:
    """Name must not contain consecutive hyphens per Agent Skills naming rules."""
    with pytest.raises(SkillError, match="Invalid skill name"):
        SkillMetadata(name="bad--name", description="desc")


def test_skill_name_must_match_directory_name(tmp_path: Path) -> None:
    """SKILL.md frontmatter name must match the containing directory name."""
    skill_dir = tmp_path / "correct-dir"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: wrong-dir\ndescription: test skill\n---\n\n# Test",
        encoding="utf-8",
    )

    with pytest.raises(SkillError, match="must match directory name"):
        Skill.from_path(skill_dir)


def test_references_must_be_markdown_files(tmp_path: Path) -> None:
    """references/ only accepts markdown files."""
    skill_dir = tmp_path / "ref-skill"
    refs_dir = skill_dir / "references"
    refs_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: ref-skill\ndescription: test skill\n---\n\n# Test",
        encoding="utf-8",
    )
    (refs_dir / "notes.txt").write_text("not markdown", encoding="utf-8")

    with pytest.raises(SkillError, match="only \\.md files are allowed"):
        Skill.from_path(skill_dir)


def test_references_must_be_utf8_text(tmp_path: Path) -> None:
    """references/ files must be UTF-8 text."""
    skill_dir = tmp_path / "utf8-skill"
    refs_dir = skill_dir / "references"
    refs_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: utf8-skill\ndescription: test skill\n---\n\n# Test",
        encoding="utf-8",
    )
    (refs_dir / "bad.md").write_bytes(b"\xff\xfe\xfd")

    with pytest.raises(SkillError, match="valid UTF-8 text"):
        Skill.from_path(skill_dir)


def test_references_must_not_be_empty(tmp_path: Path) -> None:
    """references/ markdown files must not be empty."""
    skill_dir = tmp_path / "empty-ref-skill"
    refs_dir = skill_dir / "references"
    refs_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: empty-ref-skill\ndescription: test skill\n---\n\n# Test",
        encoding="utf-8",
    )
    (refs_dir / "empty.md").write_text("  \n", encoding="utf-8")

    with pytest.raises(SkillError, match="must not be empty"):
        Skill.from_path(skill_dir)


def test_invalid_frontmatter_yaml_raises(tmp_path: Path) -> None:
    """Invalid YAML frontmatter should raise a SkillError."""
    skill_dir = tmp_path / "broken-yaml-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: broken-yaml-skill\ndescription: [unclosed\n---\n\n# Test",
        encoding="utf-8",
    )

    with pytest.raises(SkillError, match="Invalid SKILL.md frontmatter"):
        Skill.from_path(skill_dir)
