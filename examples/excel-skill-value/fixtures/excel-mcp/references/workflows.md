# Choosing an Excel workflow

These are alternatives, not steps to run on every workbook. Read only the
guide needed for an unresolved decision.

| Need | Surface |
|------|---------|
| Existing cell values or formulas | [Ranges](range.md); no query/model setup |
| Direct CSV or legacy HTML import | [QueryTables](querytable.md) |
| Modern imports or stored transformations | [Power Query](powerquery.md) |
| Aggregation over loaded model data | [Data Model/DAX](datamodel.md) |
| Cross-table filtering | `datamodel_relationship` (MCP) / `datamodelrelationship` (CLI); load tables first |
| Interactive summary | [PivotTables](pivottable.md); model setup only when needed |
| A chart following PivotTable fields/filters | [Live PivotCharts](chart.md), not a chart of displayed cells |
| Requested report layout | [Optional formatting](report-formatting.md) |

## CLI batch jobs

MCP has no equivalent batch tool: await dependent calls. CLI batch avoids
repeated process startup for a known sequence. It is not a transaction.
Use individual commands when the next step needs inspection.

Batch arguments use Service camel-case names, not CLI flags. Check every NDJSON success
flag, the exit status, and expected command count. Use `--stop-on-error`;
otherwise errors do not stop later commands. Keep save/close outside the batch.

This example assumes authorized edits and save/close of a workbook opened
exclusively for the job. `$path` is the supplied path, `Sales` already exists,
and target cells have been inspected. `commands.json` is a job-owned file.
For a reused session, report partial work without discarding earlier edits.


Normal daemon shutdown may save remaining sessions; it is not failure cleanup.
Report cleanup failures rather than killing Excel or claiming rollback.
See [recovery](behavioral-rules.md#sessions-and-failures).
