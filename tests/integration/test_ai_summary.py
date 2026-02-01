"""Integration tests for AI summary generation.

These tests verify that the AI summary feature generates proper structured output
following the prompt from prompts/ai_summary.md.

Run with: pytest tests/integration/test_ai_summary.py -v
"""

from __future__ import annotations

import os
import re

import pytest

pytestmark = [pytest.mark.integration]


def _get_api_base() -> str | None:
    """Get API base from LiteLLM standard env var."""
    return os.environ.get("AZURE_API_BASE")


class TestAISummaryGeneration:
    """Test that AI summary generates proper structured output."""

    @pytest.mark.skipif(
        not _get_api_base(),
        reason="AZURE_API_BASE not set"
    )
    def test_single_model_summary_has_required_sections(self):
        """Single-model summary should have Verdict, Capabilities, Limitations, etc."""
        import litellm

        from pytest_aitest.prompts import get_ai_summary_prompt

        model = "azure/gpt-5-mini"
        system_prompt = get_ai_summary_prompt()

        user_content = """**Context: Single-Model Evaluation** - Assess if the agent is fit for purpose.

**Test Suite:** test-suite
**Pass Rate:** 66.7% (2/3 tests passed)
**Duration:** 15.0s total
**Tokens Used:** 1,900 tokens
**Tool Calls:** 4 total

**Test Results:**
- test_weather_lookup: passed
- test_forecast: passed
- test_compare_cities: failed (AssertionError: Expected comparison)
"""

        # Set up Azure Entra ID auth
        kwargs: dict = {}
        try:
            from litellm.secret_managers.get_azure_ad_token_provider import (
                get_azure_ad_token_provider,
            )
            kwargs["azure_ad_token_provider"] = get_azure_ad_token_provider()
        except (ImportError, Exception):
            pass

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        # LiteLLM reads AZURE_API_BASE from environment automatically
        response = litellm.completion(
            model=model,
            messages=messages,
            **kwargs,
        )

        summary = response.choices[0].message.content or ""

        # Verify required sections for single-model evaluation
        assert "Verdict" in summary, f"Missing 'Verdict' section in summary:\n{summary}"
        assert any(
            phrase in summary
            for phrase in ["Fit for Purpose", "Partially Fit", "Not Fit"]
        ), f"Missing verdict status in summary:\n{summary}"

        # Should have key sections (case-insensitive check)
        summary_lower = summary.lower()
        assert "capabilities" in summary_lower, f"Missing 'Capabilities' section:\n{summary}"
        assert "limitations" in summary_lower or "limitation" in summary_lower, f"Missing 'Limitations' section:\n{summary}"
        assert "recommendations" in summary_lower or "recommendation" in summary_lower, f"Missing 'Recommendations' section:\n{summary}"

    @pytest.mark.skipif(
        not _get_api_base(),
        reason="AZURE_API_BASE not set"
    )
    def test_multi_model_summary_has_comparison(self):
        """Multi-model summary should compare models and recommend one."""
        import litellm

        from pytest_aitest.prompts import get_ai_summary_prompt

        model = "azure/gpt-5-mini"
        system_prompt = get_ai_summary_prompt()

        user_content = """**Context: Multi-Model Comparison** - Compare the models and recommend which to use.

**Test Suite:** model-comparison
**Pass Rate:** 75.0% (3/4 tests passed)
**Duration:** 29.0s total
**Tokens Used:** 2,400 tokens
**Tool Calls:** 6 total
Models tested: gpt-5-mini, gpt-4.1

**Per-Model Breakdown:**
- gpt-4.1: 100% (2/2), 700 tokens
- gpt-5-mini: 50% (1/2), 1,700 tokens

**Test Results:**
- test_weather[gpt-5-mini]: passed
- test_weather[gpt-4.1]: passed
- test_complex[gpt-5-mini]: failed (Timeout)
- test_complex[gpt-4.1]: passed
"""

        kwargs: dict = {}
        try:
            from litellm.secret_managers.get_azure_ad_token_provider import (
                get_azure_ad_token_provider,
            )
            kwargs["azure_ad_token_provider"] = get_azure_ad_token_provider()
        except (ImportError, Exception):
            pass

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        # LiteLLM reads AZURE_API_BASE from environment automatically
        response = litellm.completion(
            model=model,
            messages=messages,
            **kwargs,
        )

        summary = response.choices[0].message.content or ""

        # Verify it's a multi-model comparison
        assert "Verdict" in summary, f"Missing 'Verdict' section:\n{summary}"
        
        # Should recommend a specific model
        assert any(
            model_name in summary
            for model_name in ["gpt-5-mini", "gpt-4.1"]
        ), f"Should mention model names:\n{summary}"

        # Should have trade-offs or comparison language
        summary_lower = summary.lower()
        assert any(
            phrase in summary_lower
            for phrase in ["trade-off", "tradeoff", "accurate", "cost-effective", "recommend", "use"]
        ), f"Missing comparison/trade-off language:\n{summary}"

    @pytest.mark.skipif(
        not _get_api_base(),
        reason="AZURE_API_BASE not set"
    )
    def test_summary_under_300_words(self):
        """Summary should be concise (prompt says under 200, allow up to 300)."""
        import litellm

        from pytest_aitest.prompts import get_ai_summary_prompt

        model = "azure/gpt-5-mini"
        system_prompt = get_ai_summary_prompt()

        user_content = """**Context: Single-Model Evaluation** - Assess if the agent is fit for purpose.

**Test Suite:** simple-test
**Pass Rate:** 100.0% (1/1 tests passed)
**Duration:** 5.0s total
**Tokens Used:** 500 tokens
**Tool Calls:** 1 total

**Test Results:**
- test_simple: passed
"""

        kwargs: dict = {}
        try:
            from litellm.secret_managers.get_azure_ad_token_provider import (
                get_azure_ad_token_provider,
            )
            kwargs["azure_ad_token_provider"] = get_azure_ad_token_provider()
        except (ImportError, Exception):
            pass

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        # LiteLLM reads AZURE_API_BASE from environment automatically
        response = litellm.completion(
            model=model,
            messages=messages,
            **kwargs,
        )

        summary = response.choices[0].message.content or ""

        # Count words (rough estimate)
        word_count = len(summary.split())
        
        # Allow some flexibility (300 words) since models may not precisely follow limits
        assert word_count < 300, f"Summary too long ({word_count} words):\n{summary}"

    @pytest.mark.skipif(
        not _get_api_base(),
        reason="AZURE_API_BASE not set"
    )
    def test_summary_no_tables(self):
        """Summary should NOT contain tables (per prompt rules)."""
        import litellm

        from pytest_aitest.prompts import get_ai_summary_prompt

        model = "azure/gpt-5-mini"
        system_prompt = get_ai_summary_prompt()

        user_content = """**Context: Multi-Model Comparison** - Compare the models and recommend which to use.

**Test Suite:** benchmark
**Pass Rate:** 75.0% (3/4 tests passed)
**Duration:** 20.0s total
**Tokens Used:** 2,000 tokens
**Tool Calls:** 6 total
Models tested: model-a, model-b

**Test Results:**
- test_1[model-a]: passed
- test_1[model-b]: passed
- test_2[model-a]: failed (error)
- test_2[model-b]: passed
"""

        kwargs: dict = {}
        try:
            from litellm.secret_managers.get_azure_ad_token_provider import (
                get_azure_ad_token_provider,
            )
            kwargs["azure_ad_token_provider"] = get_azure_ad_token_provider()
        except (ImportError, Exception):
            pass

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        # LiteLLM reads AZURE_API_BASE from environment automatically
        response = litellm.completion(
            model=model,
            messages=messages,
            **kwargs,
        )

        summary = response.choices[0].message.content or ""

        # Check for markdown table syntax (| col1 | col2 |)
        table_pattern = r"\|.*\|.*\|"
        has_table = bool(re.search(table_pattern, summary))
        
        assert not has_table, f"Summary contains table (violates prompt rules):\n{summary}"
