"""Tests for the pytest-aitest hook system."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from pytest_aitest.hooks import AitestHookSpec


class TestAitestHookSpec:
    """Tests for the AitestHookSpec hook specification class."""

    def test_hookspec_class_exists(self) -> None:
        """AitestHookSpec is importable and has the expected hook."""
        assert hasattr(AitestHookSpec, "pytest_aitest_analysis_prompt")

    def test_hookspec_is_firstresult(self) -> None:
        """The analysis prompt hook uses firstresult=True."""
        method = AitestHookSpec.pytest_aitest_analysis_prompt
        marker = getattr(method, "pytest_spec", None)
        assert marker is not None
        assert marker.get("firstresult") is True

    def test_hookspec_exported_from_package(self) -> None:
        """AitestHookSpec is available from the top-level package."""
        from pytest_aitest import AitestHookSpec as Exported

        assert Exported is AitestHookSpec


class TestResolveAnalysisPrompt:
    """Tests for _resolve_analysis_prompt() priority chain."""

    def _make_config(
        self,
        cli_path: str | None = None,
        hook_result: str | None = None,
    ) -> Any:
        """Create a mock config with CLI option and hook result."""
        config = mock.MagicMock()
        config.getoption.return_value = cli_path

        # Mock the hook call
        config.pluginmanager.hook.pytest_aitest_analysis_prompt.return_value = hook_result

        return config

    def test_returns_none_when_no_cli_and_no_hook(self) -> None:
        """Returns None when neither CLI nor hook provides a prompt."""
        from pytest_aitest.plugin import _resolve_analysis_prompt

        config = self._make_config(cli_path=None, hook_result=None)
        result = _resolve_analysis_prompt(config)
        assert result is None

    def test_cli_option_returns_file_content(self, tmp_path: Path) -> None:
        """CLI --aitest-analysis-prompt reads and returns file content."""
        from pytest_aitest.plugin import _resolve_analysis_prompt

        prompt_file = tmp_path / "custom.md"
        prompt_file.write_text("Custom CLI prompt content", encoding="utf-8")

        config = self._make_config(cli_path=str(prompt_file))
        result = _resolve_analysis_prompt(config)
        assert result == "Custom CLI prompt content"

    def test_cli_option_missing_file_raises(self, tmp_path: Path) -> None:
        """CLI option with nonexistent file raises UsageError."""
        from pytest_aitest.plugin import _resolve_analysis_prompt

        config = self._make_config(cli_path=str(tmp_path / "nonexistent.md"))
        with pytest.raises(pytest.UsageError, match="not found"):
            _resolve_analysis_prompt(config)

    def test_hook_result_returned_when_no_cli(self) -> None:
        """Hook result is returned when CLI option is not set."""
        from pytest_aitest.plugin import _resolve_analysis_prompt

        config = self._make_config(cli_path=None, hook_result="Hook prompt text")
        result = _resolve_analysis_prompt(config)
        assert result == "Hook prompt text"

    def test_cli_takes_precedence_over_hook(self, tmp_path: Path) -> None:
        """CLI option takes precedence over hook result."""
        from pytest_aitest.plugin import _resolve_analysis_prompt

        prompt_file = tmp_path / "cli-prompt.md"
        prompt_file.write_text("CLI wins", encoding="utf-8")

        config = self._make_config(cli_path=str(prompt_file), hook_result="Hook loses")
        result = _resolve_analysis_prompt(config)
        assert result == "CLI wins"

    def test_empty_hook_result_returns_none(self) -> None:
        """Empty string from hook is treated as no result (falsy)."""
        from pytest_aitest.plugin import _resolve_analysis_prompt

        config = self._make_config(cli_path=None, hook_result="")
        result = _resolve_analysis_prompt(config)
        assert result is None


class TestGetAnalysisPrompt:
    """Tests for get_analysis_prompt() public API."""

    def _make_config(
        self,
        cli_path: str | None = None,
        hook_result: str | None = None,
    ) -> Any:
        config = mock.MagicMock()
        config.getoption.return_value = cli_path
        config.pluginmanager.hook.pytest_aitest_analysis_prompt.return_value = hook_result
        return config

    def test_returns_builtin_default_when_no_cli_and_no_hook(self) -> None:
        """Falls back to built-in prompt content when no override is configured."""
        from pytest_aitest.plugin import get_analysis_prompt
        from pytest_aitest.reporting.insights import _load_analysis_prompt

        config = self._make_config(cli_path=None, hook_result=None)
        assert get_analysis_prompt(config) == _load_analysis_prompt()

    def test_returns_hook_prompt_when_configured(self) -> None:
        """Uses hook-provided prompt when CLI override is not set."""
        from pytest_aitest.plugin import get_analysis_prompt

        config = self._make_config(cli_path=None, hook_result="Hook prompt")
        assert get_analysis_prompt(config) == "Hook prompt"

    def test_package_root_exports_get_analysis_prompt(self) -> None:
        """get_analysis_prompt is importable from package root."""
        from pytest_aitest import get_analysis_prompt as exported
        from pytest_aitest.plugin import get_analysis_prompt

        assert exported is get_analysis_prompt


class TestGetAnalysisPromptDetails:
    """Tests for get_analysis_prompt_details() API."""

    def _make_config(
        self,
        cli_path: str | None = None,
        hook_result: str | None = None,
    ) -> Any:
        config = mock.MagicMock()
        config.getoption.return_value = cli_path
        config.pluginmanager.hook.pytest_aitest_analysis_prompt.return_value = hook_result
        return config

    def test_cli_file_source_and_path(self, tmp_path: Path) -> None:
        """CLI file override returns source metadata with file path."""
        from pytest_aitest.plugin import get_analysis_prompt_details

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("CLI prompt", encoding="utf-8")
        config = self._make_config(cli_path=str(prompt_file), hook_result="Hook")

        prompt, source, path = get_analysis_prompt_details(config)
        assert prompt == "CLI prompt"
        assert source == "cli-file"
        assert path == str(prompt_file)

    def test_hook_source(self) -> None:
        """Hook override returns hook source metadata."""
        from pytest_aitest.plugin import get_analysis_prompt_details

        config = self._make_config(cli_path=None, hook_result="Hook prompt")
        prompt, source, path = get_analysis_prompt_details(config)
        assert prompt == "Hook prompt"
        assert source == "hook"
        assert path is None

    def test_package_root_exports_get_analysis_prompt_details(self) -> None:
        """get_analysis_prompt_details is importable from package root."""
        from pytest_aitest import get_analysis_prompt_details as exported
        from pytest_aitest.plugin import get_analysis_prompt_details

        assert exported is get_analysis_prompt_details


class TestInsightsPromptParameter:
    """Tests that generate_insights uses the analysis_prompt parameter."""

    def test_custom_prompt_overrides_default(self) -> None:
        """When analysis_prompt is provided, it replaces the built-in prompt."""
        from pytest_aitest.reporting.insights import _load_analysis_prompt

        default = _load_analysis_prompt()
        custom = "You are a custom analyzer."
        assert custom != default  # Sanity check

    def test_load_analysis_prompt_returns_content(self) -> None:
        """The built-in prompt file loads successfully."""
        from pytest_aitest.reporting.insights import _load_analysis_prompt

        content = _load_analysis_prompt()
        assert isinstance(content, str)
        assert len(content) > 100  # Not the minimal fallback


class TestCliAnalysisPromptArg:
    """Tests for --analysis-prompt CLI argument."""

    def test_analysis_prompt_missing_file_returns_error(self, tmp_path: Path) -> None:
        """CLI returns error when --analysis-prompt file doesn't exist."""
        from pytest_aitest.cli import main

        json_data = {
            "schema_version": "3.0",
            "name": "test",
            "timestamp": "2026-01-01",
            "duration_ms": 0,
            "tests": [],
            "passed": 0,
            "failed": 0,
            "insights": {
                "markdown_summary": "OK",
                "model": "test",
                "tokens_used": 1,
                "cost_usd": 0.0,
                "cached": True,
            },
        }
        import json

        json_path = tmp_path / "results.json"
        json_path.write_text(json.dumps(json_data))

        result = main(
            [
                str(json_path),
                "--html",
                str(tmp_path / "out.html"),
                "--summary",
                "--summary-model",
                "test-model",
                "--analysis-prompt",
                str(tmp_path / "nonexistent.md"),
            ]
        )
        assert result == 1


class TestCompactSummaryOption:
    """Tests for compact AI summary option forwarding."""

    def test_pytest_compact_option_forwarded_to_generate_insights(self) -> None:
        """_generate_structured_insights passes compact flag through to insights."""
        from pytest_aitest.plugin import _generate_structured_insights
        from pytest_aitest.reporting.collector import SuiteReport

        config = mock.MagicMock()

        options = {
            "--aitest-summary-model": "openai/gpt-5-mini",
            "--aitest-min-pass-rate": None,
            "--aitest-analysis-prompt": None,
            "--aitest-summary-compact": True,
        }

        def getoption(name: str, default: Any = None) -> Any:
            return options.get(name, default)

        config.getoption.side_effect = getoption
        config.pluginmanager.get_plugin.return_value = None
        config.pluginmanager.hook.pytest_aitest_analysis_prompt.return_value = None

        report = SuiteReport(
            name="suite",
            timestamp="2026-02-18T00:00:00",
            duration_ms=0.0,
            tests=[],
            passed=0,
            failed=0,
            skipped=0,
        )

        class _FakeResult:
            markdown_summary = "ok"
            model = "openai/gpt-5-mini"
            tokens_used = 10
            cost_usd = 0.0
            cached = False

        captured: dict[str, Any] = {}

        async def _fake_generate_insights(**kwargs: Any) -> _FakeResult:
            captured.update(kwargs)
            return _FakeResult()

        with mock.patch(
            "pytest_aitest.reporting.insights.generate_insights",
            side_effect=_fake_generate_insights,
        ):
            result = _generate_structured_insights(config, report, required=False)

        assert result is not None
        assert captured["compact"] is True

    def test_print_analysis_prompt_logs_source(self) -> None:
        """Runtime debug flag logs prompt source and path metadata."""
        from pytest_aitest.plugin import _generate_structured_insights
        from pytest_aitest.reporting.collector import SuiteReport

        config = mock.MagicMock()
        terminalreporter = mock.MagicMock()

        options = {
            "--aitest-summary-model": "openai/gpt-5-mini",
            "--aitest-min-pass-rate": None,
            "--aitest-analysis-prompt": None,
            "--aitest-summary-compact": False,
            "--aitest-print-analysis-prompt": True,
        }

        def getoption(name: str, default: Any = None) -> Any:
            return options.get(name, default)

        config.getoption.side_effect = getoption
        config.pluginmanager.get_plugin.return_value = terminalreporter
        config.pluginmanager.hook.pytest_aitest_analysis_prompt.return_value = "Hook prompt"

        report = SuiteReport(
            name="suite",
            timestamp="2026-02-18T00:00:00",
            duration_ms=0.0,
            tests=[],
            passed=0,
            failed=0,
            skipped=0,
        )

        class _FakeResult:
            markdown_summary = "ok"
            model = "openai/gpt-5-mini"
            tokens_used = 10
            cost_usd = 0.0
            cached = False

        async def _fake_generate_insights(**_: Any) -> _FakeResult:
            return _FakeResult()

        with mock.patch(
            "pytest_aitest.reporting.insights.generate_insights",
            side_effect=_fake_generate_insights,
        ):
            _generate_structured_insights(config, report, required=False)

        assert any(
            "aitest analysis prompt: source=hook" in str(call)
            for call in terminalreporter.write_line.call_args_list
        )
