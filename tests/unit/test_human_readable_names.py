"""Tests for human-readable names in all user-facing reports.

Ensures that raw Python identifiers (TestClassName::test_method_name) are
replaced with human-readable names (docstrings) throughout the pipeline:

1. TestReport.display_name uses docstring, not nodeid
2. Group names in reports use class_docstring, not class name
3. AI analysis prompt uses display_name headings
4. Markdown reports show human-readable names
5. HTML reports show human-readable names
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from pytest_skill_engineering.core.result import AgentResult, Turn
from pytest_skill_engineering.reporting import SuiteReport, TestReport, generate_html, generate_md
from pytest_skill_engineering.reporting.insights import (
    InsightsResult,
    _build_analysis_input,
)

# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def insights() -> InsightsResult:
    return InsightsResult(
        markdown_summary="## Verdict\nDeploy gpt-5-mini.",
        model="test-model",
        tokens_used=100,
        cost_usd=0.001,
    )


def _make_result(*, success: bool = True) -> AgentResult:
    return AgentResult(
        turns=[Turn(role="assistant", content="Done.")],
        success=success,
        duration_ms=100.0,
        token_usage={"prompt": 50, "completion": 30},
        cost_usd=0.001,
    )


def _make_suite_with_class_docstrings() -> SuiteReport:
    """Suite where tests have both docstring and class_docstring."""
    return SuiteReport(
        name="human-readable-test",
        timestamp="2026-02-07T10:00:00Z",
        duration_ms=200.0,
        tests=[
            TestReport(
                name="tests/test_hero.py::TestCoreOperations::test_transfer_and_verify[gpt-5-mini]",
                outcome="passed",
                duration_ms=100.0,
                agent_result=_make_result(),
                agent_id="agent-1",
                agent_name="gpt-5-mini",
                model="gpt-5-mini",
                docstring="Transfer money and verify the result with balance check.",
                class_docstring="Core banking tests — parametrized across all benchmark agents.",
            ),
            TestReport(
                name="tests/test_hero.py::TestCoreOperations::test_check_balance[gpt-5-mini]",
                outcome="passed",
                duration_ms=100.0,
                agent_result=_make_result(),
                agent_id="agent-1",
                agent_name="gpt-5-mini",
                model="gpt-5-mini",
                docstring="Check account balance for a specific account.",
                class_docstring="Core banking tests — parametrized across all benchmark agents.",
            ),
        ],
        passed=2,
        failed=0,
    )


def _make_suite_with_error() -> SuiteReport:
    """Suite where a test has a clean assertion error (no traceback)."""
    return SuiteReport(
        name="error-name-test",
        timestamp="2026-02-07T10:00:00Z",
        duration_ms=100.0,
        tests=[
            TestReport(
                name="tests/showcase/test_hero.py::TestSavingsPlanningSession::test_01_establish_context[gpt-4.1]",
                outcome="failed",
                duration_ms=100.0,
                agent_result=_make_result(success=False),
                error="AssertionError: no concrete savings suggestion",
                agent_id="agent-2",
                agent_name="gpt-4.1",
                model="gpt-4.1",
                docstring="First turn: check balances and discuss savings goals.",
                class_docstring="Multi-turn session: Planning savings transfers.",
            ),
        ],
        passed=0,
        failed=1,
    )


# ── TestReport.display_name ─────────────────────────────────────────────────


class TestDisplayName:
    """TestReport.display_name returns human-readable text."""

    def test_uses_docstring_when_available(self) -> None:
        report = TestReport(
            name="tests/test_hero.py::TestFoo::test_bar[gpt-5-mini]",
            outcome="passed",
            duration_ms=100.0,
            docstring="Check account balance for a specific account.",
        )
        assert report.display_name == "Check account balance for a specific account."

    def test_falls_back_to_short_name(self) -> None:
        report = TestReport(
            name="tests/test_hero.py::TestFoo::test_bar[gpt-5-mini]",
            outcome="passed",
            duration_ms=100.0,
        )
        assert report.display_name == "test_bar[gpt-5-mini]"

    def test_uses_first_line_of_multiline_docstring(self) -> None:
        report = TestReport(
            name="test_x",
            outcome="passed",
            duration_ms=100.0,
            docstring="First line.\n\nSecond paragraph with details.",
        )
        assert report.display_name == "First line."

    def test_does_not_contain_double_colon(self) -> None:
        """display_name must never contain '::' (raw nodeid separator)."""
        report = TestReport(
            name="tests/test_hero.py::TestFoo::test_bar",
            outcome="passed",
            duration_ms=100.0,
            docstring="Some meaningful description.",
        )
        assert "::" not in report.display_name


# ── AI Analysis Input ────────────────────────────────────────────────────────


class TestAnalysisInputHumanReadable:
    """AI analysis input uses human-readable names, not raw nodeids."""

    def test_headings_use_docstrings(self) -> None:
        """### headings should be docstrings, not raw nodeids."""
        suite = _make_suite_with_class_docstrings()
        context = _build_analysis_input(suite, [], [], {})
        assert "### Transfer money and verify" in context
        assert "### Check account balance" in context

    def test_headings_do_not_contain_nodeids(self) -> None:
        suite = _make_suite_with_class_docstrings()
        context = _build_analysis_input(suite, [], [], {})
        assert "test_transfer_and_verify" not in context
        assert "TestCoreOperations" not in context
        assert "test_hero.py" not in context

    def test_group_context_uses_class_docstring(self) -> None:
        suite = _make_suite_with_class_docstrings()
        context = _build_analysis_input(suite, [], [], {})
        assert "Core banking tests" in context

    def test_error_is_clean_assertion_not_traceback(self) -> None:
        """Error field contains the assertion message, no tracebacks or nodeids."""
        suite = _make_suite_with_error()
        context = _build_analysis_input(suite, [], [], {})
        # Clean assertion message is present
        assert "AssertionError: no concrete savings suggestion" in context
        # No raw nodeids or file paths
        assert "TestSavingsPlanningSession::" not in context
        assert "test_hero.py" not in context
        # The heading uses the docstring
        assert "### First turn: check balances" in context


# ── Markdown Report Human-Readable Names ─────────────────────────────────────


class TestMarkdownHumanReadableNames:
    """Markdown reports use human-readable names everywhere."""

    def test_group_heading_uses_class_docstring(
        self, insights: InsightsResult, tmp_path: Path
    ) -> None:
        suite = _make_suite_with_class_docstrings()
        output = tmp_path / "report.md"
        generate_md(suite, output, insights=insights)
        md = output.read_text(encoding="utf-8")
        assert "Core banking tests" in md

    def test_group_heading_not_raw_class_name(
        self, insights: InsightsResult, tmp_path: Path
    ) -> None:
        suite = _make_suite_with_class_docstrings()
        output = tmp_path / "report.md"
        generate_md(suite, output, insights=insights)
        md = output.read_text(encoding="utf-8")
        assert "TestCoreOperations" not in md

    def test_test_name_uses_docstring(self, insights: InsightsResult, tmp_path: Path) -> None:
        suite = _make_suite_with_class_docstrings()
        output = tmp_path / "report.md"
        generate_md(suite, output, insights=insights)
        md = output.read_text(encoding="utf-8")
        assert "Transfer money and verify" in md
        assert "Check account balance" in md

    def test_no_double_colon_in_test_names(self, insights: InsightsResult, tmp_path: Path) -> None:
        """No raw '::' separators should appear in test names."""
        suite = _make_suite_with_class_docstrings()
        output = tmp_path / "report.md"
        generate_md(suite, output, insights=insights)
        md = output.read_text(encoding="utf-8")
        # Filter out the AI insights section (which is free-form LLM text)
        # and the footer, just check the test results section
        results_section = md.split("## Test Results")[1] if "## Test Results" in md else md
        # Exclude the footer
        if "---" in results_section:
            results_section = results_section.split("---")[0]
        assert "::" not in results_section


# ── HTML Report Human-Readable Names ─────────────────────────────────────────


class TestHtmlHumanReadableNames:
    """HTML reports use human-readable names in user-visible elements."""

    def test_group_heading_uses_class_docstring(
        self, insights: InsightsResult, tmp_path: Path
    ) -> None:
        suite = _make_suite_with_class_docstrings()
        output = tmp_path / "report.html"
        generate_html(suite, output, insights=insights)
        html = output.read_text(encoding="utf-8")
        assert "Core banking tests" in html

    def test_test_label_uses_docstring(self, insights: InsightsResult, tmp_path: Path) -> None:
        suite = _make_suite_with_class_docstrings()
        output = tmp_path / "report.html"
        generate_html(suite, output, insights=insights)
        html = output.read_text(encoding="utf-8")
        assert "Transfer money and verify" in html
        assert "Check account balance" in html

    def test_group_heading_not_raw_class_name(
        self, insights: InsightsResult, tmp_path: Path
    ) -> None:
        """Raw Python class names should not appear in visible group headers."""
        suite = _make_suite_with_class_docstrings()
        output = tmp_path / "report.html"
        generate_html(suite, output, insights=insights)
        html = output.read_text(encoding="utf-8")
        # The raw class name should not appear as group header text.
        # It may appear in data-attributes (internal), but not in
        # user-visible <span> text within group-header.
        # Extract group header spans
        header_texts = re.findall(r'class="font-medium text-text-light">([^<]+)<', html)
        for text in header_texts:
            assert "TestCoreOperations" not in text, f"Raw class name found in group header: {text}"
