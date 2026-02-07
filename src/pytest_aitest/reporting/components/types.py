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
    skill: str | None = None
    system_prompt_name: str | None = None
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


@dataclass(slots=True)
class AssertionData:
    """Data for an assertion result."""

    type: str
    passed: bool
    message: str
    details: Any | None = None


@dataclass(slots=True)
class TestResultData:
    """Data for a single test result for one agent."""

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
    analysis_cost_usd: float | None = None
    test_files: list[str] = field(default_factory=list)
    token_min: int = 0
    token_max: int = 0


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
    insights: AIInsightsData | None = None
