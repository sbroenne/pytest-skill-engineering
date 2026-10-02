from __future__ import annotations

import asyncio
import hashlib
import importlib.metadata
import json
import os
import subprocess
import uuid
from dataclasses import asdict
from pathlib import Path

import pytest
from checks import ROOT, check, workbook
from harness import agent, executable
from skill_discovery import assert_skill_exposure, discover_skills

pytestmark = pytest.mark.copilot


def save(path: Path, data: dict) -> None:
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


@pytest.fixture(scope="session")
async def comparison(request, tmp_path_factory):
    supplied = request.config.getoption("--receipt-dir")
    if not supplied:
        raise pytest.UsageError("Use a new --receipt-dir for each comparison")
    directory = Path(supplied).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    tasks = tmp_path_factory.mktemp("excel-skill-value")
    profile = request.config.getoption("--skill-profile")
    skills = {}
    for transport in ("mcp", "cli"):
        executable(transport)
        if profile == "broad":
            skill = ROOT / "fixtures" / f"excel-{transport}"
        else:
            value = os.environ.get(f"EXCEL_{transport.upper()}_SKILL_DIRECTORY")
            if not value:
                raise pytest.UsageError(
                    "Formatting requires both explicit prepared skill directories"
                )
            skill = Path(value).resolve()
        skills[transport] = skill
        for condition in (False, True):
            configured = agent(transport, tasks, "unused-discovery", skill if condition else None)
            discovered = await discover_skills(configured)
            expected = f"excel-{transport}" + (
                "-report-formatting" if profile == "formatting" else ""
            )
            assert_skill_exposure(
                discovered,
                expected if condition else None,
                str(skill) if condition else None,
            )
    hashes = {
        transport: {
            str(path.relative_to(skill)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(skill.rglob("*"))
            if path.is_file()
        }
        for transport, skill in skills.items()
    }
    save(
        directory / "manifest.json",
        {
            "model": "gpt-6.1-sol",
            "profile": profile,
            "skills": hashes,
            "packages": {
                name: importlib.metadata.version(name)
                for name in ("pytest-skill-engineering", "github-copilot-sdk", "mcp")
            },
            "checks": {
                name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                for name in (
                    "checks.py",
                    "Workbook.ps1",
                    "harness.py",
                    "skill_discovery.py",
                    "Close-OwnedWorkbook.ps1",
                )
            },
            "planned_cases": len(
                [item for item in request.session.items if item.get_closest_marker("copilot")]
            ),
            "prior_attempts": request.config.getoption("--prior-attempts"),
            "ceiling": request.config.getoption("--paid-limit"),
        },
    )
    return directory, tasks, skills, profile


@pytest.mark.parametrize("transport", ["mcp", "cli"])
@pytest.mark.parametrize("with_skill", [False, True], ids=["without-skill", "with-skill"])
async def test_comparison(copilot_eval, comparison, transport, with_skill):
    directory, tasks, skills, profile = comparison
    work = tasks / f"{transport}-{with_skill}"
    work.mkdir()
    path = work / "report.xlsx"
    pipe = f"excel-skill-example-{uuid.uuid4().hex}"
    await asyncio.to_thread(workbook, "create", path)
    before = await asyncio.to_thread(workbook, "inspect", path)
    configured = agent(transport, work, pipe, skills[transport] if with_skill else None)
    prompt = (
        f"Format the existing report in {path} for readers: use a bold header, "
        "two-decimal USD amounts and percentage rates, keeping 0.45 as 45%. "
        "Make the numbers readable. Preserve the identifiers, values, total and "
        "average formulas, note, and existing structure. Save and close the workbook."
    )
    record = {
        "transport": transport,
        "with_skill": with_skill,
        "profile": profile,
        "status": "reserved",
        "passed": False,
        "tokens": None,
    }
    output = directory / f"{transport}-{with_skill}.json"
    save(output, record)
    try:
        result = await copilot_eval(configured, prompt)
        record.update(
            status="verifying",
            tokens=result.total_tokens,
            model_used=result.model_used,
            success=result.success,
            evidence_complete=result.evidence_complete,
            capture_errors=result.capture_errors,
            stop_reason=result.stop_reason,
            discovery=asdict(result.skill_discovery) if result.skill_discovery else None,
            skill_reads=sum(
                call.name == "skill" and call.success is True for call in result.all_tool_calls
            ),
        )
        save(output, record)
        assert result.evidence_complete, result.capture_errors
        assert result.success, result.error
        assert result.stop_reason not in {"timeout", "tool_budget_exceeded"}, result.stop_reason
        discovery = result.skill_discovery
        assert discovery is not None and discovery.complete and not discovery.errors
        expected = f"excel-{transport}" + ("-report-formatting" if profile == "formatting" else "")
        assert [skill.name for skill in discovery.skills if skill.enabled] == (
            [expected] if with_skill else []
        )
        check(before, await asyncio.to_thread(workbook, "inspect", path))
        record.update(status="verified", passed=True)
    except BaseException as error:
        record.update(status="unverified", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        save(output, record)
        await asyncio.to_thread(
            subprocess.run,
            [
                "pwsh",
                "-NoProfile",
                "-File",
                str(ROOT / "Close-OwnedWorkbook.ps1"),
                "-Path",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if transport == "cli":
            await asyncio.to_thread(
                subprocess.run,
                [executable("cli"), "service", "stop"],
                env={**os.environ, "EXCELMCP_CLI_PIPE": pipe},
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
