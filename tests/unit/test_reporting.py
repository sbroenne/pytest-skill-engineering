"""Tests for pytest-skill-engineering reporting module."""

from __future__ import annotations

from pathlib import Path

import pytest

from pytest_skill_engineering.core.result import AgentResult, ToolCall, Turn
from pytest_skill_engineering.reporting import (
    SuiteReport,
    TestReport,
    build_suite_report,
    generate_html,
    generate_mermaid_sequence,
)
from pytest_skill_engineering.reporting.insights import InsightsResult

_TEST_INSIGHTS = InsightsResult(
    markdown_summary="Test insights.",
    model="test-model",
)


class TestTestReport:
    """Tests for TestReport dataclass."""

    def test_basic_passed(self) -> None:
        report = TestReport(name="test_foo", outcome="passed", duration_ms=100.0)
        assert report.name == "test_foo"
        assert report.outcome == "passed"
        assert report.duration_ms == 100.0
        assert report.agent_result is None
        assert report.error is None

    def test_with_error(self) -> None:
        report = TestReport(
            name="test_bar", outcome="failed", duration_ms=50.0, error="AssertionError"
        )
        assert report.outcome == "failed"
        assert report.error == "AssertionError"

    def test_with_agent_result(self) -> None:
        result = AgentResult(turns=[], success=True, duration_ms=50.0)
        report = TestReport(
            name="test_agent", outcome="passed", duration_ms=100.0, agent_result=result
        )
        assert report.agent_result is not None
        assert report.agent_result.success


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
        result1 = AgentResult(turns=[], success=True, token_usage={"prompt": 100, "completion": 50})
        result2 = AgentResult(
            turns=[], success=True, token_usage={"prompt": 200, "completion": 100}
        )
        suite = SuiteReport(
            name="suite",
            timestamp="2026-01-31T00:00:00Z",
            duration_ms=1000.0,
            tests=[
                TestReport(name="t1", outcome="passed", duration_ms=100.0, agent_result=result1),
                TestReport(name="t2", outcome="passed", duration_ms=100.0, agent_result=result2),
            ],
            passed=2,
        )
        assert suite.total_tokens == 450  # 100+50+200+100

    def test_total_cost(self) -> None:
        result1 = AgentResult(turns=[], success=True, cost_usd=0.01)
        result2 = AgentResult(turns=[], success=True, cost_usd=0.02)
        suite = SuiteReport(
            name="suite",
            timestamp="2026-01-31T00:00:00Z",
            duration_ms=1000.0,
            tests=[
                TestReport(name="t1", outcome="passed", duration_ms=100.0, agent_result=result1),
                TestReport(name="t2", outcome="passed", duration_ms=100.0, agent_result=result2),
            ],
            passed=2,
        )
        assert suite.total_cost_usd == pytest.approx(0.03)

    def test_token_stats(self) -> None:
        results = [
            AgentResult(turns=[], success=True, token_usage={"prompt": 50, "completion": 50}),
            AgentResult(turns=[], success=True, token_usage={"prompt": 100, "completion": 100}),
            AgentResult(turns=[], success=True, token_usage={"prompt": 150, "completion": 150}),
        ]
        suite = SuiteReport(
            name="suite",
            timestamp="2026-01-31T00:00:00Z",
            duration_ms=1000.0,
            tests=[
                TestReport(name=f"t{i}", outcome="passed", duration_ms=100.0, agent_result=r)
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


class TestReportGenerator:
    """Tests for generate_html/generate_json."""

    @pytest.fixture
    def sample_suite(self) -> SuiteReport:
        result = AgentResult(
            turns=[
                Turn(role="user", content="Hello"),
                Turn(
                    role="assistant",
                    content="Hi!",
                    tool_calls=[ToolCall(name="greet", arguments={}, result="ok")],
                ),
            ],
            success=True,
            duration_ms=150.0,
            token_usage={"prompt": 100, "completion": 50},
            cost_usd=0.001,
        )
        return SuiteReport(
            name="test-suite",
            timestamp="2026-01-31T12:00:00Z",
            duration_ms=500.0,
            tests=[
                TestReport(
                    name="test_example",
                    outcome="passed",
                    duration_ms=200.0,
                    agent_result=result,
                    agent_id="test-agent",
                    agent_name="test-agent",
                    model="test-model",
                ),
                TestReport(
                    name="test_failed",
                    outcome="failed",
                    duration_ms=300.0,
                    error="AssertionError: expected True",
                    agent_id="test-agent",
                    agent_name="test-agent",
                    model="test-model",
                ),
            ],
            passed=1,
            failed=1,
        )

    def test_generate_html(self, sample_suite: SuiteReport, tmp_path: Path) -> None:
        output = tmp_path / "report.html"
        generate_html(sample_suite, output, insights=_TEST_INSIGHTS)

        assert output.exists()
        html = output.read_text(encoding="utf-8")

        assert "test-suite" in html
        assert "test_example" in html
        assert "test_failed" in html
        # Pass rate shown in header or agent selector
        assert "2 tests" in html or "1 Failed" in html  # summary stats shown differently now

    def test_generate_html_contains_mermaid(
        self, sample_suite: SuiteReport, tmp_path: Path
    ) -> None:
        output = tmp_path / "report.html"
        generate_html(sample_suite, output, insights=_TEST_INSIGHTS)

        html = output.read_text(encoding="utf-8")
        # Should contain Mermaid sequence diagram
        assert "sequenceDiagram" in html or "mermaid" in html.lower()


class TestGenerateMermaidSequence:
    """Tests for Mermaid sequence diagram generation."""

    def test_simple_conversation(self) -> None:
        result = AgentResult(
            turns=[
                Turn(role="user", content="Hello"),
                Turn(role="assistant", content="Hi there!"),
            ],
            success=True,
        )
        mermaid = generate_mermaid_sequence(result)

        assert "sequenceDiagram" in mermaid
        assert 'User->>Agent: "Hello"' in mermaid
        assert 'Agent->>User: "Hi there!"' in mermaid

    def test_with_tool_calls(self) -> None:
        result = AgentResult(
            turns=[
                Turn(role="user", content="Read a file"),
                Turn(
                    role="assistant",
                    content="",
                    tool_calls=[
                        ToolCall(
                            name="read_file",
                            arguments={"path": "/tmp/test.txt"},
                            result="file contents here",
                        )
                    ],
                ),
                Turn(role="assistant", content="Here is the content"),
            ],
            success=True,
        )
        mermaid = generate_mermaid_sequence(result)

        assert 'Agent->>Tools: "read_file' in mermaid
        assert 'Tools-->>Agent: "file contents here"' in mermaid
        assert 'Agent->>User: "Here is the content"' in mermaid

    def test_tool_error(self) -> None:
        result = AgentResult(
            turns=[
                Turn(role="user", content="Read nonexistent"),
                Turn(
                    role="assistant",
                    content="",
                    tool_calls=[
                        ToolCall(
                            name="read_file",
                            arguments={"path": "/nope"},
                            error="File not found",
                        )
                    ],
                ),
            ],
            success=True,
        )
        mermaid = generate_mermaid_sequence(result)

        assert 'Tools--xAgent: "Error: File not found"' in mermaid

    def test_content_truncation(self) -> None:
        long_content = "A" * 100
        result = AgentResult(
            turns=[Turn(role="user", content=long_content)],
            success=True,
        )
        mermaid = generate_mermaid_sequence(result)

        # Content should be truncated to 80 chars (the actual truncation length)
        assert 'User->>Agent: "' + "A" * 80 in mermaid

    def test_escapes_quotes(self) -> None:
        result = AgentResult(
            turns=[Turn(role="user", content='Say "hello"')],
            success=True,
        )
        mermaid = generate_mermaid_sequence(result)

        # Double quotes should be replaced with single quotes
        assert '"hello"' not in mermaid
        assert "'hello'" in mermaid


class TestAgentLeaderboardSortOrder:
    """Tests for agent leaderboard sorting logic.

    Sorting priority:
    1. Pass rate (descending) - higher pass rate wins
    2. Cost (ascending) - lower cost wins when pass rates are equal
    3. Name (ascending) - alphabetical tiebreaker
    """

    def _make_report_with_models(self, model_stats: list[dict]) -> SuiteReport:
        """Create a report with specific model statistics.

        Args:
            model_stats: List of dicts with keys: model, passed, failed, cost
        """
        tests = []
        for stat in model_stats:
            model = stat["model"]
            passed = stat.get("passed", 0)
            failed = stat.get("failed", 0)
            cost_per_test = stat.get("cost", 0.01) / max(passed + failed, 1)

            for i in range(passed):
                result = AgentResult(
                    turns=[Turn(role="assistant", content="ok")],
                    success=True,
                    cost_usd=cost_per_test,
                )
                tests.append(
                    TestReport(
                        name=f"test_{model}_{i}",
                        outcome="passed",
                        duration_ms=100.0,
                        agent_result=result,
                        agent_id=model,
                        agent_name=model,
                        model=model,
                    )
                )
            for i in range(failed):
                result = AgentResult(
                    turns=[Turn(role="assistant", content="err")],
                    success=False,
                    cost_usd=cost_per_test,
                )
                tests.append(
                    TestReport(
                        name=f"test_{model}_fail_{i}",
                        outcome="failed",
                        duration_ms=100.0,
                        agent_result=result,
                        agent_id=model,
                        agent_name=model,
                        model=model,
                    )
                )

        return SuiteReport(
            name="test-suite",
            timestamp="2026-01-31T12:00:00Z",
            duration_ms=1000.0,
            tests=tests,
            passed=sum(s.get("passed", 0) for s in model_stats),
            failed=sum(s.get("failed", 0) for s in model_stats),
        )

    def test_higher_pass_rate_wins(self, tmp_path: Path):
        """Model with higher pass rate should rank first."""
        report = self._make_report_with_models(
            [
                {"model": "model-a", "passed": 8, "failed": 2, "cost": 0.10},  # 80%
                {"model": "model-b", "passed": 10, "failed": 0, "cost": 0.20},  # 100%
            ]
        )

        output = tmp_path / "report.html"
        generate_html(report, output, insights=_TEST_INSIGHTS)
        html = output.read_text(encoding="utf-8")

        # Find the leaderboard section
        leaderboard_start = html.find("Agent Leaderboard")
        assert leaderboard_start > 0, "Leaderboard section not found"
        leaderboard_html = html[leaderboard_start : leaderboard_start + 2000]

        # In the leaderboard, model-b (100%) should come before model-a (80%)
        assert leaderboard_html.index("model-b") < leaderboard_html.index("model-a")

    def test_lower_cost_wins_when_pass_rate_equal(self, tmp_path: Path):
        """When pass rates are equal, lower cost should win."""
        report = self._make_report_with_models(
            [
                {"model": "gpt-4.1", "passed": 5, "failed": 0, "cost": 0.10},  # 100%, $0.10
                {"model": "gpt-5-mini", "passed": 5, "failed": 0, "cost": 0.05},  # 100%, $0.05
            ]
        )

        output = tmp_path / "report.html"
        generate_html(report, output, insights=_TEST_INSIGHTS)
        html = output.read_text(encoding="utf-8")

        # Find the leaderboard section
        leaderboard_start = html.find("Agent Leaderboard")
        assert leaderboard_start > 0, "Leaderboard section not found"
        leaderboard_html = html[leaderboard_start : leaderboard_start + 2000]

        # gpt-5-mini (cheaper) should come before gpt-4.1 when both are 100%
        assert leaderboard_html.index("gpt-5-mini") < leaderboard_html.index("gpt-4.1")

    def test_alphabetical_when_pass_rate_and_cost_equal(self, tmp_path: Path):
        """When pass rate and cost are equal, alphabetical order wins."""
        report = self._make_report_with_models(
            [
                {"model": "model-z", "passed": 5, "failed": 0, "cost": 0.10},
                {"model": "model-a", "passed": 5, "failed": 0, "cost": 0.10},
            ]
        )

        output = tmp_path / "report.html"
        generate_html(report, output, insights=_TEST_INSIGHTS)
        html = output.read_text(encoding="utf-8")

        # Find the leaderboard section
        leaderboard_start = html.find("Agent Leaderboard")
        assert leaderboard_start > 0, "Leaderboard section not found"
        leaderboard_html = html[leaderboard_start : leaderboard_start + 2000]

        # model-a should come before model-z alphabetically
        assert leaderboard_html.index("model-a") < leaderboard_html.index("model-z")

    def test_real_world_scenario_ai_summary_match(self, tmp_path: Path):
        """Test the real-world scenario from the bug report.

        Both models at 100%, but gpt-5-mini is cheaper and should win.
        This matches what the AI summary would recommend.
        """
        report = self._make_report_with_models(
            [
                {"model": "gpt-4.1", "passed": 9, "failed": 0, "cost": 0.0210},
                {"model": "gpt-5-mini", "passed": 9, "failed": 0, "cost": 0.0145},
            ]
        )

        output = tmp_path / "report.html"
        generate_html(report, output, insights=_TEST_INSIGHTS)
        html = output.read_text(encoding="utf-8")

        # Find the leaderboard section
        leaderboard_start = html.find("Agent Leaderboard")
        assert leaderboard_start > 0, "Leaderboard section not found"
        leaderboard_html = html[leaderboard_start : leaderboard_start + 2000]

        # gpt-5-mini should rank first (cheaper with same pass rate)
        gpt5_pos = leaderboard_html.find("gpt-5-mini")
        gpt4_pos = leaderboard_html.find("gpt-4.1")

        assert gpt5_pos > 0, "gpt-5-mini not found in leaderboard"
        assert gpt4_pos > 0, "gpt-4.1 not found in leaderboard"
        assert gpt5_pos < gpt4_pos, "gpt-5-mini should rank before gpt-4.1 (lower cost)"
