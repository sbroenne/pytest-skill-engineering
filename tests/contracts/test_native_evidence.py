"""Offline evidence persistence contracts, not model-performance tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pytest_skill_engineering.core.result import EvalResult, ToolCall, Turn, UsageInfo
from pytest_skill_engineering.core.serialization import serialize_dataclass
from pytest_skill_engineering.reporting import (
    SuiteReport,
    build_suite_report,
    generate_json,
    load_suite_report,
)
from pytest_skill_engineering.reporting import TestReport as CaseReport


def _suite() -> SuiteReport:
    return build_suite_report(
        [
            CaseReport(
                name="test_output[model-one]",
                outcome="failed",
                duration_ms=20,
                error="AssertionError: output differs",
                agent_id="helper",
                eval_name="helper",
                model="model-one",
                properties=[("verification", {"expected": 5, "actual": 4})],
                eval_result=EvalResult(
                    turns=[
                        Turn(role="user", content="Add two numbers."),
                        Turn(
                            role="assistant",
                            content="",
                            tool_calls=[
                                ToolCall(
                                    name="add",
                                    arguments={"a": 2, "b": 3},
                                    result="4",
                                    call_id="call-1",
                                    completion_received=True,
                                    success=True,
                                    image_content=b"recorded-image",
                                    image_media_type="image/png",
                                )
                            ],
                        ),
                    ],
                    success=True,
                    evidence_complete=True,
                    effective_system_prompt="Use supplied tools.",
                    configuration={"name": "helper", "model": "model-one"},
                    usage=[UsageInfo(model="model-one", input_tokens=None, output_tokens=20)],
                    stop_reason="completed",
                    tool_calls_admitted=1,
                ),
            )
        ],
        name="Native evidence",
    )


def test_evidence_round_trip_is_lossless_and_has_no_rankings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setenv("COPILOT_CLI_PATH", str(tmp_path / "absent-copilot.exe"))
    suite = _suite()
    suite.models_without_pricing = ["model-one"]
    path = tmp_path / "evidence.json"
    before = serialize_dataclass(suite)
    generate_json(suite, path)
    restored = load_suite_report(path)
    assert serialize_dataclass(restored) == before
    assert serialize_dataclass(suite) == before
    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data) == {
        "schema_version",
        "name",
        "timestamp",
        "duration_ms",
        "tests",
        "passed",
        "failed",
        "skipped",
        "suite_docstring",
        "models_without_pricing",
    }
    assert data["schema_version"] == "4.0"
    assert data["tests"][0]["outcome"] == "failed"
    assert data["tests"][0]["eval_result"]["success"] is True
    assert not {"insights", "leaderboard", "winner", "rankings"} & data.keys()


def test_model_and_configuration_variants_remain_separate_without_ranking(tmp_path: Path) -> None:
    suite = _suite()
    other = _suite().tests[0]
    other.model = "model-two"
    assert other.eval_result is not None
    other.eval_result.configuration["model"] = "model-two"
    other.eval_result.effective_system_prompt = "Different system prompt."
    suite = build_suite_report([*suite.tests, other], name="Configuration variants")
    path = tmp_path / "evidence.json"
    generate_json(suite, path)
    restored = load_suite_report(path)
    assert [case.model for case in restored.tests] == ["model-one", "model-two"]
    assert [case.agent_id for case in restored.tests] == ["helper", "helper"]
    assert [case.eval_result.configuration for case in restored.tests if case.eval_result] == [
        {"name": "helper", "model": "model-one"},
        {"name": "helper", "model": "model-two"},
    ]


@pytest.mark.parametrize("version", ["3.0", "unknown", None])
def test_old_or_missing_schema_is_an_error(tmp_path: Path, version: str | None) -> None:
    path = tmp_path / "evidence.json"
    data = serialize_dataclass(_suite())
    data["schema_version"] = version
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported schema version"):
        load_suite_report(path)


def test_advisory_payload_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "evidence.json"
    data = serialize_dataclass(_suite())
    data.update(schema_version="4.0", insights={})
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="AI insights"):
        load_suite_report(path)


def test_missing_skill_discovery_is_not_inferred_from_configuration(tmp_path: Path) -> None:
    path = tmp_path / "evidence.json"
    data = serialize_dataclass(_suite())
    data["schema_version"] = "4.0"
    result = data["tests"][0]["eval_result"]
    result["configuration"]["skill_directories"] = ["requested-only"]
    del result["skill_discovery"]
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="missing required field 'skill_discovery'"):
        load_suite_report(path)


def test_empty_image_payload_is_not_changed_to_missing_evidence(tmp_path: Path) -> None:
    suite = _suite()
    result = suite.tests[0].eval_result
    assert result is not None
    result.all_tool_calls[0].image_content = b""
    path = tmp_path / "evidence.json"
    generate_json(suite, path)
    assert serialize_dataclass(load_suite_report(path)) == serialize_dataclass(suite)


def test_failed_publication_preserves_previous_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pytest_skill_engineering.reporting import generator

    path = tmp_path / "evidence.json"
    generate_json(_suite(), path)
    original = path.read_bytes()

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("Simulated write failure")

    monkeypatch.setattr(generator.os, "replace", fail_replace)
    with pytest.raises(OSError, match="Simulated write failure"):
        generate_json(_suite(), path)
    assert path.read_bytes() == original
    assert not list(tmp_path.glob(".evidence.json.*"))


def test_non_json_properties_are_not_silently_stringified(tmp_path: Path) -> None:
    path = tmp_path / "evidence.json"
    generate_json(_suite(), path)
    original = path.read_bytes()
    suite = _suite()
    suite.tests[0].properties.append(("unsupported", object()))
    with pytest.raises(TypeError, match="not JSON serializable"):
        generate_json(suite, path)
    assert path.read_bytes() == original
    assert not list(tmp_path.glob(".evidence.json.*"))


def test_output_failure_is_explicit_and_cleanup_still_runs(pytester: pytest.Pytester) -> None:
    pytester.makeconftest("""
        from pathlib import Path
        from pytest_skill_engineering.execution import rate_limiter

        def pytest_sessionstart(session):
            rate_limiter.reset_rate_limiters = lambda: Path("cleaned.txt").write_text("cleaned")
    """)
    pytester.makepyfile("""
        from pytest_skill_engineering.copilot import CopilotEval, CopilotResult
        from pytest_skill_engineering.copilot.fixtures import stash_on_item

        def test_output(request):
            stash_on_item(request.node, CopilotEval(name="test", model="recorded"),
                          CopilotResult(success=True))
    """)
    (pytester.path / "blocked").write_text("not a directory", encoding="utf-8")
    run = pytester.runpytest_subprocess(
        "-o",
        "addopts=",
        "--aitest-json=blocked/evidence.json",
        "-q",
    )
    run.assert_outcomes(passed=1)
    assert run.ret == pytest.ExitCode.TESTS_FAILED
    assert "Failed to save execution evidence" in run.stdout.str() + run.stderr.str()
    assert (pytester.path / "cleaned.txt").read_text() == "cleaned"
