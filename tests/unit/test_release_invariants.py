"""Deterministic release and workflow invariant checks."""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_project_version_is_pinned_to_0_6_19() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == "0.6.19"


def test_release_workflow_builds_and_validates_artifact_version() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "uv build" in workflow
    assert "pytest_skill_engineering.__version__" in workflow
    assert "Installed wheel version mismatch" in workflow


def test_docs_workflow_examples_reference_current_release_tag() -> None:
    workflow = (ROOT / ".github" / "workflows" / "docs.yml").read_text(encoding="utf-8")
    assert "v0.6.19" in workflow
