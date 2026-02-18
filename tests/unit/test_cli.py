"""Tests for CLI report regeneration."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest import mock

from pytest_aitest.cli import (
    get_config_value,
    load_config_from_pyproject,
    load_suite_report,
    main,
)
from pytest_aitest.reporting.collector import SuiteReport


class TestConfigLoading:
    """Tests for configuration loading from pyproject.toml and env vars."""

    def test_cli_value_takes_precedence(self) -> None:
        with mock.patch.dict(os.environ, {"AITEST_SUMMARY_MODEL": "env-model"}):
            result = get_config_value("summary-model", "cli-model", "AITEST_SUMMARY_MODEL")
            assert result == "cli-model"

    def test_env_var_over_pyproject(self, tmp_path: Path, monkeypatch: mock.MagicMock) -> None:
        # Create pyproject.toml
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.pytest-aitest-report]\nsummary-model = "toml-model"')

        monkeypatch.chdir(tmp_path)
        with mock.patch.dict(os.environ, {"AITEST_SUMMARY_MODEL": "env-model"}):
            result = get_config_value("summary-model", None, "AITEST_SUMMARY_MODEL")
            assert result == "env-model"

    def test_pyproject_fallback(self, tmp_path: Path, monkeypatch: mock.MagicMock) -> None:
        # Create pyproject.toml
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.pytest-aitest-report]\nsummary-model = "toml-model"')

        monkeypatch.chdir(tmp_path)
        # Clear env var if set
        env = {k: v for k, v in os.environ.items() if k != "AITEST_SUMMARY_MODEL"}
        with mock.patch.dict(os.environ, env, clear=True):
            result = get_config_value("summary-model", None, "AITEST_SUMMARY_MODEL")
            assert result == "toml-model"

    def test_returns_none_when_not_configured(
        self, tmp_path: Path, monkeypatch: mock.MagicMock
    ) -> None:
        monkeypatch.chdir(tmp_path)
        env = {k: v for k, v in os.environ.items() if k != "AITEST_SUMMARY_MODEL"}
        with mock.patch.dict(os.environ, env, clear=True):
            result = get_config_value("summary-model", None, "AITEST_SUMMARY_MODEL")
            assert result is None

    def test_load_config_no_pyproject(self, tmp_path: Path, monkeypatch: mock.MagicMock) -> None:
        monkeypatch.chdir(tmp_path)
        result = load_config_from_pyproject()
        assert result == {}


class TestLoadSuiteReport:
    """Tests for loading SuiteReport from JSON."""

    def test_load_v2_report(self, tmp_path: Path) -> None:
        json_data = {
            "schema_version": "3.0",
            "name": "test-suite",
            "timestamp": "2026-01-31T12:00:00Z",
            "duration_ms": 1000.0,
            "passed": 2,
            "failed": 1,
            "skipped": 0,
            "tests": [
                {
                    "name": "test_a",
                    "outcome": "passed",
                    "duration_ms": 100.0,
                    "agent_id": "a1",
                    "agent_name": "a1",
                    "model": "gpt-5-mini",
                },
                {
                    "name": "test_b",
                    "outcome": "passed",
                    "duration_ms": 200.0,
                    "agent_id": "a1",
                    "agent_name": "a1",
                    "model": "gpt-5-mini",
                },
                {
                    "name": "test_c",
                    "outcome": "failed",
                    "duration_ms": 300.0,
                    "agent_id": "a1",
                    "agent_name": "a1",
                    "model": "gpt-5-mini",
                },
            ],
        }
        json_path = tmp_path / "results.json"
        json_path.write_text(json.dumps(json_data))

        report, insights = load_suite_report(json_path)

        assert isinstance(report, SuiteReport)
        assert report.name == "test-suite"
        assert report.passed == 2
        assert report.failed == 1
        assert len(report.tests) == 3
        assert insights is None

    def test_load_report_with_insights(self, tmp_path: Path) -> None:
        json_data = {
            "schema_version": "3.0",
            "name": "test-suite",
            "timestamp": "2026-01-31T12:00:00Z",
            "duration_ms": 1000.0,
            "passed": 1,
            "failed": 0,
            "skipped": 0,
            "tests": [],
            "insights": {
                "markdown_summary": "All tests passed successfully.",
                "cost_usd": 0.01,
                "tokens_used": 500,
                "cached": False,
            },
        }
        json_path = tmp_path / "results.json"
        json_path.write_text(json.dumps(json_data))

        report, insights = load_suite_report(json_path)

        assert insights is not None
        assert insights.markdown_summary == "All tests passed successfully."
        assert insights.cost_usd == 0.01

    def test_load_legacy_format_raises(self, tmp_path: Path) -> None:
        """Legacy format (no schema_version) is no longer supported."""
        json_data = {
            "name": "old-suite",
            "timestamp": "2025-01-01",
            "duration_ms": 100.0,
            "tests": [],
        }
        json_path = tmp_path / "results.json"
        json_path.write_text(json.dumps(json_data))

        import pytest

        with pytest.raises(ValueError, match="Unsupported schema version"):
            load_suite_report(json_path)


class TestMainCLI:
    """Tests for main CLI entry point."""

    def test_missing_json_file(self, tmp_path: Path) -> None:
        result = main([str(tmp_path / "nonexistent.json"), "--html", "out.html"])
        assert result == 1  # Error exit code

    def test_no_output_format(self, tmp_path: Path) -> None:
        json_path = tmp_path / "results.json"
        json_path.write_text(
            json.dumps(
                {
                    "schema_version": "3.0",
                    "name": "test",
                    "timestamp": "2026-01-01",
                    "duration_ms": 0,
                    "tests": [],
                    "passed": 0,
                    "failed": 0,
                }
            )
        )

        result = main([str(json_path)])
        assert result == 1  # Error: no output format specified

    def test_summary_without_model(self, tmp_path: Path) -> None:
        json_path = tmp_path / "results.json"
        json_path.write_text(
            json.dumps(
                {
                    "schema_version": "3.0",
                    "name": "test",
                    "timestamp": "2026-01-01",
                    "duration_ms": 0,
                    "tests": [],
                    "passed": 0,
                    "failed": 0,
                }
            )
        )

        result = main([str(json_path), "--html", "out.html", "--summary"])
        assert result == 1  # Error: --summary requires --summary-model

    def test_generate_html(self, tmp_path: Path) -> None:
        json_data = {
            "schema_version": "3.0",
            "name": "test-suite",
            "timestamp": "2026-01-31T12:00:00Z",
            "duration_ms": 100.0,
            "passed": 1,
            "failed": 0,
            "skipped": 0,
            "tests": [
                {
                    "name": "test_a",
                    "outcome": "passed",
                    "duration_ms": 100.0,
                    "agent_id": "test-agent",
                    "agent_name": "test-agent",
                    "model": "test-model",
                }
            ],
            "insights": {
                "markdown_summary": "All tests passed.",
                "model": "test-model",
                "tokens_used": 100,
                "cost_usd": 0.001,
                "cached": True,
            },
        }
        json_path = tmp_path / "results.json"
        json_path.write_text(json.dumps(json_data), encoding="utf-8")
        html_path = tmp_path / "report.html"

        result = main([str(json_path), "--html", str(html_path)])

        assert result == 0
        assert html_path.exists()
        assert "test-suite" in html_path.read_text(encoding="utf-8")

    def test_no_insights_returns_error(self, tmp_path: Path) -> None:
        """Report generation fails when JSON has no AI insights."""
        json_data = {
            "schema_version": "3.0",
            "name": "test-suite",
            "timestamp": "2026-01-31T12:00:00Z",
            "duration_ms": 100.0,
            "passed": 1,
            "failed": 0,
            "skipped": 0,
            "tests": [
                {
                    "name": "test_a",
                    "outcome": "passed",
                    "duration_ms": 100.0,
                    "agent_id": "test-agent",
                    "agent_name": "test-agent",
                    "model": "test-model",
                }
            ],
        }
        json_path = tmp_path / "results.json"
        json_path.write_text(json.dumps(json_data), encoding="utf-8")
        html_path = tmp_path / "report.html"

        result = main([str(json_path), "--html", str(html_path)])

        assert result == 1
        assert not html_path.exists()

    def test_compact_flag_forwarded_to_summary_generation(self, tmp_path: Path) -> None:
        """CLI forwards --compact to generate_ai_summary when --summary is used."""
        json_data = {
            "schema_version": "3.0",
            "name": "test-suite",
            "timestamp": "2026-01-31T12:00:00Z",
            "duration_ms": 100.0,
            "passed": 1,
            "failed": 0,
            "skipped": 0,
            "tests": [
                {
                    "name": "test_a",
                    "outcome": "passed",
                    "duration_ms": 100.0,
                    "agent_id": "test-agent",
                    "agent_name": "test-agent",
                    "model": "test-model",
                }
            ],
            "insights": {
                "markdown_summary": "Existing insights",
                "model": "test-model",
                "tokens_used": 10,
                "cost_usd": 0.0,
                "cached": True,
            },
        }
        json_path = tmp_path / "results.json"
        json_path.write_text(json.dumps(json_data), encoding="utf-8")
        html_path = tmp_path / "report.html"

        with mock.patch("pytest_aitest.cli.generate_ai_summary") as mock_summary:
            mock_summary.return_value = mock.MagicMock(
                markdown_summary="Fresh insights",
                model="test-model",
                tokens_used=100,
                cost_usd=0.0,
                cached=False,
            )

            result = main(
                [
                    str(json_path),
                    "--html",
                    str(html_path),
                    "--summary",
                    "--summary-model",
                    "test-model",
                    "--compact",
                ]
            )

        assert result == 0
        assert mock_summary.call_args.kwargs["compact"] is True

    def test_print_analysis_prompt_uses_builtin_source(self, tmp_path: Path, capsys) -> None:
        """CLI can print built-in prompt source metadata."""
        json_data = {
            "schema_version": "3.0",
            "name": "test-suite",
            "timestamp": "2026-01-31T12:00:00Z",
            "duration_ms": 100.0,
            "passed": 1,
            "failed": 0,
            "skipped": 0,
            "tests": [],
            "insights": {
                "markdown_summary": "Existing insights",
                "model": "test-model",
                "tokens_used": 10,
                "cost_usd": 0.0,
                "cached": True,
            },
        }
        json_path = tmp_path / "results.json"
        json_path.write_text(json.dumps(json_data), encoding="utf-8")
        html_path = tmp_path / "report.html"

        with mock.patch("pytest_aitest.cli.generate_ai_summary") as mock_summary:
            mock_summary.return_value = mock.MagicMock(
                markdown_summary="Fresh insights",
                model="test-model",
                tokens_used=100,
                cost_usd=0.0,
                cached=False,
            )

            result = main(
                [
                    str(json_path),
                    "--html",
                    str(html_path),
                    "--summary",
                    "--summary-model",
                    "test-model",
                    "--print-analysis-prompt",
                ]
            )

        captured = capsys.readouterr()
        assert result == 0
        assert "analysis prompt: source=built-in" in captured.out

    def test_print_analysis_prompt_uses_cli_file_source(self, tmp_path: Path, capsys) -> None:
        """CLI can print file-based prompt source metadata and path."""
        json_data = {
            "schema_version": "3.0",
            "name": "test-suite",
            "timestamp": "2026-01-31T12:00:00Z",
            "duration_ms": 100.0,
            "passed": 1,
            "failed": 0,
            "skipped": 0,
            "tests": [],
            "insights": {
                "markdown_summary": "Existing insights",
                "model": "test-model",
                "tokens_used": 10,
                "cost_usd": 0.0,
                "cached": True,
            },
        }
        json_path = tmp_path / "results.json"
        json_path.write_text(json.dumps(json_data), encoding="utf-8")
        html_path = tmp_path / "report.html"
        prompt_path = tmp_path / "analysis_prompt.md"
        prompt_path.write_text("Custom prompt", encoding="utf-8")

        with mock.patch("pytest_aitest.cli.generate_ai_summary") as mock_summary:
            mock_summary.return_value = mock.MagicMock(
                markdown_summary="Fresh insights",
                model="test-model",
                tokens_used=100,
                cost_usd=0.0,
                cached=False,
            )

            result = main(
                [
                    str(json_path),
                    "--html",
                    str(html_path),
                    "--summary",
                    "--summary-model",
                    "test-model",
                    "--analysis-prompt",
                    str(prompt_path),
                    "--print-analysis-prompt",
                ]
            )

        captured = capsys.readouterr()
        assert result == 0
        assert "analysis prompt: source=cli-file" in captured.out
        assert str(prompt_path) in captured.out
