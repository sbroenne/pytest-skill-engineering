"""Level 06 — Sessions: context retention via single-prompt embedding.

**SDK limitation:** CopilotEval has NO message history reuse — each
``copilot_eval()`` call starts a fresh Copilot session with a string
prompt.  True multi-turn sessions (as in the Pydantic harness with
``@pytest.mark.session``) are not possible.

**Approach:** We test "context in a single prompt" — embed prior context
directly in the prompt and verify the agent references it.  This proves
the agent can follow contextual cues, even though the context doesn't
come from a prior conversation turn.

Mirrors pydantic/test_06_sessions.py — same level, different harness.

Run with: pytest tests/integration/copilot/test_06_sessions.py -v
"""

from __future__ import annotations

import pytest

from pytest_skill_engineering.copilot.eval import CopilotEval

pytestmark = [pytest.mark.copilot]


class TestContextRetention:
    """Verify the agent uses embedded context to inform its output."""

    async def test_context_referenced_in_code(self, copilot_eval, tmp_path):
        """Agent embeds contextual project name when given prior context."""
        agent = CopilotEval(
            name="context-code",
            instructions=(
                "You are a Python developer. When the user gives you context "
                "about their project, incorporate that context into the code "
                "you produce (e.g. variable names, module docstrings, comments)."
            ),
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(
            agent,
            "Context: I'm building a FastAPI app called 'SkyTracker' that "
            "monitors airline flight statuses.\n\n"
            "Create a config.py module with an APP_NAME constant and a "
            "Settings class that holds host, port, and debug fields.",
        )
        assert result.success, f"Agent failed: {result.error}"
        assert (tmp_path / "config.py").exists(), "config.py was not created"

        content = (tmp_path / "config.py").read_text()
        assert "SkyTracker" in content or "skytracker" in content.lower(), (
            "Agent did not reference the project name 'SkyTracker' from context.\n"
            f"Generated content:\n{content}"
        )

    async def test_followup_uses_embedded_context(self, copilot_eval, tmp_path):
        """Agent uses 'earlier discussion' context embedded in the prompt."""
        agent = CopilotEval(
            name="context-followup",
            instructions="You are a helpful Python developer.",
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(
            agent,
            "Earlier we agreed on these conventions:\n"
            "- All functions use Google-style docstrings\n"
            "- Module names are snake_case\n"
            "- Every module has __version__ = '0.1.0'\n\n"
            "Now create string_utils.py with functions: reverse(s), "
            "capitalize_words(s), truncate(s, max_len).",
        )
        assert result.success, f"Agent failed: {result.error}"
        assert (tmp_path / "string_utils.py").exists(), "string_utils.py was not created"

        content = (tmp_path / "string_utils.py").read_text()
        assert "__version__" in content, (
            "Agent ignored embedded convention requiring __version__.\n"
            f"Generated content:\n{content}"
        )
        has_docstring = '"""' in content or "'''" in content
        assert has_docstring, (
            "Agent ignored embedded convention requiring docstrings.\n"
            f"Generated content:\n{content}"
        )

    async def test_domain_context_steers_implementation(self, copilot_eval, tmp_path):
        """Domain context (healthcare) steers naming and structure choices."""
        agent = CopilotEval(
            name="context-domain",
            instructions="You are a Python developer. Follow any domain context the user provides.",
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(
            agent,
            "Context: This is a healthcare system. We use FHIR terminology. "
            "A 'Patient' has a given_name, family_name, and birth_date. "
            "A 'Practitioner' has a given_name, family_name, and specialty.\n\n"
            "Create models.py with dataclasses for Patient and Practitioner "
            "using exactly the field names above.",
        )
        assert result.success, f"Agent failed: {result.error}"
        assert (tmp_path / "models.py").exists(), "models.py was not created"

        content = (tmp_path / "models.py").read_text()
        for field_name in ("given_name", "family_name", "birth_date", "specialty"):
            assert field_name in content, (
                f"Domain field '{field_name}' missing from generated code.\n"
                f"Generated content:\n{content}"
            )


class TestSinglePromptMultiStep:
    """Multi-step tasks in a single prompt — no session state needed."""

    async def test_create_then_refactor(self, copilot_eval, tmp_path):
        """Single prompt asks to create, then refactor — both steps complete."""
        agent = CopilotEval(
            name="multi-step",
            instructions="You are a Python developer. Complete all steps in order.",
            working_directory=str(tmp_path),
        )
        result = await copilot_eval(
            agent,
            "Step 1: Create math_ops.py with functions add(a, b) and multiply(a, b). "
            "Keep them simple — no docstrings, no type hints.\n"
            "Step 2: Then refactor math_ops.py to add type hints (int params, int return) "
            "and a one-line docstring to each function.\n"
            "Complete both steps.",
        )
        assert result.success, f"Agent failed: {result.error}"
        assert (tmp_path / "math_ops.py").exists(), "math_ops.py was not created"

        content = (tmp_path / "math_ops.py").read_text()
        assert "->" in content or ": int" in content, (
            "Step 2 (add type hints) was not completed.\n"
            f"Generated content:\n{content}"
        )
        has_docstring = '"""' in content or "'''" in content
        assert has_docstring, (
            "Step 2 (add docstrings) was not completed.\n"
            f"Generated content:\n{content}"
        )
