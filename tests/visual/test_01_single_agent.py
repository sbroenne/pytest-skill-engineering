"""Visual tests for single agent report (01_single_agent.json).

Tests:
- Header with suite name and status badge
- AI Analysis section renders and toggles
- Test cards expand/collapse
- Mermaid diagrams render
- Filter buttons work
- NO leaderboard (single agent)
- NO agent selector (single agent)
- NO comparison columns (single column only)
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page


class TestSingleAgentHeader:
    """Test header section for single agent report."""

    def test_header_exists(self, page: Page, single_agent_report: Path):
        """Header section should exist."""
        page.goto(f"file://{single_agent_report}")
        page.wait_for_load_state("networkidle")

        header = page.locator("header")
        assert header.count() > 0, "Header section not found"

    def test_suite_title_from_docstring(self, page: Page, single_agent_report: Path):
        """Header should show suite docstring as title."""
        page.goto(f"file://{single_agent_report}")
        page.wait_for_load_state("networkidle")

        # Check for h1 with the suite docstring
        title = page.locator("h1").first
        assert title.count() > 0, "Title not found"
        title_text = (title.text_content() or "").strip()
        # Should show a meaningful title, not generic "pytest-aitest"
        assert len(title_text) > 10, f"Title too short: {title_text}"
        assert "pytest-aitest" not in title_text.lower(), (
            f"Expected suite docstring in title, not generic name: {title_text}"
        )

    def test_cost_breakdown_present(self, page: Page, single_agent_report: Path):
        """Header should show test cost, AI cost, and total cost."""
        page.goto(f"file://{single_agent_report}")
        page.wait_for_load_state("networkidle")

        header = page.locator("header")
        header_text = (header.text_content() or "").strip()

        # Should contain cost indicators (🧪 test cost, 🤖 AI cost, 💰 total)
        assert "🧪" in header_text or "$" in header_text, "Test cost not found in header"
        assert "🤖" in header_text, "AI analysis cost not found in header"
        assert "💰" in header_text, "Total cost not found in header"

    def test_status_badge_exists(self, page: Page, single_agent_report: Path):
        """Status badge should show pass/fail."""
        page.goto(f"file://{single_agent_report}")
        page.wait_for_load_state("networkidle")

        # Status badge uses status-passed or status-failed class
        badge = page.locator(".status-passed, .status-failed").first
        assert badge.count() > 0, "Status badge not found"
        assert badge.is_visible(), "Status badge is not visible"

        badge_text = (badge.text_content() or "").strip()
        if "status-passed" in (badge.get_attribute("class") or ""):
            assert "All Passed" in badge_text, "Status badge text missing 'All Passed'"
        else:
            assert "Failed" in badge_text, "Status badge text missing 'Failed'"


class TestSingleAgentAIAnalysis:
    """Test AI analysis section."""

    def test_ai_analysis_exists(self, page: Page, single_agent_report: Path):
        """AI analysis section should exist."""
        page.goto(f"file://{single_agent_report}")
        page.wait_for_load_state("networkidle")

        # AI insights section uses .ai-insights class
        analysis = page.locator(".ai-insights")
        assert analysis.count() > 0, "AI analysis section not found"


class TestSingleAgentTestGrid:
    """Test test grid functionality."""

    def test_test_rows_exist(self, page: Page, single_agent_report: Path):
        """Test rows should exist."""
        page.goto(f"file://{single_agent_report}")
        page.wait_for_load_state("networkidle")

        test_rows = page.locator(".test-row")
        assert test_rows.count() > 0, "No test rows found"

    def test_test_row_expands_on_click(self, page: Page, single_agent_report: Path):
        """Clicking test row should expand details via onclick handler."""
        page.goto(f"file://{single_agent_report}")
        page.wait_for_load_state("networkidle")

        # First verify the function exists
        func_exists = page.evaluate("typeof toggleTestDetail === 'function'")
        assert func_exists, "toggleTestDetail function not defined in JavaScript"

        # Click on test row header (has onclick="toggleTestDetail(this.parentElement)")
        header = page.locator(".test-row .px-5.py-3").first
        header.click()
        page.wait_for_timeout(300)

        # Detail should be visible (not hidden) - toggled by onclick handler
        visible_details = page.locator(".test-row:first-child .test-detail:not(.hidden)")
        assert visible_details.count() > 0, (
            "Test detail did not expand on click - onclick handler may not be working"
        )

    def test_filter_buttons_exist(self, page: Page, single_agent_report: Path):
        """Filter buttons should exist."""
        page.goto(f"file://{single_agent_report}")
        page.wait_for_load_state("networkidle")

        all_btn = page.locator('.filter-btn[data-filter="all"]')
        assert all_btn.count() == 1, "All filter button not found"


class TestSingleAgentMermaid:
    """Test mermaid diagram rendering."""

    def test_mermaid_divs_exist(self, page: Page, single_agent_report: Path):
        """Mermaid diagram containers should exist when test detail is expanded."""
        page.goto(f"file://{single_agent_report}")
        page.wait_for_load_state("networkidle")

        # Click to expand test detail
        header = page.locator(".test-row .px-5.py-3").first
        header.click()
        page.wait_for_timeout(500)

        # Mermaid diagrams should be present
        mermaid = page.locator(".test-row:first-child .test-detail .mermaid")
        assert mermaid.count() > 0, "No mermaid diagrams found in expanded detail"


class TestSingleAgentNoComparisonUI:
    """Test that comparison UI is NOT shown for single agent."""

    def test_no_leaderboard(self, page: Page, single_agent_report: Path):
        """Leaderboard should NOT exist for single agent."""
        page.goto(f"file://{single_agent_report}")
        page.wait_for_load_state("networkidle")

        leaderboard = page.locator(".leaderboard-table")
        assert leaderboard.count() == 0, "Leaderboard should not exist for single agent"

    def test_no_agent_selector(self, page: Page, single_agent_report: Path):
        """Agent selector should NOT exist for single agent."""
        page.goto(f"file://{single_agent_report}")
        page.wait_for_load_state("networkidle")

        selector = page.locator("#agent-selector")
        assert selector.count() == 0, "Agent selector should not exist for single agent"

    def test_single_column_only(self, page: Page, single_agent_report: Path):
        """Should have only one result column (no comparison)."""
        page.goto(f"file://{single_agent_report}")
        page.wait_for_load_state("networkidle")

        # Click to expand test detail
        header = page.locator(".test-row .px-5.py-3").first
        header.click()
        page.wait_for_timeout(300)

        # Should have exactly 1 comparison column (or result column)
        columns = page.locator(".test-row:first-child .test-detail .comparison-column")
        assert columns.count() == 1, f"Expected 1 column for single agent, got {columns.count()}"
