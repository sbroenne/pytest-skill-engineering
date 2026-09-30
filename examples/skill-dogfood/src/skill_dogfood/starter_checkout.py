"""A persistent checkout CLI for imported orders."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

COLUMNS = ["order_id", "line_id", "unit_price_cents", "quantity", "discount_percent", "tax_percent"]


def rounded(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_HALF_EVEN))


def calculate(path: Path) -> dict[str, Any]:
    totals = {
        "subtotal_cents": 0,
        "discount_cents": 0,
        "net_cents": 0,
        "tax_cents": 0,
        "total_cents": 0,
    }
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != COLUMNS:
            raise ValueError("Incorrect order columns")
        rows = list(reader)
    if not rows:
        raise ValueError("An order must contain lines")
    order_id = rows[0]["order_id"]
    if not order_id or any(row["order_id"] != order_id for row in rows):
        raise ValueError("Each file must contain exactly one order")
    seen: set[str] = set()
    for row in rows:
        line_id = row["line_id"]
        if not line_id or line_id in seen or set(row) != set(COLUMNS):
            raise ValueError("Line identifiers must be unique and rows complete")
        seen.add(line_id)
        price, quantity = int(row["unit_price_cents"]), int(row["quantity"])
        discount, rate = Decimal(row["discount_percent"]), Decimal(row["tax_percent"])
        if (
            price < 0
            or quantity <= 0
            or not discount.is_finite()
            or not rate.is_finite()
            or not 0 <= discount <= 100
            or not 0 <= rate <= 100
        ):
            raise ValueError("Invalid price, quantity, discount, or tax")
        subtotal = price * quantity
        deduction = rounded(Decimal(subtotal) * discount / 100)
        net = subtotal - deduction
        tax = rounded(Decimal(subtotal) * rate / 100)
        values = (subtotal, deduction, net, tax, net + tax)
        for name, value in zip(totals, values, strict=True):
            totals[name] += value
    return {"order_id": order_id, **totals}


def load_ledger(path: Path) -> dict[str, Any]:
    if not path.exists():
        empty = {"postings": [], "requests": {}}
        path.write_text(json.dumps(empty), encoding="utf-8")
    data = json.loads(path.read_text(encoding="utf-8"))
    if set(data) != {"postings", "requests"}:
        raise ValueError("Incorrect ledger schema")
    return data


def execute(
    command: str, order: Path | None, ledger: Path, request_id: str | None
) -> dict[str, Any]:
    state = load_ledger(ledger)
    if command == "ledger":
        return state
    if order is None:
        raise ValueError("An order file is required")
    invoice = calculate(order)
    if command == "preview":
        return {**invoice, "replayed": False}
    if not request_id:
        raise ValueError("A request identifier is required")
    fingerprint = hashlib.sha256(order.read_bytes()).hexdigest()
    existing = state["requests"].get(request_id)
    replayed = existing is not None and existing["fingerprint"] == fingerprint
    state["postings"].append(
        {
            "order_id": invoice["order_id"],
            "request_id": request_id,
            "total_cents": invoice["total_cents"] // 100,
        }
    )
    state["requests"][request_id] = {"fingerprint": fingerprint, "invoice": invoice}
    ledger.write_text(json.dumps(state), encoding="utf-8")
    return {**invoice, "replayed": replayed}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["preview", "post", "ledger"])
    parser.add_argument("--order", type=Path)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--request-id")
    args = parser.parse_args()
    try:
        output = execute(args.command, args.order, args.ledger, args.request_id)
    except (ValueError, InvalidOperation) as exc:
        parser.error(str(exc))
    print(json.dumps(output))


if __name__ == "__main__":
    main()
