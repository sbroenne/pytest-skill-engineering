"""Prompt loading and management."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class Prompt:
    """A loadable prompt configuration.

    Example YAML:
        name: banking-assistant
        version: "1.0"
        description: Concise banking responses
        system_prompt: |
          You are a banking assistant.
          Be brief and always include account balances.

    Example usage:
        prompt = Prompt.from_yaml("prompts/banking.yaml")
        agent = Agent(system_prompt=prompt.system_prompt, ...)
    """

    name: str
    system_prompt: str = ""
    version: str = "1.0"
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str | Path) -> Prompt:
        """Load a prompt from a YAML file.

        Args:
            path: Path to YAML file

        Returns:
            Prompt instance

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If required fields are missing
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Prompt file not found: {path}")

        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        if "name" not in data:
            raise ValueError(f"Prompt file missing required 'name' field: {path}")

        return cls(
            name=data["name"],
            system_prompt=data.get("system_prompt", ""),
            version=str(data.get("version", "1.0")),
            description=data.get("description", ""),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Prompt:
        """Create a Prompt from a dictionary."""
        if "name" not in data:
            raise ValueError("Prompt data missing required 'name' field")

        return cls(
            name=data["name"],
            system_prompt=data.get("system_prompt", ""),
            version=str(data.get("version", "1.0")),
            description=data.get("description", ""),
            metadata=data.get("metadata", {}),
        )

    def __repr__(self) -> str:
        return f"Prompt({self.name!r}, version={self.version!r})"


def load_prompts(directory: str | Path) -> list[Prompt]:
    """Load all prompt YAML files from a directory.

    Args:
        directory: Path to directory containing .yaml/.yml files

    Returns:
        List of Prompt instances sorted by name

    Example:
        prompts = load_prompts("prompts/")

        @pytest.mark.parametrize("prompt", prompts, ids=lambda p: p.name)
        async def test_prompts(aitest_run, prompt):
            agent = Agent(system_prompt=prompt.system_prompt, ...)
    """
    directory = Path(directory)
    if not directory.exists():
        raise FileNotFoundError(f"Prompts directory not found: {directory}")

    prompts = []
    yaml_files = set()

    for path in sorted(directory.glob("*.yaml")):
        prompts.append(Prompt.from_yaml(path))
        yaml_files.add(path.stem)

    for path in sorted(directory.glob("*.yml")):
        if path.stem not in yaml_files:
            prompts.append(Prompt.from_yaml(path))

    return sorted(prompts, key=lambda p: p.name)


def load_prompt(path: str | Path) -> Prompt:
    """Load a single prompt from a YAML file.

    Args:
        path: Path to YAML file

    Returns:
        Prompt instance
    """
    return Prompt.from_yaml(path)


def load_system_prompts(directory: str | Path) -> dict[str, str]:
    """Load all system prompts from a directory as a simple dict.

    This is a convenience function for quick parametrization.
    For full Prompt metadata, use load_prompts() instead.

    Args:
        directory: Path to directory containing .yaml/.yml or .md files

    Returns:
        Dict mapping prompt name to system_prompt content

    Example:
        prompts = load_system_prompts(Path("prompts/"))
        # {"concise": "Be brief...", "detailed": "Explain..."}

        @pytest.mark.parametrize("prompt_name,system_prompt", prompts.items())
        async def test_with_prompt(aitest_run, prompt_name, system_prompt):
            agent = Agent(system_prompt=system_prompt, ...)
    """
    directory = Path(directory)
    if not directory.exists():
        raise FileNotFoundError(f"Prompts directory not found: {directory}")

    result = {}

    # Load from YAML files
    for prompt in load_prompts(directory):
        result[prompt.name] = prompt.system_prompt

    # Also load from .md files (plain markdown = system prompt content)
    for path in sorted(directory.glob("*.md")):
        name = path.stem
        if name not in result:  # YAML takes precedence
            result[name] = path.read_text(encoding="utf-8")

    return result
