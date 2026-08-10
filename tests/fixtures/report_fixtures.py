"""Deterministic generators for checked-in report fixtures and demo reports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from pytest_skill_engineering.core.result import EvalResult, ToolCall, Turn
from pytest_skill_engineering.reporting.collector import SuiteReport, TestReport
from pytest_skill_engineering.reporting.generator import generate_json
from pytest_skill_engineering.reporting.insights import InsightsResult

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_JSON_DIR = ROOT / "tests" / "fixtures" / "reports"
DOCS_REPORTS_DIR = ROOT / "docs" / "reports"
DOCS_DEMO_DIR = ROOT / "docs" / "demo"


@dataclass(slots=True, frozen=True)
class ReportArtifactSpec:
    """Manifest entry for a generated report artifact bundle."""

    name: str
    generator_source: str
    output_dir: Path
    builder: Callable[[], tuple[SuiteReport, InsightsResult]]

    @property
    def json_path(self) -> Path:
        return (
            FIXTURE_JSON_DIR / f"{self.name}.json"
            if self.output_dir == DOCS_REPORTS_DIR
            else self.output_dir / f"{self.name}.json"
        )

    @property
    def html_path(self) -> Path:
        return self.output_dir / f"{self.name}.html"

    @property
    def md_path(self) -> Path:
        return self.output_dir / f"{self.name}.md"


def _insights(summary: str) -> InsightsResult:
    return InsightsResult(
        markdown_summary=summary,
        model="copilot/gpt-5.4-mini",
        tokens_used=240,
        cost_usd=0.0012,
        cached=True,
    )


def _assertions(*, passed: bool, message: str) -> list[dict[str, object]]:
    return [
        {
            "type": "llm",
            "passed": passed,
            "message": message,
            "details": "Deterministic fixture assertion.",
        }
    ]


def _score_assertion(total: int, max_total: int, weighted_score: float) -> dict[str, object]:
    return {
        "type": "llm_score",
        "passed": True,
        "message": f"{total}/{max_total} ({weighted_score:.0%})",
        "details": "Deterministic score reasoning.",
        "dimensions": [
            {"name": "correctness", "score": total, "max_score": max_total, "weight": 1.0}
        ],
        "total": total,
        "max_total": max_total,
        "weighted_score": weighted_score,
    }


def _result(
    prompt: str,
    response: str,
    *,
    tools: list[ToolCall] | None = None,
    success: bool = True,
    error: str | None = None,
    prompt_tokens: int = 120,
    completion_tokens: int = 60,
    duration_ms: float = 2_500.0,
    cost_usd: float = 0.0,
    premium_requests: float = 1.0,
    session_context_count: int = 0,
    effective_system_prompt: str = "Use tools before answering.",
) -> EvalResult:
    tool_calls = tools or []
    turns = [Turn(role="user", content=prompt)]
    if tool_calls:
        turns.append(Turn(role="assistant", content="", tool_calls=tool_calls))
    turns.append(Turn(role="assistant", content=response))
    return EvalResult(
        turns=turns,
        success=success,
        error=error,
        duration_ms=duration_ms,
        token_usage={"prompt": prompt_tokens, "completion": completion_tokens},
        cost_usd=cost_usd,
        session_context_count=session_context_count,
        effective_system_prompt=effective_system_prompt,
        premium_requests=premium_requests,
    )


def _tool(
    name: str, *, result: str | None = None, error: str | None = None, **arguments: object
) -> ToolCall:
    return ToolCall(
        name=name,
        arguments=dict(arguments),
        result=result,
        error=error,
        duration_ms=180.0,
    )


def _test(
    *,
    name: str,
    outcome: str,
    agent_id: str,
    eval_name: str,
    model: str,
    prompt: str,
    response: str,
    tools: list[ToolCall] | None = None,
    error: str | None = None,
    duration_ms: float = 3_000.0,
    docstring: str,
    class_docstring: str | None = None,
    system_prompt_name: str | None = None,
    skill_name: str | None = None,
    iteration: int | None = None,
    assertion_message: str | None = None,
    include_score: bool = False,
    success: bool | None = None,
    premium_requests: float = 1.0,
    session_context_count: int = 0,
) -> TestReport:
    test_success = outcome == "passed" if success is None else success
    assertions: list[dict[str, object]] = []
    if assertion_message:
        assertions.extend(_assertions(passed=test_success, message=assertion_message))
    if include_score:
        assertions.append(
            _score_assertion(4 if test_success else 2, 5, 0.8 if test_success else 0.4)
        )
    return TestReport(
        name=name,
        outcome=outcome,
        duration_ms=duration_ms,
        eval_result=_result(
            prompt,
            response,
            tools=tools,
            success=test_success,
            error=error,
            duration_ms=duration_ms,
            prompt_tokens=130 + (iteration or 0),
            completion_tokens=65 + (iteration or 0),
            premium_requests=premium_requests,
            session_context_count=session_context_count,
            effective_system_prompt=f"Fixture instructions for {eval_name}.",
        ),
        error=error,
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


def _suite(
    name: str,
    suite_docstring: str,
    tests: list[TestReport],
    *,
    timestamp: str,
) -> SuiteReport:
    return SuiteReport(
        name=name,
        timestamp=timestamp,
        duration_ms=sum(test.duration_ms for test in tests),
        tests=tests,
        passed=sum(1 for test in tests if test.outcome == "passed"),
        failed=sum(1 for test in tests if test.outcome == "failed"),
        skipped=sum(1 for test in tests if test.outcome == "skipped"),
        suite_docstring=suite_docstring,
    )


def _fixture_summary(title: str) -> str:
    return (
        f"## 🎯 Recommendation\n\nDeploy the strongest passing eval for **{title}**.\n\n"
        "## ❌ Failure Analysis\n\nAt least one compared result failed, so the report must keep the failure visible.\n\n"
        "## 🔧 MCP Tool Feedback\n\nTool names are deterministic in these fixture reports.\n"
    )


def build_01_single_agent() -> tuple[SuiteReport, InsightsResult]:
    tests = [
        _test(
            name="tests/fixtures/scenario_01_single_agent.py::test_check_balance",
            outcome="passed",
            agent_id="agent-gpt-5-4-mini",
            eval_name="gpt-5.4-mini",
            model="gpt-5.4-mini",
            prompt="What's my checking account balance?",
            response="Your checking balance is $1,500.00.",
            tools=[_tool("get_balance", account="checking", result='{"formatted": "$1,500.00"}')],
            docstring="Check a single account balance.",
            assertion_message="mentions the current balance",
        ),
        _test(
            name="tests/fixtures/scenario_01_single_agent.py::test_transfer_confirmation",
            outcome="passed",
            agent_id="agent-gpt-5-4-mini",
            eval_name="gpt-5.4-mini",
            model="gpt-5.4-mini",
            prompt="Transfer $200 to savings and confirm it worked.",
            response="Transferred $200 and confirmed the updated balances.",
            tools=[
                _tool(
                    "transfer",
                    from_account="checking",
                    to_account="savings",
                    amount=200,
                    result="ok",
                ),
                _tool(
                    "get_all_balances", result='{"checking": "$1,300.00", "savings": "$3,200.00"}'
                ),
            ],
            docstring="Transfer funds and verify the result.",
            assertion_message="confirms the transfer outcome",
            include_score=True,
        ),
    ]
    return _suite(
        "fixture-01-single-agent",
        "Single agent banking smoke report.",
        tests,
        timestamp="2026-08-10T18:00:00+00:00",
    ), _insights(_fixture_summary("single-agent coverage"))


def build_02_multi_agent() -> tuple[SuiteReport, InsightsResult]:
    tests = [
        _test(
            name="tests/fixtures/scenario_02_multi_agent.py::test_check_balance[gpt-5.4-mini]",
            outcome="passed",
            agent_id="agent-gpt-5-4-mini",
            eval_name="gpt-5.4-mini",
            model="gpt-5.4-mini",
            prompt="Check balances.",
            response="Checking is $1,500.00 and savings is $3,000.00.",
            tools=[
                _tool(
                    "get_all_balances", result='{"checking": "$1,500.00", "savings": "$3,000.00"}'
                )
            ],
            docstring="Compare balance handling across agents.",
        ),
        _test(
            name="tests/fixtures/scenario_02_multi_agent.py::test_check_balance[claude-haiku-4.5]",
            outcome="passed",
            agent_id="agent-claude-haiku-4-5",
            eval_name="claude-haiku-4.5",
            model="claude-haiku-4.5",
            prompt="Check balances.",
            response="Checking is $1,500.00 and savings is $3,000.00.",
            tools=[
                _tool(
                    "get_all_balances", result='{"checking": "$1,500.00", "savings": "$3,000.00"}'
                )
            ],
            docstring="Compare balance handling across agents.",
        ),
        _test(
            name="tests/fixtures/scenario_02_multi_agent.py::test_error_handling[gpt-5.4-mini]",
            outcome="passed",
            agent_id="agent-gpt-5-4-mini",
            eval_name="gpt-5.4-mini",
            model="gpt-5.4-mini",
            prompt="Withdraw too much money.",
            response="The withdrawal failed because the balance is insufficient.",
            tools=[_tool("withdraw", account="checking", amount=50000, error="Insufficient funds")],
            docstring="Reject overdrawn withdrawals cleanly.",
        ),
        _test(
            name="tests/fixtures/scenario_02_multi_agent.py::test_error_handling[claude-haiku-4.5]",
            outcome="failed",
            agent_id="agent-claude-haiku-4-5",
            eval_name="claude-haiku-4.5",
            model="claude-haiku-4.5",
            prompt="Withdraw too much money.",
            response="I cannot help with that.",
            tools=[],
            error="AssertionError: withdraw tool was never called",
            docstring="Reject overdrawn withdrawals cleanly.",
            assertion_message="calls the withdraw tool before explaining the failure",
        ),
    ]
    return _suite(
        "fixture-02-multi-agent",
        "Two agents compared on shared banking workflows.",
        tests,
        timestamp="2026-08-10T18:01:00+00:00",
    ), _insights(_fixture_summary("multi-agent comparison"))


def build_03_multi_agent_sessions() -> tuple[SuiteReport, InsightsResult]:
    class_doc = "Multi-turn session: moving money and verifying the final state."
    tests = [
        _test(
            name="tests/fixtures/scenario_03_sessions.py::TestBankingWorkflow::test_check_balance[gpt-5.4-mini]",
            outcome="passed",
            agent_id="agent-gpt-5-4-mini",
            eval_name="gpt-5.4-mini",
            model="gpt-5.4-mini",
            prompt="Start by checking balances.",
            response="Balances loaded and ready for the next step.",
            tools=[
                _tool(
                    "get_all_balances", result='{"checking": "$1,500.00", "savings": "$3,000.00"}'
                )
            ],
            docstring="First turn: establish the current balances.",
            class_docstring=class_doc,
        ),
        _test(
            name="tests/fixtures/scenario_03_sessions.py::TestBankingWorkflow::test_check_balance[claude-haiku-4.5]",
            outcome="passed",
            agent_id="agent-claude-haiku-4-5",
            eval_name="claude-haiku-4.5",
            model="claude-haiku-4.5",
            prompt="Start by checking balances.",
            response="Balances loaded and ready for the next step.",
            tools=[
                _tool(
                    "get_all_balances", result='{"checking": "$1,500.00", "savings": "$3,000.00"}'
                )
            ],
            docstring="First turn: establish the current balances.",
            class_docstring=class_doc,
        ),
        _test(
            name="tests/fixtures/scenario_03_sessions.py::TestBankingWorkflow::test_transfer_funds[gpt-5.4-mini]",
            outcome="passed",
            agent_id="agent-gpt-5-4-mini",
            eval_name="gpt-5.4-mini",
            model="gpt-5.4-mini",
            prompt="Move $250 to savings.",
            response="Transferred $250 to savings.",
            tools=[
                _tool(
                    "transfer",
                    from_account="checking",
                    to_account="savings",
                    amount=250,
                    result="ok",
                )
            ],
            docstring="Second turn: transfer funds into savings.",
            class_docstring=class_doc,
            session_context_count=2,
        ),
        _test(
            name="tests/fixtures/scenario_03_sessions.py::TestBankingWorkflow::test_transfer_funds[claude-haiku-4.5]",
            outcome="passed",
            agent_id="agent-claude-haiku-4-5",
            eval_name="claude-haiku-4.5",
            model="claude-haiku-4.5",
            prompt="Move $250 to savings.",
            response="Transferred $250 to savings.",
            tools=[
                _tool(
                    "transfer",
                    from_account="checking",
                    to_account="savings",
                    amount=250,
                    result="ok",
                )
            ],
            docstring="Second turn: transfer funds into savings.",
            class_docstring=class_doc,
            session_context_count=2,
        ),
    ]
    return _suite(
        "fixture-03-sessions",
        "Two agents compared inside one banking session.",
        tests,
        timestamp="2026-08-10T18:02:00+00:00",
    ), _insights(_fixture_summary("session grouping"))


def build_04_agent_selector() -> tuple[SuiteReport, InsightsResult]:
    tests: list[TestReport] = []
    agents = [
        ("agent-gpt-5-4-mini", "gpt-5.4-mini", "gpt-5.4-mini", "passed"),
        ("agent-claude-haiku-4-5", "claude-haiku-4.5", "claude-haiku-4.5", "passed"),
        ("agent-gemini-3-6-flash", "gemini-3.6-flash", "gemini-3.6-flash", "failed"),
    ]
    for agent_id, eval_name, model, outcome in agents:
        tests.append(
            _test(
                name=f"tests/fixtures/scenario_04_agent_selector.py::test_compare_agents[{eval_name}]",
                outcome=outcome,
                agent_id=agent_id,
                eval_name=eval_name,
                model=model,
                prompt="Create a summary file.",
                response="Created summary.txt."
                if outcome == "passed"
                else "Refused to create the file.",
                tools=[_tool("create_file", path="summary.txt", result="written")]
                if outcome == "passed"
                else [],
                error=None
                if outcome == "passed"
                else "AssertionError: summary.txt was not created",
                docstring="Compare three agents with selector controls.",
            )
        )
    return _suite(
        "fixture-04-agent-selector",
        "Three agents for testing the agent selector UI.",
        tests,
        timestamp="2026-08-10T18:03:00+00:00",
    ), _insights(_fixture_summary("agent selector"))


def build_05_prompt_comparison() -> tuple[SuiteReport, InsightsResult]:
    prompt_agents = [
        ("prompt-concise", "concise", "gpt-5.4-mini"),
        ("prompt-detailed", "detailed", "gpt-5.4-mini"),
        ("prompt-structured", "structured", "gpt-5.4-mini"),
    ]
    tests: list[TestReport] = []
    for agent_id, prompt_name, model in prompt_agents:
        tests.append(
            _test(
                name=f"tests/fixtures/scenario_05_prompt_comparison.py::test_balance_check[{model} + {prompt_name}]",
                outcome="passed",
                agent_id=agent_id,
                eval_name=f"{model} / {prompt_name}",
                model=model,
                prompt="Explain the balance.",
                response=f"{prompt_name.title()} response with the same answer.",
                tools=[
                    _tool("get_balance", account="checking", result='{"formatted":"$1,500.00"}')
                ],
                docstring="Compare prompt variants for a balance question.",
                system_prompt_name=prompt_name,
            )
        )
    return _suite(
        "fixture-05-prompt-comparison",
        "System prompt comparison across three prompt variants.",
        tests,
        timestamp="2026-08-10T18:04:00+00:00",
    ), _insights(_fixture_summary("prompt comparison"))


def build_06_model_prompt_matrix() -> tuple[SuiteReport, InsightsResult]:
    tests: list[TestReport] = []
    for model in ("gpt-5.4-mini", "claude-haiku-4.5"):
        for prompt_name in ("concise", "detailed"):
            tests.append(
                _test(
                    name=f"tests/fixtures/scenario_06_model_prompt_matrix.py::TestModelPromptMatrix::test_balance_check[{prompt_name}-{model}]",
                    outcome="passed",
                    agent_id=f"{model}-{prompt_name}",
                    eval_name=f"{model} / {prompt_name}",
                    model=model,
                    prompt="Check the balance.",
                    response=f"{model} handled the {prompt_name} instructions.",
                    tools=[
                        _tool("get_balance", account="checking", result='{"formatted":"$1,500.00"}')
                    ],
                    docstring="Measure one point in the model × prompt matrix.",
                    class_docstring="Model × prompt matrix cases.",
                    system_prompt_name=prompt_name,
                )
            )
    return _suite(
        "fixture-06-model-prompt-matrix",
        "Model × prompt matrix fixture.",
        tests,
        timestamp="2026-08-10T18:05:00+00:00",
    ), _insights(_fixture_summary("model prompt matrix"))


def build_07_skill_improvement() -> tuple[SuiteReport, InsightsResult]:
    tests = [
        _test(
            name="tests/fixtures/scenario_07_skill_improvement.py::test_without_skill",
            outcome="failed",
            agent_id="baseline-no-skill",
            eval_name="baseline",
            model="gpt-5.4-mini",
            prompt="Explain available account types.",
            response="Accounts exist.",
            error="AssertionError: expected banking terminology was missing",
            docstring="Baseline agent without the skill.",
            assertion_message="uses domain-correct banking terminology",
        ),
        _test(
            name="tests/fixtures/scenario_07_skill_improvement.py::test_with_skill",
            outcome="passed",
            agent_id="treatment-financial-literacy",
            eval_name="with skill",
            model="gpt-5.4-mini",
            prompt="Explain available account types.",
            response="Checking handles daily spending, while savings earns interest.",
            tools=[
                _tool("get_all_balances", result='{"checking":"$1,500.00","savings":"$3,000.00"}')
            ],
            docstring="Treatment agent with the financial-literacy skill.",
            skill_name="financial-literacy",
            assertion_message="uses domain-correct banking terminology",
        ),
    ]
    return _suite(
        "fixture-07-skill-improvement",
        "Skill treatment improves domain language and tool usage.",
        tests,
        timestamp="2026-08-10T18:06:00+00:00",
    ), _insights(_fixture_summary("skill improvement"))


def build_08_cli_server() -> tuple[SuiteReport, InsightsResult]:
    tests = [
        _test(
            name="tests/fixtures/scenario_08_cli_server.py::test_cli_echo_basic",
            outcome="passed",
            agent_id="cli-gpt-5-4-mini",
            eval_name="gpt-5.4-mini",
            model="gpt-5.4-mini",
            prompt="Echo hello from the CLI wrapper.",
            response="The CLI returned hello.",
            tools=[_tool("echo_execute", args="hello", result='{"stdout":"hello\\n"}')],
            docstring="Exercise a simple CLI wrapper call.",
        ),
        _test(
            name="tests/fixtures/scenario_08_cli_server.py::test_cli_echo_with_reasoning",
            outcome="passed",
            agent_id="cli-gpt-5-4-mini",
            eval_name="gpt-5.4-mini",
            model="gpt-5.4-mini",
            prompt="Echo hello and explain the result.",
            response="The CLI returned hello and I explained it.",
            tools=[_tool("echo_execute", args="hello", result='{"stdout":"hello\\n"}')],
            docstring="Exercise CLI output plus explanatory text.",
        ),
    ]
    return _suite(
        "fixture-08-cli-server",
        "CLI wrapper fixture report.",
        tests,
        timestamp="2026-08-10T18:07:00+00:00",
    ), _insights(_fixture_summary("CLI server"))


def build_09_ab_servers() -> tuple[SuiteReport, InsightsResult]:
    tests = [
        _test(
            name="tests/fixtures/scenario_09_ab_servers.py::test_simple_balance_query[verbose-prompt]",
            outcome="passed",
            agent_id="prompt-verbose",
            eval_name="verbose-prompt",
            model="gpt-5.4-mini",
            prompt="Tell me the balance.",
            response="Verbose answer with extra guidance.",
            tools=[_tool("get_balance", account="checking", result='{"formatted":"$1,500.00"}')],
            docstring="Verbose variant for the same banking request.",
            system_prompt_name="verbose",
        ),
        _test(
            name="tests/fixtures/scenario_09_ab_servers.py::test_simple_balance_query[terse-prompt]",
            outcome="passed",
            agent_id="prompt-terse",
            eval_name="terse-prompt",
            model="gpt-5.4-mini",
            prompt="Tell me the balance.",
            response="Terse answer.",
            tools=[_tool("get_balance", account="checking", result='{"formatted":"$1,500.00"}')],
            docstring="Terse variant for the same banking request.",
            system_prompt_name="terse",
        ),
    ]
    return _suite(
        "fixture-09-ab-servers",
        "A/B prompt comparison with identical tool behavior.",
        tests,
        timestamp="2026-08-10T18:08:00+00:00",
    ), _insights(_fixture_summary("A/B prompts"))


def build_10_dimension_detection() -> tuple[SuiteReport, InsightsResult]:
    tests: list[TestReport] = []
    for model in ("gpt-5.4-mini", "claude-haiku-4.5"):
        for prompt_name in ("concise", "detailed"):
            tests.append(
                _test(
                    name=(
                        "tests/fixtures/scenario_10_dimension_detection.py::"
                        f"TestDimensionDetection::test_balance_with_all_permutations[{prompt_name}-{model}]"
                    ),
                    outcome="passed",
                    agent_id=f"dimension-{model}-{prompt_name}",
                    eval_name=f"{model} / {prompt_name}",
                    model=model,
                    prompt="Check balances with all dimensions enabled.",
                    response=f"{model} answered with the {prompt_name} prompt.",
                    tools=[
                        _tool(
                            "get_all_balances",
                            result='{"checking":"$1,500.00","savings":"$3,000.00"}',
                        )
                    ],
                    docstring="Keep distinct pytest parameter IDs in the report.",
                    class_docstring="Dimension detection cases.",
                    system_prompt_name=prompt_name,
                )
            )
    return _suite(
        "fixture-10-dimension-detection",
        "Dimension detection and parameter identity fixture.",
        tests,
        timestamp="2026-08-10T18:09:00+00:00",
    ), _insights(_fixture_summary("dimension detection"))


def build_hero_report() -> tuple[SuiteReport, InsightsResult]:
    class_doc = "Showcase: banking tasks, sessions, and custom agent comparisons."
    tests = [
        _test(
            name="tests/showcase/test_hero.py::TestCoreOperations::test_check_single_balance[gpt-5.4-mini]",
            outcome="passed",
            agent_id="hero-gpt-5-4-mini",
            eval_name="gpt-5.4-mini",
            model="gpt-5.4-mini",
            prompt="Check the checking balance.",
            response="The checking balance is $1,500.00.",
            tools=[_tool("get_balance", account="checking", result='{"formatted":"$1,500.00"}')],
            docstring="Check one account balance.",
            class_docstring=class_doc,
        ),
        _test(
            name="tests/showcase/test_hero.py::TestCoreOperations::test_check_single_balance[claude-haiku-4.5]",
            outcome="passed",
            agent_id="hero-claude-haiku-4-5",
            eval_name="claude-haiku-4.5",
            model="claude-haiku-4.5",
            prompt="Check the checking balance.",
            response="The checking balance is $1,500.00.",
            tools=[_tool("get_balance", account="checking", result='{"formatted":"$1,500.00"}')],
            docstring="Check one account balance.",
            class_docstring=class_doc,
        ),
        _test(
            name="tests/showcase/test_hero.py::TestCoreOperations::test_transfer_and_verify[gpt-5.4-mini]",
            outcome="passed",
            agent_id="hero-gpt-5-4-mini",
            eval_name="gpt-5.4-mini",
            model="gpt-5.4-mini",
            prompt="Transfer $300 to savings and verify it.",
            response="Transferred $300 and verified the new balances.",
            tools=[
                _tool(
                    "transfer",
                    from_account="checking",
                    to_account="savings",
                    amount=300,
                    result="ok",
                ),
                _tool("get_all_balances", result='{"checking":"$1,200.00","savings":"$3,300.00"}'),
            ],
            docstring="Transfer funds and verify the updated balances.",
            class_docstring=class_doc,
            include_score=True,
        ),
        _test(
            name="tests/showcase/test_hero.py::TestCoreOperations::test_transfer_and_verify[claude-haiku-4.5]",
            outcome="failed",
            agent_id="hero-claude-haiku-4-5",
            eval_name="claude-haiku-4.5",
            model="claude-haiku-4.5",
            prompt="Transfer $300 to savings and verify it.",
            response="The transfer may have worked.",
            tools=[
                _tool(
                    "transfer",
                    from_account="checking",
                    to_account="savings",
                    amount=300,
                    result="ok",
                )
            ],
            error="AssertionError: verification step was missing",
            docstring="Transfer funds and verify the updated balances.",
            class_docstring=class_doc,
            assertion_message="verifies the post-transfer balance",
        ),
    ]
    return _suite(
        "hero-report",
        "Hero showcase report for docs/demo.",
        tests,
        timestamp="2026-08-10T18:10:00+00:00",
    ), _insights(_fixture_summary("hero showcase"))


FIXTURE_SPECS: tuple[ReportArtifactSpec, ...] = (
    ReportArtifactSpec(
        "01_single_agent",
        "tests.fixtures.report_fixtures:build_01_single_agent",
        DOCS_REPORTS_DIR,
        build_01_single_agent,
    ),
    ReportArtifactSpec(
        "02_multi_agent",
        "tests.fixtures.report_fixtures:build_02_multi_agent",
        DOCS_REPORTS_DIR,
        build_02_multi_agent,
    ),
    ReportArtifactSpec(
        "03_multi_agent_sessions",
        "tests.fixtures.report_fixtures:build_03_multi_agent_sessions",
        DOCS_REPORTS_DIR,
        build_03_multi_agent_sessions,
    ),
    ReportArtifactSpec(
        "04_agent_selector",
        "tests.fixtures.report_fixtures:build_04_agent_selector",
        DOCS_REPORTS_DIR,
        build_04_agent_selector,
    ),
    ReportArtifactSpec(
        "05_prompt_comparison",
        "tests.fixtures.report_fixtures:build_05_prompt_comparison",
        DOCS_REPORTS_DIR,
        build_05_prompt_comparison,
    ),
    ReportArtifactSpec(
        "06_model_prompt_matrix",
        "tests.fixtures.report_fixtures:build_06_model_prompt_matrix",
        DOCS_REPORTS_DIR,
        build_06_model_prompt_matrix,
    ),
    ReportArtifactSpec(
        "07_skill_improvement",
        "tests.fixtures.report_fixtures:build_07_skill_improvement",
        DOCS_REPORTS_DIR,
        build_07_skill_improvement,
    ),
    ReportArtifactSpec(
        "08_cli_server",
        "tests.fixtures.report_fixtures:build_08_cli_server",
        DOCS_REPORTS_DIR,
        build_08_cli_server,
    ),
    ReportArtifactSpec(
        "09_ab_servers",
        "tests.fixtures.report_fixtures:build_09_ab_servers",
        DOCS_REPORTS_DIR,
        build_09_ab_servers,
    ),
    ReportArtifactSpec(
        "10_dimension_detection",
        "tests.fixtures.report_fixtures:build_10_dimension_detection",
        DOCS_REPORTS_DIR,
        build_10_dimension_detection,
    ),
)

DEMO_SPECS: tuple[ReportArtifactSpec, ...] = (
    ReportArtifactSpec(
        "hero-report",
        "tests.fixtures.report_fixtures:build_hero_report",
        DOCS_DEMO_DIR,
        build_hero_report,
    ),
)

ALL_REPORT_SPECS = FIXTURE_SPECS + DEMO_SPECS
FIXTURE_NAMES = tuple(spec.name for spec in FIXTURE_SPECS)


def get_report_spec(name: str) -> ReportArtifactSpec:
    """Return a manifest entry by artifact name."""
    for spec in ALL_REPORT_SPECS:
        if spec.name == name:
            return spec
    raise KeyError(name)


def write_fixture_json(spec: ReportArtifactSpec) -> Path:
    """Write one deterministic JSON artifact."""
    report, insights = spec.builder()
    spec.json_path.parent.mkdir(parents=True, exist_ok=True)
    generate_json(report, spec.json_path, insights=insights)
    return spec.json_path


def regenerate_all_fixture_json() -> list[Path]:
    """Regenerate every checked-in JSON fixture and demo JSON artifact."""
    return [write_fixture_json(spec) for spec in ALL_REPORT_SPECS]
