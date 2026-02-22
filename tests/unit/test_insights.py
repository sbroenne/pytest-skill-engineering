"""Tests for AI insights input generation."""

from __future__ import annotations

from pytest_skill_engineering.core.result import EvalResult, ToolCall, Turn
from pytest_skill_engineering.reporting.collector import SuiteReport
from pytest_skill_engineering.reporting.collector import TestReport as ReportTest
from pytest_skill_engineering.reporting.insights import _build_analysis_input


class TestBuildAnalysisInput:
    """Tests for compact analysis input generation."""

    def test_compact_omits_passed_conversation_but_keeps_failed(self) -> None:
        passed_result = EvalResult(
            turns=[
                Turn(
                    role="assistant",
                    content="passed conversation detail",
                    tool_calls=[
                        ToolCall(
                            name="get_balance",
                            arguments={"account": "checking"},
                            result="1500",
                        )
                    ],
                )
            ],
            success=True,
            duration_ms=100,
            token_usage={"prompt": 10, "completion": 5},
            cost_usd=0.001,
        )
        failed_result = EvalResult(
            turns=[
                Turn(
                    role="assistant",
                    content="failed conversation detail",
                    tool_calls=[],
                )
            ],
            success=False,
            error="boom",
            duration_ms=120,
            token_usage={"prompt": 12, "completion": 8},
            cost_usd=0.002,
        )

        report = SuiteReport(
            name="suite",
            timestamp="2026-02-18T00:00:00",
            duration_ms=220,
            tests=[
                ReportTest(
                    name="tests/test_demo.py::test_passed",
                    outcome="passed",
                    duration_ms=100,
                    eval_result=passed_result,
                    eval_name="agent-a",
                    model="gpt-5-mini",
                ),
                ReportTest(
                    name="tests/test_demo.py::test_failed",
                    outcome="failed",
                    duration_ms=120,
                    eval_result=failed_result,
                    eval_name="agent-a",
                    model="gpt-5-mini",
                    error="boom",
                ),
            ],
            passed=1,
            failed=1,
            skipped=0,
        )

        compact_text = _build_analysis_input(
            suite_report=report,
            tool_info=[],
            skill_info=[],
            prompts={},
            compact=True,
        )

        full_text = _build_analysis_input(
            suite_report=report,
            tool_info=[],
            skill_info=[],
            prompts={},
            compact=False,
        )

        assert "passed conversation detail" not in compact_text
        assert "failed conversation detail" in compact_text
        assert "*Passed — 1 turns*" in compact_text

        assert "passed conversation detail" in full_text
        assert "failed conversation detail" in full_text
