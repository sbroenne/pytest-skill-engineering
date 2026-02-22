"""Tests for core.prompt module - YAML prompt loading."""

from pathlib import Path

import pytest

from pytest_skill_engineering.core.prompt import Prompt, load_prompt, load_prompts


class TestPrompt:
    """Tests for Prompt dataclass."""

    def test_basic_prompt(self) -> None:
        """Create a basic prompt."""
        prompt = Prompt(name="test", system_prompt="You are helpful.")
        assert prompt.name == "test"
        assert prompt.system_prompt == "You are helpful."
        assert prompt.version == "1.0"  # Default
        assert prompt.description == ""  # Default

    def test_prompt_with_all_fields(self) -> None:
        """Create a prompt with all fields."""
        prompt = Prompt(
            name="full",
            system_prompt="Be helpful",
            version="2.0",
            description="A full prompt",
            metadata={"author": "test"},
        )
        assert prompt.name == "full"
        assert prompt.version == "2.0"
        assert prompt.description == "A full prompt"
        assert prompt.metadata == {"author": "test"}

    def test_prompt_repr(self) -> None:
        """Repr shows name and version."""
        prompt = Prompt(name="test", version="1.5")
        assert repr(prompt) == "Prompt('test', version='1.5')"


class TestPromptFromYaml:
    """Tests for loading prompts from YAML files."""

    def test_load_minimal_yaml(self, tmp_path: Path) -> None:
        """Load YAML with only required fields."""
        yaml_file = tmp_path / "minimal.yaml"
        yaml_file.write_text("name: minimal-prompt")

        prompt = Prompt.from_yaml(yaml_file)
        assert prompt.name == "minimal-prompt"
        assert prompt.system_prompt == ""
        assert prompt.version == "1.0"

    def test_load_full_yaml(self, tmp_path: Path) -> None:
        """Load YAML with all fields."""
        yaml_content = """
name: full-prompt
version: "2.0"
description: A complete prompt
system_prompt: |
  You are a helpful assistant.
  Be concise and accurate.
metadata:
  author: test
  category: general
"""
        yaml_file = tmp_path / "full.yaml"
        yaml_file.write_text(yaml_content)

        prompt = Prompt.from_yaml(yaml_file)
        assert prompt.name == "full-prompt"
        assert prompt.version == "2.0"
        assert prompt.description == "A complete prompt"
        assert "helpful assistant" in prompt.system_prompt
        assert "concise" in prompt.system_prompt
        assert prompt.metadata["author"] == "test"

    def test_load_yaml_missing_name_raises(self, tmp_path: Path) -> None:
        """YAML without name field raises ValueError."""
        yaml_file = tmp_path / "no_name.yaml"
        yaml_file.write_text("system_prompt: Hello")

        with pytest.raises(ValueError, match="missing required 'name' field"):
            Prompt.from_yaml(yaml_file)

    def test_load_yaml_file_not_found(self, tmp_path: Path) -> None:
        """Non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="not found"):
            Prompt.from_yaml(tmp_path / "nonexistent.yaml")

    def test_load_yaml_numeric_version_converted(self, tmp_path: Path) -> None:
        """Numeric version is converted to string."""
        yaml_file = tmp_path / "numeric.yaml"
        yaml_file.write_text("name: test\nversion: 1.5")

        prompt = Prompt.from_yaml(yaml_file)
        assert prompt.version == "1.5"
        assert isinstance(prompt.version, str)


class TestPromptFromDict:
    """Tests for creating prompts from dictionaries."""

    def test_from_dict_basic(self) -> None:
        """Create prompt from dict."""
        data = {"name": "dict-prompt", "system_prompt": "Hello"}
        prompt = Prompt.from_dict(data)
        assert prompt.name == "dict-prompt"
        assert prompt.system_prompt == "Hello"

    def test_from_dict_missing_name(self) -> None:
        """Dict without name raises ValueError."""
        with pytest.raises(ValueError, match="missing required 'name' field"):
            Prompt.from_dict({"system_prompt": "Hello"})


class TestLoadPrompts:
    """Tests for loading multiple prompts from a directory."""

    def test_load_prompts_from_directory(self, tmp_path: Path) -> None:
        """Load all YAML files from directory."""
        (tmp_path / "a.yaml").write_text("name: alpha")
        (tmp_path / "b.yaml").write_text("name: beta")
        (tmp_path / "c.yaml").write_text("name: gamma")

        prompts = load_prompts(tmp_path)
        assert len(prompts) == 3
        # Should be sorted by name
        assert prompts[0].name == "alpha"
        assert prompts[1].name == "beta"
        assert prompts[2].name == "gamma"

    def test_load_prompts_yml_extension(self, tmp_path: Path) -> None:
        """Also loads .yml files."""
        (tmp_path / "a.yml").write_text("name: yml-prompt")

        prompts = load_prompts(tmp_path)
        assert len(prompts) == 1
        assert prompts[0].name == "yml-prompt"

    def test_load_prompts_prefers_yaml_over_yml(self, tmp_path: Path) -> None:
        """If both .yaml and .yml exist with same stem, prefer .yaml."""
        (tmp_path / "test.yaml").write_text("name: from-yaml")
        (tmp_path / "test.yml").write_text("name: from-yml")

        prompts = load_prompts(tmp_path)
        assert len(prompts) == 1
        assert prompts[0].name == "from-yaml"

    def test_load_prompts_empty_directory(self, tmp_path: Path) -> None:
        """Empty directory returns empty list."""
        prompts = load_prompts(tmp_path)
        assert prompts == []

    def test_load_prompts_nonexistent_directory(self, tmp_path: Path) -> None:
        """Non-existent directory raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="not found"):
            load_prompts(tmp_path / "nonexistent")


class TestLoadPrompt:
    """Tests for load_prompt convenience function."""

    def test_load_single_prompt(self, tmp_path: Path) -> None:
        """Load a single prompt file."""
        yaml_file = tmp_path / "single.yaml"
        yaml_file.write_text("name: single\nsystem_prompt: Hello")

        prompt = load_prompt(yaml_file)
        assert prompt.name == "single"
        assert prompt.system_prompt == "Hello"
