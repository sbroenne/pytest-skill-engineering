"""Framework boundary checks, not claims about model performance."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

import pytest_skill_engineering as framework


@pytest.mark.parametrize(
    "module",
    [
        "copilot.judge",
        "reporting.insights",
        "fixtures.llm_assert",
        "fixtures.llm_score",
        "fixtures.skill_refine",
        "fixtures.skill_eval",
        "fixtures.skill_benchmark",
        "core.skill_refiner",
        "core.skill_benchmark",
        "core.skill_eval_results",
        "core.scoring",
        "cli",
        "hooks",
        "plugin_recording",
        "prompts",
        "reporting.components",
        "reporting.markdown",
        "reporting.identity",
    ],
)
def test_no_separate_model_judging_or_advice_modules(module: str) -> None:
    assert importlib.util.find_spec(f"pytest_skill_engineering.{module}") is None


@pytest.mark.parametrize(
    "artifact",
    [
        "docs/assets/images/ai_analysis.png",
        "docs/demo",
        "docs/reports",
        "screenshots/ai_analysis.png",
        "scripts/generate_fixture_html.py",
        "src/pytest_skill_engineering/templates",
        "src/pytest_skill_engineering/reporting/components",
        "src/pytest_skill_engineering/prompts",
        "tests/fixtures/reports",
    ],
)
def test_removed_presentation_artifacts_are_absent(artifact: str) -> None:
    assert not (Path(__file__).resolve().parents[2] / artifact).exists()


@pytest.mark.parametrize(
    "symbol",
    [
        "analyze_skill_failures",
        "RefinementResult",
        "RefinementSuggestion",
        "ScoreResult",
        "ScoringDimension",
        "assert_score",
        "get_analysis_prompt",
        "get_analysis_prompt_details",
        "AitestHookSpec",
        "SkillBenchmarkResult",
        "SkillGradingResult",
        "generate_html",
        "generate_md",
        "generate_mermaid_sequence",
    ],
)
def test_removed_public_apis_are_not_retained(symbol: str) -> None:
    assert not hasattr(framework, symbol)


@pytest.mark.parametrize(
    "option",
    [
        "--llm-model=example",
        "--aitest-summary-model=example",
        "--aitest-analysis-prompt=example",
        "--aitest-summary-compact",
        "--aitest-print-analysis-prompt",
        "--aitest-html=report.html",
        "--aitest-md=report.md",
    ],
)
def test_removed_pytest_flags_fail_clearly(pytester: pytest.Pytester, option: str) -> None:
    result = pytester.runpytest_subprocess("-o", "addopts=", "--collect-only", option)
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    assert "unrecognized arguments" in result.stderr.str()


def test_plugin_saves_evidence_and_preserves_real_assertion_failures(
    pytester: pytest.Pytester,
) -> None:
    pytester.makepyfile("""
        from pytest_skill_engineering.copilot import CopilotEval, CopilotResult
        from pytest_skill_engineering.copilot.fixtures import stash_on_item

        def test_verified_file(request, record_property, tmp_path):
            expected = tmp_path / "output.txt"
            record_property("verification", {"artifact": str(expected), "exists": expected.exists()})
            stash_on_item(request.node, CopilotEval(name="evidence", model="recorded"),
                          CopilotResult(success=True))
            assert expected.exists(), "The requested file does not exist"
    """)
    result = pytester.runpytest_subprocess(
        "-o",
        "addopts=",
        "--aitest-json=result.json",
        "-q",
    )
    result.assert_outcomes(failed=1)
    data = json.loads((pytester.path / "result.json").read_text(encoding="utf-8"))
    case = data["tests"][0]
    assert case["outcome"] == "failed"
    assert "The requested file does not exist" in case["error"]
    assert case["eval_result"]["success"] is True
    assert case["properties"][0][1]["exists"] is False
    assert not (pytester.path / "report.html").exists()
    assert not (pytester.path / "report.md").exists()


def test_case_loader_and_explicit_grading_export_remain_available() -> None:
    assert callable(framework.load_skill_evals)
    assert callable(framework.export_grading)
