# Historical experiment: why we removed our companion skill

This sample preserves the experiment that led us to remove our proposed
companion skill. It exercises a real customer workflow: write a
test, run it against a broken invoice CLI, investigate the captured failure,
repair the application, and rerun the unchanged test.

There is no AI judge. Ordinary pytest assertions and fixed, independent CLI
checks decide whether the output is correct. The coding agent interprets the
failure and makes the repair.

There is no installable framework companion skill. The original evaluated
guidance is frozen under `fixtures\retired-companion` as test data. The sample
materializes an SDK skill only inside each temporary experiment workspace.
It is not maintained, advertised, or installed as product guidance.

The basic invoice case is a workflow smoke test. The harder imported-order
checkout case tests interacting money and persistence defects with 42 fixed
checks and repeated, independently scored workflow cases. See the
[use case](../../docs/use-cases/companion-skill.md) for the experiment and results.

## Local setup and offline checks

Use a checkout containing the 1.0 changes. From the repository root:

```powershell
cd examples\skill-dogfood
uv sync --frozen
uv run --frozen python -m pytest -q
```

The sample explicitly depends on the framework checkout at `..\..`; it does not
need an unpublished PyPI release. Its lock and environment are separate from the
repository's development environment.

Default collection includes only `tests\offline`. These checks cover the seeded
rounding fault, the fixed output criteria, file permissions, single execution,
and rejection of failures that have no real Copilot tool execution. Offline
checks block creation of Copilot clients; they prove these boundaries, not model
performance.

## Run the real comparison explicitly

Only run this in an approved environment for executing generated code.
Authenticate with a GitHub account that has Copilot access:

```powershell
gh auth login --hostname github.com
uv run --frozen python -m pytest "tests\live\test_workflow.py" -v --aitest-json=..\..\aitest-reports\skill-dogfood\comparison.json
```

The two cases run sequentially: `without-skill` and `with-skill`. To select one,
add `-k "with-skill"` or `-k "without-skill"`. There is no dedicated GitHub
workflow, automatic paid job, execution retry, or model fallback.

A completed pair starts eight framework sessions: author, failing consumer run,
repair, and passing consumer run for each variant. A session can make multiple
model requests, so this is **not** a fixed billing estimate. The model is
`gpt-5.6-luna`; authoring and repair have 180-second limits and 24-tool-call caps.
Each consumer session has a 120-second limit and a four-tool-call cap, with the
guarded invoice tool allowed to execute only once.

Both variants get the same tasks, system prompts, starting application,
requirements, fixtures, model, and checks. Only skill availability differs.
The control disables the historical skill explicitly. The other case registers
its temporary fixture directory and must actually read `SKILL.md` during both
authoring and investigation. The stored source is named `instructions.txt` so it
is not discoverable as an installable skill. Its bytes match the original
evaluated version; there is no product skill or installation command.

## What must happen

The coding agent can write only `test_invoice.py` while authoring. Trusted
fixtures supply `CopilotEval`, `copilot_eval`, the exact invoice request, and the
actual CLI response. The written test must fail on the original application's
rounding behavior, after a genuine completed invoice tool execution. A syntax
error, authentication failure, skipped test, or session-completion check alone
does not satisfy this requirement.

The repair stage receives the actual native `before.json`, requirements,
application source, and authored test. It can write only `invoice_cli.py`.
The original test, requirements, fixture configuration, and before evidence
must remain unchanged. Sixteen independent checks then cover integer-cent
output, ordinary invoices, rounding boundaries, zero amounts, and invalid input.
The unchanged authored test must also pass after repair.

The first child pytest run is **supposed to fail**. The full workflow passes
only when the real failure was observed and the repair satisfies both sets of
checks. Each comparison case has its own pytest outcome; a control failure stays
visible rather than being retried or marked as an expected failure.

## Read the evidence

All evidence uses the framework's native schema:

| File | Contains |
| --- | --- |
| `aitest-reports\skill-dogfood\comparison.json` at the repository root | Authoring/repair sessions and recorded workflow checks |
| `aitest-reports\skill-dogfood\<variant>\<run-id>\before.json` | Actual failed consumer test and invoice output |
| `aitest-reports\skill-dogfood\<variant>\<run-id>\after.json` | Actual passing consumer test and invoice output |

The outer evidence records child file locations, pytest output, actual guidance
reads, and independent CLI checks through `record_property`. It does not fold
child sessions into its usage totals. Inspect each native file for its own usage;
missing usage or pricing is not zero. Failed runs retain whatever evidence was
produced, and generated JSON must never be hand-edited.

Both variants passing is a valid result. One pair establishes that this example
works, **not** that the skill improves performance. Any larger comparison needs
explicitly authorized repetitions and the same fixed criteria.

## Harder, repeated checkout comparison

From this sample directory, explicitly select the harder file:

```powershell
uv run --frozen python -m pytest "tests\live\test_checkout_workflow.py" --aitest-iterations=3 -v --aitest-json=..\..\aitest-reports\skill-dogfood\checkout-reproduction.json
```

This collects three pairs, alternating which variant goes first. Every case
starts with fresh files. A complete comparison starts up to 24 framework
sessions; failures stop that case's remaining stages rather than trigger retries.
Those sessions can make multiple model requests.

The imported-order CLI has interacting rounding, discount/tax, duplicate-post,
conflict, and persistence faults. A successful response is not enough: the
customer test sees real command replies and snapshots of the actual ledger.
The workflow previews an order, posts it, repeats the post, attempts a conflicting
request, posts a different order, and reads the ledger. Repairs must pass 42
fixed checks, preserve all inputs and criteria, and pass the unchanged authored
test. Invalid-input and missing-ledger behavior are checked independently too.

Native child evidence lives under
`aitest-reports\skill-dogfood\checkout\<variant>\<run-id>` at the repository root.
Outer properties record the actual variant, trial, criteria, protocol and skill hashes,
Python/SDK versions, completed milestones, and evidence paths. No custom report
or combined usage total is produced.

Do not select repetitions until paid execution is authorized. The recorded
comparison and its limitations belong in the [use case](../../docs/use-cases/companion-skill.md),
not in a claim that the skill must win.

The corrected 30 September 2026 run completed **1 of 3** control workflows and
**0 of 3** skill-enabled workflows. Correct application repairs passed all 42
checks in two control cases and one skill case, but two of those still failed
their unchanged, incorrectly authored tests. This run demonstrated no skill
benefit. Failures remain recorded; a small sample does not prove general harm.

An attempted revision added general test-writing advice rather than knowledge
specific to using the framework. That comparison was stopped and supports no
completed improvement claim. We chose to remove the product skill rather than
keep tuning this known task. The case study preserves that decision.

## Boundaries and source layout

All model execution belongs to `CopilotEval` and `copilot_eval`. The sample owns
the application, guarded tool adapters, subprocess invocation of pytest, and
independent checks. It creates no SDK sessions, usage collector, or alternate
report format. The repository regression test in
`tests\integration\copilot\test_19_customer_workflow.py` reuses the no-skill
workflow. Testing other domain skills remains a framework capability.

`starter.py` is copied into a fresh temporary consumer project. `application.py`
owns the fixed cases; `consumer.py` owns trusted consumer fixtures; `workflow.py`
owns the author-run-repair-rerun sequence. Agents cannot write those sample files
through the exposed tools.

File permissions and AST checks are **not an operating-system sandbox**.
Generated tests run with the current user's access and Copilot authentication.
The CLI subprocess gets a reduced environment, but can still access files and
the network as that user. Do not run untrusted generated code on a sensitive
machine merely because it passes these checks.
