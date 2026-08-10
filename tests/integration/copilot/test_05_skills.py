"""Level 05 — Skills A/B: prove skill files change Copilot behavior.

Same task, two configs — baseline (no skill) vs treatment (with skill).
Assertions verify the skill caused the observable difference.

Mirrors pydantic/test_05_skills.py — same level, different harness.

Run with: pytest tests/integration/copilot/test_05_skills.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pytest_skill_engineering.copilot.eval import CopilotEval

pytestmark = [pytest.mark.copilot]
_SKILLS_DIR = Path(__file__).resolve().parents[1] / "skills"
SKILL_MODEL = "gpt-5.5"


def _write_skill(parent: Path, name: str, body: str) -> str:
    skill_dir = parent / name
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {name} standards\n---\n\n{body}",
        encoding="utf-8",
    )
    return str(skill_dir)


class TestSkillABComparison:
    """Same task, two configs — skill produces measurably different output."""

    async def test_type_hint_skill_adds_annotations(self, copilot_eval, tmp_path):
        """Skill mandating type hints produces annotated function signatures."""
        skill_dir = _write_skill(
            tmp_path,
            "type-hints",
            "# Python Type Hint Standards\n\n"
            "Every function MUST annotate every parameter and return value.\n\n"
            "Example:\n"
            "    def add(a: float, b: float) -> float:\n"
            "        return a + b\n\n"
            "Unannotated functions are non-compliant.\n",
        )

        task = "Create math_ops.py with functions: add(a, b), subtract(a, b)."

        baseline_dir = tmp_path / "baseline"
        baseline_dir.mkdir()
        baseline = CopilotEval(
            name="baseline",
            model=SKILL_MODEL,
            instructions="Write a Python module.",
            working_directory=str(baseline_dir),
        )

        treatment_dir = tmp_path / "treatment"
        treatment_dir.mkdir()
        treatment = CopilotEval(
            name="treatment",
            model=SKILL_MODEL,
            instructions=(
                "Write a Python module. Read your loaded skills carefully and obey every "
                "required literal code pattern exactly. Apply all type hint standards from "
                "your skills with no omissions."
            ),
            working_directory=str(treatment_dir),
            skill_directories=[skill_dir],
        )

        result_a = await copilot_eval(baseline, task)
        result_b = await copilot_eval(treatment, task)

        assert result_a.success and result_b.success

        content_a = (baseline_dir / "math_ops.py").read_text()
        content_b = (treatment_dir / "math_ops.py").read_text()

        assert "->" in content_b and ": " in content_b, (
            "Type hint skill should have added annotations — not found in treatment.\n"
            f"Treatment output:\n{content_b}"
        )
        assert "->" not in content_a, (
            f"Baseline (no skill) unexpectedly contains return annotations.\nBaseline output:\n{content_a}"
        )

    async def test_simple_assistant_skill_injects_greeting_rule(self, copilot_eval, tmp_path):
        """Skill body should inject its greeting rule into the treatment config."""
        shared_instructions = (
            "Reply with exactly one short greeting sentence. Do not use the word 'Hello' "
            "unless a loaded skill requires it."
        )
        baseline_dir = tmp_path / "baseline"
        treatment_dir = tmp_path / "treatment"
        baseline_dir.mkdir()
        treatment_dir.mkdir()

        baseline = CopilotEval(
            name="baseline",
            model=SKILL_MODEL,
            instructions=shared_instructions,
            working_directory=str(baseline_dir),
        )

        treatment = CopilotEval(
            name="treatment",
            model=SKILL_MODEL,
            instructions=(
                f"{shared_instructions} Read your loaded skills carefully and obey any "
                "additional greeting requirements they impose."
            ),
            working_directory=str(treatment_dir),
            skill_directories=[str(_SKILLS_DIR / "simple-assistant")],
        )

        result_a = await copilot_eval(baseline, "Greet me.")
        result_b = await copilot_eval(treatment, "Greet me.")

        assert result_a.success and result_b.success
        assert "hello" not in (result_a.final_response or "").lower()
        assert "hello" in (result_b.final_response or "").lower()

    async def test_math_helper_skill_reads_reference_docs(self, copilot_eval, tmp_path):
        """Skill references should become usable tools and shape math workflow."""
        prompt = "What is the volume of a cylinder with radius 3 and height 5?"
        baseline_dir = tmp_path / "baseline"
        treatment_dir = tmp_path / "treatment"
        baseline_dir.mkdir()
        treatment_dir.mkdir()

        baseline = CopilotEval(
            name="baseline",
            model=SKILL_MODEL,
            instructions="Solve math questions clearly.",
            working_directory=str(baseline_dir),
        )

        treatment = CopilotEval(
            name="treatment",
            model=SKILL_MODEL,
            instructions=(
                "Solve math questions clearly. Read your loaded skills carefully and follow "
                "their required workflow exactly."
            ),
            working_directory=str(treatment_dir),
            skill_directories=[str(_SKILLS_DIR / "math-helper")],
        )

        result_a = await copilot_eval(baseline, prompt)
        result_b = await copilot_eval(treatment, prompt)

        assert result_a.success and result_b.success
        assert not result_a.tool_was_called("list_skill_references")
        assert result_b.tool_was_called("list_skill_references")
        assert result_b.tool_was_called("read_skill_reference")
        assert "141.37" in (result_b.final_response or "") or "141.38" in (
            result_b.final_response or ""
        )
