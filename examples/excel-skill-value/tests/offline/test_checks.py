from __future__ import annotations

import copy
import sys

import pytest
from checks import budget, check, workbook


def snapshots():
    before = {
        "sheet": "Report",
        "sheetCount": 1,
        "tables": 0,
        "shapes": 0,
        "names": 0,
        "calculation": -4105,
        "cells": [],
    }
    for row in range(1, 8):
        for column in ("A", "B", "C"):
            before["cells"].append(
                {
                    "address": f"{column}{row}",
                    "value": None,
                    "formula": None,
                    "format": "General",
                    "bold": False,
                    "text": "",
                }
            )
    after = copy.deepcopy(before)
    for cell in after["cells"]:
        column, row = cell["address"][0], int(cell["address"][1:])
        if row == 1:
            cell["bold"] = True
        elif row in range(2, 6) and column in ("B", "C"):
            cell["format"] = "$0.00" if column == "B" else "0.00%"
            cell["text"] = "$1.00" if column == "B" else "45.00%"
    return before, after


def test_accepts_formatting_and_rejects_unformatted_or_changed_state():
    before, after = snapshots()
    check(before, after)
    with pytest.raises(AssertionError):
        check(before, before)
    for field in ("value", "formula", "format"):
        wrong = copy.deepcopy(after)
        wrong["cells"][-1][field] = "changed"
        with pytest.raises(AssertionError):
            check(before, wrong)
    after["cells"][4]["text"] = "####"
    with pytest.raises(AssertionError):
        check(before, after)


def test_reserved_attempt_budget():
    budget(4, 46, 100)
    for planned, prior, ceiling in ((4, 1, 4), (1, -1, 4), (1, 0, 101)):
        with pytest.raises(ValueError):
            budget(planned, prior, ceiling)


def test_real_excel_checker_proof(request, tmp_path):
    if not request.config.getoption("--prove-excel"):
        pytest.skip("Desktop Excel proof requires --prove-excel")
    if sys.platform != "win32":
        pytest.skip("Desktop Excel requires Windows")
    path = tmp_path / "authored.xlsx"
    workbook("create", path)
    before = workbook("inspect", path)
    with pytest.raises(AssertionError):
        check(before, before)
    workbook("format", path)
    check(before, workbook("inspect", path))
    workbook("mutate", path)
    with pytest.raises(AssertionError):
        check(before, workbook("inspect", path))
