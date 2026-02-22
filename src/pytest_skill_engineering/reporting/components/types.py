"""Type definitions for htpy components.

These dataclasses define the exact data shape each component expects,
providing compile-time type checking instead of runtime template errors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AgentData:
    """Data for a single agent in the leaderboard."""

    id: str
    name: str
    passed: int
    failed: int
    total: int
    pass_rate: float
    cost: float
    tokens: int
    duration_s: float
    is_winner: bool = False
    disqualified: bool = False


@dataclass(slots=True)
class ToolCallData:
    """Data for a tool call in test results."""

    name: str
    success: bool
    error: str | None = None
    args: dict[str, Any] | None = None
    result: str | None = None
    image_content: bytes | None = None
    image_media_type: str | None = None


@dataclass(slots=True)
class AssertionData:
    """Data for an assertion result."""

    type: str
    passed: bool
    message: str
    details: Any | None = None


@dataclass(slots=True)
class ScoreDimensionData:
    """Data for a single scored dimension."""

    name: str
    score: int
    max_score: int
    weight: float = 1.0


@dataclass(slots=True)
class ScoreData:
    """Aggregated LLM score data for a test result."""

    dimensions: list[ScoreDimensionData]
    total: int
    max_total: int
    weighted_score: float
    reasoning: str


@dataclass(slots=True)
class IterationData:
    """Stats for a single iteration of a repeated test."""

    iteration: int
    outcome: str
    passed: bool
    duration_s: float
    tokens: int
    cost: float
    error: str | None = None


@dataclass(slots=True)
class TestResultData:
    """Data for a single test result for one agent.

    When ``iterations`` is non-empty the top-level fields contain
    **aggregated** values (mean duration, total cost, overall pass rate)
    while individual run data lives in ``iterations``.
    """

    outcome: str
    passed: bool
    duration_s: float
    tokens: int
    cost: float
    tool_calls: list[ToolCallData]
    tool_count: int
    turns: int
    mermaid: str | None = None
    final_response: str | None = None
    error: str | None = None
    assertions: list[AssertionData] = field(default_factory=list)
    scores: list[ScoreData] = field(default_factory=list)
    iterations: list[IterationData] = field(default_factory=list)
    iteration_pass_rate: float | None = None


@dataclass(slots=True)
class TestData:
    """Data for a single test across all agents."""

    id: str
    display_name: str
    results_by_agent: dict[str, TestResultData]
    has_difference: bool
    has_failed: bool


@dataclass(slots=True)
class AgentStats:
    """Per-agent stats within a test group."""

    passed: int
    failed: int


@dataclass(slots=True)
class TestGroupData:
    """Data for a group of tests (session or standalone)."""

    type: str  # "session" or "standalone"
    name: str
    tests: list[TestData]
    agent_stats: dict[str, AgentStats]


@dataclass(slots=True)
class ReportMetadata:
    """Top-level report metadata."""

    name: str
    timestamp: str
    passed: int
    failed: int
    total: int
    duration_ms: float
    total_cost_usd: float
    suite_docstring: str | None = None
    analysis_cost_usd: float = 0.0
    test_files: list[str] = field(default_factory=list)
    token_min: int = 0
    token_max: int = 0
    models_without_pricing: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AIInsightsData:
    """AI analysis insights."""

    markdown_summary: str


@dataclass(slots=True)
class ReportContext:
    """Complete context for rendering the full report."""

    report: ReportMetadata
    agents: list[AgentData]
    agents_by_id: dict[str, AgentData]
    all_agent_ids: list[str]
    selected_agent_ids: list[str]
    test_groups: list[TestGroupData]
    total_tests: int
    insights: AIInsightsData
