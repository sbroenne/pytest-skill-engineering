# Migrating to 1.0.0

**This is a breaking release.** Version 1.0 keeps real Copilot execution,
controls, ordinary pytest output, and JSON evidence. It removes the separate AI
judging, analysis, refinement, and report-presentation layers. There are no
compatibility aliases, legacy readers, or optional versions of the removed features.

## Upgrade

```powershell
uv add "pytest-skill-engineering>=1.0.0,<2"
```

No companion skill installation is required or distributed. Use the framework
documentation and [evidence inspection guide](how-to/inspect-evidence.md).
The [case study](use-cases/companion-skill.md) explains that product decision.

## Removed fixtures and APIs

| Removed surface | What to use instead |
| --- | --- |
| `llm_assert`, `llm_score`, `LLMScore` | Ordinary assertions against concrete output; subjective review is advice |
| `ScoringDimension`, `ScoreResult`, `assert_score` | Explicit measurable checks, not automatic answer scores |
| `skill_refiner`, `analyze_skill_failures`, `RefinementResult`, `RefinementSuggestion` | Current coding agent, source investigation, and targeted reruns |
| `skill_eval_runner`, `SkillCaseResult`, `SkillGradingResult` | `load_skill_evals`, pytest parametrization, `copilot_eval`, consumer-owned checks |
| `skill_benchmark`, `SkillBenchmarkResult`, `CaseBenchmark`, `BenchmarkComparison` | `ab_run`, fixed criteria, side-specific verification, and repetitions |
| `InsightsResult` and `reporting.insights` | Native execution evidence and coding-agent-led interpretation |
| `generate_html`, `generate_md`, `generate_mermaid_sequence` | Ordinary pytest output and JSON evidence |
| `pytest-skill-engineering-report`, `pytest_skill_engineering.cli` | Read saved JSON directly or use the current native loader |
| HTML/Markdown components, templates, rankings, winner selection, and demo reports | The coding agent investigates saved evidence alongside source |
| `AitestHookSpec`, `pytest_skill_engineering_analysis_prompt` | No replacement adviser hook |
| `get_analysis_prompt`, `get_analysis_prompt_details`, packaged analysis system prompts | Documentation, examples, and coding-agent-led investigation |
| `CopilotEval.max_retries`, `retry_delay_s` | Single-attempt execution; explicitly rerun a selected pytest case |

The judge, analysis, scoring, refinement, automatic grading, and automatic
benchmark modules are removed, not deprecated. Plugins registering the removed
analysis hook must remove that implementation.

`SkillEvalCase`, `load_skill_evals`, `has_skill_evals`, and `export_grading`
remain non-AI helpers. The exporter formats supplied booleans and evidence; it
does not judge a response. Free-text expectations remain descriptions that you
must translate into explicit checks.

Execution no longer retries startup, connection, or task failures. Remove
`max_retries` and `retry_delay_s` from eval construction; removed keywords are
errors. Read the recorded failure before choosing a pytest rerun, such as
`uv run python -m pytest --lf`.

## Replace judging with actual verification

Before:

```python
async def test_document(copilot_eval, llm_assert):
    result = await copilot_eval(agent, "Save the document.")
    assert llm_assert(result.final_response, "confirms that the document was saved")
```

After:

```python
async def test_document(copilot_eval, tmp_path, record_property):
    agent = CopilotEval(
        name="document",
        model="gpt-5.6-luna",
        instructions="Save the requested document exactly.",
        working_directory=str(tmp_path),
    )
    result = await copilot_eval(agent, "Write document.txt containing exactly Approved.")
    output = tmp_path / "document.txt"
    verified = output.is_file() and output.read_text() == "Approved."
    record_property("verification", {"artifact": str(output), "passed": verified})
    assert verified
    assert result.success, result.error
```

Import `CopilotEval` from `pytest_skill_engineering.copilot`. This is a different,
stronger criterion: a saved file, not a convincing claim about saving it. Do not
pretend a substring check is equivalent to a removed semantic judge. If a
requirement remains subjective, review the evidence and label the conclusion
advice rather than a measured framework result.

## Remove retired options and settings

Delete these pytest options from `addopts`, scripts, and CI:

- `--aitest-summary-model`
- `--aitest-analysis-prompt`
- `--aitest-summary-compact`
- `--aitest-print-analysis-prompt`
- `--llm-model`
- `--aitest-html`
- `--aitest-md`

The report CLI is removed entirely, including these options:

- `--summary`, `--summary-model`, `--summary-attempts`
- `--analysis-prompt`, `--compact`, `--print-analysis-prompt`

Remove the retired `AITEST_SUMMARY_MODEL` environment setting and scoring marker
usage. Removed flags fail as unknown arguments; the retired environment setting
does not select a model.

Current configuration:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
addopts = """
--aitest-json=aitest-reports/results.json
"""
```

There is no summary-model requirement. Model authentication is needed for task
execution, not for reading recorded evidence.

## Native evidence API and schema

Current signatures:

```python
report = load_suite_report(path)
generate_json(report, json_path)
```

`load_suite_report` now returns a `SuiteReport`, not `(report, insights)`.
Import `load_suite_report` and `generate_json` from
`pytest_skill_engineering.reporting`. There is no rendering API or regeneration CLI.

Schema **4.0** replaces 3.0. The `insights` payload, score presentation, and
analysis-cost fields are gone. `models_without_pricing` is saved with the suite,
so unavailable prices remain explicit when evidence is loaded. Execution
configuration, usage, request audits, tool completion evidence, and verification
properties remain.

Old JSON is rejected. Archive it if needed, then rerun its test producer with
1.x. Never hand-edit JSON or synthesize missing evidence to upgrade its version.
The synthetic report corpus, screenshots, and report-generation script are retired.

Evidence is published atomically. Unsupported property values or failed writes
are explicit errors and make the pytest command return nonzero. Reading evidence
does not start Copilot or require credentials.

## Comparisons without rankings

`ab_run` remains sequential with separate working directories and native saved
traces. Both entries share one pytest outcome. Record
`baseline_verification` and `treatment_verification` separately before asserting
the combined result. Do not migrate old benchmark improvement percentages by
deriving them from that shared outcome.

The framework no longer ranks configurations or selects a winner. Your coding
agent interprets observations using fixed criteria, representative cases, and
repeated runs.
Unavailable prices are not measured zero cost.

## What is preserved

`CopilotEval`, `copilot_eval`, `ab_run`, native tool and custom agent dispatch
evidence, images, plugins, configuration loaders, pytest repetitions, pass-rate
gates, request auditing, usage, permission controls, guarded tool adapters,
timeouts, and safe cleanup remain.

The incoming WebSocket audit-finalization fix is preserved: audited transports
close before their owning SDK client. No extra judge or adviser session is
started at pytest session finish.
