"""Level 07 — Clarification detection: catch agents that ask instead of acting.

CopilotEval does NOT have engine-level ClarificationDetection like the
Pydantic harness.  Instead, we detect clarification patterns by inspecting
``result.final_response`` — either with simple substring checks or with
the ``llm_assert`` fixture for semantic evaluation.

Mirrors pydantic/test_07_clarification.py — same level, different harness.

Run with: pytest tests/integration/copilot/test_07_clarification.py -v
"""

from __future__ import annotations

import pytest

from pytest_skill_engineering.copilot.eval import CopilotEval

pytestmark = [pytest.mark.copilot]

CLARIFICATION_PHRASES = [
    "would you like",
    "shall i",
    "do you want me to",
    "should i",
    "let me know if",
    "would you prefer",
    "do you have a preference",
]


def _has_clarification(response: str) -> bool:
    """Check whether a response contains common clarification phrases."""
    lower = response.lower()
    return any(phrase in lower for phrase in CLARIFICATION_PHRASES)


class TestClarificationDetection:
    """Clear requests should produce action, not questions."""

    async def test_no_clarification_on_clear_request(self, copilot_eval, tmp_path):
        """A fully-specified request should not trigger clarification."""
        agent = CopilotEval(
            name="no-clarify",
            instructions=(
                "Create files as requested. Never ask for permission or clarification — just do it."
            ),
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(
            agent,
            "Create hello.py with print('hello world')",
        )
        assert result.success, f"Agent failed: {result.error}"
        assert (tmp_path / "hello.py").exists(), "hello.py was not created"

        response = result.final_response or ""
        assert not _has_clarification(response), (
            "Agent asked for clarification instead of acting on a clear request.\n"
            f"Response: {response}"
        )

    async def test_no_clarification_on_multi_step_clear_request(self, copilot_eval, tmp_path):
        """A multi-step but fully-specified request should not trigger clarification."""
        agent = CopilotEval(
            name="no-clarify-multi",
            instructions=(
                "Complete all requested steps without asking for confirmation. Act immediately."
            ),
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(
            agent,
            "Create two files:\n"
            "1. utils.py with a function greet(name) that returns f'Hello, {name}!'\n"
            "2. main.py that imports greet from utils and calls greet('World')",
        )
        assert result.success, f"Agent failed: {result.error}"

        response = result.final_response or ""
        assert not _has_clarification(response), (
            "Agent asked for clarification on a fully-specified multi-step request.\n"
            f"Response: {response}"
        )
        assert (tmp_path / "utils.py").exists(), "utils.py was not created"
        assert (tmp_path / "main.py").exists(), "main.py was not created"

    async def test_ambiguous_request_may_clarify(self, copilot_eval, tmp_path, llm_assert):
        """An ambiguous request — agent may clarify or make a reasonable choice.

        This test verifies the agent either acts (creates a file) or asks a
        sensible clarifying question.  Both outcomes are acceptable; the test
        fails only if the agent does *nothing*.
        """
        agent = CopilotEval(
            name="ambiguous-task",
            instructions="You are a helpful developer.",
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(
            agent,
            "Create a web app.",
        )
        assert result.success, f"Agent failed: {result.error}"

        created_files = list(tmp_path.rglob("*.py"))
        response = result.final_response or ""

        acted = len(created_files) > 0
        asked = _has_clarification(response)

        assert acted or asked, (
            "Agent neither created files nor asked for clarification on an "
            "ambiguous request — it did nothing useful.\n"
            f"Response: {response}\n"
            f"Files created: {[f.name for f in created_files]}"
        )

    async def test_actionable_instructions_suppress_clarification(
        self, copilot_eval, tmp_path, llm_assert
    ):
        """Strong 'just do it' instructions should suppress clarification even on vague prompts."""
        agent = CopilotEval(
            name="action-oriented",
            instructions=(
                "You are a decisive developer. NEVER ask questions. "
                "If a request is ambiguous, make a reasonable choice and "
                "proceed. Always produce working code. Asking for clarification "
                "is forbidden."
            ),
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(
            agent,
            "Create a utility module.",
        )
        assert result.success, f"Agent failed: {result.error}"

        response = result.final_response or ""
        assert not _has_clarification(response), (
            "Agent asked for clarification despite instructions forbidding it.\n"
            f"Response: {response}"
        )
        created_files = list(tmp_path.rglob("*.py"))
        assert len(created_files) > 0, (
            f"Agent with 'never ask' instructions produced no files.\nResponse: {response}"
        )
