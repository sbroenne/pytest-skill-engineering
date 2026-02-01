"""Prompt arena tests - compare multiple system prompts.

Use @pytest.mark.parametrize with prompts loaded from YAML files.
The report auto-detects this and shows a prompt comparison table.

This is how you test prompt-based agents like those in Azure AI Foundry.

Run with: pytest tests/integration/test_prompt_arena.py -v --aitest-html=report.html
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pytest_aitest import Agent, Provider, load_prompts

pytestmark = [pytest.mark.integration, pytest.mark.arena]

# Load prompts from YAML files
PROMPTS_DIR = Path(__file__).parent / "prompts"
PROMPTS = load_prompts(PROMPTS_DIR)


class TestPromptArena:
    """Compare different system prompts for the same tasks.

    The report will show which prompt leads to:
    - Higher pass rates
    - Fewer tool calls (efficiency)
    - Better responses
    """

    @pytest.mark.parametrize("prompt", PROMPTS, ids=lambda p: p.name)
    @pytest.mark.asyncio
    async def test_weather_query(self, aitest_run, weather_server, prompt):
        """Same query, different prompts - which responds best?"""
        agent = Agent(
            provider=Provider(model="azure/gpt-5-mini"),
            mcp_servers=[weather_server],
            system_prompt=prompt.system_prompt,
            max_turns=5,
        )

        result = await aitest_run(agent, "What's the weather in Paris?")

        assert result.success
        assert result.tool_was_called("get_weather")

    @pytest.mark.parametrize("prompt", PROMPTS, ids=lambda p: p.name)
    @pytest.mark.asyncio
    async def test_multi_step_task(self, aitest_run, weather_server, prompt):
        """Multi-step task - prompts may differ in efficiency."""
        agent = Agent(
            provider=Provider(model="azure/gpt-5-mini"),
            mcp_servers=[weather_server],
            system_prompt=prompt.system_prompt,
            max_turns=8,
        )

        result = await aitest_run(
            agent,
            "Compare the weather in Tokyo and Sydney, and tell me which is better for a beach day",
        )

        assert result.success
        # Should have gathered weather data
        tool_calls = result.tool_call_count("get_weather") + result.tool_call_count(
            "compare_weather"
        )
        assert tool_calls >= 1
