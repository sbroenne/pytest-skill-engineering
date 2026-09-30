# We tested our own companion skill and chose not to ship it

The framework should run tasks and preserve evidence. The coding agent already
helping the user should interpret the evidence and improve the project. This
case study records whether our proposed companion skill helped that coding
agent, rather than assuming that another guidance layer was an improvement.

**Decision: remove the framework companion skill.** The completed experiment
showed no benefit, while attempted improvements drifted into general advice
about writing tests. We kept the runner, evidence, documentation, and examples.
Testing consumer-provided domain skills remains supported.

The runnable project is
[`examples/skill-dogfood`](https://github.com/sbroenne/pytest-skill-engineering/tree/main/examples/skill-dogfood).
It uses `CopilotEval`, `copilot_eval`, ordinary pytest assertions, and native JSON.
There is no second AI judge, report adviser, custom SDK runner, or hidden retry.
The original guidance survives only as a frozen historical test fixture, not
an installable or maintained product.

## Start with a real baseline

Our first case asked a coding agent to write a test for an invoice CLI,
observe an actual rounding failure, repair the CLI, and rerun the unchanged
test. Both the skill-enabled and control workflows passed all 16 independent
output checks.

| Observation in the basic case | Without skill | With skill |
| --- | --- | --- |
| Correct repair and unchanged test passed | Yes | Yes |
| Tool uses while authoring | 6 | 9 |
| Tool uses while investigating and repairing | 8 | 11 |

This established that the workflow worked, not that the skill helped. Reading
guidance added work without an observed correctness gain. A straightforward
rounding repair was insufficient to answer a reliability question.

## A harder customer project

The second case uses an imported-order checkout CLI with durable ledger state.
Its workflow is preview, first post, repeated post, conflicting request, second
order, and ledger read. Multiple faults interact: monetary rounding and tax
basis, duplicate posting, conflicting request handling, and the difference
between a successful response and the data actually saved.

The requirements are explicit before execution:

| Requirement | Independently observed evidence |
| --- | --- |
| Discount before tax, with per-line half-cent rounding upwards | Exact integer-cent command output |
| Preview has no side effects | Actual absence of the ledger |
| Same request is idempotent | Unchanged on-disk ledger after the repeated post |
| Conflicting request is rejected | Exit code 2, visible error, unchanged ledger |
| Saved amounts match reported amounts | Exact postings and request records read from disk |
| Other orders and invalid inputs behave correctly | Separate fixed CLI cases |

Forty-two independent checks live outside the model-writable project. Expected
money amounts are explicit constants, not calculated using the application.
JSON types are checked exactly: a boolean or float is not an integer-cent amount.
The initial failure must be a real business assertion failure after a completed
tool execution, not a syntax, import, or authentication error.

## Comparison design

Use three independent pairs with fresh projects. Both variants receive the same
tasks, system prompts, fixtures, inputs, starting source, model, limits, and
output criteria. Only access to the proposed companion skill changed. The
control disables that skill; the treatment must actually read it during
authoring and investigation.

The order alternates between trials to reduce a consistent first/second-order
advantage. The model is `gpt-5.6-luna`. Authoring and repair each have a
180-second limit and a 24-tool-call cap. Each consumer session has a 120-second
limit and a four-tool-call cap, with one permitted checkout workflow invocation.

The author can write only the test. The investigator can write only the CLI.
Tests, inputs, requirements, and failed-before evidence must remain unchanged.
Cases have separate pytest outcomes. Failed cases remain failed; there are no
automatic retries or expected-failure labels to manufacture a better result.
The skill and criteria are not tuned after seeing comparison outcomes.

The main measure is complete first-run workflow success: valid authored test,
genuine before failure, repair satisfying all 42 checks, and unchanged after test
passing. Record the failed stage too. Tool uses and captured usage are secondary
observations, not substitutes for correctness or automatic quality scores.

## Run it locally

Use an approved environment for executing generated code. From the repository:

```powershell
cd examples\skill-dogfood
uv sync --frozen
uv run --frozen python -m pytest -q
```

Default collection is offline and blocks Copilot client creation. Those checks
validate the application and harness boundaries, not skill effectiveness.

After explicitly authorizing live execution:

```powershell
gh auth login --hostname github.com
uv run --frozen python -m pytest "tests\live\test_checkout_workflow.py" --aitest-iterations=3 -v --aitest-json=..\..\aitest-reports\skill-dogfood\checkout-reproduction.json
```

Three completed pairs can start 24 framework sessions. Each can make multiple
model requests; that count is not a billing estimate. No dedicated workflow or
automatic paid CI job is added.

Reproduction uses the byte-identical original guidance stored as
`examples\skill-dogfood\fixtures\retired-companion\instructions.txt`, with its two
frozen reference files. Fixture checkout attributes preserve the original CRLF
bytes and recorded hashes on every platform. The sample creates `SKILL.md` only inside a temporary
experiment workspace, where the SDK can load it. No companion skill is
distributed from the repository's product skill directory. Harness code changed
to load that historical fixture after removal, so a new reproduction records
its own protocol hash; it does not overwrite or impersonate the original run.

## Recorded results

The first checkout batch produced six failed workflows, but four were blocked
by a defect in our harness: fingerprint verification requires normal hashing,
while an undeclared import restriction rejected it. The API also did not expose
the immutable input bytes through a fixture, encouraging direct file access.
That batch is retained as `checkout-comparison-2026-09-30.json`, but is not a
valid skill comparison. Its failures must not be attributed to the skill.

We corrected the harness equally for both variants: permitted standard hashing,
provided input text and real fingerprints through `checkout_inputs`, documented
import/file-access rules, and allowed plain assertion helpers. No monetary
expectation, application requirement, seeded defect, model, limit, or skill
instruction changed. A new, separately saved batch establishes the baseline
under that corrected protocol; it is not a hidden execution retry.

### Corrected comparison: 30 September 2026

**The skill did not improve the measured result in this experiment.**
The control completed one of three workflows; the skill-enabled version
completed none. All six authored tests reached a genuine business failure and
all six repair sessions completed. The failures were not authentication,
transport, capture, or import problems.

| Measure | Without skill | With skill |
| --- | --- | --- |
| Complete workflow: all checks and unchanged test pass | 1 of 3 | 0 of 3 |
| Authored test has correct monetary expectations | 1 of 3 | 0 of 3 |
| Repaired CLI passes all 42 independent checks | 2 of 3 | 1 of 3 |
| Tool uses in authoring sessions | 28 | 38 |
| Tool uses in repair sessions | 29 | 48 |

Tool-use totals are observations from the outer authoring/repair traces, not
model-request counts or complete-workflow cost. They include guidance reading.
The six workflows are the six observations; the two outer session records per
workflow are not additional independent samples.

| Trial | Without skill | With skill |
| --- | --- | --- |
| 1 | CLI passes 42/42 checks; unchanged authored test still has wrong tax expectations | CLI passes 29/42 checks; wrong monetary behavior remains |
| 2 | CLI passes 42/42 checks and unchanged test passes | CLI passes 29/42 checks; wrong monetary behavior remains |
| 3 | CLI passes 29/42 checks; wrong monetary behavior remains | CLI passes 42/42 checks; unchanged authored test has wrong order amounts |

Five of six authored tests had **incorrect monetary expectations**. For the first order,
the requirements give subtotal 50 cents, rounded discount 23 cents, net 27
cents, tax 4 cents, and total 31 cents. Several tests instead expected tax
8 cents and total 35 cents. Some repairs then preserved those wrong values
rather than satisfy the customer's tax-on-discounted-amount rule.

Two workflows repaired the application correctly but still failed the unchanged
test because its expectations were wrong. That failure is intentional and
important: a coding agent must not quietly rewrite criteria after seeing a
failure. The independent checks exposed the disagreement instead of letting
the authored test become the sole source of truth.

We did not alter the skill, weaken criteria, retry failed observations, or keep
increasing complexity until a favorable result appeared. In this small sample,
the skill required more tool work and showed no correctness benefit. Three
pairs do not establish that it generally harms performance or never helps.

### Evidence provenance

The corrected batch is saved locally as
`aitest-reports\skill-dogfood\checkout-comparison-v2-2026-09-30.json`.
It used Python 3.11.15, GitHub Copilot SDK 1.0.15, and `gpt-5.6-luna`.
All six cases recorded identical criteria, protocol, skill, and environment
identifiers. Actual skill reads were recorded in every treatment authoring and
repair session; registration alone was not treated as proof of use.

| Identifier | SHA-256 |
| --- | --- |
| Corrected native outer evidence | `73084355efeec0e5304ea83b32a4c143e575e63d3605924c134fcc542db3d0e0` |
| Fixed business criteria | `4014bef13d0c553487c14a3a3374f53da79cfd5be4302d7678e01556a038223a` |
| Corrected experiment protocol | `b3437d192436594bf84b000c5ca12491de3aebe60fb601942e98491438de8c5b` |
| Canonical skill | `4654291384d760eecc26b3a00d901934a6da62e346c84702878e595147318f32` |

Hashes identify this recorded run, not a promise that later runs will be
identical. Native JSON and the linked child files are retained locally and
are not hand-edited or embedded in the public documentation.

## What this use case establishes

The runner-and-evidence boundary worked: it preserved real failures, showed
that session completion was not business correctness, and let independent
checks catch wrong assertions and incomplete repairs. No extra AI judge was
needed to decide those concrete requirements.

The original companion skill remained an **unproven aid for this workflow**,
not a demonstrated performance improvement. More complex tasks and additional
guidance did not automatically produce better outcomes. Keep domain criteria
independently grounded; do not promote the skill as improving reliability on
the basis of this experiment.

## The attempted improvement changed the question

The original result is retained above. After that comparison, the user asked us
to improve the skill and measure whether the result improves. This is an
explicitly task-targeted development exercise, not an untouched evaluation.

Draft revision 1.0.1 added a requirement-first verification step:

- Derive expected answers from actual inputs before reading the implementation.
- Check units, quantities, operation order, intermediate values, and rounding.
- Audit the derivation a second way and record it before execution.
- Compare requirements, test expectations, observed output, and saved state
  separately when investigating a failure.
- Never change an application to satisfy an incorrect test.

The guidance is general: it contains no order identifiers, fixture amounts,
expected checkout totals, or copies of the benchmark's independent answers.
The customer task, fixtures, starting defects, model, request limits, and all
42 independent checks remain unchanged.

The planned evaluation was a fresh three-pair comparison with new control
observations, alternating order, and a separate native evidence file.

For that development comparison, the target was at least two of three complete
skill-enabled workflows and more complete workflows than the fresh control.
Correct application repairs and correctly authored expectations are separate
secondary measures. The run was stopped rather than evaluated against that target.

### Revision 1.0.1

The three-pair run was started with output directed to
`aitest-reports\skill-dogfood\checkout-skill-1.0.1-2026-09-30.json`,
then stopped when the user reconsidered whether the companion skill should
exist. It is not a completed comparison and provides no validated improvement
claim for this draft revision.
The main guidance hash for this draft revision was
`7edb7576f3b890b17ed761531913e69fd35292b92c09bb2455b3cbf89c97d935`.

Even an improvement on this known task would not establish improvement on unseen
projects. More importantly, the revision was teaching general calculation and
test-writing discipline, not missing knowledge about using our framework.

## Conclusion: a simpler product is the useful result

The original idea was attractive: replace framework-owned AI analysis with a
skill used by the coding agent already working in the repository. Testing that
idea revealed a third option: **keep neither extra layer**.

Both variants used the framework successfully. The main failures involved
incorrect business expectations, not inability to discover or operate the
framework. The completed comparison did not establish a reason to distribute
and maintain our own companion skill. Attempting to tune it shifted the question
from tool usability to general coding-agent reasoning.

We removed the companion skill, its installation instructions, and its
onboarding references. Framework-specific knowledge belongs in clear
documentation, working examples, and useful errors. Coding agents can investigate
ordinary pytest failures and native evidence directly.

This is a product decision under limited evidence, not proof that skills are
useless or that our skill causes harm. Domain skills with substantial
task-specific knowledge can still be evaluated through the framework's existing
skill support.

The failed comparisons, harness correction, and interrupted revision stay in
the case study. Historical guidance is frozen as experimental input, not kept
alive as a supported product. The lesson is not "make the skill win"; it is
**test whether the extra layer deserves to exist, and be willing to remove it**.

## Evidence and interpretation

The outer JSON contains authoring/repair traces and recorded workflow properties.
Each case links to its own native `before.json` and, when reached, `after.json`
under `aitest-reports\skill-dogfood\checkout\<variant>\<run-id>`. Locations shown
here are relative to the repository root; native properties preserve actual
local paths. Files are local generated outputs, not bundled public evidence
or a new report format.

Record trial, actual variant, criteria, protocol and skill hashes, Python/SDK versions,
completed milestones, real CLI checks, and child evidence paths. The before
record preserves the actual bad reply and ledger. Do not hand-edit JSON.

Outer usage covers authoring and repair, not the separate child pytest sessions.
Read each native file's own usage; missing pricing or usage is not measured zero.
Do not present outer timing or usage as the complete workflow cost.

Three pairs are a small, single-project experiment. Even a difference would be
an observation under these conditions, not proof of general causal improvement.
Both variants passing, both failing, or the skill performing worse are valid
results. More complexity does not entitle us to keep changing the task until the
skill wins.

File guards and AST checks are not an operating-system sandbox. Generated code
runs with the current user's access; reduced CLI environment variables do not
prevent file or network access. Use the isolation approved for your project.
