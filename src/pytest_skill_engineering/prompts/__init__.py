"""Prompt loading utilities for pytest-skill-engineering.

Provides prompt templates from the prompts directory.
"""

from __future__ import annotations

import functools
from pathlib import Path

_PROMPT_DIR = Path(__file__).parent


@functools.cache
def get_ai_summary_prompt() -> str:
    """Load the AI summary analysis prompt template.

    Returns the content of ai_summary.md as a string. Result is cached.
    """
    prompt_path = _PROMPT_DIR / "ai_summary.md"
    return prompt_path.read_text(encoding="utf-8")


__all__ = ["get_ai_summary_prompt"]
