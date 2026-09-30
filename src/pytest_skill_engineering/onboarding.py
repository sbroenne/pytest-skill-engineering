"""First-run project setup and diagnostics."""

from __future__ import annotations

import argparse
import asyncio
import shlex
import shutil
import subprocess
import sys
from collections.abc import MutableMapping
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import tomlkit
from tomlkit.exceptions import ParseError
from tomlkit.items import Array, InlineTable, Table

from pytest_skill_engineering import __version__
from pytest_skill_engineering.copilot.client import (
    create_client,
    get_github_token,
    stop_client,
)

DEFAULT_MODEL = "gpt-5.6-sol"
STARTER_TEST_PATH = Path("tests/test_copilot_eval.py")
PRICING_PATH = Path("pricing.toml")
DEFAULT_PRICING = {"input": 5.0, "output": 30.0, "cache_read": 0.5}
REPORT_OPTIONS = ("--aitest-json=aitest-reports/results.json",)

STARTER_TEST = """\
from __future__ import annotations

import json
import sys

from pytest_skill_engineering.copilot import CopilotEval

TODO_MCP = {
    "todo": {
        "command": sys.executable,
        "args": ["-m", "pytest_skill_engineering.testing.todo_mcp"],
        "tools": ["*"],
    }
}


async def test_add_task(copilot_eval):
    agent = CopilotEval(
        name="todo-quickstart",
        model="gpt-5.6-sol",
        instructions="Use the todo tools to manage tasks.",
        mcp_servers=TODO_MCP,
    )

    result = await copilot_eval(agent, "Add a task titled exactly 'buy groceries'")

    assert result.success
    assert result.tool_was_called("todo-add_task")
    calls = result.tool_calls_for("todo-add_task")
    assert len(calls) == 1
    assert calls[0].arguments["title"] == "buy groceries"
    assert calls[0].success is True
    assert calls[0].evidence_complete
    assert calls[0].result is not None
    # The SDK includes both display text and the structured MCP string result.
    display, structured = calls[0].result.rsplit("\\n\\n", 1)
    assert json.loads(structured) == {"result": display}
    saved = json.loads(display)
    assert saved["title"] == "buy groceries"
    assert saved["completed"] is False
"""


class OnboardingError(ValueError):
    """Raised when project setup is missing or conflicts with the starter."""


@dataclass(slots=True, frozen=True)
class Check:
    """One diagnostics result."""

    name: str
    passed: bool
    detail: str


def _get_or_create_table(parent: MutableMapping[str, Any], key: str) -> Table:
    existing = parent.get(key)
    if existing is None:
        table = tomlkit.table()
        parent[key] = table
        return table
    if not isinstance(existing, Table):
        raise OnboardingError(f"pyproject.toml field '{key}' must be a table")
    return existing


def _option_key(option: str) -> str:
    return option.split("=", 1)[0]


def _merge_report_options(existing: Any) -> str | Array:
    if existing is None:
        return "\n".join(REPORT_OPTIONS)

    if isinstance(existing, str):
        tokens = shlex.split(existing)
        additions = _missing_report_options(tokens)
        if not additions:
            return existing
        separator = "\n" if "\n" in existing else " "
        return f"{existing.rstrip()}{separator}{separator.join(additions)}"

    if isinstance(existing, Array):
        tokens = [str(value) for value in existing]
        additions = _missing_report_options(tokens)
        if not additions:
            return existing
        array = tomlkit.array()
        array.multiline(True)
        array.extend([*tokens, *additions])
        return array

    raise OnboardingError("tool.pytest.ini_options.addopts must be a string or array")


def _missing_report_options(tokens: list[str]) -> list[str]:
    retired = sorted({_option_key(token) for token in tokens} & {"--aitest-html", "--aitest-md"})
    if retired:
        raise OnboardingError(
            f"Remove unsupported report options from addopts: {', '.join(retired)}. "
            "The runner saves JSON evidence; it does not render reports."
        )
    additions: list[str] = []
    for desired in REPORT_OPTIONS:
        key = _option_key(desired)
        desired_value = desired.split("=", 1)[1]
        configured_values: list[str | None] = []
        for index, token in enumerate(tokens):
            if token.startswith(f"{key}="):
                configured_values.append(token.split("=", 1)[1])
            elif token == key:
                configured_values.append(tokens[index + 1] if index + 1 < len(tokens) else None)

        if configured_values and any(value != desired_value for value in configured_values):
            configured = ", ".join(
                f"{key}={value}" if value is not None else key for value in configured_values
            )
            raise OnboardingError(
                f"tool.pytest.ini_options.addopts configures {key} differently: {configured}"
            )
        if desired_value not in configured_values:
            additions.append(desired)
    return additions


def configured_pyproject(source: str) -> str:
    """Return pyproject TOML with the starter's explicit pytest configuration."""
    try:
        document = tomlkit.parse(source)
    except ParseError as error:
        raise OnboardingError(f"pyproject.toml is invalid TOML: {error}") from error

    tool = _get_or_create_table(document, "tool")
    pytest_table = _get_or_create_table(tool, "pytest")
    ini_options = _get_or_create_table(pytest_table, "ini_options")

    asyncio_mode = ini_options.get("asyncio_mode")
    if asyncio_mode not in (None, "auto"):
        raise OnboardingError(
            "tool.pytest.ini_options.asyncio_mode conflicts with required value 'auto'"
        )
    ini_options["asyncio_mode"] = "auto"
    ini_options["addopts"] = _merge_report_options(ini_options.get("addopts"))
    return tomlkit.dumps(document)


def configured_pricing(source: str) -> str:
    """Return pricing TOML with an explicit entry for the starter model."""
    try:
        document = tomlkit.parse(source)
    except ParseError as error:
        raise OnboardingError(f"pricing.toml is invalid TOML: {error}") from error

    models = _get_or_create_table(document, "models")
    existing = models.get(DEFAULT_MODEL)
    if existing is None:
        models[DEFAULT_MODEL] = DEFAULT_PRICING
    elif not isinstance(existing, (Table, InlineTable)):
        raise OnboardingError(f"pricing.toml model '{DEFAULT_MODEL}' must be an inline table")
    return tomlkit.dumps(document)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(content)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def initialize_project(project_dir: Path) -> tuple[Path, Path, Path]:
    """Create the starter test and update an existing pyproject.toml."""
    project_dir = project_dir.resolve()
    pyproject = project_dir / "pyproject.toml"
    starter = project_dir / STARTER_TEST_PATH
    pricing = project_dir / PRICING_PATH

    if not pyproject.is_file():
        raise OnboardingError(f"pyproject.toml not found in {project_dir}")
    if starter.exists():
        raise OnboardingError(f"refusing to overwrite existing starter test: {starter}")

    original_pyproject = pyproject.read_text(encoding="utf-8")
    original_pricing = pricing.read_text(encoding="utf-8") if pricing.is_file() else None
    updated_pyproject = configured_pyproject(original_pyproject)
    updated_pricing = configured_pricing(original_pricing or "")
    _atomic_write(starter, STARTER_TEST)
    try:
        _atomic_write(pyproject, updated_pyproject)
        _atomic_write(pricing, updated_pricing)
    except Exception:
        starter.unlink(missing_ok=True)
        _atomic_write(pyproject, original_pyproject)
        if original_pricing is None:
            pricing.unlink(missing_ok=True)
        else:
            _atomic_write(pricing, original_pricing)
        raise
    return starter, pyproject, pricing


def check_project(project_dir: Path) -> list[Check]:
    """Run deterministic local project checks."""
    project_dir = project_dir.resolve()
    checks = [
        Check(
            "Python",
            sys.version_info >= (3, 11),
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        ),
        Check("Package", True, f"pytest-skill-engineering {__version__}"),
    ]

    pyproject = project_dir / "pyproject.toml"
    if not pyproject.is_file():
        checks.append(Check("Project configuration", False, f"missing {pyproject}"))
    else:
        try:
            configured = configured_pyproject(pyproject.read_text(encoding="utf-8"))
            current = pyproject.read_text(encoding="utf-8")
            if configured == current:
                checks.append(Check("Project configuration", True, str(pyproject)))
            else:
                checks.append(
                    Check(
                        "Project configuration",
                        False,
                        "starter evidence settings are missing; run pytest-skill-engineering init",
                    )
                )
        except OnboardingError as error:
            checks.append(Check("Project configuration", False, str(error)))

    starter = project_dir / STARTER_TEST_PATH
    checks.append(
        Check(
            "Starter test",
            starter.is_file(),
            str(starter) if starter.is_file() else f"missing {starter}",
        )
    )

    pricing = project_dir / PRICING_PATH
    if not pricing.is_file():
        checks.append(Check("Model pricing", False, f"missing {pricing}"))
    else:
        try:
            configured = configured_pricing(pricing.read_text(encoding="utf-8"))
            current = pricing.read_text(encoding="utf-8")
            checks.append(
                Check(
                    "Model pricing",
                    configured == current,
                    (
                        str(pricing)
                        if configured == current
                        else " ".join(
                            (
                                f"{DEFAULT_MODEL} pricing is missing;",
                                "run pytest-skill-engineering init",
                            )
                        )
                    ),
                )
            )
        except OnboardingError as error:
            checks.append(Check("Model pricing", False, str(error)))

    token = get_github_token()
    if token:
        checks.append(Check("GitHub credentials", True, "GITHUB_TOKEN or GH_TOKEN is set"))
    elif shutil.which("gh") is None:
        checks.append(Check("GitHub credentials", False, "gh is not installed and no token is set"))
    else:
        try:
            status = subprocess.run(
                ["gh", "auth", "status", "--hostname", "github.com"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            detail = (
                "GitHub CLI is authenticated" if status.returncode == 0 else status.stderr.strip()
            )
            checks.append(Check("GitHub credentials", status.returncode == 0, detail))
        except (OSError, subprocess.TimeoutExpired) as error:
            checks.append(Check("GitHub credentials", False, f"{type(error).__name__}: {error}"))
    return checks


async def check_copilot(project_dir: Path) -> Check:
    """Verify Copilot startup and availability of the starter model."""
    client = create_client(str(project_dir.resolve()))
    try:
        await asyncio.wait_for(client.start(), timeout=60)
        models = await asyncio.wait_for(client.list_models(), timeout=30)
        model_ids = {model.id for model in models}
        if DEFAULT_MODEL not in model_ids:
            return Check(
                "Copilot model",
                False,
                f"{DEFAULT_MODEL} is unavailable; available models: {', '.join(sorted(model_ids))}",
            )
        return Check("Copilot model", True, f"{DEFAULT_MODEL} is available")
    except Exception as error:
        return Check("Copilot model", False, f"{type(error).__name__}: {error}")
    finally:
        await stop_client(client)


def _print_checks(checks: list[Check]) -> bool:
    for check in checks:
        marker = "PASS" if check.passed else "FAIL"
        print(f"[{marker}] {check.name}: {check.detail}")
    return all(check.passed for check in checks)


def _run_init(project_dir: Path) -> int:
    try:
        starter, pyproject, pricing = initialize_project(project_dir)
    except (OSError, OnboardingError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(f"Created {starter}")
    print(f"Updated {pyproject}")
    print(f"Updated {pricing}")
    print(f"Run: uv run python -m pytest {STARTER_TEST_PATH} -v")
    return 0


def _run_doctor(project_dir: Path) -> int:
    checks = check_project(project_dir)
    if all(check.passed for check in checks):
        checks.append(asyncio.run(check_copilot(project_dir)))
    return 0 if _print_checks(checks) else 1


def main(argv: list[str] | None = None) -> int:
    """Run project initialization or diagnostics."""
    parser = argparse.ArgumentParser(
        prog="pytest-skill-engineering",
        description="Set up and diagnose pytest-skill-engineering projects",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, help_text in (
        ("init", "Create a starter Copilot eval and configure JSON evidence"),
        ("doctor", "Validate project setup, authentication, and Copilot model access"),
    ):
        command = subparsers.add_parser(name, help=help_text)
        command.add_argument(
            "project_dir",
            nargs="?",
            type=Path,
            default=Path.cwd(),
            help="Project directory (default: current directory)",
        )

    args = parser.parse_args(argv)
    if args.command == "init":
        return _run_init(args.project_dir)
    return _run_doctor(args.project_dir)


if __name__ == "__main__":
    raise SystemExit(main())
