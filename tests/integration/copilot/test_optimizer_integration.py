"""Integration tests for optimize_instruction().

These tests require:
- GitHub Copilot credentials (for copilot_run to produce a real result)
- At least one accessible judge model provider (Azure/OpenAI/Copilot)

Fails fast when no configured provider can access a model.
"""

from __future__ import annotations

import pytest

from pytest_skill_engineering import InstructionSuggestion, optimize_instruction
from pytest_skill_engineering.copilot.agent import CopilotAgent


@pytest.mark.copilot
class TestOptimizeInstructionIntegration:
    """Integration tests for optimize_instruction() with real provider calls."""

    async def test_returns_valid_suggestion(self, copilot_run, tmp_path, integration_judge_model):
        """optimize_instruction returns an InstructionSuggestion with non-empty fields."""
        agent = CopilotAgent(
            name="minimal-coder",
            instructions="Write Python code.",
            working_directory=str(tmp_path),
        )
        result = await copilot_run(
            agent,
            "Create calc.py with add(a, b) and subtract(a, b).",
        )
        assert result.success

        suggestion = await optimize_instruction(
            agent.instructions or "",
            result,
            "Every function must have a Google-style docstring.",
            model=integration_judge_model,
        )

        assert isinstance(suggestion, InstructionSuggestion)
        assert suggestion.instruction.strip(), "Suggestion instruction must not be empty"
        assert suggestion.reasoning.strip(), "Suggestion reasoning must not be empty"
        assert suggestion.changes.strip(), "Suggestion changes must not be empty"
        assert len(suggestion.instruction) > 20, "Instruction too short to be useful"

    async def test_suggestion_str_is_human_readable(
        self, copilot_run, tmp_path, integration_judge_model
    ):
        """str(InstructionSuggestion) is readable and contains all fields."""
        agent = CopilotAgent(
            name="coder",
            instructions="Write Python code.",
            working_directory=str(tmp_path),
        )
        result = await copilot_run(agent, "Create utils.py with a helper function.")
        assert result.success

        suggestion = await optimize_instruction(
            agent.instructions or "",
            result,
            "Add type hints to all function parameters and return values.",
            model=integration_judge_model,
        )

        text = str(suggestion)
        assert suggestion.instruction in text
        assert suggestion.reasoning in text
        assert suggestion.changes in text

    async def test_suggestion_is_relevant_to_criterion(
        self, copilot_run, tmp_path, integration_judge_model
    ):
        """Optimizer returns a suggestion that addresses the given criterion."""
        agent = CopilotAgent(
            name="coder",
            instructions="Write Python code.",
            working_directory=str(tmp_path),
        )
        result = await copilot_run(
            agent,
            "Create math.py with add(a, b) and multiply(a, b).",
        )
        assert result.success

        criterion = "All functions must include Google-style docstrings."
        suggestion = await optimize_instruction(
            agent.instructions or "",
            result,
            criterion,
            model=integration_judge_model,
        )

        # The suggestion instruction should mention docstrings somehow
        combined = (suggestion.instruction + " " + suggestion.reasoning).lower()
        assert any(word in combined for word in ["docstring", "doc", "documentation", "google"]), (
            f"Suggestion doesn't address 'docstring' criterion.\n"
            f"Instruction: {suggestion.instruction}\n"
            f"Reasoning: {suggestion.reasoning}"
        )

    async def test_full_optimize_loop(self, copilot_run, tmp_path, integration_judge_model):
        """Full test→optimize→test loop: weak instruction fails, improved instruction passes.

        This is the hero use case: verify that optimize_instruction() produces
        an instruction that actually fixes a failing criterion.

        Round 1: Run with a deliberately weak instruction (no docstring mandate).
                 The agent writes code but skips docstrings.
        Optimize: Call optimize_instruction() with the failing criterion.
                  Receive a suggested instruction that mandates docstrings.
        Round 2: Run again with the improved instruction.
                 The agent now includes docstrings — criterion passes.
        """
        CRITERION = "Every function must include a Google-style docstring."
        TASK = "Create calculator.py with add(a, b) and subtract(a, b) functions."

        # --- Round 1: weak instruction, expect no docstrings ---
        weak_agent = CopilotAgent(
            name="weak-coder",
            instructions="Write minimal Python code. No comments or documentation needed.",
            working_directory=str(tmp_path / "round1"),
        )
        (tmp_path / "round1").mkdir()
        result1 = await copilot_run(weak_agent, TASK)
        assert result1.success, "Round 1 Copilot run failed"

        code1 = result1.file("calculator.py") or ""
        has_docstrings_round1 = '"""' in code1 or "'''" in code1

        # --- Optimize ---
        suggestion = await optimize_instruction(
            weak_agent.instructions or "",
            result1,
            CRITERION,
            model=integration_judge_model,
        )
        assert suggestion.instruction.strip(), "Optimizer returned empty instruction"
        print(f"\n💡 Suggested instruction:\n{suggestion}")  # visible in -s output

        # --- Round 2: improved instruction ---
        improved_agent = CopilotAgent(
            name="improved-coder",
            instructions=suggestion.instruction,
            working_directory=str(tmp_path / "round2"),
        )
        (tmp_path / "round2").mkdir()
        result2 = await copilot_run(improved_agent, TASK)
        assert result2.success, "Round 2 Copilot run failed"

        code2 = result2.file("calculator.py") or ""
        has_docstrings_round2 = '"""' in code2 or "'''" in code2

        assert has_docstrings_round2, (
            f"Round 2 code still has no docstrings after optimization.\n"
            f"Suggested instruction: {suggestion.instruction}\n"
            f"Round 2 code:\n{code2}"
        )
        print(
            f"\n✅ Loop complete. "
            f"Docstrings round 1: {has_docstrings_round1}, round 2: {has_docstrings_round2}"
        )
