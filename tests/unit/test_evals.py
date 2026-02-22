"""Unit tests for evals loader functions."""

from __future__ import annotations

import pytest

from pytest_skill_engineering.core.evals import load_custom_agents, load_prompt_file, load_prompt_files


class TestLoadPromptFile:
    """Tests for load_prompt_file()."""

    def test_basic(self, tmp_path) -> None:
        f = tmp_path / "review.prompt.md"
        f.write_text("---\ndescription: Review code\n---\nReview this code for issues.")
        result = load_prompt_file(f)
        assert result["name"] == "review"
        assert result["body"] == "Review this code for issues."
        assert result["description"] == "Review code"

    def test_name_strips_prompt_md_suffix(self, tmp_path) -> None:
        f = tmp_path / "summarize.prompt.md"
        f.write_text("---\n---\nSummarize the following.")
        result = load_prompt_file(f)
        assert result["name"] == "summarize"

    def test_metadata_available(self, tmp_path) -> None:
        f = tmp_path / "check.prompt.md"
        f.write_text("---\ndescription: Check quality\nauthor: test\n---\nCheck this.")
        result = load_prompt_file(f)
        assert result["metadata"]["author"] == "test"

    def test_empty_frontmatter(self, tmp_path) -> None:
        f = tmp_path / "simple.prompt.md"
        f.write_text("---\ndescription: \n---\nJust a prompt body.")
        result = load_prompt_file(f)
        assert result["body"] == "Just a prompt body."
        assert not result["description"]  # None or empty string when not set

    def test_no_frontmatter(self, tmp_path) -> None:
        f = tmp_path / "plain.prompt.md"
        f.write_text("A prompt without frontmatter.")
        result = load_prompt_file(f)
        assert result["body"] == "A prompt without frontmatter."
        assert result["name"] == "plain"

    def test_body_stripped(self, tmp_path) -> None:
        f = tmp_path / "trim.prompt.md"
        f.write_text("---\ndescription: Trim test\n---\n\n  Trimmed body.  \n")
        result = load_prompt_file(f)
        assert result["body"] == "Trimmed body."


class TestLoadPromptFiles:
    """Tests for load_prompt_files()."""

    def test_multiple_files(self, tmp_path) -> None:
        (tmp_path / "a.prompt.md").write_text("---\n---\nPrompt A")
        (tmp_path / "b.prompt.md").write_text("---\n---\nPrompt B")
        results = load_prompt_files(tmp_path)
        assert len(results) == 2
        names = [r["name"] for r in results]
        assert "a" in names and "b" in names

    def test_empty_directory(self, tmp_path) -> None:
        results = load_prompt_files(tmp_path)
        assert results == []

    def test_ignores_non_md_files(self, tmp_path) -> None:
        (tmp_path / "notes.txt").write_text("Some notes")
        (tmp_path / "review.prompt.md").write_text("---\ndescription: x\n---\nReview this.")
        results = load_prompt_files(tmp_path)
        assert len(results) == 1
        assert results[0]["name"] == "review"

    def test_exclude_by_name(self, tmp_path) -> None:
        (tmp_path / "a.prompt.md").write_text("---\n---\nA")
        (tmp_path / "b.prompt.md").write_text("---\n---\nB")
        results = load_prompt_files(tmp_path, exclude={"a"})
        assert len(results) == 1
        assert results[0]["name"] == "b"

    def test_include_by_name(self, tmp_path) -> None:
        (tmp_path / "a.prompt.md").write_text("---\n---\nA")
        (tmp_path / "b.prompt.md").write_text("---\n---\nB")
        results = load_prompt_files(tmp_path, include={"a"})
        assert len(results) == 1
        assert results[0]["name"] == "a"


class TestLoadCustomAgents:
    """Tests for load_custom_agents()."""

    def test_basic(self, tmp_path) -> None:
        agent_file = tmp_path / "reviewer.agent.md"
        agent_file.write_text(
            "---\nname: reviewer\ndescription: Code reviewer\n---\nReview code."
        )
        agents = load_custom_agents(tmp_path)
        assert len(agents) == 1
        assert agents[0]["name"] == "reviewer"

    def test_description_loaded(self, tmp_path) -> None:
        agent_file = tmp_path / "coder.agent.md"
        agent_file.write_text(
            "---\nname: coder\ndescription: Writes code\n---\nWrite clean code."
        )
        agents = load_custom_agents(tmp_path)
        assert agents[0]["description"] == "Writes code"

    def test_prompt_body_loaded(self, tmp_path) -> None:
        agent_file = tmp_path / "helper.agent.md"
        agent_file.write_text("---\nname: helper\n---\nBe helpful always.")
        agents = load_custom_agents(tmp_path)
        assert agents[0]["prompt"] == "Be helpful always."

    def test_empty_directory(self, tmp_path) -> None:
        agents = load_custom_agents(tmp_path)
        assert agents == []

    def test_multiple_agents(self, tmp_path) -> None:
        (tmp_path / "a.agent.md").write_text("---\nname: a\n---\nAgent A.")
        (tmp_path / "b.agent.md").write_text("---\nname: b\n---\nAgent B.")
        agents = load_custom_agents(tmp_path)
        assert len(agents) == 2
        names = {a["name"] for a in agents}
        assert names == {"a", "b"}

    def test_exclude_by_name(self, tmp_path) -> None:
        (tmp_path / "keep.agent.md").write_text("---\nname: keep\n---\nKeep me.")
        (tmp_path / "skip.agent.md").write_text("---\nname: skip\n---\nSkip me.")
        agents = load_custom_agents(tmp_path, exclude={"skip"})
        assert len(agents) == 1
        assert agents[0]["name"] == "keep"

    def test_name_derived_from_filename_when_missing(self, tmp_path) -> None:
        agent_file = tmp_path / "security-reviewer.agent.md"
        agent_file.write_text("---\ndescription: Security\n---\nReview for vulns.")
        agents = load_custom_agents(tmp_path)
        assert agents[0]["name"] == "security-reviewer"
