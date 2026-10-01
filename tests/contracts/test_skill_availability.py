"""Offline skill setup contracts; no model execution."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

import pytest
from copilot.generated.rpc import Skill as SDKSkill
from copilot.generated.rpc import SkillList, SkillsLoadDiagnostics
from copilot.generated.session_events import SkillSource

from pytest_skill_engineering.copilot import CopilotEval, runner
from pytest_skill_engineering.copilot.fixtures import _convert_to_aitest
from pytest_skill_engineering.copilot.skills import requested_skill_files
from pytest_skill_engineering.core.serialization import serialize_dataclass
from pytest_skill_engineering.reporting import TestReport as CaseReport
from pytest_skill_engineering.reporting import build_suite_report, generate_json, load_suite_report


@pytest.mark.parametrize("mode", ["empty", "copilot-cli"])
def test_explicit_skills_enable_loading_without_ambient_discovery(
    mode: Literal["empty", "copilot-cli"],
) -> None:
    agent = CopilotEval(client_mode=mode, skill_directories=["explicit-skills"])
    config = agent.build_session_config()
    assert config["enable_skills"] is True
    assert config["enable_config_discovery"] is False


def test_explicit_skills_cannot_be_globally_disabled() -> None:
    agent = CopilotEval(
        client_mode="empty",
        skill_directories=["explicit-skills"],
        extra_config={"enable_skills": False},
    )
    with pytest.raises(ValueError, match="enable_skills=False"):
        agent.build_session_config()


@pytest.mark.parametrize("enabled", [None, True])
def test_explicit_skills_with_passthrough_enable_setting(enabled: bool | None) -> None:
    config = CopilotEval(
        skill_directories=["explicit-skills"], extra_config={"enable_skills": enabled}
    ).build_session_config()
    assert config["enable_skills"] is True


def test_explicit_disable_without_directories_is_supported() -> None:
    config = CopilotEval(
        client_mode="empty", extra_config={"enable_skills": False}
    ).build_session_config()
    assert config["enable_skills"] is False


def test_passthrough_directories_cannot_evade_enable_or_replace_explicit_inputs() -> None:
    config = CopilotEval(
        client_mode="empty", extra_config={"skill_directories": ["explicit-skills"]}
    ).build_session_config()
    assert config["enable_skills"] is True
    with pytest.raises(ValueError, match="override"):
        CopilotEval(
            skill_directories=["explicit-skills"], extra_config={"skill_directories": []}
        ).build_session_config()
    with pytest.raises(ValueError, match="enable_skills=False"):
        CopilotEval(
            extra_config={"skill_directories": ["explicit-skills"], "enable_skills": False}
        ).build_session_config()


def _write_skill(parent: Path, name: str = "explicit-skill") -> Path:
    directory = parent / name
    directory.mkdir(parents=True)
    (directory / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Explicit test skill\n---\n\n# Instructions\n",
        encoding="utf-8",
    )
    return directory


def test_relative_and_repeated_paths_resolve_to_the_same_explicit_skill(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = _write_skill(tmp_path)
    monkeypatch.chdir(tmp_path)
    requested = requested_skill_files([directory.name, str(directory), str(tmp_path)])
    assert requested == {(directory / "SKILL.md").resolve(): directory.name}


@pytest.mark.parametrize("directories", [[""], [None], "not-a-list"])
async def test_invalid_directory_argument_shapes_fail_before_start(
    monkeypatch: pytest.MonkeyPatch, directories: Any
) -> None:
    def forbid_client(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Invalid directory arguments must not start a client")

    monkeypatch.setattr(runner, "create_client", forbid_client)
    result = await runner.run_copilot(CopilotEval(skill_directories=directories), "Do not send.")
    assert not result.success and result.stop_reason == "execution_error"
    assert result.error and "skill_directories" in result.error


@pytest.mark.parametrize(
    "invalid", ["missing", "file", "empty", "invalid", "partial", "unreadable", "duplicate"]
)
async def test_bad_skill_inputs_fail_before_client_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, invalid: str
) -> None:
    directory = tmp_path / "skills"
    if invalid == "file":
        directory.write_text("not a directory", encoding="utf-8")
    elif invalid != "missing":
        directory.mkdir()
    if invalid in ("invalid", "partial"):
        bad = _write_skill(directory, "invalid-skill")
        (bad / "SKILL.md").write_text("No required frontmatter", encoding="utf-8")
        if invalid == "partial":
            _write_skill(directory, "valid-skill")
    if invalid == "duplicate":
        one = _write_skill(directory / "one")
        two = _write_skill(directory / "two")
        directories = [str(one), str(two)]
    else:
        directories = [str(directory)]
    if invalid == "unreadable":
        skill = _write_skill(directory)
        original_read = Path.read_text

        def read(path: Path, *args: Any, **kwargs: Any) -> str:
            if path == skill / "SKILL.md":
                raise PermissionError("Unreadable requested skill")
            return original_read(path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", read)

    def forbid_client(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Invalid skill inputs must not start an SDK client")

    monkeypatch.setattr(runner, "create_client", forbid_client)
    result = await runner.run_copilot(
        CopilotEval(client_mode="empty", skill_directories=directories), "Do not execute."
    )
    assert not result.success and result.stop_reason == "execution_error"
    assert result.error and "Skill setup failed before model execution" in result.error
    assert str(directory) in result.error
    assert result.skill_discovery is not None
    assert not result.skill_discovery.complete
    assert result.skill_discovery.errors
    assert result.usage == [] and result.turns == []


@pytest.mark.parametrize(
    "outcome",
    [
        "loaded",
        "missing",
        "wrong-path",
        "disabled",
        "intentional-disable",
        "sdk-error",
        "rpc-error",
    ],
)
async def test_runner_checks_sdk_availability_before_its_single_send_and_saves_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    directory = _write_skill(tmp_path)
    path = str(directory / "SKILL.md")
    calls: list[str] = []
    exposed = SDKSkill(
        name=directory.name,
        description="SDK description",
        source=SkillSource.PROJECT,
        enabled=outcome not in ("disabled", "intentional-disable"),
        user_invocable=True,
        path=path if outcome != "wrong-path" else str(tmp_path / "other" / "SKILL.md"),
    )

    class Skills:
        async def ensure_loaded(self) -> None:
            calls.append("ensure")
            if outcome == "rpc-error":
                raise RuntimeError("Skill RPC failed")

        async def reload(self) -> SkillsLoadDiagnostics:
            calls.append("reload")
            return SkillsLoadDiagnostics(
                errors=["SDK skill parse failed"] if outcome == "sdk-error" else [],
                warnings=["SDK skill warning"],
            )

        async def list(self) -> SkillList:
            calls.append("list")
            return SkillList([] if outcome == "missing" else [exposed])

    class Session:
        rpc = SimpleNamespace(skills=Skills())

        async def send_and_wait(self, prompt: str, timeout: float) -> None:
            calls.append("send")

        async def abort(self) -> None:
            calls.append("abort")

    class Client:
        async def start(self) -> None:
            calls.append("start")

        async def create_session(self, **config: Any) -> Session:
            calls.append("create")
            assert config["enable_skills"] is True
            assert config["enable_config_discovery"] is False
            return Session()

        async def stop(self) -> None:
            calls.append("stop")

    monkeypatch.setattr(runner, "create_client", lambda *args, **kwargs: Client())
    agent = CopilotEval(
        client_mode="empty",
        skill_directories=[str(directory)],
        disabled_skills=[directory.name] if outcome == "intentional-disable" else [],
        audit_requests=outcome not in ("loaded", "intentional-disable"),
    )
    result = await runner.run_copilot(agent, "Do not force a skill read.")
    succeeds = outcome in ("loaded", "intentional-disable")
    assert result.success is succeeds
    assert calls.count("start") == calls.count("create") == calls.count("stop") == 1
    assert calls.count("send") == int(succeeds)
    assert calls.count("abort") == int(not succeeds)
    discovery = result.skill_discovery
    assert discovery is not None
    assert discovery.complete is (outcome != "rpc-error")
    assert discovery.warnings == ([] if outcome == "rpc-error" else ["SDK skill warning"])
    assert result.all_tool_calls == [] and result.usage == []
    if not succeeds:
        assert result.stop_reason == "execution_error" and result.error
        assert "No outbound model requests" not in result.error
        assert discovery.errors

    converted = _convert_to_aitest(agent, result)
    assert converted is not None
    saved, _ = converted
    assert saved.skill_discovery == discovery
    assert saved.skill_discovery is not discovery
    suite = build_suite_report(
        [CaseReport(name="skill-setup", outcome="passed", duration_ms=0, eval_result=saved)],
        name="Skill setup evidence",
    )
    output = tmp_path / "evidence.json"
    generate_json(suite, output)
    assert serialize_dataclass(load_suite_report(output)) == serialize_dataclass(suite)
