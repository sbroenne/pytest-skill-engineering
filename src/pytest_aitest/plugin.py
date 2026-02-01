"""pytest plugin for aitest."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from pytest_aitest.reporting import ReportCollector, ReportGenerator, TestReport

if TYPE_CHECKING:
    from _pytest.config import Config
    from _pytest.config.argparsing import Parser
    from _pytest.nodes import Item
    from _pytest.reports import TestReport as PytestTestReport
    from _pytest.terminal import TerminalReporter

    from pytest_aitest.reporting import SuiteReport


# Key for storing report collector in config
COLLECTOR_KEY = pytest.StashKey[ReportCollector]()


def pytest_addoption(parser: Parser) -> None:
    """Add pytest CLI options for aitest.

    Note: LLM authentication is handled by LiteLLM's standard environment variables:
    - Azure: AZURE_API_BASE + `az login` (Entra ID)
    - OpenAI: OPENAI_API_KEY
    - Anthropic: ANTHROPIC_API_KEY
    - etc.

    See https://docs.litellm.ai/docs/providers for full list.
    """
    group = parser.getgroup("aitest", "AI agent testing")

    # Model selection (used for both agent default and AI summary)
    group.addoption(
        "--aitest-model",
        default="openai/gpt-4o-mini",
        help="Default LiteLLM model for agents and AI summary (default: openai/gpt-4o-mini)",
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
        "--aitest-summary",
        action="store_true",
        default=False,
        help="Include AI-powered analysis in HTML report",
    )

    # Rate limit options
    group.addoption(
        "--aitest-rpm",
        type=int,
        default=None,
        metavar="N",
        help="Default requests per minute limit for LLM calls (enables LiteLLM rate limiting)",
    )
    group.addoption(
        "--aitest-tpm",
        type=int,
        default=None,
        metavar="N",
        help="Default tokens per minute limit for LLM calls (enables LiteLLM rate limiting)",
    )


def pytest_configure(config: Config) -> None:
    """Configure the aitest plugin."""
    # Register markers
    config.addinivalue_line(
        "markers",
        "aitest: Mark test as an AI agent test (optional, enables filtering with -m aitest)",
    )
    config.addinivalue_line(
        "markers",
        "aitest_skip_report: Exclude this test from AI test reports",
    )

    # Initialize report collector if any reporting is enabled
    html_path = config.getoption("--aitest-html")
    json_path = config.getoption("--aitest-json")
    if html_path or json_path:
        config.stash[COLLECTOR_KEY] = ReportCollector()


def pytest_collection_modifyitems(
    session: pytest.Session,
    config: Config,
    items: list[pytest.Item],
) -> None:
    """Auto-mark tests that use aitest fixtures."""
    for item in items:
        # Check if test uses any aitest fixtures
        if hasattr(item, "fixturenames"):
            aitest_fixtures = {"aitest_run", "judge", "agent_factory"}
            if aitest_fixtures & set(item.fixturenames):
                # Add aitest marker if not already present
                if not any(m.name == "aitest" for m in item.iter_markers()):
                    item.add_marker(pytest.mark.aitest)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: Item, call: Any) -> Any:
    """Capture test results for reporting."""
    outcome = yield
    report: PytestTestReport = outcome.get_result()

    # Only process call phase (not setup/teardown)
    if report.when != "call":
        return

    # Check if reporting is enabled
    collector = item.config.stash.get(COLLECTOR_KEY, None)
    if collector is None:
        return

    # Skip if marked to exclude from report
    if any(m.name == "aitest_skip_report" for m in item.iter_markers()):
        return

    # Get agent result if available
    agent_result = getattr(item, "_aitest_result", None)

    # Create test report
    test_report = TestReport(
        name=item.nodeid,
        outcome=report.outcome,
        duration_ms=report.duration * 1000,
        agent_result=agent_result,
        error=str(report.longrepr) if report.failed else None,
    )

    collector.add_test(test_report)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Generate reports at end of test session."""
    config = session.config
    collector = config.stash.get(COLLECTOR_KEY, None)

    if collector is None or not collector.tests:
        return

    html_path = config.getoption("--aitest-html")
    json_path = config.getoption("--aitest-json")

    if not html_path and not json_path:
        return

    # Build suite report
    suite_report = collector.build_suite_report(
        name=session.name or "pytest-aitest",
    )

    generator = ReportGenerator()

    # Generate AI summary if requested (before HTML so it can be embedded)
    ai_summary = None
    if html_path and config.getoption("--aitest-summary"):
        ai_summary = _generate_ai_summary(config, suite_report)

    # Generate HTML report
    if html_path:
        path = Path(html_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        generator.generate_html(suite_report, path, ai_summary=ai_summary)
        _log_report_path(config, "HTML", path)

    # Generate JSON report
    if json_path:
        path = Path(json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        generator.generate_json(suite_report, path)
        _log_report_path(config, "JSON", path)


def _log_report_path(config: Config, format_name: str, path: Path) -> None:
    """Log report path to terminal."""
    terminalreporter: TerminalReporter | None = config.pluginmanager.get_plugin("terminalreporter")
    if terminalreporter:
        terminalreporter.write_line(f"aitest {format_name} report: {path}")


def _generate_ai_summary(config: Config, report: SuiteReport) -> str | None:
    """Generate AI-powered summary of test results.

    Uses the structured AI summary prompt from prompts/ai_summary.md.
    Auto-detects single-model vs multi-model evaluation context.

    Authentication is handled by LiteLLM via standard environment variables:
    - Azure: AZURE_API_BASE + `az login` (Entra ID)
    - OpenAI: OPENAI_API_KEY
    - Anthropic: ANTHROPIC_API_KEY

    Returns the summary text or None if generation fails.
    """
    import os

    try:
        import litellm

        from pytest_aitest.prompts import get_ai_summary_prompt

        model = config.getoption("--aitest-model")

        # Load the system prompt
        system_prompt = get_ai_summary_prompt()

        # Detect evaluation context
        is_multi_model = len(report.models_used) > 1
        context_hint = (
            "**Context: Multi-Model Comparison** - Compare the models and recommend which to use."
            if is_multi_model
            else "**Context: Single-Model Evaluation** - Assess if the agent is fit for purpose."
        )

        # Build test results summary
        test_summary = "\n".join(
            [
                f"- {t.name}: {t.outcome}" + (f" ({t.error[:100]})" if t.error else "")
                for t in report.tests
            ]
        )

        # Build per-model breakdown for multi-model scenarios
        model_breakdown = ""
        if is_multi_model and report.tests:
            from collections import defaultdict

            model_stats: dict[str, dict[str, int]] = defaultdict(
                lambda: {"passed": 0, "failed": 0, "tokens": 0}
            )
            for t in report.tests:
                if t.model:
                    model_stats[t.model]["passed" if t.outcome == "passed" else "failed"] += 1
                    model_stats[t.model]["tokens"] += t.tokens_used or 0

            lines = ["**Per-Model Breakdown:**"]
            for m, stats in sorted(model_stats.items()):
                total = stats["passed"] + stats["failed"]
                rate = (stats["passed"] / total * 100) if total > 0 else 0
                lines.append(
                    f"- {m}: {rate:.0f}% ({stats['passed']}/{total}), {stats['tokens']:,} tokens"
                )
            model_breakdown = "\n".join(lines)

        models_info = (
            f"Models tested: {', '.join(report.models_used)}" if report.models_used else ""
        )
        prompts_info = (
            f"Prompts tested: {', '.join(report.prompts_used)}" if report.prompts_used else ""
        )
        files_info = f"Test files: {', '.join(report.test_files)}" if report.test_files else ""

        user_content = f"""{context_hint}

**Test Suite:** {report.name}
**Pass Rate:** {report.pass_rate:.1f}% ({report.passed}/{report.total} tests passed)
**Duration:** {report.duration_ms / 1000:.1f}s total
**Tokens Used:** {report.total_tokens:,} tokens
**Tool Calls:** {report.tool_call_count} total
{models_info}
{prompts_info}
{files_info}
{model_breakdown}

**Test Results:**
{test_summary}
"""

        # Build proper system/user messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        # Set up Azure Entra ID auth if needed (no API key in env)
        kwargs: dict = {}
        if model.startswith("azure/") and not os.environ.get("AZURE_API_KEY"):
            try:
                from litellm.secret_managers.get_azure_ad_token_provider import (
                    get_azure_ad_token_provider,
                )

                kwargs["azure_ad_token_provider"] = get_azure_ad_token_provider()
            except (ImportError, Exception):
                pass  # Fall through to let litellm handle auth

        response = litellm.completion(
            model=model,
            messages=messages,
            **kwargs,
        )

        return response.choices[0].message.content or ""
    except Exception as e:
        terminalreporter: TerminalReporter | None = config.pluginmanager.get_plugin(
            "terminalreporter"
        )
        if terminalreporter:
            terminalreporter.write_line(f"Warning: AI summary generation failed: {e}")
        return None


# Register fixtures from fixtures module
pytest_plugins = ["pytest_aitest.fixtures"]
