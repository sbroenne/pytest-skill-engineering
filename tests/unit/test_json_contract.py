"""Syrupy snapshot tests for JSON report schema contract.

These tests ensure the JSON serialization format stays stable. Any change to
field names, types, nesting, or structure will show up as a snapshot diff,
preventing accidental breaking changes to the report format.

Snapshots capture the SHAPE (keys + value types) rather than content,
so they're stable across data changes but catch structural regressions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from pytest_skill_engineering.cli import load_suite_report
from pytest_skill_engineering.core.serialization import serialize_dataclass

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "reports"

FIXTURE_NAMES = [
    "01_single_agent",
    "02_multi_agent",
    "03_multi_agent_sessions",
    "04_agent_selector",
]


def _extract_schema(obj: Any) -> Any:
    """Extract the structural schema from a JSON-like object.

    Returns a compact representation showing keys and value types:
    - dicts → {key: schema(value)} with sorted keys
    - lists → [schema(first_item)] or ["<empty>"]
    - scalars → type name ("str", "int", "float", "bool", "NoneType")
    """
    if isinstance(obj, dict):
        return {k: _extract_schema(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        if not obj:
            return ["<empty>"]
        return [_extract_schema(obj[0])]
    return type(obj).__name__


class TestJsonSchemaContract:
    """Snapshot the JSON schema shape for each fixture.

    If a field is added, removed, renamed, or its type changes,
    these snapshots will break — which is the desired behavior.
    """

    @pytest.mark.parametrize("fixture_name", FIXTURE_NAMES)
    def test_json_schema_shape(self, fixture_name: str, snapshot: SnapshotAssertion) -> None:
        """Schema shape should match the stored snapshot."""
        json_path = FIXTURES_DIR / f"{fixture_name}.json"
        data = json.loads(json_path.read_text(encoding="utf-8"))
        schema = _extract_schema(data)
        assert schema == snapshot


class TestRoundTrip:
    """Verify that deserialize → re-serialize produces the same schema."""

    @pytest.mark.parametrize("fixture_name", FIXTURE_NAMES)
    def test_round_trip_preserves_schema(
        self, fixture_name: str, snapshot: SnapshotAssertion
    ) -> None:
        """Deserialize from JSON, re-serialize, verify schema matches."""
        json_path = FIXTURES_DIR / f"{fixture_name}.json"
        report, _insights = load_suite_report(json_path)
        re_serialized = serialize_dataclass(report)
        schema = _extract_schema(re_serialized)
        assert schema == snapshot


class TestSchemaVersion:
    """Schema version field must be present and match expected value."""

    @pytest.mark.parametrize("fixture_name", FIXTURE_NAMES)
    def test_has_schema_version(self, fixture_name: str) -> None:
        json_path = FIXTURES_DIR / f"{fixture_name}.json"
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert "schema_version" in data
        assert data["schema_version"] == "3.0"


class TestInsightsContract:
    """Insights section has required fields when present."""

    @pytest.mark.parametrize("fixture_name", FIXTURE_NAMES)
    def test_insights_structure(self, fixture_name: str) -> None:
        json_path = FIXTURES_DIR / f"{fixture_name}.json"
        data = json.loads(json_path.read_text(encoding="utf-8"))
        if "insights" in data and isinstance(data["insights"], dict):
            insights = data["insights"]
            assert "markdown_summary" in insights
            assert "cost_usd" in insights
            assert "tokens_used" in insights
            assert "cached" in insights
