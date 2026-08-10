"""Level 04 — Model × system prompt matrix comparison.

Runs the same task across every configured model and two distinct system
prompts. The report exposes both dimensions for side-by-side comparison.

Run with: pytest tests/integration/copilot/test_04_matrix.py -v
"""

from __future__ import annotations

import pytest

from pytest_skill_engineering.copilot.eval import CopilotEval

from .conftest import MODELS

pytestmark = [pytest.mark.copilot, pytest.mark.matrix, pytest.mark.slow]

SYSTEM_PROMPTS = {
    "typed": (
        "Write fully typed Python. Every function must have parameter and return "
        "type annotations plus a concise docstring."
    ),
    "minimal": (
        "Write minimal Python. Do not add type annotations, docstrings, comments, "
        "tests, or supporting files."
    ),
}


class TestModelSystemPromptMatrix:
    """Compare each model under typed and minimal system prompts."""

    @pytest.mark.parametrize("model", MODELS)
    @pytest.mark.parametrize("system_prompt_name", SYSTEM_PROMPTS)
    async def test_greeting_module(
        self,
        copilot_eval,
        tmp_path,
        model: str,
        system_prompt_name: str,
    ) -> None:
        """Each matrix cell creates the requested module in its required style."""
        agent = CopilotEval(
            name=f"{model}-{system_prompt_name}",
            model=model,
            instructions=SYSTEM_PROMPTS[system_prompt_name],
            working_directory=str(tmp_path),
        )

        result = await copilot_eval(
            agent,
            "Create greeting.py with greet(name), returning 'Hello, {name}!'.",
        )

        assert result.success, result.error
        content = (tmp_path / "greeting.py").read_text(encoding="utf-8")
        assert "def greet" in content
        if system_prompt_name == "typed":
            assert "-> str" in content
            assert '"""' in content or "'''" in content
        else:
            assert "->" not in content
            assert '"""' not in content and "'''" not in content
