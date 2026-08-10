"""Serialization helpers for dataclasses to JSON-compatible dicts."""

from __future__ import annotations

import base64
from dataclasses import fields, is_dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pytest_skill_engineering.reporting.collector import SuiteReport


def _require_key(data: dict[str, Any], key: str, *, context: str) -> Any:
    """Read a required key or raise a schema-alignment error."""
    if key not in data:
        msg = f"{context} is missing required field {key!r}"
        raise ValueError(msg)
    return data[key]


def serialize_dataclass(obj: Any) -> Any:
    """Convert dataclass to dict recursively, handling special types.

    Excludes private fields (prefixed with _) from serialization.
    Encodes bytes fields as base64 strings.

    Uses manual field iteration instead of ``dataclasses.asdict()`` to avoid
    ``copy.deepcopy`` on large private fields (e.g. ``_messages`` containing
    SDK session payloads).
    """
    if is_dataclass(obj) and not isinstance(obj, type):
        result = {}
        for f in fields(obj):
            if f.name.startswith("_"):
                continue
            v = getattr(obj, f.name)
            if isinstance(v, bytes):
                result[f.name] = base64.b64encode(v).decode("ascii")
            else:
                result[f.name] = serialize_dataclass(v)
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
    from pytest_skill_engineering.core.result import EvalResult, ToolCall, Turn
    from pytest_skill_engineering.reporting.collector import SuiteReport, TestReport

    # Reconstruct tests
    raw_tests = _require_key(data, "tests", context="SuiteReport")
    if not isinstance(raw_tests, list):
        raise ValueError("SuiteReport field 'tests' must be a list")

    tests = []
    for test_data in raw_tests:
        if not isinstance(test_data, dict):
            raise ValueError("SuiteReport tests must contain objects")

        eval_result = None
        raw_eval_result = _require_key(
            test_data,
            "eval_result",
            context=f"TestReport {test_data!r}",
        )
        if raw_eval_result is not None:
            if not isinstance(raw_eval_result, dict):
                raise ValueError("TestReport field 'eval_result' must be an object or null")
            ar_data = raw_eval_result

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
                            name=_require_key(tc_data, "name", context="ToolCall"),
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
                        role=_require_key(turn_data, "role", context="Turn"),
                        content=_require_key(turn_data, "content", context="Turn"),
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
            from pytest_skill_engineering.core.result import (
                MCPPrompt,
                MCPPromptArgument,
                SkillInfo,
                ToolInfo,
            )

            available_tools = []
            for t_data in ar_data.get("available_tools", []):
                available_tools.append(
                    ToolInfo(
                        name=_require_key(t_data, "name", context="ToolInfo"),
                        description=_require_key(t_data, "description", context="ToolInfo"),
                        input_schema=_require_key(t_data, "input_schema", context="ToolInfo"),
                        server_name=_require_key(t_data, "server_name", context="ToolInfo"),
                    )
                )

            # Reconstruct MCP prompts if present
            mcp_prompts = []
            for p_data in ar_data.get("mcp_prompts", []):
                args = [
                    MCPPromptArgument(
                        name=a["name"],
                        description=a.get("description", ""),
                        required=a.get("required", False),
                    )
                    for a in p_data.get("arguments", [])
                ]
                mcp_prompts.append(
                    MCPPrompt(
                        name=_require_key(p_data, "name", context="MCPPrompt"),
                        description=p_data.get("description", ""),
                        arguments=args,
                    )
                )

            # Reconstruct skill info if present
            skill_info = None
            si_data = ar_data.get("skill_info")
            if si_data:
                skill_info = SkillInfo(
                    name=_require_key(si_data, "name", context="SkillInfo"),
                    description=_require_key(si_data, "description", context="SkillInfo"),
                    instruction_content=si_data.get("instruction_content", ""),
                    reference_names=si_data.get("reference_names", []),
                )

            # Reconstruct custom agent info if present
            from pytest_skill_engineering.core.result import CustomAgentInfo, InstructionFileInfo

            custom_agent_info = None
            ca_data = ar_data.get("custom_agent_info")
            if ca_data:
                custom_agent_info = CustomAgentInfo(
                    name=_require_key(ca_data, "name", context="CustomAgentInfo"),
                    description=ca_data.get("description", ""),
                    file_path=ca_data.get("file_path", ""),
                )

            # Reconstruct instruction files if present
            instruction_files = []
            for if_data in ar_data.get("instruction_files", []):
                instruction_files.append(
                    InstructionFileInfo(
                        name=_require_key(if_data, "name", context="InstructionFileInfo"),
                        file_path=if_data.get("file_path", ""),
                        apply_to=if_data.get("apply_to", ""),
                        description=if_data.get("description", ""),
                    )
                )

            # Reconstruct agent result
            eval_result = EvalResult(
                turns=turns,
                success=_require_key(ar_data, "success", context="EvalResult"),
                error=ar_data.get("error"),
                duration_ms=_require_key(ar_data, "duration_ms", context="EvalResult"),
                token_usage=_require_key(ar_data, "token_usage", context="EvalResult"),
                cost_usd=_require_key(ar_data, "cost_usd", context="EvalResult"),
                session_context_count=_require_key(
                    ar_data, "session_context_count", context="EvalResult"
                ),
                clarification_stats=clarification_stats,
                assertions=assertions,
                available_tools=available_tools,
                skill_info=skill_info,
                effective_system_prompt=_require_key(
                    ar_data, "effective_system_prompt", context="EvalResult"
                ),
                mcp_prompts=mcp_prompts,
                prompt_name=ar_data.get("prompt_name"),
                custom_agent_info=custom_agent_info,
                premium_requests=_require_key(ar_data, "premium_requests", context="EvalResult"),
                instruction_files=instruction_files,
            )

        agent_id = _require_key(test_data, "agent_id", context="TestReport")
        eval_name = _require_key(test_data, "eval_name", context="TestReport")
        model = _require_key(test_data, "model", context="TestReport")
        system_prompt_name = test_data.get("system_prompt_name")
        skill_name = test_data.get("skill_name")

        # Reconstruct test report
        test_report = TestReport(
            name=_require_key(test_data, "name", context="TestReport"),
            outcome=_require_key(test_data, "outcome", context="TestReport"),
            duration_ms=_require_key(test_data, "duration_ms", context="TestReport"),
            eval_result=eval_result,
            error=test_data.get("error"),
            assertions=test_data.get("assertions", []),
            docstring=test_data.get("docstring"),
            class_docstring=test_data.get("class_docstring"),
            agent_id=agent_id,
            eval_name=eval_name,
            model=model,
            system_prompt_name=system_prompt_name,
            skill_name=skill_name,
            iteration=test_data.get("iteration"),
        )
        tests.append(test_report)

    # Reconstruct suite report
    return SuiteReport(
        name=_require_key(data, "name", context="SuiteReport"),
        timestamp=_require_key(data, "timestamp", context="SuiteReport"),
        duration_ms=_require_key(data, "duration_ms", context="SuiteReport"),
        tests=tests,
        passed=_require_key(data, "passed", context="SuiteReport"),
        failed=_require_key(data, "failed", context="SuiteReport"),
        skipped=_require_key(data, "skipped", context="SuiteReport"),
        suite_docstring=data.get("suite_docstring"),
    )
