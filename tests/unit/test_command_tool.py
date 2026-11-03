"""Offline direct-command coverage; no SDK session or model requests."""

from __future__ import annotations

import asyncio
import base64
import inspect
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import pytest
from copilot.tools import Tool, ToolInvocation, ToolResult

from pytest_copilot.copilot import (
    CommandCancelledError,
    CopilotTask,
    commands,
    create_command_tool,
)


async def invoke(tool: Tool, arguments: Any) -> ToolResult:
    assert tool.handler is not None
    result = tool.handler(ToolInvocation(arguments=arguments))
    return await result if inspect.isawaitable(result) else result


def payload(result: ToolResult) -> dict[str, Any]:
    return json.loads(result.text_result_for_llm)


async def test_arguments_stdin_cwd_and_environment_are_preserved(tmp_path: Path) -> None:
    environment = {"DIRECT_TOOL_TEST": 'space "quote" $value'}
    tool = create_command_tool(sys.executable, cwd=tmp_path, env=environment)
    environment["DIRECT_TOOL_TEST"] = "mutated"
    args = ["", 'a "quoted" value', r"C:\folder with spaces\last\\", "$x", "|", ">", "a;b"]
    code = (
        "import json, os, sys; "
        "print(json.dumps([sys.argv[1:], sys.stdin.read(), os.getcwd(), "
        "os.environ['DIRECT_TOOL_TEST'], 'PATH' in os.environ])); "
        "sys.stderr.write('warning\\n')"
    )
    result = await invoke(tool, {"args": ["-c", code, *args], "stdin": "line 1\nline 2\n"})
    assert result.result_type == "success", result.error
    data = payload(result)
    assert set(data) == {"stdout", "stderr", "exit_code", "error", "error_kind"}
    assert json.loads(data["stdout"]) == [
        args,
        "line 1\nline 2\n",
        str(tmp_path),
        'space "quote" $value',
        True,
    ]
    assert data["stderr"].splitlines() == ["warning"]
    assert data["exit_code"] == 0
    assert data["error"] is None and data["error_kind"] is None


async def test_stdin_absence_is_eof_and_bytes_are_lossless() -> None:
    result = await invoke(
        create_command_tool(sys.executable),
        {
            "args": [
                "-c",
                "import sys; assert sys.stdin.read() == ''; sys.stdout.buffer.write(b'\\xff\\r\\n')",
            ]
        },
    )
    assert result.result_type == "success", result.error
    assert base64.b64decode(payload(result)["stdout_base64"]) == b"\xff\r\n"
    assert "stderr_base64" not in payload(result)


async def test_valid_utf8_is_not_duplicated_and_binary_stderr_is_lossless() -> None:
    result = await invoke(
        create_command_tool(sys.executable),
        {
            "args": [
                "-c",
                "import sys; sys.stdout.buffer.write(b'\\xc3\\xa9\\r\\n'); sys.stderr.buffer.write(b'\\x80')",
            ]
        },
    )
    data = payload(result)
    assert result.result_type == "success", result.error
    assert data["stdout"] == "\u00e9\r\n"
    assert "stdout_base64" not in data
    assert base64.b64decode(data["stderr_base64"]) == b"\x80"


@pytest.mark.parametrize(
    "arguments",
    [
        None,
        [],
        {},
        {"args": "--help"},
        {"args": [1]},
        {"args": ["\0"]},
        {"args": [], "stdin": None},
        {"args": [], "cwd": "ignored"},
        {"args": [], "executable": "ignored"},
    ],
)
async def test_invalid_input_is_a_failure(arguments: Any) -> None:
    result = await invoke(create_command_tool(sys.executable), arguments)
    assert result.result_type == "failure"
    assert payload(result)["error_kind"] == "invalid_input"
    assert payload(result)["exit_code"] is None


@pytest.mark.parametrize(
    "options",
    [
        {"timeout_s": 0},
        {"timeout_s": float("inf")},
        {"timeout_s": True},
        {"cleanup_timeout_s": -1},
        {"cleanup_timeout_s": float("nan")},
        {"name": ""},
        {"env": {"BAD=KEY": "value"}},
        {"env": {"KEY": "\0"}},
        {"terminate_descendants": "yes"},
    ],
)
def test_invalid_configuration_is_rejected(options: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        create_command_tool(sys.executable, **options)


@pytest.mark.parametrize("executable", ["", "\0", "script.cmd", "script.BAT"])
def test_invalid_executable_is_rejected(executable: str) -> None:
    with pytest.raises(ValueError):
        create_command_tool(executable)


async def test_missing_executable_and_cwd_fail_explicitly(tmp_path: Path) -> None:
    for executable, cwd in [
        (str(tmp_path / "missing-executable"), tmp_path),
        (sys.executable, tmp_path / "missing-directory"),
    ]:
        result = await invoke(create_command_tool(executable, cwd=cwd), {"args": []})
        assert result.result_type == "failure"
        assert payload(result)["error_kind"] == "start"
        assert payload(result)["exit_code"] is None


async def test_nonzero_exit_retains_both_streams() -> None:
    result = await invoke(
        create_command_tool(sys.executable),
        {"args": ["-c", "import sys; print('out'); print('err', file=sys.stderr); sys.exit(7)"]},
    )
    data = payload(result)
    assert result.result_type == "failure"
    assert data["error_kind"] == "exit" and data["exit_code"] == 7
    assert data["stdout"].strip() == "out" and data["stderr"].strip() == "err"


async def test_timeout_preserves_partial_output_and_stops_writes(tmp_path: Path) -> None:
    marker = tmp_path / "must-not-exist"
    tool = create_command_tool(sys.executable, timeout_s=0.4, cleanup_timeout_s=1)
    start = time.monotonic()
    result = await invoke(
        tool,
        {
            "args": [
                "-u",
                "-c",
                "import pathlib, sys, time; print('partial'); "
                "print('warning', file=sys.stderr); time.sleep(2); "
                "pathlib.Path(sys.argv[1]).write_text('leaked')",
                str(marker),
            ]
        },
    )
    data = payload(result)
    assert result.result_type == "failure"
    assert data["error_kind"] == "timeout", data
    assert "partial" in data["stdout"] and "warning" in data["stderr"]
    assert data["exit_code"] is not None
    assert time.monotonic() - start < 2
    await asyncio.sleep(2)
    assert not marker.exists()


async def test_cancellation_keeps_partial_output_and_stops_descendants(tmp_path: Path) -> None:
    ready = tmp_path / "ready"
    marker = tmp_path / "must-not-exist"
    child = (
        "import pathlib, sys, time; pathlib.Path(sys.argv[1]).write_text('ready'); "
        "time.sleep(2); pathlib.Path(sys.argv[2]).write_text('leaked')"
    )
    parent = (
        "import subprocess, sys, time; "
        "subprocess.Popen([sys.executable, '-c', sys.argv[1], *sys.argv[2:]]); "
        "print('partial', flush=True); time.sleep(30)"
    )
    task = asyncio.create_task(
        invoke(
            create_command_tool(sys.executable, cleanup_timeout_s=1),
            {"args": ["-c", parent, child, str(ready), str(marker)]},
        )
    )
    async with asyncio.timeout(5):
        while not ready.exists():
            await asyncio.sleep(0.01)
    start = time.monotonic()
    task.cancel()
    with pytest.raises(CommandCancelledError) as caught:
        await task
    assert task.cancelled()
    data = payload(caught.value.result)
    assert data["error_kind"] == "cancelled", data
    assert "partial" in data["stdout"]
    assert data["exit_code"] is not None
    assert time.monotonic() - start < 2
    await asyncio.sleep(2)
    assert not marker.exists()


async def test_parent_exit_does_not_leave_a_descendant_holding_pipes(tmp_path: Path) -> None:
    marker = tmp_path / "must-not-exist"
    child = (
        "import pathlib, sys, time; time.sleep(2); pathlib.Path(sys.argv[1]).write_text('leaked')"
    )
    parent = (
        "import subprocess, sys; subprocess.Popen([sys.executable, '-c', sys.argv[1], sys.argv[2]])"
    )
    result = await invoke(
        create_command_tool(sys.executable, timeout_s=0.4, cleanup_timeout_s=1),
        {"args": ["-c", parent, child, str(marker)]},
    )
    assert payload(result)["error_kind"] == "timeout", payload(result)
    await asyncio.sleep(2)
    assert not marker.exists()


async def test_large_stdin_and_simultaneous_output_do_not_deadlock() -> None:
    text = "x" * 200000
    result = await invoke(
        create_command_tool(sys.executable),
        {
            "args": [
                "-c",
                "import sys; sys.stderr.write('y' * 200000); print(len(sys.stdin.read()))",
            ],
            "stdin": text,
        },
    )
    data = payload(result)
    assert result.result_type == "success", result.error
    assert data["stdout"].strip() == "200000"
    assert data["stderr"] == "y" * 200000


async def test_environment_is_inherited_at_invocation(monkeypatch: pytest.MonkeyPatch) -> None:
    tool = create_command_tool(sys.executable, env={"FIXED_VALUE": "override"})
    monkeypatch.setenv("CASE_PIPE", "case-selected-after-tool-construction")
    monkeypatch.setenv("FIXED_VALUE", "inherited")
    result = await invoke(
        tool,
        {
            "args": [
                "-c",
                "import os; print(os.environ['CASE_PIPE']); print(os.environ['FIXED_VALUE'])",
            ]
        },
    )
    assert result.result_type == "success", result.error
    assert payload(result)["stdout"].splitlines() == [
        "case-selected-after-tool-construction",
        "override",
    ]


@pytest.mark.parametrize("cancel", [False, True])
async def test_root_only_cleanup_preserves_caller_owned_service(
    tmp_path: Path, cancel: bool
) -> None:
    ready = tmp_path / "ready"
    preserved = tmp_path / "preserved"
    root_leak = tmp_path / "root-must-not-finish"
    child = (
        "import pathlib, sys, time; pathlib.Path(sys.argv[1]).write_text('ready'); "
        "time.sleep(1); pathlib.Path(sys.argv[2]).write_text('preserved')"
    )
    parent = (
        "import pathlib, subprocess, sys, time; "
        "subprocess.Popen([sys.executable, '-c', sys.argv[1], sys.argv[2], sys.argv[3]], "
        "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); "
        "print('partial', flush=True); time.sleep(2); pathlib.Path(sys.argv[4]).touch()"
    )
    task = asyncio.create_task(
        invoke(
            create_command_tool(
                sys.executable,
                timeout_s=10 if cancel else 0.4,
                cleanup_timeout_s=1,
                terminate_descendants=False,
            ),
            {"args": ["-c", parent, child, str(ready), str(preserved), str(root_leak)]},
        )
    )
    async with asyncio.timeout(5):
        while not ready.exists():
            await asyncio.sleep(0.01)
    if cancel:
        task.cancel()
        with pytest.raises(CommandCancelledError) as caught:
            await task
        result = caught.value.result
    else:
        result = await task
    assert payload(result)["error_kind"] == ("cancelled" if cancel else "timeout")
    assert "partial" in payload(result)["stdout"]
    assert payload(result)["exit_code"] is not None
    await asyncio.sleep(2.1)
    assert preserved.read_text() == "preserved"
    assert not root_leak.exists()


async def test_native_help_and_empty_or_nul_stdin() -> None:
    result = await invoke(create_command_tool(sys.executable), {"args": ["--help"]})
    assert result.result_type == "success", result.error
    assert "usage:" in payload(result)["stdout"].lower()
    assert set(payload(result)) == {"stdout", "stderr", "exit_code", "error", "error_kind"}
    for stdin in ("", "with\0nul"):
        result = await invoke(
            create_command_tool(sys.executable),
            {
                "args": ["-c", "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"],
                "stdin": stdin,
            },
        )
        assert result.result_type == "success", result.error
        assert payload(result)["stdout"] == stdin
        assert "stdout_base64" not in payload(result)


@pytest.mark.skipif(os.name != "nt", reason="Windows job assignment failure")
async def test_failed_job_assignment_still_stops_the_started_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FailedJob:
        def assign(self, pid: int) -> None:
            raise OSError("job assignment rejected")

        def close(self) -> None:
            pass

    monkeypatch.setattr(commands, "CommandJob", FailedJob)
    marker = tmp_path / "must-not-exist"
    result = await invoke(
        create_command_tool(sys.executable, cleanup_timeout_s=1),
        {
            "args": [
                "-c",
                "import pathlib, sys, time; time.sleep(1); pathlib.Path(sys.argv[1]).touch()",
                str(marker),
            ]
        },
    )
    assert payload(result)["error_kind"] == "start"
    assert "job assignment rejected" in (result.error or "")
    assert payload(result)["exit_code"] is not None
    await asyncio.sleep(1.1)
    assert not marker.exists()


def test_tool_is_wired_into_sdk_configuration_without_a_shell() -> None:
    tool = create_command_tool(sys.executable)
    config = CopilotTask(
        client_mode="empty",
        allowed_tools=["run_command"],
        extra_config={"tools": [tool]},
    ).build_session_config()
    assert config["tools"] == [tool]
    assert config["available_tools"] == ["run_command"]
    assert tool.parameters is not None
    assert tool.parameters["required"] == ["args"]
    assert tool.parameters["additionalProperties"] is False
    assert "shell" in tool.description
    assert os.path.basename(sys.executable) in tool.description
