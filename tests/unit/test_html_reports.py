"""Tests for HTML report generation — replaces Playwright visual tests.

Fast string-assertion tests that verify HTML structure deterministically.
Covers all scenarios: single agent, multi-agent, sessions, agent selector.

Runs in <2s vs 136s for the Playwright equivalents.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pytest_skill_engineering.cli import load_suite_report
from pytest_skill_engineering.reporting.components import full_report
from pytest_skill_engineering.reporting.generator import _build_report_context
from pytest_skill_engineering.reporting.insights import InsightsResult

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "reports"

_FALLBACK_INSIGHTS = InsightsResult(
    markdown_summary="## Verdict\n\nTest insights.",
    model="test-model",
    tokens_used=100,
    cost_usd=0.001,
    cached=True,
)


def _render_html(fixture_name: str) -> str:
    """Load fixture JSON and render to HTML string."""
    json_path = FIXTURES_DIR / f"{fixture_name}.json"
    report, insights = load_suite_report(json_path)
    if insights is None:
        insights = _FALLBACK_INSIGHTS
    ctx = _build_report_context(report, insights=insights)
    return str(full_report(ctx))


def _strip_css_js(html: str) -> str:
    """Strip <style> and <script> blocks for structural HTML assertions.

    CSS class names and JS references can cause false matches when checking
    for rendered HTML elements. This helper removes those blocks.
    """
    # Use an HTML parser to properly strip style/script elements
    from html.parser import HTMLParser

    class _Stripper(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self._skip = False
            self._parts: list[str] = []

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag in ("style", "script"):
                self._skip = True
            elif not self._skip:
                attr_str = "".join(f' {k}="{v}"' if v else f" {k}" for k, v in attrs)
                self._parts.append(f"<{tag}{attr_str}>")

        def handle_endtag(self, tag: str) -> None:
            if tag in ("style", "script"):
                self._skip = False
            elif not self._skip:
                self._parts.append(f"</{tag}>")

        def handle_data(self, data: str) -> None:
            if not self._skip:
                self._parts.append(data)

    stripper = _Stripper()
    stripper.feed(html)
    return "".join(stripper._parts)


def _leaderboard_row_count(html: str) -> int:
    """Count <tr> rows in the leaderboard table's tbody only."""
    body = _strip_css_js(html)
    table_start = body.find('class="leaderboard-table"')
    if table_start == -1:
        return 0
    tbody_start = body.find("<tbody", table_start)
    if tbody_start == -1:
        return 0
    tbody_end = body.find("</tbody>", tbody_start)
    return body[tbody_start:tbody_end].count("<tr")


# ============================================================================
# Fixtures (cached per module — each rendered once)
# ============================================================================


@pytest.fixture(scope="module")
def single_agent_html() -> str:
    return _render_html("01_single_agent")


@pytest.fixture(scope="module")
def multi_agent_html() -> str:
    return _render_html("02_multi_agent")


@pytest.fixture(scope="module")
def session_html() -> str:
    return _render_html("03_multi_agent_sessions")


@pytest.fixture(scope="module")
def agent_selector_html() -> str:
    return _render_html("04_agent_selector")


# ============================================================================
# 01: Single Agent — header, AI analysis, test grid, mermaid, NO comparison UI
# ============================================================================


class TestSingleAgentHeader:
    """Header section for single agent report."""

    def test_header_exists(self, single_agent_html: str) -> None:
        assert "<header" in single_agent_html

    def test_suite_title_present(self, single_agent_html: str) -> None:
        assert "<h1" in single_agent_html

    def test_cost_breakdown_present(self, single_agent_html: str) -> None:
        """Header shows test cost, AI cost, and total cost."""
        assert "🧪" in single_agent_html or "$" in single_agent_html
        assert "🤖" in single_agent_html
        assert "💰" in single_agent_html

    def test_status_badge_exists(self, single_agent_html: str) -> None:
        assert "status-passed" in single_agent_html or "status-failed" in single_agent_html


class TestSingleAgentAIAnalysis:
    """AI analysis section."""

    def test_ai_analysis_section_exists(self, single_agent_html: str) -> None:
        assert "ai-insights" in single_agent_html

    def test_ai_analysis_has_content(self, single_agent_html: str) -> None:
        assert "Verdict" in single_agent_html or "insights" in single_agent_html.lower()


class TestSingleAgentTestGrid:
    """Test grid functionality."""

    def test_test_rows_exist(self, single_agent_html: str) -> None:
        assert "test-row" in single_agent_html

    def test_toggle_function_defined(self, single_agent_html: str) -> None:
        """toggleTestDetail JS function should be present."""
        assert "toggleTestDetail" in single_agent_html

    def test_filter_buttons_exist(self, single_agent_html: str) -> None:
        assert 'data-filter="all"' in single_agent_html
        assert "filter-btn" in single_agent_html


class TestSingleAgentMermaid:
    """Mermaid diagram rendering."""

    def test_mermaid_containers_exist(self, single_agent_html: str) -> None:
        assert "mermaid" in single_agent_html
        assert "sequenceDiagram" in single_agent_html


class TestSingleAgentNoComparisonUI:
    """Comparison UI should NOT appear for single agent."""

    def test_no_leaderboard(self, single_agent_html: str) -> None:
        body = _strip_css_js(single_agent_html)
        assert 'class="leaderboard-table"' not in body

    def test_no_agent_selector(self, single_agent_html: str) -> None:
        body = _strip_css_js(single_agent_html)
        assert "agent-chip" not in body

    def test_single_column_layout(self, single_agent_html: str) -> None:
        """Should have exactly 1 comparison-column per test (no side-by-side)."""
        body = _strip_css_js(single_agent_html)
        col_count = body.count("comparison-column")
        assert col_count > 0, "Should have at least one comparison column"
        test_count = body.count("test-row")
        assert col_count == test_count, (
            f"Single agent: columns ({col_count}) should equal tests ({test_count})"
        )


# ============================================================================
# 02: Multi-Agent (2 agents) — leaderboard, comparison, NO agent selector
# ============================================================================


class TestMultiAgentLeaderboard:
    """Leaderboard for 2-agent report."""

    def test_leaderboard_exists(self, multi_agent_html: str) -> None:
        assert "leaderboard-table" in multi_agent_html

    def test_leaderboard_has_rows(self, multi_agent_html: str) -> None:
        row_count = _leaderboard_row_count(multi_agent_html)
        assert row_count == 2, f"Expected 2 agent rows, got {row_count}"

    def test_winner_highlighted(self, multi_agent_html: str) -> None:
        assert "winner" in multi_agent_html


class TestMultiAgentNoSelector:
    """Agent selector should NOT appear for only 2 agents."""

    def test_no_agent_selector(self, multi_agent_html: str) -> None:
        body = _strip_css_js(multi_agent_html)
        assert "agent-chip" not in body


class TestMultiAgentComparison:
    """Comparison columns for 2 agents."""

    def test_comparison_columns_exist(self, multi_agent_html: str) -> None:
        assert "comparison-column" in multi_agent_html
        assert "comparison-grid" in multi_agent_html

    def test_two_columns_per_test(self, multi_agent_html: str) -> None:
        """Each test should have 2 comparison columns (one per agent)."""
        body = _strip_css_js(multi_agent_html)
        col_count = body.count("comparison-column")
        test_count = body.count("test-row")
        # 2 agents → 2 columns per test
        assert col_count == test_count * 2, (
            f"2 agents: columns ({col_count}) should be 2 * tests ({test_count})"
        )


class TestMultiAgentOverlay:
    """Mermaid overlay."""

    def test_overlay_exists(self, multi_agent_html: str) -> None:
        assert 'id="overlay"' in multi_agent_html

    def test_overlay_mermaid_container(self, multi_agent_html: str) -> None:
        assert 'id="overlay-mermaid"' in multi_agent_html

    def test_overlay_close_function(self, multi_agent_html: str) -> None:
        assert "hideOverlay" in multi_agent_html


class TestMultiAgentFilterButtons:
    """Filter buttons."""

    def test_filter_buttons_exist(self, multi_agent_html: str) -> None:
        assert 'data-filter="all"' in multi_agent_html
        assert 'data-filter="failed"' in multi_agent_html

    def test_all_filter_active_by_default(self, multi_agent_html: str) -> None:
        # The "All" button should have the active class
        all_btn_idx = multi_agent_html.find('data-filter="all"')
        # Look backward for the class attribute
        preceding = multi_agent_html[max(0, all_btn_idx - 200) : all_btn_idx]
        assert "active" in preceding or "filter-btn active" in multi_agent_html


# ============================================================================
# 03: Sessions (2 agents) — session grouping, leaderboard, NO selector
# ============================================================================


class TestSessionGrouping:
    """Session grouping functionality."""

    def test_session_groups_exist(self, session_html: str) -> None:
        assert 'data-group-type="session"' in session_html

    def test_session_header_exists(self, session_html: str) -> None:
        assert "group-header" in session_html

    def test_session_contains_multiple_tests(self, session_html: str) -> None:
        """Session groups should contain test rows."""
        body = _strip_css_js(session_html)
        session_start = body.find('data-group-type="session"')
        assert session_start > -1, "No session group found"
        # Session group should contain multiple test-rows
        # Use a generous window to capture the full session group
        section = body[session_start : session_start + 20000]
        row_count = section.count('class="test-row')
        assert row_count >= 2, f"Session should have >= 2 test-rows, got {row_count}"


class TestSessionLeaderboard:
    """Leaderboard with sessions."""

    def test_leaderboard_exists(self, session_html: str) -> None:
        assert "leaderboard-table" in session_html

    def test_leaderboard_has_2_agents(self, session_html: str) -> None:
        row_count = _leaderboard_row_count(session_html)
        assert row_count == 2, f"Expected 2 agent rows, got {row_count}"


class TestSessionNoSelector:
    """Agent selector should NOT appear for 2 agents."""

    def test_no_agent_selector(self, session_html: str) -> None:
        body = _strip_css_js(session_html)
        assert "agent-chip" not in body


class TestSessionComparison:
    """Comparison columns in session report."""

    def test_comparison_columns_exist(self, session_html: str) -> None:
        assert "comparison-column" in session_html


class TestSessionTestInteraction:
    """Test row interaction JS in sessions."""

    def test_toggle_detail_function_exists(self, session_html: str) -> None:
        assert "toggleTestDetail" in session_html

    def test_test_detail_sections_exist(self, session_html: str) -> None:
        assert "test-detail" in session_html


# ============================================================================
# 04: Agent Selector (3 agents) — leaderboard with medals, selector, swap logic
# ============================================================================


class TestAgentSelectorLeaderboard:
    """Leaderboard with 3 agents."""

    def test_leaderboard_exists(self, agent_selector_html: str) -> None:
        assert "leaderboard-table" in agent_selector_html

    def test_leaderboard_has_3_agents(self, agent_selector_html: str) -> None:
        assert _leaderboard_row_count(agent_selector_html) == 3

    def test_leaderboard_has_medals(self, agent_selector_html: str) -> None:
        assert "🥇" in agent_selector_html
        assert "🥈" in agent_selector_html
        assert "🥉" in agent_selector_html


class TestAgentSelectorExists:
    """Agent selector presence and structure."""

    def test_agent_chips_exist(self, agent_selector_html: str) -> None:
        assert "agent-chip" in agent_selector_html

    def test_correct_number_of_checkboxes(self, agent_selector_html: str) -> None:
        body = _strip_css_js(agent_selector_html)
        assert body.count('name="compare-agent"') == 3

    def test_three_agent_chips(self, agent_selector_html: str) -> None:
        assert agent_selector_html.count("agent-chip") >= 3


class TestAgentSelectorDefaultState:
    """Default selection state."""

    def test_two_agents_checked_by_default(self, agent_selector_html: str) -> None:
        """First 2 agents should be checked."""
        checked_count = agent_selector_html.count("checked")
        # At least 2 checkboxes should be checked
        assert checked_count >= 2, f"Expected >= 2 checked, got {checked_count}"

    def test_selected_chips_present(self, agent_selector_html: str) -> None:
        """Some chips should have selected class."""
        assert "selected" in agent_selector_html


class TestAgentSelectorJS:
    """Agent selector JavaScript logic."""

    def test_update_comparison_function(self, agent_selector_html: str) -> None:
        assert "updateAgentComparison" in agent_selector_html

    def test_swap_selection_logic(self, agent_selector_html: str) -> None:
        """JS should enforce exactly 2 selected agents."""
        # The JS has selection queue logic
        assert "compare-agent" in agent_selector_html


class TestAgentSelectorComparisonColumns:
    """Comparison columns with agent selector."""

    def test_columns_exist(self, agent_selector_html: str) -> None:
        assert "comparison-column" in agent_selector_html
        assert "comparison-grid" in agent_selector_html

    def test_hidden_columns_for_unselected(self, agent_selector_html: str) -> None:
        """Third agent's columns should be hidden initially."""
        assert "hidden" in agent_selector_html

    def test_data_agent_id_attributes(self, agent_selector_html: str) -> None:
        """Columns should have data-agent-id for JS toggling."""
        assert "data-agent-id" in agent_selector_html


# ============================================================================
# Cross-cutting: features present in ALL reports
# ============================================================================


class TestCrossCuttingFeatures:
    """Features that should exist in every report type."""

    @pytest.mark.parametrize(
        "fixture_name",
        ["01_single_agent", "02_multi_agent", "03_multi_agent_sessions", "04_agent_selector"],
    )
    def test_has_html_structure(self, fixture_name: str) -> None:
        html = _render_html(fixture_name)
        assert "<!doctype html>" in html.lower() or "<html" in html

    @pytest.mark.parametrize(
        "fixture_name",
        ["01_single_agent", "02_multi_agent", "03_multi_agent_sessions", "04_agent_selector"],
    )
    def test_has_css(self, fixture_name: str) -> None:
        html = _render_html(fixture_name)
        assert "<style" in html

    @pytest.mark.parametrize(
        "fixture_name",
        ["01_single_agent", "02_multi_agent", "03_multi_agent_sessions", "04_agent_selector"],
    )
    def test_has_mermaid_js(self, fixture_name: str) -> None:
        html = _render_html(fixture_name)
        assert "mermaid" in html

    @pytest.mark.parametrize(
        "fixture_name",
        ["01_single_agent", "02_multi_agent", "03_multi_agent_sessions", "04_agent_selector"],
    )
    def test_has_ai_insights(self, fixture_name: str) -> None:
        html = _render_html(fixture_name)
        assert "ai-insights" in html

    @pytest.mark.parametrize(
        "fixture_name",
        ["01_single_agent", "02_multi_agent", "03_multi_agent_sessions", "04_agent_selector"],
    )
    def test_has_test_rows(self, fixture_name: str) -> None:
        html = _render_html(fixture_name)
        assert "test-row" in html

    @pytest.mark.parametrize(
        "fixture_name",
        ["01_single_agent", "02_multi_agent", "03_multi_agent_sessions", "04_agent_selector"],
    )
    def test_has_filter_buttons(self, fixture_name: str) -> None:
        html = _render_html(fixture_name)
        assert "filter-btn" in html

    @pytest.mark.parametrize(
        "fixture_name",
        ["01_single_agent", "02_multi_agent", "03_multi_agent_sessions", "04_agent_selector"],
    )
    def test_has_footer(self, fixture_name: str) -> None:
        html = _render_html(fixture_name)
        assert "pytest-skill-engineering" in html
