"""pytest plugin for aitest."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest

from pytest_skill_engineering.plugin_options import add_aitest_options
from pytest_skill_engineering.plugin_report import (
    log_report_path,
)
from pytest_skill_engineering.reporting import (
    TestReport,
    build_suite_report,
    generate_json,
)

if TYPE_CHECKING:
    from _pytest.config import Config
    from _pytest.config.argparsing import Parser
    from _pytest.nodes import Item
    from _pytest.reports import TestReport as PytestTestReport
    from _pytest.terminal import TerminalReporter

    from pytest_skill_engineering.core.result import EvalResult


_logger = logging.getLogger(__name__)


# Key for storing test reports in config
COLLECTOR_KEY = pytest.StashKey[list[TestReport]]()
# Key for storing session messages for @pytest.mark.session
SESSION_MESSAGES_KEY = pytest.StashKey[dict[str, list[dict[str, Any]]]]()
PHASE_REPORTS_KEY = pytest.StashKey[dict[str, "PytestTestReport"]]()
# Export for use in fixtures and downstream consumers
__all__ = [
    "COLLECTOR_KEY",
    "SESSION_MESSAGES_KEY",
]


def _get_timestamped_path(
    base_name: str, test_name: str | None = None, default_dir: Path | None = None
) -> Path:
    """Generate timestamped filename for unique report names.

    Args:
        base_name: Base evidence filename with extension (e.g., 'results.json')
        test_name: Name of the test/suite to include in filename
        default_dir: Directory to store the file (default: 'aitest-reports')

    Returns:
        Path with format: {dir}/{prefix}_{test_name}_{ISO8601-timestamp}.{ext}
    """
    if default_dir is None:
        default_dir = Path("aitest-reports")

    # Use ISO8601 timestamp: YYYY-MM-DDTHH-MM-SS (seconds precision, : replaced with -)
    timestamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")

    # Sanitize test name (remove paths, lowercase, replace spaces/special chars)
    if test_name:
        # Remove file extensions and paths
        safe_name = (
            test_name.split("/")[-1].split(".")[0].lower().replace(" ", "-").replace("_", "-")
        )
    else:
        safe_name = None

    # Split filename and extension
    if "." in base_name:
        name_part, ext = base_name.rsplit(".", 1)
        if safe_name:
            filename = f"{name_part}_{safe_name}_{timestamp}.{ext}"
        else:
            filename = f"{name_part}_{timestamp}.{ext}"
    else:
        if safe_name:
            filename = f"{base_name}_{safe_name}_{timestamp}"
        else:
            filename = f"{base_name}_{timestamp}"

    return default_dir / filename


def pytest_addoption(parser: Parser) -> None:
    """Add pytest CLI options for aitest.

    Note: Copilot-authenticated runs use the GitHub CLI or ``GITHUB_TOKEN``.
    """
    group = parser.getgroup("aitest", "AI agent testing")
    add_aitest_options(group)


def pytest_configure(config: Config) -> None:
    """Configure the aitest plugin."""
    if not config.pluginmanager.hasplugin("pytest_skill_engineering.fixtures"):
        config.pluginmanager.import_plugin("pytest_skill_engineering.fixtures")

    # Register markers
    config.addinivalue_line(
        "markers",
        "aitest: Mark test as an AI agent test (optional, enables filtering with -m aitest)",
    )
    config.addinivalue_line(
        "markers",
        "aitest_skip_report: Exclude this test from AI test reports",
    )
    config.addinivalue_line(
        "markers",
        "session(name): Mark tests as part of a named session for multi-turn conversations. "
        "Tests with the same session name share conversation history automatically.",
    )
    config.addinivalue_line(
        "markers",
        "copilot: mark test as requiring GitHub Copilot SDK credentials",
    )
    config.addinivalue_line(
        "markers",
        "aitest_iteration_axis(position): internal repetition parameter-group index",
    )

    # Always initialize report collection - JSON is always generated
    config.stash[COLLECTOR_KEY] = []
    # Initialize session message storage
    config.stash[SESSION_MESSAGES_KEY] = {}


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Parametrize tests with iteration index when ``--aitest-iterations`` > 1.

    Follows the same pattern as *pytest-repeat*: the fixture name is
    appended to ``metafunc.fixturenames`` so every test function
    receives the parameter even though it does not declare the fixture
    explicitly.
    """
    count_option = metafunc.config.getoption("--aitest-iterations", default=1)
    count = count_option if isinstance(count_option, int) else 1
    if count <= 1:
        return
    metafunc.fixturenames.append("_aitest_iteration")
    existing = getattr(metafunc, "_calls", [])
    position = len(existing[0]._idlist) if existing else 0
    metafunc.parametrize(
        "_aitest_iteration",
        [
            pytest.param(i, marks=pytest.mark.aitest_iteration_axis(position))
            for i in range(1, count + 1)
        ],
        ids=[f"iter-{i}" for i in range(1, count + 1)],
        indirect=True,
    )


def pytest_collection_modifyitems(
    session: pytest.Session,
    config: Config,
    items: list[pytest.Item],
) -> None:
    """Auto-mark tests that use aitest fixtures."""
    for item in items:
        # Check if test uses any aitest fixtures
        fixturenames = getattr(item, "fixturenames", [])
        aitest_fixtures = {"copilot_eval"}
        if (aitest_fixtures & set(fixturenames)) and not any(
            m.name == "aitest" for m in item.iter_markers()
        ):
            item.add_marker(pytest.mark.aitest)


def _require_agent_string(agent: Any, *, field_name: str) -> str:
    """Read a required string from the reporting wrapper."""
    value = getattr(agent, field_name, None)
    if isinstance(value, str) and value:
        return value
    msg = f"aitest reporting agent is missing required field '{field_name}'"
    raise ValueError(msg)


def _require_provider_model(agent: Any) -> str | None:
    """Read the required provider model from the reporting wrapper."""
    provider = getattr(agent, "provider", None)
    if provider is None or not hasattr(provider, "model"):
        raise ValueError("aitest reporting agent is missing required field 'provider.model'")
    model = provider.model
    if model is None or isinstance(model, str) and model:
        return model
    raise ValueError("aitest reporting agent is missing required field 'provider.model'")


def _display_model(model: str | None) -> str | None:
    """Strip any provider prefix from a model name for display."""
    return model.split("/")[-1] if model is not None and "/" in model else model


def _build_agent_identity(
    agent: Any,
    eval_result: EvalResult,
) -> tuple[str, str, str | None, str | None, str | None]:
    """Resolve stable and human-facing identity fields for report production."""
    base_agent_id = _require_agent_string(agent, field_name="id")
    eval_name = _require_agent_string(agent, field_name="name")
    model_raw = _require_provider_model(agent)
    system_prompt_name = getattr(agent, "system_prompt_name", None)
    if system_prompt_name is not None and not isinstance(system_prompt_name, str):
        raise ValueError("aitest reporting agent field 'system_prompt_name' must be a string")

    skill_name = eval_result.skill_info.name if eval_result.skill_info else None
    if skill_name is None:
        skill = getattr(agent, "skill", None)
        if skill is not None:
            skill_name = _require_agent_string(skill, field_name="name")

    return (
        base_agent_id,
        eval_name,
        _display_model(model_raw),
        system_prompt_name,
        skill_name,
    )


def _build_case_name(item: Item) -> str:
    """Build a case identity that removes only the synthetic iteration axis."""
    callspec = getattr(item, "callspec", None)
    if callspec is None or "_aitest_iteration" not in callspec.params:
        return item.nodeid

    param_ids = list(getattr(callspec, "_idlist", []))
    axis = item.get_closest_marker("aitest_iteration_axis")
    if axis is None or len(axis.args) != 1 or type(axis.args[0]) is not int:
        raise ValueError(
            "Unable to derive case identity for "
            f"{item.nodeid!r}: repetition parameter-group identity is unavailable"
        )
    position = axis.args[0]
    if not 0 <= position < len(param_ids):
        raise ValueError(f"Invalid repetition parameter-group index for {item.nodeid!r}")
    del param_ids[position]
    base_nodeid = item.nodeid.removesuffix(f"[{callspec.id}]")
    if not param_ids:
        return base_nodeid
    return f"{base_nodeid}[{'-'.join(param_ids)}]"


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item: Item, call: Any) -> Any:
    """Capture test results for reporting.

    Also auto-stashes CopilotResult for tests that call ``run_copilot()``
    directly instead of using the ``copilot_eval`` fixture — critical for
    module-scoped agent fixtures that cannot use the function-scoped fixture.
    """
    # Auto-stash CopilotResult before processing (tryfirst ensures this runs early)
    if call.when in ("setup", "call") and not hasattr(item, "_aitest_result"):
        from pytest_skill_engineering.copilot.eval import CopilotEval
        from pytest_skill_engineering.copilot.fixtures import stash_on_item
        from pytest_skill_engineering.copilot.result import CopilotResult

        funcargs = getattr(item, "funcargs", {})
        for val in funcargs.values():
            if isinstance(val, CopilotResult) and val.agent is not None:
                stash_on_item(item, cast(CopilotEval, val.agent), val)
                break

    outcome = yield
    report: PytestTestReport = outcome.get_result()

    phases = item.stash.setdefault(PHASE_REPORTS_KEY, {})
    phases[report.when] = report

    # Check if reporting is enabled
    tests = item.config.stash.get(COLLECTOR_KEY, None)
    if tests is None:
        return

    # Skip if marked to exclude from report
    if any(m.name == "aitest_skip_report" for m in item.iter_markers()):
        return

    runs = getattr(item, "_aitest_runs", [])

    # Only collect tests that actually used aitest (have an agent result)
    # Tests without eval execution do not create eval reports.
    if not runs:
        return
    if report.when != "teardown":
        if report.when == "call":
            for eval_result, agent in runs:
                _add_junit_properties(report, eval_result, agent)
        return
    failed_phases = [phase for phase in phases.values() if phase.failed]
    skipped_phases = [phase for phase in phases.values() if phase.skipped]
    final_outcome = "failed" if failed_phases else "skipped" if skipped_phases else "passed"

    # Get test function docstring if available
    docstring = None
    func = getattr(item, "function", None)
    if func is not None and func.__doc__:
        docstring = func.__doc__

    # Get test class docstring if available
    class_docstring = None
    parent = getattr(item, "parent", None)
    if parent is not None:
        parent_obj = getattr(parent, "obj", None)
        if parent_obj is not None and hasattr(parent_obj, "__doc__") and parent_obj.__doc__:
            # Only use class docstrings (not module docstrings)
            import inspect

            if inspect.isclass(parent_obj):
                class_docstring = parent_obj.__doc__

    # Capture error message — just the assertion/exception, never raw tracebacks.
    # Tracebacks contain file paths, line numbers, and nodeids that pollute
    # User-facing reports.
    phase_errors = []
    for failed_report in failed_phases:
        error_msg = None
        error_text = str(failed_report.longrepr)
        error_lines = error_text.split("\n")

        # Extract lines starting with "E " — pytest's assertion/exception lines
        e_lines = [line.strip()[2:] for line in error_lines if line.strip().startswith("E ")]

        if e_lines:
            error_msg = "\n".join(e_lines)
        else:
            # No E-lines: grab the last non-empty line (typically "ExceptionType: message")
            for line in reversed(error_lines):
                stripped = line.strip()
                if stripped:
                    error_msg = stripped
                    break
        if error_msg is not None:
            phase_errors.append(
                error_msg if failed_report.when == "call" else f"{failed_report.when}: {error_msg}"
            )
    error_msg = "\n".join(phase_errors) or None

    # Detect iteration index from _aitest_iteration fixture
    iteration: int | None = None
    callspec = getattr(item, "callspec", None)
    if callspec and "_aitest_iteration" in callspec.params:
        iteration = callspec.params["_aitest_iteration"]

    properties = list(report.user_properties)
    for eval_result, agent in runs:
        agent_id, eval_name, model, system_prompt_name, skill_name = _build_agent_identity(
            agent, eval_result
        )
        test_report = TestReport(
            name=_build_case_name(item),
            outcome=final_outcome,
            duration_ms=(
                eval_result.duration_ms
                if len(runs) > 1
                else sum(phase.duration for phase in phases.values()) * 1000
            ),
            eval_result=eval_result,
            error=error_msg,
            properties=properties,
            docstring=docstring,
            class_docstring=class_docstring,
            agent_id=agent_id,
            eval_name=eval_name,
            model=model,
            system_prompt_name=system_prompt_name,
            skill_name=skill_name,
            iteration=iteration,
        )
        tests.append(test_report)
        _add_junit_properties(report, eval_result, agent)


def _add_junit_properties(
    report: PytestTestReport,
    eval_result: EvalResult,
    agent: Any | None = None,
) -> None:
    """Add agent metadata to pytest report for JUnit XML output.

    Properties are added to report.user_properties which pytest writes
    as <property> elements in JUnit XML output.

    Example output:
        <testcase name="test_balance">
          <properties>
            <property name="aitest.agent.name" value="banking-agent"/>
            <property name="aitest.model" value="gpt-5.6-sol"/>
            <property name="aitest.skill" value="financial-advisor"/>
            <property name="aitest.tools.called" value="get_balance,transfer"/>
          </properties>
        </testcase>
    """
    if not hasattr(report, "user_properties"):
        return

    props = []

    # Eval identity (from Eval object)
    if agent:
        agent_id, eval_name, model, system_prompt_name, _ = _build_agent_identity(
            agent, eval_result
        )
        props.append(("aitest.agent.name", eval_name))
        if model is not None:
            props.append(("aitest.model", model))
        if system_prompt_name:
            props.append(("aitest.prompt", system_prompt_name))

    # Skill
    if eval_result.skill_info:
        props.append(("aitest.skill", eval_result.skill_info.name))

    # MCP servers (from agent config)
    if agent and agent.mcp_servers:
        server_names = []
        for server in agent.mcp_servers:
            # Use server.name if available, otherwise derive from command
            name = getattr(server, "name", None)
            if not name and hasattr(server, "command") and server.command:
                name = server.command[-1].split("/")[-1].split(".")[0]
            if name:
                server_names.append(name)
        if server_names:
            props.append(("aitest.servers", ",".join(server_names)))

    # Allowed tools filter (from agent config)
    if agent and agent.allowed_tools:
        props.append(("aitest.allowed_tools", ",".join(sorted(agent.allowed_tools))))

    # Token usage
    if eval_result.token_usage:
        prompt = eval_result.token_usage.get("prompt", 0)
        completion = eval_result.token_usage.get("completion", 0)
        if prompt:
            props.append(("aitest.tokens.input", str(prompt)))
        if completion:
            props.append(("aitest.tokens.output", str(completion)))
        total = prompt + completion
        if total:
            props.append(("aitest.tokens.total", str(total)))

    # Cost
    if eval_result.cost_usd > 0:
        props.append(("aitest.cost_usd", f"{eval_result.cost_usd:.6f}"))

    # Turns
    if eval_result.turns:
        props.append(("aitest.turns", str(len(eval_result.turns))))

    # Tools called (unique, comma-separated)
    tools_called = set()
    for turn in eval_result.turns:
        for tc in turn.tool_calls:
            tools_called.add(tc.name)
    if tools_called:
        props.append(("aitest.tools.called", ",".join(sorted(tools_called))))

    # Success/failure
    props.append(("aitest.success", str(eval_result.success).lower()))

    # Add all properties to report
    report.user_properties.extend(props)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Save execution evidence and enforce the observed pytest pass-rate threshold."""
    config = session.config
    tests = config.stash.get(COLLECTOR_KEY, None)

    if tests is None or not tests:
        return

    json_path = config.getoption("--aitest-json")
    min_pass_rate: int | None = config.getoption("--aitest-min-pass-rate")

    # Extract suite docstring from first test's parent class/module
    suite_docstring = None
    if session.items:
        first_item = session.items[0]
        # Try to get docstring from test class first
        if hasattr(first_item, "parent") and first_item.parent:
            parent = first_item.parent
            # Check if parent is a class
            parent_obj = getattr(parent, "obj", None)
            if parent_obj and hasattr(parent_obj, "__doc__"):
                suite_docstring = parent_obj.__doc__
                if suite_docstring:
                    # Get first line only
                    suite_docstring = suite_docstring.strip().split("\n")[0].strip()

    # Build suite report first (to get the test name for default filenames)
    default_dir = Path("aitest-reports")
    suite_report = build_suite_report(
        tests,
        name=session.name or "pytest-skill-engineering",
        suite_docstring=suite_docstring,
    )

    # Generate default paths with test name included
    default_json_path = _get_timestamped_path(
        "results.json", test_name=suite_report.name, default_dir=default_dir
    )

    json_output_path = Path(json_path) if json_path else default_json_path
    try:
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        generate_json(suite_report, json_output_path)
    except (OSError, TypeError, ValueError) as error:
        if session.exitstatus == pytest.ExitCode.OK:
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
        terminalreporter = config.pluginmanager.get_plugin("terminalreporter")
        if terminalreporter:
            terminalreporter.write_line(
                f"\naitest: Failed to save execution evidence to {json_output_path}: {error}",
                red=True,
                bold=True,
            )
        _logger.error(
            "Failed to save execution evidence to %s; "
            "continuing with pass-rate enforcement and cleanup",
            json_output_path,
            exc_info=True,
        )
    else:
        log_report_path(config, "JSON evidence", json_output_path)

    # Enforce minimum pass rate threshold
    if min_pass_rate is not None:
        actual_rate = suite_report.pass_rate
        terminalreporter: TerminalReporter | None = config.pluginmanager.get_plugin(
            "terminalreporter"
        )
        if actual_rate < min_pass_rate:
            if terminalreporter:
                terminalreporter.write_line(
                    f"\naitest: FAILED - pass rate {actual_rate:.1f}% "
                    f"is below minimum threshold {min_pass_rate}% "
                    f"({suite_report.passed}/{suite_report.total} passed)",
                    red=True,
                    bold=True,
                )
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
        elif terminalreporter:
            terminalreporter.write_line(
                f"\naitest: pass rate {actual_rate:.1f}% meets minimum threshold {min_pass_rate}%",
            )

    # Reset global plugin/execution state without masking the main test outcome.
    from pytest_skill_engineering.execution.rate_limiter import reset_rate_limiters

    try:
        reset_rate_limiters()
    except Exception:
        _logger.warning("Rate limiter cleanup failed", exc_info=True)
