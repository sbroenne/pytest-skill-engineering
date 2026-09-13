"""Offline comparison and saved-analysis recovery contracts."""

from __future__ import annotations

import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from pytest_skill_engineering.cli import load_suite_report
from pytest_skill_engineering.core.result import EvalResult
from pytest_skill_engineering.core.serialization import serialize_dataclass
from pytest_skill_engineering.reporting.collector import TestReport as CaseReport
from pytest_skill_engineering.reporting.collector import build_suite_report
from pytest_skill_engineering.reporting.generator import (
    _build_report_context,
    generate_html,
    generate_json,
    generate_md,
)
from pytest_skill_engineering.reporting.insights import InsightsResult, _build_analysis_input


def _case(model: str, *, instructions: str = "Use supplied tools.") -> CaseReport:
    return CaseReport(
        name="test_task",
        outcome="passed" if model == "sol" else "failed",
        duration_ms=10,
        agent_id="same-runtime-name",
        eval_name="Same runtime name",
        model=model,
        eval_result=EvalResult(
            turns=[],
            success=True,
            effective_system_prompt=instructions,
            configuration={
                "name": "same-runtime-name",
                "model": model,
                "instructions": instructions,
            },
        ),
    )


def _insights() -> InsightsResult:
    return InsightsResult(
        markdown_summary="Offline contract content, not AI analysis.", model="none"
    )


def test_model_variants_have_distinct_report_rows_without_runtime_renaming(tmp_path: Path) -> None:
    cases = [_case("sol"), _case("luna"), _case("sol")]
    cases[0].iteration = 1
    cases[2].iteration = 2
    suite = build_suite_report(cases, name="Model comparison")
    original = deepcopy(serialize_dataclass(suite))
    context = _build_report_context(suite, insights=_insights())
    assert len(context.agents) == 2
    assert sorted(agent.total for agent in context.agents) == [1, 2]
    assert {agent.display_name for agent in context.agents} == {
        "Same runtime name [sol]",
        "Same runtime name [luna]",
    }
    results = context.test_groups[0].tests[0].results_by_agent_id
    assert set(results) == set(context.all_agent_ids)
    assert sorted(len(result.iterations) for result in results.values()) == [0, 2]
    generate_html(suite, tmp_path / "report.html", insights=_insights())
    generate_md(suite, tmp_path / "report.md", insights=_insights())
    for suffix in ("html", "md"):
        rendered = (tmp_path / f"report.{suffix}").read_text(encoding="utf-8")
        assert "Same runtime name [sol]" in rendered
        assert "Same runtime name [luna]" in rendered
    assert serialize_dataclass(suite) == original


def test_same_model_different_configuration_is_not_merged() -> None:
    suite = build_suite_report(
        [_case("sol"), _case("sol", instructions="Verify first.")], name="Config"
    )
    context = _build_report_context(suite, insights=_insights())
    assert len(context.agents) == 2
    assert len({agent.display_name for agent in context.agents}) == 2
    assert all(agent.total == 1 for agent in context.agents)
    before = {agent.display_name: agent.agent_id for agent in context.agents}
    suite.tests.reverse()
    after = _build_report_context(suite, insights=_insights())
    assert {agent.display_name: agent.agent_id for agent in after.agents} == before


def test_analysis_statistics_use_the_same_model_groups_as_rendering() -> None:
    suite = build_suite_report([_case("sol"), _case("luna")], name="Comparison")
    analysis = _build_analysis_input(suite, [], [], {})
    assert "Eval Configurations: 2" in analysis
    assert "Same runtime name [sol]" in analysis
    assert "Same runtime name [luna]" in analysis


def test_single_configuration_keeps_existing_report_identity() -> None:
    suite = build_suite_report([_case("sol")], name="Single")
    context = _build_report_context(suite, insights=_insights())
    assert context.agents[0].agent_id == "same-runtime-name"
    assert context.agents[0].display_name == "Same runtime name"


def _cli(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    missing_cli = tmp_path / "missing-copilot.exe"
    assert not missing_cli.exists()
    return subprocess.run(
        [sys.executable, "-m", "pytest_skill_engineering.cli", *args],
        env={**os.environ, "COPILOT_CLI_PATH": str(missing_cli)},
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_saved_analysis_survives_render_failure_and_is_reusable(tmp_path: Path) -> None:
    suite = build_suite_report([_case("sol"), _case("luna")], name="Saved comparison")
    source = tmp_path / "source.json"
    saved = tmp_path / "saved-summary.json"
    generate_json(suite, source, insights=_insights())
    original = source.read_bytes()
    blocked = tmp_path / "blocked"
    blocked.write_text("This file prevents creating the HTML directory.", encoding="utf-8")
    failed = _cli(
        tmp_path, str(source), "--json", str(saved), "--html", str(blocked / "report.html")
    )
    assert failed.returncode == 1, failed.stdout + failed.stderr
    assert "Failed to render report" in failed.stderr
    restored, insights = load_suite_report(saved)
    assert serialize_dataclass(restored) == serialize_dataclass(suite)
    assert insights == _insights()
    assert source.read_bytes() == original
    output = tmp_path / "recovered.html"
    recovered = _cli(tmp_path, str(saved), "--html", str(output))
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    assert _insights().markdown_summary in output.read_text(encoding="utf-8")
    assert "Generating AI summary" not in recovered.stdout


def test_summary_checkpoint_path_is_automatic_and_separate(tmp_path: Path) -> None:
    from pytest_skill_engineering.cli import _summary_checkpoint_path

    source = tmp_path / "results.json"
    assert _summary_checkpoint_path(source, None, True) == tmp_path / "results.summary.json"
    assert _summary_checkpoint_path(source, None, False) is None
    explicit = tmp_path / "chosen.json"
    assert _summary_checkpoint_path(source, explicit, True) == explicit


def test_checkpoint_cannot_overwrite_source_report(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    generate_json(build_suite_report([_case("sol")], name="Original"), source, insights=_insights())
    original = source.read_bytes()
    result = _cli(tmp_path, str(source), "--json", str(source))
    assert result.returncode == 1, result.stdout + result.stderr
    assert "must differ from the input" in result.stderr
    assert source.read_bytes() == original


def test_existing_paid_checkpoint_is_not_overwritten_or_regenerated(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    generate_json(build_suite_report([_case("sol")], name="Original"), source)
    saved = tmp_path / "source.summary.json"
    generate_json(build_suite_report([_case("sol")], name="Saved"), saved, insights=_insights())
    original = saved.read_bytes()
    result = _cli(tmp_path, str(source), "--summary", "--summary-model", "copilot/test-model")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "checkpoint already exists" in result.stderr
    assert "Generating AI summary" not in result.stdout
    assert saved.read_bytes() == original


@pytest.mark.parametrize("attempts", [1, 2])
def test_summary_attempt_budget_is_enforced_before_runtime_start(
    tmp_path: Path, attempts: int
) -> None:
    source = tmp_path / "source.json"
    generate_json(build_suite_report([_case("sol")], name="Budget"), source)
    result = _cli(
        tmp_path,
        str(source),
        "--summary",
        "--summary-model",
        "copilot/test-model",
        "--summary-attempts",
        str(attempts),
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stderr.count("CopilotClient.start failed") == attempts
    assert not (tmp_path / "source.summary.json").exists()


@pytest.mark.parametrize("attempts", ["0", "4"])
def test_invalid_summary_attempt_budget_is_rejected(tmp_path: Path, attempts: str) -> None:
    result = _cli(tmp_path, "unused.json", "--summary-attempts", attempts)
    assert result.returncode == 2
    assert "invalid choice" in result.stderr


def test_summary_attempt_budget_defaults_to_three() -> None:
    import inspect

    from pytest_skill_engineering.cli import generate_ai_summary
    from pytest_skill_engineering.reporting.insights import generate_insights

    for function in (generate_ai_summary, generate_insights):
        assert inspect.signature(function).parameters["max_attempts"].default == 3
