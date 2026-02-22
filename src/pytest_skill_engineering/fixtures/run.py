"""Eval run fixture."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator, Callable
from typing import TYPE_CHECKING, Any

import pytest

from pytest_skill_engineering.core.eval import Eval
from pytest_skill_engineering.core.result import EvalResult
from pytest_skill_engineering.execution.engine import EvalEngine
from pytest_skill_engineering.plugin import SESSION_MESSAGES_KEY

if TYPE_CHECKING:
    pass

_logger = logging.getLogger(__name__)


def _get_session_key(request: pytest.FixtureRequest) -> str | None:
    """Get session key from @pytest.mark.session marker.

    The key includes parametrize params for isolation, so tests with different
    parameters get isolated sessions.

    Returns:
        Session key string or None if no session marker present.
    """
    marker = request.node.get_closest_marker("session")
    if not marker:
        return None

    if not marker.args:
        raise ValueError("@pytest.mark.session requires a session name argument")

    session_name = marker.args[0]

    # Include parametrize params for isolation
    params = getattr(request.node, "callspec", None)
    if params and params.id:
        return f"{session_name}[{params.id}]"
    return session_name


@pytest.fixture
def eval_run(
    request: pytest.FixtureRequest,
) -> Callable[..., Any]:
    """Fixture providing a function to run agent interactions.

    Works seamlessly with pytest.mark.parametrize for model/prompt comparison:

    Example:
        @pytest.mark.parametrize("model", ["openai/gpt-4o", "openai/gpt-4o-mini"])
        async def test_model_comparison(eval_run, model):
            agent = Eval.from_instructions(
                "default",
                "You are a helpful assistant.",
                provider=Provider(model=model),
            )
            result = await eval_run(agent, "Hello!")
            assert result.success

        @pytest.mark.parametrize("prompt", [PROMPT_V1, PROMPT_V2])
        async def test_prompt_comparison(eval_run, prompt):
            agent = Eval.from_instructions(
                prompt.name,
                prompt.system_prompt,
                provider=Provider(model="openai/gpt-4o-mini"),
            )
            result = await eval_run(agent, "Hello!")
            assert result.success

    Session continuity with @pytest.mark.session:

        @pytest.mark.session("banking_session")
        async def test_check_balance(eval_run):
            result = await eval_run(agent, "What's my checking balance?")
            assert result.success

        @pytest.mark.session("banking_session")
        async def test_followup_transfer(eval_run):
            # Messages from previous test are automatically injected
            result = await eval_run(agent, "Transfer $100 to savings")
            assert result.success
    """
    engines: list[EvalEngine] = []
    results: list[EvalResult] = []

    # Get session key for this test (if @pytest.mark.session is present)
    session_key = _get_session_key(request)

    async def run_agent(
        agent: Eval,
        prompt: str,
        *,
        max_turns: int | None = None,
        timeout_ms: int = 60000,
        messages: list[Any] | None = None,
        prompt_name: str | None = None,
    ) -> EvalResult:
        """Run an agent with the given prompt.

        Args:
            agent: Eval configuration with provider and servers
            prompt: User prompt to send
            max_turns: Maximum conversation turns (default: agent.max_turns)
            timeout_ms: Timeout for the entire run (default: 60000)
            messages: Optional prior conversation messages for session continuity.
                     Pass result.messages from a previous test to continue the
                     conversation instead of starting fresh.
                     If using @pytest.mark.session and messages is not provided,
                     messages from the previous test in the session are used automatically.
            prompt_name: Optional name identifying which prompt file was used
                (e.g., from ``load_prompt_file()["name"]``). Stored on the
                result and passed to AI analysis for prompt file feedback.

        Returns:
            EvalResult with conversation history and tool calls
        """
        # Auto-inject session messages if not explicitly provided
        effective_messages = messages
        if effective_messages is None and session_key:
            session_storage = request.config.stash.get(SESSION_MESSAGES_KEY, {})
            effective_messages = session_storage.get(session_key)

        engine = EvalEngine(agent)
        engines.append(engine)

        await engine.initialize()
        result = await engine.run(
            prompt, max_turns=max_turns, timeout_ms=timeout_ms, messages=effective_messages
        )

        # Store prompt name on result if provided
        if prompt_name is not None:
            result.prompt_name = prompt_name

        # Auto-save messages for next test in session
        # Note: Session storage is not thread-safe. Session tests must run
        # sequentially (not with pytest-xdist). This is by design — session
        # tests have ordered dependencies and cannot be parallelized.
        if session_key:
            session_storage = request.config.stash.get(SESSION_MESSAGES_KEY, {})
            session_storage[session_key] = result.messages
            request.config.stash[SESSION_MESSAGES_KEY] = session_storage

        # Store result for reporting
        results.append(result)
        # Store the most recent result and agent for the plugin to pick up
        request.node._aitest_result = result  # type: ignore[attr-defined]
        request.node._aitest_agent = agent  # type: ignore[attr-defined]

        return result

    # Store engines for cleanup
    request.node._aitest_engines = engines  # type: ignore[attr-defined]

    return run_agent


@pytest.fixture(autouse=True)
async def _aitest_auto_cleanup(
    request: pytest.FixtureRequest,
) -> AsyncGenerator[None, None]:
    """Automatically cleanup any agent engines after each test."""
    yield

    engines = getattr(request.node, "_aitest_engines", [])
    for engine in engines:
        try:
            await engine.shutdown()
        except Exception:
            _logger.warning("Engine cleanup failed", exc_info=True)
