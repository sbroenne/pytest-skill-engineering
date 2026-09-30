"""Fixed application criteria and independent subprocess checks."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True, frozen=True)
class InvoiceCase:
    subtotal: str
    tax_percent: str
    expected: tuple[int, int, int] | None


CASES = (
    InvoiceCase("12.50", "8", (1250, 100, 1350)),
    InvoiceCase("0.05", "10", (5, 1, 6)),
    InvoiceCase("0.25", "10", (25, 3, 28)),
    InvoiceCase("0.15", "10", (15, 2, 17)),
    InvoiceCase("0.00", "10", (0, 0, 0)),
    InvoiceCase("19.99", "0", (1999, 0, 1999)),
    InvoiceCase("-1", "10", None),
    InvoiceCase("1.005", "10", None),
    InvoiceCase("1", "101", None),
    InvoiceCase("1", "-1", None),
    InvoiceCase("NaN", "10", None),
    InvoiceCase("Infinity", "10", None),
    InvoiceCase("1", "NaN", None),
    InvoiceCase("1", "Infinity", None),
    InvoiceCase("not-money", "10", None),
    InvoiceCase("1", "not-tax", None),
)
INVOICE_TASK = "Use the invoice tool for a subtotal of $0.05 with 10 percent tax."
REQUIREMENTS = """# Invoice project

The command is: python invoice_cli.py --subtotal AMOUNT --tax-percent PERCENT
Return one JSON object with exactly subtotal_cents, tax_cents, total_cents.
All output amounts must be integer cents. Compute tax on the subtotal, rounding
to the nearest cent with half a cent rounded upwards. Add the rounded tax to
the subtotal. Zero amounts and zero tax are valid.
Reject negative subtotals, fractional-cent subtotals, tax outside 0..100,
non-finite values, and non-numeric input with exit code 2 and a stderr message.

Tests use the supplied invoice_eval and invoice_task fixtures with the ordinary
copilot_eval fixture. invoice_task requests a $0.05 subtotal with 10 percent tax.
The separate invoice_output fixture is a callable taking no arguments; request
it as a test parameter and call it to obtain the actual CLI response, not a
model's claim. Write one async test in test_invoice.py that
detects incorrect rounding for this task and records its check with record_property.
Do not create conftest.py, change the project, execute tests, or install packages.
"""


def run_invoice(project: Path, subtotal: str, tax_percent: str) -> subprocess.CompletedProcess[str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in {"SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL"}
    }
    return subprocess.run(
        [
            sys.executable,
            "-I",
            str(project / "invoice_cli.py"),
            "--subtotal",
            subtotal,
            "--tax-percent",
            tax_percent,
        ],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )


def read_invoice(stdout: str) -> dict[str, int]:
    data = json.loads(stdout)
    if not isinstance(data, dict) or set(data) != {"subtotal_cents", "tax_cents", "total_cents"}:
        raise ValueError("Invoice output has the wrong schema")
    if any(type(value) is not int for value in data.values()):
        raise ValueError("Invoice output amounts must be integer cents")
    return data


def inspect_cli(project: Path) -> list[dict[str, Any]]:
    observed: list[dict[str, Any]] = []
    for case in CASES:
        run = run_invoice(project, case.subtotal, case.tax_percent)
        expected = (
            dict(zip(("subtotal_cents", "tax_cents", "total_cents"), case.expected, strict=True))
            if case.expected is not None
            else None
        )
        actual = read_invoice(run.stdout) if run.returncode == 0 else None
        passed = (
            run.returncode == 0 and not run.stderr and actual == expected
            if expected is not None
            else run.returncode == 2 and bool(run.stderr) and not run.stdout
        )
        observed.append(
            {
                "subtotal": case.subtotal,
                "tax_percent": case.tax_percent,
                "exit_code": run.returncode,
                "expected": expected,
                "actual": actual,
                "stderr": run.stderr,
                "passed": passed,
            }
        )
    return observed


def seed_application(project: Path) -> None:
    project.mkdir(parents=True, exist_ok=False)
    (project / "invoice_cli.py").write_bytes(Path(__file__).with_name("starter.py").read_bytes())
    (project / "README.md").write_text(REQUIREMENTS, encoding="utf-8")
