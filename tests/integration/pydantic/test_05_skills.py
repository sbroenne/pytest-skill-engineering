"""Level 05 — Skills: load domain knowledge and inject into eval context.

Tests skill loading, metadata validation, reference tools, and skill-enhanced
agent behavior. Skills add structured domain knowledge that the eval can
use via virtual tools (list_skill_references, read_skill_reference).

Permutation: Skill added to eval.

Run with: pytest tests/integration/pydantic/test_05_skills.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from pytest_skill_engineering import Eval, MCPServer, Provider, SkillError, Wait, load_skill

from ..conftest import DEFAULT_MODEL, DEFAULT_RPM, DEFAULT_TPM

pytestmark = [pytest.mark.integration, pytest.mark.skill]

# Skills live in the parent integration/skills/ directory
SKILLS_DIR = Path(__file__).parent.parent / "skills"


# =============================================================================
# Skill Loading & Validation (no LLM calls)
# =============================================================================


class TestSkillLoading:
    """Tests for load_skill() and skill validation."""

    def test_load_skill_with_references(self):
        """Load a skill that has a references/ directory."""
        skill = load_skill(SKILLS_DIR / "math-helper")

        assert skill.name == "math-helper"
        assert skill.description == "Mathematical calculation helper with formulas reference"
        assert skill.metadata.version == "1.0.0"
        assert skill.metadata.license == "MIT"
        assert "math" in skill.metadata.tags
        assert skill.has_references
        assert "formulas.md" in skill.references

    def test_load_skill_without_references(self):
        """Load a skill without references/ directory."""
        skill = load_skill(SKILLS_DIR / "simple-assistant")

        assert skill.name == "simple-assistant"
        assert skill.description == "A simple helpful assistant skill"
        assert not skill.has_references
        assert skill.references == {}

    def test_load_skill_from_skill_md_path(self):
        """Load skill by pointing directly to SKILL.md file."""
        skill = load_skill(SKILLS_DIR / "simple-assistant" / "SKILL.md")

        assert skill.name == "simple-assistant"

    def test_skill_content_contains_body(self):
        """Verify skill content contains the markdown body."""
        skill = load_skill(SKILLS_DIR / "math-helper")

        assert "Math Helper Skill" in skill.content
        assert "show your work step-by-step" in skill.content

    def test_skill_invalid_path_raises_error(self):
        """Non-existent path should raise SkillError."""
        with pytest.raises(SkillError, match="Invalid skill path"):
            load_skill(SKILLS_DIR / "nonexistent-skill")

    def test_metadata_tags_as_tuple(self):
        """Tags should be accessible as a tuple."""
        skill = load_skill(SKILLS_DIR / "math-helper")
        assert isinstance(skill.metadata.tags, tuple)
        assert "math" in skill.metadata.tags


# =============================================================================
# Skill + Agent Integration (real LLM calls)
# =============================================================================


class TestSkillWithAgent:
    """Integration tests for skills with actual LLM calls."""

    async def test_skill_prepends_to_system_prompt(self, eval_run):
        """Skill content should be prepended to eval's system prompt."""
        skill = load_skill(SKILLS_DIR / "simple-assistant")

        agent = Eval.from_instructions(
            "skill-prepend-test",
            "Be extremely brief.",
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            skill=skill,
            max_turns=5,
        )

        result = await eval_run(agent, "Greet me")

        assert result.success
        assert "hello" in result.final_response.lower()

    async def test_skill_with_references_provides_tools(self, eval_run):
        """Skills with references/ should inject virtual tools."""
        skill = load_skill(SKILLS_DIR / "math-helper")

        banking_server = MCPServer(
            command=[sys.executable, "-u", "-m", "pytest_skill_engineering.testing.banking_mcp"],
            wait=Wait.for_tools(["get_balance"]),
        )

        agent = Eval.from_instructions(
            "skill-references-test",
            (
                "You MUST use the available tools to look up formulas. "
                "Start by listing available references, then read the formulas file."
            ),
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            skill=skill,
            mcp_servers=[banking_server],
            max_turns=10,
        )

        result = await eval_run(agent, "What is the formula for the area of a circle?")

        assert result.success
        assert result.tool_was_called("list_skill_references") or result.tool_was_called(
            "read_skill_reference"
        )
        assert "π" in result.final_response or "pi" in result.final_response.lower()

    async def test_skill_references_list_tool_returns_files(self, eval_run):
        """The list_skill_references tool should return available filenames."""
        skill = load_skill(SKILLS_DIR / "math-helper")

        agent = Eval.from_instructions(
            "skill-list-refs-test",
            (
                "When asked to list references, use the list_skill_references tool. "
                "Report exactly what files are available."
            ),
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            skill=skill,
            max_turns=5,
        )

        result = await eval_run(agent, "List all available reference documents")

        assert result.success
        assert result.tool_was_called("list_skill_references")
        assert "formulas" in result.final_response.lower()

    async def test_skill_read_reference_returns_content(self, eval_run):
        """The read_skill_reference tool should return file content."""
        skill = load_skill(SKILLS_DIR / "math-helper")

        agent = Eval.from_instructions(
            "skill-read-ref-test",
            (
                "When asked about Pythagorean theorem, use read_skill_reference to read "
                "formulas.md and then quote the exact formula from the reference."
            ),
            provider=Provider(model=f"azure/{DEFAULT_MODEL}", rpm=DEFAULT_RPM, tpm=DEFAULT_TPM),
            skill=skill,
            max_turns=5,
        )

        result = await eval_run(
            agent, "What is the Pythagorean theorem? Quote the formula exactly."
        )

        assert result.success
        assert result.tool_was_called("read_skill_reference")
        assert "a²" in result.final_response or "a^2" in result.final_response
