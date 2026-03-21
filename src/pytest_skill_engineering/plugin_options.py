"""CLI option definitions for the aitest pytest plugin.

Separated from ``plugin.py`` for readability. Called by
``pytest_addoption`` in the main plugin module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from _pytest.config.argparsing import OptionGroup


def add_aitest_options(group: OptionGroup) -> None:
    """Register all ``--aitest-*`` and ``--llm-*`` CLI options.

    Args:
        group: The pytest option group created for ``aitest``.
    """
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
