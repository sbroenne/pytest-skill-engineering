"""Deterministic coverage for report fixture provenance manifest."""

from __future__ import annotations

import json
from pathlib import Path

from pytest_skill_engineering.cli import load_suite_report
from tests.fixtures.report_fixtures import (
    ALL_REPORT_SPECS,
    DEMO_SPECS,
    FIXTURE_NAMES,
    FIXTURE_SPECS,
)


def test_fixture_manifest_covers_all_checked_in_fixture_jsons() -> None:
    fixture_dir = Path(__file__).parents[1] / "fixtures" / "reports"
    checked_in = sorted(path.stem for path in fixture_dir.glob("*.json"))
    assert checked_in == sorted(FIXTURE_NAMES)


def test_demo_manifest_covers_hero_report() -> None:
    assert [spec.name for spec in DEMO_SPECS] == ["hero-report"]


def test_each_manifest_entry_has_a_generator_source_and_loadable_json() -> None:
    for spec in ALL_REPORT_SPECS:
        assert spec.generator_source.startswith("tests.fixtures.report_fixtures:")
        data = json.loads(spec.json_path.read_text(encoding="utf-8"))
        assert data["schema_version"] == "3.0"
        report, insights = load_suite_report(spec.json_path)
        assert report.tests
        assert insights is not None


def test_fixture_manifest_is_name_unique() -> None:
    names = [spec.name for spec in FIXTURE_SPECS]
    assert len(names) == len(set(names))
