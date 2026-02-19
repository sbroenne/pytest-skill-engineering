"""CLI for regenerating reports from JSON data.

Usage:
    pytest-aitest-report results.json --html report.html
    pytest-aitest-report results.json --md report.md
    pytest-aitest-report results.json --html report.html --summary --summary-model azure/gpt-4.1

Configuration (in order of precedence):
    1. CLI arguments (highest)
    2. Environment variables: AITEST_SUMMARY_MODEL
    3. pyproject.toml [tool.pytest-aitest-report] section (lowest)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from pytest_aitest.reporting.collector import SuiteReport
from pytest_aitest.reporting.generator import generate_html, generate_md
from pytest_aitest.reporting.insights import InsightsResult

_logger = logging.getLogger(__name__)


def load_config_from_pyproject() -> dict[str, Any]:
    """Load configuration from pyproject.toml [tool.pytest-aitest-report] section.

    Searches for pyproject.toml in current directory and parents.
    Returns empty dict if not found or section doesn't exist.
    """
    try:
        import tomllib
    except ImportError:
        # Python < 3.11 fallback
        try:
            import tomli as tomllib  # type: ignore[import-not-found]
        except ImportError:
            return {}

    # Search for pyproject.toml
    current = Path.cwd()
    for parent in [current, *current.parents]:
        pyproject = parent / "pyproject.toml"
        if pyproject.exists():
            try:
                data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
                return data.get("tool", {}).get("pytest-aitest-report", {})
            except Exception:
                _logger.warning("Failed to parse pyproject.toml", exc_info=True)
                return {}
    return {}


def get_config_value(key: str, cli_value: Any, env_var: str) -> Any:
    """Get config value with precedence: CLI > env var > pyproject.toml."""
    # CLI takes highest precedence
    if cli_value is not None:
        return cli_value

    # Then environment variable
    env_value = os.environ.get(env_var)
    if env_value:
        return env_value

    # Finally pyproject.toml
    config = load_config_from_pyproject()
    return config.get(key)


def load_suite_report(
    json_path: Path,
) -> tuple[SuiteReport, InsightsResult | None]:
    """Load SuiteReport from JSON file.

    Returns:
        Tuple of (SuiteReport, InsightsResult or None)
    """
    data = json.loads(json_path.read_text(encoding="utf-8"))

    schema_version = data.get("schema_version")
    try:
        major = int(schema_version.split(".")[0]) if schema_version else 0
    except (ValueError, AttributeError):
        major = 0
    if major < 2:
        msg = (
            f"Unsupported schema version: {schema_version!r}. "
            "Only v2.0+ is supported. Re-run tests to generate a new JSON file."
        )
        raise ValueError(msg)

    return _load_v2_report(data)


def _load_v2_report(
    data: dict[str, Any],
) -> tuple[SuiteReport, InsightsResult | None]:
    """Load report from v2.0 schema format (current format with dataclasses).

    Returns:
        Tuple of (SuiteReport, InsightsResult or None)
    """
    from pytest_aitest.core.serialization import deserialize_suite_report

    suite_report = deserialize_suite_report(data)

    # Reconstruct InsightsResult from JSON
    insights = None
    raw_insights = data.get("insights")
    if raw_insights:
        if isinstance(raw_insights, dict) and raw_insights.get("markdown_summary"):
            insights = InsightsResult(
                markdown_summary=raw_insights["markdown_summary"],
                model=raw_insights.get("model", "unknown"),
                tokens_used=raw_insights.get("tokens_used", 0),
                cost_usd=raw_insights.get("cost_usd", 0.0),
                cached=raw_insights.get("cached", True),
            )
        elif isinstance(raw_insights, str) and raw_insights:
            insights = InsightsResult(
                markdown_summary=raw_insights,
                model="unknown",
                cached=True,
            )

    return suite_report, insights


def generate_ai_summary(
    report: SuiteReport,
    model: str,
    *,
    analysis_prompt: str | None = None,
    compact: bool = False,
) -> InsightsResult:
    """Generate AI insights for the report.

    Args:
        report: The suite report to summarize
        model: Model string (e.g., azure/gpt-4.1)
        analysis_prompt: Custom analysis prompt text (optional)
        compact: Omit full conversation for passed tests to reduce tokens

    Returns:
        InsightsResult with markdown summary and metadata
    """
    import asyncio

    from pytest_aitest.reporting.insights import generate_insights

    async def _run() -> InsightsResult:
        return await generate_insights(
            suite_report=report,
            tool_info=[],
            skill_info=[],
            prompts={},
            model=model,
            analysis_prompt=analysis_prompt,
            compact=compact,
        )

    return asyncio.run(_run())


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="pytest-aitest-report",
        description="Regenerate reports from pytest-aitest JSON data",
    )

    parser.add_argument(
        "json_file",
        type=Path,
        help="Path to JSON results file (e.g., aitest-reports/results.json)",
    )

    parser.add_argument(
        "--html",
        metavar="PATH",
        type=Path,
        help="Generate HTML report to given path",
    )

    parser.add_argument(
        "--md",
        metavar="PATH",
        type=Path,
        help="Generate Markdown report to given path",
    )

    parser.add_argument(
        "--summary",
        action="store_true",
        help="Generate AI-powered summary (requires --summary-model)",
    )

    parser.add_argument(
        "--summary-model",
        metavar="MODEL",
        help="Model for AI summary (e.g., azure/gpt-4.1, openai/gpt-4o). "
        "Can also be set via AITEST_SUMMARY_MODEL env var or pyproject.toml.",
    )

    parser.add_argument(
        "--analysis-prompt",
        metavar="PATH",
        type=Path,
        help="Path to a custom analysis prompt file for AI insights. "
        "Overrides the built-in prompt.",
    )

    parser.add_argument(
        "--compact",
        action="store_true",
        default=False,
        help="Omit full conversation turns for passed tests in AI analysis. "
        "Reduces token usage for large test suites that exceed model context limits. "
        "Failed tests always include full conversation detail.",
    )

    parser.add_argument(
        "--print-analysis-prompt",
        action="store_true",
        default=False,
        help=(
            "Print resolved analysis prompt source/path before AI summary generation "
            "(for debugging prompt overrides)."
        ),
    )

    args = parser.parse_args(argv)

    # Resolve summary-model with config precedence
    summary_model = get_config_value("summary-model", args.summary_model, "AITEST_SUMMARY_MODEL")

    # Validate arguments
    if not args.json_file.exists():
        print(f"Error: JSON file not found: {args.json_file}", file=sys.stderr)
        return 1

    if not args.html and not args.md:
        print("Error: at least one of --html or --md is required", file=sys.stderr)
        return 1

    if args.summary and not summary_model:
        print("Error: --summary requires --summary-model to be specified", file=sys.stderr)
        print("Options:", file=sys.stderr)
        print("  --summary-model azure/gpt-4.1", file=sys.stderr)
        print("  AITEST_SUMMARY_MODEL=azure/gpt-4.1", file=sys.stderr)
        print(
            "  pyproject.toml: [tool.pytest-aitest-report] summary-model = 'azure/gpt-4.1'",
            file=sys.stderr,
        )
        return 1

    # Load report from JSON
    try:
        report, existing_insights = load_suite_report(args.json_file)
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"Error: Failed to parse JSON file: {e}", file=sys.stderr)
        return 1

    # Generate AI summary if requested
    insights = existing_insights
    if args.summary:
        # Resolve analysis prompt (CLI file or built-in default)
        custom_prompt = None
        prompt_source = "built-in"
        prompt_path: str | None = None
        if args.analysis_prompt:
            if not args.analysis_prompt.exists():
                print(
                    f"Error: Analysis prompt file not found: {args.analysis_prompt}",
                    file=sys.stderr,
                )
                return 1
            custom_prompt = args.analysis_prompt.read_text(encoding="utf-8")
            prompt_source = "cli-file"
            prompt_path = str(args.analysis_prompt)
        else:
            from pytest_aitest.reporting.insights import _load_analysis_prompt

            custom_prompt = _load_analysis_prompt()

        if args.print_analysis_prompt:
            path_info = f", path={prompt_path}" if prompt_path else ""
            print(f"analysis prompt: source={prompt_source}{path_info}, chars={len(custom_prompt)}")

        print(f"Generating AI summary with {summary_model}...")
        try:
            insights = generate_ai_summary(
                report, summary_model, analysis_prompt=custom_prompt, compact=args.compact
            )
            print("AI summary generated successfully.")
        except Exception as e:
            print(f"Warning: Failed to generate AI summary: {e}", file=sys.stderr)
            insights = existing_insights

    # AI insights are mandatory for all report formats
    if insights is None:
        print(
            "Error: AI insights are required for report generation. "
            "Use --summary --summary-model to generate them, "
            "or use a JSON file that already contains insights.",
            file=sys.stderr,
        )
        return 1

    # Generate reports
    if args.html:
        args.html.parent.mkdir(parents=True, exist_ok=True)
        generate_html(report, args.html, insights=insights)
        print(f"HTML report: {args.html}")

    if args.md:
        args.md.parent.mkdir(parents=True, exist_ok=True)
        generate_md(report, args.md, insights=insights)
        print(f"Markdown report: {args.md}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
