"""Clarification detection using PydanticAI's LLM-as-judge.

Detects when an agent asks for user input instead of executing the requested task.
Uses pydantic-evals' judge_output() for structured LLM evaluation.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from pydantic_evals.evaluators.llm_as_a_judge import judge_output

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from pydantic_ai.models import Model

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
    judge_model: Model | str,
    timeout_seconds: float = 10.0,
) -> bool:
    """Check if an agent response is asking for clarification.

    Uses pydantic-evals' LLM judge to semantically classify the response.
    Fails open (returns False) on any error, so detection never breaks test execution.

    Args:
        response_text: The agent's final response text to classify.
        judge_model: PydanticAI model (Model object or string like "openai:gpt-5-mini").
        timeout_seconds: Timeout for the judge LLM call.

    Returns:
        True if the response is asking for clarification, False otherwise.
    """
    if not response_text or not response_text.strip():
        return False

    try:
        async with asyncio.timeout(timeout_seconds):
            grading = await judge_output(
                output=response_text,
                rubric=CLARIFICATION_RUBRIC,
                model=judge_model,
            )

            if grading.pass_:
                _logger.info(
                    "Clarification detected (reason: %s) in response: %s",
                    grading.reason,
                    response_text[:100],
                )

            return grading.pass_

    except TimeoutError:
        _logger.debug("Clarification judge timed out after %ss", timeout_seconds)
        return False
    except Exception:
        _logger.debug("Clarification judge failed, skipping detection", exc_info=True)
        return False
