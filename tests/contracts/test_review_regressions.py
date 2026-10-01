"""Regression contracts for the whole-repository review; no model calls."""

from __future__ import annotations

import base64
import json
import shlex
import sys
from inspect import isawaitable
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from copilot.generated.session_events import SessionEvent
from copilot.tools import ToolInvocation

from pytest_skill_engineering.copilot.config import snapshot_session_configuration
from pytest_skill_engineering.copilot.contracts import CopilotEvalConfig, SubagentInvocation
from pytest_skill_engineering.copilot.eval import CopilotEval
from pytest_skill_engineering.copilot.events import EventMapper
from pytest_skill_engineering.copilot.fixtures import _convert_to_aitest
from pytest_skill_engineering.copilot.personas import (
    _inject_skill_reference_tools,
    _make_subagent_dispatch_tool,
)
from pytest_skill_engineering.copilot.result import CopilotResult
from pytest_skill_engineering.core.evals import load_custom_agent, load_custom_agents
from pytest_skill_engineering.core.result import ToolCall, Turn, UsageInfo
from pytest_skill_engineering.core.serialization import serialize_dataclass
from pytest_skill_engineering.execution.servers import CLIServer, CLIServerProcess
from pytest_skill_engineering.reporting import build_suite_report, generate_json, load_suite_report
from pytest_skill_engineering.reporting.collector import TestReport as CaseReport


def test_agent_settings_are_shared_across_loaders(tmp_path: Path) -> None:
    definition = (
        "---\nname: declared-name\ndescription: Specialist\nmodel: child-model\n"
        "reasoning_effort: high\ntools: []\ninfer: false\nskills: [specialist]\n"
        "mcp-servers:\n  helper:\n    command: helper\n    args: []\n---\nDo the task."
    )
    plugin = tmp_path / "plugin"
    (plugin / "agents").mkdir(parents=True)
    (plugin / "plugin.json").write_text('{"name":"review-plugin"}', encoding="utf-8")
    agent_file = plugin / "agents" / "filename.agent.md"
    agent_file.write_text(definition, encoding="utf-8")
    expected = load_custom_agent(agent_file)
    assert expected["name"] == "declared-name"
    assert expected["tools"] == []
    assert expected["mcp_servers"]["helper"]["command"] == "helper"
    assert CopilotEval.from_plugin(plugin).custom_agents == [expected]
    for folder, factory in (
        (".github", CopilotEval.from_copilot_config),
        (".claude", CopilotEval.from_claude_config),
    ):
        directory = tmp_path / folder / "agents"
        directory.mkdir(parents=True)
        (directory / "filename.agent.md").write_text(definition, encoding="utf-8")
        assert factory(tmp_path).custom_agents == [expected]
    assert load_custom_agents(agent_file.parent, include={"declared-name"}) == [expected]
    (agent_file.parent / "another.agent.md").write_text(definition, encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate custom agent name"):
        load_custom_agents(agent_file.parent)
    with pytest.raises(ValueError, match="Duplicate custom agent name"):
        CopilotEval.from_plugin(plugin)


def _skill(parent: Path, name: str, reference: str = "commands/guide.md") -> Path:
    directory = parent / name
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Fixture\n---\nInstructions.",
        encoding="utf-8",
    )
    path = directory / "references" / reference
    path.parent.mkdir(parents=True)
    path.write_text(f"Instructions for {name}", encoding="utf-8")
    return directory


@pytest.mark.parametrize("parent_directory", [False, True])
async def test_disabled_and_nested_references(tmp_path: Path, parent_directory: bool) -> None:
    enabled = _skill(tmp_path, "enabled")
    disabled = _skill(tmp_path, "disabled", "secret.md")
    agent = CopilotEval(
        skill_directories=[str(tmp_path)] if parent_directory else [str(enabled), str(disabled)],
        extra_config={"disabled_skills": ["disabled"]},
    )
    config = agent.build_session_config()
    _inject_skill_reference_tools(agent, config)
    tools = {tool.name: tool for tool in config["tools"]}
    enum = tools["read_skill_reference"].parameters["properties"]["filename"]["enum"]
    assert enum == ["commands/guide.md"]
    assert "secret.md" not in config["system_message"]["content"]
    result = await tools["read_skill_reference"].handler(
        ToolInvocation(tool_name="read_skill_reference", arguments={"filename": enum[0]})
    )
    assert result.text_result_for_llm == "Instructions for enabled"
    rejected = await tools["read_skill_reference"].handler(
        ToolInvocation(tool_name="read_skill_reference", arguments={"filename": "secret.md"})
    )
    assert rejected.result_type == "failure"
    config["disabled_skills"] = ["enabled", "disabled"]
    config.pop("tools")
    config.pop("system_message")
    _inject_skill_reference_tools(agent, config)
    assert "tools" not in config
    assert "system_message" not in config


@pytest.mark.skipif(sys.platform != "win32", reason="Windows direct argument parsing")
@pytest.mark.parametrize("arguments", [r"C:\work\input.txt", r'"C:\work folder\input.txt" ""'])
async def test_direct_cli_windows_paths(arguments: str) -> None:
    server = CLIServerProcess(
        CLIServer(
            tool_prefix="echo",
            command=f"{shlex.quote(sys.executable)} -c 'import sys,json; print(json.dumps(sys.argv[1:]))'",
            shell="none",
        )
    )
    result: dict[str, Any] = json.loads(await server.call_tool("echo_execute", {"args": arguments}))
    assert result["exit_code"] == 0, result
    assert json.loads(result["stdout"]) == (
        [r"C:\work\input.txt"] if arguments.startswith("C:") else [r"C:\work folder\input.txt", ""]
    )


def _event(kind: str, **data: Any) -> SessionEvent:
    return SessionEvent.from_dict(
        {"id": str(uuid4()), "type": kind, "timestamp": "2026-10-01T08:00:00Z", "data": data}
    )


@pytest.mark.parametrize("field", ["contents", "binaryResultsForLlm"])
def test_sdk_images_are_captured_and_round_trip(tmp_path: Path, field: str) -> None:
    mapper = EventMapper()
    mapper.handle(
        _event("tool.execution_start", toolCallId="image-1", toolName="image", arguments={})
    )
    payloads = [b"first-image", b"", b"third-image"]
    completion = _event(
        "tool.execution_complete",
        toolCallId="image-1",
        success=True,
        result={
            "content": "",
            field: [
                {"type": "image", "data": base64.b64encode(data).decode(), "mimeType": "image/png"}
                for data in payloads
            ],
        },
    )
    mapper.handle(completion)
    mapper.handle(completion)
    result = mapper.build()
    call = result.all_tool_calls[0]
    assert result.evidence_complete
    assert call.image_content == payloads[0]
    assert [image.data for image in call.additional_images] == payloads[1:]
    converted = _convert_to_aitest(CopilotEval(), result)
    assert converted is not None
    suite = build_suite_report([CaseReport("image-test", "passed", 1, converted[0])], "Images")
    output = tmp_path / "images.json"
    generate_json(suite, output)
    restored = load_suite_report(output)
    assert serialize_dataclass(restored) == serialize_dataclass(suite)
    captured = restored.tests[0].eval_result
    assert captured is not None
    assert [image.data for image in captured.tool_images_for("image")] == payloads


def test_invalid_image_is_an_explicit_capture_error() -> None:
    mapper = EventMapper()
    mapper.handle(
        _event("tool.execution_start", toolCallId="image-1", toolName="image", arguments={})
    )
    mapper.handle(
        _event(
            "tool.execution_complete",
            toolCallId="image-1",
            success=True,
            result={
                "content": "",
                "contents": [{"type": "image", "data": "!", "mimeType": "image/png"}],
            },
        )
    )
    result = mapper.build()
    assert not result.evidence_complete
    assert not result.success
    assert any("invalid image" in error for error in result.capture_errors)


@pytest.mark.parametrize("successful", [True, False])
async def test_child_evidence_is_separate_and_counted_once(
    tmp_path: Path, successful: bool
) -> None:
    child_agent = CopilotEval(name="child", model="child-model")
    grandchild = CopilotResult(
        agent=CopilotEval(name="grandchild", model="grandchild-model"),
        usage=[UsageInfo("grandchild-model", 7, 3)],
        total_premium_requests=1,
    )
    child = CopilotResult(
        agent=child_agent,
        success=successful,
        error=None if successful else "child failed",
        capture_errors=[] if successful else ["incomplete child"],
        usage=[UsageInfo("child-model", 100, 20)],
        turns=[
            Turn(
                "assistant",
                "child output",
                [
                    ToolCall(
                        "write",
                        {},
                        result="child receipt",
                        call_id="write-1",
                        success=True,
                        completion_received=True,
                    ),
                ],
            )
        ],
        configuration={"model": "child-model", "instructions": "child instructions"},
        subagent_invocations=[
            SubagentInvocation("grandchild-1", "grandchild", "completed", result=grandchild)
        ],
        total_premium_requests=2,
    )

    async def nested(agent: CopilotEvalConfig, prompt: str) -> CopilotResult:
        return child

    parent = CopilotEval(name="parent", model="parent-model")
    mapper = EventMapper()
    mapper.handle(_event("assistant.usage", model="parent-model", inputTokens=10, outputTokens=5))
    tool = _make_subagent_dispatch_tool(
        "runSubagent", parent, [{"name": "child", "prompt": "Child instructions"}], mapper, nested
    )
    assert tool.handler is not None
    pending = tool.handler(
        ToolInvocation(
            tool_call_id="dispatch-1",
            tool_name="runSubagent",
            arguments={"agentSlug": "child", "prompt": "Do the task"},
        )
    )
    assert isawaitable(pending)
    outcome = await pending
    result = mapper.build()
    assert outcome.result_type == ("success" if successful else "failure")
    assert result.usage[0].input_tokens == 10
    assert result.total_tokens == 145
    assert result.total_premium_requests == 2
    assert result.all_tool_calls == []
    assert result.evidence_complete is successful
    assert result.subagent_invocations[0].result is child
    converted = _convert_to_aitest(parent, result)
    assert converted is not None
    suite = build_suite_report([CaseReport("child-test", "passed", 1, converted[0])], "Children")
    output = tmp_path / "children.json"
    generate_json(suite, output)
    restored = load_suite_report(output)
    assert serialize_dataclass(restored) == serialize_dataclass(suite)
    saved = restored.tests[0].eval_result
    assert saved is not None
    assert len(saved.execution_results) == 3
    assert saved.token_usage["total"] == 145
    saved_child = saved.subagent_invocations[0].result
    assert saved_child is not None
    assert saved_child.all_tool_calls[0].result == "child receipt"
    child.usage[0].input_tokens = None
    assert result.total_input_tokens is None
    assert result.total_tokens is None


def test_prepared_settings_are_saved_not_reconstructed() -> None:
    agent = CopilotEval(
        model="configured-model",
        instructions="Original prompt",
        allowed_tools=["read"],
        extra_config={
            "model": "runtime-model",
            "available_tools": ["write"],
            "system_message": {"mode": "replace", "content": "Runtime prompt"},
        },
    )
    configuration = snapshot_session_configuration(agent, agent.build_session_config())
    result = CopilotResult(model_used="runtime-model", configuration=configuration)
    converted = _convert_to_aitest(agent, result)
    assert converted is not None
    assert converted[0].configuration["model"] == "runtime-model"
    assert converted[0].configuration["allowed_tools"] == ["write"]
    assert converted[0].effective_system_prompt == "Runtime prompt"
    configuration["allowed_tools"].append("extra")
    assert converted[0].configuration["allowed_tools"] == ["write"]


def test_unknown_model_is_null_and_unavailable_settings_remain_missing(tmp_path: Path) -> None:
    converted = _convert_to_aitest(
        CopilotEval(), CopilotResult(success=False, error="startup failed")
    )
    assert converted is not None
    assert converted[1].provider.model is None
    assert converted[0].configuration is None
    assert converted[0].effective_system_prompt is None
    suite = build_suite_report(
        [CaseReport("startup", "failed", 1, converted[0], model=None)], "Unknown"
    )
    output = tmp_path / "unknown.json"
    generate_json(suite, output)
    assert load_suite_report(output).tests[0].model is None


@pytest.mark.parametrize(
    "field",
    [
        "configuration",
        "capture_errors",
        "evidence_complete",
        "request_audit",
        "usage",
        "tool_calls_admitted",
        "subagent_invocations",
        "stop_reason",
        "turns",
    ],
)
def test_current_schema_rejects_missing_evidence(tmp_path: Path, field: str) -> None:
    converted = _convert_to_aitest(CopilotEval(), CopilotResult())
    assert converted is not None
    suite = build_suite_report([CaseReport("missing", "passed", 1, converted[0])], "Missing")
    path = tmp_path / "missing.json"
    generate_json(suite, path)
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["tests"][0]["eval_result"][field]
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match=f"missing required field '{field}'"):
        load_suite_report(path)


def test_all_usage_models_contribute_pricing_warnings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    pricing = tmp_path / "pricing.toml"
    pricing.write_text("[models.last-model]\ninput = 1\noutput = 2\n", encoding="utf-8")
    agent = CopilotEval(model="last-model")
    result = CopilotResult(
        model_used="last-model",
        usage=[UsageInfo("first-model", 100, 20), UsageInfo("last-model", 50, 10)],
    )
    converted = _convert_to_aitest(agent, result)
    assert converted is not None
    suite = build_suite_report(
        [CaseReport("pricing", "passed", 1, converted[0], model="last-model")], "Pricing"
    )
    assert suite.models_without_pricing == ["first-model"]
    pricing.write_text(
        "[models.first-model]\ninput = 3\noutput = 4\n[models.last-model]\ninput = 1\noutput = 2\n",
        encoding="utf-8",
    )
    assert build_suite_report(suite.tests, "Updated pricing").models_without_pricing == []
