# Upgrading to pytest-copilot 2.0

Version 2.0 renames the project without changing how tasks run or how assertions
check their results. Replace your dependency on `pytest-skill-engineering` with
`pytest-copilot>=2.0.0,<3`; update imports from `pytest_skill_engineering` to
`pytest_copilot`, `CopilotEval` to `CopilotTask`, and the `copilot_eval` fixture to
`copilot_run`. Direct calls to `run_copilot` keep their name.

The command is now `pytest-copilot`, and `init` creates
`tests/test_copilot_run.py`. There are no old-name imports, commands, or fixtures.
Report options such as `--aitest-json`, report folders, native JSON schema 4.0,
and consumer-owned output checks are unchanged. Existing saved evidence does not
need to be rewritten.

```bash
uv remove pytest-skill-engineering
uv add "pytest-copilot>=2.0.0,<3"
```

The existing GitHub repository was renamed, not replaced. Old releases
remain historical; the new package is published separately on PyPI.

## Changes for users upgrading from 0.6.x

**Version 1.0 is a breaking change.** Tests now use real Copilot execution,
ordinary pytest assertions, and saved JSON evidence. Built-in AI judging,
analysis, refinement, and report rendering were removed, not deprecated.

The remaining sections explain the earlier 1.0 removals using current examples.
New projects should follow
[getting started](getting-started/index.md).

## Upgrade

```bash
uv add "pytest-copilot>=2.0.0,<3"
```

After upgrading, replace removed assertions, delete retired flags, and regenerate
evidence with the current producer. There are no compatibility aliases or legacy
readers. No framework companion skill is required or distributed.

## Removed fixtures and APIs

| Removed surface | What to use instead |
| --- | --- |
| `llm_assert`, `llm_score`, `LLMScore` | Ordinary assertions against concrete output; subjective review is advice |
| `ScoringDimension`, `ScoreResult`, `assert_score` | Explicit measurable checks, not automatic answer scores |
| `skill_refiner`, `analyze_skill_failures`, `RefinementResult`, `RefinementSuggestion` | Current coding agent, source investigation, and targeted reruns |
| `skill_eval_runner`, `SkillCaseResult`, `SkillGradingResult` | `load_skill_evals`, pytest parametrization, `copilot_run`, consumer-owned checks |
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

Old 0.6.x code (no longer supported):

```python
async def test_document(copilot_eval, llm_assert):
    result = await copilot_eval(agent, "Save the document.")
    assert llm_assert(result.final_response, "confirms that the document was saved")
```

Current code:

```python
from pytest_copilot.copilot import CopilotTask


async def test_document(copilot_run, tmp_path, record_property):
    agent = CopilotTask(
        name="document",
        model="gpt-5.6-luna",
        instructions="Save the requested document exactly.",
        working_directory=str(tmp_path),
    )
    result = await copilot_run(agent, "Write document.txt containing exactly Approved.")
    output = tmp_path / "document.txt"
    verified = output.is_file() and output.read_text() == "Approved."
    record_property("verification", {"artifact": str(output), "passed": verified})
    assert verified
    assert result.success, result.error
```

The new criterion checks a saved file, not a convincing claim about saving it. Do not
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

There is no summary-model requirement. Authentication is needed for live task
execution, not for reading saved evidence.

## Native evidence API and schema

To read or write current native evidence:

```python
from pytest_copilot.reporting import generate_json, load_suite_report

report = load_suite_report(path)
generate_json(report, json_path)
```

`load_suite_report` returns a `SuiteReport`, not `(report, insights)`.
There is no rendering API or regeneration CLI.

Schema **4.0** replaces 3.0. The `insights` payload, score presentation, and
analysis-cost fields are gone. `models_without_pricing` is saved with the suite,
so unavailable prices remain explicit when evidence is loaded. Execution
configuration, usage, request audits, tool completion evidence, and verification
properties remain.

Old JSON is rejected. Archive it if needed, then rerun its test producer with
the current version. Never hand-edit JSON or synthesize missing evidence to upgrade its version.
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

`CopilotTask`, `copilot_run`, `ab_run`, native tool and custom agent dispatch
evidence, images, plugins, configuration loaders, pytest repetitions, pass-rate
gates, request auditing, usage, permission controls, guarded tool adapters,
timeouts, and safe cleanup remain.

Audited transports close before their owning SDK client. Reading evidence and
finishing a pytest session do not start an extra judge or adviser session.
