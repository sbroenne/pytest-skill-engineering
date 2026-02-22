"""htpy components for report generation.

This module provides type-safe HTML generation using htpy.
All report partials are implemented as functions returning htpy elements.
"""

from __future__ import annotations

from .agent_leaderboard import agent_leaderboard
from .agent_selector import agent_selector
from .overlay import overlay
from .report import full_report
from .test_comparison import test_comparison
from .test_grid import test_grid

__all__ = [
    "agent_leaderboard",
    "agent_selector",
    "full_report",
    "overlay",
    "test_comparison",
    "test_grid",
]
