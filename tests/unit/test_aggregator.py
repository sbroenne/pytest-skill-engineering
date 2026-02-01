"""Tests for reporting.aggregator module - dimension detection."""

import pytest

from pytest_aitest.core.result import AgentResult, Turn
from pytest_aitest.reporting.aggregator import (
    DimensionAggregator,
    GroupedResult,
    MatrixCell,
    ReportMode,
    TestDimensions,
)
from pytest_aitest.reporting.collector import SuiteReport, TestReport


def make_test_report(
    name: str,
    outcome: str = "passed",
    model: str | None = None,
    prompt: str | None = None,
) -> TestReport:
    """Helper to create test reports with optional metadata."""
    metadata = {}
    if model:
        metadata["model"] = model
    if prompt:
        metadata["prompt"] = prompt

    result = AgentResult(
        turns=[Turn(role="assistant", content="Hello")],
        success=outcome == "passed",
        duration_ms=100,
        token_usage={"prompt": 100, "completion": 50},
        cost_usd=0.001,
    )

    return TestReport(
        name=name,
        outcome=outcome,
        duration_ms=100,
        agent_result=result,
        metadata=metadata,
    )


def make_suite(*tests: TestReport) -> SuiteReport:
    """Helper to create suite reports."""
    passed = sum(1 for t in tests if t.outcome == "passed")
    failed = sum(1 for t in tests if t.outcome == "failed")
    return SuiteReport(
        name="test",
        timestamp="2026-01-01T00:00:00Z",
        duration_ms=sum(t.duration_ms for t in tests),
        tests=list(tests),
        passed=passed,
        failed=failed,
    )


class TestDimensionDetection:
    """Tests for detecting test dimensions from parametrized tests."""

    def test_simple_mode_no_parametrize(self) -> None:
        """Tests without parametrization detected as SIMPLE."""
        suite = make_suite(
            make_test_report("test_foo"),
            make_test_report("test_bar"),
        )

        aggregator = DimensionAggregator()
        dims = aggregator.detect_dimensions(suite)

        assert dims.mode == ReportMode.SIMPLE
        assert dims.models == []
        assert dims.prompts == []

    def test_model_comparison_from_metadata(self) -> None:
        """Model dimension detected from test metadata."""
        suite = make_suite(
            make_test_report("test_foo", model="gpt-4o"),
            make_test_report("test_foo", model="claude-3-haiku"),
        )

        aggregator = DimensionAggregator()
        dims = aggregator.detect_dimensions(suite)

        assert dims.mode == ReportMode.MODEL_COMPARISON
        assert sorted(dims.models) == ["claude-3-haiku", "gpt-4o"]
        assert dims.prompts == []

    def test_model_comparison_from_node_id(self) -> None:
        """Model dimension detected from pytest node ID."""
        suite = make_suite(
            make_test_report("test_foo[gpt-4o]"),
            make_test_report("test_foo[gpt-4o-mini]"),
        )

        aggregator = DimensionAggregator()
        dims = aggregator.detect_dimensions(suite)

        assert dims.mode == ReportMode.MODEL_COMPARISON
        assert "gpt-4o" in dims.models
        assert "gpt-4o-mini" in dims.models

    def test_prompt_comparison_from_metadata(self) -> None:
        """Prompt dimension detected from test metadata."""
        suite = make_suite(
            make_test_report("test_foo", prompt="PROMPT_V1"),
            make_test_report("test_foo", prompt="PROMPT_V2"),
        )

        aggregator = DimensionAggregator()
        dims = aggregator.detect_dimensions(suite)

        assert dims.mode == ReportMode.PROMPT_COMPARISON
        assert sorted(dims.prompts) == ["PROMPT_V1", "PROMPT_V2"]
        assert dims.models == []

    def test_matrix_mode_both_dimensions(self) -> None:
        """Matrix mode detected when both model and prompt vary."""
        suite = make_suite(
            make_test_report("test[gpt-4o-PROMPT_V1]", model="gpt-4o", prompt="PROMPT_V1"),
            make_test_report("test[gpt-4o-PROMPT_V2]", model="gpt-4o", prompt="PROMPT_V2"),
            make_test_report("test[claude-PROMPT_V1]", model="claude-3-haiku", prompt="PROMPT_V1"),
            make_test_report("test[claude-PROMPT_V2]", model="claude-3-haiku", prompt="PROMPT_V2"),
        )

        aggregator = DimensionAggregator()
        dims = aggregator.detect_dimensions(suite)

        assert dims.mode == ReportMode.MATRIX
        assert len(dims.models) == 2
        assert len(dims.prompts) == 2


class TestParseNodeId:
    """Tests for parsing pytest node IDs."""

    def test_parse_simple_test(self) -> None:
        """Parse test without parameters."""
        aggregator = DimensionAggregator()
        base, params = aggregator._parse_node_id("test_example")

        assert base == "test_example"
        assert params == []

    def test_parse_single_param(self) -> None:
        """Parse test with single parameter."""
        aggregator = DimensionAggregator()
        base, params = aggregator._parse_node_id("test_example[gpt-4o]")

        assert base == "test_example"
        assert "gpt-4o" in params

    def test_parse_multiple_params(self) -> None:
        """Parse test with multiple parameters."""
        aggregator = DimensionAggregator()
        base, params = aggregator._parse_node_id("test_example[gpt-4o-PROMPT_V1]")

        assert base == "test_example"
        # Should split into model and prompt parts
        assert len(params) >= 1


class TestGroupByModel:
    """Tests for grouping results by model."""

    def test_groups_by_model(self) -> None:
        """Results are grouped by model name."""
        suite = make_suite(
            make_test_report("test_a", model="gpt-4o", outcome="passed"),
            make_test_report("test_b", model="gpt-4o", outcome="passed"),
            make_test_report("test_a", model="claude", outcome="failed"),
        )

        aggregator = DimensionAggregator()
        groups = aggregator.group_by_model(suite)

        assert len(groups) == 2
        # Sorted by pass rate (descending), gpt-4o has 100%, claude has 0%
        assert groups[0].dimension_value == "gpt-4o"
        assert groups[0].passed == 2
        assert groups[1].dimension_value == "claude"
        assert groups[1].failed == 1

    def test_grouped_result_computes_stats(self) -> None:
        """GroupedResult computes pass rate and totals."""
        tests = [
            make_test_report("test_a", outcome="passed"),
            make_test_report("test_b", outcome="passed"),
            make_test_report("test_c", outcome="failed"),
        ]

        group = GroupedResult(dimension_value="test", tests=tests)

        assert group.passed == 2
        assert group.failed == 1
        assert group.pass_rate == pytest.approx(66.67, rel=0.1)
        assert group.total_tokens == 450  # 3 tests * 150 tokens each


class TestGroupByPrompt:
    """Tests for grouping results by prompt."""

    def test_groups_by_prompt(self) -> None:
        """Results are grouped by prompt name."""
        suite = make_suite(
            make_test_report("test", prompt="PROMPT_V1", outcome="passed"),
            make_test_report("test", prompt="PROMPT_V2", outcome="failed"),
        )

        aggregator = DimensionAggregator()
        groups = aggregator.group_by_prompt(suite)

        assert len(groups) == 2


class TestBuildMatrix:
    """Tests for building 2D comparison matrix."""

    def test_builds_matrix(self) -> None:
        """Matrix is built with correct dimensions."""
        suite = make_suite(
            make_test_report("t[a-x]", model="model_a", prompt="prompt_x", outcome="passed"),
            make_test_report("t[a-y]", model="model_a", prompt="prompt_y", outcome="failed"),
            make_test_report("t[b-x]", model="model_b", prompt="prompt_x", outcome="passed"),
            make_test_report("t[b-y]", model="model_b", prompt="prompt_y", outcome="passed"),
        )

        aggregator = DimensionAggregator()
        dims = TestDimensions(
            mode=ReportMode.MATRIX,
            models=["model_a", "model_b"],
            prompts=["prompt_x", "prompt_y"],
        )

        matrix = aggregator.build_matrix(suite, dims)

        # 2 prompts = 2 rows
        assert len(matrix) == 2
        # 2 models = 2 columns per row
        assert len(matrix[0]) == 2

        # Check specific cell
        cell = matrix[0][0]  # prompt_x, model_a
        assert cell.model == "model_a"
        assert cell.prompt == "prompt_x"
        assert cell.passed is True


class TestMatrixCell:
    """Tests for MatrixCell dataclass."""

    def test_cell_with_test(self) -> None:
        """Cell with test shows correct outcome."""
        test = make_test_report("test", outcome="passed")
        cell = MatrixCell(model="m", prompt="p", test=test)

        assert cell.outcome == "passed"
        assert cell.passed is True

    def test_cell_without_test(self) -> None:
        """Cell without test shows as missing."""
        cell = MatrixCell(model="m", prompt="p", test=None)

        assert cell.outcome == "missing"
        assert cell.passed is False


class TestTestDimensions:
    """Tests for TestDimensions dataclass."""

    def test_is_comparison_simple(self) -> None:
        """SIMPLE mode is not a comparison."""
        dims = TestDimensions(mode=ReportMode.SIMPLE)
        assert dims.is_comparison is False

    def test_is_comparison_model(self) -> None:
        """MODEL_COMPARISON is a comparison."""
        dims = TestDimensions(mode=ReportMode.MODEL_COMPARISON, models=["a", "b"])
        assert dims.is_comparison is True

    def test_is_matrix(self) -> None:
        """MATRIX mode is detected."""
        dims = TestDimensions(mode=ReportMode.MATRIX, models=["a"], prompts=["x"])
        assert dims.is_matrix is True
        assert dims.is_comparison is True
