"""Judge configuration and report failure checks without a model or mock."""

from __future__ import annotations

import inspect
import os
import subprocess
import sys
from pathlib import Path

import pytest
from copilot.client import CopilotClient

from pytest_skill_engineering.copilot import judge
from pytest_skill_engineering.copilot.client import create_client
from pytest_skill_engineering.core.result import EvalResult, ToolCall, Turn
from pytest_skill_engineering.core.serialization import (
    deserialize_suite_report,
    serialize_dataclass,
)
from pytest_skill_engineering.reporting.collector import TestReport as CaseReport
from pytest_skill_engineering.reporting.collector import build_suite_report
from pytest_skill_engineering.reporting.generator import generate_json
from pytest_skill_engineering.reporting.insights import InsightsResult


def test_judge_configuration_uses_supported_sdk_keys_and_no_tools() -> None:
    with judge._judge_environment("test-model") as (client_options, session_options):
        inspect.signature(CopilotClient).bind(**client_options)
        inspect.signature(create_client).bind(**client_options)
        inspect.signature(CopilotClient.create_session).bind(None, **session_options)
        assert client_options["mode"] == "empty"
        assert session_options["available_tools"] == []
        assert session_options["tools"] == []
        assert session_options["mcp_servers"] == {}
        assert session_options["custom_agents"] == []
        assert session_options["enable_config_discovery"] is False
        assert session_options["enable_file_hooks"] is False
        assert session_options["skip_custom_instructions"] is True
        assert session_options["model"] == "test-model"
        decision = session_options["on_permission_request"]({"kind": "shell"}, {})
        assert decision.to_dict()["kind"] == "reject"


def test_sdk_preserves_empty_tool_allowlist() -> None:
    from copilot._mode import _normalize_tool_filter, _require_available_tools_for_empty_mode

    tools = _normalize_tool_filter([])
    assert tools == []
    assert tools is not None
    _require_available_tools_for_empty_mode("empty", tools)
    with pytest.raises(ValueError, match="without available_tools"):
        _require_available_tools_for_empty_mode("empty", None)


@pytest.mark.parametrize("kind", ["shell", "read", "write", "mcp", "url", "unknown"])
def test_judge_denies_every_permission_kind(kind: str) -> None:
    decision = judge._deny_all_permissions({"kind": kind}, {})
    assert decision.to_dict()["kind"] == "reject"


def test_judge_working_and_config_directories_are_temporary() -> None:
    with judge._judge_environment(None) as (client_options, session_options):
        working = Path(client_options["working_directory"])
        storage = Path(client_options["base_directory"])
        assert working.is_dir() and storage.is_dir()
        assert working != Path.cwd()
        assert not working.is_relative_to(Path.cwd())
        assert session_options["working_directory"] == str(working)
        assert session_options["config_directory"] == str(storage)
        assert list(working.iterdir()) == []
        assert list(storage.iterdir()) == []
        assert "model" not in session_options
    assert not working.exists()
    assert not storage.exists()


def test_recorded_tool_images_survive_report_serialization() -> None:
    image = b"recorded-image-bytes"
    call = ToolCall(
        name="screenshot",
        arguments={},
        call_id="image-call",
        image_content=image,
        image_media_type="image/png",
        completion_received=True,
        success=True,
    )
    result = EvalResult(turns=[Turn(role="assistant", content="", tool_calls=[call])], success=True)
    report = build_suite_report(
        [CaseReport(name="image", outcome="passed", duration_ms=1, eval_result=result)],
        name="Tool image evidence",
    )
    restored = deserialize_suite_report(serialize_dataclass(report)).tests[0].eval_result
    assert restored is not None
    assert restored.tool_images_for("screenshot")[0].data == image
    assert restored.all_tool_calls[0].evidence_complete


def test_shared_client_preserves_judge_empty_mode_without_starting_runtime() -> None:
    with judge._judge_environment("test-model") as (client_options, _):
        client = create_client(**client_options)
        assert client._options.mode == "empty"
        assert client._options.working_directory == client_options["working_directory"]
        assert client._options.base_directory == client_options["base_directory"]


def test_requested_summary_failure_does_not_reuse_old_insights(tmp_path: Path) -> None:
    source = tmp_path / "results.json"
    output = tmp_path / "report.html"
    generate_json(
        build_suite_report([], name="Evidence"),
        source,
        insights=InsightsResult(markdown_summary="Old analysis must not be reused.", model="old"),
    )
    missing_cli = tmp_path / "does-not-exist.exe"
    assert not missing_cli.exists()
    environment = {**os.environ, "COPILOT_CLI_PATH": str(missing_cli)}
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest_skill_engineering.cli",
            str(source),
            "--html",
            str(output),
            "--summary",
            "--summary-model",
            "copilot/test-model",
        ],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode != 0, completed.stdout + completed.stderr
    assert "Failed to generate AI summary" in completed.stderr
    assert not output.exists()
    assert "AI summary generated successfully" not in completed.stdout


@pytest.mark.parametrize("request_summary", ["raw", "summary", "html"])
def test_pytest_raw_export_and_requested_summary_failure(
    pytester: pytest.Pytester, request_summary: str
) -> None:
    script = pytester.makepyfile(
        """
        from pytest_skill_engineering.copilot.eval import CopilotEval
        from pytest_skill_engineering.copilot.fixtures import stash_on_item
        from pytest_skill_engineering.copilot.result import CopilotResult

        def test_evidence(request):
            stash_on_item(request.node, CopilotEval(name="evidence", model="test-model"),
                          CopilotResult())
        """
    )
    missing_cli = pytester.path / "does-not-exist.exe"
    assert not missing_cli.exists()
    args = [
        sys.executable,
        "-m",
        "pytest",
        str(script),
        "-o",
        "addopts=",
        "--aitest-json=results.json",
        "-q",
    ]
    if request_summary != "raw":
        args.append("--aitest-summary-model=copilot/test-model")
    if request_summary == "html":
        args.append("--aitest-html=report.html")
    completed = subprocess.run(
        args,
        cwd=pytester.path,
        env={**os.environ, "COPILOT_CLI_PATH": str(missing_cli)},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == (0 if request_summary == "raw" else 1), (
        completed.stdout + completed.stderr
    )
    assert (pytester.path / "results.json").is_file()
    assert not (pytester.path / "report.html").exists()
    if request_summary == "raw":
        assert "AI analysis" not in completed.stdout + completed.stderr
        assert "CopilotClient" not in completed.stdout + completed.stderr


@pytest.mark.parametrize(
    "complete,parts,expected",
    [("PASS\nReason", [], "PASS\nReason"), ("", ["PA", "SS"], "PASS"), ("PASS", ["old"], "PASS")],
)
def test_judge_keeps_text_and_streaming_responses(
    complete: str, parts: list[str], expected: str
) -> None:
    assert judge._judge_text(complete, parts) == expected


@pytest.mark.parametrize("complete,parts", [("", []), (" ", ["\n"])])
def test_empty_judge_response_is_not_success(complete: str, parts: list[str]) -> None:
    with pytest.raises(RuntimeError, match="no response text"):
        judge._judge_text(complete, parts)
