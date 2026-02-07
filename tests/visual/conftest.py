"""Configuration for visual/Playwright tests.

Disable pytest-asyncio auto mode for these sync tests.
The aitest plugin has an async autouse fixture that conflicts with sync Playwright.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pytest_aitest.cli import load_suite_report
from pytest_aitest.reporting.generator import generate_html

# Mark all tests in this directory as not needing aitest fixtures
pytestmark = pytest.mark.usefixtures()

# Stable fixtures for reproducible testing
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "reports"
GENERATED_HTML_DIR = Path(__file__).parent.parent.parent / "docs" / "reports"


def pytest_configure(config: pytest.Config) -> None:
    """Disable asyncio for visual tests."""
    # Set asyncio_mode to strict (manual) instead of auto for this dir
    config._inicache["asyncio_mode"] = "strict"


# Override the aitest autouse fixture to be a no-op sync fixture for visual tests
@pytest.fixture(autouse=True)
def _aitest_auto_cleanup() -> None:
    """No-op override of the async cleanup fixture for sync Playwright tests."""
    pass


def _ensure_html_report(fixture_name: str) -> Path:
    """Generate HTML from JSON fixture if missing."""
    html_path = GENERATED_HTML_DIR / f"{fixture_name}.html"
    if not html_path.exists():
        json_path = FIXTURES_DIR / f"{fixture_name}.json"
        report, insights = load_suite_report(json_path)
        generate_html(report, html_path, insights=insights)
    return html_path


@pytest.fixture(scope="module")
def single_agent_report() -> Path:
    """HTML report from 01_single_agent.json (1 agent, no comparison UI)."""
    return _ensure_html_report("01_single_agent")


@pytest.fixture(scope="module")
def multi_agent_report() -> Path:
    """HTML report from 02_multi_agent.json (2 agents, leaderboard, no selector)."""
    return _ensure_html_report("02_multi_agent")


@pytest.fixture(scope="module")
def session_report() -> Path:
    """HTML report from 03_multi_agent_sessions.json (2 agents, sessions)."""
    return _ensure_html_report("03_multi_agent_sessions")


@pytest.fixture(scope="module")
def agent_selector_report() -> Path:
    """HTML report from 04_agent_selector.json (3 agents, agent selector)."""
    return _ensure_html_report("04_agent_selector")
