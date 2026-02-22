"""Model comparison tests.

Use parametrize to run the same prompt against different models
and compare results in the report.
"""

from __future__ import annotations

import pytest

from pytest_aitest.copilot.agent import CopilotAgent

from .conftest import MODELS


@pytest.mark.copilot
class TestModelComparison:
    """Compare models on the same task."""

    @pytest.mark.parametrize("model", MODELS)
    async def test_simple_function(self, copilot_run, tmp_path, model):
        """Each model should create a working function."""
        agent = CopilotAgent(
            name=f"model-{model}",
            model=model,
            instructions="Create files as requested. Be concise.",
            working_directory=str(tmp_path),
        )
        result = await copilot_run(
            agent,
            "Create fibonacci.py with a function fibonacci(n) that returns the nth Fibonacci number.",
        )
        assert result.success, f"Model {model} failed: {result.error}"
        assert (tmp_path / "fibonacci.py").exists()

    @pytest.mark.parametrize("model", MODELS)
    async def test_error_handling(self, copilot_run, tmp_path, model):
        """Each model should produce code with proper error handling."""
        agent = CopilotAgent(
            name=f"model-{model}",
            model=model,
            instructions="Write production-quality code with proper error handling.",
            working_directory=str(tmp_path),
        )
        result = await copilot_run(
            agent,
            "Create a file parser.py that reads a JSON file and returns its contents. "
            "Handle FileNotFoundError and json.JSONDecodeError gracefully.",
        )
        assert result.success
        content = (tmp_path / "parser.py").read_text()
        assert "FileNotFoundError" in content or "except" in content
