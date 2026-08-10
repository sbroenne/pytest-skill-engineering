"""Deterministic coverage for skill workflow parsing and result helpers."""

from __future__ import annotations

from pathlib import Path

from pytest_skill_engineering.core.skill import Skill
from pytest_skill_engineering.core.skill_benchmark import (
    BenchmarkComparison,
    CaseBenchmark,
    SkillBenchmarkResult,
)
from pytest_skill_engineering.core.skill_evals import has_skill_evals, load_skill_evals

PLUGIN_SKILL_DIR = (
    Path(__file__).parents[1]
    / "integration"
    / "plugins"
    / "banking-plugin"
    / "skills"
    / "financial-literacy"
)
MATH_SKILL_DIR = Path(__file__).parents[1] / "integration" / "skills" / "math-helper"


def test_plugin_skill_loads_from_plugin_directory() -> None:
    skill = Skill.from_path(PLUGIN_SKILL_DIR)
    assert skill.metadata.name == "financial-literacy"
    assert skill.metadata.description == "Domain knowledge for banking operations"
    assert "banking" in skill.metadata.tags


def test_plugin_skill_declares_evals() -> None:
    assert has_skill_evals(PLUGIN_SKILL_DIR)


def test_plugin_skill_evals_parse_with_expected_structure() -> None:
    cases = load_skill_evals(PLUGIN_SKILL_DIR)
    assert len(cases) == 2
    assert cases[0].prompt
    assert len(cases[0].expectations) == 3
    assert len(cases[1].expectations) == 2


def test_math_skill_evals_parse_with_expected_case_ids() -> None:
    cases = load_skill_evals(MATH_SKILL_DIR)
    assert [case.id for case in cases] == [1, 2]
    assert all(case.prompt for case in cases)


def test_skill_benchmark_result_properties_are_deterministic() -> None:
    case_a = CaseBenchmark(
        case=load_skill_evals(MATH_SKILL_DIR)[0],
        baseline_passed=False,
        treatment_passed=True,
        comparisons=[
            BenchmarkComparison(
                expectation="mentions compound interest",
                baseline_passed=False,
                treatment_passed=True,
                delta="improved",
            )
        ],
        baseline_duration_ms=10.0,
        treatment_duration_ms=12.0,
        baseline_tool_calls=1,
        treatment_tool_calls=2,
    )
    case_b = CaseBenchmark(
        case=load_skill_evals(MATH_SKILL_DIR)[1],
        baseline_passed=True,
        treatment_passed=True,
        comparisons=[
            BenchmarkComparison(
                expectation="returns the derivative",
                baseline_passed=True,
                treatment_passed=True,
                delta="unchanged",
            )
        ],
        baseline_duration_ms=8.0,
        treatment_duration_ms=9.0,
        baseline_tool_calls=1,
        treatment_tool_calls=1,
    )
    result = SkillBenchmarkResult(
        skill_name="math-helper",
        cases=[case_a, case_b],
        baseline_grading={"summary": {"passed": 1}},
        treatment_grading={"summary": {"passed": 2}},
    )

    assert result.baseline_pass_rate == 0.5
    assert result.treatment_pass_rate == 1.0
    assert result.improvement == 0.5
    assert result.skill_helps
    assert [comparison.delta for comparison in result.improvements] == ["improved"]
    assert result.regressions == []
    assert "Skill Benchmark: math-helper" in result.summary()
    assert "🎯 Verdict: Skill helps" in result.summary()
