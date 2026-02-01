"""Reporting module - smart result aggregation and report generation."""

from pytest_aitest.reporting.aggregator import (
    AdaptiveFlags,
    DimensionAggregator,
    GroupedResult,
    MatrixCell,
    ReportMode,
    TestDimensions,
)
from pytest_aitest.reporting.collector import ReportCollector, SuiteReport, TestReport
from pytest_aitest.reporting.generator import (
    ReportGenerator,
    generate_mermaid_sequence,
    get_provider,
)

__all__ = [
    "AdaptiveFlags",
    "DimensionAggregator",
    "generate_mermaid_sequence",
    "get_provider",
    "GroupedResult",
    "MatrixCell",
    "ReportCollector",
    "ReportGenerator",
    "ReportMode",
    "SuiteReport",
    "TestDimensions",
    "TestReport",
]
