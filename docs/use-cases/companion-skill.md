# Does a skill help a coding agent? A real-world case study

**We tested a skill intended to help coding agents use this framework. It did
not demonstrate a benefit, so we chose not to ship it.** We kept the test
runner, saved execution records, documentation, and examples.

You do not need to install a companion skill to use pytest-skill-engineering.
The framework still supports testing **your own skills**. Removing our guidance
package did not remove that capability.

## What were we trying to improve?

A coding agent can write code, run tests, and investigate failures. A *skill*
is a package of instructions and reference material that the agent can read
while working.

Our proposed companion skill explained how to use the framework: write tests,
check actual results, inspect saved execution records, and investigate failures.
It was guidance for the agent using the framework, not a separate AI judge.

The question was simple: **does adding that guidance help the agent complete a
real task more reliably than giving it the same project without the skill?**

## What we asked the agent to do

We gave the agent a small application with deliberate bugs. It had to:

1. Write a test from the customer's requirements.
2. Let us run that test and confirm it caught a real application failure.
3. Read the failure and repair the application.
4. Pass both the original, unchanged test and our separate correctness checks.

Those separate checks were written before the experiment and could not be
changed by the agent. This mattered because **the agent's test could be wrong
too**. Passing a test written by the same agent is not enough to establish
that the customer's requirements were met.

### First: a simple invoice calculation

The application rounded a tax amount incorrectly. Both versions of the agent
fixed it and passed all 16 separate checks.

The skill version used more tool calls, including calls to read guidance.
That showed the example worked, but did not show that the skill helped.

### Next: order calculations and saved records

We then used a harder application that imports orders from CSV files and saves
a ledger: a file containing the completed transactions.

The agent needed to handle discounts and tax correctly, avoid charging twice
for a repeated request, reject conflicting requests, and save the same amounts
that it reported to the user. Previewing an order must not change saved records.
Invalid inputs and a missing ledger also had specified behavior.

We checked actual command output and the files on disk, using **42 separate
checks**. A successful response alone could not prove that the saved data was
correct.

For this harder task, we ran three fresh attempts without the skill and three
with it. Both groups received the same requirements, inputs, starting code,
model, and limits. We alternated which group went first. The skill was actually
read in each skill-enabled attempt, not merely made available.

## What happened?

The completed comparison on **30 September 2026** showed no improvement:

| Result in the harder task | Without skill | With skill |
| --- | --- | --- |
| Completed the whole task | 1 of 3 | 0 of 3 |
| Wrote a test with correct expected amounts | 1 of 3 | 0 of 3 |
| Repaired the application to pass all 42 separate checks | 2 of 3 | 1 of 3 |

"Completed the whole task" means the agent wrote a valid test, caught a real
failure, repaired the application correctly, and passed its unchanged test.
All six attempts reached a real application failure and completed the repair
session. The remaining failures were not login, connection, or import failures.

### The important failure: a test can expect the wrong answer

Five of the six generated tests contained incorrect expected amounts.

For example, one order should have had a total of **31 cents**, including
**4 cents of tax** after discount. Several tests instead expected **35 cents**,
including **8 cents of tax**. Some repairs then kept the wrong calculation
rather than satisfy the customer's requirements.

In two attempts, the agent repaired the application correctly, but its unchanged
test still failed because that test expected the wrong answer. Our separate
checks caught the disagreement.

In normal development, an incorrect test should be corrected. In this experiment,
the repair stage could change only the application. Keeping the test unchanged
let us measure whether the agent had written a trustworthy test in the first
place; we did not rewrite failed tests to make the comparison look better.

**A completed agent session is not the same as a correct result. Neither is
agreement between a broken application and an incorrect test.**

## Why not keep improving the skill?

We started a revision that told the agent to derive expected answers from the
requirements, double-check calculations, and distinguish a wrong test from a
broken application. A new comparison began, but we stopped it when we reconsidered
the purpose of the skill. That interrupted run supports no improvement claim.

The revision was becoming general advice about writing tests and reasoning
correctly. It was not filling a demonstrated gap in how agents used our tool.
Both groups had already used the framework successfully.

That changed the product question. Rather than keep adding instructions until
this particular task improved, we asked: **does this extra guidance package
deserve to be part of the framework?**

Our answer was no. Framework-specific knowledge belongs in clear documentation,
working examples, and helpful errors. The coding agent can investigate ordinary
pytest failures and saved execution records directly.

## What this means for users

Use the framework to run tasks and record what happened. Use ordinary assertions
to check actual application output. Give your coding agent the failure, saved
records, requirements, and relevant source when you need help investigating.

There is no framework companion skill to install and no separate AI judge.
You can still use the framework to compare your own domain skills: guidance
containing knowledge specific to the tasks your users need to complete.

This was a small experiment on one project and one model. It does **not** prove
that skills are useless, or that our skill generally made agents worse. It did
not demonstrate enough value to justify shipping ours.

**The useful conclusion was a simpler product: test whether an extra layer
deserves to exist, and be willing to remove it.**

## Explore the example

The runnable project is
[`examples/skill-dogfood`](https://github.com/sbroenne/pytest-skill-engineering/tree/main/examples/skill-dogfood).
Its [README](https://github.com/sbroenne/pytest-skill-engineering/blob/main/examples/skill-dogfood/README.md)
explains setup and explicitly selected live comparisons.

From the repository root, these commands run only the offline checks:

```powershell
cd examples\skill-dogfood
uv sync --frozen
uv run --frozen python -m pytest -q
```

Offline checks verify the sample and its checking code; they do not measure
agent performance. Live comparisons consume Copilot requests and execute
generated code, so run them only with authorization and suitable isolation.
A temporary folder and file-access checks are not a security sandbox.

The original skill text is retained only as historical test data under
`fixtures\retired-companion`. The sample turns it into a loadable skill inside
a temporary experiment folder. It is not an installable or maintained product.
New runs save new records rather than overwrite the original experiment.

## Experiment details

The details below explain how we ran the comparison. You do not need them
to get started with the framework.

### Conditions and complete results

The recorded runs used `gpt-5.6-luna`, Python 3.11.15, and GitHub Copilot SDK
1.0.15. These are the versions used then, not necessarily the current versions.
Writing and repair each had a 180-second limit and a 24-tool-call limit.
Each separate test execution had a 120-second limit and a four-tool-call limit;
the supplied application tool could run the workflow only once.

| Attempt | Without skill | With skill |
| --- | --- | --- |
| 1 | Application passed 42/42 checks; generated test expected wrong tax amounts | Application passed 29/42 checks; incorrect calculations remained |
| 2 | Application passed 42/42 checks and unchanged test passed | Application passed 29/42 checks; incorrect calculations remained |
| 3 | Application passed 29/42 checks; incorrect calculations remained | Application passed 42/42 checks; generated test expected wrong order amounts |

The simple case used 6 writing and 8 repair tool calls without the skill,
versus 9 and 11 with it. Across the harder task's three attempts per group,
the totals were 28 writing and 29 repair calls without the skill, versus 38
and 48 with it. Reading guidance counts as tool work. More calls alone do not
prove harm, and these counts are not model-request counts or billing estimates.

Each full attempt has one pytest outcome. Its writing and repair records are
not two independent attempts. Their usage excludes the separate sessions that
execute the generated test; it is not the cost of the whole task. Missing
usage or pricing is not measured zero.

### Excluded and interrupted runs

An earlier checkout batch was invalid: four of six attempts were blocked by our
test setup. It rejected a normal hashing import and did not provide input bytes
through the supplied test fixtures. We corrected those restrictions equally
for both groups, without changing the application requirements or expected
amounts, and ran the completed comparison reported above.

The excluded batch is not included in the result counts. Do not attribute its
setup failures to the skill.

Draft revision 1.0.1 began a separate three-pair comparison, but it was stopped
before completion. We make no improvement claim for that revision.

### What readers can reproduce

The linked sample contains the application, checks, and original guidance needed
to run a new comparison. The original generated execution records are not
distributed with this case study; the tables above summarize our observations.

A new run uses the current environment and produces its own execution records.
It is a new observation, not a promise of the same outcome or an exact copy of
the original run.

We ran the agent through the framework and used tests to check its actual
output. We did not ask another AI to judge the result or automatically repeat
failed attempts.
