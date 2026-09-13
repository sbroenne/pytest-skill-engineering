---
description: "Generate HTML and Markdown reports from pytest runs or from saved JSON, using Copilot models for AI insights."
---

# How to generate reports

## Recommended pytest configuration

```toml
[tool.pytest.ini_options]
addopts = """
--aitest-summary-model=copilot/gpt-5.4-mini
--aitest-html=aitest-reports/report.html
"""
```

Start with `copilot/gpt-5.4-mini` for routine report analysis. Opt into larger models only when you need a more expensive comparison or deeper write-up.

## Run pytest

```bash
uv run python -m pytest tests/ -v
```

JSON is always written. HTML and Markdown reports require a summary model.

## Regenerate from saved JSON

Use this for report-template work and for re-rendering without new LLM calls:

```bash
uv run pytest-skill-engineering-report aitest-reports/results.json   --html aitest-reports/report.html
```

## Refresh AI insights

```bash
uv run pytest-skill-engineering-report aitest-reports/results.json   --html aitest-reports/report.html   --summary   --summary-model copilot/gpt-5.4-mini
```

## Evidence-only summaries and separate assessment

The judge uses SDK empty mode, an explicit empty tool allowlist, no attached MCP
or custom tools, disabled configuration/skill/hook discovery, and temporary
working and Copilot storage directories. Every permission request is rejected.
These settings require `github-copilot-sdk>=1.0.9`. They restrict the judge's
capabilities through the SDK; they are not an operating-system sandbox.

Supply authentication through `GITHUB_TOKEN` in the report process. Empty mode
disables the usual Copilot keychain probe, and temporary storage does not contain
the user's saved Copilot configuration. Do not copy credential files into the
temporary directory or include tokens in report arguments or properties.

To assess results independently before paying for a summary:

1. Run the approved evaluations with `-o addopts=` and
   `--aitest-json=aitest-reports\results.json`, without summary, HTML, or Markdown
   options. This native export does not request analysis. Test-owned `llm_assert`
   or `llm_score` calls are separate and must also be excluded if not approved.
2. Inspect the saved evidence and finish the independent assessment.
3. Generate the requested overall summary from that saved JSON:

```powershell
uv run pytest-skill-engineering-report aitest-reports\results.json `
  --html aitest-reports\report.html `
  --json aitest-reports\results.summary.json `
  --summary --summary-model copilot/gpt-5.6-sol `
  --analysis-prompt src\pytest_skill_engineering\prompts\ai_summary.md
```

Use the analysis system prompt path in the framework checkout when running from
a consumer project. This command does not rerun evaluations or change raw JSON.
Before rendering, it saves the successful summary together with all evidence in
native report JSON. `--json` chooses this checkpoint path; with `--summary`, the
default is `<input-stem>.summary.json` next to the input. The checkpoint must be
a new path, distinct from the input and rendered outputs. An existing checkpoint
is rejected before requesting analysis, so it cannot be silently replaced.

If HTML or Markdown rendering fails, reuse the saved checkpoint without
`--summary`. This makes no new model calls:

```powershell
uv run pytest-skill-engineering-report aitest-reports\results.summary.json `
  --html aitest-reports\report.html --md aitest-reports\report.md
```

For summary-only generation, omit `--html` and `--md`; the checkpoint is still
written. `--json` can also save already-loaded insights without requesting new
analysis. Writes use a temporary file followed by replacement, so a partially
written checkpoint is not published as a successful save.

One invocation defaults to at most three summary attempts, with 1- and 2-second
waits after failures. `--summary-attempts` accepts 1, 2, or 3. If one attempt was
already consumed and the total budget is three, use `--summary-attempts 2` for
the remaining invocation and do not start another. The limit is per invocation,
not a persistent cross-process budget. Each attempt creates a new isolated judge
session; SDK/runtime internal model requests are not counted by this retry limit.
Summary token and cost values are currently unavailable; recorded zeros must not
be treated as free usage.

If a requested summary fails, the standalone command returns nonzero and does
not silently reuse older insights. A requested pytest summary/report failure
also makes that command unsuccessful, while preserving raw JSON and running
cleanup. Existing output files from earlier runs are not deleted: use a fresh
output path and check the exit status.

## Compact mode

Use `--aitest-summary-compact` or `--compact` when you want analysis without sending full passing transcripts.

Incomplete traces remain visible even in compact mode. Analysis input includes
test references, call IDs, completion status, errors, and recorded test properties.
Recommendations must distinguish observed facts from inferred advice and cite
that evidence. The framework supplies references but does not validate the prose
returned by an analysis model.

## Record independent verification

Use pytest's `record_property` with JSON-serializable values. Properties are saved
under `tests[].properties` in JSON and shown in HTML and Markdown, alongside
session success and evidence completeness. They also reach AI analysis when it
is explicitly requested.

```python
async def test_saved_document(copilot_eval, record_property, eval_config, expected_file):
    result = await copilot_eval(eval_config, "Save the requested document.")
    verified = expected_file.is_file() and expected_file.read_text() == "Expected text"
    record_property("verification", {
        "status": "verified" if verified else "failed",
        "artifact": expected_file.name,
    })
    assert verified, "Independent file check failed"
    assert result.success
    assert result.evidence_complete
```

The consumer owns application checks, artifact creation, build/version identifiers,
and safe cleanup. Artifact references are recorded as data; the framework does
not copy files or open links. Do not record credentials or private content.
Properties alone do not change pytest's verdict: assert the verification result.
When no verifier ran, record `"status": "not verified"`, not a success.
Tests without an eval result (including setup failures or opt-out skips) remain
in pytest/JUnit output, not the eval report; do not interpret their absence as a pass.

## Keep both sides of a comparison

Runtime eval names do not need to include the model. HTML, Markdown, and analysis
statistics share report-only grouping by recorded identity, model, system prompt,
skill label, and captured configuration. Different configurations under the same
runtime name receive distinct report IDs and model-qualified display labels;
same-model variants also receive configuration numbers. Repeated executions with
the same configuration remain together. Original names, IDs, configuration, and
test evidence in JSON are unchanged. Unambiguous report identities keep their
existing labels and IDs. Only captured configuration can distinguish groups;
record omitted environment/build differences separately.

`ab_run(baseline, treatment, task)` returns both `CopilotResult` objects and saves
both through the existing reporting path. Display names have `(baseline)` and
`(treatment)` suffixes, including when the input names match. Runtime eval names
and result back-references stay unchanged. Saved configuration keeps the original
name and adds `comparison_role` to identify the side. The baseline is
saved before treatment starts, so a treatment exception cannot erase it.

Each result retains its call trace and `eval_result.configuration`: requested
model, system prompt, tool filters, limits, retry settings, persona, selected
agent, skill directories, and server names/types/tool selections. This is a
configuration snapshot, not a complete environment manifest or proof of available
tools. Server commands, arguments, environment variables, URLs, headers, and
arbitrary SDK configuration are deliberately excluded. Record safe build and
environment identifiers explicitly with `record_property`.

Both entries share the enclosing pytest test's outcome and properties. Use
separate `verification_baseline` and `verification_treatment` properties for
per-side evidence; do not interpret a failed comparison assertion as proof both
sides failed their tasks. Report totals count saved eval runs, not pytest test
functions. Multiple calls to `copilot_eval` in one test also retain every result.

Separate working directories do not isolate a desktop or inherited SDK/user
configuration. Use consumer-owned setup and reset between runs; do not use
`ab_run` for a shared desktop that requires a reset between sides. Set
`max_retries=0` when an experiment must not retry whole executions.

## Deterministic checks without models

The framework's event-to-report contract tests use real SDK event parsing,
ordinary pytest reporting, and synthetic event sequences, without running an
agent, desktop tools, or AI analysis:

```powershell
uv run python -m pytest -o addopts= "tests\contracts\test_usage_evidence.py" -q
uv run python -m pytest -o addopts= "tests\contracts\test_report_recovery.py" -q
```

The shared test configuration loads `pytester`, and the existing deterministic
CI job includes both `tests/unit/` and `tests/contracts/` with report options
cleared. Normal discovery under `tests/` also includes the contract checks.

`-o addopts=` clears configured paid summary generation. For an approved consumer
run against an unpublished checkout, add `--with-editable` to `uv run` with the
absolute worktree path. Keep that machine-specific path out of source control.
Record the imported module path, installed framework/SDK versions, and worktree
commit separately: a package version alone does not identify uncommitted fixes.
