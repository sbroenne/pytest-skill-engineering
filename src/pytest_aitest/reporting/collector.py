"""Report collector and data structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pytest_aitest.core.result import AgentResult


@dataclass
class TestReport:
    """Report data for a single test.

    Attributes:
        name: Full test node ID (e.g., "test_weather[gpt-4o-PROMPT_V1]")
        outcome: Test outcome - "passed", "failed", or "skipped"
        duration_ms: Test duration in milliseconds
        agent_result: Optional AgentResult from aitest_run
        error: Error message if test failed
        assertions: List of assertion results
        metadata: Additional test metadata (model, prompt, etc.)
    """

    name: str
    outcome: str  # "passed", "failed", "skipped"
    duration_ms: float
    agent_result: AgentResult | None = None
    error: str | None = None
    assertions: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_passed(self) -> bool:
        return self.outcome == "passed"

    @property
    def is_failed(self) -> bool:
        return self.outcome == "failed"

    @property
    def model(self) -> str | None:
        """Get model name from metadata if present."""
        return self.metadata.get("model")

    @property
    def prompt_name(self) -> str | None:
        """Get prompt name from metadata if present."""
        return self.metadata.get("prompt")

    @property
    def tokens_used(self) -> int:
        """Get total tokens used from agent_result if present."""
        if self.agent_result:
            return self.agent_result.token_usage.get(
                "prompt", 0
            ) + self.agent_result.token_usage.get("completion", 0)
        return 0

    @property
    def tool_calls(self) -> list[str]:
        """Get tool call names from agent_result if present."""
        if self.agent_result:
            return [tc.name for tc in self.agent_result.all_tool_calls]
        return []


@dataclass
class SuiteReport:
    """Report data for a test suite.

    Automatically computes statistics from test results.
    """

    name: str
    timestamp: str
    duration_ms: float
    tests: list[TestReport] = field(default_factory=list)
    passed: int = 0
    failed: int = 0
    skipped: int = 0

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.skipped

    @property
    def pass_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.passed / self.total * 100

    @property
    def total_tokens(self) -> int:
        """Sum of all tokens used."""
        total = 0
        for t in self.tests:
            if t.agent_result:
                total += t.agent_result.token_usage.get("prompt", 0)
                total += t.agent_result.token_usage.get("completion", 0)
        return total

    @property
    def total_cost_usd(self) -> float:
        """Sum of all costs in USD."""
        return sum(t.agent_result.cost_usd for t in self.tests if t.agent_result)

    @property
    def token_stats(self) -> dict[str, int]:
        """Get min/max/avg token usage."""
        tokens = [
            t.agent_result.token_usage.get("prompt", 0)
            + t.agent_result.token_usage.get("completion", 0)
            for t in self.tests
            if t.agent_result
        ]
        if not tokens:
            return {"min": 0, "max": 0, "avg": 0}
        return {
            "min": min(tokens),
            "max": max(tokens),
            "avg": sum(tokens) // len(tokens),
        }

    @property
    def cost_stats(self) -> dict[str, float]:
        """Get min/max/avg cost in USD."""
        costs = [
            t.agent_result.cost_usd
            for t in self.tests
            if t.agent_result and t.agent_result.cost_usd > 0
        ]
        if not costs:
            return {"min": 0.0, "max": 0.0, "avg": 0.0}
        return {
            "min": min(costs),
            "max": max(costs),
            "avg": sum(costs) / len(costs),
        }

    @property
    def duration_stats(self) -> dict[str, float]:
        """Get min/max/avg duration in ms."""
        durations = [t.duration_ms for t in self.tests if t.duration_ms > 0]
        if not durations:
            return {"min": 0.0, "max": 0.0, "avg": 0.0}
        return {
            "min": min(durations),
            "max": max(durations),
            "avg": sum(durations) / len(durations),
        }

    @property
    def tool_call_count(self) -> int:
        """Total number of tool calls across all tests."""
        return sum(len(t.agent_result.all_tool_calls) for t in self.tests if t.agent_result)

    @property
    def test_files(self) -> list[str]:
        """Unique test file paths."""
        files = set()
        for t in self.tests:
            # Extract file path from node ID (e.g., "tests/test_basic.py::TestClass::test")
            if "::" in t.name:
                files.add(t.name.split("::")[0])
            else:
                files.add(t.name)
        return sorted(files)

    @property
    def models_used(self) -> list[str]:
        """Unique models used across tests."""
        models = set()
        for t in self.tests:
            if t.model:
                models.add(t.model)
        return sorted(models)

    @property
    def prompts_used(self) -> list[str]:
        """Unique prompts used across tests."""
        prompts = set()
        for t in self.tests:
            if t.prompt_name:
                prompts.add(t.prompt_name)
        return sorted(prompts)


class ReportCollector:
    """Collects test results during pytest run.

    Example:
        collector = ReportCollector()
        collector.add_test(TestReport(name="test_foo", outcome="passed", ...))
        report = collector.build_suite_report("my_tests")
    """

    def __init__(self) -> None:
        self.tests: list[TestReport] = []
        self._start_time: float | None = None

    def add_test(self, test: TestReport) -> None:
        """Add a test result."""
        self.tests.append(test)

    def build_suite_report(self, name: str) -> SuiteReport:
        """Build final suite report from collected tests."""
        passed = sum(1 for t in self.tests if t.outcome == "passed")
        failed = sum(1 for t in self.tests if t.outcome == "failed")
        skipped = sum(1 for t in self.tests if t.outcome == "skipped")
        total_duration = sum(t.duration_ms for t in self.tests)

        return SuiteReport(
            name=name,
            timestamp=datetime.now(timezone.utc).isoformat(),
            duration_ms=total_duration,
            tests=self.tests,
            passed=passed,
            failed=failed,
            skipped=skipped,
        )
