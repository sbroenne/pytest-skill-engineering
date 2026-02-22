"""pytest plugin for aitest."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

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
    from pytest_skill_engineering.reporting import SuiteReport
    from pytest_skill_engineering.reporting.insights import InsightsResult


# Key for storing test reports in config
COLLECTOR_KEY = pytest.StashKey[list[TestReport]]()
# Key for storing session messages for @pytest.mark.session
SESSION_MESSAGES_KEY = pytest.StashKey[dict[str, list[dict[str, Any]]]]()
# Export for use in fixtures
__all__ = ["COLLECTOR_KEY", "SESSION_MESSAGES_KEY"]


class _RecordingLLMAssert:
    """Wrapper that records LLM assertions for report rendering."""

    def __init__(self, inner: Any, store: list[dict[str, Any]]) -> None:
        self._inner = inner
        self._store = store

    def __call__(self, content: str, criterion: str) -> Any:
        result = self._inner(content, criterion)
        self._store.append(
            {
                "type": "llm",
                "passed": bool(result),
                "message": result.criterion,
                "details": result.reasoning,
            }
        )
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class _RecordingLLMAssertImage:
    """Wrapper that records LLM image assertions for report rendering."""

    def __init__(self, inner: Any, store: list[dict[str, Any]]) -> None:
        self._inner = inner
        self._store = store

    def __call__(self, image: Any, criterion: str, **kwargs: Any) -> Any:
        result = self._inner(image, criterion, **kwargs)
        self._store.append(
            {
                "type": "llm_image",
                "passed": bool(result),
                "message": result.criterion,
                "details": result.reasoning,
            }
        )
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class _RecordingLLMScore:
    """Wrapper that records multi-dimension LLM scores for report rendering."""

    def __init__(self, inner: Any, store: list[dict[str, Any]]) -> None:
        self._inner = inner
        self._store = store

    def _record(self, result: Any, rubric: Any) -> Any:
        """Store score data including per-dimension detail."""
        dimensions = []
        for dim in rubric:
            dimensions.append(
                {
                    "name": dim.name,
                    "score": result.scores.get(dim.name, 0),
                    "max_score": dim.max_score,
                    "weight": dim.weight,
                }
            )
        self._store.append(
            {
                "type": "llm_score",
                "passed": True,  # scoring always succeeds; thresholds checked via assert_score
                "message": f"{result.total}/{result.max_total} ({result.weighted_score:.0%})",
                "details": result.reasoning,
                "dimensions": dimensions,
                "total": result.total,
                "max_total": result.max_total,
                "weighted_score": result.weighted_score,
            }
        )
        return result

    def __call__(self, content: str, rubric: Any, **kwargs: Any) -> Any:
        result = self._inner(content, rubric, **kwargs)
        return self._record(result, rubric)

    async def async_score(self, content: str, rubric: Any, **kwargs: Any) -> Any:
        result = await self._inner.async_score(content, rubric, **kwargs)
        return self._record(result, rubric)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


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
    if llm_assert is not None and not isinstance(llm_assert, _RecordingLLMAssert):
        pyfuncitem.funcargs["llm_assert"] = _RecordingLLMAssert(llm_assert, store)  # type: ignore[index]

    # Wrap llm_assert_image
    llm_assert_image = funcargs.get("llm_assert_image")
    if llm_assert_image is not None and not isinstance(llm_assert_image, _RecordingLLMAssertImage):
        pyfuncitem.funcargs["llm_assert_image"] = _RecordingLLMAssertImage(llm_assert_image, store)  # type: ignore[index]

    # Wrap llm_score
    llm_score = funcargs.get("llm_score")
    if llm_score is not None and not isinstance(llm_score, _RecordingLLMScore):
        pyfuncitem.funcargs["llm_score"] = _RecordingLLMScore(llm_score, store)  # type: ignore[index]

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

    # Model selection for AI summary (use the most capable model you can afford)
    group.addoption(
        "--aitest-summary-model",
        default=None,
        help=(
            "Model for AI analysis. Required when generating reports. "
            "Use the most capable model you can afford (e.g., gpt-5.1-chat, claude-opus-4)."
        ),
    )

    # Custom analysis prompt file
    group.addoption(
        "--aitest-analysis-prompt",
        metavar="PATH",
        default=None,
        help=(
            "Path to a custom analysis prompt file for AI insights. "
            "Overrides the built-in prompt and any plugin-provided prompt."
        ),
    )

    group.addoption(
        "--aitest-summary-compact",
        action="store_true",
        default=False,
        help=(
            "Omit full conversation turns for passed tests in AI analysis. "
            "Reduces token usage and prompt size for large suites. "
            "Failed tests still include full conversation detail."
        ),
    )

    group.addoption(
        "--aitest-print-analysis-prompt",
        action="store_true",
        default=False,
        help=(
            "Print resolved AI analysis prompt source/path at runtime "
            "(for debugging prompt overrides)."
        ),
    )

    # Report options
    group.addoption(
        "--aitest-html",
        metavar="PATH",
        default=None,
        help="Generate HTML report to given path (e.g., report.html)",
    )
    group.addoption(
        "--aitest-json",
        metavar="PATH",
        default=None,
        help="Generate JSON report to given path (e.g., results.json)",
    )
    group.addoption(
        "--aitest-md",
        metavar="PATH",
        default=None,
        help="Generate Markdown report to given path (e.g., report.md)",
    )
    group.addoption(
        "--aitest-min-pass-rate",
        metavar="N",
        type=int,
        default=None,
        help=(
            "Minimum pass rate threshold (0-100). If the overall pass rate falls below "
            "this percentage, the test session exits with failure. "
            "Example: --aitest-min-pass-rate=80"
        ),
    )

    # Iteration support for statistical baselines
    group.addoption(
        "--aitest-iterations",
        metavar="N",
        type=int,
        default=1,
        help=(
            "Run each test N times and aggregate results across iterations. "
            "Useful for establishing stable baselines with noisy AI tests. "
            "Example: --aitest-iterations=3"
        ),
    )

    # LLM judge model for llm_assert fixture
    group.addoption(
        "--llm-model",
        default="openai/gpt-5-mini",
        help=(
            "Model for llm_assert semantic assertions. "
            "Defaults to --aitest-summary-model if set, otherwise openai/gpt-5-mini."
        ),
    )

    # Vision model for llm_assert_image fixture
    group.addoption(
        "--llm-vision-model",
        default=None,
        help=(
            "Vision-capable model for llm_assert_image assertions. "
            "Defaults to --llm-model if not set. "
            "Use a model that supports image input (e.g., gpt-4o, claude-sonnet-4)."
        ),
    )


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
        aitest_fixtures = {"eval_run", "copilot_eval"}
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
        test_report._copilot_test = True  # type: ignore[attr-defined]

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
    _log_report_path(config, "JSON", json_output_path)

    # Generate AI insights if HTML/MD report requested OR summary model specified
    summary_model = config.getoption("--aitest-summary-model")
    insights = None
    if html_path or md_path or summary_model:
        insights = _generate_structured_insights(
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
            insights = _generate_structured_insights(config, suite_report, required=True)

        assert insights is not None  # guaranteed by required=True above
        generate_html(
            suite_report, html_output_path, insights=insights, min_pass_rate=min_pass_rate
        )
        _log_report_path(config, "HTML", html_output_path)

    # Generate Markdown report if requested
    if md_path:
        md_output_path = Path(md_path)
        md_output_path.parent.mkdir(parents=True, exist_ok=True)

        if insights is None:
            insights = _generate_structured_insights(config, suite_report, required=True)

        assert insights is not None  # noqa: S101
        generate_md(suite_report, md_output_path, insights=insights, min_pass_rate=min_pass_rate)
        _log_report_path(config, "Markdown", md_output_path)

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

    # Clean up shared CopilotClient if it was started for copilot/ model provider
    _shutdown_copilot_model_client()


def _shutdown_copilot_model_client() -> None:
    """Shut down the shared CopilotClient if it was started."""
    try:
        from pytest_skill_engineering.copilot.model import _client, shutdown_copilot_model_client

        if _client is not None:
            import asyncio

            try:
                loop = asyncio.get_event_loop()
                if not loop.is_closed() and not loop.is_running():
                    loop.run_until_complete(shutdown_copilot_model_client())
                    return
            except RuntimeError:
                pass
            # Fallback: create a new event loop if the existing one is unusable
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(shutdown_copilot_model_client())
            finally:
                loop.close()
    except ImportError:
        pass


def _log_report_path(config: Config, format_name: str, path: Path) -> None:
    """Log report path to terminal."""
    terminalreporter: TerminalReporter | None = config.pluginmanager.get_plugin("terminalreporter")
    if terminalreporter:
        terminalreporter.write_line(f"aitest {format_name} report: {path}")


def _resolve_analysis_prompt(config: Config) -> str | None:
    """Resolve the analysis prompt from CLI option, plugin hook, or default.

    Priority: CLI option > plugin hook > None (let insights.py use built-in).
    """
    # 1. CLI option takes highest precedence
    prompt_path = config.getoption("--aitest-analysis-prompt", default=None)
    if prompt_path:
        path = Path(prompt_path)
        if not path.exists():
            raise pytest.UsageError(f"Analysis prompt file not found: {path}")
        return path.read_text(encoding="utf-8")

    # 2. Plugin hook (firstresult=True — first non-None wins)
    result = config.pluginmanager.hook.pytest_skill_engineering_analysis_prompt(config=config)
    if result:
        return result

    # 3. Fall back to built-in default (None signals insights.py to use its default)
    return None


def get_analysis_prompt_details(config: Config) -> tuple[str, str, str | None]:
    """Get effective analysis prompt text and metadata for current config.

    Returns:
        tuple of ``(prompt_text, source, path)`` where:
        - ``source`` is one of: ``cli-file``, ``hook``, ``built-in``
        - ``path`` is set only when source is ``cli-file``
    """
    prompt_path = config.getoption("--aitest-analysis-prompt", default=None)
    if prompt_path:
        path = Path(prompt_path)
        if not path.exists():
            raise pytest.UsageError(f"Analysis prompt file not found: {path}")
        return path.read_text(encoding="utf-8"), "cli-file", str(path)

    result = config.pluginmanager.hook.pytest_skill_engineering_analysis_prompt(config=config)
    if result:
        return result, "hook", None

    from pytest_skill_engineering.reporting.insights import _load_analysis_prompt

    return _load_analysis_prompt(), "built-in", None


def get_analysis_prompt(config: Config) -> str:
    """Get the effective analysis prompt text for the current pytest config.

    Resolution order:
    1. ``--aitest-analysis-prompt`` file content
    2. ``pytest_skill_engineering_analysis_prompt`` hook result
    3. Built-in default prompt from ``prompts/ai_summary.md``
    """
    prompt, _, _ = get_analysis_prompt_details(config)
    return prompt


def _generate_structured_insights(
    config: Config, report: SuiteReport, *, required: bool = False
) -> InsightsResult | None:
    """Generate structured AI insights from test results.

    Args:
        config: pytest config
        report: Suite report with test results
        required: If True, raise error when model not configured (for report generation)

    Returns:
        InsightsResult or None if generation fails/skipped.

    Raises:
        pytest.UsageError: If required=True and model not configured.
    """
    import asyncio

    try:
        from pytest_skill_engineering.reporting.insights import generate_insights

        # Require dedicated summary model - no fallback
        model = config.getoption("--aitest-summary-model")
        if not model:
            if required:
                raise pytest.UsageError(
                    "AI analysis is required for report generation.\n"
                    "Please specify --aitest-summary-model with a capable model.\n"
                    "Example: --aitest-summary-model=azure/gpt-4.1\n"
                    "         --aitest-summary-model=openai/gpt-4o"
                )
            return None

        # Collect tool info and skill info from test results
        tool_info: list[Any] = []
        skill_info: list[Any] = []
        mcp_prompt_info: list[Any] = []
        custom_agent_info: list[Any] = []
        prompt_names: list[str] = []
        instruction_file_info: list[Any] = []
        prompts: dict[str, str] = {}

        for test in report.tests:
            if test.eval_result:
                # Collect tools (deduplicate by name)
                seen_tools = {t.name for t in tool_info}
                for t in getattr(test.eval_result, "available_tools", []) or []:
                    if t.name not in seen_tools:
                        tool_info.append(t)
                        seen_tools.add(t.name)

                # Collect MCP prompts (deduplicate by name)
                seen_mcp_prompts = {p.name for p in mcp_prompt_info}
                for p in getattr(test.eval_result, "mcp_prompts", []) or []:
                    if p.name not in seen_mcp_prompts:
                        mcp_prompt_info.append(p)
                        seen_mcp_prompts.add(p.name)

                # Collect skills (deduplicate by name)
                skill = getattr(test.eval_result, "skill_info", None)
                if skill and skill.name not in {s.name for s in skill_info}:
                    skill_info.append(skill)

                # Collect custom agent info (deduplicate by name)
                ca = getattr(test.eval_result, "custom_agent_info", None)
                if ca and ca.name not in {c.name for c in custom_agent_info}:
                    custom_agent_info.append(ca)

                # Collect prompt names used
                pn = getattr(test.eval_result, "prompt_name", None)
                if pn and pn not in prompt_names:
                    prompt_names.append(pn)

                # Collect instruction file info (deduplicate by name)
                for inf in getattr(test.eval_result, "instruction_files", []) or []:
                    if inf.name not in {i.name for i in instruction_file_info}:
                        instruction_file_info.append(inf)

                # Collect effective system prompts as prompt variants
                effective_prompt = getattr(test.eval_result, "effective_system_prompt", "")
                if effective_prompt:
                    prompt_label = test.system_prompt_name or "default"
                    if prompt_label not in prompts:
                        prompts[prompt_label] = effective_prompt

        # Generate insights using async function
        analysis_prompt, prompt_source, prompt_path = get_analysis_prompt_details(config)

        terminalreporter: TerminalReporter | None = config.pluginmanager.get_plugin(
            "terminalreporter"
        )
        if config.getoption("--aitest-print-analysis-prompt") and terminalreporter:
            path_info = f", path={prompt_path}" if prompt_path else ""
            terminalreporter.write_line(
                f"aitest analysis prompt: source={prompt_source}{path_info}, "
                f"chars={len(analysis_prompt)}"
            )

        async def _run() -> InsightsResult:
            return await generate_insights(
                suite_report=report,
                tool_info=tool_info,
                skill_info=skill_info,
                mcp_prompt_info=mcp_prompt_info,
                custom_agent_info=custom_agent_info,
                prompt_names=prompt_names,
                instruction_file_info=instruction_file_info,
                prompts=prompts,
                model=model,
                min_pass_rate=config.getoption("--aitest-min-pass-rate"),
                analysis_prompt=analysis_prompt,
                compact=config.getoption("--aitest-summary-compact"),
            )

        # Use asyncio.run() instead of deprecated get_event_loop().run_until_complete()
        result = asyncio.run(_run())

        # Log generation stats
        if terminalreporter:
            tokens_str = f"{result.tokens_used:,}" if result.tokens_used else "N/A"
            cost_str = f"${result.cost_usd:.4f}" if result.cost_usd else "N/A"
            cached_str = " (cached)" if result.cached else ""
            terminalreporter.write_line(
                f"\nAI Insights generated{cached_str}: {tokens_str} tokens, {cost_str}"
            )

        return result

    except pytest.UsageError:
        # Re-raise configuration errors
        raise
    except Exception as e:
        terminalreporter: TerminalReporter | None = config.pluginmanager.get_plugin(
            "terminalreporter"
        )
        if required:
            msg = (
                f"AI analysis failed (required for report generation): {e}\n"
                "JSON results were saved. Regenerate reports from JSON:\n"
                "  pytest-skill-engineering-report <json-path> --html report.html --summary"
            )
            if terminalreporter:
                terminalreporter.write_line(f"\nERROR: {msg}", red=True, bold=True)
            raise pytest.UsageError(msg) from e
        if terminalreporter:
            terminalreporter.write_line(f"Warning: AI insights generation failed: {e}")
        return None


# Register fixtures from fixtures module
pytest_plugins = ["pytest_skill_engineering.fixtures"]


# ── Coding agent analysis prompt ──

_CODING_AGENT_ANALYSIS_PROMPT_PATH = Path(__file__).parent / "prompts" / "coding_agent_analysis.md"


@pytest.hookimpl(optionalhook=True)
def pytest_skill_engineering_analysis_prompt(config: object) -> str | None:
    """Provide coding-agent-specific analysis prompt when copilot tests are detected.

    Checks if any collected tests use the ``copilot_eval`` fixture. If so,
    returns the coding agent analysis prompt instead of the default MCP/tool
    prompt.

    The ``{{PRICING_TABLE}}`` placeholder is replaced with a live
    pricing table built from litellm's ``model_cost`` data.
    """
    from _pytest.config import Config

    assert isinstance(config, Config)

    # Only activate if copilot tests were collected
    tests = config.stash.get(COLLECTOR_KEY, [])
    has_copilot_tests = any(getattr(t, "_copilot_test", False) for t in tests)
    if not has_copilot_tests:
        return None

    if _CODING_AGENT_ANALYSIS_PROMPT_PATH.exists():
        prompt = _CODING_AGENT_ANALYSIS_PROMPT_PATH.read_text(encoding="utf-8")
        if "{{PRICING_TABLE}}" in prompt:
            prompt = prompt.replace("{{PRICING_TABLE}}", _build_pricing_table())
        return prompt
    return None


def _build_pricing_table() -> str:
    """Build a markdown pricing table from litellm's model_cost map.

    Returns a table of common coding-agent models with their per-token
    pricing, pulled live from litellm so it stays current.
    """
    try:
        from litellm import model_cost  # type: ignore[reportMissingImports]
    except ImportError:
        return "*Pricing data unavailable (litellm not installed).*"

    # Models we care about — bare names (no provider prefix).
    models_of_interest = [
        "gpt-4.1-nano",
        "gpt-5-nano",
        "gpt-4.1-mini",
        "gpt-5-mini",
        "gpt-4.1",
        "gpt-5",
        "gpt-5.1",
        "gpt-5.2",
        "claude-sonnet-4",
        "claude-sonnet-4-5",
        "claude-opus-4-5",
        "claude-opus-4-6",
        "gpt-5-pro",
        "gpt-5.2-pro",
    ]

    rows: list[str] = []
    for name in models_of_interest:
        info = model_cost.get(name) or model_cost.get(f"azure/{name}", {})
        ic = info.get("input_cost_per_token", 0) or 0
        oc = info.get("output_cost_per_token", 0) or 0
        if ic == 0 and oc == 0:
            continue
        rows.append(f"| {name} | ${ic * 1_000_000:.2f} | ${oc * 1_000_000:.2f} |")

    if not rows:
        return "*No model pricing data available from litellm.*"

    header = (
        "**Model pricing reference** ($/M tokens, from litellm):\n\n"
        "| Model | Input $/M | Output $/M |\n"
        "|-------|-----------|------------|\n"
    )
    return header + "\n".join(rows)
