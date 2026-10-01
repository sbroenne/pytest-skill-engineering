"""The starting invoicing application copied into each disposable project."""

from __future__ import annotations

import argparse
import json
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation


def invoice(subtotal: str, tax_percent: str) -> dict[str, int]:
    try:
        amount = Decimal(subtotal)
        rate = Decimal(tax_percent)
    except InvalidOperation as exc:
        raise ValueError("Amounts must be decimal numbers") from exc
    if not amount.is_finite() or not rate.is_finite():
        raise ValueError("Amounts must be finite")
    if amount < 0 or not 0 <= rate <= 100 or amount * 100 != (amount * 100).to_integral():
        raise ValueError("Invalid subtotal or tax percentage")
    tax = (amount * rate / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    return {
        "subtotal_cents": int(amount * 100),
        "tax_cents": int(tax * 100),
        "total_cents": int((amount + tax) * 100),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subtotal", required=True)
    parser.add_argument("--tax-percent", required=True)
    args = parser.parse_args()
    try:
        payload = invoice(args.subtotal, args.tax_percent)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
