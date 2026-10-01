"""Real SDK discovery and blocked-request checks. Never execute a model."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest
from copilot import CopilotRequestContext, CopilotRequestHandler, CopilotWebSocketHandler
from copilot.session import CopilotSession

from pytest_skill_engineering.copilot import CopilotEval
from pytest_skill_engineering.copilot.client import create_client, stop_client
from pytest_skill_engineering.copilot.skills import discover_requested_skills, requested_skill_files
from pytest_skill_engineering.core.result import SkillDiscovery

pytestmark = pytest.mark.copilot


def _write_skill(parent: Path, name: str) -> Path:
    directory = parent / name
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Explicit discovery test\n---\n\n# {name}\n",
        encoding="utf-8",
    )
    return directory


@pytest.mark.parametrize("selection", ["baseline", "individual", "parent", "disabled"])
async def test_empty_mode_discovers_only_explicit_skills_without_model_sends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, selection: str
) -> None:
    async def forbid_send(*args: object, **kwargs: object) -> None:
        pytest.fail("Discovery checks must not send model messages")

    monkeypatch.setattr(CopilotSession, "send", forbid_send)
    monkeypatch.setattr(CopilotSession, "send_and_wait", forbid_send)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_skill(workspace / ".github" / "skills", "ambient-project")
    (workspace / ".github" / "copilot-instructions.md").write_text(
        "AMBIENT INSTRUCTIONS MUST NOT LOAD", encoding="utf-8"
    )
    storage = tmp_path / "storage"
    storage.mkdir()
    _write_skill(storage / "skills", "ambient-personal")
    parent = tmp_path / "explicit"
    first = _write_skill(parent, "explicit-first")
    second = _write_skill(parent, "explicit-second")
    directories = {
        "baseline": [],
        "individual": [str(first)],
        "parent": [str(parent)],
        "disabled": [str(first)],
    }[selection]
    expected = {
        "baseline": set(),
        "individual": {str(first / "SKILL.md")},
        "parent": {str(first / "SKILL.md"), str(second / "SKILL.md")},
        "disabled": {str(first / "SKILL.md")},
    }[selection]
    agent = CopilotEval(
        client_mode="empty",
        working_directory=str(workspace),
        skill_directories=directories,
        disabled_skills=["explicit-first"] if selection == "disabled" else [],
    )
    client = create_client(str(workspace), mode="empty", base_directory=str(storage))
    try:
        async with asyncio.timeout(60):
            await client.start()
            session = await client.create_session(**agent.build_session_config())
            await session.rpc.skills.ensure_loaded()
            skills = (await session.rpc.skills.list()).skills
            assert {skill.path for skill in skills} == expected
            assert all(skill.enabled is (selection != "disabled") for skill in skills)
            assert (await session.rpc.skills.get_invoked()).skills == []
            discovery = SkillDiscovery()
            await discover_requested_skills(
                session, requested_skill_files(directories), agent.disabled_skills, discovery
            )
            assert discovery.complete and not discovery.errors and not discovery.warnings
            assert {skill.path for skill in discovery.skills} == expected
    finally:
        assert await stop_client(client) == []


async def test_empty_mode_omits_ambient_instructions_from_blocked_request(tmp_path: Path) -> None:
    """Build a request, but block both transports before any network forwarding."""
    captured: list[bytes] = []
    received = asyncio.Event()

    class BlockRequests(CopilotRequestHandler):
        async def send_request(
            self, request: httpx.Request, ctx: CopilotRequestContext
        ) -> httpx.Response:
            captured.append(await request.aread())
            received.set()
            raise RuntimeError("Model execution forbidden by discovery test")

        async def open_websocket(self, ctx: CopilotRequestContext) -> CopilotWebSocketHandler:
            raise RuntimeError("WebSocket model execution forbidden by discovery test")

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_skill(workspace / ".github" / "skills", "ambient-project")
    (workspace / ".github" / "copilot-instructions.md").write_text(
        "AMBIENT_INSTRUCTION_SENTINEL", encoding="utf-8"
    )
    (workspace / "AGENTS.md").write_text("AMBIENT_AGENT_SENTINEL", encoding="utf-8")
    first = _write_skill(tmp_path / "explicit", "explicit-first")
    agent = CopilotEval(
        client_mode="empty",
        model="gpt-4.1",
        working_directory=str(workspace),
        skill_directories=[str(first)],
        instructions="EXPLICIT_INSTRUCTION_SENTINEL",
        extra_config={
            "provider": {
                "type": "openai",
                "base_url": "http://127.0.0.1:1",
                "api_key": "offline-not-a-credential",
                "wire_api": "completions",
                "transport": "http",
            }
        },
    )
    client = create_client(
        str(workspace),
        mode="empty",
        base_directory=str(tmp_path / "storage"),
        request_handler=BlockRequests(),
    )
    try:
        async with asyncio.timeout(60):
            await client.start()
            session = await client.create_session(**agent.build_session_config())
            await session.rpc.skills.ensure_loaded()
            assert [skill.name for skill in (await session.rpc.skills.list()).skills] == [
                "explicit-first"
            ]
            await session.send("Check isolated configuration.")
            await received.wait()
            await session.abort()
            payload = json.dumps(json.loads(captured[0]))
            assert "EXPLICIT_INSTRUCTION_SENTINEL" in payload
            assert "AMBIENT_INSTRUCTION_SENTINEL" not in payload
            assert "AMBIENT_AGENT_SENTINEL" not in payload
            assert "ambient-project" not in payload
    finally:
        assert await stop_client(client) == []
