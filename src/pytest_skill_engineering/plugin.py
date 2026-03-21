"""pytest plugin for aitest."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from pytest_skill_engineering.plugin_options import add_aitest_options
from pytest_skill_engineering.plugin_recording import (
    RecordingLLMAssert,
    RecordingLLMAssertImage,
    RecordingLLMScore,
)
from pytest_skill_engineering.plugin_report import (
    build_coding_agent_prompt,
    generate_structured_insights,
    get_analysis_prompt,
    get_analysis_prompt_details,
    log_report_path,
    shutdown_copilot_model_client,
)
from pytest_skill_engineering.reporting import (
    TestReport,
    build_suite_report,
    generate_html,
    generate_json,
    generate_md,
)

if TYPE_CHECKING:
    from _pytest.config import Config
    from _pytest.config.argparsing import Parser
    from _pytest.nodes import Item
    from _pytest.reports import TestReport as PytestTestReport
    from _pytest.terminal import TerminalReporter

    from pytest_skill_engineering.core.eval import Eval
    from pytest_skill_engineering.core.result import EvalResult


# Key for storing test reports in config
COLLECTOR_KEY = pytest.StashKey[list[TestReport]]()
# Key for storing session messages for @pytest.mark.session
SESSION_MESSAGES_KEY = pytest.StashKey[dict[str, list[dict[str, Any]]]]()
# Export for use in fixtures and downstream consumers
__all__ = [
    "COLLECTOR_KEY",
    "SESSION_MESSAGES_KEY",
    "get_analysis_prompt",
    "get_analysis_prompt_details",
]


@pytest.hookimpl(hookwrapper=True)
def pytest_pyfunc_call(pyfuncitem: Item) -> Any:
    """Wrap llm_assert and llm_assert_image fixture values before test function execution."""
    funcargs = getattr(pyfuncitem, "funcargs", {})

    # Ensure assertion store exists
    store = getattr(pyfuncitem, "_aitest_assertions", None)
    if store is None:
        store = []
        pyfuncitem._aitest_assertions = store  # type: ignore[attr-defined]

    # Wrap llm_assert
    llm_assert = funcargs.get("llm_assert")
    if llm_assert is not None and not isinstance(llm_assert, RecordingLLMAssert):
        pyfuncitem.funcargs["llm_assert"] = RecordingLLMAssert(llm_assert, store)  # type: ignore[index]

    # Wrap llm_assert_image
    llm_assert_image = funcargs.get("llm_assert_image")
    if llm_assert_image is not None and not isinstance(llm_assert_image, RecordingLLMAssertImage):
        pyfuncitem.funcargs["llm_assert_image"] = RecordingLLMAssertImage(llm_assert_image, store)  # type: ignore[index]

    # Wrap llm_score
    llm_score = funcargs.get("llm_score")
    if llm_score is not None and not isinstance(llm_score, RecordingLLMScore):
        pyfuncitem.funcargs["llm_score"] = RecordingLLMScore(llm_score, store)  # type: ignore[index]

    yield


def _get_timestamped_path(
    base_name: str, test_name: str | None = None, default_dir: Path | None = None
) -> Path:
    """Generate timestamped filename for unique report names.

    Args:
        base_name: Base filename with extension (e.g., 'results.json', 'report.html')
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

    Note: LLM authentication is handled via standard environment variables:
    - Azure: AZURE_API_BASE + `az login` (Entra ID)
    - OpenAI: OPENAI_API_KEY
    - Anthropic: ANTHROPIC_API_KEY
    - etc.

    See https://ai.pydantic.dev/ for supported providers.
    """
    group = parser.getgroup("aitest", "AI agent testing")
    add_aitest_options(group)


def pytest_configure(config: Config) -> None:
    """Configure the aitest plugin."""
    # Register custom hookspecs so downstream plugins can extend behavior
    from pytest_skill_engineering.hooks import AitestHookSpec

    config.pluginmanager.add_hookspecs(AitestHookSpec)

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
    count: int = metafunc.config.getoption("--aitest-iterations", default=1)
    if count <= 1:
        return
    metafunc.fixturenames.append("_aitest_iteration")
    metafunc.parametrize(
        "_aitest_iteration",
        range(1, count + 1),
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


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item: Item, call: Any) -> Any:
    """Capture test results for reporting.

    Also auto-stashes CopilotResult for tests that call ``run_copilot()``
    directly instead of using the ``copilot_eval`` fixture — critical for
    module-scoped agent fixtures that cannot use the function-scoped fixture.
    """
    # Auto-stash CopilotResult before processing (tryfirst ensures this runs early)
    if call.when == "call" and not hasattr(item, "_aitest_result"):
        try:
            from pytest_skill_engineering.copilot.result import CopilotResult

            funcargs = getattr(item, "funcargs", {})
            for val in funcargs.values():
                if isinstance(val, CopilotResult) and val.agent is not None:
                    from pytest_skill_engineering.copilot.fixtures import stash_on_item

                    stash_on_item(item, val.agent, val)
                    break
        except ImportError:
            pass  # Copilot SDK not installed — skip auto-stashing

    outcome = yield
    report: PytestTestReport = outcome.get_result()

    # Only process call phase (not setup/teardown)
    if report.when != "call":
        return

    # Check if reporting is enabled
    tests = item.config.stash.get(COLLECTOR_KEY, None)
    if tests is None:
        return

    # Skip if marked to exclude from report
    if any(m.name == "aitest_skip_report" for m in item.iter_markers()):
        return

    # Get agent result if available
    eval_result = getattr(item, "_aitest_result", None)

    # Only collect tests that actually used aitest (have an agent result)
    # This prevents unit tests from triggering AI analysis for reports
    if eval_result is None:
        return

    # Get agent identity directly from the Eval object stashed by the fixture
    agent = getattr(item, "_aitest_agent", None)

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

    # Extract assertions recorded by the llm_assert fixture
    assertions = getattr(item, "_aitest_assertions", [])

    # Capture error message — just the assertion/exception, never raw tracebacks.
    # Tracebacks contain file paths, line numbers, and nodeids that pollute
    # AI analysis and user-facing reports.
    error_msg = None
    if report.failed:
        error_text = str(report.longrepr)
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

    # Build agent identity from the Eval object
    agent_id = agent.id if agent else ""
    if agent:
        raw = agent.provider.model
        model = raw.split("/")[-1] if "/" in raw else raw
    else:
        model = ""
    eval_name = agent.name if agent else ""
    system_prompt_name = agent.system_prompt_name if agent else None
    skill_name = agent.skill.name if agent and agent.skill else None

    # Detect iteration index from _aitest_iteration fixture
    iteration: int | None = None
    callspec = getattr(item, "callspec", None)
    if callspec and "_aitest_iteration" in callspec.params:
        iteration = callspec.params["_aitest_iteration"]

    # Create test report with typed identity fields
    test_report = TestReport(
        name=item.nodeid,
        outcome=report.outcome,
        duration_ms=report.duration * 1000,
        eval_result=eval_result,
        error=error_msg,
        assertions=assertions,
        docstring=docstring,
        class_docstring=class_docstring,
        agent_id=agent_id,
        eval_name=eval_name,
        model=model,
        system_prompt_name=system_prompt_name,
        skill_name=skill_name,
        iteration=iteration,
    )

    # Flag copilot tests for analysis prompt selection
    if any(m.name == "copilot" for m in item.iter_markers()):
        test_report._copilot_test = True

    tests.append(test_report)

    # Enrich JUnit XML with agent metadata (user_properties → <property> elements)
    _add_junit_properties(report, eval_result, agent)


def _add_junit_properties(
    report: PytestTestReport,
    eval_result: EvalResult,
    agent: Eval | None = None,
) -> None:
    """Add agent metadata to pytest report for JUnit XML output.

    Properties are added to report.user_properties which pytest writes
    as <property> elements in JUnit XML output.

    Example output:
        <testcase name="test_balance">
          <properties>
            <property name="aitest.agent.name" value="banking-agent"/>
            <property name="aitest.model" value="gpt-5-mini"/>
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
        model = agent.provider.model
        display_model = model.split("/")[-1] if "/" in model else model
        props.append(("aitest.agent.name", agent.name))
        props.append(("aitest.model", display_model))
        if agent.system_prompt_name:
            props.append(("aitest.prompt", agent.system_prompt_name))

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
    """Generate reports and enforce minimum pass rate at end of test session."""
    config = session.config
    tests = config.stash.get(COLLECTOR_KEY, None)

    if tests is None or not tests:
        return

    html_path = config.getoption("--aitest-html")
    json_path = config.getoption("--aitest-json")
    md_path = config.getoption("--aitest-md")
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

    # Always generate JSON report first (before AI analysis which may fail)
    json_output_path = Path(json_path) if json_path else default_json_path
    json_output_path.parent.mkdir(parents=True, exist_ok=True)
    generate_json(suite_report, json_output_path)
    log_report_path(config, "JSON", json_output_path)

    # Generate AI insights if HTML/MD report requested OR summary model specified
    summary_model = config.getoption("--aitest-summary-model")
    insights = None
    if html_path or md_path or summary_model:
        insights = generate_structured_insights(
            config, suite_report, required=bool(html_path or md_path)
        )

    # Update JSON with insights if analysis succeeded
    if insights is not None:
        generate_json(suite_report, json_output_path, insights=insights)

    # Generate HTML report only when explicitly requested
    if html_path:
        html_output_path = Path(html_path)
        html_output_path.parent.mkdir(parents=True, exist_ok=True)

        if insights is None:
            insights = generate_structured_insights(config, suite_report, required=True)

        assert insights is not None  # guaranteed by required=True above
        generate_html(
            suite_report, html_output_path, insights=insights, min_pass_rate=min_pass_rate
        )
        log_report_path(config, "HTML", html_output_path)

    # Generate Markdown report if requested
    if md_path:
        md_output_path = Path(md_path)
        md_output_path.parent.mkdir(parents=True, exist_ok=True)

        if insights is None:
            insights = generate_structured_insights(config, suite_report, required=True)

        assert insights is not None  # noqa: S101
        generate_md(suite_report, md_output_path, insights=insights, min_pass_rate=min_pass_rate)
        log_report_path(config, "Markdown", md_output_path)

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

    # Reset rate limiter state so long-lived processes start fresh next session
    from pytest_skill_engineering.execution.rate_limiter import reset_rate_limiters

    reset_rate_limiters()

    # Clean up shared CopilotClient if it was started for copilot/ model provider
    shutdown_copilot_model_client()


# Register fixtures from fixtures module
pytest_plugins = ["pytest_skill_engineering.fixtures"]


# ── Coding agent analysis prompt ──


@pytest.hookimpl(optionalhook=True)
def pytest_skill_engineering_analysis_prompt(config: object) -> str | None:
    """Provide coding-agent-specific analysis prompt when copilot tests are detected."""
    from _pytest.config import Config

    assert isinstance(config, Config)

    tests = config.stash.get(COLLECTOR_KEY, [])
    return build_coding_agent_prompt(tests)
