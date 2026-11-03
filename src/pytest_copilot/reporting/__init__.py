"""Native execution evidence and ordinary pytest outcomes."""

from __future__ import annotations

from pytest_copilot.reporting.collector import SuiteReport, TestReport, build_suite_report
from pytest_copilot.reporting.generator import generate_json, load_suite_report

__all__ = [
    # Core exports
    "SuiteReport",
    "TestReport",
    "build_suite_report",
    # Generation
    "generate_json",
    "load_suite_report",
]
