"""Unit tests for the coding agent analysis prompt."""

from __future__ import annotations

from pathlib import Path


class TestCodingAgentAnalysisPrompt:
    """Tests for the coding agent analysis prompt file."""

    def test_prompt_file_exists(self) -> None:
        """The coding agent analysis prompt file exists."""
        prompt_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "pytest_aitest"
            / "prompts"
            / "coding_agent_analysis.md"
        )
        assert prompt_path.exists(), f"Prompt file not found: {prompt_path}"

    def test_prompt_has_coding_agent_framing(self) -> None:
        """Prompt uses coding-agent framing, not the default aitest framing."""
        prompt_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "pytest_aitest"
            / "prompts"
            / "coding_agent_analysis.md"
        )
        content = prompt_path.read_text(encoding="utf-8")
        assert "coding agent" in content.lower()

    def test_prompt_has_required_sections(self) -> None:
        """Prompt contains all expected analysis sections."""
        prompt_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "pytest_aitest"
            / "prompts"
            / "coding_agent_analysis.md"
        )
        content = prompt_path.read_text(encoding="utf-8")
        for section in [
            "Failure Analysis",
            "Model Comparison",
            "Instruction Effectiveness",
            "Tool Usage",
        ]:
            assert section in content, f"Missing section: {section}"

    def test_prompt_has_pricing_placeholder(self) -> None:
        """Prompt includes the pricing table placeholder for litellm."""
        prompt_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "pytest_aitest"
            / "prompts"
            / "coding_agent_analysis.md"
        )
        content = prompt_path.read_text(encoding="utf-8")
        assert "{{PRICING_TABLE}}" in content
