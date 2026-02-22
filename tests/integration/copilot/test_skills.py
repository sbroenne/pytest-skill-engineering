"""Skill A/B testing.

Proves that skill files change agent behavior by running the SAME task
with two configs and asserting the outputs differ in a predictable way:

    Baseline  — no skill, minimal instructions
    Treatment — same instructions + skill directory with a specific mandate

The assertion proves the SKILL caused the difference, not the instructions.
"""

from __future__ import annotations

import pytest

from pytest_skill_engineering.copilot.eval import CopilotEval


@pytest.mark.copilot
class TestSkillABComparison:
    """Same task, two configs — skill produces measurably different output than no-skill baseline."""

    async def test_version_declaration_skill_adds_dunder_version(self, copilot_eval, tmp_path):
        """Skill mandating __version__ produces a module version declaration.

        Baseline (no skill): agent creates a plain module — LLMs never add __version__
        to simple utility modules without being told.
        Treatment (__version__ skill): same module declares its version at the top.
        The declaration is the observable signal that the skill was applied.
        """
        skill_dir = tmp_path / "skills"
        skill_dir.mkdir()
        (skill_dir / "versioning.md").write_text(
            "# Module Versioning Standards\n\n"
            "Every Python module MUST declare its version at the top of the file:\n\n"
            '    __version__ = "1.0.0"\n\n'
            "Place this immediately after imports. "
            "Modules without __version__ are considered unversioned and will fail release checks.\n"
        )

        task = "Create math_ops.py with functions: add(a, b), subtract(a, b)."

        baseline_dir = tmp_path / "baseline"
        baseline_dir.mkdir()
        baseline = CopilotEval(
            name="baseline",
            instructions="Write a Python module.",
            working_directory=str(baseline_dir),
        )

        treatment_dir = tmp_path / "treatment"
        treatment_dir.mkdir()
        treatment = CopilotEval(
            name="treatment",
            instructions="Write a Python module. Apply all versioning standards from your skills.",
            working_directory=str(treatment_dir),
            skill_directories=[str(skill_dir)],
        )

        result_a = await copilot_eval(baseline, task)
        result_b = await copilot_eval(treatment, task)

        assert result_a.success and result_b.success

        content_a = (baseline_dir / "math_ops.py").read_text()
        content_b = (treatment_dir / "math_ops.py").read_text()

        assert "__version__" in content_b, (
            "Versioning skill should have added __version__ declaration — not found in treatment.\n"
            f"Treatment output:\n{content_b}"
        )
        assert "__version__" not in content_a, (
            "Baseline (no skill) unexpectedly contains __version__ — this differentiator is unreliable.\n"
            f"Baseline output:\n{content_a}"
        )

    async def test_module_exports_skill_adds_all_declaration(self, copilot_eval, tmp_path):
        """Skill mandating __all__ exports produces explicit public API declarations.

        Baseline (no skill): agent creates a plain module — LLMs almost never add __all__
        without being told to.
        Treatment (__all__ skill): same module explicitly declares its public API.
        """
        skill_dir = tmp_path / "skills"
        skill_dir.mkdir()
        (skill_dir / "module-exports.md").write_text(
            "# Module Export Standards\n\n"
            "Every Python module MUST declare its public API using __all__.\n\n"
            "Place this at the top of every module (after imports):\n"
            '    __all__ = ["FunctionName", "ClassName"]\n\n'
            "Modules without __all__ are considered incomplete and will fail review.\n"
        )

        task = "Create math_utils.py with functions: add(a, b), subtract(a, b), multiply(a, b)."

        baseline_dir = tmp_path / "baseline"
        baseline_dir.mkdir()
        baseline = CopilotEval(
            name="baseline",
            instructions="Write a Python module.",
            working_directory=str(baseline_dir),
        )

        treatment_dir = tmp_path / "treatment"
        treatment_dir.mkdir()
        treatment = CopilotEval(
            name="treatment",
            instructions="Write a Python module. Apply all module export standards from your skills.",
            working_directory=str(treatment_dir),
            skill_directories=[str(skill_dir)],
        )

        result_a = await copilot_eval(baseline, task)
        result_b = await copilot_eval(treatment, task)

        assert result_a.success and result_b.success

        content_a = (baseline_dir / "math_utils.py").read_text()
        content_b = (treatment_dir / "math_utils.py").read_text()

        assert "__all__" in content_b, (
            "Module exports skill should have added __all__ declaration — not found in treatment.\n"
            f"Treatment output:\n{content_b}"
        )
        assert "__all__" not in content_a, (
            "Baseline (no skill) unexpectedly contains __all__ — choose a stronger differentiator.\n"
            f"Baseline output:\n{content_a}"
        )

    async def test_docstring_format_skill_produces_google_style(self, copilot_eval, tmp_path):
        """Skill mandating Google-style docstrings produces Args:/Returns: sections.

        Baseline (no skill): agent writes plain one-line docstrings or none at all.
        Treatment (Google docstring skill): every function has structured Args: and Returns: sections.
        The structured format is the observable signal that the skill was applied.
        """
        skill_dir = tmp_path / "skills"
        skill_dir.mkdir()
        (skill_dir / "docstring-format.md").write_text(
            "# Docstring Standards — Google Style\n\n"
            "Every function MUST have a Google-style docstring with these sections:\n\n"
            "    def example(x: int) -> str:\n"
            '        """One-line summary.\n\n'
            "        Args:\n"
            "            x: Description of x.\n\n"
            "        Returns:\n"
            "            Description of return value.\n"
            '        """\n\n'
            "Docstrings without Args: and Returns: sections are non-compliant.\n"
        )

        task = "Create converter.py with functions: to_celsius(f), to_fahrenheit(c), to_kelvin(c)."

        baseline_dir = tmp_path / "baseline"
        baseline_dir.mkdir()
        baseline = CopilotEval(
            name="baseline",
            instructions="Write a Python module with minimal documentation.",
            working_directory=str(baseline_dir),
        )

        treatment_dir = tmp_path / "treatment"
        treatment_dir.mkdir()
        treatment = CopilotEval(
            name="treatment",
            instructions="Write a Python module. Apply all docstring standards from your skills.",
            working_directory=str(treatment_dir),
            skill_directories=[str(skill_dir)],
        )

        result_a = await copilot_eval(baseline, task)
        result_b = await copilot_eval(treatment, task)

        assert result_a.success and result_b.success

        content_a = (baseline_dir / "converter.py").read_text()
        content_b = (treatment_dir / "converter.py").read_text()

        assert "Args:" in content_b and "Returns:" in content_b, (
            "Google docstring skill should have added Args:/Returns: sections — not found in treatment.\n"
            f"Treatment output:\n{content_b}"
        )
        assert content_a != content_b, (
            "Skill had no effect — both configs produced identical output."
        )
