"""Deterministic SDK-event to report checks; no model or desktop execution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from copilot.generated.session_events import SessionEvent

from pytest_skill_engineering.copilot.eval import CopilotEval
from pytest_skill_engineering.copilot.events import EventMapper
from pytest_skill_engineering.copilot.fixtures import _convert_to_aitest
from pytest_skill_engineering.core.serialization import deserialize_suite_report
from pytest_skill_engineering.reporting.collector import TestReport as Report
from pytest_skill_engineering.reporting.collector import build_suite_report
from pytest_skill_engineering.reporting.generator import generate_html, generate_json, generate_md
from pytest_skill_engineering.reporting.insights import InsightsResult, _build_analysis_input


def event(kind: str, **data: Any) -> SessionEvent:
    return SessionEvent.from_dict(
        {
            "id": str(uuid4()),
            "timestamp": "2026-09-13T08:00:00Z",
            "type": kind,
            "data": data,
        }
    )


def request() -> SessionEvent:
    return event(
        "assistant.message",
        content="",
        messageId="message-1",
        toolRequests=[
            {"toolCallId": "call-1", "name": "powershell", "arguments": {"command": "app --help"}}
        ],
    )


def start() -> SessionEvent:
    return event(
        "tool.execution_start",
        toolCallId="call-1",
        toolName="powershell",
        arguments={"command": "app --help"},
    )


def complete(content: str = "Usage: app") -> SessionEvent:
    return event(
        "tool.execution_complete",
        toolCallId="call-1",
        success=True,
        result={"content": content},
    )


@pytest.mark.parametrize(
    "sequence",
    [
        [request(), start(), complete()],
        [request(), event("assistant.turn_end", turnId="turn-1"), start(), complete()],
        [start(), request(), complete()],
        [start(), start(), complete(), complete()],
        [start(), complete(), event("assistant.turn_end", turnId="turn-1"), request()],
    ],
)
def test_call_identity_survives_event_order_and_duplicates(sequence: list[SessionEvent]) -> None:
    mapper = EventMapper()
    for item in sequence:
        mapper.handle(item)
    result = mapper.build()
    assert len(result.all_tool_calls) == 1
    call = result.all_tool_calls[0]
    assert call.result == "Usage: app"
    assert call.call_id == "call-1"
    assert call.completion_received is True
    assert call.success is True
    assert result.evidence_complete
    assert len([turn for turn in result.turns if turn.role == "tool"]) == 1


@pytest.mark.parametrize("content", ["", "Usage: app", "<script>alert('x')</script>"])
def test_capture_survives_conversion_json_reload_and_html(tmp_path: Path, content: str) -> None:
    mapper = EventMapper()
    for item in [request(), start(), complete(content)]:
        mapper.handle(item)
    result = mapper.build()
    converted = _convert_to_aitest(CopilotEval(name="CLI", model="test-model"), result)
    assert converted is not None
    suite = build_suite_report(
        [
            Report(
                name="test_usage",
                outcome="passed",
                duration_ms=1,
                eval_result=converted[0],
                agent_id="CLI",
                eval_name="CLI",
                model="test-model",
            )
        ],
        name="Usage evidence",
    )
    output = tmp_path / "report.json"
    generate_json(suite, output)
    saved = json.loads(output.read_text(encoding="utf-8"))
    loaded = deserialize_suite_report(saved)
    assert loaded.tests[0].eval_result is not None
    call = loaded.tests[0].eval_result.all_tool_calls[0]
    assert call.result == content
    assert call.call_id == "call-1"
    assert call.completion_received is True
    assert call.success is True
    html = tmp_path / "report.html"
    generate_html(
        loaded,
        html,
        insights=InsightsResult(markdown_summary="No model analysis requested.", model="none"),
    )
    rendered = html.read_text(encoding="utf-8")
    assert "call-1" in rendered
    assert "app --help" in rendered
    assert "<script>alert('x')</script>" not in rendered
    assert (
        "Empty output"
        if content == ""
        else "Usage: app"
        if content.startswith("Usage")
        else "&lt;script&gt;"
    ) in rendered


@pytest.mark.parametrize("terminal", [None, event("abort", reason="user_initiated")])
def test_unfinished_call_is_not_a_success(terminal: SessionEvent | None) -> None:
    mapper = EventMapper()
    mapper.handle(start())
    if terminal is not None:
        mapper.handle(terminal)
    result = mapper.build()
    assert not result.success
    assert not result.evidence_complete
    assert result.all_tool_calls[0].completion_received is False
    assert result.all_tool_calls[0].result is None
    assert result.error is not None and "call-1" in result.error


def test_missing_output_is_not_empty_output() -> None:
    mapper = EventMapper()
    mapper.handle(start())
    mapper.handle(event("tool.execution_complete", toolCallId="call-1", success=True))
    result = mapper.build()
    assert not result.evidence_complete
    assert result.all_tool_calls[0].completion_received is True
    assert result.all_tool_calls[0].result is None


def test_completion_before_start_is_correlated() -> None:
    mapper = EventMapper()
    mapper.handle(complete())
    mapper.handle(start())
    result = mapper.build()
    assert result.success
    assert result.evidence_complete
    assert result.all_tool_calls[0].result == "Usage: app"


def test_conflicting_completion_is_visible() -> None:
    mapper = EventMapper()
    for item in [start(), complete("first"), complete("different")]:
        mapper.handle(item)
    result = mapper.build()
    assert not result.success
    assert not result.evidence_complete
    assert result.all_tool_calls[0].result == "first"
    assert result.error is not None and "call-1" in result.error


def test_tool_error_without_output_is_preserved() -> None:
    mapper = EventMapper()
    mapper.handle(request())
    mapper.handle(start())
    mapper.handle(
        event(
            "tool.execution_complete",
            toolCallId="call-1",
            success=False,
            error={"message": "invalid argument"},
        )
    )
    result = mapper.build()
    call = result.all_tool_calls[0]
    assert call.error == "invalid argument"
    assert call.success is False
    assert call.completion_received is True
    assert result.evidence_complete


def test_orphan_completion_is_not_silently_accepted() -> None:
    mapper = EventMapper()
    mapper.handle(complete())
    result = mapper.build()
    assert not result.success
    assert not result.evidence_complete
    assert result.error is not None and "call-1" in result.error


def test_failed_session_keeps_incomplete_trace_in_html(tmp_path: Path) -> None:
    mapper = EventMapper()
    mapper.handle(start())
    converted = _convert_to_aitest(CopilotEval(name="CLI", model="test-model"), mapper.build())
    assert converted is not None
    suite = build_suite_report(
        [
            Report(
                name="test_usage",
                outcome="failed",
                duration_ms=1,
                eval_result=converted[0],
                agent_id="CLI",
                eval_name="CLI",
                model="test-model",
            )
        ],
        name="Usage evidence",
    )
    output = tmp_path / "report.html"
    generate_html(
        suite, output, insights=InsightsResult(markdown_summary="Not requested.", model="none")
    )
    rendered = output.read_text(encoding="utf-8")
    assert "powershell" in rendered
    assert "Incomplete evidence" in rendered
    assert "call-1" in rendered


def test_multiple_runs_and_verification_properties_reach_native_report(
    pytester: pytest.Pytester,
) -> None:
    pytester.makepyfile(
        """
        import pytest
        from pytest_skill_engineering.copilot.eval import CopilotEval
        from pytest_skill_engineering.copilot.fixtures import stash_on_item
        from pytest_skill_engineering.copilot.result import CopilotResult

        def test_comparison(request, record_property):
            record_property("verification", {"status": "failed", "artifact": "expected.txt"})
            for name in ("baseline", "treatment"):
                stash_on_item(request.node,
                              CopilotEval(name=name, model="test-model", instructions=name),
                              CopilotResult(success=True))
            assert False, "Independent file check failed"
        """
    )
    run = pytester.runpytest_subprocess("-o", "addopts=", "--aitest-json=report.json", "-q")
    run.assert_outcomes(failed=1)
    saved = json.loads((pytester.path / "report.json").read_text(encoding="utf-8"))
    assert len(saved["tests"]) == 2
    assert {test["eval_name"] for test in saved["tests"]} == {"baseline", "treatment"}
    for test in saved["tests"]:
        assert test["outcome"] == "failed"
        assert test["eval_result"]["success"] is True
        assert test["properties"] == [
            ["verification", {"status": "failed", "artifact": "expected.txt"}]
        ]
        assert test["eval_result"]["configuration"]["instructions"] == test["eval_name"]
    restored = deserialize_suite_report(saved)
    assert restored.tests[0].properties == [
        ("verification", {"status": "failed", "artifact": "expected.txt"})
    ]
    output = pytester.path / "report.html"
    generate_html(
        restored, output, insights=InsightsResult(markdown_summary="Not requested.", model="none")
    )
    assert "expected.txt" in output.read_text(encoding="utf-8")


def test_analysis_references_and_markdown_preserve_incomplete_evidence(tmp_path: Path) -> None:
    tests = []
    for name, finish in [("baseline", True), ("treatment", False)]:
        mapper = EventMapper()
        mapper.handle(start())
        if finish:
            mapper.handle(complete(""))
        converted = _convert_to_aitest(CopilotEval(name=name, model="test-model"), mapper.build())
        assert converted is not None
        tests.append(
            Report(
                name="test_usage",
                outcome="passed",
                duration_ms=1,
                eval_result=converted[0],
                agent_id=name,
                eval_name=name,
                model="test-model",
                properties=[("verification", {"status": "not verified"})],
            )
        )
    suite = build_suite_report(tests, name="Evidence")
    analysis = _build_analysis_input(suite, [], [], {}, compact=False)
    assert "[test-1/call:call-1]" in analysis
    assert "[test-2/call:call-1]" in analysis
    assert "completion_received=False" in analysis
    assert "not verified" in analysis
    compact = _build_analysis_input(suite, [], [], {}, compact=True)
    assert "[test-2/call:call-1]" in compact
    output = tmp_path / "report.md"
    generate_md(
        suite, output, insights=InsightsResult(markdown_summary="Not requested.", model="none")
    )
    markdown = output.read_text(encoding="utf-8")
    assert "Incomplete evidence" in markdown
    assert "Empty output" in markdown
    assert "call-1" in markdown
    assert "not verified" in markdown


def test_configuration_is_a_snapshot_without_connection_secrets() -> None:
    tools = ["read"]
    agent = CopilotEval(
        name="documents",
        model="test-model",
        allowed_tools=tools,
        mcp_servers={
            "documents": {
                "type": "local",
                "command": "document-server",
                "args": ["synthetic-secret"],
                "env": {"TOKEN": "synthetic-secret"},
                "tools": tools,
            }
        },
    )
    converted = _convert_to_aitest(agent, EventMapper().build())
    assert converted is not None
    tools.append("write")
    configuration = converted[0].configuration
    assert configuration["allowed_tools"] == ["read"]
    assert configuration["mcp_servers"]["documents"]["tools"] == ["read"]
    assert "synthetic-secret" not in json.dumps(configuration)


def test_mcp_call_without_arguments_keeps_its_result() -> None:
    mapper = EventMapper()
    mapper.handle(
        event(
            "assistant.message",
            content="",
            messageId="message-1",
            toolRequests=[{"toolCallId": "call-1", "name": "documents_list"}],
        )
    )
    mapper.handle(
        event(
            "tool.execution_start",
            toolCallId="call-1",
            toolName="documents_list",
            mcpServerName="documents",
            mcpToolName="list",
        )
    )
    mapper.handle(complete('{"documents": []}'))
    result = mapper.build()
    assert result.success
    assert result.evidence_complete
    assert result.all_tool_calls[0].arguments == {}
    assert result.all_tool_calls[0].result == '{"documents": []}'


def test_ab_configs_preserve_runtime_names(tmp_path: Path) -> None:
    from pytest_skill_engineering.copilot.fixtures import _prepare_ab_configs

    baseline = CopilotEval(name="helper", model="test-model", instructions="Baseline")
    treatment = CopilotEval(name="helper", model="test-model", instructions="Treatment")
    prepared = _prepare_ab_configs(baseline, treatment, tmp_path)
    assert [config.name for config in prepared] == ["helper", "helper"]
    assert [config.instructions for config in prepared] == ["Baseline", "Treatment"]
    assert prepared[0].working_directory == str(tmp_path / "baseline")
    assert prepared[1].working_directory == str(tmp_path / "treatment")
    assert (tmp_path / "baseline").is_dir() and (tmp_path / "treatment").is_dir()
    assert baseline.working_directory is None and treatment.working_directory is None


def test_ab_labels_apply_only_to_saved_reports(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        from pytest_skill_engineering.copilot.eval import CopilotEval
        from pytest_skill_engineering.copilot.fixtures import stash_on_item
        from pytest_skill_engineering.copilot.result import CopilotResult

        def test_comparison(request):
            agent = CopilotEval(name="helper", model="test-model")
            for role in ("baseline", "treatment"):
                result = CopilotResult(agent=agent)
                stash_on_item(request.node, agent, result, comparison_role=role)
                assert agent.name == "helper"
                assert result.agent.name == "helper"
        """
    )
    run = pytester.runpytest_subprocess("-o", "addopts=", "--aitest-json=report.json", "-q")
    run.assert_outcomes(passed=1)
    saved = json.loads((pytester.path / "report.json").read_text(encoding="utf-8"))
    assert len(saved["tests"]) == 2
    for test, role in zip(saved["tests"], ("baseline", "treatment"), strict=True):
        assert test["eval_name"] == f"helper ({role})"
        assert test["agent_id"] == f"helper ({role})"
        assert test["eval_result"]["configuration"]["name"] == "helper"
        assert test["eval_result"]["configuration"]["comparison_role"] == role


def test_tool_repr_preserves_existing_status_format() -> None:
    from pytest_skill_engineering.core.result import ToolCall

    success = ToolCall(name="read_file", arguments={}, result="ok")
    error = ToolCall(name="read_file", arguments={}, error="fail")
    assert repr(success) == "ToolCall(read_file, ok)"
    assert repr(error) == "ToolCall(read_file, error)"
    assert not success.evidence_complete
    assert not error.evidence_complete


def test_diagram_retains_output_when_completion_status_is_unknown() -> None:
    from pytest_skill_engineering.core.result import EvalResult, ToolCall, Turn
    from pytest_skill_engineering.reporting.generator import generate_mermaid_sequence

    result = EvalResult(
        turns=[
            Turn(
                role="assistant",
                content="",
                tool_calls=[ToolCall(name="read_file", arguments={}, result="file contents here")],
            )
        ],
        success=True,
    )
    diagram = generate_mermaid_sequence(result)
    assert 'Tools-->>Eval: "file contents here"' in diagram
    assert "Incomplete evidence" in diagram
