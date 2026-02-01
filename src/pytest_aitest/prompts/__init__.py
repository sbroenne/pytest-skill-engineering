"""Prompt loading utilities for pytest-aitest.

Provides functions to load prompt templates from the prompts directory.
"""

from __future__ import annotations

import functools
from importlib import resources


@functools.cache
def get_ai_summary_prompt() -> str:
    """Load the AI summary system prompt.

    The prompt is cached after first load.

    Returns:
        The system prompt text for AI summary generation.
    """
    package = __package__ or __name__
    prompt_file = resources.files(package) / "ai_summary.md"
    return prompt_file.read_text(encoding="utf-8")


__all__ = ["get_ai_summary_prompt"]
