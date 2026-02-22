"""Serialization helpers for dataclasses to JSON-compatible dicts."""

from __future__ import annotations

import base64
from dataclasses import asdict, is_dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pytest_skill_engineering.reporting.collector import SuiteReport


def serialize_dataclass(obj: Any) -> Any:
    """Convert dataclass to dict recursively, handling special types.

    Excludes private fields (prefixed with _) from serialization.
    Encodes bytes fields as base64 strings.
    """
    if is_dataclass(obj) and not isinstance(obj, type):
        data = asdict(obj)  # type: ignore[arg-type]
        result = {}
        for k, v in data.items():
            if k.startswith("_"):
                continue
            if isinstance(v, bytes):
                result[k] = base64.b64encode(v).decode("ascii")
            else:
                result[k] = serialize_dataclass(v)
        return result
    elif isinstance(obj, (list, tuple)):
        return [serialize_dataclass(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: serialize_dataclass(v) for k, v in obj.items()}
    elif isinstance(obj, bytes):
        return base64.b64encode(obj).decode("ascii")
    else:
        # For enums, strings, numbers, etc.
        return obj


def deserialize_suite_report(data: dict[str, Any]) -> SuiteReport:
    """Deserialize a SuiteReport from a dict (from JSON).

    Reconstructs the full dataclass hierarchy from the serialized format.
    """
    from pytest_skill_engineering.core.result import AgentResult, ToolCall, Turn
    from pytest_skill_engineering.reporting.collector import SuiteReport, TestReport

    # Reconstruct tests
    tests = []
    for test_data in data.get("tests", []):
        # Reconstruct agent result if present
        agent_result = None
        if test_data.get("agent_result"):
            ar_data = test_data["agent_result"]

            # Reconstruct turns
            turns = []
            for turn_data in ar_data.get("turns", []):
                # Reconstruct tool calls
                tool_calls = []
                for tc_data in turn_data.get("tool_calls", []):
                    # Decode base64 image content if present
                    image_content = None
                    if tc_data.get("image_content"):
                        image_content = base64.b64decode(tc_data["image_content"])

                    tool_calls.append(
                        ToolCall(
                            name=tc_data["name"],
                            arguments=tc_data.get("arguments", {}),
                            result=tc_data.get("result"),
                            error=tc_data.get("error"),
                            duration_ms=tc_data.get("duration_ms"),
                            image_content=image_content,
                            image_media_type=tc_data.get("image_media_type"),
                        )
                    )

                turns.append(
                    Turn(
                        role=turn_data["role"],
                        content=turn_data["content"],
                        tool_calls=tool_calls,
                    )
                )

            # Reconstruct clarification stats if present
            from pytest_skill_engineering.core.result import ClarificationStats

            clarification_stats = None
            if ar_data.get("clarification_stats") is not None:
                cs_data = ar_data["clarification_stats"]
                clarification_stats = ClarificationStats(
                    count=cs_data.get("count", 0),
                    turn_indices=cs_data.get("turn_indices", []),
                    examples=cs_data.get("examples", []),
                )

            # Reconstruct assertions if present
            from pytest_skill_engineering.core.result import Assertion

            assertions = []
            for a_data in ar_data.get("assertions", []):
                assertions.append(
                    Assertion(
                        type=a_data["type"],
                        passed=a_data["passed"],
                        message=a_data["message"],
                        details=a_data.get("details"),
                    )
                )

            # Reconstruct available tools if present
            from pytest_skill_engineering.core.result import SkillInfo, ToolInfo

            available_tools = []
            for t_data in ar_data.get("available_tools", []):
                available_tools.append(
                    ToolInfo(
                        name=t_data["name"],
                        description=t_data["description"],
                        input_schema=t_data.get("input_schema", {}),
                        server_name=t_data.get("server_name", ""),
                    )
                )

            # Reconstruct skill info if present
            skill_info = None
            si_data = ar_data.get("skill_info")
            if si_data:
                skill_info = SkillInfo(
                    name=si_data["name"],
                    description=si_data["description"],
                    instruction_content=si_data.get("instruction_content", ""),
                    reference_names=si_data.get("reference_names", []),
                )

            # Reconstruct agent result
            agent_result = AgentResult(
                turns=turns,
                success=ar_data.get("success", False),
                error=ar_data.get("error"),
                duration_ms=ar_data.get("duration_ms", 0.0),
                token_usage=ar_data.get("token_usage", {}),
                cost_usd=ar_data.get("cost_usd", 0.0),
                session_context_count=ar_data.get("session_context_count", 0),
                clarification_stats=clarification_stats,
                assertions=assertions,
                available_tools=available_tools,
                skill_info=skill_info,
                effective_system_prompt=ar_data.get("effective_system_prompt", ""),
            )

        # Read identity from typed fields
        agent_id = test_data.get("agent_id", "")
        agent_name = test_data.get("agent_name", "")
        model = test_data.get("model", "")
        system_prompt_name = test_data.get("system_prompt_name")
        skill_name = test_data.get("skill_name")

        # Reconstruct test report
        test_report = TestReport(
            name=test_data["name"],
            outcome=test_data["outcome"],
            duration_ms=test_data["duration_ms"],
            agent_result=agent_result,
            error=test_data.get("error"),
            assertions=test_data.get("assertions", []),
            docstring=test_data.get("docstring"),
            class_docstring=test_data.get("class_docstring"),
            agent_id=agent_id,
            agent_name=agent_name,
            model=model,
            system_prompt_name=system_prompt_name,
            skill_name=skill_name,
            iteration=test_data.get("iteration"),
        )
        tests.append(test_report)

    # Reconstruct suite report
    return SuiteReport(
        name=data["name"],
        timestamp=data["timestamp"],
        duration_ms=data["duration_ms"],
        tests=tests,
        passed=data.get("passed", 0),
        failed=data.get("failed", 0),
        skipped=data.get("skipped", 0),
        suite_docstring=data.get("suite_docstring"),
    )
