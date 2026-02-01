"""Smart dimension detection and aggregation for test results.

Automatically detects multi-model and multi-prompt test patterns from
pytest.mark.parametrize and groups results accordingly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest_aitest.reporting.collector import SuiteReport, TestReport


class ReportMode(Enum):
    """Detected report mode based on test dimensions."""

    SIMPLE = auto()  # Single tests, no parametrization
    MODEL_COMPARISON = auto()  # Same tests across multiple models
    PROMPT_COMPARISON = auto()  # Same model, multiple prompts
    MATRIX = auto()  # Multiple models AND prompts (2D grid)


@dataclass
class AdaptiveFlags:
    """Flags controlling which sections to render in the report.

    Mirrors agent-benchmark: detect dimensions → set flags → template renders.
    """

    # Core visibility flags
    show_model_leaderboard: bool = False
    show_prompt_comparison: bool = False
    show_matrix: bool = False
    show_test_overview: bool = True

    # Counts for display
    model_count: int = 0
    prompt_count: int = 0
    test_count: int = 0

    # Single model/prompt mode (no comparison needed)
    single_model_mode: bool = True
    single_model_name: str | None = None
    single_prompt_mode: bool = True
    single_prompt_name: str | None = None

    @classmethod
    def from_dimensions(cls, dimensions: "TestDimensions", test_count: int) -> "AdaptiveFlags":
        """Create flags from detected dimensions."""
        model_count = len(dimensions.models)
        prompt_count = len(dimensions.prompts)

        return cls(
            show_model_leaderboard=model_count > 1,
            show_prompt_comparison=prompt_count > 1,
            show_matrix=model_count > 1 and prompt_count > 1,
            show_test_overview=test_count > 1,
            model_count=model_count,
            prompt_count=prompt_count,
            test_count=test_count,
            single_model_mode=model_count <= 1,
            single_model_name=dimensions.models[0] if model_count == 1 else None,
            single_prompt_mode=prompt_count <= 1,
            single_prompt_name=dimensions.prompts[0] if prompt_count == 1 else None,
        )


@dataclass
class TestDimensions:
    """Detected dimensions from parametrized tests.

    Parses test node IDs like "test_weather[gpt-4o-PROMPT_V1]" to extract:
    - Base test name (test_weather)
    - Model variations (gpt-4o, claude-3-haiku)
    - Prompt variations (PROMPT_V1, PROMPT_V2)
    """

    mode: ReportMode
    models: list[str] = field(default_factory=list)
    prompts: list[str] = field(default_factory=list)
    base_tests: list[str] = field(default_factory=list)

    @property
    def is_comparison(self) -> bool:
        """True if this involves model or prompt comparison."""
        return self.mode != ReportMode.SIMPLE

    @property
    def is_matrix(self) -> bool:
        """True if this is a 2D model x prompt matrix."""
        return self.mode == ReportMode.MATRIX


@dataclass
class GroupedResult:
    """Results grouped by a dimension (model or prompt)."""

    dimension_value: str
    tests: list[TestReport]
    passed: int = 0
    failed: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    avg_duration_ms: float = 0.0
    rank: int = 0  # 1 = best, 2 = second, etc.

    def __post_init__(self) -> None:
        self.passed = sum(1 for t in self.tests if t.outcome == "passed")
        self.failed = sum(1 for t in self.tests if t.outcome == "failed")
        self.total_tokens = sum(
            (
                t.agent_result.token_usage.get("prompt", 0)
                + t.agent_result.token_usage.get("completion", 0)
            )
            for t in self.tests
            if t.agent_result is not None
        )
        self.total_cost = sum(
            t.agent_result.cost_usd for t in self.tests if t.agent_result is not None
        )
        durations = [t.duration_ms for t in self.tests]
        self.avg_duration_ms = sum(durations) / len(durations) if durations else 0.0

    @property
    def pass_rate(self) -> float:
        total = self.passed + self.failed
        return (self.passed / total * 100) if total > 0 else 0.0

    @property
    def efficiency(self) -> float:
        """Tokens per passed test (lower is better). Returns inf if no passed tests."""
        if self.passed == 0:
            return float("inf")
        return self.total_tokens / self.passed

    @property
    def medal(self) -> str:
        """Return medal emoji based on rank."""
        if self.rank == 1:
            return "🥇"
        elif self.rank == 2:
            return "🥈"
        elif self.rank == 3:
            return "🥉"
        return ""


@dataclass
class MatrixCell:
    """A single cell in a model x prompt matrix."""

    model: str
    prompt: str
    test: TestReport | None = None

    @property
    def outcome(self) -> str:
        return self.test.outcome if self.test else "missing"

    @property
    def passed(self) -> bool:
        return self.test is not None and self.test.outcome == "passed"


class DimensionAggregator:
    """Analyzes test results and groups by detected dimensions.

    Uses pytest node ID parsing to detect parametrization patterns:
    - test_foo[gpt-4o] -> model dimension
    - test_foo[PROMPT_V1] -> prompt dimension
    - test_foo[gpt-4o-PROMPT_V1] -> matrix (both dimensions)

    Example:
        aggregator = DimensionAggregator()
        dimensions = aggregator.detect_dimensions(suite_report)

        if dimensions.mode == ReportMode.MODEL_COMPARISON:
            groups = aggregator.group_by_model(suite_report)
        elif dimensions.mode == ReportMode.MATRIX:
            matrix = aggregator.build_matrix(suite_report, dimensions)
    """

    # Common model patterns (litellm format) - non-greedy to avoid matching prompt names
    MODEL_PATTERNS = [
        r"openai/gpt-\d[\w.-]*",  # openai/gpt-4o, openai/gpt-4o-mini
        r"anthropic/claude-\d[\w.-]*",  # anthropic/claude-3-opus
        r"azure/[\w.-]+",
        r"gpt-\d[\w.]*(?:-mini|-turbo)?",  # gpt-4o, gpt-4.1, gpt-5-mini
        r"gpt-3\.5-turbo",  # gpt-3.5-turbo
        r"claude-\d(?:\.\d)?(?:-\w+)?",  # claude-3, claude-3.5-sonnet
        r"gemini-\d[\w.-]*",  # gemini-1.5-pro
        r"mistral-[\w-]+",
        r"llama\d[\w.-]*",  # llama3, llama3-8b
        r"o\d(?:-mini|-preview)?",  # o1, o1-mini
    ]

    # Pattern for prompt names (typically SCREAMING_CASE or PascalCase)
    PROMPT_PATTERNS = [
        r"PROMPT_\w+",
        r"[A-Z][a-z]+Prompt",
        r"prompt_v\d+",
    ]

    def detect_dimensions(self, report: SuiteReport) -> TestDimensions:
        """Detect test dimensions from parametrized test names.

        Parses test node IDs to find model and prompt variations.
        """
        models: set[str] = set()
        prompts: set[str] = set()
        base_tests: set[str] = set()

        for test in report.tests:
            # Extract base test name and parameters
            base_name, params = self._parse_node_id(test.name)
            base_tests.add(base_name)

            # Check for model and prompt in parameter string
            if params:
                params_str = params[0]
                model = self._extract_model_from_params(params_str)
                if model:
                    models.add(model)
                prompt = self._extract_prompt_from_params(params_str)
                if prompt:
                    prompts.add(prompt)

            # Also check metadata
            if test.metadata.get("model"):
                models.add(test.metadata["model"])
            if test.metadata.get("prompt"):
                prompts.add(test.metadata["prompt"])

        # Determine mode
        if models and prompts:
            mode = ReportMode.MATRIX
        elif models:
            mode = ReportMode.MODEL_COMPARISON
        elif prompts:
            mode = ReportMode.PROMPT_COMPARISON
        else:
            mode = ReportMode.SIMPLE

        return TestDimensions(
            mode=mode,
            models=sorted(models),
            prompts=sorted(prompts),
            base_tests=sorted(base_tests),
        )

    def _parse_node_id(self, node_id: str) -> tuple[str, list[str]]:
        """Parse pytest node ID into base name and parameters.

        Example:
            "test_weather[gpt-4o-PROMPT_V1]" -> ("test_weather", ["gpt-4o-PROMPT_V1"])

        Note: Returns the full parameter string as a single item. Model/prompt
        extraction is done by matching patterns against this string.
        """
        match = re.match(r"([^\[]+)(?:\[([^\]]+)\])?", node_id)
        if not match:
            return node_id, []

        base_name = match.group(1)
        params_str = match.group(2)

        if not params_str:
            return base_name, []

        # Return the full param string - pattern matching handles extraction
        return base_name, [params_str]

    def _extract_model_from_params(self, params_str: str) -> str | None:
        """Extract model name from parameter string using pattern matching."""
        model_pattern = re.compile("|".join(f"({p})" for p in self.MODEL_PATTERNS), re.IGNORECASE)
        match = model_pattern.search(params_str)
        if match:
            return match.group(0)
        return None

    def _extract_prompt_from_params(self, params_str: str) -> str | None:
        """Extract prompt name from parameter string using pattern matching."""
        prompt_pattern = re.compile("|".join(f"({p})" for p in self.PROMPT_PATTERNS))
        match = prompt_pattern.search(params_str)
        if match:
            return match.group(0)
        return None

    def group_by_model(self, report: SuiteReport) -> list[GroupedResult]:
        """Group test results by model.

        Returns results sorted by pass rate (descending) with ranks assigned.
        """
        groups: dict[str, list[TestReport]] = {}

        for test in report.tests:
            model = test.metadata.get("model")
            if not model:
                # Try to extract from node ID
                _, params = self._parse_node_id(test.name)
                if params:
                    model = self._extract_model_from_params(params[0])

            if model:
                groups.setdefault(model, []).append(test)

        results = [
            GroupedResult(dimension_value=model, tests=tests) for model, tests in groups.items()
        ]
        results = sorted(results, key=lambda g: (-g.pass_rate, g.dimension_value))

        # Assign ranks
        for i, result in enumerate(results):
            result.rank = i + 1

        return results

    def group_by_prompt(self, report: SuiteReport) -> list[GroupedResult]:
        """Group test results by prompt.

        Returns results sorted by pass rate (descending) with ranks assigned.
        """
        groups: dict[str, list[TestReport]] = {}

        for test in report.tests:
            prompt = test.metadata.get("prompt")
            if not prompt:
                # Try to extract from node ID
                _, params = self._parse_node_id(test.name)
                if params:
                    prompt = self._extract_prompt_from_params(params[0])

            if prompt:
                groups.setdefault(prompt, []).append(test)

        results = [
            GroupedResult(dimension_value=prompt, tests=tests) for prompt, tests in groups.items()
        ]
        results = sorted(results, key=lambda g: (-g.pass_rate, g.dimension_value))

        # Assign ranks
        for i, result in enumerate(results):
            result.rank = i + 1

        return results

    def build_matrix(
        self, report: SuiteReport, dimensions: TestDimensions
    ) -> list[list[MatrixCell]]:
        """Build 2D matrix of model x prompt results.

        Returns a list of rows (prompts), each containing cells (models).
        """
        # Create lookup: (model, prompt) -> test
        lookup: dict[tuple[str, str], TestReport] = {}
        for test in report.tests:
            model = test.metadata.get("model", "")
            prompt = test.metadata.get("prompt", "")

            # Try to extract from node ID if not in metadata
            if not model or not prompt:
                _, params = self._parse_node_id(test.name)
                if params:
                    params_str = params[0]
                    if not model:
                        model = self._extract_model_from_params(params_str) or ""
                    if not prompt:
                        prompt = self._extract_prompt_from_params(params_str) or ""

            if model and prompt:
                lookup[(model, prompt)] = test

        # Build matrix
        matrix = []
        for prompt in dimensions.prompts:
            row = []
            for model in dimensions.models:
                test = lookup.get((model, prompt))
                row.append(MatrixCell(model=model, prompt=prompt, test=test))
            matrix.append(row)

        return matrix

    def get_model_rankings(self, report: SuiteReport) -> list[tuple[str, float, int, float]]:
        """Get models ranked by pass rate.

        Returns list of (model, pass_rate, total_tests, avg_cost).
        """
        groups = self.group_by_model(report)
        return [
            (
                g.dimension_value,
                g.pass_rate,
                len(g.tests),
                g.total_cost / len(g.tests) if g.tests else 0,
            )
            for g in groups
        ]

    def get_prompt_rankings(self, report: SuiteReport) -> list[tuple[str, float, int]]:
        """Get prompts ranked by pass rate.

        Returns list of (prompt, pass_rate, total_tests).
        """
        groups = self.group_by_prompt(report)
        return [(g.dimension_value, g.pass_rate, len(g.tests)) for g in groups]

    def get_adaptive_flags(self, report: SuiteReport) -> AdaptiveFlags:
        """Create adaptive flags for template rendering."""
        dimensions = self.detect_dimensions(report)
        return AdaptiveFlags.from_dimensions(dimensions, len(report.tests))
