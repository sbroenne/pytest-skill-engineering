"""Model × Instructions matrix tests.

Cross-product of models and instruction styles to find the best combination.
"""

from __future__ import annotations

import pytest

from pytest_skill_engineering.copilot.agent import CopilotAgent

from .conftest import MODELS

INSTRUCTIONS = {
    "minimal": "Create files as requested. No explanations.",
    "detailed": (
        "You are a senior software engineer. Write clean, well-documented code. "
        "Include type hints, docstrings, and handle edge cases."
    ),
}


@pytest.mark.copilot
class TestMatrix:
    """Model × Instructions grid."""

    @pytest.mark.parametrize("model", MODELS)
    @pytest.mark.parametrize("style,instructions", list(INSTRUCTIONS.items()))
    async def test_create_utility(self, copilot_run, tmp_path, model, style, instructions):
        """Every combination should produce a working utility module."""
        agent = CopilotAgent(
            name=f"{model}/{style}",
            model=model,
            instructions=instructions,
            working_directory=str(tmp_path),
        )
        result = await copilot_run(
            agent,
            "Create a string_utils.py with functions: reverse, capitalize_words, count_vowels.",
        )
        assert result.success, f"{model}/{style} failed: {result.error}"
        path = tmp_path / "string_utils.py"
        assert path.exists()
        content = path.read_text()
        for fn in ("reverse", "capitalize_words", "count_vowels"):
            assert fn in content, f"{model}/{style}: function '{fn}' not found in string_utils.py"
