"""Integration tests for AI insights generation.

These tests verify that the AI insights feature generates proper structured output
using the report_analysis prompt.

Run with: pytest tests/integration/test_ai_summary.py -v
"""

from __future__ import annotations

import pytest

from pytest_skill_engineering.reporting.collector import SuiteReport, TestReport

pytestmark = [pytest.mark.integration]


def _make_test_report(
    name: str,
    outcome: str = "passed",
    model: str | None = None,
    duration_ms: float = 1000.0,
) -> TestReport:
    """Create a test report for testing."""
    return TestReport(
        name=name,
        outcome=outcome,
        duration_ms=duration_ms,
        model=model or "",
    )


def _make_suite_report(tests: list[TestReport]) -> SuiteReport:
    """Create a suite report for testing."""
    passed = sum(1 for t in tests if t.outcome == "passed")
    failed = sum(1 for t in tests if t.outcome == "failed")
    return SuiteReport(
        name="test-suite",
        timestamp="2026-01-01T00:00:00Z",
        duration_ms=sum(t.duration_ms for t in tests),
        tests=tests,
        passed=passed,
        failed=failed,
    )


class TestAIInsightsGeneration:
    """Test that AI insights generates markdown output."""

    @pytest.mark.asyncio
    async def test_insights_returns_markdown_string(self):
        """Insights should return a markdown string."""
        from pytest_skill_engineering.reporting.insights import generate_insights

        tests = [
            _make_test_report("test_balance_check", "passed", model="gpt-5-mini"),
            _make_test_report("test_transfer", "passed", model="gpt-5-mini"),
        ]
        suite = _make_suite_report(tests)

        result = await generate_insights(
            suite_report=suite,
            tool_info=[],
            skill_info=[],
            prompts={},
            model="azure/gpt-5-mini",
        )

        # Insights is now a plain markdown string
        assert isinstance(result.markdown_summary, str), "Insights should be a string"
        assert len(result.markdown_summary) > 50, "Insights should have substantial content"

    @pytest.mark.asyncio
    async def test_insights_contains_recommendation(self):
        """Insights markdown should contain recommendation section."""
        from pytest_skill_engineering.reporting.insights import generate_insights

        tests = [
            _make_test_report("test_a", "passed", model="gpt-5-mini"),
            _make_test_report("test_b", "failed", model="gpt-5-mini"),
        ]
        suite = _make_suite_report(tests)

        result = await generate_insights(
            suite_report=suite,
            tool_info=[],
            skill_info=[],
            prompts={},
            model="azure/gpt-5-mini",
        )

        # Check markdown contains expected sections
        assert isinstance(result.markdown_summary, str)
        # The prompt asks for a recommendation section
        lower = result.markdown_summary.lower()
        assert "recommend" in lower, "Insights should contain a recommendation section"

    @pytest.mark.asyncio
    async def test_insights_with_failures(self):
        """Insights should analyze failures when present."""
        from pytest_skill_engineering.reporting.insights import generate_insights

        tests = [
            _make_test_report("test_passing", "passed", model="gpt-5-mini"),
            _make_test_report("test_failing", "failed", model="gpt-5-mini"),
        ]
        suite = _make_suite_report(tests)
        # Add error to failing test
        suite.tests[1].error = "AssertionError: Expected result not found"

        result = await generate_insights(
            suite_report=suite,
            tool_info=[],
            skill_info=[],
            prompts={},
            model="azure/gpt-5-mini",
        )

        # Should be a string with content
        assert isinstance(result.markdown_summary, str)
        assert len(result.markdown_summary) > 50

    @pytest.mark.asyncio
    async def test_insights_returns_metadata(self):
        """Insights should return analysis metadata."""
        from pytest_skill_engineering.reporting.insights import generate_insights

        tests = [_make_test_report("test_one", "passed", model="gpt-5-mini")]
        suite = _make_suite_report(tests)

        result = await generate_insights(
            suite_report=suite,
            tool_info=[],
            skill_info=[],
            prompts={},
            model="azure/gpt-5-mini",
        )

        # Verify metadata fields
        assert result.model == "azure/gpt-5-mini"
        assert result.tokens_used >= 0
        assert result.cost_usd >= 0


class TestPromptLoading:
    """Test that the prompt loads correctly."""

    def test_report_analysis_prompt_loads(self):
        """The AI summary prompt should load successfully."""
        from pytest_skill_engineering.prompts import get_ai_summary_prompt

        prompt = get_ai_summary_prompt()
        assert prompt, "Prompt should not be empty"
        assert "pytest-skill-engineering" in prompt.lower() or "analysis" in prompt.lower()
        assert len(prompt) > 100, "Prompt should have substantial content"

    def test_prompt_is_cached(self):
        """Prompt should be cached after first load."""
        from pytest_skill_engineering.prompts import get_ai_summary_prompt

        prompt1 = get_ai_summary_prompt()
        prompt2 = get_ai_summary_prompt()
        # Same object due to caching
        assert prompt1 is prompt2
