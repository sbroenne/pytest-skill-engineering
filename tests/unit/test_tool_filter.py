"""Tests for _apply_tool_filter in pydantic_adapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from pytest_skill_engineering.execution.pydantic_adapter import _apply_tool_filter


class TestApplyToolFilter:
    """Tests for _apply_tool_filter function."""

    def test_returns_filtered_toolsets(self) -> None:
        """Each toolset is wrapped in a FilteredToolset."""
        from pydantic_ai.toolsets import FilteredToolset

        ts1 = MagicMock()
        ts2 = MagicMock()
        result = _apply_tool_filter([ts1, ts2], ["tool_a", "tool_b"])

        assert len(result) == 2
        assert all(isinstance(r, FilteredToolset) for r in result)

    def test_empty_allowed_tools_wraps_all(self) -> None:
        """Empty allowed_tools still wraps toolsets (filters out everything)."""
        from pydantic_ai.toolsets import FilteredToolset

        ts = MagicMock()
        result = _apply_tool_filter([ts], [])

        assert len(result) == 1
        assert isinstance(result[0], FilteredToolset)

    @pytest.mark.asyncio
    async def test_filter_func_allows_matching_tools(self) -> None:
        """Filter function allows tools in the allowed list."""
        from pydantic_ai.tools import ToolDefinition
        from pydantic_ai.toolsets.abstract import ToolsetTool

        # Create mock tools
        tool_a_def = ToolDefinition(name="tool_a", description="Tool A")
        tool_b_def = ToolDefinition(name="tool_b", description="Tool B")
        tool_c_def = ToolDefinition(name="tool_c", description="Tool C")

        tool_a = MagicMock(spec=ToolsetTool)
        tool_a.tool_def = tool_a_def
        tool_b = MagicMock(spec=ToolsetTool)
        tool_b.tool_def = tool_b_def
        tool_c = MagicMock(spec=ToolsetTool)
        tool_c.tool_def = tool_c_def

        # Create mock toolset that returns all 3 tools
        mock_toolset = AsyncMock()
        mock_toolset.get_tools = AsyncMock(
            return_value={"tool_a": tool_a, "tool_b": tool_b, "tool_c": tool_c}
        )
        mock_toolset.__aenter__ = AsyncMock(return_value=mock_toolset)
        mock_toolset.__aexit__ = AsyncMock(return_value=None)

        # Apply filter allowing only tool_a and tool_c
        filtered = _apply_tool_filter([mock_toolset], ["tool_a", "tool_c"])
        assert len(filtered) == 1

        # Get tools through the filter
        ctx = MagicMock()
        tools = await filtered[0].get_tools(ctx)

        assert set(tools.keys()) == {"tool_a", "tool_c"}
        assert "tool_b" not in tools
