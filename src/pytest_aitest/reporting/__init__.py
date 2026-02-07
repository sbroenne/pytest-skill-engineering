"""Reporting module - smart result aggregation and report generation."""

from pytest_aitest.reporting.collector import SuiteReport, TestReport, build_suite_report
from pytest_aitest.reporting.generator import (
    generate_html,
    generate_json,
    generate_mermaid_sequence,
)
from pytest_aitest.reporting.insights import (
    InsightsGenerationError,
    InsightsResult,
    generate_insights,
)

__all__ = [
    # Core exports
    "SuiteReport",
    "TestReport",
    "build_suite_report",
    # Generation
    "generate_html",
    "generate_json",
    "generate_mermaid_sequence",
    # Insights generation
    "generate_insights",
    "InsightsGenerationError",
    "InsightsResult",
]
