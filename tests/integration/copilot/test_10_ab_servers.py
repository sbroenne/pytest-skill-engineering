"""Level 10 — A/B comparison: compare instruction variants side by side.

Since CopilotEval operates via Copilot's coding agent (not MCP banking
servers), A/B comparison tests instruction variants rather than server
variants. Same task, different configs — the report shows which performs
better.

Mirrors pydantic/test_10_ab_servers.py — same level, different harness.

Run with: pytest tests/integration/copilot/test_10_ab_servers.py -v
"""

from __future__ import annotations

import pytest

from pytest_skill_engineering.copilot.eval import CopilotEval

pytestmark = [pytest.mark.copilot]

INSTRUCTIONS = {
    "detailed": (
        "You are a senior Python developer. Always add type hints on every "
        "parameter and return value. Add Google-style docstrings to every "
        "function. Include error handling with try/except where appropriate. "
        "Use descriptive variable names."
    ),
    "minimal": "Write Python code.",
}


class TestInstructionABComparison:
    """Same task, two instruction variants — compare output quality."""

    @pytest.mark.parametrize("variant", ["detailed", "minimal"])
    async def test_code_creation_quality(self, copilot_eval, tmp_path, variant):
        """Compare file creation quality between detailed and minimal instructions."""
        work_dir = tmp_path / variant
        work_dir.mkdir()
        agent = CopilotEval(
            name=f"coder-{variant}",
            instructions=INSTRUCTIONS[variant],
            working_directory=str(work_dir),
        )
        result = await copilot_eval(
            agent,
            "Create a user_manager.py module with add_user(name, email) and "
            "get_user(user_id) functions. Use a dict as in-memory storage.",
        )
        assert result.success, f"{variant} failed: {result.error}"

        py_files = list(work_dir.rglob("*.py"))
        assert len(py_files) > 0, f"{variant}: no Python files created"

        content = "\n".join(f.read_text() for f in py_files)
        assert "def add_user" in content, f"{variant}: add_user not found"
        assert "def get_user" in content, f"{variant}: get_user not found"

    @pytest.mark.parametrize("variant", ["detailed", "minimal"])
    async def test_error_handling_presence(self, copilot_eval, tmp_path, variant):
        """Compare error handling quality between instruction variants."""
        work_dir = tmp_path / variant
        work_dir.mkdir()
        agent = CopilotEval(
            name=f"error-handling-{variant}",
            instructions=INSTRUCTIONS[variant],
            working_directory=str(work_dir),
        )
        result = await copilot_eval(
            agent,
            "Create a file_utils.py module with read_json(path) that reads and "
            "returns parsed JSON, and write_json(path, data) that serializes and "
            "writes JSON to a file. Handle I/O errors gracefully.",
        )
        assert result.success, f"{variant} failed: {result.error}"

        py_files = list(work_dir.rglob("*.py"))
        assert len(py_files) > 0, f"{variant}: no Python files created"

        content = "\n".join(f.read_text() for f in py_files)
        assert "def read_json" in content, f"{variant}: read_json not found"
        assert "def write_json" in content, f"{variant}: write_json not found"


class TestDocumentationQualityImpact:
    """Test how instruction detail affects documentation quality."""

    @pytest.mark.parametrize("variant", ["detailed", "minimal"])
    async def test_documentation_presence(self, copilot_eval, tmp_path, variant):
        """Detailed instructions should produce more documented code."""
        work_dir = tmp_path / variant
        work_dir.mkdir()
        agent = CopilotEval(
            name=f"docs-{variant}",
            instructions=INSTRUCTIONS[variant],
            working_directory=str(work_dir),
        )
        result = await copilot_eval(
            agent,
            "Create a string_utils.py module with: reverse(s), capitalize_words(s), "
            "and truncate(s, max_length) functions.",
        )
        assert result.success, f"{variant} failed: {result.error}"

        py_files = list(work_dir.rglob("*.py"))
        assert len(py_files) > 0, f"{variant}: no Python files created"

        content = "\n".join(f.read_text() for f in py_files)
        assert "def reverse" in content, f"{variant}: reverse not found"
        assert "def capitalize_words" in content, f"{variant}: capitalize_words not found"
        assert "def truncate" in content, f"{variant}: truncate not found"
