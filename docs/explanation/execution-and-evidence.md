# Execution, evidence, and investigation

Running a session, verifying the task, and explaining a failure are three
different jobs.

| Job | Owner | Output |
| --- | --- | --- |
| Execute | Framework | Copilot session, controls, usage, and captured events |
| Verify | Your pytest test | Assertions against actual output and the pytest outcome |
| Investigate | Your coding agent or a human | An explanation based on evidence, requirements, and source |

The framework saves execution and pytest results as JSON. Reading that JSON
does not start another model session or require authentication.

## What evidence can establish

`result.success` records execution completion. Tool calls show what was selected,
with which arguments. Completion flags and capture errors show whether those
observed calls have complete evidence. Usage describes the recorded execution.

Those facts are useful for diagnosis, but none establishes that the requested
application state exists. For example, a completed `save` call is not a check
that the file contains the requested values.

Check files, output schemas, exact values, fixture state, or returned operation
results with ordinary assertions. Save useful observations with
`record_property` before asserting so failed checks remain inspectable.
Properties record evidence; they do not change pytest's verdict by themselves.

Missing output is not empty output, unavailable usage is not zero usage, and
missing pricing is not zero cost. Preserve these distinctions when interpreting
the result. See the [result reference](../reference/result.md).

## Why there is no separate judge

A transcript alone may not reveal whether the cause was a tool bug, wrong test,
permission denial, or ambiguous requirement. Your existing coding agent has
access to the source and environment needed to investigate that distinction.
An extra framework-owned judge would add cost without independent verification.

Subjective review can still be useful, but label it advice rather than a
measured result. Version 1.0 removed built-in judging and report advice; the
[migration guide](../migration.md) covers the retired APIs.

## Comparisons need discipline

Keep inputs and criteria fixed, vary one factor, and check both sides.
`ab_run` isolates working directories, not shared desktops, external services,
or all inherited environment state. Its two entries have one shared pytest
outcome. Repetitions and representative cases matter more than an eloquent
explanation of a single run.

Record each side's verification separately. The framework does not select a
winner: interpreting a difference requires considering sample size, incomplete
evidence, and missing prices. A shared pytest outcome cannot establish
independent per-side pass rates or a causal improvement.
