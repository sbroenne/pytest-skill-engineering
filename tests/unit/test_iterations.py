"""Tests for iteration support (--aitest-iterations=N).

Covers:
- TestReport.iteration field
- _build_result_for_agent aggregation logic
- _extract_test_result_fields helper
- Iteration rendering in test_comparison and test_grid
- Markdown iteration table output
- Serialization round-trip for iteration field
- Eval.retries field
- CLIServer.timeout field
- pytest_generate_tests hook parametrization
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pytest_skill_engineering.core.eval import CLIServer, Eval, Provider
from pytest_skill_engineering.core.result import EvalResult, ToolCall, Turn
from pytest_skill_engineering.core.serialization import (
    deserialize_suite_report,
    serialize_dataclass,
)
from pytest_skill_engineering.reporting.collector import SuiteReport, TestReport
from pytest_skill_engineering.reporting.components.types import IterationData, TestResultData
from pytest_skill_engineering.reporting.generator import (
    _build_result_for_agent,
    _extract_test_result_fields,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent_result(
    success: bool = True,
    cost: float = 0.002,
    prompt_tokens: int = 200,
    completion_tokens: int = 100,
    duration_ms: float = 150.0,
) -> EvalResult:
    """Create a minimal EvalResult for testing."""
    return EvalResult(
        turns=[
            Turn(role="user", content="test prompt"),
            Turn(role="assistant", content="test response"),
        ],
        success=success,
        duration_ms=duration_ms,
        token_usage={"prompt": prompt_tokens, "completion": completion_tokens},
        cost_usd=cost,
    )


def _make_agent_result_with_tools(
    success: bool = True,
    cost: float = 0.003,
) -> EvalResult:
    """Create an EvalResult that includes tool calls."""
    return EvalResult(
        turns=[
            Turn(role="user", content="What's my balance?"),
            Turn(
                role="assistant",
                content="",
                tool_calls=[
                    ToolCall(
                        name="get_balance",
                        arguments={"account": "checking"},
                        result='{"balance": 1500}',
                    )
                ],
            ),
            Turn(role="assistant", content="Your balance is $1,500."),
        ],
        success=success,
        duration_ms=200.0,
        token_usage={"prompt": 300, "completion": 150},
        cost_usd=cost,
    )


def _make_test_report(
    name: str = "tests/test_foo.py::test_example",
    outcome: str = "passed",
    duration_ms: float = 100.0,
    eval_result: EvalResult | None = None,
    eval_name: str = "agent-1",
    model: str = "gpt-5-mini",
    iteration: int | None = None,
    error: str | None = None,
    assertions: list | None = None,
) -> TestReport:
    """Create a TestReport for testing."""
    return TestReport(
        name=name,
        outcome=outcome,
        duration_ms=duration_ms,
        eval_result=eval_result or _make_agent_result(success=(outcome == "passed")),
        agent_id=eval_name,
        eval_name=eval_name,
        model=model,
        iteration=iteration,
        error=error,
        assertions=assertions or [],
    )


# ---------------------------------------------------------------------------
# TestReport.iteration field tests
# ---------------------------------------------------------------------------


class TestIterationField:
    """Tests for the iteration field on TestReport."""

    def test_default_is_none(self) -> None:
        report = TestReport(name="test_foo", outcome="passed", duration_ms=100.0)
        assert report.iteration is None

    def test_can_set_iteration(self) -> None:
        report = TestReport(name="test_foo", outcome="passed", duration_ms=100.0, iteration=3)
        assert report.iteration == 3

    def test_iteration_serializes_to_json(self) -> None:
        report = TestReport(name="test_foo", outcome="passed", duration_ms=100.0, iteration=2)
        data = serialize_dataclass(report)
        assert data["iteration"] == 2

    def test_iteration_none_serializes(self) -> None:
        report = TestReport(name="test_foo", outcome="passed", duration_ms=100.0, iteration=None)
        data = serialize_dataclass(report)
        assert data["iteration"] is None


# ---------------------------------------------------------------------------
# Serialization round-trip tests
# ---------------------------------------------------------------------------


class TestIterationSerialization:
    """Tests for iteration field serialization/deserialization."""

    def test_round_trip_preserves_iteration(self) -> None:
        """iteration value survives serialize → deserialize."""
        test = _make_test_report(iteration=3)
        suite = SuiteReport(
            name="test-suite",
            timestamp="2026-02-15T00:00:00Z",
            duration_ms=200.0,
            tests=[test],
            passed=1,
        )
        data = serialize_dataclass(suite)
        restored = deserialize_suite_report(data)
        assert restored.tests[0].iteration == 3

    def test_round_trip_preserves_none_iteration(self) -> None:
        test = _make_test_report(iteration=None)
        suite = SuiteReport(
            name="test-suite",
            timestamp="2026-02-15T00:00:00Z",
            duration_ms=200.0,
            tests=[test],
            passed=1,
        )
        data = serialize_dataclass(suite)
        restored = deserialize_suite_report(data)
        assert restored.tests[0].iteration is None

    def test_missing_iteration_in_json_deserializes_as_none(self) -> None:
        """Fixture JSONs from before iteration support still load correctly."""
        test = _make_test_report()
        suite = SuiteReport(
            name="test-suite",
            timestamp="2026-02-15T00:00:00Z",
            duration_ms=200.0,
            tests=[test],
            passed=1,
        )
        data = serialize_dataclass(suite)
        # Simulate old JSON without iteration field
        del data["tests"][0]["iteration"]
        restored = deserialize_suite_report(data)
        assert restored.tests[0].iteration is None


# ---------------------------------------------------------------------------
# _extract_test_result_fields tests
# ---------------------------------------------------------------------------


class TestExtractTestResultFields:
    """Tests for the _extract_test_result_fields helper."""

    def test_extracts_tool_calls(self) -> None:
        test = _make_test_report(eval_result=_make_agent_result_with_tools())
        tool_calls, _, _, _, _, _, _ = _extract_test_result_fields(test)
        assert len(tool_calls) == 1
        assert tool_calls[0].name == "get_balance"
        assert tool_calls[0].success is True

    def test_extracts_assertions_from_dicts(self) -> None:
        test = _make_test_report(
            assertions=[
                {"type": "tool_called", "passed": True, "message": "get_balance called"},
                {"type": "semantic", "passed": False, "message": "bad response"},
            ]
        )
        _, assertions, _, _, _, _, _ = _extract_test_result_fields(test)
        assert len(assertions) == 2
        assert assertions[0].type == "tool_called"
        assert assertions[0].passed is True
        assert assertions[1].passed is False

    def test_extracts_turn_count(self) -> None:
        test = _make_test_report(eval_result=_make_agent_result_with_tools())
        _, _, _, turn_count, _, _, _ = _extract_test_result_fields(test)
        assert turn_count == 3  # user + tool_call + final assistant

    def test_extracts_tokens(self) -> None:
        test = _make_test_report(
            eval_result=_make_agent_result(prompt_tokens=500, completion_tokens=200)
        )
        _, _, _, _, tokens, _, _ = _extract_test_result_fields(test)
        assert tokens == 700

    def test_generates_mermaid(self) -> None:
        test = _make_test_report(eval_result=_make_agent_result_with_tools())
        _, _, _, _, _, mermaid, _ = _extract_test_result_fields(test)
        assert mermaid is not None
        assert "sequenceDiagram" in mermaid

    def test_extracts_final_response(self) -> None:
        test = _make_test_report(eval_result=_make_agent_result_with_tools())
        _, _, _, _, _, _, final_resp = _extract_test_result_fields(test)
        assert final_resp == "Your balance is $1,500."

    def test_handles_no_agent_result(self) -> None:
        test = TestReport(name="test_foo", outcome="passed", duration_ms=100.0, eval_result=None)
        tool_calls, _, _, turn_count, tokens, mermaid, final_resp = _extract_test_result_fields(
            test
        )
        assert tool_calls == []
        assert turn_count == 0
        assert tokens == 0
        assert mermaid is None
        assert final_resp is None


# ---------------------------------------------------------------------------
# _build_result_for_agent tests
# ---------------------------------------------------------------------------


class TestBuildResultForAgent:
    """Tests for _build_result_for_agent iteration aggregation."""

    def test_single_test_no_iterations(self) -> None:
        """Single test produces a result with no iterations list."""
        test = _make_test_report(outcome="passed", duration_ms=200.0)
        result = _build_result_for_agent([test])
        assert result.passed is True
        assert result.outcome == "passed"
        assert result.iterations == []
        assert result.iteration_pass_rate is None
        assert result.duration_s == pytest.approx(0.2)

    def test_multiple_tests_all_pass(self) -> None:
        """All iterations pass → aggregated outcome=passed, 100% rate."""
        tests = [
            _make_test_report(iteration=1, outcome="passed", duration_ms=100.0),
            _make_test_report(iteration=2, outcome="passed", duration_ms=150.0),
            _make_test_report(iteration=3, outcome="passed", duration_ms=120.0),
        ]
        result = _build_result_for_agent(tests)
        assert result.passed is True
        assert result.outcome == "passed"
        assert len(result.iterations) == 3
        assert result.iteration_pass_rate == pytest.approx(100.0)
        assert result.duration_s == pytest.approx(0.370)  # total: 370ms

    def test_multiple_tests_some_fail(self) -> None:
        """Mixed results → outcome=failed, correct pass rate."""
        tests = [
            _make_test_report(iteration=1, outcome="passed", duration_ms=100.0),
            _make_test_report(
                iteration=2, outcome="failed", duration_ms=100.0, error="AssertionError"
            ),
            _make_test_report(iteration=3, outcome="passed", duration_ms=100.0),
        ]
        result = _build_result_for_agent(tests)
        assert result.passed is False
        assert result.outcome == "failed"
        assert len(result.iterations) == 3
        assert result.iteration_pass_rate == pytest.approx(200 / 3)  # 66.67%

    def test_aggregates_tokens_and_cost(self) -> None:
        """Total tokens and cost are summed across iterations."""
        tests = [
            _make_test_report(
                iteration=1,
                eval_result=_make_agent_result(prompt_tokens=100, completion_tokens=50, cost=0.001),
            ),
            _make_test_report(
                iteration=2,
                eval_result=_make_agent_result(prompt_tokens=200, completion_tokens=80, cost=0.002),
            ),
        ]
        result = _build_result_for_agent(tests)
        assert result.tokens == 430  # 150 + 280
        assert result.cost == pytest.approx(0.003)

    def test_uses_last_iteration_for_tool_calls(self) -> None:
        """Tool calls and mermaid come from the last iteration."""
        tests = [
            _make_test_report(iteration=1, eval_result=_make_agent_result()),
            _make_test_report(iteration=2, eval_result=_make_agent_result_with_tools()),
        ]
        result = _build_result_for_agent(tests)
        assert result.tool_count == 1
        assert result.tool_calls[0].name == "get_balance"
        assert result.mermaid is not None

    def test_iteration_data_contents(self) -> None:
        """Each IterationData contains correct per-run values."""
        test1 = _make_test_report(
            iteration=1,
            outcome="passed",
            duration_ms=200.0,
            eval_result=_make_agent_result(prompt_tokens=100, completion_tokens=50, cost=0.001),
        )
        test2 = _make_test_report(
            iteration=2,
            outcome="failed",
            duration_ms=300.0,
            error="Failed assertion",
            eval_result=_make_agent_result(
                prompt_tokens=150, completion_tokens=80, cost=0.002, success=False
            ),
        )
        result = _build_result_for_agent([test1, test2])

        iter1 = result.iterations[0]
        assert iter1.iteration == 1
        assert iter1.passed is True
        assert iter1.outcome == "passed"
        assert iter1.duration_s == pytest.approx(0.2)
        assert iter1.tokens == 150
        assert iter1.cost == pytest.approx(0.001)
        assert iter1.error is None

        iter2 = result.iterations[1]
        assert iter2.iteration == 2
        assert iter2.passed is False
        assert iter2.outcome == "failed"
        assert iter2.error == "Failed assertion"

    def test_all_fail_outcome(self) -> None:
        """All iterations fail → outcome=failed, 0% pass rate."""
        tests = [
            _make_test_report(iteration=1, outcome="failed", error="err1"),
            _make_test_report(iteration=2, outcome="failed", error="err2"),
        ]
        result = _build_result_for_agent(tests)
        assert result.passed is False
        assert result.outcome == "failed"
        assert result.iteration_pass_rate == pytest.approx(0.0)

    def test_falls_back_to_idx_when_no_iteration(self) -> None:
        """When iteration is None, uses enumeration index."""
        tests = [
            _make_test_report(iteration=None),
            _make_test_report(iteration=None),
        ]
        result = _build_result_for_agent(tests)
        assert result.iterations[0].iteration == 1
        assert result.iterations[1].iteration == 2


# ---------------------------------------------------------------------------
# Eval.retries and CLIServer.timeout tests
# ---------------------------------------------------------------------------


class TestAgentRetries:
    """Tests for Eval.retries field."""

    def test_default_retries_is_one(self) -> None:
        agent = Eval(provider=Provider(model="test/model"))
        assert agent.retries == 1

    def test_custom_retries(self) -> None:
        agent = Eval(provider=Provider(model="test/model"), retries=5)
        assert agent.retries == 5


class TestCLIServerTimeout:
    """Tests for CLIServer.timeout field."""

    def test_default_timeout(self) -> None:
        server = CLIServer(name="test-cli", command="echo hello")
        assert server.timeout == 30.0

    def test_custom_timeout(self) -> None:
        server = CLIServer(name="test-cli", command="echo hello", timeout=60.0)
        assert server.timeout == 60.0


# ---------------------------------------------------------------------------
# IterationData type tests
# ---------------------------------------------------------------------------


class TestIterationData:
    """Tests for the IterationData dataclass."""

    def test_basic_construction(self) -> None:
        data = IterationData(
            iteration=1,
            outcome="passed",
            passed=True,
            duration_s=1.5,
            tokens=300,
            cost=0.002,
        )
        assert data.iteration == 1
        assert data.passed is True
        assert data.error is None

    def test_with_error(self) -> None:
        data = IterationData(
            iteration=2,
            outcome="failed",
            passed=False,
            duration_s=0.5,
            tokens=100,
            cost=0.001,
            error="AssertionError: expected True",
        )
        assert data.passed is False
        assert data.error == "AssertionError: expected True"


# ---------------------------------------------------------------------------
# TestResultData with iterations
# ---------------------------------------------------------------------------


class TestTestResultDataIterations:
    """Tests for TestResultData iteration-related fields."""

    def test_default_empty_iterations(self) -> None:
        result = TestResultData(
            outcome="passed",
            passed=True,
            duration_s=1.0,
            tokens=100,
            cost=0.001,
            tool_calls=[],
            tool_count=0,
            turns=1,
        )
        assert result.iterations == []
        assert result.iteration_pass_rate is None

    def test_with_iterations(self) -> None:
        iters = [
            IterationData(
                iteration=1, outcome="passed", passed=True, duration_s=0.5, tokens=100, cost=0.001
            ),
            IterationData(
                iteration=2, outcome="failed", passed=False, duration_s=0.6, tokens=120, cost=0.001
            ),
        ]
        result = TestResultData(
            outcome="failed",
            passed=False,
            duration_s=1.1,
            tokens=220,
            cost=0.002,
            tool_calls=[],
            tool_count=0,
            turns=1,
            iterations=iters,
            iteration_pass_rate=50.0,
        )
        assert len(result.iterations) == 2
        assert result.iteration_pass_rate == 50.0


# ---------------------------------------------------------------------------
# Report rendering with iterations
# ---------------------------------------------------------------------------


class TestIterationInReports:
    """Integration tests: iteration data flows through to HTML and markdown."""

    @pytest.fixture()
    def iteration_suite(self) -> SuiteReport:
        """Create a SuiteReport with iteration test data."""
        tests = []
        # 3 iterations of the same test for the same agent
        for i in range(1, 4):
            outcome = "passed" if i != 2 else "failed"
            tests.append(
                _make_test_report(
                    name="tests/test_banking.py::test_balance",
                    outcome=outcome,
                    duration_ms=100.0 * i,
                    eval_name="banking-agent",
                    model="gpt-5-mini",
                    iteration=i,
                    error="Assertion failed" if outcome == "failed" else None,
                    eval_result=_make_agent_result(
                        success=(outcome == "passed"),
                        cost=0.001 * i,
                        prompt_tokens=100 * i,
                        completion_tokens=50 * i,
                    ),
                )
            )
        return SuiteReport(
            name="iteration-tests",
            timestamp="2026-02-15T10:00:00Z",
            duration_ms=600.0,
            tests=tests,
            passed=2,
            failed=1,
        )

    def test_html_report_contains_iteration_badge(
        self, iteration_suite: SuiteReport, tmp_path: Path
    ) -> None:
        """HTML report renders iteration pass rate info."""
        from pytest_skill_engineering.reporting import generate_html
        from pytest_skill_engineering.reporting.insights import InsightsResult

        insights = InsightsResult(markdown_summary="Test insights.", model="test")
        output = tmp_path / "report.html"
        generate_html(iteration_suite, output, insights=insights)
        html = output.read_text(encoding="utf-8")

        # Should contain iteration pass rate info
        assert "iters" in html or "iterations passed" in html or "iter pass rate" in html

    def test_markdown_report_contains_iteration_table(
        self, iteration_suite: SuiteReport, tmp_path: Path
    ) -> None:
        """Markdown report includes iteration breakdown table."""
        from pytest_skill_engineering.reporting import generate_md
        from pytest_skill_engineering.reporting.insights import InsightsResult

        insights = InsightsResult(markdown_summary="Test insights.", model="test")
        output = tmp_path / "report.md"
        generate_md(iteration_suite, output, insights=insights)
        md = output.read_text(encoding="utf-8")

        # Should contain iteration breakdown
        assert "iterations passed" in md.lower() or "iteration" in md.lower()


# ---------------------------------------------------------------------------
# Insights builder iteration awareness
# ---------------------------------------------------------------------------


class TestInsightsIterationAwareness:
    """Tests for iteration-aware insights builder."""

    def test_has_iterations_detected(self) -> None:
        """_build_analysis_input detects when tests have iteration data."""
        from pytest_skill_engineering.reporting.insights import _build_analysis_input

        tests = [
            _make_test_report(iteration=1, outcome="passed"),
            _make_test_report(iteration=2, outcome="failed"),
        ]
        suite = SuiteReport(
            name="test",
            timestamp="2026-02-15T00:00:00Z",
            duration_ms=200.0,
            tests=tests,
            passed=1,
            failed=1,
        )
        analysis_input = _build_analysis_input(suite, tool_info=[], skill_info=[], prompts={})

        # Should mention iteration statistics
        assert "Iteration Statistics" in analysis_input or "iter" in analysis_input.lower()

    def test_no_iterations_skips_section(self) -> None:
        """Without iteration data, iteration stats section is absent."""
        from pytest_skill_engineering.reporting.insights import _build_analysis_input

        tests = [_make_test_report(iteration=None, outcome="passed")]
        suite = SuiteReport(
            name="test",
            timestamp="2026-02-15T00:00:00Z",
            duration_ms=100.0,
            tests=tests,
            passed=1,
        )
        analysis_input = _build_analysis_input(suite, tool_info=[], skill_info=[], prompts={})
        assert "Iteration Statistics" not in analysis_input
