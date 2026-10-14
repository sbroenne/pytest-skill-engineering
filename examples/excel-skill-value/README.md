# Excel: compare a task with and without a skill

This example sends one authored formatting task through native MCP tools and
`excelcli`, with and without the matching skill. Fixed checks reopen the saved
workbook through desktop Excel COM. The model cannot edit those checks or their
expected answers.

**This demonstrates the method, not the historical 48-case workload.** The
[case study](../../docs/use-cases/excel-skill-value.md) and
[receipt](evidence/real-world-1.0.3.json) describe broad skills. No paid run of
this small example or the new formatting skills is claimed.

## Choose what to run

| Mode | Purpose | Requirements |
| --- | --- | --- |
| Default offline tests | Check example logic without desktop or model calls | Repository Python environment |
| `--prove-excel` | Prove the checker rejects wrong workbooks and accepts correct formatting | Windows, PowerShell 7, desktop Excel, and built ExcelMcp executables |
| `--run-live` | Execute four paid skill/no-skill cases | The desktop requirements plus Copilot access and `gpt-6.1-sol` |

## Set up from this directory

This directory uses the repository's local source and root `uv.lock`, not a
separate dependency environment. GitHub-hosted runners do not supply desktop
Excel. Run the commands below from `examples/excel-skill-value`.

```powershell
uv sync --project ..\.. --frozen --all-extras
uv run --project ..\.. --frozen python -m pytest -q
```

For the desktop checker proof, configure the executables and opt in:

```powershell
$env:EXCEL_MCP_EXECUTABLE = 'C:\Tools\ExcelMcp\Sbroenne.ExcelMcp.McpServer.exe'
$env:EXCEL_CLI_EXECUTABLE = 'C:\Tools\ExcelMcp\excelcli.exe'
uv run --project ..\.. --frozen python -m pytest tests\offline\test_checks.py --prove-excel -q
```

The opt-in proof rejects the unformatted input, accepts proper formatting, and
rejects a changed fractional rate in a real workbook.

## Explicit paid comparison

```powershell
gh auth login --hostname github.com
uv run --project ..\.. --frozen python -m pytest tests\live --run-live --paid-limit 4 --receipt-dir receipts\new-broad-run --aitest-json receipts\new-broad-native.json -v
```

Four selected cases reserve four attempts before model execution. Existing
receipt directories are rejected. Supply `--prior-attempts` for a resumed
allowance and never exceed the user's authorized ceiling, at most 100.
This example makes one attempt per case, with no retries or judging model.
Do not add iterations; the example rejects multiplicative iteration counts.
Every paid smoke test or rerun counts, including interrupted executions.

## Select the skill profile

The default `--skill-profile broad` uses frozen `fixtures\excel-mcp` and
`fixtures\excel-cli`. These reproduce the historical *guidance*, not all
historical tasks. Git preserves these fixture bytes without line-ending
conversion so their hashes match the historical receipt on every checkout.
To test the new, unproven narrow skills instead:

```powershell
$env:EXCEL_MCP_SKILL_DIRECTORY = 'C:\PreparedSkills\excel-mcp-report-formatting'
$env:EXCEL_CLI_SKILL_DIRECTORY = 'C:\PreparedSkills\excel-cli-report-formatting'
uv run --project ..\.. --frozen python -m pytest tests\live --run-live --skill-profile formatting --paid-limit 4 --receipt-dir receipts\new-formatting-run --aitest-json receipts\new-formatting-native.json -v
```

Do not pool a formatting-profile run with the historical broad-skill result.
No paid run of the new formatting skills is established by this example.

## What the comparison holds fixed

Within each entry point the request, tools, permissions, model, and budgets
are unchanged between conditions. The CLI is one custom SDK tool that accepts
an argument array and runs without a shell. Native MCP schemas are unchanged.
The workspace tool can only read the task and skill directories and write
non-executable task inputs. No expected result is put in the task directory.

The public skill loader and no-send SDK discovery run before paid execution,
including exact treatment names/source paths and empty baselines. Returned
execution is saved before verification.

## Read evidence and handle cleanup

Discovery, skill reads, nullable token usage, and independent verification are
separate fields. `passed: true` means
the workbook check passed, not merely that the agent said it finished.
There is no claimed live event journal. `reserved` or `verifying` records left
by interruption are incomplete, not free attempts or verified successes.

Raw native evidence contains local paths and tool outputs; keep it private.
Only the compact historical receipt is intended for publication. Cleanup closes
only the exact test-owned workbook without saving, then stops the private CLI
pipe. It does not stop a user's default service or kill Excel by name.

The authored Python/PowerShell example and frozen ExcelMcp guidance are MIT
licensed; preserve the included licence. No SpreadsheetBench content ships here.
