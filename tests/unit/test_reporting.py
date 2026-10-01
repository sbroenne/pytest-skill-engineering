"""Tests for pytest-skill-engineering reporting module."""

from __future__ import annotations

import pytest

from pytest_skill_engineering.core.result import EvalResult
from pytest_skill_engineering.reporting import (
    SuiteReport,
    TestReport,
    build_suite_report,
)


class TestTestReport:
    """Tests for TestReport dataclass."""

    def test_basic_passed(self) -> None:
        report = TestReport(name="test_foo", outcome="passed", duration_ms=100.0)
        assert report.name == "test_foo"
        assert report.outcome == "passed"
        assert report.duration_ms == 100.0
        assert report.eval_result is None
        assert report.error is None

    def test_with_error(self) -> None:
        report = TestReport(
            name="test_bar", outcome="failed", duration_ms=50.0, error="AssertionError"
        )
        assert report.outcome == "failed"
        assert report.error == "AssertionError"

    def test_with_agent_result(self) -> None:
        result = EvalResult(turns=[], success=True, duration_ms=50.0)
        report = TestReport(
            name="test_agent", outcome="passed", duration_ms=100.0, eval_result=result
        )
        assert report.eval_result is not None
        assert report.eval_result.success


class TestSuiteReport:
    """Tests for SuiteReport dataclass."""

    def test_empty_suite(self) -> None:
        suite = SuiteReport(name="suite", timestamp="2026-01-31T00:00:00Z", duration_ms=0.0)
        assert suite.total == 0
        assert suite.pass_rate == 0.0
        assert suite.total_tokens == 0
        assert suite.total_cost_usd == 0.0

    def test_pass_rate(self) -> None:
        suite = SuiteReport(
            name="suite",
            timestamp="2026-01-31T00:00:00Z",
            duration_ms=1000.0,
            passed=8,
            failed=2,
            skipped=0,
        )
        assert suite.total == 10
        assert suite.pass_rate == 80.0

    def test_pass_rate_all_passed(self) -> None:
        suite = SuiteReport(
            name="suite",
            timestamp="2026-01-31T00:00:00Z",
            duration_ms=500.0,
            passed=5,
            failed=0,
            skipped=0,
        )
        assert suite.pass_rate == 100.0

    def test_total_tokens(self) -> None:
        result1 = EvalResult(turns=[], success=True, token_usage={"prompt": 100, "completion": 50})
        result2 = EvalResult(turns=[], success=True, token_usage={"prompt": 200, "completion": 100})
        suite = SuiteReport(
            name="suite",
            timestamp="2026-01-31T00:00:00Z",
            duration_ms=1000.0,
            tests=[
                TestReport(name="t1", outcome="passed", duration_ms=100.0, eval_result=result1),
                TestReport(name="t2", outcome="passed", duration_ms=100.0, eval_result=result2),
            ],
            passed=2,
        )
        assert suite.total_tokens == 450  # 100+50+200+100

    def test_total_cost(self) -> None:
        result1 = EvalResult(turns=[], success=True, cost_usd=0.01)
        result2 = EvalResult(turns=[], success=True, cost_usd=0.02)
        suite = SuiteReport(
            name="suite",
            timestamp="2026-01-31T00:00:00Z",
            duration_ms=1000.0,
            tests=[
                TestReport(name="t1", outcome="passed", duration_ms=100.0, eval_result=result1),
                TestReport(name="t2", outcome="passed", duration_ms=100.0, eval_result=result2),
            ],
            passed=2,
        )
        assert suite.total_cost_usd == pytest.approx(0.03)

    def test_token_stats(self) -> None:
        results = [
            EvalResult(turns=[], success=True, token_usage={"prompt": 50, "completion": 50}),
            EvalResult(turns=[], success=True, token_usage={"prompt": 100, "completion": 100}),
            EvalResult(turns=[], success=True, token_usage={"prompt": 150, "completion": 150}),
        ]
        suite = SuiteReport(
            name="suite",
            timestamp="2026-01-31T00:00:00Z",
            duration_ms=1000.0,
            tests=[
                TestReport(name=f"t{i}", outcome="passed", duration_ms=100.0, eval_result=r)
                for i, r in enumerate(results)
            ],
            passed=3,
        )
        stats = suite.token_stats
        assert stats["min"] == 100  # 50+50
        assert stats["max"] == 300  # 150+150
        assert stats["avg"] == 200  # (100+200+300)/3

    def test_token_stats_empty(self) -> None:
        suite = SuiteReport(name="suite", timestamp="2026-01-31T00:00:00Z", duration_ms=0.0)
        stats = suite.token_stats
        assert stats == {"min": 0, "max": 0, "avg": 0}


class TestBuildSuiteReport:
    """Tests for build_suite_report function."""

    def test_build_suite_report(self) -> None:
        tests = [
            TestReport(name="t1", outcome="passed", duration_ms=100.0),
            TestReport(name="t2", outcome="failed", duration_ms=200.0),
            TestReport(name="t3", outcome="skipped", duration_ms=50.0),
        ]

        suite = build_suite_report(tests, "my-suite")

        assert suite.name == "my-suite"
        assert suite.passed == 1
        assert suite.failed == 1
        assert suite.skipped == 1
        assert suite.total == 3
        assert suite.duration_ms == 350.0
        assert len(suite.tests) == 3

    def test_build_suite_report_empty(self) -> None:
        suite = build_suite_report([], "empty")

        assert suite.name == "empty"
        assert suite.total == 0
