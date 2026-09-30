# Execution, evidence, and investigation

The framework and your coding agent have different jobs.

The framework executes the task, enforces configured controls, captures evidence,
and saves JSON alongside ordinary pytest output. Your test owns the output checks. Your existing
coding agent investigates source and evidence, proposes changes, and helps you
rerun the relevant cases.

## Why no separate AI analysis layer?

An adviser receiving a shortened report has less context than the coding agent
already working in the repository. It cannot independently establish the cause
of a failure from a transcript alone. Its prose can sound authoritative while
misdiagnosing an environment problem, a wrong test, or a bug in the tool.

Another model session also adds cost and a failure point unrelated to whether
the task under test passed. Reading captured results should not need another paid call.

Version 1.0 therefore removes built-in judging, answer scoring, report advice,
dashboards, rankings, and automatic skill refinement. The existing coding agent
investigates source and evidence without another framework-owned guidance layer.
We also tested and removed our proposed companion skill; the
[case study](../use-cases/companion-skill.md) explains why.

## What evidence can establish

`result.success` records session completion. Calls show which tool and arguments
were selected. Completion flags and errors show what was captured. Usage records
describe the observed execution. None of these automatically establishes that
the user's desired state exists.

Use ordinary assertions against files, output schemas, exact values, fixture
state, or returned operation results. Save those checks with `record_property`.
Subjective review can still be useful, but label it advice, not a measured pass
rate or a framework verdict.

## Comparisons need discipline

Keep inputs and criteria fixed, vary one factor, and check both sides.
`ab_run` isolates working directories, not shared desktops, external services,
or all inherited environment state. Its two entries have one shared pytest
outcome. Repetitions and representative cases matter more than an eloquent
explanation of a single run.

The framework does not select a winner. Your coding agent must consider sample
size, side-specific verification, incomplete evidence, and missing prices before
drawing conclusions from the observations.
