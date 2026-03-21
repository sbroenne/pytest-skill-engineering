"""Export eval results in skill-creator compatible grading.json format.

This enables our CI/CD results to be consumed by skill-creator's
eval-viewer and analysis agents.

Example:
    result = await eval_run(agent, case.prompt)
    passed = [llm_assert(result.final_response, e) for e in case.expectations]
    grading = export_grading(result, case.expectations, passed)
    Path("grading.json").write_text(json.dumps(grading, indent=2))
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pytest_skill_engineering.core.result import EvalResult


def export_grading(
    result: EvalResult,
    expectations: Sequence[str],
    expectation_results: Sequence[bool],
    evidence: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Export eval result as skill-creator compatible grading.json.

    Args:
        result: The eval result from a test run
        expectations: The assertion texts that were checked
        expectation_results: Whether each expectation passed
        evidence: Optional evidence strings for each expectation

    Returns:
        Dict matching skill-creator's grading.json schema

    Raises:
        ValueError: If expectations and results have different lengths
    """
    if len(expectations) != len(expectation_results):
        raise ValueError(
            f"expectations ({len(expectations)}) and "
            f"expectation_results ({len(expectation_results)}) must have the same length"
        )
    if evidence is not None and len(evidence) != len(expectations):
        raise ValueError(
            f"evidence ({len(evidence)}) must match "
            f"expectations ({len(expectations)}) length"
        )

    expectation_entries: list[dict[str, Any]] = []
    for i, (text, passed) in enumerate(zip(expectations, expectation_results, strict=True)):
        entry: dict[str, Any] = {
            "text": text,
            "passed": passed,
        }
        if evidence is not None:
            entry["evidence"] = evidence[i]
        expectation_entries.append(entry)

    passed_count = sum(1 for r in expectation_results if r)
    total = len(expectation_results)
    failed_count = total - passed_count

    grading: dict[str, Any] = {
        "expectations": expectation_entries,
        "summary": {
            "passed": passed_count,
            "failed": failed_count,
            "total": total,
            "pass_rate": round(passed_count / total, 2) if total > 0 else 0.0,
        },
        "execution_metrics": {
            "tool_calls": len(result.all_tool_calls),
            "turns": len(result.turns),
            "duration_ms": result.duration_ms,
            "success": result.success,
        },
    }

    return grading
