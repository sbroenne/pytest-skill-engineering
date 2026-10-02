# Do broad Excel skills help an agent?

ExcelMcp tested whether a skill improved an agent's use of two equal product
entry points: native MCP tools and `excelcli`. The comparison found no
correctness advantage on the selected tasks, while recorded tokens increased.
Useful documentation and useful automatically loaded instructions are not
the same thing.

## What was compared

The completed comparison used public **pytest-skill-engineering 1.0.3**,
`github-copilot-sdk` **1.0.16**, `mcp` **2.2.0**, and **gpt-6.1-sol**.
Six tasks, two entry points, skill/no-skill conditions, and two repetitions
produced **48 unique cases**. Requests, tools, permissions, fixtures, model,
and budgets were held constant within each entry point. Only the matching
skill's availability changed.

Four tasks used pinned public SpreadsheetBench workbooks: grouped transaction
totals, monthly inventory comparison, last-record deduplication, and conditional
date/text totals. Two authored tasks repaired Power Query and refreshed an
existing Data Model/DAX/PivotTable/PivotChart report. This was an adapted pilot,
not an official SpreadsheetBench score.

The input revision was `49b73a94775fb489063f60ca1865e3a650079a79`; the archive
SHA256 was `10ef893dd29cb13ab97143ea787e68cdc9574a13873ab9a54e50b31dc03fc949`.
SpreadsheetBench declares CC BY-SA 4.0. No upstream workbook, answer file, or
adapted benchmark instruction is included in this example.

## Evidence, not completion claims

Fixed checks ran outside the model-writable task directory. They reopened
saved workbooks through desktop Excel COM, checked every requested result,
and protected unrelated values, formulas, formats, calculation mode, and
named analysis objects. Formula cases also changed inputs to reject constants
that happened to match the original answer.

Before paying for comparisons, checker proofs rejected unchanged or deliberately
incorrect workbooks. Model prose and successful tool calls alone could not pass.
Missing correlated completion evidence was a capture failure, not a task success.

An early lesson was that supplying a skill directory did **not** establish
availability. In the SDK's isolated `empty` mode, skills needed explicit
`enable_skills=True`. Each real directory was validated with public `load_skill`,
then SDK discovery checked the exact enabled name and resolved source path.
Discovery probes forbade `send` and `send_and_wait`; they made no model requests.
Actual treatment calls separately established that the skills were read.

## Measured result

| Entry point | Without skill | With broad skill | Correct cases per condition |
|---|---:|---:|---:|
| MCP | 4,312,584 recorded tokens | 5,320,118 recorded tokens | 12/12 |
| CLI | 1,794,556 recorded tokens | 3,092,967 recorded tokens | 12/12 |

Recorded token usage increased **23.4% for MCP** and **72.4% for CLI**.
All **24 treatment cases read the matching skill**. This was not a
missing-treatment result.

The resumed round reserved **50 of 100 authorized attempts**: 48 verified
unique cases and two interrupted reservations. Interrupted usage is unknown,
excluded from those percentages, and never represented as zero. Earlier
package-1.0.2 comparisons had a separate allowance and are not pooled here.

The [compact receipt](https://github.com/sbroenne/pytest-skill-engineering/blob/main/examples/excel-skill-value/evidence/real-world-1.0.3.json)
preserves case metrics, frozen hashes, and invocation boundaries without private
workbook paths or raw conversations.

## Limits and the recording problem

One capable model, six tasks, and two repetitions do not establish universal
skill value. Repeated cases reused input contents; public cases may already be
known to the model. Equal success creates a ceiling: there is no observed
correctness difference to estimate.

The runner resumed across three invocations and a recorder-code change.
Two interrupted runners returned no final result; their cause was not proven.
The recorder later saved returned execution before workbook verification and
used atomic attempt snapshots. Those protections worked. The configured public
`on_event` callback received **zero live events** in the actual comparison.
Mocked callback tests are not evidence that live journaling works.

## Product decision

The broad default skills were replaced by two optional report-formatting
skills. General workflows, limitations, recovery, and command references moved
to ordinary documentation, with the existing website addresses preserved.
The `skills` directory now contains actual skills, not a documentation corpus.
Native schemas/help and recovery messages remain responsible for product
behavior and essential safety.

This decision is supported for the tested model and tasks. It does **not**
establish that the new narrow skills help. Their separate, unrun comparison has
positive formatting tasks and ordinary non-trigger tasks; it checks selection,
workbook correctness, and usage separately.

## Small runnable example

The [Excel example](https://github.com/sbroenne/pytest-skill-engineering/tree/main/examples/excel-skill-value) demonstrates the
method with one self-authored workbook task, both entry points, and paired
skill/no-skill cases using the public 1.x API. Its frozen broad fixtures match
the historical manifests. A formatting-profile run instead uses explicitly
supplied prepared narrow skills and must not be pooled with the broad result.

The example does **not** reproduce the full 48-case workload or promise the
same token percentages. Default tests are offline. Desktop-Excel checker
proofs and paid live comparisons are separate commands. No new live example
run was used to support the historical conclusion.
