"""Tests for pytest-aitest reporting module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pytest_aitest.reporting import (
    ReportCollector,
    ReportGenerator,
    SuiteReport,
    TestReport,
    generate_mermaid_sequence,
)
from pytest_aitest.result import AgentResult, ToolCall, Turn


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
        result1 = AgentResult(
            turns=[], success=True, token_usage={"prompt": 100, "completion": 50}
        )
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

    def test_cost_stats(self) -> None:
        results = [
            AgentResult(turns=[], success=True, cost_usd=0.01),
            AgentResult(turns=[], success=True, cost_usd=0.02),
            AgentResult(turns=[], success=True, cost_usd=0.03),
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
        stats = suite.cost_stats
        assert stats["min"] == pytest.approx(0.01)
        assert stats["max"] == pytest.approx(0.03)
        assert stats["avg"] == pytest.approx(0.02)

    def test_cost_stats_empty(self) -> None:
        suite = SuiteReport(name="suite", timestamp="2026-01-31T00:00:00Z", duration_ms=0.0)
        stats = suite.cost_stats
        assert stats == {"min": 0.0, "max": 0.0, "avg": 0.0}


class TestReportCollector:
    """Tests for ReportCollector."""

    def test_add_test(self) -> None:
        collector = ReportCollector()
        report = TestReport(name="test_foo", outcome="passed", duration_ms=100.0)
        collector.add_test(report)
        assert len(collector.tests) == 1
        assert collector.tests[0].name == "test_foo"

    def test_build_suite_report(self) -> None:
        collector = ReportCollector()
        collector.add_test(TestReport(name="t1", outcome="passed", duration_ms=100.0))
        collector.add_test(TestReport(name="t2", outcome="failed", duration_ms=200.0))
        collector.add_test(TestReport(name="t3", outcome="skipped", duration_ms=50.0))

        suite = collector.build_suite_report("my-suite")

        assert suite.name == "my-suite"
        assert suite.passed == 1
        assert suite.failed == 1
        assert suite.skipped == 1
        assert suite.total == 3
        assert suite.duration_ms == 350.0
        assert len(suite.tests) == 3

    def test_build_suite_report_empty(self) -> None:
        collector = ReportCollector()
        suite = collector.build_suite_report("empty")

        assert suite.name == "empty"
        assert suite.total == 0


class TestReportGenerator:
    """Tests for ReportGenerator."""

    @pytest.fixture
    def generator(self) -> ReportGenerator:
        return ReportGenerator()

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
                ),
                TestReport(
                    name="test_failed",
                    outcome="failed",
                    duration_ms=300.0,
                    error="AssertionError: expected True",
                ),
            ],
            passed=1,
            failed=1,
        )

    def test_generate_json(self, generator: ReportGenerator, sample_suite: SuiteReport, tmp_path: Path) -> None:
        output = tmp_path / "report.json"
        generator.generate_json(sample_suite, output)

        assert output.exists()
        data = json.loads(output.read_text())

        assert data["name"] == "test-suite"
        assert data["summary"]["total"] == 2
        assert data["summary"]["passed"] == 1
        assert data["summary"]["failed"] == 1
        assert data["summary"]["pass_rate"] == 50.0
        assert len(data["tests"]) == 2

    def test_generate_json_test_details(self, generator: ReportGenerator, sample_suite: SuiteReport, tmp_path: Path) -> None:
        output = tmp_path / "report.json"
        generator.generate_json(sample_suite, output)

        data = json.loads(output.read_text())
        test_passed = next(t for t in data["tests"] if t["outcome"] == "passed")
        test_failed = next(t for t in data["tests"] if t["outcome"] == "failed")

        assert test_passed["agent_result"]["success"] is True
        assert test_passed["agent_result"]["tools_called"] == ["greet"]
        assert test_failed["error"] == "AssertionError: expected True"

    def test_generate_html(self, generator: ReportGenerator, sample_suite: SuiteReport, tmp_path: Path) -> None:
        output = tmp_path / "report.html"
        generator.generate_html(sample_suite, output)

        assert output.exists()
        html = output.read_text()

        assert "test-suite" in html
        assert "test_example" in html
        assert "test_failed" in html
        assert "50.0%" in html or "50%" in html  # pass rate

    def test_generate_html_contains_mermaid(self, generator: ReportGenerator, sample_suite: SuiteReport, tmp_path: Path) -> None:
        output = tmp_path / "report.html"
        generator.generate_html(sample_suite, output)

        html = output.read_text()
        # Should contain Mermaid sequence diagram
        assert "sequenceDiagram" in html or "mermaid" in html.lower()

    def test_format_cost(self) -> None:
        assert ReportGenerator._format_cost(0) == "N/A"
        assert ReportGenerator._format_cost(0.001) == "$0.001000"
        assert ReportGenerator._format_cost(0.01) == "$0.0100"
        assert ReportGenerator._format_cost(1.5) == "$1.5000"


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
        assert "\"hello\"" not in mermaid
        assert "'hello'" in mermaid
