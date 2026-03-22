"""Clarification detection using Copilot SDK as LLM-as-judge.

Detects when an agent asks for user input instead of executing the requested task.
Uses the Copilot SDK to make a semantic evaluation of the response.
"""

from __future__ import annotations

import asyncio
import logging

_logger = logging.getLogger(__name__)

CLARIFICATION_RUBRIC = (
    "The AI assistant is asking for user input, confirmation, or clarification "
    "BEFORE completing the requested task. "
    "This includes asking 'Would you like me to...', 'Should I proceed...', "
    "'Do you want me to...', 'Which would you prefer?', requesting confirmation "
    "before acting, or asking for missing information. "
    "The response FAILS this rubric (is NOT asking for clarification) if it: "
    "provides the requested information directly, "
    "uses past tense to describe completed actions, "
    "starts with 'Done!' or 'Complete' or 'Successfully', "
    "or ends with 'Let me know if...' AFTER describing completed work."
)


async def check_clarification(
    response_text: str,
    *,
    judge_model: str,
    timeout_seconds: float = 10.0,
) -> bool:
    """Check if an agent response is asking for clarification.

    Uses the Copilot SDK as an LLM judge to semantically classify the response.
    Fails open (returns False) on any error, so detection never breaks test execution.

    Args:
        response_text: The agent's final response text to classify.
        judge_model: Model string (e.g. "gpt-5-mini", "claude-sonnet-4").
        timeout_seconds: Timeout for the judge LLM call.

    Returns:
        True if the response is asking for clarification, False otherwise.
    """
    if not response_text or not response_text.strip():
        return False

    try:
        from pytest_skill_engineering.copilot.judge import copilot_judge  # noqa: PLC0415

        async with asyncio.timeout(timeout_seconds):
            prompt = (
                f"You are a judge. Determine if the following AI assistant response "
                f"is asking for user input or clarification BEFORE completing the task.\n\n"
                f"Rubric: {CLARIFICATION_RUBRIC}\n\n"
                f"Response to evaluate:\n---\n{response_text}\n---\n\n"
                f"Respond with ONLY 'PASS' if the assistant IS asking for clarification, "
                f"or 'FAIL' if the assistant is NOT asking for clarification (completed the task). "
                f"Include a brief reason on the second line."
            )

            # Strip model prefix if present
            model = judge_model
            if "/" in model:
                model = model.split("/", 1)[1]

            response = await copilot_judge(prompt, model=model, timeout_seconds=timeout_seconds)

            # Parse response: PASS = asking for clarification, FAIL = not asking
            verdict = response.strip().split("\n")[0].upper()
            is_clarification = "PASS" in verdict and "FAIL" not in verdict

            if is_clarification:
                _logger.info(
                    "Clarification detected in response: %s",
                    response_text[:100],
                )

            return is_clarification

    except TimeoutError:
        _logger.debug("Clarification judge timed out after %ss", timeout_seconds)
        return False
    except Exception:
        _logger.debug("Clarification judge failed, skipping detection", exc_info=True)
        return False
