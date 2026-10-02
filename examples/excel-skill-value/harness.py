from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from copilot.tools import Tool, ToolInvocation, ToolResult

from pytest_skill_engineering.copilot import CopilotEval

ROOT = Path(__file__).resolve().parent


def executable(transport: str) -> str:
    name = f"EXCEL_{transport.upper()}_EXECUTABLE"
    supplied = os.environ.get(name)
    if not supplied or not Path(supplied).is_file():
        raise ValueError(f"Set {name} to a built executable")
    return str(Path(supplied).resolve())


def workspace(directory: Path, skill: Path | None) -> Tool:
    roots = [directory.resolve(), *([skill.resolve()] if skill else [])]

    def run(invocation: ToolInvocation) -> ToolResult:
        args = invocation.arguments or {}
        path = (directory / args["path"]).resolve()
        if not any(path.is_relative_to(root) for root in roots):
            return ToolResult(result_type="denied", text_result_for_llm="Outside supplied files")
        try:
            if args["action"] == "read":
                return ToolResult(text_result_for_llm=path.read_text(encoding="utf-8"))
            if args["action"] == "list":
                return ToolResult(text_result_for_llm="\n".join(p.name for p in path.iterdir()))
            if not path.is_relative_to(roots[0]) or path.suffix not in {
                ".json",
                ".csv",
                ".txt",
                ".m",
            }:
                return ToolResult(
                    result_type="denied", text_result_for_llm="Write task inputs only"
                )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(args["content"], encoding="utf-8")
            return ToolResult(text_result_for_llm="Written")
        except (OSError, UnicodeError) as error:
            return ToolResult(result_type="failure", text_result_for_llm=str(error))

    return Tool(
        name="workspace",
        description="Read/list task and skill files; write non-executable task inputs.",
        parameters={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["read", "list", "write"]},
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["action", "path"],
        },
        handler=run,
        defer="never",
    )


def cli_tool(directory: Path, pipe: str) -> Tool:
    command = executable("cli")

    def run(invocation: ToolInvocation) -> ToolResult:
        args = (invocation.arguments or {}).get("args", [])
        try:
            completed = subprocess.run(
                [command, *args],
                cwd=directory,
                env={**os.environ, "EXCELMCP_CLI_PIPE": pipe},
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            return ToolResult(result_type="failure", text_result_for_llm=str(error))
        return ToolResult(
            text_result_for_llm=json.dumps(
                {
                    "exit_code": completed.returncode,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                }
            )
        )

    return Tool(
        name="excelcli",
        description="Run excelcli with individual arguments, without a shell.",
        parameters={
            "type": "object",
            "properties": {
                "args": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["args"],
        },
        handler=run,
        defer="never",
    )


def agent(transport: str, directory: Path, pipe: str, skill: Path | None) -> CopilotEval:
    tools = [workspace(directory, skill)]
    servers: dict[str, Any] = {}
    allowed = ["builtin:skill", "builtin:tool_search_tool", "custom:workspace"]
    if transport == "cli":
        tools.append(cli_tool(directory, pipe))
        allowed.append("custom:excelcli")
    else:
        servers["excel-mcp"] = {
            "type": "local",
            "command": executable("mcp"),
            "args": [],
            "tools": ["*"],
        }
        allowed.append("mcp:*")
    return CopilotEval(
        name=f"excel-{transport}-{'skill' if skill else 'baseline'}",
        model="gpt-6.1-sol",
        client_mode="empty",
        working_directory=str(directory),
        instructions="Use the available Excel tools to complete the requested workbook task.",
        skill_directories=[str(skill)] if skill else [],
        mcp_servers=servers,
        allowed_tools=allowed,
        max_turns=20,
        max_tool_calls=80,
        timeout_s=600,
        extra_config={"tools": tools, "enable_skills": True},
    )
