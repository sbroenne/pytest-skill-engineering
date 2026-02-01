"""Reporting module for pytest-aitest.

This module provides backwards-compatible imports from the new package structure.
New code should import from pytest_aitest.reporting directly.
"""

# Re-export from reporting package for backwards compatibility
from pytest_aitest.reporting import (
    ReportCollector,
    ReportGenerator,
    SuiteReport,
    TestReport,
    generate_mermaid_sequence,
)

__all__ = [
    "ReportCollector",
    "ReportGenerator",
    "SuiteReport",
    "TestReport",
    "generate_mermaid_sequence",
]
