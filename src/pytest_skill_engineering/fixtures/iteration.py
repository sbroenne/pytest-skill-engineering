"""Iteration fixture for --aitest-iterations support."""

from __future__ import annotations

import pytest


@pytest.fixture
def _aitest_iteration(request: pytest.FixtureRequest) -> int:
    """Iteration index (1-based) injected by ``--aitest-iterations``.

    Not intended for direct use by test authors.  The
    ``pytest_generate_tests`` hook in :mod:`pytest_skill_engineering.plugin`
    parametrizes this fixture automatically when the CLI option is set.
    """
    return getattr(request, "param", 1)
