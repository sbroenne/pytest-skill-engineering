"""Frozen checkout requirements and independent real-command checks."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

COLUMNS = ("order_id", "line_id", "unit_price_cents", "quantity", "discount_percent", "tax_percent")
ORDER_ROWS = (
    ("O100", "A", "5", "5", "50", "10"),
    ("O100", "B", "25", "1", "40", "20"),
)
OTHER_ROWS = (("O200", "C", "1250", "2", "10", "8"),)
CONFLICT_ROWS = (
    ("O100", "A", "5", "6", "50", "10"),
    ("O100", "B", "25", "1", "40", "20"),
)
INVOICE = {
    "order_id": "O100",
    "subtotal_cents": 50,
    "discount_cents": 23,
    "net_cents": 27,
    "tax_cents": 4,
    "total_cents": 31,
}
OTHER_INVOICE = {
    "order_id": "O200",
    "subtotal_cents": 2500,
    "discount_cents": 250,
    "net_cents": 2250,
    "tax_cents": 180,
    "total_cents": 2430,
}
TASK = "Run the checkout workflow for the supplied imported orders."
REQUIREMENTS = """# Imported-order checkout

The CLI supports preview, post, and ledger commands. Every command receives
--ledger PATH. Preview and post also receive --order CSV; post requires
--request-id KEY. CSV columns are order_id,line_id,unit_price_cents,quantity,
discount_percent,tax_percent. Files contain a nonempty single order with unique
nonempty line identifiers, integer nonnegative unit prices, positive integer
quantities, and finite discount and tax percentages in 0..100.

For each line, multiply unit price by quantity, round its discount to integer
cents with ties rounded upwards, subtract the rounded discount, then compute
tax on that discounted line amount with the same rounding rule. Sum the line
values. Output exactly order_id, subtotal_cents, discount_cents, net_cents,
tax_cents, total_cents, and replayed for preview/post; amounts are integer cents.

Preview must not create or change a ledger. Post persists one posting with
order_id, request_id, and the exact total_cents, plus requests[KEY] containing
fingerprint (SHA-256 of the CSV bytes) and invoice (the six invoice fields).
Reusing the same key and identical CSV bytes returns the original invoice with
replayed=true, without changing the ledger. Reusing a key with different bytes
must fail with exit code 2 and a stderr message, leaving all state unchanged.
New posts return replayed=false. The first valid post creates the initially
absent ledger. Ledger prints the exact on-disk object with postings and requests;
reading an absent ledger fails with exit code 2 without creating it.
Malformed orders fail with exit code 2 and a stderr message, without writing
state. Zero prices and 100 percent discounts are valid.

The customer workflow previews order.csv, posts it as checkout-1, repeats that
post, attempts conflict.csv under checkout-1, posts other.csv as checkout-2,
and reads the ledger. Test this workflow in one async test_checkout.py function.
The provided fixtures perform one framework session and expose actual command
receipts and on-disk snapshots. Record observations with record_property.
Only author the test; the customer executes it. Do not modify input files.
"""


@dataclass(slots=True, frozen=True)
class OrderCase:
    name: str
    rows: tuple[tuple[str, ...], ...]
    expected: tuple[int, int, int, int, int] | None


CASES = (
    OrderCase("discount-before-tax", ORDER_ROWS, (50, 23, 27, 4, 31)),
    OrderCase("ordinary-order", OTHER_ROWS, (2500, 250, 2250, 180, 2430)),
    OrderCase("tax-tie-up", (("O", "L", "5", "1", "0", "10"),), (5, 0, 5, 1, 6)),
    OrderCase(
        "per-line-rounding",
        (
            ("O", "L1", "5", "1", "0", "10"),
            ("O", "L2", "5", "1", "0", "10"),
        ),
        (10, 0, 10, 2, 12),
    ),
    OrderCase("zero-price", (("O", "L", "0", "1", "0", "10"),), (0, 0, 0, 0, 0)),
    OrderCase("full-discount", (("O", "L", "25", "1", "100", "20"),), (25, 25, 0, 0, 0)),
    OrderCase("negative-price", (("O", "L", "-1", "1", "0", "10"),), None),
    OrderCase("zero-quantity", (("O", "L", "5", "0", "0", "10"),), None),
    OrderCase("fractional-quantity", (("O", "L", "5", "1.5", "0", "10"),), None),
    OrderCase("nonfinite-discount", (("O", "L", "5", "1", "NaN", "10"),), None),
    OrderCase("excess-discount", (("O", "L", "5", "1", "101", "10"),), None),
    OrderCase("negative-discount", (("O", "L", "5", "1", "-1", "10"),), None),
    OrderCase("negative-tax", (("O", "L", "5", "1", "0", "-1"),), None),
    OrderCase("excess-tax", (("O", "L", "5", "1", "0", "101"),), None),
    OrderCase("nonfinite-tax", (("O", "L", "5", "1", "0", "Infinity"),), None),
    OrderCase(
        "duplicate-line",
        (
            ("O", "L", "5", "1", "0", "10"),
            ("O", "L", "5", "1", "0", "10"),
        ),
        None,
    ),
    OrderCase(
        "mixed-orders",
        (
            ("O1", "L1", "5", "1", "0", "10"),
            ("O2", "L2", "5", "1", "0", "10"),
        ),
        None,
    ),
    OrderCase("empty-order", (), None),
)


def order_csv(rows: tuple[tuple[str, ...], ...]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(COLUMNS)
    writer.writerows(rows)
    return stream.getvalue()


def criteria_digest() -> str:
    data = (REQUIREMENTS, INVOICE, OTHER_INVOICE, [(c.name, c.rows, c.expected) for c in CASES])
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def seed_checkout(project: Path) -> None:
    project.mkdir(parents=True, exist_ok=False)
    (project / "checkout_cli.py").write_bytes(
        Path(__file__).with_name("starter_checkout.py").read_bytes()
    )
    (project / "README.md").write_text(REQUIREMENTS, encoding="utf-8")
    for name, rows in (
        ("order.csv", ORDER_ROWS),
        ("other.csv", OTHER_ROWS),
        ("conflict.csv", CONFLICT_ROWS),
    ):
        (project / name).write_text(order_csv(rows), encoding="utf-8")


def run_checkout_command(
    project: Path, state: Path, command: str, order: Path | None, request_id: str | None
) -> dict[str, Any]:
    args = [
        sys.executable,
        "-E",
        "-s",
        str(project / "checkout_cli.py"),
        command,
        "--ledger",
        str(state),
    ]
    if order is not None:
        args.extend(["--order", str(order)])
    if request_id is not None:
        args.extend(["--request-id", request_id])
    env = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in {"SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL"}
    }
    run = subprocess.run(args, cwd=project, env=env, capture_output=True, text=True, timeout=10)
    output = json.loads(run.stdout) if run.returncode == 0 else None
    disk = json.loads(state.read_text(encoding="utf-8")) if state.is_file() else None
    return {
        "exit_code": run.returncode,
        "output": output,
        "stderr": run.stderr,
        "disk": disk,
    }


def observe_checkout(project: Path) -> dict[str, Any]:
    state_dir = project / "runtime" / uuid4().hex
    state_dir.mkdir(parents=True)
    ledger = state_dir / "ledger.json"
    steps = (
        ("preview", "preview", "order.csv", None),
        ("post", "post", "order.csv", "checkout-1"),
        ("repeat", "post", "order.csv", "checkout-1"),
        ("conflict", "post", "conflict.csv", "checkout-1"),
        ("second", "post", "other.csv", "checkout-2"),
        ("read", "ledger", None, None),
    )
    return {
        name: run_checkout_command(
            project,
            ledger,
            command,
            project / filename if filename is not None else None,
            key,
        )
        for name, command, filename, key in steps
    }


def workflow_checks(observed: dict[str, Any], project: Path) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def check(name: str, actual: Any, expected: Any) -> None:
        checks.append(
            {
                "name": name,
                "actual": actual,
                "expected": expected,
                "passed": exact_value(actual, expected),
            }
        )

    for step, invoice, replayed in (
        ("preview", INVOICE, False),
        ("post", INVOICE, False),
        ("repeat", INVOICE, True),
        ("second", OTHER_INVOICE, False),
    ):
        receipt = observed[step]
        check(f"{step}: exit", receipt["exit_code"], 0)
        check(f"{step}: output", receipt["output"], {**invoice, "replayed": replayed})
        check(f"{step}: stderr", receipt["stderr"], "")
    check("preview: no state creation", observed["preview"]["disk"], None)
    first = {
        "postings": [{"order_id": "O100", "request_id": "checkout-1", "total_cents": 31}],
        "requests": {
            "checkout-1": {
                "fingerprint": hashlib.sha256((project / "order.csv").read_bytes()).hexdigest(),
                "invoice": INVOICE,
            }
        },
    }
    check("post: exact durable state", observed["post"]["disk"], first)
    check("repeat: no mutation", observed["repeat"]["disk"], first)
    check("conflict: exit", observed["conflict"]["exit_code"], 2)
    check("conflict: error visible", bool(observed["conflict"]["stderr"]), True)
    check("conflict: no mutation", observed["conflict"]["disk"], first)
    final = {
        "postings": [
            *first["postings"],
            {
                "order_id": "O200",
                "request_id": "checkout-2",
                "total_cents": 2430,
            },
        ],
        "requests": {
            **first["requests"],
            "checkout-2": {
                "fingerprint": hashlib.sha256((project / "other.csv").read_bytes()).hexdigest(),
                "invoice": OTHER_INVOICE,
            },
        },
    }
    check("second: exact durable state", observed["second"]["disk"], final)
    check("read: exit", observed["read"]["exit_code"], 0)
    check("read: output equals real ledger", observed["read"]["output"], final)
    check("read: durable state", observed["read"]["disk"], final)
    return checks


def exact_value(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(
            exact_value(actual[name], value) for name, value in expected.items()
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            exact_value(left, right) for left, right in zip(actual, expected, strict=True)
        )
    return actual == expected


def inspect_checkout(project: Path) -> list[dict[str, Any]]:
    checks = workflow_checks(observe_checkout(project), project)
    for case in CASES:
        directory = project / "runtime" / uuid4().hex
        directory.mkdir(parents=True)
        order, ledger = directory / "order.csv", directory / "ledger.json"
        order.write_text(order_csv(case.rows), encoding="utf-8")
        actual = run_checkout_command(project, ledger, "preview", order, None)
        expected = (
            {
                "order_id": case.rows[0][0],
                **dict(
                    zip(
                        (
                            "subtotal_cents",
                            "discount_cents",
                            "net_cents",
                            "tax_cents",
                            "total_cents",
                        ),
                        case.expected,
                        strict=True,
                    )
                ),
                "replayed": False,
            }
            if case.expected is not None
            else None
        )
        passed = (
            actual["exit_code"] == 0
            and exact_value(actual["output"], expected)
            and actual["stderr"] == ""
            and actual["disk"] is None
            if expected is not None
            else actual["exit_code"] == 2 and bool(actual["stderr"]) and actual["disk"] is None
        )
        checks.append(
            {
                "name": case.name,
                "actual": actual,
                "expected": expected,
                "passed": passed,
            }
        )
    directory = project / "runtime" / uuid4().hex
    directory.mkdir(parents=True)
    missing = run_checkout_command(project, directory / "missing.json", "ledger", None, None)
    checks.append(
        {
            "name": "missing-ledger-errors",
            "actual": missing,
            "expected": "exit 2 and visible error",
            "passed": missing["exit_code"] == 2 and bool(missing["stderr"]),
        }
    )
    checks.append(
        {
            "name": "missing-ledger-not-created",
            "actual": missing["disk"],
            "expected": None,
            "passed": missing["disk"] is None,
        }
    )
    return checks
