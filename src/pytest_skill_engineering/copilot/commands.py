"""Direct executable tools: argument arrays, no shell and no persistent server."""

from __future__ import annotations

import asyncio
import base64
import json
import math
import os
import signal
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from copilot.tools import Tool, ToolInvocation, ToolResult

from pytest_skill_engineering.copilot._command_job import CommandJob


class CommandCancelledError(asyncio.CancelledError):
    """Cancellation after cleanup; ``result`` retains partial command output."""

    def __init__(self, result: ToolResult) -> None:
        super().__init__("Direct command cancelled")
        self.result = result


def _result(
    stdout: bytearray,
    stderr: bytearray,
    exit_code: int | None,
    error: str | None = None,
    error_kind: str | None = None,
) -> ToolResult:
    payload = {
        "stdout": stdout.decode("utf-8", errors="replace"),
        "stderr": stderr.decode("utf-8", errors="replace"),
        "stdout_base64": base64.b64encode(stdout).decode("ascii"),
        "stderr_base64": base64.b64encode(stderr).decode("ascii"),
        "exit_code": exit_code,
        "error": error,
        "error_kind": error_kind,
    }
    return ToolResult(
        text_result_for_llm=json.dumps(payload),
        result_type="failure" if error is not None else "success",
        error=error,
    )


def _text(value: object, label: str, *, empty: bool = True) -> str:
    if not isinstance(value, str) or "\0" in value or (not empty and not value.strip()):
        raise ValueError(f"{label} must be a {'nonempty ' if not empty else ''}string without NUL")
    return value


def create_command_tool(
    executable: str,
    *,
    name: str = "run_command",
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout_s: float = 30.0,
    cleanup_timeout_s: float = 5.0,
    terminate_descendants: bool = True,
) -> Tool:
    """Create an SDK tool for a caller-selected executable and model-supplied arguments.

    ``cwd`` defaults to the caller's directory at construction. ``env`` overrides
    the environment inherited at invocation; overrides are copied at construction.
    ``terminate_descendants=False`` stops only the command process, leaving
    caller-owned services for consumer cleanup. These settings are not model input.
    Input is ``{"args": ["--help"], "stdin": "optional UTF-8 text"}``.
    No argument is parsed as shell syntax. Use a real executable, not a batch
    file or a shell launcher. Caller-owned adapters must enforce application
    permissions; selecting an executable is not a security sandbox.

    Output is JSON with stdout, stderr, exact bytes in corresponding base64 fields,
    exit_code, error and error_kind. Nonzero exit, invalid input, startup failure,
    timeout and cleanup failure are tool failures. Cancellation propagates as
    ``CommandCancelledError`` with partial output in ``result``.
    """
    executable = _text(executable, "executable", empty=False)
    name = _text(name, "name", empty=False)
    if type(terminate_descendants) is not bool:
        raise ValueError("terminate_descendants must be a boolean")
    if Path(executable).suffix.lower() in {".bat", ".cmd"}:
        raise ValueError("Select a native executable, not a .bat or .cmd shell script")
    for label, value in (("timeout_s", timeout_s), ("cleanup_timeout_s", cleanup_timeout_s)):
        if isinstance(value, bool) or not isinstance(value, (float, int)):
            raise ValueError(f"{label} must be a finite positive number")
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{label} must be a finite positive number")
    directory = str(Path(cwd).absolute() if cwd is not None else Path.cwd())
    _text(directory, "cwd", empty=False)
    overrides: dict[str, str] = {}
    for key, value in (env or {}).items():
        _text(key, "environment key", empty=False)
        if "=" in key:
            raise ValueError("Environment keys must not contain '='")
        overrides[key.upper() if os.name == "nt" else key] = _text(value, "environment value")

    async def invoke(invocation: ToolInvocation) -> ToolResult:
        stdout, stderr = bytearray(), bytearray()
        try:
            data: Any = invocation.arguments
            if not isinstance(data, dict) or set(data) - {"args", "stdin"}:
                raise ValueError("Input must be an object with args and optional stdin")
            args = data.get("args")
            if not isinstance(args, list):
                raise ValueError("args must be an array of strings")
            arguments = [_text(arg, "argument") for arg in args]
            stdin = None
            if "stdin" in data:
                if not isinstance(data["stdin"], str):
                    raise ValueError("stdin must be a string")
                stdin = data["stdin"].encode("utf-8")
        except ValueError as exc:
            return _result(stdout, stderr, None, str(exc), "invalid_input")

        process: asyncio.subprocess.Process | None = None
        job: CommandJob | None = None
        job_assigned = False
        tasks: list[asyncio.Task[None]] = []

        async def read(stream: asyncio.StreamReader, output: bytearray) -> None:
            while chunk := await stream.read(65536):
                output.extend(chunk)

        async def run() -> None:
            nonlocal process, job, job_assigned
            if os.name == "nt" and terminate_descendants:
                job = CommandJob()
            process = await asyncio.create_subprocess_exec(
                executable,
                *arguments,
                cwd=directory,
                env={**os.environ, **overrides},
                stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=os.name != "nt" and terminate_descendants,
            )
            assert process.stdout is not None and process.stderr is not None
            tasks.extend(
                [
                    asyncio.create_task(read(process.stdout, stdout)),
                    asyncio.create_task(read(process.stderr, stderr)),
                ]
            )
            if job is not None:
                job.assign(process.pid)
                job_assigned = True
            if process.stdin is not None:
                try:
                    process.stdin.write(stdin or b"")
                    await process.stdin.drain()
                except (BrokenPipeError, ConnectionResetError):
                    pass  # The exit status and stderr describe early command termination.
                finally:
                    process.stdin.close()
            await process.wait()
            await asyncio.gather(*tasks)

        async def cleanup() -> str | None:
            if process is not None:
                try:
                    if job is not None:
                        job.close()
                        if not job_assigned and process.returncode is None:
                            process.kill()
                    elif os.name != "nt" and terminate_descendants:
                        os.killpg(process.pid, signal.SIGKILL)
                    elif process.returncode is None:
                        process.kill()
                except ProcessLookupError:
                    pass
                except OSError as exc:
                    return f"Command cleanup failed: {exc}"
            elif job is not None:
                job.close()
            return None

        execution = asyncio.create_task(run())
        error: str | None = None
        error_kind: str | None = None
        cancelled = False
        try:
            done, _ = await asyncio.wait({execution}, timeout=timeout_s)
            if not done:
                error, error_kind = f"Command timed out after {timeout_s:g}s", "timeout"
            else:
                await execution
        except asyncio.CancelledError:
            cancelled = True
            error, error_kind = "Command cancelled", "cancelled"
        except (OSError, ValueError) as exc:
            error, error_kind = f"Command could not start or complete: {exc}", "start"
        finally:
            # Keep ownership even when the caller cancels again during shutdown.
            async def finish() -> str | None:
                # asyncio owns and reaps a subprocess if creation itself is cancelled.
                if process is None and not execution.done():
                    execution.cancel()
                    await asyncio.gather(execution, return_exceptions=True)
                cleanup_error = await cleanup()
                pending = {execution, *tasks}
                if process is not None:

                    async def reap() -> None:
                        assert process is not None
                        await process.wait()

                    pending.add(asyncio.create_task(reap()))
                _, remaining = await asyncio.wait(pending, timeout=cleanup_timeout_s)
                if remaining:
                    for task in remaining:
                        task.cancel()
                    await asyncio.gather(*remaining, return_exceptions=True)
                    cleanup_error = cleanup_error or "Command cleanup exceeded its time limit"
                await asyncio.gather(*pending, return_exceptions=True)
                return cleanup_error

            finishing = asyncio.create_task(finish())
            while True:
                try:
                    cleanup_error = await asyncio.shield(finishing)
                    break
                except asyncio.CancelledError:
                    cancelled = True
                    error, error_kind = "Command cancelled", "cancelled"
            if cleanup_error:
                error = f"{error}; {cleanup_error}" if error else cleanup_error
                error_kind = "cleanup"

        exit_code = process.returncode if process is not None else None
        if error is None and exit_code != 0:
            error, error_kind = f"Command exited with status {exit_code}", "exit"
        result = _result(stdout, stderr, exit_code, error, error_kind)
        if cancelled:
            raise CommandCancelledError(result)
        return result

    return Tool(
        name=name,
        description=(
            f"Run {Path(executable).name} directly with an argument array, without a shell. "
            "Use its native --help to discover commands. Use this tool for setup and "
            "supporting commands too. Shell operators and quoting are literal arguments. "
            "Returns stdout, stderr, exit_code and explicit errors."
        ),
        parameters={
            "type": "object",
            "properties": {
                "args": {"type": "array", "items": {"type": "string"}},
                "stdin": {"type": "string", "description": "Optional UTF-8 standard input"},
            },
            "required": ["args"],
            "additionalProperties": False,
        },
        handler=invoke,
    )
