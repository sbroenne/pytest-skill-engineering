"""Unit tests for pytest hook implementations in plugin.py."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from _pytest.config import Config
from _pytest.pytester import Pytester

from pytest_skill_engineering.core.result import EvalResult, SkillInfo, ToolCall, Turn
from pytest_skill_engineering.plugin import (
    COLLECTOR_KEY,
    SESSION_MESSAGES_KEY,
    _add_junit_properties,
    _get_timestamped_path,
    pytest_configure,
    pytest_skill_engineering_analysis_prompt,
)
from pytest_skill_engineering.plugin_report import build_coding_agent_prompt
from pytest_skill_engineering.reporting import TestReport as ReportingTestReport

pytest_plugins = ["pytester"]


def _parse_config(pytester: Pytester, *args: str) -> Config:
    """Parse pytest config with only the aitest plugin explicitly loaded."""

    return pytester.parseconfig("-p", "no:aitest", "-p", "pytest_skill_engineering.plugin", *args)


def _run_pytest(pytester: Pytester, *args: str):
    """Run pytest with only the aitest plugin explicitly loaded."""

    return pytester.runpytest("-p", "no:aitest", "-p", "pytest_skill_engineering.plugin", *args)


def _load_json(path: Path) -> Any:
    """Load JSON from disk."""

    return json.loads(path.read_text(encoding="utf-8"))


def _make_eval_result(
    *,
    success: bool = True,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cost_usd: float = 0.0,
    skill_name: str | None = None,
) -> EvalResult:
    """Build a real EvalResult with predictable tool calls."""

    turns = [
        Turn(
            role="assistant", content="First response", tool_calls=[ToolCall("search", {"q": "x"})]
        ),
        Turn(
            role="assistant",
            content="Second response",
            tool_calls=[
                ToolCall("search", {"q": "y"}),
                ToolCall("write_file", {"path": "out.txt"}),
            ],
        ),
    ]
    skill_info = None
    if skill_name is not None:
        skill_info = SkillInfo(
            name=skill_name,
            description=f"{skill_name} description",
            instruction_content=f"{skill_name} instructions",
        )
    return EvalResult(
        turns=turns,
        success=success,
        token_usage={"prompt": prompt_tokens, "completion": completion_tokens},
        cost_usd=cost_usd,
        skill_info=skill_info,
    )


@dataclass(slots=True)
class FakeProvider:
    """Minimal provider object for JUnit property tests."""

    model: str


@dataclass(slots=True)
class FakeServer:
    """Minimal MCP server object for JUnit property tests."""

    name: str | None = None
    command: list[str] | None = None


@dataclass(slots=True)
class FakeSkill:
    """Minimal skill object for plugin agent metadata."""

    name: str


@dataclass(slots=True)
class FakeAgent:
    """Minimal agent object exposing the fields plugin.py reads."""

    name: str
    id: str
    provider: FakeProvider
    system_prompt_name: str | None = None
    mcp_servers: list[FakeServer] | None = None
    allowed_tools: list[str] | None = None
    skill: FakeSkill | None = None

    def __post_init__(self) -> None:
        if self.mcp_servers is None:
            self.mcp_servers = []


CAPTURE_REPORTS_CONFTEST = """
from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from pytest_skill_engineering.copilot.eval import CopilotEval
from pytest_skill_engineering.copilot.result import CopilotResult
from pytest_skill_engineering.core.result import EvalResult, SkillInfo, ToolCall, Turn
from pytest_skill_engineering.plugin import COLLECTOR_KEY


@dataclass(slots=True)
class Provider:
    model: str


@dataclass(slots=True)
class Skill:
    name: str


@dataclass(slots=True)
class Agent:
    name: str
    id: str
    provider: Provider
    system_prompt_name: str | None = None
    mcp_servers: list[object] | None = None
    allowed_tools: list[str] | None = None
    skill: Skill | None = None

    def __post_init__(self) -> None:
        if self.mcp_servers is None:
            self.mcp_servers = []


@pytest.fixture
def auto_result() -> CopilotResult:
    agent = CopilotEval(name="auto-agent", model="copilot/gpt-4.1", instructions="Do things.")
    return CopilotResult(
        turns=[Turn(role="assistant", content="Used search", tool_calls=[ToolCall("search", {"q": "boom"})])],
        success=True,
        model_used="copilot/gpt-5.4-mini",
        agent=agent,
    )


@pytest.fixture
def manual_aitest(request: pytest.FixtureRequest) -> EvalResult:
    result = EvalResult(
        turns=[
            Turn(
                role="assistant",
                content="Completed task",
                tool_calls=[ToolCall("write_file", {"path": "out.txt"})],
            )
        ],
        success=True,
        token_usage={"prompt": 2, "completion": 3},
        skill_info=SkillInfo(
            name="manual-skill",
            description="manual description",
            instruction_content="manual instructions",
        ),
    )
    request.node._aitest_result = result
    request.node._aitest_agent = Agent(
        name="manual-agent",
        id="manual-id",
        provider=Provider(model="copilot/claude-sonnet-4.5"),
        system_prompt_name="manual-prompt",
        allowed_tools=["beta", "alpha"],
        skill=Skill(name="manual-skill"),
    )
    return result


def pytest_sessionfinish(session, exitstatus):
    data = []
    for test in session.config.stash.get(COLLECTOR_KEY, []):
        data.append(
            {
                "name": test.name,
                "outcome": test.outcome,
                "error": test.error,
                "assertions": test.assertions,
                "docstring": test.docstring,
                "class_docstring": test.class_docstring,
                "agent_id": test.agent_id,
                "eval_name": test.eval_name,
                "model": test.model,
                "system_prompt_name": test.system_prompt_name,
                "skill_name": test.skill_name,
                "iteration": test.iteration,
                "copilot_test": getattr(test, "_copilot_test", False),
            }
        )
    (session.config.rootpath / "collected.json").write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )
"""


SESSIONFINISH_CONFTEST = """
from __future__ import annotations

from dataclasses import dataclass

import pytest

from pytest_skill_engineering.core.result import EvalResult, ToolCall, Turn


@dataclass(slots=True)
class Provider:
    model: str


@dataclass(slots=True)
class Agent:
    name: str
    id: str
    provider: Provider
    system_prompt_name: str | None = None
    mcp_servers: list[object] | None = None
    allowed_tools: list[str] | None = None
    skill: object | None = None

    def __post_init__(self) -> None:
        if self.mcp_servers is None:
            self.mcp_servers = []


@pytest.fixture
def manual_aitest(request: pytest.FixtureRequest) -> EvalResult:
    result = EvalResult(
        turns=[Turn(role="assistant", content="done", tool_calls=[ToolCall("search", {"q": "ok"})])],
        success=True,
        token_usage={"prompt": 1, "completion": 1},
    )
    request.node._aitest_result = result
    request.node._aitest_agent = Agent(
        name="sessionfinish-agent",
        id="sessionfinish-id",
        provider=Provider(model="copilot/gpt-5.4-mini"),
    )
    return result
"""


class TestGetTimestampedPath:
    """Tests for timestamped default report path generation."""

    def test_uses_default_directory_and_preserves_extension(self) -> None:
        """Default output directory is aitest-reports and timestamp precedes the extension."""

        path = _get_timestamped_path("results.json")

        assert path.parent == Path("aitest-reports")
        assert re.fullmatch(r"results_\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}\.json", path.name)

    def test_sanitizes_test_name_for_extended_filenames(self) -> None:
        """Path segments, extensions, spaces, and underscores are stripped from test names."""

        path = _get_timestamped_path("report.html", test_name="suite/path/My Test_Name.py")

        assert re.fullmatch(
            r"report_my-test-name_\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}\.html",
            path.name,
        )

    def test_handles_base_names_without_extensions(self, tmp_path: Path) -> None:
        """Base names without dots still receive test-name and timestamp suffixes."""

        path = _get_timestamped_path(
            "results", test_name="nested/Sample_Case.py", default_dir=tmp_path
        )

        assert path.parent == tmp_path
        assert re.fullmatch(
            r"results_sample-case_\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}",
            path.name,
        )


class TestPytestAddoption:
    """Tests for plugin CLI option registration."""

    def test_help_output_includes_aitest_group_and_options(self, pytester: Pytester) -> None:
        """The plugin registers an 'AI agent testing' help group with aitest options."""

        result = _run_pytest(pytester, "--help")

        assert result.ret == 0
        stdout = result.stdout.str()
        assert "AI agent testing:" in stdout
        assert "--aitest-json=PATH" in stdout
        assert "--aitest-iterations=N" in stdout
        assert "--llm-model=LLM_MODEL" in stdout


class TestPytestConfigure:
    """Tests for plugin configuration bootstrap."""

    def test_registers_hooks_markers_and_stash(self, pytester: Pytester) -> None:
        """pytest_configure registers hookspecs, markers, and per-session stash state."""

        config = _parse_config(pytester)
        pytest_configure(config)

        assert hasattr(config.pluginmanager.hook, "pytest_skill_engineering_analysis_prompt")
        assert config.stash[COLLECTOR_KEY] == []
        assert config.stash[SESSION_MESSAGES_KEY] == {}

        markers = "\n".join(config.getini("markers"))
        assert "aitest:" in markers
        assert "aitest_skip_report:" in markers
        assert "session(name):" in markers
        assert "copilot:" in markers


class TestPytestGenerateTests:
    """Tests for iteration parametrization."""

    def test_parametrizes_tests_when_iterations_exceed_one(self, pytester: Pytester) -> None:
        """The hook injects _aitest_iteration with iter-N IDs when requested."""

        pytester.makepyfile(
            """
            def test_repeated():
                pass
            """
        )

        result = _run_pytest(pytester, "--aitest-iterations=3", "-vv")

        result.assert_outcomes(passed=3)
        stdout = result.stdout.str()
        assert "test_repeated[iter-1]" in stdout
        assert "test_repeated[iter-2]" in stdout
        assert "test_repeated[iter-3]" in stdout

    def test_leaves_tests_unparametrized_by_default(self, pytester: Pytester) -> None:
        """Omitting --aitest-iterations runs the test only once without iter-* IDs."""

        pytester.makepyfile(
            """
            def test_once():
                pass
            """
        )

        result = _run_pytest(pytester, "-vv")

        result.assert_outcomes(passed=1)
        assert "test_once[iter-" not in result.stdout.str()


class TestPytestCollectionModifyItems:
    """Tests for automatic aitest marker injection."""

    def test_auto_marks_only_tests_using_copilot_eval(self, pytester: Pytester) -> None:
        """Only copilot_eval-consuming tests gain the aitest marker, without duplicates."""

        pytester.makeconftest(
            """
            from __future__ import annotations

            import json

            import pytest


            @pytest.fixture
            def copilot_eval():
                return object()


            def pytest_collection_finish(session):
                markers = {
                    item.name: [mark.name for mark in item.iter_markers()]
                    for item in session.items
                }
                (session.config.rootpath / "markers.json").write_text(
                    json.dumps(markers, indent=2),
                    encoding="utf-8",
                )
            """
        )
        pytester.makepyfile(
            """
            import pytest


            def test_uses_fixture(copilot_eval):
                assert copilot_eval is not None


            @pytest.mark.aitest
            def test_already_marked(copilot_eval):
                assert copilot_eval is not None


            def test_plain():
                assert True
            """
        )

        result = _run_pytest(pytester, "--collect-only", "-q")

        assert result.ret == 0
        markers = _load_json(pytester.path / "markers.json")
        assert markers["test_uses_fixture"].count("aitest") == 1
        assert markers["test_already_marked"].count("aitest") == 1
        assert "aitest" not in markers["test_plain"]


class TestPytestRuntestMakereport:
    """Tests for report capture during test execution."""

    def test_collects_only_aitest_results_and_extracts_metadata(self, pytester: Pytester) -> None:
        """Only aitest-backed tests are collected, with clean errors and identity fields."""

        pytester.makeconftest(CAPTURE_REPORTS_CONFTEST)
        pytester.makepyfile(
            """
            from __future__ import annotations

            import pytest


            class TestCapturedReports:
                \"\"\"Collected class docstring.\"\"\"

                def test_auto_stashed_failure(self, auto_result, request):
                    \"\"\"Auto-stashed failure docstring.\"\"\"
                    request.node._aitest_assertions = [
                        {"type": "semantic", "passed": True, "message": "recorded"}
                    ]
                    assert False, "boom"

                def test_manual_failure_without_e_lines(self, manual_aitest):
                    pytest.fail("plain failure", pytrace=False)

                @pytest.mark.copilot
                def test_manual_passing_report(self, manual_aitest):
                    \"\"\"Manual passing docstring.\"\"\"
                    assert manual_aitest.success

                @pytest.mark.aitest_skip_report
                def test_skip_report_marker(self, manual_aitest):
                    assert manual_aitest.success


            def test_plain_unit():
                assert True
            """
        )

        result = _run_pytest(pytester, "-q")

        result.assert_outcomes(passed=3, failed=2)
        collected = _load_json(pytester.path / "collected.json")

        assert [entry["name"] for entry in collected] == [
            "test_collects_only_aitest_results_and_extracts_metadata.py::TestCapturedReports::test_auto_stashed_failure",
            "test_collects_only_aitest_results_and_extracts_metadata.py::TestCapturedReports::test_manual_failure_without_e_lines",
            "test_collects_only_aitest_results_and_extracts_metadata.py::TestCapturedReports::test_manual_passing_report",
        ]

        auto_failure = collected[0]
        assert auto_failure["outcome"] == "failed"
        assert auto_failure["docstring"] == "Auto-stashed failure docstring."
        assert auto_failure["class_docstring"] == "Collected class docstring."
        assert auto_failure["assertions"] == [
            {"type": "semantic", "passed": True, "message": "recorded"}
        ]
        assert auto_failure["agent_id"] == "auto-agent"
        assert auto_failure["eval_name"] == "auto-agent"
        assert auto_failure["model"] == "gpt-5.4-mini"
        assert "boom" in auto_failure["error"]
        assert "test_auto_stashed_failure" not in auto_failure["error"]

        no_e_lines_failure = collected[1]
        assert no_e_lines_failure["outcome"] == "failed"
        assert no_e_lines_failure["error"] == "plain failure"

        manual_pass = collected[2]
        assert manual_pass["outcome"] == "passed"
        assert manual_pass["eval_name"] == "manual-agent"
        assert manual_pass["agent_id"] == "manual-id"
        assert manual_pass["model"] == "claude-sonnet-4.5"
        assert manual_pass["system_prompt_name"] == "manual-prompt"
        assert manual_pass["skill_name"] == "manual-skill"
        assert manual_pass["copilot_test"] is True

    def test_captures_iteration_from_callspec(self, pytester: Pytester) -> None:
        """Collected reports include the injected _aitest_iteration value."""

        pytester.makeconftest(CAPTURE_REPORTS_CONFTEST)
        pytester.makepyfile(
            """
            class TestIterationCapture:
                def test_iteration_value(self, manual_aitest):
                    assert manual_aitest.success
            """
        )

        result = _run_pytest(pytester, "--aitest-iterations=2", "-q")

        result.assert_outcomes(passed=2)
        collected = _load_json(pytester.path / "collected.json")
        assert [entry["iteration"] for entry in collected] == [1, 2]


class TestAddJunitProperties:
    """Tests for JUnit XML metadata enrichment."""

    def test_adds_all_expected_properties_for_populated_eval_results(self) -> None:
        """The helper appends stable JUnit properties for agent, tools, tokens, and cost."""

        report = SimpleNamespace(user_properties=[])
        eval_result = _make_eval_result(
            prompt_tokens=11,
            completion_tokens=7,
            cost_usd=0.123456,
            skill_name="financial-advisor",
        )
        agent = FakeAgent(
            name="banking-agent",
            id="banking-id",
            provider=FakeProvider(model="copilot/gpt-5.4-mini"),
            system_prompt_name="concise",
            mcp_servers=[
                FakeServer(name="banking"),
                FakeServer(command=["python", "/srv/todo_server.py"]),
            ],
            allowed_tools=["write_file", "search"],
        )

        _add_junit_properties(cast(Any, report), eval_result, agent)

        assert report.user_properties == [
            ("aitest.agent.name", "banking-agent"),
            ("aitest.model", "gpt-5.4-mini"),
            ("aitest.prompt", "concise"),
            ("aitest.skill", "financial-advisor"),
            ("aitest.servers", "banking,todo_server"),
            ("aitest.allowed_tools", "search,write_file"),
            ("aitest.tokens.input", "11"),
            ("aitest.tokens.output", "7"),
            ("aitest.tokens.total", "18"),
            ("aitest.cost_usd", "0.123456"),
            ("aitest.turns", "2"),
            ("aitest.tools.called", "search,write_file"),
            ("aitest.success", "true"),
        ]

    def test_omits_zero_value_optional_properties(self) -> None:
        """Zero tokens and zero cost do not emit extra JUnit properties."""

        report = SimpleNamespace(user_properties=[])
        eval_result = EvalResult(
            turns=[], success=False, token_usage={"prompt": 0, "completion": 0}
        )

        _add_junit_properties(cast(Any, report), eval_result, agent=None)

        assert report.user_properties == [("aitest.success", "false")]

    def test_returns_early_when_report_has_no_user_properties(self) -> None:
        """Objects without user_properties are ignored without raising."""

        eval_result = EvalResult(turns=[], success=True)

        _add_junit_properties(cast(Any, object()), eval_result, agent=None)


class TestPytestSessionfinish:
    """Tests for end-of-session report generation and threshold enforcement."""

    def test_skips_report_generation_when_no_aitest_results_exist(self, pytester: Pytester) -> None:
        """A plain unit-only run leaves the default aitest-reports directory absent."""

        pytester.makepyfile(
            """
            def test_plain():
                assert True
            """
        )

        result = _run_pytest(pytester, "-q")

        result.assert_outcomes(passed=1)
        assert not (pytester.path / "aitest-reports").exists()

    def test_writes_json_report_to_requested_path(self, pytester: Pytester) -> None:
        """An aitest-backed test produces JSON at the exact --aitest-json path."""

        pytester.makeconftest(SESSIONFINISH_CONFTEST)
        pytester.makepyfile(
            test_json_output="""
            def test_aitest_result(manual_aitest):
                assert manual_aitest.success
            """
        )

        output_path = pytester.path / "custom" / "results.json"
        result = _run_pytest(pytester, f"--aitest-json={output_path}", "-q")

        result.assert_outcomes(passed=1)
        assert output_path.exists()

        report = _load_json(output_path)
        assert report["schema_version"] == "3.0"
        assert report["passed"] == 1
        assert report["failed"] == 0
        assert report["skipped"] == 0
        assert len(report["tests"]) == 1
        assert report["tests"][0]["name"].endswith("test_json_output.py::test_aitest_result")
        assert report["tests"][0]["outcome"] == "passed"

    def test_forces_failure_when_pass_rate_is_below_threshold(self, pytester: Pytester) -> None:
        """A skipped aitest still fails the session when the minimum pass rate is unmet."""

        pytester.makeconftest(SESSIONFINISH_CONFTEST)
        pytester.makepyfile(
            """
            import pytest


            def test_skipped_aitest(manual_aitest):
                pytest.skip("not passing")
            """
        )

        result = _run_pytest(pytester, "--aitest-min-pass-rate=100", "-q")

        result.assert_outcomes(skipped=1)
        assert result.ret == pytest.ExitCode.TESTS_FAILED
        assert (
            "aitest: FAILED - pass rate 0.0% is below minimum threshold 100% (0/1 passed)"
            in result.stdout.str()
        )

    def test_leaves_successful_session_passing_when_threshold_is_met(
        self, pytester: Pytester
    ) -> None:
        """A fully passing aitest suite keeps a successful exit status and logs the threshold message."""

        pytester.makeconftest(SESSIONFINISH_CONFTEST)
        pytester.makepyfile(
            """
            def test_passing_aitest(manual_aitest):
                assert manual_aitest.success
            """
        )

        result = _run_pytest(pytester, "--aitest-min-pass-rate=100", "-q")

        result.assert_outcomes(passed=1)
        assert result.ret == 0
        assert "aitest: pass rate 100.0% meets minimum threshold 100%" in result.stdout.str()


class TestAnalysisPromptHook:
    """Tests for the coding-agent analysis prompt hook implementation."""

    def test_returns_none_without_copilot_reports(self, pytester: Pytester) -> None:
        """No coding-agent prompt is returned when the stash has no copilot-flagged tests."""

        config = _parse_config(pytester)
        config.stash[COLLECTOR_KEY] = []

        assert pytest_skill_engineering_analysis_prompt(config) is None

    def test_delegates_to_real_coding_agent_prompt_builder(self, pytester: Pytester) -> None:
        """The hook passes collected TestReport objects to build_coding_agent_prompt()."""

        config = _parse_config(pytester)
        report = ReportingTestReport(name="test_demo", outcome="passed", duration_ms=1.0)
        report._copilot_test = True
        config.stash[COLLECTOR_KEY] = [report]

        expected = build_coding_agent_prompt([report])
        assert expected is not None
        assert pytest_skill_engineering_analysis_prompt(config) == expected
