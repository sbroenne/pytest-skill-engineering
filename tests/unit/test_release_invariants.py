"""Deterministic release and workflow invariant checks."""

from __future__ import annotations

import tomllib
from importlib.metadata import distribution
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_project_version_is_pinned_to_2_1_0() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == "2.1.0"


def test_release_workflow_builds_and_validates_artifact_version() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "uv build" in workflow
    assert "pytest_copilot.__version__" in workflow
    assert "Installed wheel version mismatch" in workflow
    assert 'expected_name = "pytest-copilot"' in workflow
    assert 'wheel_metadata["Name"]' in workflow
    assert 'sdist_metadata["Name"]' in workflow
    assert "Artifact name mismatch" in workflow


def test_distribution_registers_only_current_command_and_plugin() -> None:
    package = distribution("pytest-copilot")
    assert package.metadata["Name"] == "pytest-copilot"
    commands = {
        entry.name: entry.value
        for entry in package.entry_points
        if entry.group == "console_scripts"
    }
    assert commands == {"pytest-copilot": "pytest_copilot.onboarding:main"}
    plugins = {
        entry.name: entry.value for entry in package.entry_points if entry.group == "pytest11"
    }
    assert plugins == {"aitest": "pytest_copilot.plugin"}


def test_docs_workflow_examples_reference_current_release_tag() -> None:
    workflow = (ROOT / ".github" / "workflows" / "docs.yml").read_text(encoding="utf-8")
    assert "v2.1.0" in workflow


def test_github_release_job_selects_repository_without_checkout() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    release_job = workflow.split("\n  github-release:", 1)[1].split("\n  deploy-docs:", 1)[0]
    assert "GH_REPO: ${{ github.repository }}" in release_job
