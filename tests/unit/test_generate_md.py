"""Tests for Markdown report generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from pytest_skill_engineering.core.result import AgentResult, ToolCall, Turn
from pytest_skill_engineering.reporting import SuiteReport, TestReport, generate_md
from pytest_skill_engineering.reporting.insights import InsightsResult


@pytest.fixture
def insights() -> InsightsResult:
    """Minimal insights for markdown generation (required)."""
    return InsightsResult(
        markdown_summary="## Verdict\n\nAll tests passed. Deploy with confidence.",
        model="test-model",
        tokens_used=100,
        cost_usd=0.001,
    )


@pytest.fixture
def single_agent_suite() -> SuiteReport:
    """Suite with a single agent, one pass and one fail."""
    result_pass = AgentResult(
        turns=[
            Turn(role="user", content="What's my checking balance?"),
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
            Turn(role="assistant", content="Your checking balance is $1,500."),
        ],
        success=True,
        duration_ms=1500.0,
        token_usage={"prompt": 200, "completion": 100},
        cost_usd=0.002,
    )
    result_fail = AgentResult(
        turns=[
            Turn(role="user", content="Transfer money"),
            Turn(role="assistant", content="I can't do that."),
        ],
        success=False,
        duration_ms=800.0,
        token_usage={"prompt": 80, "completion": 40},
        cost_usd=0.001,
    )
    return SuiteReport(
        name="banking-tests",
        timestamp="2026-02-07T10:00:00Z",
        duration_ms=2300.0,
        tests=[
            TestReport(
                name="TestBanking::test_check_balance",
                outcome="passed",
                duration_ms=1500.0,
                agent_result=result_pass,
                agent_id="agent-1",
                agent_name="banking-bot",
                model="gpt-5-mini",
                docstring="Check account balance",
            ),
            TestReport(
                name="TestBanking::test_transfer_fail",
                outcome="failed",
                duration_ms=800.0,
                agent_result=result_fail,
                error="AssertionError: expected tool call",
                agent_id="agent-1",
                agent_name="banking-bot",
                model="gpt-5-mini",
            ),
        ],
        passed=1,
        failed=1,
    )


@pytest.fixture
def multi_agent_suite() -> SuiteReport:
    """Suite with two agents for leaderboard testing."""
    result_a = AgentResult(
        turns=[Turn(role="assistant", content="ok")],
        success=True,
        duration_ms=100.0,
        token_usage={"prompt": 50, "completion": 30},
        cost_usd=0.001,
    )
    result_b = AgentResult(
        turns=[Turn(role="assistant", content="ok")],
        success=True,
        duration_ms=200.0,
        token_usage={"prompt": 100, "completion": 60},
        cost_usd=0.003,
    )
    result_b_fail = AgentResult(
        turns=[Turn(role="assistant", content="error")],
        success=False,
        duration_ms=150.0,
        token_usage={"prompt": 80, "completion": 40},
        cost_usd=0.002,
    )
    return SuiteReport(
        name="comparison-tests",
        timestamp="2026-02-07T12:00:00Z",
        duration_ms=450.0,
        tests=[
            TestReport(
                name="Tests::test_one",
                outcome="passed",
                duration_ms=100.0,
                agent_result=result_a,
                agent_id="agent-a",
                agent_name="gpt-5-mini",
                model="gpt-5-mini",
            ),
            TestReport(
                name="Tests::test_one",
                outcome="passed",
                duration_ms=200.0,
                agent_result=result_b,
                agent_id="agent-b",
                agent_name="gpt-4.1 + detailed",
                model="gpt-4.1",
                system_prompt_name="detailed",
            ),
            TestReport(
                name="Tests::test_two",
                outcome="passed",
                duration_ms=100.0,
                agent_result=result_a,
                agent_id="agent-a",
                agent_name="gpt-5-mini",
                model="gpt-5-mini",
            ),
            TestReport(
                name="Tests::test_two",
                outcome="failed",
                duration_ms=150.0,
                agent_result=result_b_fail,
                agent_id="agent-b",
                agent_name="gpt-4.1 + detailed",
                model="gpt-4.1",
                system_prompt_name="detailed",
            ),
        ],
        passed=3,
        failed=1,
    )


class TestGenerateMd:
    """Tests for generate_md function."""

    def test_creates_file(
        self, single_agent_suite: SuiteReport, insights: InsightsResult, tmp_path: Path
    ) -> None:
        output = tmp_path / "report.md"
        generate_md(single_agent_suite, output, insights=insights)
        assert output.exists()

    def test_contains_title(
        self, single_agent_suite: SuiteReport, insights: InsightsResult, tmp_path: Path
    ) -> None:
        output = tmp_path / "report.md"
        generate_md(single_agent_suite, output, insights=insights)
        md = output.read_text(encoding="utf-8")
        assert "# banking-tests" in md

    def test_contains_summary_stats(
        self, single_agent_suite: SuiteReport, insights: InsightsResult, tmp_path: Path
    ) -> None:
        output = tmp_path / "report.md"
        generate_md(single_agent_suite, output, insights=insights)
        md = output.read_text(encoding="utf-8")
        assert "**2** tests" in md
        assert "**1** passed" in md
        assert "**1** failed" in md
        assert "50%" in md

    def test_contains_ai_insights(
        self, single_agent_suite: SuiteReport, insights: InsightsResult, tmp_path: Path
    ) -> None:
        output = tmp_path / "report.md"
        generate_md(single_agent_suite, output, insights=insights)
        md = output.read_text(encoding="utf-8")
        assert "## AI Analysis" in md
        assert "Deploy with confidence" in md

    def test_contains_test_results_section(
        self, single_agent_suite: SuiteReport, insights: InsightsResult, tmp_path: Path
    ) -> None:
        output = tmp_path / "report.md"
        generate_md(single_agent_suite, output, insights=insights)
        md = output.read_text(encoding="utf-8")
        assert "## Test Results" in md

    def test_contains_status_emojis(
        self, single_agent_suite: SuiteReport, insights: InsightsResult, tmp_path: Path
    ) -> None:
        output = tmp_path / "report.md"
        generate_md(single_agent_suite, output, insights=insights)
        md = output.read_text(encoding="utf-8")
        assert "✅" in md
        assert "❌" in md

    def test_contains_mermaid_diagram(
        self, single_agent_suite: SuiteReport, insights: InsightsResult, tmp_path: Path
    ) -> None:
        output = tmp_path / "report.md"
        generate_md(single_agent_suite, output, insights=insights)
        md = output.read_text(encoding="utf-8")
        assert "```mermaid" in md
        assert "sequenceDiagram" in md

    def test_contains_tool_calls_table(
        self, single_agent_suite: SuiteReport, insights: InsightsResult, tmp_path: Path
    ) -> None:
        output = tmp_path / "report.md"
        generate_md(single_agent_suite, output, insights=insights)
        md = output.read_text(encoding="utf-8")
        assert "**Tool Calls:**" in md
        assert "`get_balance`" in md

    def test_contains_collapsible_details(
        self, single_agent_suite: SuiteReport, insights: InsightsResult, tmp_path: Path
    ) -> None:
        output = tmp_path / "report.md"
        generate_md(single_agent_suite, output, insights=insights)
        md = output.read_text(encoding="utf-8")
        assert "<details>" in md
        assert "</details>" in md
        assert "<summary>" in md

    def test_contains_error_message(
        self, single_agent_suite: SuiteReport, insights: InsightsResult, tmp_path: Path
    ) -> None:
        output = tmp_path / "report.md"
        generate_md(single_agent_suite, output, insights=insights)
        md = output.read_text(encoding="utf-8")
        assert "AssertionError: expected tool call" in md

    def test_contains_footer(
        self, single_agent_suite: SuiteReport, insights: InsightsResult, tmp_path: Path
    ) -> None:
        output = tmp_path / "report.md"
        generate_md(single_agent_suite, output, insights=insights)
        md = output.read_text(encoding="utf-8")
        assert "pytest-skill-engineering" in md
        assert "---" in md

    def test_uses_docstring_as_display_name(
        self, single_agent_suite: SuiteReport, insights: InsightsResult, tmp_path: Path
    ) -> None:
        output = tmp_path / "report.md"
        generate_md(single_agent_suite, output, insights=insights)
        md = output.read_text(encoding="utf-8")
        assert "Check account balance" in md


class TestGenerateMdMultiAgent:
    """Tests for multi-agent markdown reports."""

    def test_contains_leaderboard(
        self, multi_agent_suite: SuiteReport, insights: InsightsResult, tmp_path: Path
    ) -> None:
        output = tmp_path / "report.md"
        generate_md(multi_agent_suite, output, insights=insights)
        md = output.read_text(encoding="utf-8")
        assert "## Agent Leaderboard" in md

    def test_leaderboard_has_table(
        self, multi_agent_suite: SuiteReport, insights: InsightsResult, tmp_path: Path
    ) -> None:
        output = tmp_path / "report.md"
        generate_md(multi_agent_suite, output, insights=insights)
        md = output.read_text(encoding="utf-8")
        assert "|#|Agent|" in md
        assert "Pass Rate" in md

    def test_leaderboard_shows_winner(
        self, multi_agent_suite: SuiteReport, insights: InsightsResult, tmp_path: Path
    ) -> None:
        output = tmp_path / "report.md"
        generate_md(multi_agent_suite, output, insights=insights)
        md = output.read_text(encoding="utf-8")
        assert "🏆" in md

    def test_leaderboard_shows_prompt_name(
        self, multi_agent_suite: SuiteReport, insights: InsightsResult, tmp_path: Path
    ) -> None:
        output = tmp_path / "report.md"
        generate_md(multi_agent_suite, output, insights=insights)
        md = output.read_text(encoding="utf-8")
        assert "detailed" in md

    def test_no_leaderboard_for_single_agent(
        self, single_agent_suite: SuiteReport, insights: InsightsResult, tmp_path: Path
    ) -> None:
        output = tmp_path / "report.md"
        generate_md(single_agent_suite, output, insights=insights)
        md = output.read_text(encoding="utf-8")
        assert "## Agent Leaderboard" not in md


class TestGenerateMdCli:
    """Tests for CLI markdown report generation."""

    def test_generate_md_from_cli(self, tmp_path: Path) -> None:
        import json

        from pytest_skill_engineering.cli import main

        json_data = {
            "schema_version": "3.0",
            "name": "cli-test",
            "timestamp": "2026-02-07T12:00:00Z",
            "duration_ms": 100.0,
            "passed": 1,
            "failed": 0,
            "skipped": 0,
            "tests": [
                {
                    "name": "test_a",
                    "outcome": "passed",
                    "duration_ms": 100.0,
                    "agent_id": "test-agent",
                    "agent_name": "test-agent",
                    "model": "test-model",
                }
            ],
            "insights": {
                "markdown_summary": "All good.",
                "cost_usd": 0.01,
                "tokens_used": 500,
                "cached": True,
            },
        }
        json_path = tmp_path / "results.json"
        json_path.write_text(json.dumps(json_data), encoding="utf-8")
        md_path = tmp_path / "report.md"

        result = main([str(json_path), "--md", str(md_path)])

        assert result == 0
        assert md_path.exists()
        md = md_path.read_text(encoding="utf-8")
        assert "# cli-test" in md
        assert "All good." in md

    def test_without_insights_fails(self, tmp_path: Path) -> None:
        """Report generation fails when JSON has no AI insights."""
        import json

        from pytest_skill_engineering.cli import main

        json_data = {
            "schema_version": "3.0",
            "name": "no-insights",
            "timestamp": "2026-02-07T12:00:00Z",
            "duration_ms": 100.0,
            "passed": 1,
            "failed": 0,
            "skipped": 0,
            "tests": [
                {
                    "name": "test_a",
                    "outcome": "passed",
                    "duration_ms": 100.0,
                    "agent_id": "test-agent",
                    "agent_name": "test-agent",
                    "model": "test-model",
                }
            ],
        }
        json_path = tmp_path / "results.json"
        json_path.write_text(json.dumps(json_data), encoding="utf-8")
        md_path = tmp_path / "report.md"

        result = main([str(json_path), "--md", str(md_path)])

        assert result == 1
        assert not md_path.exists()

    def test_no_output_format_fails(self, tmp_path: Path) -> None:
        import json

        from pytest_skill_engineering.cli import main

        json_data = {
            "schema_version": "3.0",
            "name": "test",
            "timestamp": "2026-01-01",
            "duration_ms": 0,
            "tests": [],
            "passed": 0,
            "failed": 0,
        }
        json_path = tmp_path / "results.json"
        json_path.write_text(json.dumps(json_data), encoding="utf-8")

        result = main([str(json_path)])
        assert result == 1

    def test_both_html_and_md(self, tmp_path: Path) -> None:
        import json

        from pytest_skill_engineering.cli import main

        json_data = {
            "schema_version": "3.0",
            "name": "both-formats",
            "timestamp": "2026-02-07T12:00:00Z",
            "duration_ms": 100.0,
            "passed": 1,
            "failed": 0,
            "skipped": 0,
            "tests": [
                {
                    "name": "test_a",
                    "outcome": "passed",
                    "duration_ms": 100.0,
                    "agent_id": "test-agent",
                    "agent_name": "test-agent",
                    "model": "test-model",
                }
            ],
            "insights": {
                "markdown_summary": "Tests passed.",
                "cost_usd": 0.01,
                "tokens_used": 500,
                "cached": True,
            },
        }
        json_path = tmp_path / "results.json"
        json_path.write_text(json.dumps(json_data), encoding="utf-8")
        html_path = tmp_path / "report.html"
        md_path = tmp_path / "report.md"

        result = main([str(json_path), "--html", str(html_path), "--md", str(md_path)])

        assert result == 0
        assert html_path.exists()
        assert md_path.exists()
