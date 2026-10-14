# Write, run, fix, and rerun a customer test

This sample gives a coding agent a broken CLI and fixed customer requirements.
The agent writes a test, observes a real application failure, repairs the CLI,
and reruns the unchanged test. Separate checks verify the repaired application,
because the agent's own test can be wrong too.

It also preserves our historical framework companion-skill experiment.
The guidance is frozen test data under `fixtures/retired-companion`, not a
maintained or installable product skill. The sample materializes it as
`SKILL.md` only inside temporary experiment workspaces. Its stored
`instructions.txt` bytes must remain unchanged.

**Default tests are offline.** Live comparisons consume Copilot requests and
execute generated code; run them only with authorization and approved isolation.
For a simpler first test, use [quickstart](../quickstart/).

## Set up and run offline checks

From the repository root:

```bash
cd examples/skill-dogfood
uv sync --frozen
uv run --frozen python -m pytest -q
```

The sample uses the framework checkout at `../..` with its own environment and
lock. Default collection includes only `tests/offline`.

Offline checks cover the seeded fault, fixed output criteria, file-write
restrictions, single execution, and rejection of failures without real Copilot
tool execution. They block Copilot client creation. They prove sample
boundaries, not model performance.

## Choose a live workflow

| Workflow | Application | Independent checks | Use |
| --- | --- | --- | --- |
| Invoice | A CLI with an incorrect tax-rounding calculation | 16 fixed checks | Smaller workflow smoke test |
| Checkout | Imported orders with rounding, discount/tax, duplicate, conflict, and persistence defects | 42 fixed checks | Harder repeated comparison |

Both compare `without-skill` and `with-skill` under the same tasks, system
prompts, starting application, fixtures, model, budgets, and checks. Only skill
availability differs. The treatment must actually read the historical guidance
during authoring and repair; the control disables it.

### Invoice comparison

From this sample directory:

```bash
gh auth login --hostname github.com
uv run --frozen python -m pytest tests/live/test_workflow.py -v --aitest-json=../../aitest-reports/skill-dogfood/comparison.json
```

The two cases run sequentially. Select one with `-k "with-skill"` or
`-k "without-skill"`. There is no automatic paid job, execution retry, or model
fallback.

A completed pair starts eight framework sessions: author, failing consumer
test, repair, and passing consumer test for each variant. A session may make
multiple model requests, so this is not a fixed billing estimate.

The model is `gpt-5.6-luna`. Authoring and repair each have a 180-second timeout
and 24-tool-call cap. Each consumer session has a 120-second timeout and
four-tool-call cap; the guarded application tool may execute only once.

### Repeated checkout comparison

Authorize the repetitions before running:

```bash
uv run --frozen python -m pytest tests/live/test_checkout_workflow.py --aitest-iterations=3 -v --aitest-json=../../aitest-reports/skill-dogfood/checkout-reproduction.json
```

This runs three fresh pairs, alternating the first variant. A full comparison
starts up to 24 framework sessions. A failure stops that case's remaining
stages; it does not trigger retries.

The workflow previews an order, posts it, repeats the post, attempts a
conflicting request, posts a different order, and reads the ledger. Checks
inspect actual command replies and saved state, including invalid inputs and
missing-ledger behavior. A successful response alone cannot satisfy them.

## What makes a workflow pass

The agent may write only `test_invoice.py` during invoice authoring. Trusted
fixtures supply `CopilotEval`, `copilot_eval`, the exact request, and the actual
CLI response. The test must fail on the original application after genuine,
completed tool execution. Syntax errors, authentication failures, skips, and
session-completion checks do not count as detecting the application fault.

The repair stage receives the native `before.json`, requirements, application
source, and authored test. It may write only `invoice_cli.py`. The test,
requirements, fixture setup, and before evidence stay unchanged. The repaired
application must pass both the original test and the 16 independent checks.
Checkout uses the same principle with its own files and 42 checks.

The first child pytest run is **supposed to fail**. The outer workflow passes
only when it observes that real failure and the repair satisfies both sets of
checks. Each variant has its own pytest outcome; failures stay visible.

## Find and interpret the evidence

All paths below are relative to the repository root:

| Path | Contents |
| --- | --- |
| `aitest-reports/skill-dogfood/comparison.json` | Invoice authoring/repair sessions and recorded workflow checks |
| `aitest-reports/skill-dogfood/<variant>/<run-id>/before.json` | Failed consumer test and actual invoice output |
| `aitest-reports/skill-dogfood/<variant>/<run-id>/after.json` | Passing consumer test and actual invoice output |
| `aitest-reports/skill-dogfood/checkout/<variant>/<run-id>/` | Checkout child evidence |
| The selected checkout reproduction JSON | Checkout authoring/repair sessions and recorded workflow checks |

Outer `record_property` values retain child paths, pytest output, guidance
reads, and independent checks. Checkout also records trial, hashes, versions,
criteria, and completed milestones.

Each file uses the framework's native schema. Outer usage does not include the
separately invoked child pytest sessions; inspect each native file for its own
usage. Missing usage or pricing is not zero. Failed runs preserve whatever
evidence was produced. Never hand-edit generated JSON.

## Historical result, not an expected winner

The simple invoice pair passed in both conditions. That showed the workflow
worked, not that the skill improved it.

The corrected **30 September 2026** checkout comparison completed **1 of 3**
control workflows and **0 of 3** skill-enabled workflows. Two control repairs
and one skill-enabled repair passed all 42 application checks, but two of those
still failed their unchanged, incorrectly authored tests. The comparison did
not demonstrate a skill benefit; the small sample does not prove general harm.

A later revision added general test-writing advice, but its comparison was
stopped. It supports no completed improvement claim. We removed the product
skill rather than keep tuning this task.

The [case study](../../docs/use-cases/companion-skill.md) explains the full
results, excluded runs, and limitations. New execution produces new
observations, not a promised reproduction of those counts.

## Implementation and isolation boundaries

`starter.py` is copied to a fresh consumer project. `application.py` owns the
fixed cases; `consumer.py` supplies trusted fixtures; `workflow.py` runs the
author-fail-repair-pass sequence. The agent's exposed write tools cannot modify
those trusted sample files.

All model execution uses `CopilotEval` and `copilot_eval`. The sample owns the
application, guarded adapters, child pytest subprocesses, and independent checks.
It has no separate SDK runner, usage collector, or report format.
`tests/integration/copilot/test_19_customer_workflow.py` reuses the no-skill
workflow as framework regression coverage.

**File-write restrictions and AST checks are not an operating-system sandbox.**
Generated tests run with the current user's access and Copilot authentication.
The CLI subprocess has a reduced environment but can still access files and the
network. Do not run untrusted generated code on a sensitive machine.
