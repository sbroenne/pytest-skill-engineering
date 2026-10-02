from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent


def workbook(action: str, path: Path) -> dict[str, Any] | None:
    completed = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(ROOT / "Workbook.ps1"),
            "-Action",
            action,
            "-Path",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=90,
    )
    return json.loads(completed.stdout) if action == "inspect" else None


def check(before: dict[str, Any] | None, after: dict[str, Any] | None) -> None:
    assert before is not None and after is not None, "Missing workbook inspection"
    for field in ("sheet", "sheetCount", "tables", "shapes", "names", "calculation"):
        assert after[field] == before[field], f"Changed {field}"
    original = {cell["address"]: cell for cell in before["cells"]}
    actual = {cell["address"]: cell for cell in after["cells"]}
    assert actual.keys() == original.keys(), "Changed inspected cells"
    for address, previous in original.items():
        assert actual[address]["value"] == previous["value"], f"Changed value at {address}"
        assert actual[address]["formula"] == previous["formula"], f"Changed formula at {address}"
        if address not in {f"{column}{row}" for column in ("B", "C") for row in range(2, 6)}:
            assert actual[address]["format"] == previous["format"], (
                f"Changed unrelated format at {address}"
            )
    for column in ("A", "B", "C"):
        assert actual[f"{column}1"]["bold"] is True, "Header is not bold"
    for row in range(2, 6):
        money, rate = actual[f"B{row}"], actual[f"C{row}"]
        assert "$" in money["format"] and "0.00" in money["format"], (
            "Missing two-decimal USD format"
        )
        assert "%" in rate["format"], "Missing percent format"
        assert "%" not in money["format"], "Amount formatted as a percent"
        assert "####" not in money["text"] + rate["text"], "Numbers are unreadable"
    assert "45" in actual["C2"]["text"], "Fractional rate is not displayed as 45%"


def budget(planned: int, prior: int, ceiling: int) -> None:
    if not 1 <= ceiling <= 100 or prior < 0 or planned < 0 or planned + prior > ceiling:
        raise ValueError("Selected and prior attempts exceed the authorized ceiling")
