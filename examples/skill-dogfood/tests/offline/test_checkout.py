"""Application and observation contracts; these do not measure skill effectiveness."""

from __future__ import annotations

from pathlib import Path

import pytest
from skill_dogfood.checkout import (
    CASES,
    criteria_digest,
    exact_value,
    inspect_checkout,
    observe_checkout,
    seed_checkout,
)


def corrected_application(project: Path) -> None:
    source = (project / "checkout_cli.py").read_text(encoding="utf-8")
    source = source.replace("ROUND_HALF_EVEN", "ROUND_HALF_UP")
    source = source.replace(
        "tax = rounded(Decimal(subtotal) * rate / 100)",
        "tax = rounded(Decimal(net) * rate / 100)",
    )
    source = source.replace(
        '        path.write_text(json.dumps(empty), encoding="utf-8")',
        "        return empty",
    )
    source = source.replace(
        '    if command == "ledger":\n        return state',
        '    if command == "ledger":\n'
        "        if not ledger.exists():\n"
        '            raise ValueError("Ledger does not exist")\n'
        "        return state",
    )
    source = source.replace(
        '    replayed = existing is not None and existing["fingerprint"] == fingerprint',
        "    if existing is not None:\n"
        '        if existing["fingerprint"] != fingerprint:\n'
        '            raise ValueError("Conflicting request")\n'
        '        return {**existing["invoice"], "replayed": True}\n'
        "    replayed = False",
    )
    source = source.replace(
        '"total_cents": invoice["total_cents"] // 100',
        '"total_cents": invoice["total_cents"]',
    )
    (project / "checkout_cli.py").write_text(source, encoding="utf-8")


def test_seeded_checkout_exposes_interacting_state_and_money_faults(tmp_path: Path) -> None:
    project = tmp_path / "consumer"
    seed_checkout(project)
    observed = observe_checkout(project)
    assert observed["preview"]["disk"] is not None
    assert observed["post"]["output"]["total_cents"] == 35
    assert observed["post"]["disk"]["postings"][0]["total_cents"] == 0
    assert observed["repeat"]["output"]["replayed"] is True
    assert len(observed["repeat"]["disk"]["postings"]) == 2
    assert observed["conflict"]["exit_code"] == 0
    checks = inspect_checkout(project)
    assert len(checks) == 42
    assert any(not check["passed"] for check in checks)


def test_fixed_checkout_checks_accept_the_complete_correct_workflow(tmp_path: Path) -> None:
    project = tmp_path / "consumer"
    seed_checkout(project)
    corrected_application(project)
    digest = criteria_digest()
    checks = inspect_checkout(project)
    assert len(checks) == 42
    assert all(check["passed"] for check in checks), checks
    assert criteria_digest() == digest


@pytest.mark.parametrize("actual", [True, 1.0, "1"])
def test_amount_schema_does_not_accept_bool_float_or_string(actual: object) -> None:
    assert not exact_value({"amount": actual}, {"amount": 1})


def test_fixed_cases_are_not_derived_from_the_application() -> None:
    assert CASES[0].expected == (50, 23, 27, 4, 31)
    assert CASES[1].expected == (2500, 250, 2250, 180, 2430)
    assert len(criteria_digest()) == 64
