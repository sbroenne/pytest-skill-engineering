"""Skill refinement based on eval grading results.

Phase 3 of the skill-creator workflow: analyze failures from grading.json
and suggest improvements to SKILL.md.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pytest_skill_engineering.copilot.judge import copilot_judge

if TYPE_CHECKING:
    from pytest_skill_engineering.core.skill import Skill
    from pytest_skill_engineering.core.skill_eval_results import SkillGradingResult

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class RefinementSuggestion:
    """A suggested improvement to a skill's instructions."""

    section: str  # Which part of SKILL.md to modify
    current_text: str  # What's there now (snippet)
    suggested_text: str  # What it should say
    reasoning: str  # Why this change would help
    addresses_failures: tuple[str, ...]  # Which failed expectations this fixes


@dataclass(slots=True)
class RefinementResult:
    """Result of analyzing skill eval failures and suggesting improvements."""

    skill_name: str
    suggestions: list[RefinementSuggestion]
    summary: str  # Human-readable summary of what needs fixing
    failures_analyzed: int
    pass_rate_before: float


async def analyze_skill_failures(
    skill: Skill,
    grading_result: SkillGradingResult,
    *,
    model: str | None = None,
) -> RefinementResult:
    """Analyze eval failures and suggest SKILL.md improvements.

    Uses an LLM to understand WHY expectations failed and HOW
    the skill instructions could be improved to fix them.

    Args:
        skill: The loaded skill (has .content for SKILL.md text)
        grading_result: Results from skill_eval_runner
        model: Model to use for analysis (defaults to copilot judge default)

    Returns:
        RefinementResult with suggested improvements
    """
    # If all tests passed, return empty suggestions
    if grading_result.all_passed:
        return RefinementResult(
            skill_name=skill.metadata.name,
            suggestions=[],
            summary="All evaluations passed — no improvements needed.",
            failures_analyzed=0,
            pass_rate_before=1.0,
        )

    # Build list of failed expectations
    failed_expectations: list[dict[str, str]] = []
    for case_result in grading_result.cases:
        if not case_result.passed:
            for exp, passed, evidence in zip(
                case_result.case.expectations,
                case_result.expectation_results,
                case_result.evidence,
                strict=True,
            ):
                if not passed:
                    failed_expectations.append(
                        {
                            "prompt": case_result.case.prompt,
                            "expectation": exp,
                            "evidence": evidence[:500],  # Truncate long responses
                        }
                    )

    if not failed_expectations:
        return RefinementResult(
            skill_name=skill.metadata.name,
            suggestions=[],
            summary="All expectations passed.",
            failures_analyzed=0,
            pass_rate_before=grading_result.pass_rate,
        )

    # Build the analysis prompt
    failed_text = "\n\n".join(
        f"### Failure {i + 1}\n"
        f"**Prompt:** {fail['prompt']}\n\n"
        f"**Failed Expectation:** {fail['expectation']}\n\n"
        f"**Agent Response (evidence):** {fail['evidence']}"
        for i, fail in enumerate(failed_expectations)
    )

    schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "suggestions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "section": {"type": "string"},
                        "current_text": {"type": "string"},
                        "suggested_text": {"type": "string"},
                        "reasoning": {"type": "string"},
                        "addresses_failures": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": [
                        "section",
                        "current_text",
                        "suggested_text",
                        "reasoning",
                        "addresses_failures",
                    ],
                },
            },
        },
        "required": ["summary", "suggestions"],
    }

    prompt = f"""You are analyzing a skill's eval results to suggest improvements.

## Current Skill Instructions (SKILL.md)
```markdown
{skill.content}
```

## Failed Expectations
{failed_text}

## Task
Analyze why these expectations failed and suggest specific changes to the skill instructions.

For each suggestion, provide:
- **section**: Which part of the skill to modify (e.g., "Main Instructions", "Tool Usage")
- **current_text**: Quote the relevant text from the skill (or "N/A" if adding new)
- **suggested_text**: The improved text that would fix the failures
- **reasoning**: Why this would help the agent pass the failed expectations
- **addresses_failures**: List the failed expectation texts this suggestion addresses

Respond ONLY with valid JSON matching this schema:
```json
{json.dumps(schema, indent=2)}
```

**IMPORTANT:** Your response must be ONLY the JSON object, with no markdown formatting,
no code fences, no additional text.
"""

    # Call the LLM judge
    response = await copilot_judge(prompt, model=model, timeout_seconds=60.0)

    # Parse the response
    try:
        # Strip markdown code fences if present
        cleaned = response.strip()
        if cleaned.startswith("```"):
            # Remove opening fence
            lines = cleaned.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            # Remove closing fence
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines)

        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse LLM refinement response as JSON: %s", exc)
        logger.debug("Raw response: %s", response)
        # Return a generic suggestion
        return RefinementResult(
            skill_name=skill.metadata.name,
            suggestions=[
                RefinementSuggestion(
                    section="General",
                    current_text="",
                    suggested_text=(
                        "Review the skill instructions and ensure they provide "
                        "clear, actionable guidance for the agent."
                    ),
                    reasoning=(
                        f"Failed to parse LLM refinement response. "
                        f"{len(failed_expectations)} expectations failed."
                    ),
                    addresses_failures=tuple(
                        f["expectation"] for f in failed_expectations[:3]
                    ),  # First 3
                )
            ],
            summary=(
                f"Analysis failed (JSON parse error). "
                f"{len(failed_expectations)} expectations failed."
            ),
            failures_analyzed=len(failed_expectations),
            pass_rate_before=grading_result.pass_rate,
        )

    # Extract suggestions from parsed JSON
    suggestions: list[RefinementSuggestion] = []
    for sug_data in data.get("suggestions", []):
        suggestions.append(
            RefinementSuggestion(
                section=sug_data.get("section", "Unknown"),
                current_text=sug_data.get("current_text", ""),
                suggested_text=sug_data.get("suggested_text", ""),
                reasoning=sug_data.get("reasoning", ""),
                addresses_failures=tuple(sug_data.get("addresses_failures", [])),
            )
        )

    summary = data.get("summary", f"{len(failed_expectations)} expectations failed.")

    return RefinementResult(
        skill_name=skill.metadata.name,
        suggestions=suggestions,
        summary=summary,
        failures_analyzed=len(failed_expectations),
        pass_rate_before=grading_result.pass_rate,
    )


__all__ = ["RefinementSuggestion", "RefinementResult", "analyze_skill_failures"]
