"""Contracts for the first-run project experience."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import tomlkit

from pytest_skill_engineering.execution.cost import estimate_cost
from pytest_skill_engineering.onboarding import (
    DEFAULT_MODEL,
    DEFAULT_PRICING,
    PRICING_PATH,
    REPORT_OPTIONS,
    STARTER_TEST,
    STARTER_TEST_PATH,
    OnboardingError,
    check_project,
    configured_pyproject,
    initialize_project,
)


def test_initializer_creates_complete_starter_and_preserves_project_data(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "consumer"\nversion = "1.0.0"\n\n[tool.ruff]\nline-length = 88\n',
        encoding="utf-8",
    )

    starter, updated, pricing = initialize_project(tmp_path)

    assert starter == tmp_path / STARTER_TEST_PATH
    assert starter.read_text(encoding="utf-8") == STARTER_TEST
    parsed = tomlkit.parse(updated.read_text(encoding="utf-8"))
    assert parsed["project"]["name"] == "consumer"
    assert parsed["tool"]["ruff"]["line-length"] == 88
    pytest_options = parsed["tool"]["pytest"]["ini_options"]
    assert pytest_options["asyncio_mode"] == "auto"
    assert all(option in pytest_options["addopts"] for option in REPORT_OPTIONS)
    pricing_data = tomlkit.parse(pricing.read_text(encoding="utf-8"))
    assert dict(pricing_data["models"][DEFAULT_MODEL]) == DEFAULT_PRICING


def test_initializer_merges_unrelated_addopts(tmp_path: Path) -> None:
    source = """\
[tool.pytest.ini_options]
addopts = "-q --strict-markers"
"""
    configured = tomlkit.parse(configured_pyproject(source))
    addopts = configured["tool"]["pytest"]["ini_options"]["addopts"]
    assert addopts.startswith("-q --strict-markers")
    assert all(option in addopts for option in REPORT_OPTIONS)


def test_initializer_accepts_equivalent_array_options() -> None:
    source = """\
[tool.pytest.ini_options]
addopts = [
    "-q",
    "--aitest-summary-model",
    "copilot/gpt-5.6-sol",
    "--aitest-html=aitest-reports/report.html",
    "--aitest-json=aitest-reports/results.json",
]
"""
    configured = tomlkit.parse(configured_pyproject(source))
    addopts = configured["tool"]["pytest"]["ini_options"]["addopts"]
    assert list(addopts) == [
        "-q",
        "--aitest-summary-model",
        "copilot/gpt-5.6-sol",
        "--aitest-html=aitest-reports/report.html",
        "--aitest-json=aitest-reports/results.json",
    ]


@pytest.mark.parametrize(
    "source, expected",
    [
        (
            '[tool.pytest.ini_options]\nasyncio_mode = "strict"\n',
            "asyncio_mode conflicts",
        ),
        (
            '[tool.pytest.ini_options]\naddopts = "--aitest-html=custom/report.html"\n',
            "--aitest-html",
        ),
        (
            '[tool.pytest.ini_options]\naddopts = "--aitest-html=aitest-reports/report.html '
            '--aitest-html=custom/report.html"\n',
            "--aitest-html",
        ),
    ],
)
def test_initializer_refuses_configuration_conflicts(source: str, expected: str) -> None:
    with pytest.raises(OnboardingError, match=expected):
        configured_pyproject(source)


def test_initializer_refuses_to_overwrite_starter_without_mutating_config(
    tmp_path: Path,
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    original = '[project]\nname = "consumer"\nversion = "1.0.0"\n'
    pyproject.write_text(original, encoding="utf-8")
    starter = tmp_path / STARTER_TEST_PATH
    starter.parent.mkdir(parents=True)
    starter.write_text("# existing\n", encoding="utf-8")

    with pytest.raises(OnboardingError, match="refusing to overwrite"):
        initialize_project(tmp_path)

    assert pyproject.read_text(encoding="utf-8") == original
    assert starter.read_text(encoding="utf-8") == "# existing\n"


def test_initializer_preserves_existing_model_pricing(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "consumer"\nversion = "1.0.0"\n',
        encoding="utf-8",
    )
    pricing = tmp_path / PRICING_PATH
    pricing.write_text(
        '[models]\n"gpt-5.6-sol" = { input = 1.0, output = 2.0 }\n',
        encoding="utf-8",
    )

    initialize_project(tmp_path)

    parsed = tomlkit.parse(pricing.read_text(encoding="utf-8"))
    assert parsed["models"][DEFAULT_MODEL]["input"] == 1.0
    assert parsed["models"][DEFAULT_MODEL]["output"] == 2.0


def test_generated_pricing_enables_cost_estimates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "consumer"\nversion = "1.0.0"\n',
        encoding="utf-8",
    )
    initialize_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    assert estimate_cost(DEFAULT_MODEL, 1_000_000, 1_000_000) == 35.0


def test_committed_quickstart_matches_generated_starter() -> None:
    root = Path(__file__).parents[2]
    example = root / "examples/quickstart" / STARTER_TEST_PATH
    assert example.read_text(encoding="utf-8") == STARTER_TEST


def test_local_project_checks_explain_missing_setup(tmp_path: Path) -> None:
    checks = check_project(tmp_path)
    by_name = {check.name: check for check in checks}
    assert not by_name["Project configuration"].passed
    assert "missing" in by_name["Project configuration"].detail
    assert not by_name["Starter test"].passed
    assert not by_name["Model pricing"].passed


def test_cli_init_reports_created_files(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "consumer"\nversion = "1.0.0"\n',
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-m", "pytest_skill_engineering.onboarding", "init", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "Created" in result.stdout
    assert f"uv run python -m pytest {Path('tests') / 'test_copilot_eval.py'} -v" in result.stdout
