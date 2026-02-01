"""Integration tests for Agent Skills support.

These tests verify:
1. Skill loading from SKILL.md files
2. Skill content being prepended to system prompts
3. Virtual reference tools (list_skill_references, read_skill_reference)
"""

from pathlib import Path

import pytest

from pytest_aitest import SkillError, load_skill

# Path to test skills
SKILLS_DIR = Path(__file__).parent / "skills"


class TestSkillLoading:
    """Tests for Skill.from_path() and skill validation."""

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


class TestSkillMetadataValidation:
    """Tests for skill metadata validation per agentskills.io spec."""

    def test_name_validation_lowercase_required(self):
        """Name must be lowercase letters, numbers, and hyphens."""
        # Valid names are tested via actual skill loading
        skill = load_skill(SKILLS_DIR / "simple-assistant")
        assert skill.name == "simple-assistant"

    def test_metadata_tags_as_tuple(self):
        """Tags should be accessible as a tuple."""
        skill = load_skill(SKILLS_DIR / "math-helper")
        assert isinstance(skill.metadata.tags, tuple)
        assert "math" in skill.metadata.tags


@pytest.mark.integration
class TestSkillWithAgent:
    """Integration tests for skills with actual LLM calls."""

    async def test_skill_prepends_to_system_prompt(
        self, agent_factory, skill_factory, aitest_run
    ):
        """Skill content should be prepended to agent's system prompt."""
        skill = skill_factory(SKILLS_DIR / "simple-assistant")

        # The skill instructs to always include "Hello" in greetings
        agent = agent_factory(
            skill=skill,
            system_prompt="Be extremely brief.",  # This comes after skill content
        )

        result = await aitest_run(agent, "Greet me")

        assert result.success
        # Skill says to include "Hello" in greetings
        assert "hello" in result.final_response.lower()

    async def test_skill_with_references_provides_tools(
        self, agent_factory, skill_factory, aitest_run
    ):
        """Skills with references/ should inject virtual tools."""
        skill = skill_factory(SKILLS_DIR / "math-helper")

        agent = agent_factory(
            skill=skill,
            system_prompt=(
                "You MUST use the available tools to look up formulas. "
                "Start by listing available references, then read the formulas file."
            ),
        )

        result = await aitest_run(agent, "What is the formula for the area of a circle?")

        assert result.success
        # Should have called the skill reference tools
        assert result.tool_was_called("list_skill_references") or result.tool_was_called(
            "read_skill_reference"
        )
        # The answer should include the formula from references
        assert "π" in result.final_response or "pi" in result.final_response.lower()

    async def test_skill_references_list_tool_returns_files(
        self, agent_factory, skill_factory, aitest_run
    ):
        """The list_skill_references tool should return available filenames."""
        skill = skill_factory(SKILLS_DIR / "math-helper")

        agent = agent_factory(
            skill=skill,
            system_prompt=(
                "When asked to list references, use the list_skill_references tool. "
                "Report exactly what files are available."
            ),
        )

        result = await aitest_run(agent, "List all available reference documents")

        assert result.success
        assert result.tool_was_called("list_skill_references")
        # The response should mention formulas.md
        assert "formulas" in result.final_response.lower()

    async def test_skill_read_reference_returns_content(
        self, agent_factory, skill_factory, aitest_run
    ):
        """The read_skill_reference tool should return file content."""
        skill = skill_factory(SKILLS_DIR / "math-helper")

        agent = agent_factory(
            skill=skill,
            system_prompt=(
                "When asked about Pythagorean theorem, use read_skill_reference to read "
                "formulas.md and then quote the exact formula from the reference."
            ),
        )

        result = await aitest_run(
            agent, "What is the Pythagorean theorem? Quote the formula exactly."
        )

        assert result.success
        assert result.tool_was_called("read_skill_reference")
        # Should contain the formula from the reference (a² + b² = c²)
        assert "a²" in result.final_response or "a^2" in result.final_response
