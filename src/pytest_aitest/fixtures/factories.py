"""Agent factory fixtures."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pytest

from pytest_aitest.core.agent import Agent, Provider
from pytest_aitest.core.skill import Skill


@pytest.fixture
def agent_factory(request: pytest.FixtureRequest) -> Callable[..., Agent]:
    """Factory fixture for creating Agent configurations.

    LLM authentication is handled by LiteLLM via standard environment variables:
    - Azure: AZURE_API_BASE + `az login` (Entra ID)
    - OpenAI: OPENAI_API_KEY
    - Anthropic: ANTHROPIC_API_KEY

    Example:
        async def test_with_agent(agent_factory, aitest_run):
            agent = agent_factory(
                model="openai/gpt-4o",
                system_prompt="Be very concise.",
            )
            result = await aitest_run(agent, "Hello")
            assert result.success

        async def test_with_defaults(agent_factory, aitest_run):
            # Uses model from --aitest-model CLI option
            agent = agent_factory(system_prompt="You are helpful.")
            result = await aitest_run(agent, "Hi!")

        async def test_with_skill(agent_factory, skill_factory, aitest_run):
            skill = skill_factory("path/to/my-skill")
            agent = agent_factory(skill=skill)
            result = await aitest_run(agent, "Do something")
    """

    def create_agent(
        model: str | None = None,
        system_prompt: str | None = None,
        skill: Skill | None = None,
        max_turns: int = 10,
        rpm: int | None = None,
        tpm: int | None = None,
        **provider_kwargs: Any,
    ) -> Agent:
        """Create an Agent with sensible defaults.

        Args:
            model: LiteLLM model string (uses CLI default if not specified)
            system_prompt: Optional system prompt
            skill: Optional Skill to enhance agent capabilities
            max_turns: Maximum conversation turns
            rpm: Requests per minute limit (uses CLI default if not specified)
            tpm: Tokens per minute limit (uses CLI default if not specified)
            **provider_kwargs: Additional Provider arguments (temperature, max_tokens)

        Returns:
            Configured Agent instance
        """
        model = model or request.config.getoption("--aitest-model")
        if model is None:
            raise ValueError("Model must be specified via --aitest-model or parameter")

        # Use CLI defaults for rate limits if not specified
        if rpm is None:
            rpm = request.config.getoption("--aitest-rpm")
        if tpm is None:
            tpm = request.config.getoption("--aitest-tpm")

        provider = Provider(
            model=model,
            rpm=rpm,
            tpm=tpm,
            **provider_kwargs,
        )

        return Agent(
            provider=provider,
            system_prompt=system_prompt,
            skill=skill,
            max_turns=max_turns,
        )

    return create_agent


@pytest.fixture
def provider_factory(request: pytest.FixtureRequest) -> Callable[..., Provider]:
    """Factory fixture for creating Provider configurations.

    LLM authentication is handled by LiteLLM via standard environment variables.

    Example:
        def test_provider(provider_factory):
            provider = provider_factory("openai/gpt-4o", temperature=0.7)
            agent = Agent(provider=provider, ...)

        def test_with_rate_limits(provider_factory):
            provider = provider_factory(rpm=10, tpm=10000)  # Azure free tier
    """

    def create_provider(
        model: str | None = None,
        rpm: int | None = None,
        tpm: int | None = None,
        **kwargs: Any,
    ) -> Provider:
        """Create a Provider with CLI defaults.

        Args:
            model: LiteLLM model string
            rpm: Requests per minute limit (uses CLI default if not specified)
            tpm: Tokens per minute limit (uses CLI default if not specified)
            **kwargs: Provider arguments (temperature, max_tokens)

        Returns:
            Configured Provider instance
        """
        model = model or request.config.getoption("--aitest-model")
        if model is None:
            raise ValueError("Model must be specified via --aitest-model or parameter")

        # Use CLI defaults for rate limits if not specified
        if rpm is None:
            rpm = request.config.getoption("--aitest-rpm")
        if tpm is None:
            tpm = request.config.getoption("--aitest-tpm")

        return Provider(
            model=model,
            rpm=rpm,
            tpm=tpm,
            **kwargs,
        )

    return create_provider


@pytest.fixture
def skill_factory() -> Callable[[Path | str], Skill]:
    """Factory fixture for loading Skills.

    Example:
        def test_with_skill(skill_factory, agent_factory, aitest_run):
            skill = skill_factory("path/to/my-skill")
            agent = agent_factory(skill=skill)
            result = await aitest_run(agent, "Do something with the skill")
            assert result.success

        def test_skill_metadata(skill_factory):
            skill = skill_factory("skills/my-skill")
            assert skill.name == "my-skill"
            assert skill.has_references
    """

    def load(path: Path | str) -> Skill:
        """Load a Skill from a path.

        Args:
            path: Path to skill directory or SKILL.md file

        Returns:
            Loaded Skill instance
        """
        return Skill.from_path(path)

    return load
