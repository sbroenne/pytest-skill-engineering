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

from pytest_skill_engineering import (
    Eval,
    MCPServer,
    Provider,
    Skill,
    SkillError,
    Wait,
    export_grading,
    has_skill_evals,
    load_skill,
    load_skill_evals,
)
from pytest_skill_engineering.core.result import EvalResult

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
        assert skill.description == "Math calculation and formula helper for financial and algebraic computations"
        assert skill.metadata.version == "1.0.0"
        assert skill.metadata.license == "Apache-2.0"
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


# =============================================================================
# Agent Skills Spec Compliance (no LLM calls)
# =============================================================================


class TestAgentSkillsSpec:
    """Test full agentskills.io spec compliance."""

    async def test_load_spec_compliant_skill(self):
        """Load a skill with all agentskills.io fields."""
        skill = Skill.from_path(SKILLS_DIR / "spec-compliant")

        # Required fields
        assert skill.metadata.name == "spec-compliant"
        assert skill.metadata.description.startswith("A fully spec-compliant")

        # Optional spec fields
        assert skill.metadata.compatibility == "Requires Python 3.11+ and bash"
        assert skill.metadata.allowed_tools == ("bash", "python")
        assert skill.metadata.metadata_dict == {
            "author": "pytest-skill-engineering-team",
            "category": "testing",
        }
        assert skill.metadata.version == "2.0.0"
        assert skill.metadata.license == "MIT"

    async def test_scripts_discovery(self):
        """Scripts directory is discovered and loaded."""
        skill = Skill.from_path(SKILLS_DIR / "spec-compliant")
        assert skill.has_scripts
        assert "validate.py" in skill.scripts
        assert "def validate" in skill.scripts["validate.py"]

    async def test_assets_discovery(self):
        """Assets directory is discovered (filenames only)."""
        skill = Skill.from_path(SKILLS_DIR / "spec-compliant")
        assert skill.has_assets
        assert "template.txt" in skill.assets
        assert "schema.json" in skill.assets
        assert skill.assets_dir is not None

    async def test_references_still_work(self):
        """References directory still works with new features."""
        skill = Skill.from_path(SKILLS_DIR / "spec-compliant")
        assert skill.has_references
        assert "guide.md" in skill.references

    async def test_skill_without_optional_dirs(self):
        """Skills without scripts/assets still load fine."""
        skill = Skill.from_path(SKILLS_DIR / "simple-assistant")
        assert not skill.has_scripts
        assert not skill.has_assets
        assert skill.scripts == {}
        assert skill.assets == ()

    async def test_metadata_entries_frozen_compatible(self):
        """Metadata entries work with frozen dataclass."""
        skill = Skill.from_path(SKILLS_DIR / "spec-compliant")
        meta = skill.metadata
        # Access as dict via property
        assert isinstance(meta.metadata_dict, dict)
        assert meta.metadata_dict["author"] == "pytest-skill-engineering-team"
        # The underlying storage is tuple-of-tuples (frozen compatible)
        assert isinstance(meta.metadata_entries, tuple)


# =============================================================================
# Skill-Creator Eval Bridge (no LLM calls)
# =============================================================================


class TestSkillCreatorEvals:
    """Test skill-creator eval format import."""

    async def test_load_skill_evals(self):
        """Load evals from evals/evals.json."""
        cases = load_skill_evals(SKILLS_DIR / "spec-compliant")
        assert len(cases) == 2
        assert cases[0].prompt.startswith("Validate")
        assert len(cases[0].expectations) == 2

    async def test_has_skill_evals(self):
        """Check if skill has evals."""
        assert has_skill_evals(SKILLS_DIR / "spec-compliant")
        assert has_skill_evals(SKILLS_DIR / "math-helper")
        assert not has_skill_evals(SKILLS_DIR / "simple-assistant")

    async def test_eval_case_fields(self):
        """Eval cases have correct fields."""
        cases = load_skill_evals(SKILLS_DIR / "math-helper")
        case = cases[0]
        assert case.id == 1
        assert case.prompt  # non-empty
        assert case.expected_output  # present
        assert len(case.expectations) == 3
        assert case.name  # auto-generated name

    async def test_export_grading(self):
        """Export grading in skill-creator format."""
        # Create a minimal result for testing export
        result = EvalResult(
            turns=[],
            success=True,
        )

        grading = export_grading(
            result=result,
            expectations=["Has result", "Is correct"],
            expectation_results=[True, False],
            evidence=["Found result in output", "Missing expected value"],
        )

        assert grading["summary"]["passed"] == 1
        assert grading["summary"]["failed"] == 1
        assert grading["summary"]["total"] == 2
        assert grading["summary"]["pass_rate"] == 0.5
        assert len(grading["expectations"]) == 2
        assert grading["expectations"][0]["text"] == "Has result"
        assert grading["expectations"][0]["passed"] is True
        assert grading["expectations"][1]["passed"] is False

    async def test_missing_evals_error(self):
        """Error when evals/evals.json doesn't exist."""
        with pytest.raises(FileNotFoundError):
            load_skill_evals(SKILLS_DIR / "simple-assistant")
