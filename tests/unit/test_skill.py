"""Tests for core.skill module."""

from __future__ import annotations

import os
import stat
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, Literal

import pytest

from pytest_skill_engineering import load_skill
from pytest_skill_engineering.core.skill import Skill, SkillError, SkillMetadata


@pytest.fixture
def nested_reference_skill(tmp_path: Path) -> Path:
    directory = tmp_path / "nested-skill"
    references = directory / "references"
    (references / "commands" / "advanced").mkdir(parents=True)
    (references / "topics").mkdir()
    (directory / "SKILL.md").write_text(
        "---\nname: nested-skill\ndescription: Nested reference test\n---\n\n"
        "See [commands](references/commands/read.md).\n",
        encoding="utf-8",
    )
    for relative, content in {
        "overview.md": "# Overview",
        "commands/read.md": "# Read command",
        "commands/advanced/read.md": "# Advanced read command",
        "topics/read.md": "# Reading topics",
    }.items():
        references.joinpath(*relative.split("/")).write_text(content, encoding="utf-8")
    return directory


@pytest.mark.parametrize("loader", [Skill.from_path, load_skill])
def test_nested_references_preserve_relative_paths(
    nested_reference_skill: Path, loader: Callable[[Path | str], Skill]
) -> None:
    skill = loader(nested_reference_skill)
    assert skill.references == {
        "commands/advanced/read.md": "# Advanced read command",
        "commands/read.md": "# Read command",
        "overview.md": "# Overview",
        "topics/read.md": "# Reading topics",
    }
    assert skill.has_references
    assert list(skill.references) == sorted(skill.references)


@pytest.mark.parametrize("invalid", ["extension", "utf8", "empty"])
def test_nested_references_keep_file_validation(nested_reference_skill: Path, invalid: str) -> None:
    reference = nested_reference_skill / "references" / "commands" / "read.md"
    if invalid == "extension":
        reference.rename(reference.with_suffix(".txt"))
        message = r"only \.md files are allowed"
    elif invalid == "utf8":
        reference.write_bytes(b"\xff")
        message = "valid UTF-8 text"
    else:
        reference.write_text(" \n", encoding="utf-8")
        message = "must not be empty"
    with pytest.raises(SkillError, match=message):
        load_skill(nested_reference_skill)


@pytest.mark.parametrize("operation", ["list", "read", "stat"])
def test_unreadable_nested_references_fail_with_the_path(
    nested_reference_skill: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    reference = nested_reference_skill / "references" / "commands" / "read.md"
    directory = reference.parent
    if operation == "list":
        original = Path.iterdir

        def list_directory(path: Path) -> Iterator[Path]:
            if path == directory:
                raise PermissionError("Blocked directory")
            return original(path)

        monkeypatch.setattr(Path, "iterdir", list_directory)
        expected_path = directory
    elif operation == "read":
        original_read = Path.read_text

        def read_file(path: Path, *args: Any, **kwargs: Any) -> str:
            if path == reference:
                raise PermissionError("Blocked reference")
            return original_read(path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", read_file)
        expected_path = reference
    else:
        original_stat = Path.stat

        def inspect(path: Path, *args: Any, **kwargs: Any) -> os.stat_result:
            if path == reference:
                raise PermissionError("Blocked inspection")
            return original_stat(path, *args, **kwargs)

        monkeypatch.setattr(Path, "stat", inspect)
        expected_path = reference
    with pytest.raises(SkillError) as error:
        load_skill(nested_reference_skill)
    assert str(expected_path) in str(error.value)
    assert "Blocked" in str(error.value)


def test_nonregular_nested_reference_fails_before_reading(
    nested_reference_skill: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reference = nested_reference_skill / "references" / "commands" / "read.md"
    original_stat = Path.stat

    def inspect(path: Path, *args: Any, **kwargs: Any) -> os.stat_result:
        if path == reference:
            return os.stat_result((stat.S_IFIFO, 0, 0, 1, 0, 0, 0, 0, 0, 0))
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", inspect)
    with pytest.raises(SkillError, match="must be a file"):
        load_skill(nested_reference_skill)


def _link_directory(link: Path, target: Path, kind: Literal["symlink", "junction"]) -> None:
    if kind == "symlink":
        link.symlink_to(target, target_is_directory=True)
    else:
        subprocess.run(
            [os.environ["COMSPEC"], "/c", "mklink", "/J", str(link), str(target)],
            check=True,
            capture_output=True,
        )


@pytest.mark.parametrize(
    "kind",
    [
        "symlink",
        pytest.param("junction", marks=pytest.mark.skipif(os.name != "nt", reason="Windows")),
    ],
)
@pytest.mark.parametrize("target_kind", ["internal", "outside", "cycle", "root-outside"])
def test_reference_directory_links_are_contained_and_cycle_checked(
    nested_reference_skill: Path,
    tmp_path: Path,
    kind: Literal["symlink", "junction"],
    target_kind: str,
) -> None:
    references = nested_reference_skill / "references"
    if target_kind == "internal":
        target = references / "commands"
    elif target_kind == "cycle":
        target = references
    else:
        target = tmp_path / "outside"
        target.mkdir()
        (target / "secret.md").write_text("# Not a skill reference", encoding="utf-8")
    if target_kind == "root-outside":
        # Use a fresh skill so references/ itself can be a link.
        skill = tmp_path / "linked-root"
        skill.mkdir()
        (skill / "SKILL.md").write_text(
            "---\nname: linked-root\ndescription: Linked root test\n---\n\n# Instructions",
            encoding="utf-8",
        )
        link = skill / "references"
    else:
        skill = nested_reference_skill
        link = references / "linked"
    _link_directory(link, target, kind)
    try:
        if target_kind == "internal":
            loaded = load_skill(skill)
            assert loaded.references["linked/read.md"] == "# Read command"
            assert loaded.references["linked/advanced/read.md"] == "# Advanced read command"
        else:
            message = "cycle" if target_kind == "cycle" else "escapes its root"
            with pytest.raises(SkillError, match=message):
                load_skill(skill)
    finally:
        if kind == "symlink":
            link.unlink()
        else:
            link.rmdir()


@pytest.mark.parametrize("target_kind", ["internal", "outside", "broken", "cycle"])
def test_reference_file_links_are_contained_and_resolvable(
    nested_reference_skill: Path, tmp_path: Path, target_kind: str
) -> None:
    references = nested_reference_skill / "references"
    link = references / "linked.md"
    if target_kind == "internal":
        target = references / "commands" / "read.md"
    elif target_kind == "cycle":
        target = link
    else:
        target = tmp_path / "outside.md"
        if target_kind == "outside":
            target.write_text("# Not a skill reference", encoding="utf-8")
    link.symlink_to(target)
    try:
        if target_kind == "internal":
            assert load_skill(nested_reference_skill).references["linked.md"] == "# Read command"
        else:
            message = "escapes its root" if target_kind == "outside" else "Cannot resolve"
            with pytest.raises(SkillError, match=message):
                load_skill(nested_reference_skill)
    finally:
        link.unlink()


def test_skill_name_rejects_trailing_hyphen() -> None:
    """Name must not end with a hyphen per Eval Skills naming rules."""
    with pytest.raises(SkillError, match="Invalid skill name"):
        SkillMetadata(name="bad-name-", description="desc")


def test_skill_name_rejects_consecutive_hyphens() -> None:
    """Name must not contain consecutive hyphens per Eval Skills naming rules."""
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
