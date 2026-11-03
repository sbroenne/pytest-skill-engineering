"""Execution-evidence reporting options for the pytest plugin."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from _pytest.config.argparsing import OptionGroup


def add_aitest_options(group: OptionGroup) -> None:
    """Register execution evidence, pass-rate thresholds, and repeated runs."""
    group.addoption(
        "--aitest-json",
        metavar="PATH",
        default=None,
        help="Save structured execution evidence and pytest outcomes as JSON",
    )
    group.addoption(
        "--aitest-min-pass-rate",
        metavar="N",
        type=int,
        default=None,
        help="Fail the session when the observed pytest pass rate is below N percent (0-100)",
    )
    group.addoption(
        "--aitest-iterations",
        metavar="N",
        type=int,
        default=1,
        help="Run each test N times in independently created pytest fixtures",
    )
