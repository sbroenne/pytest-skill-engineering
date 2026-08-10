"""Project-wide pytest helpers for this repository's own test suite."""

from __future__ import annotations

import pytest
from _pytest.config import Config
from _pytest.config.argparsing import Parser


def pytest_addoption(parser: Parser) -> None:
    """Add an opt-in flag for slow tests in this repository."""
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="Run tests marked slow/expensive for this repository.",
    )


def pytest_collection_modifyitems(config: Config, items: list[pytest.Item]) -> None:
    """Skip slow tests unless the caller explicitly opts in."""
    if config.getoption("--run-slow"):
        return

    skip_slow = pytest.mark.skip(reason="slow test skipped by default; pass --run-slow to execute")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)
